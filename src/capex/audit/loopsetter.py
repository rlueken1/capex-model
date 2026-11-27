"""Hook 7 under `tx.model = dcpf` (formulation 7.4a.7): section 4 with electrical islands, bus-local classes in
congested island-hours, then CONGESTION_LOOP weights alpha (and an interval when they are not computable)."""
from __future__ import annotations

import dataclasses
from typing import NamedTuple

import numpy as np
import pandas as pd

from ..solver import make_solver
from . import loop
from .duals import Economics
from .network import NetworkReport
from .pricesetter import LoopRow, PriceSetter, _Class, _classes, _Interval, assemble, pools, setter_costs
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


def _congestion(sv: Solved, eco: Economics, rep: NetworkReport, tol_pi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(island-hour congested (I,P,T), binding-line mask K (L,P,T)): |mu| > tol_pi, and also at the rating for K."""
    g, tol = rep.grid, sv.case.tolerances
    priced = np.abs(eco.mu_link) > np.maximum(tol_pi[g.end], tol_pi[g.origin])
    congested = np.zeros((len(g.ids), *priced.shape[1:]), dtype=bool)
    np.logical_or.at(congested, g.line, priced)
    at_rating = np.abs(sv.var("flow")) >= g.rating[:, None, None] - tol.tol_q_abs_mw
    return congested, priced & at_rating


def _members(sv: Solved, eco: Economics, local: list[_Class], nodes: np.ndarray, p: int, t: int) -> list[Member]:
    """M_i: every setter of a bus-local class at any bus of the island, sorted by id. Class setters already passed
    their class's price check; VOLL_BLACKOUT is excluded (pi = VOLL + mu_use there is not a known cost, see `_bounds`)."""
    case, found = sv.case, []
    for cls in (c for c in local if c.name != BLACKOUT):
        pool = pools(case, cls.kind, *eco.pi.shape[1:])
        for z in nodes:
            idx = np.flatnonzero(cls.setters[z, :, p, t])
            found += [Member(pool["ids"][r], pool["tech"][r], pool["fuel"][r], int(pool["zone"][r]), float(c))
                      for r, c in zip(idx, setter_costs(case, eco, cls, idx, p, t))]
    return sorted(found, key=lambda m: m.id)


def _bounds(sv: Solved, nodes: np.ndarray, h_k: np.ndarray, p: int, t: int) -> list[loop.Bound]:
    """Resources at a bound at a bus of the island: gens at cap (pi >= mc) or zero (pi <= mc), unserved at 0 (<= VOLL),
    total-blackout buses (pi >= VOLL)."""
    case, gen, tol = sv.case, sv.case.gen, sv.case.tolerances
    g, cap = sv.var("g")[:, p, t], gen.avail[:, p, t] * (gen.k0 + sv.var("x"))
    tq = np.maximum(tol.tol_q_abs_mw, tol.tol_q_rel * (gen.k0 + sv.var("x")))
    in_island = np.isin(gen.zone, nodes) & (cap > tq)
    out = [loop.Bound(loop.phi(h_k, gen.zone[r:r + 1])[0], float(gen.mc[r, p, t]), 1 if g[r] >= cap[r] - tq[r] else -1)
           for r in np.flatnonzero(in_island & ((g >= cap - tq) | (g <= tq)))]
    u, d = sv.var("use")[:, p, t], case.demand[:, p, t]
    zero_unserved = [z for z in nodes if u[z] <= max(tol.tol_q_abs_mw, tol.tol_q_rel * d[z]) and d[z] > tol.tol_q_abs_mw]
    blackout = [z for z in nodes if u[z] >= d[z] - max(tol.tol_q_abs_mw, tol.tol_q_rel * d[z]) and d[z] > tol.tol_q_abs_mw]
    return (out + [loop.Bound(loop.phi(h_k, np.array([z]))[0], case.voll, -1) for z in zero_unserved]
            + [loop.Bound(loop.phi(h_k, np.array([z]))[0], case.voll, 1) for z in blackout])


def _island_hour(sv: Solved, rep: NetworkReport, members: list[Member], nodes: np.ndarray, binding: np.ndarray,
                 p: int, t: int) -> dict[int, LoopRow]:
    """alpha (cases (a), (b)) or the price interval (case (c)) for every bus of one congested island-hour."""
    case, h_k = sv.case, rep.h[binding]
    buses = np.array(sorted({m.bus for m in members}))
    at_bus = [[m for m in members if m.bus == b] for b in buses]
    cost_b = np.array([np.mean([m.cost for m in ms]) for ms in at_bus])
    phi_b, phi_n = loop.phi(h_k, buses), loop.phi(h_k, nodes)
    kind = loop.classify(phi_b)
    if kind == loop.INTERVAL:
        sign_k = np.sign(sv.var("flow")[binding, p, t])
        iv = loop.interval(make_solver(case.solver_config), phi_b, cost_b, sign_k, _bounds(sv, nodes, h_k, p, t), phi_n)
        cost, lo, hi, alpha = iv[:, 0], iv[:, 0], iv[:, 1], np.empty((len(nodes), 0))
    else:
        by_bus = loop.weights(phi_b, phi_n)
        alpha = np.hstack([np.repeat(by_bus[:, [j]] / len(ms), len(ms), axis=1) for j, ms in enumerate(at_bus)])
        cost = lo = hi = by_bus @ cost_b
    ordered = [m for ms in at_bus for m in ms]      # members grouped by bus, matching the columns of alpha
    return {int(z): LoopRow(ids=[m.id for m in ordered], techs=[m.tech for m in ordered],
                            fuels=[m.fuel for m in ordered], zones=[case.zones[m.bus] for m in ordered],
                            costs=np.array([m.cost for m in ordered]), alpha=alpha[j], cost=float(cost[j]),
                            lo=float(lo[j]), hi=float(hi[j]), case=kind) for j, z in enumerate(nodes)}


def _loops(sv: Solved, eco: Economics, rep: NetworkReport, local: list[_Class], congested: np.ndarray,
           binding: np.ndarray) -> dict[tuple[int, int, int], LoopRow]:
    """Loop data of every bus of every congested island-hour that has a marginal set, keyed (zone, period, t)."""
    g, out = rep.grid, {}
    for i, p, t in zip(*np.nonzero(congested)):
        nodes = np.flatnonzero(g.node == i)
        members = _members(sv, eco, local, nodes, p, t)
        if members:
            rows = _island_hour(sv, rep, members, nodes, binding[:, p, t] & (g.line == i), p, t)
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


def dcpf_price_setter(sv: Solved, eco: Economics, rep: NetworkReport) -> PriceSetter:
    """Section 4 under dcpf: Step 0 is replaced by electrical islands and the congested-island-hour rule."""
    if not sv.sol.basis_valid:
        raise ValueError("price-setter requires a basic solution (basis_valid is False)")
    g, shape = rep.grid, eco.pi.shape
    tol_pi = np.maximum(sv.case.tolerances.tol_pi_abs, sv.case.tolerances.tol_pi_rel * np.abs(eco.pi))
    congested, binding_lines = _congestion(sv, eco, rep, tol_pi)
    island = np.broadcast_to(g.node[:, None, None], shape)
    by_island, interval = _classes(sv, eco, island, tol_pi)
    by_bus, bus_interval = _classes(sv, eco, np.broadcast_to(np.arange(shape[0])[:, None, None], shape), tol_pi)
    cong_z = congested[g.node]
    loops = _loops(sv, eco, rep, by_bus[:N_LOCAL], congested, binding_lines)
    classes = [*(_merge(a, b, cong_z) for a, b in zip(by_island[:N_LOCAL], by_bus[:N_LOCAL])),
               _loop_class(loops, eco.pi, tol_pi), _merge(by_island[N_LOCAL], by_bus[N_LOCAL], cong_z)]
    merged = _Interval(*(np.where(cong_z[:, None] if x.ndim == 4 else cong_z, y, x) for x, y in
                         zip((interval.lo, interval.hi, interval.rent), (bus_interval.lo, bus_interval.hi,
                                                                       bus_interval.rent))), interval.invest)
    binding = binding_lines[None] & (g.node[:, None] == g.line[None])[:, :, None, None]
    no_link_state = np.zeros(binding_lines.shape, dtype=bool)
    ps = assemble(sv, eco, classes, merged, island + 1, binding, np.zeros_like(binding),
                  (no_link_state, no_link_state), loops)
    return dataclasses.replace(ps, loop=_loop_table(sv, ps, loops))
