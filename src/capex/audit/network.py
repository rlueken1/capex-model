"""Case-data route of the DC power flow audit (formulation 7.4a.6, 7.4a.10).

Everything here is recomputed from the case tables and the primal/dual solution, never from the LP matrix and never
with the builder's network module (islands, PTDF and angles are rebuilt independently).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from ..data import T, Case
from .duals import Economics
from .solved import Solved

PTDF_NOISE = 1e-10
ISLAND_ANGLE_TOL = 1e-9


@dataclass(frozen=True)
class Grid:
    """Network of the case data: AC islands (ids i1.. by smallest zone row), reference zones, b, PTDF, ratings, DC links
    and rent components (islands joined by any DC link, formulation 7.4a.12)."""
    ids: tuple[str, ...]
    node: np.ndarray      # (N,) island index per zone
    ref: np.ndarray       # (I,) reference zone per island
    origin: np.ndarray    # (L,)
    end: np.ndarray       # (L,)
    b: np.ndarray         # (L,) MW/rad (0 for a DC link)
    f_plus: np.ndarray    # (L,) MW forward rating, inf = unlimited
    f_minus: np.ndarray   # (L,) MW reverse rating
    dc: np.ndarray        # (L,) bool: controllable DC link
    rent: np.ndarray      # (N,) rent-component index per zone

    @property
    def incidence(self) -> np.ndarray:
        """A (L,N): +1 at the line's origin, -1 at its end."""
        a = np.zeros((len(self.b), len(self.node)))
        a[np.arange(len(self.b)), self.origin] = 1.0
        a[np.arange(len(self.b)), self.end] = -1.0
        return a

    @property
    def ac(self) -> np.ndarray:
        return np.flatnonzero(~self.dc)

    def reduced(self, island: int) -> np.ndarray:
        """Indices of the island's zones without its reference zone."""
        return np.flatnonzero((self.node == island) & (np.arange(len(self.node)) != self.ref[island]))


@dataclass(frozen=True)
class NetworkReport:
    """Recomputed network quantities of one dcpf solve and the metrics of the network health checks."""
    grid: Grid
    h: np.ndarray               # (L,N) PTDF from case data
    inj: np.ndarray             # (N,P,T) solved net injection (incl. unserved energy) minus demand
    theta: np.ndarray           # (N,P,T) rad
    theta_source: str           # "lp" | "recomputed"
    lmp_energy: np.ndarray      # (N,P,T) lambda of the zone's island
    lmp_congestion: np.ndarray  # (N,P,T) -sum_l H mu
    metrics: dict[str, float]
    island_violations: int
    island_detail: str


def _components(case: Case, links: np.ndarray) -> np.ndarray:
    """Component label per zone over the selected links, numbered in order of the smallest zone row index."""
    lk, n = case.links, len(case.zones)
    raw = connected_components(coo_matrix((np.ones(links.sum()), (lk.origin[links], lk.end[links])), shape=(n, n)),
                               directed=False)[1]
    first = {lab: k for k, lab in enumerate(dict.fromkeys(raw.tolist()))}
    return np.array([first[lab] for lab in raw.tolist()], dtype=np.int64)


def _reference_zones(case: Case, node: np.ndarray) -> np.ndarray:
    given = case.switches.get("tx.ref_bus", [])
    ref = np.array([np.flatnonzero(node == i)[0] for i in range(int(node.max()) + 1)], dtype=np.int64)
    for z in [given] if isinstance(given, str) else given:
        ref[node[case.zones.index(z)]] = case.zones.index(z)
    return ref


def grid(case: Case) -> Grid:
    lk = case.links
    node = _components(case, ~lk.is_dc)
    return Grid(ids=tuple(f"i{i + 1}" for i in range(int(node.max()) + 1)), node=node,
                ref=_reference_zones(case, node), origin=lk.origin, end=lk.end,
                b=np.where(lk.is_dc, 0.0, lk.base_mva / lk.x_pu), f_plus=lk.f_plus, f_minus=lk.f_minus, dc=lk.is_dc,
                rent=_components(case, np.ones(len(lk.ids), dtype=bool)))


def _bus_susceptance(g: Grid) -> np.ndarray:
    a = g.incidence
    return a.T @ (g.b[:, None] * a)


def ptdf(g: Grid) -> np.ndarray:
    """H_{l,n} = d f_l / d inj_n with the balancing withdrawal at the island reference (case susceptances)."""
    bus, n = _bus_susceptance(g), len(g.node)
    x = np.zeros((n, n))
    for i in range(len(g.ids)):
        keep = g.reduced(i)
        if len(keep):
            x[np.ix_(keep, keep)] = np.linalg.solve(bus[np.ix_(keep, keep)], np.eye(len(keep)))
    h = g.b[:, None] * (g.incidence @ x)
    h[np.abs(h) <= PTDF_NOISE] = 0.0
    return h


