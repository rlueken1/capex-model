"""Gate 4 comparison harness (verifier-owned, G4-3): gate-4.md section 5 metrics F0, C0, C1, C2, G1, G2, L1, L2, P1, U0.

Written from docs/gates/gate-4.md only. Nothing here imports capex. Inputs are (a) the case CSVs under cases/rts_gmlc*,
(b) the PLEXOS reference tables cases/rts_gmlc/reference/ref_plexos_da_{alltx,notx}.csv.gz, and (c) for the run-side
metrics, the output tables of a capex run (dict of DataFrames as `capex.run.output_tables` returns them, or a directory of
CSVs). The "independent route" for the zonal LP is scipy.optimize.linprog(method="highs") built from the case CSVs.

Window (gate-4.md section 2): the reference starts exactly at block p063 t=1 and is 336 h; the comparison uses p063..p066 plus
the first 48 h of p067 (4 x 72 + 48 = 336).
Sign conventions: reference branch flow + = From Bus -> To Bus (branch.csv); DC1 `113_316_1` + = bus 113 -> 316; our link
flow + = zone_from -> zone_to.
"""
from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import linprog

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "cases"
RAW = CASES / "raw" / "rts_gmlc" / "RTS_Data" / "SourceData"
REFDIR = CASES / "rts_gmlc" / "reference"
RUN_PERIODS = ["p063", "p064", "p065", "p066", "p067"]            # R4-Z/C/N/NP window run (360 h)
N_HOURS = 336
VOLL = 10_000.0
TECH_GROUP = {"coal": "coal", "gas_cc": "gas_cc", "gas_ct": "gas_ct", "oil_ct": "oil", "oil_st": "oil", "nuclear": "nuclear",
              "hydro": "hydro", "wind": "wind", "solar_pv": "pv", "solar_rtpv": "rtpv", "csp": "csp", "storage": "storage"}
GROUPS = ["coal", "gas_cc", "gas_ct", "oil", "nuclear", "hydro", "wind", "pv", "rtpv"]


# ------------------------------------------------------------------------------------------ window and reference tables
def window_index() -> pd.MultiIndex:
    rows = [(p, t) for p in RUN_PERIODS for t in range(1, 73)][:N_HOURS]
    return pd.MultiIndex.from_tuples(rows, names=["period_id", "t"])


@lru_cache(maxsize=None)
def ref_long(variant: str) -> pd.DataFrame:
    """variant in {"alltx", "notx"}: tidy reference table (variable, entity, period_id, t, value, ...)."""
    return pd.read_csv(REFDIR / f"ref_plexos_da_{variant}.csv.gz")


@lru_cache(maxsize=None)
def ref_wide(variant: str, variable: str) -> pd.DataFrame:
    """(336 hours) x (entity) for one variable, indexed like window_index()."""
    r = ref_long(variant)
    w = r[r["variable"] == variable].pivot(index=["period_id", "t"], columns="entity", values="value")
    return w.reindex(window_index())


def ref_meta() -> pd.DataFrame:
    return pd.read_csv(REFDIR / "ref_plexos_da_meta.csv")


