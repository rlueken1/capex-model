"""Hook 7 under `tx.model = dcpf` (formulation 7.4a.7, 7.4a.12): section 4 with price components (islands joined by free
DC links), bus-local classes in congested component-hours, then CONGESTION_LOOP weights alpha (and an interval, with the
S2 storage rows, when they are not computable)."""
from __future__ import annotations

import dataclasses
from typing import NamedTuple

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from ..solver import make_solver
from . import loop
from .duals import Economics
from .network import Grid, NetworkReport
from .pricesetter import (LoopRow, PriceSetter, _Class, _classes, _Interval, _link_state, assemble, pools,
                          setter_costs)
from .solved import Solved

N_LOCAL = 6    # VOLL, VOLL_BLACKOUT, MARGINAL_UNIT, STORAGE_DIS, STORAGE_CH, TIE_AT_BOUND (CAPACITY_RENT follows)
BLACKOUT = "VOLL_BLACKOUT"
LOOP_COLUMNS = ["zone", "period_id", "t", "resource_id", "alpha", "cost_usd_mwh", "setter_zone", "case"]


class Member(NamedTuple):
    """A marginal resource or unserved energy of the island, with its class setter cost c_m."""
    id: str
    tech: str
    fuel: str
    bus: int
    cost: float


def _at_limit(sv: Solved, rep: NetworkReport) -> np.ndarray:
    """(L,P,T): flow within tol_q of its forward or reverse rating (AC ratings are symmetric)."""
    g, flow, tq = rep.grid, sv.var("flow"), sv.case.tolerances.tol_q_abs_mw
    return (flow >= g.f_plus[:, None, None] - tq) | (flow <= -g.f_minus[:, None, None] + tq)


def price_components(rep: NetworkReport, free_dc: np.ndarray) -> np.ndarray:
    """(Z,P,T) price-component label of each zone-hour: components of (islands, free DC links), labelled by the smallest
    island index. With no free DC link in an hour the label is the electrical island."""
    g = rep.grid
    out = np.broadcast_to(g.node[:, None, None], (len(g.node), *free_dc.shape[1:])).copy()
    n_isl = len(g.ids)
    for p, t in zip(*np.nonzero(free_dc.any(axis=0))):
        k = free_dc[:, p, t]
        graph = coo_matrix((np.ones(k.sum()), (g.node[g.origin[k]], g.node[g.end[k]])), shape=(n_isl, n_isl))
        label = connected_components(graph, directed=False)[1]
        smallest = np.full(label.max() + 1, n_isl)
        np.minimum.at(smallest, label, np.arange(n_isl))
        out[:, p, t] = smallest[label][g.node]
    return out


