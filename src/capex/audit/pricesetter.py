"""Hook 7: price-setter algorithm (formulation section 4). Requires a basic solution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .duals import Economics
from .solved import Solved

CLASS_ORDER = ["VOLL", "VOLL_BLACKOUT", "MARGINAL_UNIT", "STORAGE_DIS", "STORAGE_CH", "TIE_AT_BOUND", "CAPACITY_RENT"]
PRIMARY_NAME = {"VOLL_BLACKOUT": "VOLL"}


class _Class(NamedTuple):
    """One candidate class: where its condition holds, where it also passes its price check, and its setters."""
    name: str
    cond: np.ndarray        # (Z,P,T)
    ok: np.ndarray          # (Z,P,T) condition holds and every candidate passes the price check
    setters: np.ndarray     # (Z,R,P,T) bool over the class's resource index set
    kind: str               # "gen" | "storage" | "zone"


class _Interval(NamedTuple):
    """CAPACITY_RENT price interval (Z,P,T) and the build status of generators."""
    lo: np.ndarray
    hi: np.ndarray
    x: np.ndarray           # (G,) new build
    tol_q: np.ndarray       # (G,)


@dataclass(frozen=True)
class PriceSetter:
    table: pd.DataFrame
    summary: pd.DataFrame
    link_issues: pd.DataFrame
    unexplained: int
    link_inconsistent: int
    islands: np.ndarray     # (Z,P,T)


def _components(edges: np.ndarray, origin: np.ndarray, end: np.ndarray, n_zones: int) -> np.ndarray:
    """Island labels (Z,P,T): zones joined by links whose price gap is within tolerance."""
    n_p, n_t = edges.shape[1:]
    out = np.zeros((n_zones, n_p, n_t), dtype=int)
    for p in range(n_p):
        for t in range(n_t):
            on = edges[:, p, t]
            graph = coo_matrix((np.ones(on.sum()), (origin[on], end[on])), shape=(n_zones, n_zones))
            out[:, p, t] = connected_components(graph, directed=False)[1]
    return out


def _link_state(sv: Solved, eco: Economics, tol_pi: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(price gap beyond tolerance, link at a bound, link inconsistent) per (l,p,t); step 0 of section 4."""
    lk, tol = sv.case.links, sv.case.tolerances
    gap = eco.pi[lk.end] - eco.pi[lk.origin]
    tol_l = np.maximum(tol_pi[lk.end], tol_pi[lk.origin])
    flow = sv.var("flow")
    tq = tol.tol_q_abs_mw
    at_high = flow >= lk.f_plus[:, None, None] - tq
    at_low = flow <= -lk.f_minus[:, None, None] + tq
    separated = np.abs(gap) > tol_l
    consistent = np.where(gap > 0, at_high, at_low) & (np.abs(eco.mu_link - gap) <= tol_l)
    return separated, at_high | at_low, separated & ~consistent


def _gen_class(name: str, cond_g: np.ndarray, pc: np.ndarray, inisl: np.ndarray) -> _Class:
    """Class over generators: cond_g (G,P,T), price check pc (Z,G,P,T), island membership inisl (Z,G,P,T)."""
    cand = inisl & cond_g[None]
    cond = cand.any(axis=1)
    return _Class(name, cond, cond & ~(cand & ~pc).any(axis=1), cand & pc, "gen")


def _storage_class(name: str, cond_s: np.ndarray, pc: np.ndarray, inisl: np.ndarray) -> _Class:
    cand = inisl & cond_s[None]
    cond = cand.any(axis=1)
    return _Class(name, cond, cond & ~(cand & ~pc).any(axis=1), cand & pc, "storage")