# ------------------------------------------------------------------------------------------ case data (CSV route)
class CaseData:
    """rts_gmlc* case CSVs as the verifier reads them: resources, per-hour availability, load, links, fuel prices, MC."""

    def __init__(self, case: str):
        self.dir = CASES / case
        self.cfg = yaml.safe_load((self.dir / "case.yaml").read_text())
        self.tables = {k: (self.dir / v["file"]).resolve() for k, v in self.cfg["tables"].items()}
        self.res = pd.read_csv(self.tables["resources"])
        self.zones = pd.read_csv(self.tables["zones"])["zone_id"].tolist()
        self.links = pd.read_csv(self.tables["links"]) if "links" in self.tables else pd.DataFrame()
        idx = window_index()
        ld = pd.read_csv(self.tables["load"])
        self.load = ld.pivot(index=["period_id", "t"], columns="zone", values="demand_mw").reindex(idx)[self.zones]
        av = pd.read_csv(self.tables["availability"])
        av = av[av["period_id"].isin(RUN_PERIODS)].pivot(index=["period_id", "t"], columns="resource_id",
                                                           values="availability_frac").reindex(idx)
        k0 = self.res.set_index("resource_id")["k0_mw"]
        cap = pd.DataFrame(1.0, index=idx, columns=k0.index)
        for c in av.columns:
            if c in cap:
                cap[c] = av[c]
        self.cap = cap * k0                                         # MW available per unit-hour (thermal A = 1, assumption A6)
        fp = pd.read_csv(self.tables["fuel_prices"])
        fp = fp[fp["period_id"].isin(RUN_PERIODS)].pivot(index=["period_id", "t"], columns="fuel_hub",
                                                           values="price_usd_mmbtu").reindex(idx)
        fm = pd.read_csv(self.tables["fuel_map"]).set_index("fuel")["fuel_hub"]
        mc = pd.DataFrame(0.0, index=idx, columns=k0.index)
        for _, r in self.res.iterrows():
            if r["type"] == "TH":
                mc[r["resource_id"]] = r["heat_rate_mmbtu_mwh"] * fp[fm[r["fuel"]]].to_numpy() + float(r.get("vom_usd_mwh") or 0.0)
            else:
                mc[r["resource_id"]] = float(r.get("vom_usd_mwh") or 0.0) if pd.notna(r.get("vom_usd_mwh")) else 0.0
        self.mc = mc                                                # $/MWh, deflator factor 1 (all dollar_year 2024)
        assert (self.res["dollar_year"] == self.cfg["base_dollar_year"]).all()
        self.zone_of = self.res.set_index("resource_id")["zone"]
        self.tech = self.res.set_index("resource_id")["tech"].map(TECH_GROUP)
        self.bus_of = self.res.set_index("resource_id")["x_bus_id"].astype(int)


@lru_cache(maxsize=None)
def case_data(case: str) -> CaseData:
    return CaseData(case)


# ------------------------------------------------------------------------------------------ reference topology
@lru_cache(maxsize=None)
def raw_topology():
    bus = pd.read_csv(RAW / "bus.csv").set_index("Bus ID")
    br = pd.read_csv(RAW / "branch.csv")
    br["a_from"], br["a_to"] = br["From Bus"].map(bus["Area"]), br["To Bus"].map(bus["Area"])
    dc = pd.read_csv(RAW / "dc_branch.csv")
    return bus, br, dc


AREA_ZONE = {1: "r1", 2: "r2", 3: "r3"}


def reference_link_flows(variant: str, case: str = "rts_gmlc_px") -> pd.DataFrame:
    """PLEXOS flows summed per area pair (+ = zone_from -> zone_to of our links.csv) and DC1 as its own link
    (gate-4.md F0: 'tie flows summed per area pair and DC1 as the DC link'). Columns = our link ids."""
    cd = case_data(case)
    _, br, dc = raw_topology()
    fl = ref_wide(variant, "flow")
    out = pd.DataFrame(0.0, index=fl.index, columns=cd.links["link_id"].tolist())
    for _, l in cd.links.iterrows():
        lid, zf, zt = l["link_id"], l["zone_from"], l["zone_to"]
        if lid.startswith("dc_"):
            for _, d in dc.iterrows():
                key = f"{int(d['From Bus'])}_{int(d['To Bus'])}_1"
                sgn = 1.0 if AREA_ZONE[int(raw_topology()[0].loc[d["From Bus"], "Area"])] == zf else -1.0
                out[lid] += sgn * fl[key]
            continue
        for _, b in br.iterrows():
            if b["a_from"] == b["a_to"]:
                continue
            za, zb = AREA_ZONE[b["a_from"]], AREA_ZONE[b["a_to"]]
            if (za, zb) == (zf, zt):
                out[lid] += fl[b["UID"]]
            elif (za, zb) == (zt, zf):
                out[lid] -= fl[b["UID"]]
    return out