def injection(sv: Solved) -> np.ndarray:
    """Net injection (N,P,T): generation + (discharge - charge) + unserved - demand, from the primal solution."""
    gen, st = sv.case.gen, sv.case.storage
    inj = sv.var("use") - sv.case.demand
    np.add.at(inj, gen.zone, sv.var("g"))
    np.add.at(inj, st.zone, sv.var("dis") - sv.var("ch"))
    return inj


def dc_injection(sv: Solved, g: Grid) -> np.ndarray:
    """Injection (N,P,T) of the solved DC flows: +f_k at e(k), -f_k at o(k) (zero with no DC link)."""
    out = np.zeros(sv.case.demand.shape)
    f = sv.var("flow")[g.dc]
    np.add.at(out, g.end[g.dc], f)
    np.add.at(out, g.origin[g.dc], -f)
    return out


def angles_from_injection(g: Grid, inj: np.ndarray) -> np.ndarray:
    """theta (rad, theta_ref = 0) solving B_red theta = inj per island with `numpy.linalg.solve`, no PTDF."""
    bus, theta = _bus_susceptance(g), np.zeros(inj.shape)
    for i in range(len(g.ids)):
        keep = g.reduced(i)
        if len(keep):
            theta[keep] = np.linalg.solve(bus[np.ix_(keep, keep)], inj[keep].reshape(len(keep), -1)).reshape(
                (len(keep), *inj.shape[1:]))
    return theta


def line_flow(g: Grid, theta: np.ndarray) -> np.ndarray:
    """b_l (theta_o - theta_e) (L,P,T) MW."""
    return g.b[:, None, None] * (theta[g.origin] - theta[g.end])


def _flow_residual(sv: Solved, g: Grid, theta: np.ndarray) -> float:
    """max over AC lines of |f - b (theta_o - theta_e)| MW; DC links carry no angle relation and are skipped."""
    return float(np.abs(sv.var("flow") - line_flow(g, theta))[g.ac].max(initial=0.0))


def _line_dual_violation(sv: Solved, g: Grid, mu: np.ndarray) -> float:
    """max |mu| off the ratings and max(0, -mu sgn f) at a rating (complementary slackness, sign table 7.4a.5),
    over AC lines and DC links; a DC link may have different forward and reverse ratings."""
    f, slack = sv.var("flow"), sv.case.tolerances.binding_slack
    at_rating = (f >= g.f_plus[:, None, None] - slack) | (f <= -g.f_minus[:, None, None] + slack)
    off = np.where(at_rating, 0.0, np.abs(mu))
    on = np.where(at_rating, np.maximum(0.0, -mu * np.sign(f)), 0.0)
    return float(max(off.max(initial=0.0), on.max(initial=0.0)))


def _rent_residual(g: Grid, pi: np.ndarray, inj: np.ndarray, mu: np.ndarray, f: np.ndarray) -> float:
    """Congestion-rent identity per rent-component hour: sum_{n in C} pi (-inj) = sum_{l in C} mu f (AC lines and DC
    links; inj excludes DC flows), relative to max(1, |sum mu f|); the maximum over (C,p,t), so residuals of different
    components cannot cancel. With no DC link a component is an island (formulation 7.4a.5)."""
    n_comp = int(g.rent.max()) + 1
    lhs = np.zeros((n_comp, *pi.shape[1:]))
    rhs = np.zeros_like(lhs)
    np.add.at(lhs, g.rent, pi * -inj)
    np.add.at(rhs, g.rent[g.origin], mu * f)
    return float((np.abs(lhs - rhs) / np.maximum(1.0, np.abs(rhs))).max(initial=0.0))


def _ref_angle_rows_ok(sv: Solved, g: Grid) -> np.ndarray:
    """(I,P,T): the island-hour has one active `ref_angle` row (lo = hi = 0) whose only nonzero is on theta_ref."""
    lp = sv.lp
    shape = (len(g.ids), len(sv.case.periods), T)
    blk = lp.rows["ref_angle"]
    if blk.shape != shape:
        return np.zeros(shape, dtype=bool)
    ii, ip, it = np.indices(shape)
    rows = lp.a[blk.offset:blk.offset + blk.size]
    on_ref = np.asarray(rows[np.arange(blk.size), lp.cols["theta"].idx(g.ref[ii], ip, it).ravel()]).ravel() != 0.0
    single = np.diff(rows.indptr) == 1
    fixed = (blk.view(lp.row_lo) == 0.0) & (blk.view(lp.row_hi) == 0.0)
    return (single & on_ref).reshape(shape) & fixed & (np.abs(sv.var("theta")[g.ref]) <= ISLAND_ANGLE_TOL)