def _classes(sv: Solved, eco: Economics, isl: np.ndarray, tol_pi: np.ndarray) -> tuple[list[_Class], _Interval]:
    case, gen, st, tol = sv.case, sv.case.gen, sv.case.storage, sv.case.tolerances
    pi, pi_z = eco.pi, eco.pi[:, None]
    tpi_z = tol_pi[:, None]
    g, x = sv.var("g"), sv.var("x")
    cap = gen.avail * (gen.k0 + x)[:, None, None]
    tq = np.maximum(tol.tol_q_abs_mw, tol.tol_q_rel * (gen.k0 + x))[:, None, None]
    present, interior = cap > tq, (g > tq) & (g < cap - tq)
    at_cap, room = present & (g >= cap - tq), present & (g < cap - tq)
    isl_g = isl[gen.zone]
    inisl_g = isl[:, None] == isl_g[None]                                     # (Z,G,P,T)
    near_mc = np.abs(pi_z - gen.mc[None]) <= tpi_z
    # storage
    ch, dis, xp = sv.var("ch"), sv.var("dis"), sv.var("xP")
    p_cap = (st.p0 + xp)[:, None, None]
    tq_s = np.maximum(tol.tol_q_abs_mw, tol.tol_q_rel * p_cap)
    pwr_slack = p_cap - ch - dis > tq_s
    inisl_s = isl[:, None] == isl[st.zone][None]
    pc_dis = np.abs(pi_z - st.vom[None, :, None, None] - eco.v[None] / st.eta_d[None, :, None, None]) <= tpi_z
    pc_ch = np.abs(pi_z - st.eta_c[None, :, None, None] * eco.v[None]) <= tpi_z
    # unserved energy
    u, d_mw = sv.var("use"), case.demand
    tq_z = np.maximum(tol.tol_q_abs_mw, tol.tol_q_rel * d_mw)
    inisl_z = isl[:, None] == isl[None]                                       # (Z,Z',P,T)
    partial, blackout = (u > tq_z) & (u < d_mw - tq_z), (u >= d_mw - tq_z) & (d_mw > tol.tol_q_abs_mw)
    pc_voll = np.abs(pi - case.voll) <= tol_pi
    cand_vo, cand_bl = inisl_z & partial[None], inisl_z & blackout[None]
    pc_black = (pi >= case.voll - tol_pi)[:, None] & (np.abs(pi[:, None] - case.voll - eco.mu_use[None]) <= tol_pi[:, None])
    cond_vo, cond_bl = cand_vo.any(axis=1), cand_bl.any(axis=1)
    voll = _Class("VOLL", cond_vo, cond_vo & pc_voll, cand_vo & pc_voll[:, None], "zone")
    black = _Class("VOLL_BLACKOUT", cond_bl, cond_bl & ~(cand_bl & ~pc_black).any(axis=1), cand_bl & pc_black, "zone")
    # capacity rent
    mc_b = np.broadcast_to(gen.mc[None], inisl_g.shape)
    violators = (inisl_g & room[None] & (mc_b < pi_z - tpi_z)).any(axis=1)
    rent_units = inisl_g & (at_cap & (eco.rho > tol_pi[gen.zone]))[None]
    lo = np.where(inisl_g & at_cap[None], mc_b, -np.inf).max(axis=1, initial=-np.inf)
    hi = np.minimum(case.voll, np.where(inisl_g & room[None], mc_b, np.inf).min(axis=1, initial=np.inf))
    cond_cr = ~violators & rent_units.any(axis=1)
    ok_cr = cond_cr & (pi >= lo - tol_pi) & (pi <= hi + tol_pi)
    classes = [
        voll, black,
        _gen_class("MARGINAL_UNIT", interior, near_mc, inisl_g),
        _storage_class("STORAGE_DIS", (dis > tq_s) & pwr_slack, pc_dis, inisl_s),
        _storage_class("STORAGE_CH", (ch > tq_s) & pwr_slack, pc_ch, inisl_s),
        _gen_class("TIE_AT_BOUND", present & ~interior, np.ones_like(near_mc), inisl_g & near_mc),
        _Class("CAPACITY_RENT", cond_cr, ok_cr, rent_units, "gen")]
    return classes, _Interval(lo, hi, x, tq[:, 0, 0])