# ------------------------------------------------------------------------------------------ F0, C0 route
def f0_violations(variant: str, case: str) -> dict:
    """F0 (gate-4.md section 5): the PLEXOS dispatch, with tie flows per area pair and DC1 as the DC link, against the
    constraints of OUR LP built from the case CSVs: 0 <= g <= availability x k0, nodal(zonal) balance with the flows,
    -ntc_rev <= f <= ntc_fwd. Returns the maximum violation (MW) of each constraint family; the rule is every value <= 1 MW."""
    cd = case_data(case)
    g = ref_wide(variant, "generation")
    units = cd.res["resource_id"].tolist()
    gu = g[units]
    out = {"gen_below_0": float((-gu).max().max()), "gen_above_cap": float((gu - cd.cap[units]).max().max())}
    zg = gu.T.groupby(cd.zone_of[units]).sum().T[cd.zones]
    if len(cd.zones) == 1:
        out["balance"] = float((zg.iloc[:, 0] - cd.load.iloc[:, 0]).abs().max())
        out["flow_above_limit"] = 0.0
        return out
    f = reference_link_flows(variant, case)
    net_out = pd.DataFrame(0.0, index=g.index, columns=cd.zones)
    for _, l in cd.links.iterrows():
        net_out[l["zone_from"]] += f[l["link_id"]]
        net_out[l["zone_to"]] -= f[l["link_id"]]
    out["balance"] = float((zg - cd.load - net_out).abs().max().max())
    over = [(f[l["link_id"]] - l["ntc_fwd_mw"]).max() for _, l in cd.links.iterrows()]
    under = [(-f[l["link_id"]] - l["ntc_rev_mw"]).max() for _, l in cd.links.iterrows()]
    out["flow_above_limit"] = float(max(max(over), max(under)))
    return out


def px_dispatch_cost(variant: str, case: str) -> float:
    """C^PX_our = sum over the 336 h of g^PX x MC^our (PLEXOS dispatch priced at our cost data), $."""
    cd = case_data(case)
    g = ref_wide(variant, "generation")[cd.res["resource_id"].tolist()]
    return float((g * cd.mc[g.columns]).to_numpy().sum())


def px_cost_file_total(variant: str) -> float:
    return float(ref_wide(variant, "cost").to_numpy().sum())


# ------------------------------------------------------------------------------------------ independent zonal LP
@lru_cache(maxsize=None)
def zonal_lp(case: str) -> dict:
    """Independent transport LP per hour (fixed fleet, no inter-hour coupling at Gate 4): min sum MC g + VOLL u subject to
    zonal balance, 0 <= g <= cap, u <= D, -rev <= f <= fwd. Returns Z (total $), per-hour arrays and balance duals."""
    cd = case_data(case)
    units = cd.res["resource_id"].tolist()
    zi = {z: i for i, z in enumerate(cd.zones)}
    R, Z, Lk = len(units), len(cd.zones), len(cd.links)
    zr = np.array([zi[cd.zone_of[u]] for u in units])
    n = R + Z + Lk
    Aeq = np.zeros((Z, n))
    for r in range(R):
        Aeq[zr[r], r] = 1.0
    for z in range(Z):
        Aeq[z, R + z] = 1.0
    for k, (_, l) in enumerate(cd.links.iterrows()):
        Aeq[zi[l["zone_to"]], R + Z + k] += 1.0                      # bal: + f at e(l), - f at o(l)
        Aeq[zi[l["zone_from"]], R + Z + k] -= 1.0
    H = len(cd.load)
    gen, unserved, price, flow = np.zeros((H, R)), np.zeros((H, Z)), np.zeros((H, Z)), np.zeros((H, Lk))
    tot = 0.0
    for h in range(H):
        D = cd.load.iloc[h].to_numpy(float)
        c = np.r_[cd.mc.iloc[h][units].to_numpy(float), np.full(Z, VOLL), np.zeros(Lk)]
        bounds = [(0, v) for v in cd.cap.iloc[h][units].to_numpy(float)] + [(0, d) for d in D]
        bounds += [(-l["ntc_rev_mw"], l["ntc_fwd_mw"]) for _, l in cd.links.iterrows()]
        r = linprog(c, A_eq=Aeq, b_eq=D, bounds=bounds, method="highs")
        assert r.status == 0, r.message
        tot += r.fun
        gen[h], unserved[h], flow[h], price[h] = r.x[:R], r.x[R:R + Z], r.x[R + Z:], r.eqlin.marginals
    return dict(Z=tot, gen=pd.DataFrame(gen, index=cd.load.index, columns=units),
                unserved=pd.DataFrame(unserved, index=cd.load.index, columns=cd.zones),
                price=pd.DataFrame(price, index=cd.load.index, columns=cd.zones),
                flow=pd.DataFrame(flow, index=cd.load.index, columns=cd.links["link_id"].tolist() if Lk else []))


