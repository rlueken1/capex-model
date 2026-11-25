"""Shared helpers for the verifier health tests (tests/test_health_*.py).

Everything here is written from docs/formulation.md and docs/gates/gate-1.md:
  * `Spec` + `write_case`: build a case directory (CSV tables + case.yaml) from plain numpy data, so that fixtures
    and 50 randomized instances do not depend on the loader's internal arrays.
  * `linprog_z`: an INDEPENDENT build of the section 2 LP with scipy.optimize.linprog(method="highs"), written from
    the equations (2.1-2.3), used to cross-check the objective of the production model.
  * independent re-computations of the section 3 checks (complementary slackness, strong duality, rents, storage
    reduced costs, balance) from the solver arrays, used instead of trusting the audit layer's own verdicts.
Only the public surface of capex (run_case, solve_case, health_report, output_tables, load_case, Solved arrays) is used.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml
from scipy.optimize import linprog

from capex.audit.report import HealthReport, health_report
from capex.data import load_case
from capex.run import solve_case

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "cases"
COMMON = REPO / "data" / "common"
W1 = 365.0 / 3.0
T = 72
CANON_CASES = ["T1", "T2a", "T2b", "T2c", "T3a", "T3b", "T4"]

PROV = dict(source_id="toy_spec", vintage="F-0.2", retrieved="2026-11-22", method="assumed",
            basis="verifier health-test fixture", confidence="low")


# ------------------------------------------------------------------ case construction
@dataclass
class Spec:
    """Plain description of a toy case (all I/O units; one fuel-free marginal cost per resource)."""
    zones: list[str]
    weights: list[float]
    demand: np.ndarray                       # (Z, P, 72)
    resources: list[dict]
    links: list[dict] = field(default_factory=list)
    voll: float = 10_000.0
    switches: dict = field(default_factory=dict)
    solver: dict = field(default_factory=lambda: {"name": "highs"})
    seed: int = 0


def th(rid, zone, k0=0.0, xmax=0.0, mc=0.0, cfix=None, avail=None, kind="TH"):
    """Thermal / VRE resource. Existing: k0 > 0, xmax = 0. Candidate: k0 = 0, xmax > 0 (may be inf), cfix given."""
    status = "existing" if k0 > 0 else "candidate"
    return dict(id=rid, zone=zone, type=kind, status=status, k0=float(k0), xmax=float(xmax), mc=mc,
                cfix=cfix, avail=avail)


def st(rid, zone, p0=0.0, e0=0.0, xp=0.0, xe=0.0, eta_c=0.9, eta_d=0.9, sigma=0.0, vom=0.0, cp=None, ce=None,
       dmin=None, dmax=None):
    status = "existing" if p0 > 0 else "candidate"
    return dict(id=rid, zone=zone, type="ST", status=status, k0=float(p0), e0=float(e0), xmax=float(xp),
                xmaxE=float(xe), eta_c=eta_c, eta_d=eta_d, sigma=sigma, vom=vom, cfix=cp, cfixE=ce, dmin=dmin,
                dmax=dmax, mc=None, avail=None)


def link(lid, a, b, fwd, rev=None):
    return dict(id=lid, a=a, b=b, fwd=float(fwd), rev=float(fwd if rev is None else rev))


def flat_demand(levels: dict[str, list[float]], n_periods: int = 1) -> np.ndarray:
    """levels[zone] = list of (value) per hour (length 72) or scalar list for every period."""
    zs = list(levels)
    d = np.zeros((len(zs), n_periods, T))
    for i, z in enumerate(zs):
        d[i, :, :] = np.asarray(levels[z], float)
    return d


def _prov(n: int) -> dict:
    return {k: [v] * n for k, v in PROV.items()}


def write_case(spec: Spec, out: Path, case_id: str = "fx") -> Path:
    """Write CSV tables and case.yaml for `spec`; returns the case directory."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    zs, P = spec.zones, len(spec.weights)
    w = np.asarray(spec.weights, float)
    pids = [f"p{i + 1}" for i in range(P)]
    pd.DataFrame({"period_id": pids, "weight_blocks": w, "rep_kind": "single", "days_represented": 3 * w}
                 ).to_csv(out / "periods.csv", index=False)
    pd.DataFrame({"zone_id": zs, "name": [f"zone {z}" for z in zs], "rto": "PJM", **_prov(len(zs))}
                 ).to_csv(out / "zones.csv", index=False)
    rows = [(z, pids[p], t + 1, float(spec.demand[i, p, t])) for i, z in enumerate(zs) for p in range(P)
            for t in range(T)]
    pd.DataFrame(rows, columns=["zone", "period_id", "t", "demand_mw"]).to_csv(out / "load.csv", index=False)
    pd.DataFrame({"zone": zs, "net_of_btm": False, "year": 2025, **_prov(len(zs))}).to_csv(out / "load_meta.csv",
                                                                                          index=False)
    pd.DataFrame([dict(finance_class="toy_simple", mode="simple_crf", wacc_real_frac=0.07, **PROV)]
                 ).to_csv(out / "finance.csv", index=False)
    recs, avail_rows = [], []
    for r in spec.resources:
        rec = dict(resource_id=r["id"], zone=r["zone"], type=r["type"], tech=r["id"], status=r["status"],
                   k0_mw=r["k0"], xmax_mw=r["xmax"], dollar_year=2024, **PROV)
        if r["type"] == "ST":
            rec |= dict(e0_mwh=r.get("e0", 0.0), xmax_mwh=r.get("xmaxE", 0.0), vom_usd_mwh=r.get("vom", 0.0),
                        eta_c_frac=r["eta_c"], eta_d_frac=r["eta_d"], selfdis_frac_h=r.get("sigma", 0.0),
                        cfix_override_usd_mw_yr=r["cfix"], cfix_e_override_usd_mwh_yr=r.get("cfixE"),
                        dur_min_h=r.get("dmin"), dur_max_h=r.get("dmax"))
        else:
            rec |= dict(mc_override_usd_mwh=r["mc"], cfix_override_usd_mw_yr=r["cfix"])
            if r["type"] == "VRE":
                rec["mc_override_usd_mwh"] = r["mc"] if r["mc"] is not None else np.nan
        recs.append(rec)
        if r.get("avail") is not None:
            for p in range(P):
                for t in range(T):
                    avail_rows.append((r["id"], pids[p], t + 1, float(r["avail"][p][t])))
    pd.DataFrame(recs).to_csv(out / "resources.csv", index=False)
    tables = {n: {"file": f"{n}.csv"} for n in ("periods", "zones", "load", "load_meta", "resources", "finance")}
    tables["deflator"] = {"file": str(COMMON / "deflator.csv")}
    tables["sources"] = {"file": str(COMMON / "sources.csv")}
    if avail_rows:
        pd.DataFrame(avail_rows, columns=["resource_id", "period_id", "t", "availability_frac"]
                     ).to_csv(out / "availability.csv", index=False)
        tables["availability"] = {"file": "availability.csv"}
    if spec.links:
        pd.DataFrame([dict(link_id=l["id"], zone_from=l["a"], zone_to=l["b"], ntc_fwd_mw=l["fwd"],
                           ntc_rev_mw=l["rev"], **PROV) for l in spec.links]).to_csv(out / "links.csv", index=False)
        tables["links"] = {"file": "links.csv"}
    manifest = dict(case_id=case_id, description="verifier health fixture", schema_version="S-0.1",
                    formulation_version="F-0.2", base_dollar_year=2024, model_year=2025, dt_h=1.0,
                    voll_usd_mwh=float(spec.voll), voll_dollar_year=2024, finance_default="toy_simple", seed=spec.seed,
                    solver=spec.solver, switches=spec.switches, tables=tables)
    (out / "case.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return out


# ------------------------------------------------------------------ running
def solve_audit(case_dir, solver=None, scaling=None):
    """(Solved, HealthReport) for a case directory."""
    sv = solve_case(load_case(case_dir), scaling, solver)
    return sv, health_report(sv)


def failing(health: HealthReport) -> list[str]:
    c = health.checks
    return c.loc[c["status"] == "fail", "check_id"].tolist()


def non_pass(health: HealthReport) -> pd.DataFrame:
    c = health.checks
    return c[c["status"] != "pass"][["check_id", "status", "value", "tolerance", "detail"]]


# ------------------------------------------------------------------ independent LP (formulation section 2)
def linprog_z(spec: Spec) -> float:
    """Optimal objective Z (excluding the constant Z0, which is 0 for every spec here), via scipy linprog/HiGHS."""
    zi = {z: i for i, z in enumerate(spec.zones)}
    G = [r for r in spec.resources if r["type"] in ("TH", "VRE")]
    S = [r for r in spec.resources if r["type"] == "ST"]
    L = spec.links
    P = len(spec.weights)
    w = np.asarray(spec.weights, float)
    n = 0

    def alloc(*shape):
        nonlocal n
        size = int(np.prod(shape)) if shape else 1
        ix = np.arange(n, n + size).reshape(shape)
        n += size
        return ix

    ix_x, ix_xp, ix_xe = alloc(len(G)), alloc(len(S)), alloc(len(S))
    ix_g = alloc(len(G), P, T)
    ix_ch, ix_dis, ix_soc = alloc(len(S), P, T), alloc(len(S), P, T), alloc(len(S), P, T)
    ix_f = alloc(len(L), P, T)
    ix_u = alloc(len(spec.zones), P, T)
    c = np.zeros(n)
    lo, hi = np.zeros(n), np.full(n, np.inf)
    for i, r in enumerate(G):
        c[ix_x[i]] = r["cfix"] or 0.0
        hi[ix_x[i]] = r["xmax"]
        c[ix_g[i]] = np.broadcast_to(w[:, None] * (r["mc"] or 0.0), (P, T))
    for i, r in enumerate(S):
        c[ix_xp[i]], c[ix_xe[i]] = r["cfix"] or 0.0, r.get("cfixE") or 0.0
        hi[ix_xp[i]], hi[ix_xe[i]] = r["xmax"], r["xmaxE"]
        c[ix_dis[i]] = np.broadcast_to(w[:, None] * r.get("vom", 0.0), (P, T))
    for i, l in enumerate(L):
        lo[ix_f[i]], hi[ix_f[i]] = -l["rev"], l["fwd"]
    c[ix_u] = w[None, :, None] * spec.voll
    hi[ix_u] = spec.demand

    eq_r, eq_c, eq_v, eq_b = [], [], [], []
    ub_r, ub_c, ub_v, ub_b = [], [], [], []
    ne = nu = 0

    def eq_row(entries, rhs):
        nonlocal ne
        for col, val in entries:
            eq_r.append(ne), eq_c.append(col), eq_v.append(val)
        eq_b.append(rhs)
        ne += 1

    def ub_row(entries, rhs):
        nonlocal nu
        for col, val in entries:
            ub_r.append(nu), ub_c.append(col), ub_v.append(val)
        ub_b.append(rhs)
        nu += 1

    for z in spec.zones:
        for p in range(P):
            for t in range(T):
                e = [(ix_g[i, p, t], 1.0) for i, r in enumerate(G) if r["zone"] == z]
                e += [(ix_dis[i, p, t], 1.0) for i, r in enumerate(S) if r["zone"] == z]
                e += [(ix_ch[i, p, t], -1.0) for i, r in enumerate(S) if r["zone"] == z]
                e += [(ix_f[i, p, t], 1.0) for i, l in enumerate(L) if l["b"] == z]
                e += [(ix_f[i, p, t], -1.0) for i, l in enumerate(L) if l["a"] == z]
                e += [(ix_u[zi[z], p, t], 1.0)]
                eq_row(e, spec.demand[zi[z], p, t])
    for i, r in enumerate(G):
        a = np.broadcast_to(np.asarray(r["avail"], float) if r.get("avail") is not None else np.ones((P, T)), (P, T))
        a = np.where(a < 1e-3, 0.0, a)           # section 6.1 rule (b)
        for p in range(P):
            for t in range(T):
                ub_row([(ix_g[i, p, t], 1.0), (ix_x[i], -a[p, t])], a[p, t] * r["k0"])
    for i, r in enumerate(S):
        E0, P0 = r.get("e0", 0.0), r["k0"]
        for p in range(P):
            for t in range(T):
                tp = (t - 1) % T
                ub_row([(ix_ch[i, p, t], 1.0), (ix_dis[i, p, t], 1.0), (ix_xp[i], -1.0)], P0)
                eq_row([(ix_soc[i, p, t], 1.0), (ix_soc[i, p, tp], -(1 - r["sigma"])),
                        (ix_ch[i, p, t], -r["eta_c"]), (ix_dis[i, p, t], 1.0 / r["eta_d"])], 0.0)
                ub_row([(ix_soc[i, p, t], 1.0), (ix_xe[i], -1.0)], E0)
        if r["status"] == "candidate":
            if r.get("dmin") is not None:
                ub_row([(ix_xe[i], -1.0), (ix_xp[i], r["dmin"])], 0.0)
            if r.get("dmax") is not None:
                ub_row([(ix_xe[i], 1.0), (ix_xp[i], -r["dmax"])], 0.0)
    a_eq = sp.csr_matrix((eq_v, (eq_r, eq_c)), shape=(ne, n))
    a_ub = sp.csr_matrix((ub_v, (ub_r, ub_c)), shape=(nu, n))
    res = linprog(c, A_ub=a_ub, b_ub=np.asarray(ub_b), A_eq=a_eq, b_eq=np.asarray(eq_b),
                  bounds=np.column_stack([lo, hi]), method="highs")
    assert res.status == 0, res.message
    return float(res.fun)


# ------------------------------------------------------------------ randomized instances
def random_spec(seed: int) -> Spec:
    """Seeded small instance: 1-3 zones, 1-3 periods, mixed thermal / VRE / storage / links."""
    rng = np.random.default_rng(1000 + seed)
    nz, npd = int(rng.integers(1, 4)), int(rng.integers(1, 4))
    zones = [f"Z{i}" for i in range(nz)]
    cuts = rng.dirichlet(np.ones(npd))
    weights = list(1.0 + cuts * (W1 - npd))                   # each >= 1, sum = 365/3
    tt = np.arange(T)
    demand = np.zeros((nz, npd, T))
    for i in range(nz):
        base = rng.uniform(60, 160)
        for p in range(npd):
            shape = 1 + 0.35 * np.sin(2 * np.pi * (tt - rng.uniform(0, 24)) / 24) * rng.uniform(0.3, 1.0)
            demand[i, p] = base * rng.uniform(0.7, 1.3) * shape * (1 + 0.04 * rng.standard_normal(T))
    demand = np.maximum(demand, 5.0)
    res, links = [], []
    for z in zones:
        for j in range(int(rng.integers(1, 3))):                              # existing thermals
            res.append(th(f"{z}_ex{j}", z, k0=rng.uniform(30, 120), mc=rng.uniform(15, 70),
                          avail=rng.uniform(0.75, 1.0, size=(npd, T)) if rng.random() < 0.3 else None))
        if rng.random() < 0.8:                                                # candidate thermal
            res.append(th(f"{z}_cand", z, xmax=np.inf if rng.random() < 0.5 else rng.uniform(20, 100),
                          mc=rng.uniform(10, 110), cfix=rng.uniform(20_000, 150_000)))
        if rng.random() < 0.6:                                                # VRE
            prof = np.clip(0.45 + 0.45 * np.sin(2 * np.pi * (tt - rng.uniform(0, 24)) / 24)
                           + 0.2 * rng.standard_normal((npd, T)), 0.0, 1.0)
            if rng.random() < 0.5:
                res.append(th(f"{z}_vre", z, k0=rng.uniform(20, 80), kind="VRE", mc=0.0, avail=prof))
            else:
                res.append(th(f"{z}_vre", z, xmax=np.inf if rng.random() < 0.5 else rng.uniform(30, 200), kind="VRE",
                              mc=0.0, cfix=rng.uniform(40_000, 120_000), avail=prof))
        if rng.random() < 0.6:                                                # storage
            ec, ed = rng.uniform(0.8, 0.97, 2)
            sig = 0.0 if rng.random() < 0.5 else 0.002
            if rng.random() < 0.5:
                p0 = rng.uniform(5, 40)
                res.append(st(f"{z}_bat", z, p0=p0, e0=p0 * rng.uniform(2, 6), eta_c=ec, eta_d=ed, sigma=sig,
                              vom=rng.uniform(0, 3)))
            else:
                xp = rng.uniform(10, 50)
                res.append(st(f"{z}_bat", z, xp=xp, xe=xp * 6.0, eta_c=ec, eta_d=ed, sigma=sig,
                              vom=rng.uniform(0, 3), cp=rng.uniform(0, 20_000), ce=rng.uniform(1_000, 8_000),
                              dmin=2.0, dmax=6.0))
    for i in range(nz - 1):
        links.append(link(f"L{i}", zones[i], zones[i + 1], rng.uniform(10, 80), rng.uniform(10, 80)))
    if nz == 3 and rng.random() < 0.5:
        links.append(link("L2", zones[2], zones[0], rng.uniform(10, 80), rng.uniform(10, 80)))
    return Spec(zones=zones, weights=weights, demand=demand, resources=res, links=links,
                voll=float(rng.uniform(2_000, 10_000)), seed=seed)


# ------------------------------------------------------------------ independent re-computation of section 3 checks
def lp_arrays(sv):
    """Scaled LP arrays and solver output (public fields of the LP / Solution)."""
    lp, sol = sv.lp, sv.sol
    return lp.a, lp.c, lp.row_lo, lp.row_hi, lp.col_lo, lp.col_hi, sol.x, sol.row_dual, sol.col_dual, sol.row_activity


def cs_and_signs(sv):
    """(max |y*slack| / max(1,|Z~|) over rows and bounds, max sign violation, strong-duality rel gap), scaled units.

    Sign rule (formulation 1.3): row y <= 0 on a binding <= side, y >= 0 on a binding >= side, free on equalities;
    column s >= 0 at the lower bound, s <= 0 at the upper bound, s = 0 strictly inside."""
    a, c, rlo, rhi, clo, chi, x, y, s, act = lp_arrays(sv)
    z = float(c @ x)
    scale = max(1.0, abs(z))
    cs, viol = 0.0, 0.0
    for i in range(len(y)):
        d_lo = act[i] - rlo[i] if np.isfinite(rlo[i]) else np.inf
        d_hi = rhi[i] - act[i] if np.isfinite(rhi[i]) else np.inf
        if y[i] > 0:
            cs = max(cs, abs(y[i]) * d_lo)
            viol = max(viol, y[i] if not np.isfinite(rlo[i]) else 0.0)
        elif y[i] < 0:
            cs = max(cs, abs(y[i]) * d_hi)
            viol = max(viol, -y[i] if not np.isfinite(rhi[i]) else 0.0)
    for j in range(len(s)):
        if s[j] > 0:
            cs = max(cs, s[j] * (x[j] - clo[j]))
            viol = max(viol, s[j] if not np.isfinite(clo[j]) else 0.0)
        elif s[j] < 0:
            cs = max(cs, -s[j] * (chi[j] - x[j]) if np.isfinite(chi[j]) else abs(s[j]))
            viol = max(viol, -s[j] if not np.isfinite(chi[j]) else 0.0)
    # dual objective: sum_i b_i y_i + sum_j bound_j s_j with b/bound the side the dual prices
    dual = 0.0
    for i in range(len(y)):
        if y[i] > 0 and np.isfinite(rlo[i]):
            dual += y[i] * rlo[i]
        elif y[i] < 0 and np.isfinite(rhi[i]):
            dual += y[i] * rhi[i]
    for j in range(len(s)):
        if s[j] > 0 and np.isfinite(clo[j]):
            dual += s[j] * clo[j]
        elif s[j] < 0 and np.isfinite(chi[j]):
            dual += s[j] * chi[j]
    return cs / scale, viol, abs(z - dual) / scale


def stationarity_residual(sv) -> float:
    """max |c - A'y - s| (scaled): defines s_j = c_j - sum_i a_ij y_i of formulation 1.3."""
    a, c, *_rest = lp_arrays(sv)
    y, s = sv.sol.row_dual, sv.sol.col_dual
    return float(np.abs(c - a.T @ y - s).max())


def rents_from_duals(sv):
    """dict of per-resource rents recomputed from raw duals with the section 3 conversions (unscaled $)."""
    case, w = sv.case, sv.case.w
    out = {}
    y_gen, y_pwr, y_em = sv.row_dual("gen_max"), sv.row_dual("st_pwr"), sv.row_dual("st_emax")
    for i, rid in enumerate(case.gen.ids):
        rho = -y_gen[i] / w[:, None]                                  # $/MWh per available MW
        out[rid] = dict(R=float((w[:, None] * case.gen.avail[i] * rho).sum()))
    for i, rid in enumerate(case.storage.ids):
        out[rid] = dict(RP=float((-y_pwr[i]).sum()), RE=float((-y_em[i]).sum()))
    return out


def storage_rc_from_duals(sv, sid_index: int):
    """(s_xP, s_xE) recomputed from duals per section 3 check 5: s_xP = C^P - R^P + d_lo y_lo + d_hi y_hi,
    s_xE = C^E - R^E - y_lo - y_hi (unscaled $)."""
    case, st_ = sv.case, sv.case.storage
    rid = st_.ids[sid_index]
    y_pwr, y_em = sv.row_dual("st_pwr")[sid_index], sv.row_dual("st_emax")[sid_index]
    rp, re_ = float((-y_pwr).sum()), float((-y_em).sum())
    y_lo = y_hi = 0.0
    lo_ids = sv.lp.rows["st_dur_lo"].ids[0]
    hi_ids = sv.lp.rows["st_dur_hi"].ids[0]
    if rid in lo_ids:
        y_lo = float(sv.row_dual("st_dur_lo")[lo_ids.index(rid)])
    if rid in hi_ids:
        y_hi = float(sv.row_dual("st_dur_hi")[hi_ids.index(rid)])
    d_lo = st_.dur_lo[sid_index] if not np.isnan(st_.dur_lo[sid_index]) else 0.0
    d_hi = st_.dur_hi[sid_index] if not np.isnan(st_.dur_hi[sid_index]) else 0.0
    s_xp = st_.cp[sid_index] - rp + d_lo * y_lo + d_hi * y_hi
    s_xe = st_.ce[sid_index] - re_ - y_lo - y_hi
    return s_xp, s_xe


def independent_balance(case_dir: Path, tables: dict[str, pd.DataFrame]) -> float:
    """max |sum(injections) - D| in MW recomputed from the OUTPUT dispatch / flows / zone_hourly tables and the INPUT
    csv files of the case (resource zones, link ends, demand)."""
    case_dir = Path(case_dir)
    res = pd.read_csv(case_dir / "resources.csv").set_index("resource_id")
    load = pd.read_csv(case_dir / "load.csv").rename(columns={"period_id": "period"})
    key = ["zone", "period", "t"]
    dem = load.set_index(key)["demand_mw"]
    d = tables["dispatch"].copy()
    d["zone"] = d["resource"].map(res["zone"])
    inj = (d["g_mw"].fillna(0) + d["discharge_mw"].fillna(0) - d["charge_mw"].fillna(0)).groupby(
        [d["zone"], d["period"], d["t"]]).sum()
    total = inj.rename_axis(key).reindex(dem.index).fillna(0.0)
    zh = tables["zone_hourly"].set_index(key)
    total = total + zh["unserved_mw"].reindex(dem.index).fillna(0.0)
    if (case_dir / "links.csv").exists():
        lk = pd.read_csv(case_dir / "links.csv").set_index("link_id")
        fl = tables["flows"].copy()
        fl["a"], fl["b"] = fl["link"].map(lk["zone_from"]), fl["link"].map(lk["zone_to"])
        into = fl.groupby(["b", "period", "t"])["flow_mw"].sum().rename_axis(key)
        out = fl.groupby(["a", "period", "t"])["flow_mw"].sum().rename_axis(key)
        total = total + into.reindex(dem.index).fillna(0.0) - out.reindex(dem.index).fillna(0.0)
    return float((total - dem).abs().max())


def rent_violations(sv, tol: float = 1e-6) -> list[str]:
    """Section 3 checks 5-6 recomputed from raw duals: zero-profit rule per candidate, revenue identity per resource,
    storage reduced costs. Returns human-readable violations (empty list = all pass)."""
    case, w = sv.case, sv.case.w
    gen, st_ = case.gen, case.storage
    pi = sv.row_dual("bal") / w[None, :, None]                         # (Z,P,T) $/MWh
    rents = rents_from_duals(sv)
    x, g, xp, xe = sv.var("x"), sv.var("g"), sv.var("xP"), sv.var("xE")
    ch, dis = sv.var("ch"), sv.var("dis")
    out = []
    for i, rid in enumerate(gen.ids):
        r_cap, k = rents[rid]["R"], gen.k0[i] + x[i]
        rev = float((w[:, None] * (pi[gen.zone[i]] - gen.mc[i]) * g[i]).sum())
        if abs(rev - r_cap * k) / max(1.0, abs(rev), abs(r_cap * k)) > tol:
            out.append(f"{rid}: revenue identity {rev!r} vs R*K {r_cap * k!r}")
        if gen.status[i] != "candidate":
            continue
        c, xm = gen.cfix[i], gen.xmax[i]
        at_max = np.isfinite(xm) and x[i] >= xm - 1e-6
        if x[i] <= 1e-6:
            ok = r_cap <= c * (1 + tol)
        elif at_max:
            ok = r_cap >= c * (1 - tol)
        else:
            ok = abs(r_cap - c) <= tol * c
        if not ok:
            out.append(f"{rid}: zero-profit rule violated (x={x[i]!r}, xmax={xm!r}, R={r_cap!r}, Cfix={c!r})")
    for i, rid in enumerate(st_.ids):
        rp, re_ = rents[rid]["RP"], rents[rid]["RE"]
        p_cap, e_cap = st_.p0[i] + xp[i], st_.e0[i] + xe[i]
        rev = float((w[:, None] * (pi[st_.zone[i]] * (dis[i] - ch[i]) - st_.vom[i] * dis[i])).sum())
        rhs = rp * p_cap + re_ * e_cap
        if abs(rev - rhs) / max(1.0, abs(rev), abs(rhs)) > tol:
            out.append(f"{rid}: storage revenue identity {rev!r} vs R^P P + R^E E {rhs!r}")
        s_xp, s_xe = storage_rc_from_duals(sv, i)
        f = sv.lp.scaling.dual_factor
        for name, mine, solver in (("xP", s_xp, sv.col_dual("xP")[i]), ("xE", s_xe, sv.col_dual("xE")[i])):
            if abs(mine - solver) / f > tol:
                out.append(f"{rid}: reduced cost {name} recomputed {mine!r} vs solver {solver!r}")
        d_lo, d_hi = st_.dur_lo[i], st_.dur_hi[i]
        if st_.status[i] == "candidate" and not np.isnan(d_lo) and d_lo == d_hi:
            comb = (st_.cp[i] + d_lo * st_.ce[i]) - (rp + d_lo * re_)
            tolc = tol * max(1.0, st_.cp[i] + d_lo * st_.ce[i])
            at_max = xp[i] >= st_.xp_max[i] - 1e-6
            if xp[i] <= 1e-6:
                ok = comb >= -tolc
            elif at_max:
                ok = comb <= tolc
            else:
                ok = abs(comb) <= tolc
            if not ok:
                out.append(f"{rid}: fixed-duration combined zero-profit rule violated (cost-rent={comb!r})")
    return out


def soc_residual(sv) -> float:
    """max |e_t - (1-sigma) e_{t-} - eta_c c_t + d_t/eta_d| (MWh) recomputed from the primal solution and case data."""
    st_ = sv.case.storage
    if not len(st_.ids):
        return 0.0
    e, c, d = sv.var("soc"), sv.var("ch"), sv.var("dis")
    prev = np.roll(e, 1, axis=2)
    sig, ec, ed = (a[:, None, None] for a in (st_.sigma, st_.eta_c, st_.eta_d))
    return float(np.abs(e - (1 - sig) * prev - ec * c + d / ed).max())


def tol_pi(pi):
    return np.maximum(0.01, 1e-5 * np.abs(pi))


def price_setter_violations(sv, table: pd.DataFrame) -> list[str]:
    """Section 4 price checks recomputed independently: MARGINAL_UNIT / TIE_AT_BOUND: price within tol_pi of the setter's
    marginal cost (table `setter_cost`); STORAGE_DIS: |pi - VOM - v/eta_d| <= tol_pi and STORAGE_CH: |pi - eta_c v| <= tol_pi
    with v recomputed from the raw `st_soc` dual; VOLL: |pi - VOLL| <= tol_pi or pi >= VOLL (blackout); CAPACITY_RENT:
    price inside [price_lo, price_hi] +- tol_pi. UNEXPLAINED rows are violations."""
    out = []
    voll, w, stg = sv.case.voll, sv.case.w, sv.case.storage
    pix = {p: i for i, p in enumerate(sv.case.periods)}
    y_soc = sv.row_dual("st_soc") if len(stg.ids) else None
    for r in table.itertuples():
        tol = float(tol_pi(r.price))
        pc = r.primary_class
        if pc == "UNEXPLAINED":
            out.append(f"UNEXPLAINED {r.zone} {r.period_id} t={r.t}")
        elif pc == "CAPACITY_RENT":
            if not (r.price_lo - tol <= r.price <= r.price_hi + tol):
                out.append(f"CAPACITY_RENT {r.zone} t={r.t}: {r.price} outside [{r.price_lo}, {r.price_hi}]")
        elif pc == "VOLL":
            if abs(r.price - voll) > tol and r.price < voll - tol:
                out.append(f"VOLL {r.zone} t={r.t}: price {r.price} vs VOLL {voll}")
        elif pc in ("STORAGE_DIS", "STORAGE_CH"):
            for sid in str(r.setter_ids).split(","):
                i, p = stg.ids.index(sid), pix[r.period_id]
                v = -y_soc[i, p, r.t - 1] / w[p]
                expect = stg.vom[i] + v / stg.eta_d[i] if pc == "STORAGE_DIS" else stg.eta_c[i] * v
                if abs(r.price - expect) > tol:
                    out.append(f"{pc} {r.zone} t={r.t}: price {r.price} vs {expect}")
        elif abs(r.residual) > tol:
            out.append(f"{pc} {r.zone} t={r.t}: residual {r.residual}")
    return out


# ------------------------------------------------------------------ small designed toys (formulation section 10 style)
def _spike(level=50.0, spike=110.0):
    d = np.full(T, level)
    d[T - 1] = spike
    return d


def toy_spec(name: str) -> Spec:
    """Designed toys. S1/S2 close the W4a gap (a STORAGE_CH / STORAGE_DIS tie actually occurs):
    S1: G1 100 MW MC 20, G2 200 MW MC 60, existing storage 20 MW / 20 MWh (eta .9/.9); D = 50 MW except t=72: 150.
        Storage charges 20/0.9 = 22.2 MWh off-peak (interior in at least one hour: P = 20 < 22.2) and discharges
        20*0.9 = 18 MW (< P, energy-limited, interior) in t=72 where G2 (32 MW, interior) is marginal at 60.
    S2: G1 100 MW MC 20 only; existing storage 20 MW / 40 MWh; D = 50 MW except t=72: 110 (10 MW short of G1).
        Storage alone covers the shortfall (d = 10 < P, interior) so no thermal is marginal in t=72:
        pi_72 = MC/(eta_c eta_d) = 24.691 (STORAGE_DIS); charging hours are MARGINAL_UNIT G1 with a STORAGE_CH tie.
    S2asym / T2asym: S2 and a T2a-like case with eta_c = .95, eta_d = .80 (so swapping eta changes the model).
    P2: two-period T1 (weights 80 and 365/3 - 80), second period at 0.8 x demand."""
    if name == "S1":
        return Spec(["A"], [W1], np.array([[_spike(50.0, 150.0)]]),
                    [th("g1", "A", k0=100, mc=20.0), th("g2", "A", k0=200, mc=60.0),
                     st("bat", "A", p0=20, e0=20, eta_c=0.9, eta_d=0.9)])
    if name in ("S2", "S2asym"):
        e = (0.9, 0.9) if name == "S2" else (0.95, 0.80)
        return Spec(["A"], [W1], np.array([[_spike(50.0, 110.0)]]),
                    [th("g1", "A", k0=100, mc=20.0), st("bat", "A", p0=20, e0=40, eta_c=e[0], eta_d=e[1])])
    if name == "T2asym":
        d = np.r_[np.full(36, 50.0), np.full(36, 150.0)]
        return Spec(["A"], [W1], np.array([[d]]),
                    [th("g1", "A", k0=100, mc=20.0), th("g2", "A", k0=200, mc=60.0),
                     st("bat", "A", p0=10, e0=40, eta_c=0.95, eta_d=0.80)])
    if name == "P2":
        d = np.r_[np.full(36, 80.0), np.full(24, 120.0), np.full(12, 150.0)]
        return Spec(["A"], [80.0, W1 - 80.0], np.array([[d, 0.8 * d]]),
                    [th("base", "A", xmax=np.inf, mc=20.0, cfix=150_000.0),
                     th("peak", "A", xmax=np.inf, mc=80.0, cfix=60_000.0)])
    raise KeyError(name)


TOYS = ["S1", "S2", "S2asym", "T2asym", "P2"]