def _boundary_links(sv: Solved, isl: np.ndarray, at_bound: np.ndarray, bad: np.ndarray
                    ) -> tuple[np.ndarray, np.ndarray]:
    """(binding boundary links, links with inconsistent price gap touching the island) as (Z,L,P,T) masks."""
    lk = sv.case.links
    touch = (isl[:, None] == isl[lk.origin][None]) | (isl[:, None] == isl[lk.end][None])
    crossing = (isl[lk.origin] != isl[lk.end])[None]
    return touch & crossing & at_bound[None], touch & bad[None]


def _join(items) -> str:
    return ",".join(map(str, items))


@dataclass(frozen=True)
class _Ctx:
    """Everything the per-zone-hour record needs, bundled once."""
    sv: Solved
    eco: Economics
    classes: list[_Class]
    interval: _Interval
    matched: np.ndarray
    primary: np.ndarray
    explained: np.ndarray
    binding: np.ndarray
    touching_bad: np.ndarray
    islands: np.ndarray

    def pools(self, kind: str) -> dict[str, np.ndarray]:
        """ids, zone index, tech, fuel and cost (over p,t) of the resource set a class kind indexes."""
        case, gen, st = self.sv.case, self.sv.case.gen, self.sv.case.storage
        n_p, n_t = self.eco.pi.shape[1:]
        if kind == "gen":
            return {"ids": np.asarray(gen.ids, dtype=object), "zone": gen.zone, "tech": gen.tech, "fuel": gen.fuel,
                    "cost": gen.mc}
        if kind == "storage":
            return {"ids": np.asarray(st.ids, dtype=object), "zone": st.zone, "tech": st.tech,
                    "fuel": np.full(len(st.ids), "storage"),
                    "cost": np.broadcast_to(st.vom[:, None, None], (len(st.ids), n_p, n_t))}
        n_z = len(case.zones)
        return {"ids": np.asarray([f"unserved:{z}" for z in case.zones], dtype=object), "zone": np.arange(n_z),
                "tech": np.full(n_z, "unserved"), "fuel": np.full(n_z, "none"),
                "cost": np.full((n_z, n_p, n_t), case.voll)}

    def _storage_costs(self, name: str, members: np.ndarray, p: int, t: int) -> list[float]:
        """Section 4 Outputs: STORAGE_DIS cost VOM + v/eta_d, STORAGE_CH cost eta_c v (v = water value)."""
        st, v = self.sv.case.storage, self.eco.v[members, p, t]
        if name == "STORAGE_DIS":
            return list(st.vom[members] + v / st.eta_d[members])
        return list(st.eta_c[members] * v)

    def record(self, z: int, p: int, t: int) -> tuple[dict, list[tuple]]:
        """Table row and (zone, tech, fuel, class, hours) pieces for the summary, for one zone-hour."""
        case, price = self.sv.case, self.eco.pi[z, p, t]
        zones = case.zones
        matched = self.matched[:, z, p, t]
        explained = bool(self.explained[z, p, t])
        cls = self.classes[self.primary[z, p, t]]
        name = PRIMARY_NAME.get(cls.name, cls.name) if explained else "UNEXPLAINED"
        flags: list[str] = [] if explained else ["UNEXPLAINED"]
        ids = techs = fuels = szones = []
        costs: list[float] = []
        lo = hi = np.nan
        if explained:
            pool = self.pools(cls.kind)
            members = np.flatnonzero(cls.setters[z, :, p, t])
            ids, techs, fuels = pool["ids"][members], pool["tech"][members], pool["fuel"][members]
            szones = [zones[i] for i in pool["zone"][members]]
            costs = list(pool["cost"][members, p, t])
            if cls.name == "CAPACITY_RENT":
                lo, hi = self.interval.lo[z, p, t], self.interval.hi[z, p, t]
                costs = [lo]
                tq = self.interval.tol_q[members]
                invest = ((self.interval.x[members] > tq) & (self.interval.x[members] < case.gen.xmax[members] - tq)).any()
                flags.append("INVESTMENT_MARGIN" if invest else "DEGENERATE")
            if cls.name == "VOLL_BLACKOUT":
                flags.append("BLACKOUT")
        if any(sz != zones[z] for sz in szones):
            flags.append("IMPORT")
        links = np.asarray(case.links.ids, dtype=object)[self.binding[z, :, p, t]]
        if len(links):
            flags.append("CONGESTED")
        if self.touching_bad[z, :, p, t].any():
            flags.append("LINK_INCONSISTENT")
        if explained and cls.kind == "storage":
            costs = self._storage_costs(cls.name, members, p, t)
        cost = float(np.mean(costs)) if costs else np.nan
        all_classes = [PRIMARY_NAME.get(c.name, c.name) + (":BLACKOUT" if c.name == "VOLL_BLACKOUT" else "")
                       for c, m in zip(self.classes, matched) if m]
        row = {"zone": zones[z], "period_id": case.periods[p], "t": t + 1, "primary_class": name,
               "all_classes": _join(all_classes), "setter_ids": _join(ids), "setter_tech": _join(sorted(set(techs))),
               "setter_fuel": _join(sorted(set(fuels))), "setter_zone": _join(sorted(set(szones))), "price": price,
               "setter_cost": cost, "residual": price - cost, "island_id": int(self.islands[z, p, t]),
               "binding_links": _join(links), "flags": _join(flags), "price_lo": lo, "price_hi": hi,
               "weight_hours": case.w[p]}
        n = len(ids)
        pieces = [(zones[z], "none", "none", name, case.w[p])] if n == 0 else \
            [(zones[z], tc, fl, name, case.w[p] / n) for tc, fl in zip(techs, fuels)]
        return row, pieces