# ------------------------------------------------------------------------------------------ run-side extraction
def read_out_dir(out_dir: Path) -> dict:
    """Output CSVs of a capex run as {table_name: DataFrame}."""
    out = {}
    for p in Path(out_dir).glob("*.csv"):
        out[p.stem] = pd.read_csv(p)
    return out


def _win(df: pd.DataFrame, pcol="period") -> pd.DataFrame:
    """Rows of a run table restricted to the 336-hour comparison window."""
    key = pd.MultiIndex.from_frame(df[[pcol, "t"]])
    return df[key.isin(window_index())]


def run_dispatch(tables: dict, case: str) -> pd.DataFrame:
    """(336 h) x (resource) dispatch in MW from a run's `dispatch` table."""
    d = _win(tables["dispatch"])
    w = d.pivot(index=["period", "t"], columns="resource", values="g_mw")
    w.index.names = ["period_id", "t"]
    return w.reindex(window_index())


def run_zone_hourly(tables: dict, col: str) -> pd.DataFrame:
    z = _win(tables["zone_hourly"])
    w = z.pivot(index=["period", "t"], columns="zone", values=col)
    w.index.names = ["period_id", "t"]
    return w.reindex(window_index())


def z_our(tables: dict, case: str) -> float:
    """Z^our: our variable cost in the window, sum g x MC^our from the case data ($, 336 h, unweighted: blocks are real)."""
    cd = case_data(case)
    g = run_dispatch(tables, case)
    cols = [c for c in g.columns if c in cd.mc.columns]
    return float((g[cols] * cd.mc[cols]).to_numpy().sum())


# ------------------------------------------------------------------------------------------ section 5 metrics
def c_metrics(z_our_usd: float, variant: str, case: str) -> dict:
    """C0, C1, C2 for one run. C2 closure: (PX cost - C^PX) + (C^PX - Z^our) = PX cost - Z^our."""
    cpx = px_dispatch_cost(variant, case)
    px_cost = px_cost_file_total(variant)
    return dict(C_px_our=cpx, Z_our=z_our_usd, c0_ok=z_our_usd <= cpx * (1 + 1e-6), c1_gap=(cpx - z_our_usd) / cpx,
                px_cost_file=px_cost, basis_gap=px_cost - cpx, dispatch_gap=cpx - z_our_usd,
                c2_lhs=(px_cost - cpx) + (cpx - z_our_usd), c2_rhs=px_cost - z_our_usd,
                basis_gap_rel=(px_cost - cpx) / px_cost)


def tech_shares(gen: pd.DataFrame, case: str) -> pd.Series:
    """Generation share by tech group over the window (unit columns of `gen` mapped through the case tech)."""
    cd = case_data(case)
    cols = [c for c in gen.columns if c in cd.tech.index]
    e = gen[cols].sum().groupby(cd.tech[cols]).sum()
    e = e.reindex(GROUPS).fillna(0.0)
    return e / e.sum()