def _congested(priced_ac: np.ndarray, comp: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """(labels,P,T): price component-hour has some AC line with a nonzero price (labels are island indices < Z)."""
    cong = np.zeros(comp.shape, dtype=bool)
    _, pp, tt = np.indices(priced_ac.shape)
    np.logical_or.at(cong, (comp[origin], pp, tt), priced_ac)
    return cong


def _members(sv: Solved, eco: Economics, local: list[_Class], nodes: np.ndarray, p: int, t: int) -> list[Member]:
    """M_i: every setter of a bus-local class at any bus of the component, sorted by id. Class setters already passed
    their class's price check; VOLL_BLACKOUT is excluded (pi = VOLL + mu_use there is not a known cost, see `_bounds`)."""
    case, found = sv.case, []
    for cls in (c for c in local if c.name != BLACKOUT):
        pool = pools(case, cls.kind, *eco.pi.shape[1:])
        for z in nodes:
            idx = np.flatnonzero(cls.setters[z, :, p, t])
            found += [Member(pool["ids"][r], pool["tech"][r], pool["fuel"][r], int(pool["zone"][r]), float(c))
                      for r, c in zip(idx, setter_costs(case, eco, cls, idx, p, t))]
    return sorted(found, key=lambda m: m.id)


def _bounds(sv: Solved, nodes: np.ndarray, phi_of, p: int, t: int) -> list[loop.Bound]:
    """Resources at a bound at a bus of the component: gens at cap (pi >= mc) or zero (pi <= mc), unserved at 0 (<= VOLL),
    total-blackout buses (pi >= VOLL)."""
    case, gen, tol = sv.case, sv.case.gen, sv.case.tolerances
    g, cap = sv.var("g")[:, p, t], gen.avail[:, p, t] * (gen.k0 + sv.var("x"))
    tq = np.maximum(tol.tol_q_abs_mw, tol.tol_q_rel * (gen.k0 + sv.var("x")))
    in_island = np.isin(gen.zone, nodes) & (cap > tq)
    out = [loop.Bound(phi_of(gen.zone[r:r + 1])[0], float(gen.mc[r, p, t]), 1 if g[r] >= cap[r] - tq[r] else -1)
           for r in np.flatnonzero(in_island & ((g >= cap - tq) | (g <= tq)))]
    u, d = sv.var("use")[:, p, t], case.demand[:, p, t]
    zero_unserved = [z for z in nodes if u[z] <= max(tol.tol_q_abs_mw, tol.tol_q_rel * d[z]) and d[z] > tol.tol_q_abs_mw]
    blackout = [z for z in nodes if u[z] >= d[z] - max(tol.tol_q_abs_mw, tol.tol_q_rel * d[z]) and d[z] > tol.tol_q_abs_mw]
    return (out + [loop.Bound(phi_of(np.array([z]))[0], case.voll, -1) for z in zero_unserved]
            + [loop.Bound(phi_of(np.array([z]))[0], case.voll, 1) for z in blackout])


def _storage_bounds(sv: Solved, eco: Economics, members: list[Member], nodes: np.ndarray, phi_of, tol_pi: float,
                    p: int, t: int) -> list[loop.Bound]:
    """S2 rows (formulation 7.4a.7): storage at a bus of the component, not in M_i, with P_r > tol_q, at the solved
    water value v: idle c^c - tol <= pi <= c^d + tol; at the st_pwr limit discharging pi >= c^d - tol, charging
    pi <= c^c + tol (c^d = VOM + v/eta_d, c^c = eta_c v)."""
    st, tol = sv.case.storage, sv.case.tolerances
    p_cap = st.p0 + sv.var("xP")
    tq = np.maximum(tol.tol_q_abs_mw, tol.tol_q_rel * p_cap)
    ch, dis, v = sv.var("ch")[:, p, t], sv.var("dis")[:, p, t], eco.v[:, p, t]
    c_dis, c_ch = st.vom + v / st.eta_d, st.eta_c * v
    taken = {m.id for m in members}
    out: list[loop.Bound] = []
    for r in np.flatnonzero(np.isin(st.zone, nodes) & (p_cap > tq)):
        if st.ids[r] in taken:
            continue
        row = phi_of(st.zone[r:r + 1])[0]
        if ch[r] <= tq[r] and dis[r] <= tq[r]:
            out += [loop.Bound(row, c_ch[r] - tol_pi, 1), loop.Bound(row, c_dis[r] + tol_pi, -1)]
        elif dis[r] >= p_cap[r] - tq[r]:
            out.append(loop.Bound(row, c_dis[r] - tol_pi, 1))
        elif ch[r] >= p_cap[r] - tq[r]:
            out.append(loop.Bound(row, c_ch[r] + tol_pi, -1))
    return out


def _island_hour(sv: Solved, eco: Economics, rep: NetworkReport, members: list[Member], nodes: np.ndarray,
                 binding: np.ndarray, free: np.ndarray, tol_pi: float, p: int, t: int) -> dict[int, LoopRow]:
    """alpha (cases (a), (b)) or the price interval (case (c)) for every bus of one congested price component-hour.
    Unknowns: one lambda per island of the component, then mu_K; rows: marginal buses (RHS c_b) and free DC links
    phi_e - phi_o (RHS 0)."""
    case, g, h_k = sv.case, rep.grid, rep.h[binding]
    isl = np.unique(g.node[nodes])
    phi_of = lambda zs: loop.phi(h_k, zs, np.searchsorted(isl, g.node[zs]), len(isl))  # noqa: E731
    buses = np.array(sorted({m.bus for m in members}))
    at_bus = [[m for m in members if m.bus == b] for b in buses]
    cost_b = np.array([np.mean([m.cost for m in ms]) for ms in at_bus])
    phi_b, phi_n = phi_of(buses), phi_of(nodes)
    phi_hat = np.vstack([phi_b, phi_of(g.end[free]) - phi_of(g.origin[free])])
    cost_hat = np.r_[cost_b, np.zeros(free.sum())]
    kind = loop.classify(phi_hat)
    n_storage = 0
    failed = 0
    if kind == loop.INTERVAL:
        storage = _storage_bounds(sv, eco, members, nodes, phi_of, tol_pi, p, t)
        n_storage = len(storage)
        point = np.r_[eco.pi[g.ref[isl], p, t], eco.mu_link[binding, p, t]]
        iv = loop.interval(make_solver(case.solver_config), phi_hat, cost_hat, np.sign(sv.var("flow")[binding, p, t]),
                           _bounds(sv, nodes, phi_of, p, t) + storage, phi_n, point, tol_pi)
        cost, lo, hi, alpha = iv[:, 0], iv[:, 0], iv[:, 1], np.empty((len(nodes), 0))
        failed = np.isnan(iv).sum(axis=1)
    else:
        by_bus = loop.weights(phi_hat, phi_n)[:, :len(buses)]
        alpha = np.hstack([np.repeat(by_bus[:, [j]] / len(ms), len(ms), axis=1) for j, ms in enumerate(at_bus)])
        cost = lo = hi = by_bus @ cost_b
        failed = np.zeros(len(nodes), dtype=int)
    ordered = [m for ms in at_bus for m in ms]      # members grouped by bus, matching the columns of alpha
    return {int(z): LoopRow(ids=[m.id for m in ordered], techs=[m.tech for m in ordered],
                            fuels=[m.fuel for m in ordered], zones=[case.zones[m.bus] for m in ordered],
                            costs=np.array([m.cost for m in ordered]), alpha=alpha[j], cost=float(cost[j]),
                            lo=float(lo[j]), hi=float(hi[j]), case=kind, failed=int(failed[j]),
                            storage_rows=n_storage) for j, z in enumerate(nodes)}


def _loops(sv: Solved, eco: Economics, rep: NetworkReport, local: list[_Class], comp: np.ndarray, cong: np.ndarray,
           binding: np.ndarray, free: np.ndarray, tol_pi: np.ndarray) -> dict[tuple[int, int, int], LoopRow]:
    """Loop data of every bus of every congested component-hour that has a marginal set, keyed (zone, period, t)."""
    g, out = rep.grid, {}
    for c, p, t in zip(*np.nonzero(cong)):
        nodes = np.flatnonzero(comp[:, p, t] == c)
        members = _members(sv, eco, local, nodes, p, t)
        if members:
            in_comp = comp[g.origin, p, t] == c
            rows = _island_hour(sv, eco, rep, members, nodes, binding[:, p, t] & in_comp, free[:, p, t] & in_comp,
                                float(tol_pi[nodes, p, t].max()), p, t)
            out |= {(z, p, t): row for z, row in rows.items()}
    return out


def _merge(island: _Class, local: _Class, congested: np.ndarray) -> _Class:
    """Island rule in uncongested island-hours, bus-local rule (island := {n}) in congested ones."""
    return _Class(island.name, np.where(congested, local.cond, island.cond), np.where(congested, local.ok, island.ok),
                  np.where(congested[:, None], local.setters, island.setters), island.kind)


def _loop_class(loops: dict[tuple[int, int, int], LoopRow], pi: np.ndarray, tol_pi: np.ndarray) -> _Class:
    """CONGESTION_LOOP: holds where weights or an interval exist; its price check is pi within [lo, hi] +- tol_pi."""
    cond, ok = np.zeros(pi.shape, dtype=bool), np.zeros(pi.shape, dtype=bool)
    for key, row in loops.items():
        cond[key] = True
        ok[key] = row.lo - tol_pi[key] <= pi[key] <= row.hi + tol_pi[key]
    return _Class("CONGESTION_LOOP", cond, ok, np.zeros((pi.shape[0], 0, *pi.shape[1:]), dtype=bool), "loop")


def _loop_table(sv: Solved, ps: PriceSetter, loops: dict[tuple[int, int, int], LoopRow]) -> pd.DataFrame:
    """price_setter_loop: alpha per member for every bus-hour whose primary class is CONGESTION_LOOP (cases a, b)."""
    case, tab = sv.case, ps.table
    zone_ix, period_ix = {z: i for i, z in enumerate(case.zones)}, {p: i for i, p in enumerate(case.periods)}
    rows = []
    for r in tab[tab["primary_class"] == "CONGESTION_LOOP"].itertuples():
        lp = loops[(zone_ix[r.zone], period_ix[r.period_id], r.t - 1)]
        if lp.case != loop.INTERVAL:
            rows += [(r.zone, r.period_id, r.t, i, a, c, z, lp.case) for i, a, c, z in
                     zip(lp.ids, lp.alpha, lp.costs, lp.zones)]
    return pd.DataFrame(rows, columns=LOOP_COLUMNS)


def alpha_residual(ps: PriceSetter) -> float:
    """price_setter.loop_alpha: max over weighted CONGESTION_LOOP bus-hours of max(|sum alpha - 1|, |pi - sum alpha c|)."""
    if ps.loop is None or ps.loop.empty:
        return 0.0
    key = ["zone", "period_id", "t"]
    sums = ps.loop.assign(ac=ps.loop["alpha"] * ps.loop["cost_usd_mwh"]).groupby(key).agg(
        alpha=("alpha", "sum"), ac=("ac", "sum"))
    price = ps.table.set_index(key)["price"].reindex(sums.index)
    return float(np.maximum((sums["alpha"] - 1.0).abs(), (price - sums["ac"]).abs()).max())


def interval_failures(loops: dict[tuple[int, int, int], LoopRow], pi: np.ndarray, tol_pi: np.ndarray) -> int:
    """price_setter.loop_interval (7.4a.6): failed interval solves (NaN sides) plus case-(c) bus-hours with pi outside
    [lo - tol_pi, hi + tol_pi]."""
    count = 0
    for key, row in loops.items():
        if row.case == loop.INTERVAL:
            count += row.failed + (row.failed == 0 and not row.lo - tol_pi[key] <= pi[key] <= row.hi + tol_pi[key])
    return int(count)


def _binding_masks(g: Grid, comp: np.ndarray, binding_ac: np.ndarray, dc_limit: np.ndarray) -> np.ndarray:
    """(Z,L,P,T): `binding_links` of a zone-hour: the binding AC lines of its price component plus every DC link at a
    limit with a nonzero price and an end in the component (7.4a.12)."""
    in_origin = comp[:, None] == comp[g.origin][None]
    in_end = comp[:, None] == comp[g.end][None]
    return (binding_ac[None] & in_origin) | (dc_limit[None] & (in_origin | in_end))


def dcpf_price_setter(sv: Solved, eco: Economics, rep: NetworkReport) -> PriceSetter:
    """Section 4 under dcpf: Step 0 is replaced by price components (electrical islands joined by DC links strictly
    inside their limits) and the congested-component-hour rule."""
    if not sv.sol.basis_valid:
        raise ValueError("price-setter requires a basic solution (basis_valid is False)")
    g, shape = rep.grid, eco.pi.shape
    tol_pi = np.maximum(sv.case.tolerances.tol_pi_abs, sv.case.tolerances.tol_pi_rel * np.abs(eco.pi))
    dc, limit = g.dc[:, None, None], _at_limit(sv, rep)
    comp = price_components(rep, dc & ~limit)
    priced = np.abs(eco.mu_link) > np.maximum(tol_pi[g.end], tol_pi[g.origin])
    cong = _congested(priced & ~dc, comp, g.origin)
    cong_z = np.take_along_axis(cong, comp, axis=0)
    binding_ac = priced & ~dc & limit
    by_island, interval = _classes(sv, eco, comp, tol_pi)
    by_bus, bus_interval = _classes(sv, eco, np.broadcast_to(np.arange(shape[0])[:, None, None], shape), tol_pi)
    loops = _loops(sv, eco, rep, by_bus[:N_LOCAL], comp, cong, binding_ac, dc & ~limit, tol_pi)
    classes = [*(_merge(a, b, cong_z) for a, b in zip(by_island[:N_LOCAL], by_bus[:N_LOCAL])),
               _loop_class(loops, eco.pi, tol_pi), _merge(by_island[N_LOCAL], by_bus[N_LOCAL], cong_z)]
    merged = _Interval(*(np.where(cong_z[:, None] if x.ndim == 4 else cong_z, y, x) for x, y in
                         zip((interval.lo, interval.hi, interval.rent), (bus_interval.lo, bus_interval.hi,
                                                                       bus_interval.rent))), interval.invest)
    binding = _binding_masks(g, comp, binding_ac, priced & dc & limit)
    separated, _, bad = _link_state(sv, eco, tol_pi)
    ps = assemble(sv, eco, classes, merged, np.broadcast_to(g.node[:, None, None], shape) + 1, binding,
                  np.zeros_like(binding), (separated & dc, bad & dc), loops)
    return dataclasses.replace(ps, loop=_loop_table(sv, ps, loops), loop_interval=interval_failures(loops, eco.pi, tol_pi),
                               storage_rows_used=any(r.storage_rows for r in loops.values()))