def price_setter(sv: Solved, eco: Economics) -> PriceSetter:
    """Classify every zone-hour; raises if the solution has no valid basis (section 4)."""
    if not sv.sol.basis_valid:
        raise ValueError("price-setter requires a basic solution (basis_valid is False)")
    case, lk = sv.case, sv.case.links
    n_z, n_p, n_t = eco.pi.shape
    tol_pi = np.maximum(case.tolerances.tol_pi_abs, case.tolerances.tol_pi_rel * np.abs(eco.pi))
    separated, at_bound, bad = _link_state(sv, eco, tol_pi)
    isl = _components(~separated, lk.origin, lk.end, n_z)
    classes, interval = _classes(sv, eco, isl, tol_pi)
    matched = np.stack([c.cond for c in classes])
    ok = np.stack([c.ok for c in classes])
    primary = matched.argmax(axis=0)
    explained = matched.any(axis=0) & np.take_along_axis(ok, primary[None], 0)[0]
    binding, touching_bad = _boundary_links(sv, isl, at_bound, bad)
    ctx = _Ctx(sv, eco, classes, interval, matched, primary, explained, binding, touching_bad, isl)
    records = [ctx.record(z, p, t) for z in range(n_z) for p in range(n_p) for t in range(n_t)]
    table = pd.DataFrame([r for r, _ in records])
    return PriceSetter(table=table, summary=_summary([pc for _, ps in records for pc in ps]),
                       link_issues=_link_issues(sv, separated, bad), unexplained=int((~explained).sum()),
                       link_inconsistent=int(bad.sum()), islands=isl)


def _summary(pieces: list[tuple]) -> pd.DataFrame:
    """Weighted hours by (zone, tech, fuel, class); ties split the hour equally (section 4)."""
    summary = pd.DataFrame(pieces, columns=["zone", "tech", "fuel", "class", "weighted_hours"])
    summary = summary.groupby(["zone", "tech", "fuel", "class"], as_index=False)["weighted_hours"].sum()
    summary["share_weighted_hours"] = summary["weighted_hours"] / summary.groupby("zone")["weighted_hours"].transform("sum")
    return summary


def _link_issues(sv: Solved, separated: np.ndarray, bad: np.ndarray) -> pd.DataFrame:
    blk = sv.lp.cols["flow"]
    frame = blk.frame().drop(columns="label").assign(separated=separated.ravel(), inconsistent=bad.ravel())
    return frame[bad.ravel()]