def g1_check(ours: pd.Series, px: pd.Series) -> pd.DataFrame:
    d = (ours - px).abs() * 100.0                                    # percentage points
    lim = pd.Series(3.0, index=d.index)
    lim["nuclear"] = 0.5
    return pd.DataFrame({"ours_pct": ours * 100, "px_pct": px * 100, "abs_pp": d, "limit_pp": lim, "ok": d <= lim})


def g2_unserved_mwh(tables: dict) -> float:
    return float(run_zone_hourly(tables, "unserved_mw").to_numpy().sum())


def curtailment_report(tables: dict) -> pd.Series:
    """Window curtailment by tech group would need hourly curtailment; reported from the dispatch table's curtail_mw."""
    d = _win(tables["dispatch"])
    return d.groupby("resource")["curtail_mw"].sum()


LMP_QUANTILES = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]


def lmp_report(price: pd.DataFrame, tol=0.01) -> dict:
    """L1 for a (hour x node) price table: mean, quantiles of the price-duration curve, hours <= tol and < 0 (node-hours),
    hours with a node price spread above tol."""
    v = price.to_numpy(float)
    spread = np.nanmax(v, axis=1) - np.nanmin(v, axis=1)
    return dict(mean=float(np.nanmean(v)), min=float(np.nanmin(v)), max=float(np.nanmax(v)),
                quantiles={q: float(np.nanquantile(v, q)) for q in LMP_QUANTILES},
                node_hours_le_tol=int((v <= tol).sum()), node_hours_neg=int((v < 0).sum()),
                spread_hours=int((spread > tol).sum()), n_node_hours=int(v.size))


def px_price(variant: str, by: str = "bus") -> pd.DataFrame:
    p = ref_wide(variant, "price")
    if by == "bus":
        return p
    bus, _, _ = raw_topology()
    area = bus["Area"]
    return p.T.groupby(p.columns.map(lambda b: AREA_ZONE[int(area[int(b)])])).mean().T


def l2_px(variant: str = "alltx") -> dict:
    """L2 reference facts from the PLEXOS tables: hours CB-1 at its 500 MW limit (ref 10), DC1 at +-100 (ref 323),
    hours with a bus-price spread above 0.01 (ref 13)."""
    fl = ref_wide(variant, "flow")
    pr = ref_wide(variant, "price")
    spread = pr.max(axis=1) - pr.min(axis=1)
    return dict(cb1_at_limit_hours=int((fl["CB-1"].abs() >= 500 - 1e-6).sum()),
                dc1_at_limit_hours=int((fl["113_316_1"].abs() >= 100 - 1e-6).sum()),
                congested_hours=int((spread > 0.01).sum()), dc1_plus100=int((fl["113_316_1"] >= 100 - 1e-6).sum()),
                dc1_minus100=int((fl["113_316_1"] <= -100 + 1e-6).sum()), dc1_mean=float(fl["113_316_1"].mean()))


def p1_px_shares(variant: str, case: str, tol_mc: float = 0.5) -> pd.Series:
    """P1 PLEXOS-inferred marginal tech shares: a committed unit strictly inside [Pmin, Pmax] whose MC is within 0.5 $/MWh
    of the price at its bus; unit-hour counts split equally per hour among the hour's inferred setters; shares of hours
    with at least one setter. (reported)"""
    cd = case_data(case)
    g = ref_wide(variant, "generation")[cd.res["resource_id"].tolist()]
    com = ref_wide(variant, "commitment")[g.columns]
    pr = ref_wide(variant, "price")
    pmin = cd.res.set_index("resource_id")["x_pmin_mw"].reindex(g.columns)
    pmax = cd.res.set_index("resource_id")["k0_mw"].reindex(g.columns)
    bus_price = pd.DataFrame({u: pr[str(int(cd.bus_of[u]))] for u in g.columns})
    inside = (com > 0.5) & (g > pmin + 1e-6) & (g < pmax - 1e-6) & ((cd.mc[g.columns] - bus_price).abs() <= tol_mc)
    w = inside.astype(float)
    w = w.div(w.sum(axis=1).replace(0, np.nan), axis=0)
    s = w.sum().groupby(cd.tech[g.columns]).sum().reindex(GROUPS).fillna(0.0)
    return s / s.sum() if s.sum() > 0 else s


