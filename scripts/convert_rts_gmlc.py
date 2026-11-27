#!/usr/bin/env python3
"""Convert the vendored RTS-GMLC raw data (cases/raw/rts_gmlc, commit 3ece0d3) into the capex-model input
schema S-0.1 (docs/data-schema.md) under cases/rts_gmlc/.

Usage:  python scripts/convert_rts_gmlc.py [--raw DIR] [--out DIR]
Deterministic (no randomness, no network); rerunning reproduces every output byte-for-byte, including the
sha256 values written into case.yaml. Stdlib + pandas/numpy/yaml only. Method notes: cases/rts_gmlc/README.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
SRC = "rts_gmlc"
VINTAGE = "rts_gmlc@3ece0d3"          # pinned upstream commit (cases/raw/rts_gmlc/PROVENANCE.md)
RETRIEVED = "2026-11-26"              # P1 fetch date
MODEL_YEAR = 2020
T = 72
BASE_YEAR = 2024
ASSUMED_DOLLAR_YEAR = 2024            # upstream gives no dollar year (see assumption A1)
RTS_DEFAULT = dict(source_id=SRC, vintage=VINTAGE, retrieved=RETRIEVED, method="observed", confidence="high")
PROV = ["source_id", "vintage", "retrieved", "method", "basis", "confidence"]


def prov(basis: str, method: str = "observed", confidence: str = "high", est_level=None, **kw) -> dict:
    d = {**RTS_DEFAULT, "method": method, "basis": basis, "confidence": confidence, **kw}
    if est_level is not None:
        d["est_level"] = est_level
    return d


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    if path.suffix == ".gz":   # mtime=0 and no embedded filename -> byte-reproducible
        with open(path, "wb") as fh:
            df.to_csv(fh, index=False, compression={"method": "gzip", "mtime": 0, "filename": ""}, lineterminator="\n")
    else:
        df.to_csv(path, index=False, lineterminator="\n")


def rid(uid: str) -> str:
    return uid.lower().replace("-", "_")


# ---------------------------------------------------------------------------------------------- thermal curve
def heat_rate_curve(row: pd.Series) -> dict:
    """Piecewise-linear fuel-input curve from gen.csv fields (units: BTU/kWh -> MMBtu/MWh divide by 1000).
    F0 = HR_avg_0 * P0 ; F_k = F_{k-1} + HR_incr_k * (P_k - P_{k-1}); P_k = Output_pct_k * PMax."""
    pmax = float(row["PMax MW"])
    pts = [(float(row["Output_pct_0"]) * pmax, float(row["HR_avg_0"]) * float(row["Output_pct_0"]) * pmax / 1000.0)]
    for k in range(1, 5):
        pct, inc = row.get(f"Output_pct_{k}"), row.get(f"HR_incr_{k}")
        if pd.isna(pct) or pd.isna(inc):
            break
        p_prev, f_prev = pts[-1]
        p_k = float(pct) * pmax
        pts.append((p_k, f_prev + float(inc) * (p_k - p_prev) / 1000.0))
    (p0, f0), (pn, fn) = pts[0], pts[-1]
    return {
        "hr_full_avg": fn / pn,                                   # MMBtu/MWh, average at last curve point
        "hr_incr_secant": (fn - f0) / (pn - p0) if pn > p0 else float("nan"),   # MMBtu/MWh, slope P0..PN
        "noload_mmbtu_h": f0 - (fn - f0) / (pn - p0) * p0 if pn > p0 else float("nan"),  # intercept of the secant
        "hr_pmin_avg": f0 / p0,
        "n_points": len(pts),
    }


# ---------------------------------------------------------------------------------------------- PLEXOS reference + back-tests
PLEXOS_REL = "FormattedData/PLEXOS/PLEXOS_Solution/DAY_AHEAD Solution Files"
SCENARIOS = {"allTX": "ref_plexos_da_alltx", "noTX": "ref_plexos_da_notx"}
REF_VARS = {"generation": "MW", "commitment": "flag", "cost": "usd", "price": "usd_per_mwh", "flow": "MW"}
WINDOW_FIRST_PERIOD = "p063"          # PLEXOS window starts 2020-07-05 00:00 = period p063, t=1 (gate-4.md section 2)
WINDOW_START = "2020-07-05 00:00:00"
WINDOW_HOURS = 336


def plexos_file(raw: Path, scen: str, var: str) -> Path:
    return raw / PLEXOS_REL / scen / f"PLEXOS_DA_solution_{var}.csv"


def manifest_sha(raw: Path, path: Path) -> str:
    """sha256 recorded in cases/raw/rts_gmlc/MANIFEST.csv for a vendored file (path relative to raw/.. i.e. repo path in manifest)."""
    man = pd.read_csv(raw.parent / "MANIFEST.csv")
    rel = path.relative_to(raw.parent).as_posix() if raw.parent in path.parents else path.as_posix()
    hit = man[man["path"] == rel]
    assert len(hit) == 1, rel
    return str(hit["sha256"].iloc[0])


def plexos_backtests(raw: Path, bus: pd.DataFrame, branch: pd.DataFrame, gen: pd.DataFrame, area_load: pd.DataFrame) -> dict:
    """Back-tests of network/load assumptions against the vendored PLEXOS allTX DA results (deterministic).
    (1) DC1 flow within +-100 MW (assumption A4); (2) bus load shares: implied nodal load by KCL (gen - net AC/DC outflow)
    vs area DA series x bus.csv 'MW Load' share (A10); (3) lossless DC power flow with branch X and the PLEXOS DC1 flow
    reproduces PLEXOS AC branch flows (A11)."""
    gdf = pd.read_csv(plexos_file(raw, "allTX", "generation"), index_col=0)
    fdf = pd.read_csv(plexos_file(raw, "allTX", "flow"), index_col=0)
    ndf = pd.read_csv(plexos_file(raw, "noTX", "flow"), index_col=0)
    ids = list(bus["Bus ID"])
    ix = {b: i for i, b in enumerate(ids)}
    area = bus.set_index("Bus ID")["Area"]
    share = bus.set_index("Bus ID")["MW Load"]
    ub = dict(zip(gen["GEN UID"], gen["Bus ID"]))
    inj = pd.DataFrame(0.0, index=gdf.index, columns=ids)
    for c in gdf.columns:
        inj[ub[c]] += gdf[c]
    out = pd.DataFrame(0.0, index=gdf.index, columns=ids)
    for _, r in branch.iterrows():
        out[r["From Bus"]] += fdf[r["UID"]]
        out[r["To Bus"]] -= fdf[r["UID"]]
    out[113] += fdf["113_316_1"]
    out[316] -= fdf["113_316_1"]
    implied = inj - out
    off = (int(WINDOW_FIRST_PERIOD[1:]) - 1) * T
    w = area_load.iloc[off:off + len(gdf)].reset_index(drop=True)
    mine = pd.DataFrame({b: share[b] / share[area == area[b]].sum() * w[str(int(area[b]))].values for b in ids}, index=gdf.index)
    load_err = float((implied - mine).abs().max().max())
    # lossless DC power flow (slack bus 0), X in pu, injection = gen - load share, DC1 as +-injection
    n = len(ids)
    Bm = np.zeros((n, n))
    for _, r in branch.iterrows():
        i, j, b = ix[r["From Bus"]], ix[r["To Bus"]], 1.0 / r["X"]
        Bm[i, i] += b; Bm[j, j] += b; Bm[i, j] -= b; Bm[j, i] -= b
    pinj = inj - mine
    pinj[113] -= fdf["113_316_1"]
    pinj[316] += fdf["113_316_1"]
    th = np.zeros((len(gdf), n))
    th[:, 1:] = np.linalg.solve(Bm[1:, 1:], pinj.values[:, 1:].T).T
    fl = pd.DataFrame({r["UID"]: (th[:, ix[r["From Bus"]]] - th[:, ix[r["To Bus"]]]) / r["X"] for _, r in branch.iterrows()}, index=gdf.index)
    flow_err = float((fl - fdf[fl.columns]).abs().max().max())
    return {"dc1_max_abs_mw": float(fdf["113_316_1"].abs().max()), "dc1_min": float(fdf["113_316_1"].min()),
            "dc1_max": float(fdf["113_316_1"].max()), "dc1_notx_min": float(ndf["113_316_1"].min()),
            "dc1_notx_max": float(ndf["113_316_1"].max()), "dc1_hours_at_limit": int((fdf["113_316_1"].abs() >= 100 - 1e-9).sum()),
            "n_hours": len(gdf), "load_share_max_err_mw": load_err, "dc_pf_max_err_mw": flow_err,
            "area_gen_vs_load_max_err_mw": float(np.abs(gdf.sum(axis=1).values - w[[c for c in w.columns if c in ("1", "2", "3")]].sum(axis=1).values).max())}


def build_reference(raw: Path, out: Path, load_hours: pd.DataFrame, unit_ids: set) -> list[dict]:
    """Tidy long reference tables ref_plexos_da_{alltx,notx}.csv.gz (variable, entity, period_id, t, timestamp, value, unit) from the
    vendored PLEXOS DA result files. Returns metadata rows (sha256 checks against MANIFEST.csv)."""
    meta = []
    refdir = out / "reference"
    refdir.mkdir(parents=True, exist_ok=True)
    for scen, tname in SCENARIOS.items():
        parts = []
        for var, unit in REF_VARS.items():
            f = plexos_file(raw, scen, var)
            h_file, h_man = sha256(f), manifest_sha(raw, f)
            assert h_file == h_man, f"{f} sha256 differs from MANIFEST.csv"
            d = pd.read_csv(f)
            assert len(d) == WINDOW_HOURS and d["time"].iloc[0] == WINDOW_START, f
            h = np.arange(WINDOW_HOURS)
            p0 = int(WINDOW_FIRST_PERIOD[1:])
            pid_ = np.array([f"p{p0 + k // T:03d}" for k in h])
            tt = h % T + 1
            for col in d.columns[1:]:
                ent = rid(col) if var in ("generation", "commitment", "cost") else col
                if var in ("generation", "commitment", "cost"):
                    assert col in unit_ids, col
                parts.append(pd.DataFrame({"variable": var, "entity": ent, "period_id": pid_, "t": tt, "timestamp": d["time"].values,
                                           "value": d[col].to_numpy(float), "unit": unit}))
            meta.append(dict(table=tname, variable=var, source_file=f.relative_to(raw.parent).as_posix(), source_sha256=h_file,
                             manifest_sha256=h_man, sha256_equals_manifest=True, rows=len(d) * (len(d.columns) - 1),
                             first_hour=WINDOW_START, first_period=WINDOW_FIRST_PERIOD, first_t=1))
        tab = pd.concat(parts, ignore_index=True)
        for k, v in dict(source_id=SRC, vintage=VINTAGE, method="observed").items():
            tab[k] = v
        write_csv(tab, refdir / f"{tname}.csv.gz")
    return meta


FILES = {"periods": "periods.csv", "zones": "zones.csv", "links": "links.csv", "load": "load.csv", "load_meta": "load_meta.csv",
         "resources": "resources.csv", "finance": "finance.csv", "availability": "availability.csv.gz",
         "availability_meta": "availability_meta.csv", "fuel_map": "fuel_map.csv", "fuel_prices": "fuel_prices.csv",
         "fuel_prices_meta": "fuel_prices_meta.csv"}
TABLE_ORDER = ["periods", "zones", "links", "load", "load_meta", "resources", "finance", "availability", "availability_meta", "fuel_map",
               "fuel_prices", "fuel_prices_meta"]


def write_case(out: Path, case_id: str, description: str, owned: dict, shared: dict, switches: dict, cells: list, assumptions: pd.DataFrame) -> None:
    """Write one case directory. owned = {table: (filename, df)} written here; shared = {table: relative path of an already generated file in
    another case dir} (listed in the manifest with its sha256, like the shared deflator). `sources` always points at data/common/sources.csv
    (no sha256, DECISIONS 40); there is no case-local registry (K4)."""
    out.mkdir(parents=True, exist_ok=True)
    for name, (fn, df) in owned.items():
        write_csv(df, out / fn)
    prov_cells = pd.DataFrame(cells)[["table", "row_key", "column"] + PROV[:1] + ["vintage", "retrieved", "method", "basis", "confidence", "est_level"]]
    write_csv(prov_cells, out / "provenance_cells.csv")        # sidecar: the loader does not read it yet
    write_csv(assumptions, out / "assumptions.csv")            # sidecar: explicit assumption / gap register
    tables = {}
    for name in TABLE_ORDER:
        if name in owned:
            tables[name] = {"file": owned[name][0], "sha256": sha256(out / owned[name][0])}
        elif name in shared:
            tables[name] = {"file": shared[name], "sha256": sha256((out / shared[name]).resolve())}
    tables["sources"] = {"file": "../../data/common/sources.csv"}
    tables["deflator"] = {"file": "../../data/common/deflator.csv", "sha256": sha256(REPO / "data/common/deflator.csv")}
    manifest = {"case_id": case_id, "description": description, "schema_version": "S-0.1", "formulation_version": "F-0.4",
                "base_dollar_year": BASE_YEAR, "model_year": MODEL_YEAR, "dt_h": 1.0, "voll_usd_mwh": 10000, "voll_dollar_year": 2024,
                "finance_default": "rts_unused", "seed": 0, "solver": {"name": "highs"}, "switches": dict(switches),
                "audit_profile": "standard", "tables": tables}
    (out / "case.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(REPO / "cases/raw/rts_gmlc/RTS_Data"))
    ap.add_argument("--out", default=str(REPO / "cases/rts_gmlc"))
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sd, ts = raw / "SourceData", raw / "timeseries_data_files"

    gen = pd.read_csv(sd / "gen.csv")
    gen_all_uids = set(gen["GEN UID"])
    bus = pd.read_csv(sd / "bus.csv")
    branch = pd.read_csv(sd / "branch.csv")
    dcb = pd.read_csv(sd / "dc_branch.csv")
    sto = pd.read_csv(sd / "storage.csv")
    cells: list[dict] = []          # provenance_cells.csv rows (per-cell overrides)
    notes: list[dict] = []          # assumptions.csv rows

    # ------------------------------------------------------------------------------------------ zones
    areas = sorted(bus["Area"].unique())
    zid = {int(x): f"r{int(x)}" for x in areas}
    zones = pd.DataFrame({"zone_id": [zid[int(x)] for x in areas], "name": [f"RTS-GMLC region {int(x)} (Area {int(x)})" for x in areas],
                          "rto": "RTS-GMLC"})
    for k, v in prov("published test-system value: bus.csv Area membership (3 areas = zones)").items():
        zones[k] = v
    bus_area = dict(zip(bus["Bus ID"], bus["Area"]))

    # ------------------------------------------------------------------------------------------ periods
    n_h = 366 * 24
    n_p = n_h // T                                   # 122 blocks of 72 h; 8784 = 122 * 72 exactly
    assert n_p * T == n_h
    pid = [f"p{j:03d}" for j in range(1, n_p + 1)]
    start = dt.date(MODEL_YEAR, 1, 1)
    periods = pd.DataFrame({"period_id": pid, "weight_blocks": 1.0, "rep_kind": "full_block", "days_represented": 3.0,
                            "source_start_date": [(start + dt.timedelta(days=3 * j)).isoformat() for j in range(n_p)]})

    # ------------------------------------------------------------------------------------------ load
    ld = pd.read_csv(ts / "Load/DAY_AHEAD_regional_Load.csv")
    assert len(ld) == n_h and ld[["Year", "Month", "Day", "Period"]].iloc[0].tolist() == [2020, 1, 1, 1]
    bt = plexos_backtests(raw, bus, branch, gen, ld)
    assert bt["dc1_max_abs_mw"] <= 100 + 1e-9 and bt["load_share_max_err_mw"] < 1e-6 and bt["dc_pf_max_err_mw"] < 1e-6, bt
    rows = []
    hours = np.arange(n_h)
    for ar in areas:
        v = ld[str(int(ar))].to_numpy(float)
        rows.append(pd.DataFrame({"zone": zid[int(ar)], "period_id": np.array(pid)[hours // T], "t": hours % T + 1,
                                  "demand_mw": np.round(v, 4)}))
    load = pd.concat(rows, ignore_index=True)
    bus_sum = bus.groupby("Area")["MW Load"].sum()
    load_meta = pd.DataFrame({"zone": [zid[int(x)] for x in areas], "net_of_btm": False, "year": MODEL_YEAR})
    for k, v in prov("DAY_AHEAD_regional_Load.csv regional hourly load (MW, DA forecast, no scaling needed: series max equals "
                     "area bus.csv MW Load sum); RTPV is modeled as generation so load is gross").items():
        load_meta[k] = v
    notes.append(dict(id="A2", parameter="load_basis", applies_to="load", value="DA forecast, gross (RTPV as supply)",
                      method="observed", est_level="", confidence="high", source_id=SRC,
                      basis="timeseries README: Load files are 'forecasted power demand' per region", status="used"))

    # ------------------------------------------------------------------------------------------ links
    br = branch.copy()
    br["fa"], br["ta"] = br["From Bus"].map(bus_area), br["To Bus"].map(bus_area)
    inter = br[br["fa"] != br["ta"]].copy()
    inter["pair"] = [tuple(sorted((int(x), int(y)))) for x, y in zip(inter["fa"], inter["ta"])]
    link_rows = []
    for pair, g in sorted(inter.groupby("pair")):
        rating = float(g["Cont Rating"].sum())
        link_rows.append(dict(link_id=f"ac_{zid[pair[0]]}_{zid[pair[1]]}", zone_from=zid[pair[0]], zone_to=zid[pair[1]],
                              ntc_fwd_mw=rating, ntc_rev_mw=rating,
                              **prov(f"derived: sum of Cont Rating (MW) of inter-area AC branches {','.join(g['UID'])} in branch.csv; "
                                     "symmetric; DC power flow/reactance ignored (zonal transport model)", method="derived",
                                     est_level=1, confidence="medium")))
    for _, d in dcb.iterrows():
        fa, ta = int(bus_area[d["From Bus"]]), int(bus_area[d["To Bus"]])
        assert fa != ta
        lo, hi = sorted((fa, ta))
        mw = float(d["MW Load"])
        link_rows.append(dict(link_id=f"dc_{zid[lo]}_{zid[hi]}", zone_from=zid[lo], zone_to=zid[hi], ntc_fwd_mw=mw, ntc_rev_mw=mw,
                              **prov(f"derived: DC link {d['UID']} bus {d['From Bus']}->{d['To Bus']} (control mode {d['Control Mode']}); "
                                     "dc_branch.csv MW Load (100, scheduled setpoint) used as a symmetric +-rating; back-test: PLEXOS allTX DA "
                                     f"flow column 113_316_1 stays within [{bt['dc1_min']:.0f}, {bt['dc1_max']:.0f}] MW over {bt['n_hours']} h "
                                     f"(at the limit in {bt['dc1_hours_at_limit']} h); noTX lifts it", method="derived",
                                     est_level=1.0, confidence="medium")))
    links = pd.DataFrame(link_rows)
    notes.append(dict(id="A3", parameter="link_rating", applies_to="links", value="Cont Rating (MW)", method="derived", est_level=1,
                      confidence="medium", source_id=SRC,
                      basis="back-test: PLEXOS allTX DA flow on CB-1 saturates at exactly 500 MW = Cont Rating (LTE 600 not used)",
                      status="used"))
    notes.append(dict(id="A4", parameter="dc_link_rating", applies_to=links.loc[links.link_id.str.startswith("dc"), "link_id"].iloc[0],
                      value="100 MW symmetric", method="derived", est_level=1, confidence="medium", source_id=SRC,
                      basis="dc_branch.csv MW Load (100) is a scheduled setpoint, used as a +-100 MW rating; back-test (K5): PLEXOS allTX DA "
                            f"flow column 113_316_1 exists and lies in [{bt['dc1_min']:.0f}, {bt['dc1_max']:.0f}] MW over {bt['n_hours']} h "
                            f"(max |flow| = {bt['dc1_max_abs_mw']:.0f} MW <= 100; at the limit in {bt['dc1_hours_at_limit']} h); noTX run reaches "
                            f"[{bt['dc1_notx_min']:.0f}, {bt['dc1_notx_max']:.0f}] MW (limit lifted). Lossless: R Line ignored",
                      status="used"))

    # ------------------------------------------------------------------------------------------ resources
    fuel_name = {"Oil": "oil", "Coal": "coal", "NG": "gas", "Nuclear": "nuclear"}
    tech_name = {"Gas CC": "gas_cc", "Gas CT": "gas_ct", "Oil CT": "oil_ct", "Oil ST": "oil_st", "Coal": "coal", "Nuclear": "nuclear",
                 "Hydro": "hydro", "Solar PV": "solar_pv", "Solar RTPV": "solar_rtpv", "Wind": "wind", "CSP": "csp",
                 "Storage": "storage"}
    hub = {"oil": "rts_oil", "coal": "rts_coal", "gas": "rts_gas", "nuclear": "rts_nuclear"}
    gen = gen[gen["Category"] != "Sync_Cond"].copy()      # 3 synchronous condensers, PMax = 0 MW (gap G1)
    series = {"Hydro": ("Hydro/DAY_AHEAD_hydro.csv", None), "Solar PV": ("PV/DAY_AHEAD_pv.csv", None),
              "Solar RTPV": ("RTPV/DAY_AHEAD_rtpv.csv", None), "Wind": ("WIND/DAY_AHEAD_wind.csv", None),
              "CSP": ("CSP/DAY_AHEAD_Natural_Inflow.csv", None)}
    ts_data = {k: pd.read_csv(ts / f) for k, (f, _) in series.items()}
    for k, d in ts_data.items():
        assert len(d) == n_h, k

    res, avail_parts, avail_meta = [], [], []
    for _, g in gen.iterrows():
        cat, uid = g["Category"], g["GEN UID"]
        r = dict(resource_id=rid(uid), zone=zid[int(bus_area[g["Bus ID"]])], tech=tech_name[cat], status="existing",
                 k0_mw=float(g["PMax MW"]), xmax_mw=0.0, dollar_year=ASSUMED_DOLLAR_YEAR,
                 x_gen_uid=uid, x_bus_id=int(g["Bus ID"]), x_pmin_mw=float(g["PMin MW"]),
                 x_for_frac=float(g["FOR"]), x_maint_weeks=float(g["Scheduled Maint Weeks"]),
                 x_ramp_mw_min=float(g["Ramp Rate MW/Min"]), x_min_up_h=float(g["Min Up Time Hr"]),
                 x_min_dn_h=float(g["Min Down Time Hr"]))
        base_basis = f"published test-system value: gen.csv row {uid}"
        if cat in ("Gas CC", "Gas CT", "Oil CT", "Oil ST", "Coal", "Nuclear"):
            r["type"] = "TH"
            fuel = fuel_name[g["Fuel"]]
            r["fuel"] = fuel
            c = heat_rate_curve(g)
            if g["Fuel"] == "Nuclear" or not (c["hr_incr_secant"] > 0):
                hr, how = c["hr_full_avg"], "full-load average (secant slope is 0 for flat fuel curve)"
            else:
                hr, how = c["hr_incr_secant"], "secant incremental heat rate PMin..PMax"
            r["heat_rate_mmbtu_mwh"] = round(hr, 6)
            r["vom_usd_mwh"] = float(g["VOM"])
            r["x_hr_full_load_avg_mmbtu_mwh"] = round(c["hr_full_avg"], 6)
            r["x_hr_pmin_avg_mmbtu_mwh"] = round(c["hr_pmin_avg"], 6)
            r["x_noload_mmbtu_h"] = round(c["noload_mmbtu_h"], 4)
            r["x_fuel_price_usd_mmbtu"] = float(g["Fuel Price $/MMBTU"])
            r["x_mc_usd_mwh"] = round(hr * float(g["Fuel Price $/MMBTU"]) + float(g["VOM"]), 4)
            cells.append(dict(table="resources", row_key=r["resource_id"], column="heat_rate_mmbtu_mwh",
                              **prov(f"derived from gen.csv HR_avg_0, HR_incr_1..{c['n_points']-1}, Output_pct_*: fuel curve "
                                     f"F0=HR_avg_0*P0, F_k=F_(k-1)+HR_incr_k*dP; HR = {how}; BTU/kWh/1000 = MMBtu/MWh",
                                     method="derived", est_level=1, confidence="high")))
        else:
            r["type"] = "ST" if cat == "Storage" else "VRE"
            if cat != "Storage":
                key = cat
                d = ts_data[key]
                assert g["GEN UID"] in d.columns, uid
                v = d[uid].to_numpy(float)
                if cat == "CSP":
                    av = np.minimum(v / float(g["PMax MW"]), 1.0)
                    clipped = float(np.maximum(v - float(g["PMax MW"]), 0).sum() / v.sum())
                else:
                    av = v / float(g["PMax MW"])
                    clipped = 0.0
                assert av.min() >= -1e-9 and av.max() <= 1 + 1e-9, (uid, av.min(), av.max())
                av = np.clip(np.round(av, 6), 0, 1)
                avail_parts.append(pd.DataFrame({"resource_id": rid(uid), "period_id": np.array(pid)[hours // T], "t": hours % T + 1,
                                                 "availability_frac": av}))
                if cat == "CSP":
                    bas = ("derived: min(Natural_Inflow MW / PMax, 1) from DAY_AHEAD_Natural_Inflow.csv; solar multiple (inflow up to "
                           f"391 MW vs 200 MW turbine, {100*clipped:.1f}% of inflow energy clipped) and 1.2 GWh thermal storage not "
                           "modeled (gap G3)")
                    conf = "low"
                else:
                    bas = f"derived: series (MW, {series[cat][0]}) / gen.csv PMax MW; fixed schedule/forecast, curtailable in model"
                    conf = "high"
                avail_meta.append(dict(resource_id=rid(uid), profile_year=MODEL_YEAR, weather_year=np.nan,
                                       **prov(bas, method="derived", est_level=1, confidence=conf)))
        res.append(r)
    # storage (313_STORAGE_1 only; hydro reservoirs are not modeled: hydro is a fixed schedule)
    st = sto[sto["GEN UID"] == "313_STORAGE_1"]
    head = st[st["position"] == "head"].iloc[0]
    assert len(st) == 2 and (st["Max Volume GWh"] == head["Max Volume GWh"]).all()
    rt = float(gen.loc[gen["Category"] == "Storage", "Storage Roundtrip Efficiency"].iloc[0]) / 100.0
    eta = math.sqrt(rt)
    for r in res:
        if r["type"] == "ST":
            r.update(e0_mwh=float(head["Max Volume GWh"]) * 1000.0, xmax_mwh=0.0, eta_c_frac=round(eta, 6), eta_d_frac=round(eta, 6),
                     selfdis_frac_h=0.0, long_duration=False, vom_usd_mwh=0.0, x_roundtrip_published_frac=rt)
            cells.append(dict(table="resources", row_key=r["resource_id"], column="e0_mwh",
                              **prov("derived: storage.csv head-reservoir Max Volume GWh * 1000 (tail reservoir equal); initial "
                                     "volume 0.075 GWh not representable (cyclic SOC closure per period)", method="derived",
                                     est_level=1, confidence="medium")))
            for col in ("eta_c_frac", "eta_d_frac"):
                cells.append(dict(table="resources", row_key=r["resource_id"], column=col,
                                  **prov("estimated: published round-trip efficiency 85% (gen.csv) split symmetrically, eta = sqrt(0.85)",
                                         method="estimated", est_level=4, confidence="medium")))
            cells.append(dict(table="resources", row_key=r["resource_id"], column="selfdis_frac_h",
                              **prov("assumed 0: no self-discharge/evaporation published for the RTS-GMLC pumped storage unit",
                                     method="assumed", confidence="low")))
    resources = pd.DataFrame(res)
    for rr in resources.itertuples():
        cells.append(dict(table="resources", row_key=rr.resource_id, column="dollar_year",
                          **prov(f"assumed: upstream states no dollar year for costs; treated as {ASSUMED_DOLLAR_YEAR}$ (deflator factor 1; "
                                 "costs here are only VOM=0 and fuel prices)", method="assumed", confidence="low")))
        cells.append(dict(table="resources", row_key=rr.resource_id, column="zone",
                          **prov("derived: gen.csv Bus ID -> bus.csv Area", method="derived", est_level=1, confidence="high")))
    first = ["resource_id", "zone", "type", "tech", "fuel", "status", "k0_mw", "e0_mwh", "xmax_mw", "xmax_mwh", "heat_rate_mmbtu_mwh",
             "vom_usd_mwh", "eta_c_frac", "eta_d_frac", "selfdis_frac_h", "long_duration", "dollar_year"]
    rest = [c for c in resources.columns if c not in first]
    resources = resources[first + rest]
    for k, v in prov("published test-system value: SourceData/gen.csv (PMax MW -> k0_mw; VOM; unit data). Row default; "
                     "derived/assumed cells are overridden in provenance_cells.csv").items():
        resources[k] = v
    resources = resources.sort_values("resource_id").reset_index(drop=True)
    assert resources["resource_id"].str.len().max() <= 48 and resources["resource_id"].str.fullmatch(r"[a-z0-9_]+").all()

    availability = pd.concat(avail_parts, ignore_index=True)
    availability_meta = pd.DataFrame(avail_meta)
    n_tiny = int(((availability.availability_frac > 0) & (availability.availability_frac < 1e-3)).sum())

    # ------------------------------------------------------------------------------------------ fuel
    fp = gen[gen["Fuel"].isin(fuel_name)].groupby("Fuel")["Fuel Price $/MMBTU"].agg(["min", "max"])
    assert (fp["min"] == fp["max"]).all(), "fuel price differs within a fuel"
    fuel_map = pd.DataFrame({"fuel": list(hub), "fuel_hub": list(hub.values())})
    fprice, fmeta = [], []
    for fuel, h in hub.items():
        raw_name = [k for k, v in fuel_name.items() if v == fuel][0]
        price = float(fp.loc[raw_name, "min"])
        fprice.append(pd.DataFrame({"fuel_hub": h, "period_id": np.array(pid)[hours // T], "t": hours % T + 1, "price_usd_mmbtu": price}))
        fmeta.append(dict(fuel_hub=h, dollar_year=ASSUMED_DOLLAR_YEAR, price_basis="nominal_as_reported", license_class="verify",
                          **prov(f"published test-system value: gen.csv 'Fuel Price $/MMBTU' for Fuel={raw_name} (constant all year, "
                                 "identical for all units of the fuel); dollar_year assumed (A1)", confidence="medium")))
    fuel_prices, fuel_prices_meta = pd.concat(fprice, ignore_index=True), pd.DataFrame(fmeta)

    # ------------------------------------------------------------------------------------------ finance / sources
    finance = pd.DataFrame([dict(finance_class="rts_unused", mode="simple_crf", wacc_real_frac=0.07,
                                 **prov("placeholder required by loader; no candidates in a fixed-fleet case, never used", method="assumed",
                                        confidence="low"))])
    common_src = pd.read_csv(REPO / "data/common/sources.csv")
    assert SRC in set(common_src["source_id"]), "K4: append the rts_gmlc row to data/common/sources.csv"

    # ------------------------------------------------------------------------------------------ assumptions register
    notes += [
        dict(id="A1", parameter="dollar_year", applies_to="resources, fuel_prices", value=ASSUMED_DOLLAR_YEAR, method="assumed",
             est_level="", confidence="low", source_id=SRC, status="used",
             basis="upstream states none; set to base year so deflator factor = 1; only deflator row in data/common is 2024 (placeholder)"),
        dict(id="A5", parameter="heat_rate", applies_to="TH resources", value="secant incremental HR PMin..PMax (nuclear: full-load avg)",
             method="derived", est_level=1, confidence="high", source_id=SRC, status="used",
             basis="linear MC = HR*fuel_price + VOM has no no-load term; secant slope is the marginal cost of the piecewise curve; "
                   "x_noload_mmbtu_h, x_hr_full_load_avg_mmbtu_mwh kept for Gate 4/9 sensitivity"),
        dict(id="A6", parameter="availability_TH", applies_to="TH resources", value=1.0, method="assumed", est_level="",
             confidence="low", source_id=SRC, status="used",
             basis="no outages applied (default A=1); FOR and maintenance weeks kept as x_for_frac, x_maint_weeks; PLEXOS reference outage "
                   "treatment unverified (gap G5)"),
        dict(id="A7", parameter="hydro_modelling", applies_to="20 hydro units", value="VRE with fixed hourly schedule (MW/PMax)",
             method="derived", est_level=1, confidence="medium", source_id=SRC, status="used",
             basis="pointers set PMin=PMax=series so RTS hydro is a fixed schedule; reservoirs (storage.csv) not modeled; model may curtail"),
        dict(id="A8", parameter="rtpv_modelling", applies_to="31 RTPV units", value="VRE (curtailable)", method="derived",
             est_level=1, confidence="medium", source_id=SRC, status="used",
             basis="RTPV PMin=PMax=series upstream (non-dispatchable); schema has no must-take flag, so model may curtail"),
        dict(id="A9", parameter="storage_roundtrip", applies_to="313_storage_1", value="eta_c=eta_d=sqrt(0.85)", method="estimated",
             est_level=4, confidence="medium", source_id=SRC, status="used", basis="symmetric split of published 85% round trip"),
        dict(id="G1", parameter="sync_cond", applies_to="3 units", value="excluded (0 MW)", method="", est_level="", confidence="",
             source_id=SRC, status="gap", basis="loader needs k0>0; they provide no MW"),
        dict(id="G2", parameter="fom_capex_costs", applies_to="all resources", value="null", method="", est_level="", confidence="",
             source_id="", status="gap",
             basis="FOM/capex not in RTS-GMLC; irrelevant to fixed-fleet dispatch (constant Z0); fill from NREL ATB (est_level 4) if cost "
                   "reporting is needed; needs ATB download (Needs owner/Actions)"),
        dict(id="G3", parameter="csp_storage", applies_to="212_csp_1", value="storage and solar multiple ignored", method="", est_level="",
             confidence="", source_id=SRC, status="gap", basis="schema has no VRE+storage hybrid"),
        dict(id="G4", parameter="uc_params", applies_to="TH resources", value="x_ columns only", method="", est_level="", confidence="",
             source_id=SRC, status="gap", basis="pmin, ramps, min up/down kept as x_ columns; start costs not carried (Gate 9)"),
        dict(id="G5", parameter="reserves", applies_to="case", value="not modeled", method="", est_level="", confidence="",
             source_id=SRC, status="gap", basis="reserves are Gate 7; PLEXOS DA reference prices include reserve scarcity/commitment effects"),
    ]
    assumptions = pd.DataFrame(notes)[["id", "parameter", "applies_to", "value", "method", "est_level", "confidence", "source_id", "basis", "status"]]

    # ------------------------------------------------------------------------------------------ write: rts_gmlc (full fleet, 3 zones)
    base = dict(periods=periods, zones=zones, links=links, load=load, load_meta=load_meta, resources=resources, finance=finance,
                availability=availability, availability_meta=availability_meta, fuel_map=fuel_map, fuel_prices=fuel_prices,
                fuel_prices_meta=fuel_prices_meta)
    out_root = out.parent
    owned = {k: (FILES[k], v) for k, v in base.items()}
    write_case(out, "rts_gmlc", "RTS-GMLC fixed fleet, 3 zones (areas), full year 2020 as 122 weight-1 blocks of 72 h; Gate 4 dispatch check",
               owned, {}, {}, cells, assumptions)

    # ------------------------------------------------------------------------------------------ variants (gate-4.md section 2)
    ALIGN_DROP = {"212_csp_1", "313_storage_1"}      # PLEXOS DA result files have no columns for these two units
    gdf = pd.read_csv(plexos_file(raw, "allTX", "generation"), nrows=1)
    assert "212_CSP_1" not in gdf.columns and "313_STORAGE_1" not in gdf.columns, "PLEXOS reference unexpectedly has CSP/storage"
    keep = ~resources["resource_id"].isin(ALIGN_DROP)
    res_px = resources[keep].reset_index(drop=True)
    av_px = availability[~availability["resource_id"].isin(ALIGN_DROP)].reset_index(drop=True)
    avm_px = availability_meta[~availability_meta["resource_id"].isin(ALIGN_DROP)].reset_index(drop=True)
    cells_px = [c for c in cells if c["row_key"] not in ALIGN_DROP]
    assert len(res_px) == len(resources) - 2
    A_ALIGN = dict(id="A12", parameter="fleet_alignment", applies_to="212_csp_1, 313_storage_1", value="removed from the case",
                   method="derived", est_level=1, confidence="high", source_id=SRC, status="used",
                   basis=f"back-test: PLEXOS DA generation/commitment/cost result files (both runs) have no columns for CSP and storage "
                         f"(checked in converter); total PLEXOS generation equals area load (max diff {bt['area_gen_vs_load_max_err_mw']:.0e} MW), so the "
                         "reference is judged on the aligned fleet (gate-4.md O5; full fleet kept in rts_gmlc/rts_gmlc_nodal)")
    A_PROFILE = dict(id="A13", parameter="audit_profile", applies_to="case.yaml", value="standard", method="assumed", est_level="",
                     confidence="medium", source_id="", status="used",
                     basis="gate-4.md S3: non-toy cases use warn >1e-3 / fail >1e-1 MW(h) thresholds; 1e-1 MW is 1e-5 of the 8.2 GW peak")
    base_notes = [dict(r) for r in assumptions.to_dict("records")]
    # fix G3 (csp) wording for aligned cases
    def notes_for(extra, drop_ids=(), patch=None):
        rows = [r for r in base_notes if r["id"] not in drop_ids]
        rows = [{**r, **(patch or {}).get(r["id"], {})} for r in rows] + extra
        return pd.DataFrame(rows)[list(assumptions.columns)]
    FLEET_PATCH = {"G3": dict(status="gap", value="not in this case (aligned fleet, A12)")}
    notes_px = notes_for([A_ALIGN, A_PROFILE], patch=FLEET_PATCH)
    rel = "../rts_gmlc/"
    common_shared = {k: rel + FILES[k] for k in ("periods", "finance", "fuel_map", "fuel_prices", "fuel_prices_meta")}

    # --- rts_gmlc_px : aligned fleet, 3 zones, transport (R4-Z, R4-F)
    out_px = out_root / "rts_gmlc_px"
    write_case(out_px, "rts_gmlc_px", "RTS-GMLC PLEXOS-aligned fleet (no CSP, no storage), 3 zones, full year 2020 as 122 blocks of 72 h; "
               "Gate 4 R4-Z/R4-F vs PLEXOS DA allTX",
               {"resources": (FILES["resources"], res_px), "availability": (FILES["availability"], av_px),
                "availability_meta": (FILES["availability_meta"], avm_px)},
               {**common_shared, "zones": rel + FILES["zones"], "links": rel + FILES["links"], "load": rel + FILES["load"],
                "load_meta": rel + FILES["load_meta"]}, {}, cells_px, notes_px)

    # --- rts_gmlc_px_cp : aligned fleet, one zone (copper plate) (R4-C vs noTX)
    cp_zone = "rts"
    zones_cp = pd.DataFrame([dict(zone_id=cp_zone, name="RTS-GMLC single zone (copper plate, Areas 1-3 merged)", rto="RTS-GMLC",
                                  **prov("derived: the 3 bus.csv Areas merged into one zone (copper plate; noTX reference has one price per hour)",
                                         method="derived", est_level=1))])
    ld_cp = load.groupby(["period_id", "t"], as_index=False, sort=False)["demand_mw"].sum()
    ld_cp.insert(0, "zone", cp_zone)
    ld_cp["demand_mw"] = np.round(ld_cp["demand_mw"], 4)
    lm_cp = pd.DataFrame([dict(zone=cp_zone, net_of_btm=False, year=MODEL_YEAR,
                               **prov("derived: sum of the three DAY_AHEAD_regional_Load.csv area series (MW, DA forecast, gross; RTPV is supply)",
                                      method="derived", est_level=1))])
    res_cp = res_px.copy()
    res_cp["zone"] = cp_zone
    cells_cp = [c if not (c["column"] == "zone") else {**c, **prov("derived: single copper-plate zone (all buses)", method="derived",
                                                                  est_level=1)} for c in cells_px]
    notes_cp = notes_for([A_ALIGN, A_PROFILE,
                          dict(id="A14", parameter="copper_plate", applies_to="case", value="no links table", method="assumed", est_level="",
                               confidence="medium", source_id=SRC, status="used",
                               basis="noTX PLEXOS run has one price in every hour (checked, gate-4.md section 2); all network limits removed. "
                                     "Note noTX also lifts the DC1 limit")],
                         patch={**FLEET_PATCH, "A3": dict(status="unused (no links)"), "A4": dict(status="unused (no links)")})
    write_case(out_root / "rts_gmlc_px_cp", "rts_gmlc_px_cp", "RTS-GMLC PLEXOS-aligned fleet, one zone (copper plate), full year 2020 as 122 "
               "blocks of 72 h; Gate 4 R4-C vs PLEXOS DA noTX",
               {"zones": (FILES["zones"], zones_cp), "load": (FILES["load"], ld_cp), "load_meta": (FILES["load_meta"], lm_cp),
                "resources": (FILES["resources"], res_cp)},
               {**common_shared, "availability": "../rts_gmlc_px/" + FILES["availability"],
                "availability_meta": "../rts_gmlc_px/" + FILES["availability_meta"]}, {}, cells_cp, notes_cp)

    # --- nodal: 73 buses = 73 zones, 120 AC branches (x, Cont Rating) + DC1 as `dc` link, load = area series x bus share
    BASE_MVA = 100.0
    bus_ids = [int(b) for b in bus["Bus ID"]]
    bz = {b: f"b{b}" for b in bus_ids}
    zones_n = pd.DataFrame({"zone_id": [bz[b] for b in bus_ids],
                            "name": [f"{n} (bus {b}, Area {a})" for b, n, a in zip(bus["Bus ID"], bus["Bus Name"], bus["Area"])],
                            "rto": "RTS-GMLC", "x_bus_id": bus_ids, "x_area": [int(a) for a in bus["Area"]],
                            "x_base_kv": bus["BaseKV"].to_numpy(float)})
    for k, v in prov("published test-system value: bus.csv (Bus ID = zone, one zone per bus)").items():
        zones_n[k] = v
    share = bus.set_index("Bus ID")["MW Load"] / bus.groupby("Area")["MW Load"].transform("sum").set_axis(bus["Bus ID"])
    parts = []
    for b in bus_ids:
        a = int(bus_area[b])
        parts.append(pd.DataFrame({"zone": bz[b], "period_id": np.array(pid)[hours // T], "t": hours % T + 1,
                                   "demand_mw": np.round(ld[str(a)].to_numpy(float) * float(share[b]), 4)}))
    load_n = pd.concat(parts, ignore_index=True)
    lm_n = pd.DataFrame({"zone": [bz[b] for b in bus_ids], "net_of_btm": False, "year": MODEL_YEAR})
    for k, v in prov("derived: DAY_AHEAD_regional_Load.csv area series x bus share = bus.csv 'MW Load' / area sum of 'MW Load' (constant share); "
                     f"back-test: PLEXOS allTX KCL-implied nodal load (generation - net AC/DC outflow) equals this to {bt['load_share_max_err_mw']:.0e} "
                     f"MW max over {bt['n_hours']} h x 73 buses (A10); zero-load buses carry zero load",
                     method="derived", est_level=1, confidence="high").items():
        lm_n[k] = v
    lrows = []
    for _, r in branch.iterrows():
        lrows.append(dict(link_id="ac_" + rid(r["UID"]), zone_from=bz[int(r["From Bus"])], zone_to=bz[int(r["To Bus"])],
                          ntc_fwd_mw=float(r["Cont Rating"]), ntc_rev_mw=float(r["Cont Rating"]), reactance_pu=float(r["X"]),
                          base_mva=BASE_MVA, link_type="ac", x_branch_uid=r["UID"], x_lte_rating_mw=float(r["LTE Rating"]),
                          **prov(f"published test-system value: branch.csv {r['UID']} X (pu) and Cont Rating (MW; symmetric; LTE/STE not used, A3); "
                                 "R, B ignored (lossless DC); base_mva assumed 100 (cell override)", confidence="high")))
    d1 = dcb.iloc[0]
    lrows.append(dict(link_id="dc_" + rid(f"{int(d1['From Bus'])}_{int(d1['To Bus'])}"), zone_from=bz[int(d1["From Bus"])],
                      zone_to=bz[int(d1["To Bus"])], ntc_fwd_mw=float(d1["MW Load"]), ntc_rev_mw=float(d1["MW Load"]), reactance_pu=np.nan,
                      base_mva=np.nan, link_type="dc", x_branch_uid=d1["UID"], x_lte_rating_mw=np.nan,
                      **prov(f"derived: dc_branch.csv {d1['UID']} MW Load 100 used as +-100 MW rating (A4); controllable link, no reactance; "
                             f"back-test: PLEXOS allTX flow 113_316_1 in [{bt['dc1_min']:.0f}, {bt['dc1_max']:.0f}] MW; R Line ignored (lossless)",
                             method="derived", est_level=1, confidence="medium")))
    links_n = pd.DataFrame(lrows)
    assert (links_n["link_type"] == "ac").sum() == 120 and len(links_n) == 121
    cells_links_n = [dict(table="links", row_key=r, column="base_mva",
                          **prov("assumed: RTS-GMLC documents branch X as 'p.u.' without a base; 100 MVA (MATPOWER/RTS-96 convention) assumed. "
                                 "DC flows depend only on X ratios (PLEXOS flows reproduced to "
                                 f"{bt['dc_pf_max_err_mw']:.0e} MW, A11); the base only scales b_l and theta", method="assumed", confidence="medium"))
                     for r in links_n.loc[links_n.link_type == "ac", "link_id"]]
    res_n = resources.copy()
    res_n["zone"] = [bz[int(b)] for b in res_n["x_bus_id"]]
    cells_nz = [c if c["column"] != "zone" else {**c, **prov("derived: gen.csv Bus ID (one zone per bus)", method="derived", est_level=1)}
                for c in cells]
    A10 = dict(id="A10", parameter="bus_load_share", applies_to="load (nodal)", value="area DA series x MW Load share (constant)",
               method="derived", est_level=1, confidence="high", source_id=SRC, status="used",
               basis="PLEXOS participation factors are not vendored. Back-test instead: PLEXOS allTX nodal load implied by KCL (sum of unit generation at the "
                     "bus minus net AC branch and DC1 outflow, 336 h) equals our load to "
                     f"{bt['load_share_max_err_mw']:.0e} MW max, so PLEXOS shares are the bus.csv MW Load shares (static, area-normalised)")
    A11 = dict(id="A11", parameter="branch_reactance_lossless_dc", applies_to="links (nodal)", value="branch.csv X pu, base 100 MVA assumed; R, B ignored",
               method="observed", est_level="", confidence="high", source_id=SRC, status="used",
               basis="back-test: a lossless DC power flow with these X, PLEXOS generation, our bus loads and the PLEXOS DC1 flow reproduces all 120 PLEXOS allTX AC "
                     f"branch flows to {bt['dc_pf_max_err_mw']:.0e} MW max (336 h); the reference is therefore lossless DC, same physics as dcpf. base_mva=100 is assumed (flows invariant)")
    A15 = dict(id="A15", parameter="dc1_lossless_controllable", applies_to="dc_113_316", value="link_type dc, +-100 MW, R Line ignored",
               method="derived", est_level=1, confidence="medium", source_id=SRC, status="used",
               basis="gate-4.md S1: DC1 is a controllable link inside dcpf; its R Line (5) is ignored; PLEXOS DC1 flow lies in +-100 MW (A4)")
    notes_n = notes_for([A10, A11, A15, A_PROFILE], patch={"A3": dict(applies_to="links (each AC branch: own Cont Rating)"),
                                                           "A4": dict(applies_to="dc_113_316")})
    nodal_sw = {"tx.model": "dcpf"}
    out_n = out_root / "rts_gmlc_nodal"
    write_case(out_n, "rts_gmlc_nodal", "RTS-GMLC nodal (73 buses as zones, 120 AC branches + DC1 controllable link), full fleet incl. storage at "
               "bus 313, full year 2020 as 122 blocks of 72 h; dcpf; Gate 4 R4-NS/R4-NF",
               {"zones": (FILES["zones"], zones_n), "links": (FILES["links"], links_n), "load": (FILES["load"], load_n),
                "load_meta": (FILES["load_meta"], lm_n), "resources": (FILES["resources"], res_n)},
               {**common_shared, "availability": rel + FILES["availability"], "availability_meta": rel + FILES["availability_meta"]},
               nodal_sw, cells_nz + cells_links_n, notes_n)

    # --- rts_gmlc_nodal_px : aligned fleet nodal (R4-N, R4-NP, R4-NX)
    res_npx = res_n[~res_n["resource_id"].isin(ALIGN_DROP)].reset_index(drop=True)
    cells_npx = [c for c in cells_nz if c["row_key"] not in ALIGN_DROP] + cells_links_n
    notes_npx = pd.concat([notes_n, pd.DataFrame([A_ALIGN])], ignore_index=True)[list(assumptions.columns)]
    notes_npx.loc[notes_npx["id"] == "G3", ["status", "value"]] = ["gap", "not in this case (aligned fleet, A12)"]
    write_case(out_root / "rts_gmlc_nodal_px", "rts_gmlc_nodal_px", "RTS-GMLC nodal (73 buses, 120 AC branches + DC1), PLEXOS-aligned fleet (no CSP, no "
               "storage), full year 2020 as 122 blocks of 72 h; dcpf; Gate 4 R4-N/R4-NP/R4-NX vs PLEXOS DA allTX",
               {"resources": (FILES["resources"], res_npx)},
               {**common_shared, **{k: "../rts_gmlc_nodal/" + FILES[k] for k in ("zones", "links", "load", "load_meta")},
                "availability": "../rts_gmlc_px/" + FILES["availability"], "availability_meta": "../rts_gmlc_px/" + FILES["availability_meta"]},
               nodal_sw, cells_npx, notes_npx)

    # --- reference tables (K6)
    ref_meta = build_reference(raw, out, ld, gen_all_uids)
    rm = pd.DataFrame(ref_meta)
    for k, v in prov(f"observed: vendored PLEXOS DA result files (allTX, noTX), 336 h from {WINDOW_START}; tidy long format; first hour = period "
                     f"{WINDOW_FIRST_PERIOD} t=1 (verified against periods.csv source_start_date); sha256 equals MANIFEST.csv").items():
        rm[k] = v
    write_csv(rm, out / "reference" / "ref_plexos_da_meta.csv")

    # ------------------------------------------------------------------------------------------ summary
    print(f"zones={len(zones)} links={len(links)} resources={len(resources)} by type:",
          resources.groupby("type").size().to_dict(), "load_rows=", len(load), "hours/zone=", n_h, "periods=", len(periods))
    print("availability rows", len(availability), "tiny(<1e-3, zeroed by loader):", n_tiny)
    cap = resources.groupby(["type", "tech"])["k0_mw"].agg(["count", "sum"])
    print(cap.to_string())
    print("total MW", resources["k0_mw"].sum())


if __name__ == "__main__":
    main()