def _bal_sys_rows_ok(sv: Solved, g: Grid) -> np.ndarray:
    """(I,P,T): exactly one `bal_sys` row per island-hour with lo = hi = the island's demand (case data)."""
    case = sv.case
    demand = np.zeros((len(g.ids), *case.demand.shape[1:]))
    np.add.at(demand, g.node, case.demand)
    blk = sv.lp.rows["bal_sys"]
    if blk.shape != demand.shape:
        return np.zeros(demand.shape, dtype=bool)
    lo, hi = blk.view(sv.row_lo), blk.view(sv.row_hi)
    return (np.abs(lo - demand) <= ISLAND_ANGLE_TOL * np.maximum(1.0, demand)) & (lo == hi)


def _island_check(sv: Solved, g: Grid) -> tuple[int, str]:
    ok = _ref_angle_rows_ok(sv, g) if sv.case.dcpf_form == "angle" else _bal_sys_rows_ok(sv, g)
    refs = "; ".join(f"{i} ref {sv.case.zones[r]}" for i, r in zip(g.ids, g.ref))
    return int((~ok).sum()), f"{len(g.ids)} islands: {refs}"


def network_report(sv: Solved, eco: Economics) -> NetworkReport:
    """Recompute angles, flows, LMP components and rent from case data; collect the metrics of 7.4a.6."""
    g = grid(sv.case)
    h = ptdf(g)
    inj = injection(sv)
    mu, f, pi = eco.mu_link, sv.var("flow"), eco.pi
    rc_theta = angles_from_injection(g, inj + dc_injection(sv, g))
    lp_theta = "theta" in sv.lp.cols
    theta = sv.var("theta") if lp_theta else rc_theta
    energy = pi[g.ref[g.node]]
    congestion = -np.einsum("ln,lpt->npt", h, mu)
    violations, detail = _island_check(sv, g)
    metrics = {
        "kvl": _flow_residual(sv, g, theta), "ptdf": _flow_residual(sv, g, rc_theta),
        "lmp": float(np.abs(pi - (energy + congestion)).max(initial=0.0)),
        "rent": _rent_residual(g, pi, inj, mu, f), "line_duals": _line_dual_violation(sv, g, mu)}
    return NetworkReport(grid=g, h=h, inj=inj, theta=theta, theta_source="lp" if lp_theta else "recomputed",
                         lmp_energy=energy, lmp_congestion=congestion, metrics=metrics,
                         island_violations=violations, island_detail=detail)


def zone_hourly_columns(sv: Solved, rep: NetworkReport) -> dict[str, np.ndarray]:
    """Extra `zone_hourly` columns under dcpf (formulation 7.4a.8), raveled in (zone, period, t) order."""
    g, shape = rep.grid, rep.lmp_energy.shape
    zones, island = np.asarray(sv.case.zones, dtype=object), np.asarray(g.ids, dtype=object)[g.node]
    return {"lmp_energy_usd_mwh": rep.lmp_energy.ravel(), "lmp_congestion_usd_mwh": rep.lmp_congestion.ravel(),
            "lmp_loss_usd_mwh": np.zeros(shape).ravel(),
            "island_id": np.broadcast_to(island[:, None, None], shape).ravel(),
            "ref_zone": np.broadcast_to(zones[g.ref[g.node]][:, None, None], shape).ravel()}


def angles_table(sv: Solved, rep: NetworkReport) -> pd.DataFrame:
    g, shape = rep.grid, rep.theta.shape
    is_ref = np.zeros(len(g.node), dtype=bool)
    is_ref[g.ref] = True
    return sv.lp.cols["use"].frame().drop(columns="label").assign(
        theta_rad=rep.theta.ravel(), island_id=np.broadcast_to(np.asarray(g.ids, dtype=object)[g.node][:, None, None],
                                                              shape).ravel(),
        is_ref=np.broadcast_to(is_ref[:, None, None], shape).ravel(), theta_source=rep.theta_source)


def islands_table(case: Case, rep: NetworkReport) -> pd.DataFrame:
    g = rep.grid
    return pd.DataFrame({"zone": case.zones, "island_id": np.asarray(g.ids, dtype=object)[g.node],
                         "ref_zone": np.asarray(case.zones, dtype=object)[g.ref[g.node]]})