def u0_px_must_run(variant: str, case: str) -> pd.DataFrame:
    """U0: PLEXOS energy at Pmin from committed units with MC > bus price ("UC must-run"), by tech (MWh, and share of tech
    output). A committed unit counts when g <= Pmin + 1e-6."""
    cd = case_data(case)
    g = ref_wide(variant, "generation")[cd.res["resource_id"].tolist()]
    com = ref_wide(variant, "commitment")[g.columns]
    pr = ref_wide(variant, "price")
    pmin = cd.res.set_index("resource_id")["x_pmin_mw"].reindex(g.columns)
    bus_price = pd.DataFrame({u: pr[str(int(cd.bus_of[u]))] for u in g.columns})
    mr = (com > 0.5) & (g <= pmin + 1e-6) & (cd.mc[g.columns] > bus_price) & (cd.res.set_index("resource_id")["type"].reindex(g.columns) == "TH").to_numpy()
    e = (g.where(mr, 0.0)).sum().groupby(cd.tech[g.columns]).sum().reindex(GROUPS).fillna(0.0)
    tot = g.sum().groupby(cd.tech[g.columns]).sum().reindex(GROUPS).fillna(0.0)
    return pd.DataFrame({"must_run_mwh": e, "tech_mwh": tot, "share": (e / tot.replace(0, np.nan)).fillna(0.0)})


# ------------------------------------------------------------------------------------------ window cases (R4-Z etc.)
WINDOW_TABLES = ("load", "availability", "fuel_prices", "periods")


def make_window_case(case: str, tmp: Path, periods=tuple(RUN_PERIODS), name: str | None = None) -> Path:
    """Copy `cases/<case>` into tmp/cases/<name or case_win> with the period-indexed tables restricted to `periods`
    (R4-Z/C/N/NP window runs). Every table file is copied into the case dir and re-pinned; shared registries keep their
    relative path through a data symlink. The run is then identical to the full case on those blocks (blocks are independent
    at Gate 4, which is what B1 tests)."""
    import hashlib
    src = CASES / case
    cfg = yaml.safe_load((src / "case.yaml").read_text())
    dst = Path(tmp) / "cases" / (name or f"{case}_win")
    dst.mkdir(parents=True, exist_ok=True)
    if not (Path(tmp) / "data").exists():
        (Path(tmp) / "data").symlink_to(REPO / "data")
    for key, spec in cfg["tables"].items():
        f = (src / spec["file"]).resolve()
        if key in ("sources", "deflator"):
            continue                                                  # '../../data/common/...' resolves through the symlink
        df = pd.read_csv(f)
        if "period_id" in df.columns:
            df = df[df["period_id"].isin(periods)]
        out = dst / (f"{key}.csv.gz" if f.suffix == ".gz" else f"{key}.csv")
        df.to_csv(out, index=False)
        spec["file"] = out.name
        spec["sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    (dst / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return dst


# ------------------------------------------------------------------------------------------ health (section 6) helpers
DCPF_CHECKS = ["kvl.recompute", "ptdf.recompute", "lmp.decomposition", "congestion_rent", "dcpf.line_duals",
               "price_setter.link_inconsistent", "dcpf.islands", "price_setter.loop_alpha", "price_setter.loop_interval"]


def unexplained_count(tables: dict) -> int:
    ps = tables["price_setter"]
    return int((ps["primary_class"] == "UNEXPLAINED").sum() + ps["flags"].fillna("").astype(str).str.contains("UNEXPLAINED").sum())
