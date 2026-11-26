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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(REPO / "cases/raw/rts_gmlc/RTS_Data"))
    ap.add_argument("--out", default=str(REPO / "cases/rts_gmlc"))
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sd, ts = raw / "SourceData", raw / "timeseries_data_files"

    gen = pd.read_csv(sd / "gen.csv")
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
                              **prov(f"assumed: DC link {d['UID']} bus {d['From Bus']}->{d['To Bus']} (control mode {d['Control Mode']}); "
                                     "dc_branch.csv MW Load (scheduled setpoint) used as a symmetric rating", method="assumed",
                                     confidence="low")))
    links = pd.DataFrame(link_rows)
    notes.append(dict(id="A3", parameter="link_rating", applies_to="links", value="Cont Rating (MW)", method="derived", est_level=1,
                      confidence="medium", source_id=SRC,
                      basis="back-test: PLEXOS allTX DA flow on CB-1 saturates at exactly 500 MW = Cont Rating (LTE 600 not used)",
                      status="used"))
    notes.append(dict(id="A4", parameter="dc_link_rating", applies_to=links.loc[links.link_id.str.startswith("dc"), "link_id"].iloc[0],
                      value="100 MW symmetric", method="assumed", est_level="", confidence="low", source_id=SRC,
                      basis="dc_branch.csv has a scheduled setpoint, not a rating; PLEXOS DA flow file has no DC1 column to back-test",
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
    local_src = pd.concat([common_src, pd.DataFrame([dict(source_id=SRC, description=(
        "RTS-GMLC test system (GridMod/NREL, github.com/GridMod/RTS-GMLC) at pinned commit 3ece0d3; internal test use only, "
        "licence unverified (DECISIONS 34); Barrows et al., IEEE Trans. Power Syst. 35(1), 2020"))])], ignore_index=True)

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

    # ------------------------------------------------------------------------------------------ write
    files = {"periods": ("periods.csv", periods), "zones": ("zones.csv", zones), "links": ("links.csv", links),
             "load": ("load.csv", load), "load_meta": ("load_meta.csv", load_meta), "resources": ("resources.csv", resources),
             "finance": ("finance.csv", finance), "availability": ("availability.csv.gz", availability),
             "availability_meta": ("availability_meta.csv", availability_meta), "fuel_map": ("fuel_map.csv", fuel_map),
             "fuel_prices": ("fuel_prices.csv", fuel_prices), "fuel_prices_meta": ("fuel_prices_meta.csv", fuel_prices_meta),
             "sources": ("sources.csv", local_src)}
    for name, (fn, df) in files.items():
        write_csv(df, out / fn)
    prov_cells = pd.DataFrame(cells)[["table", "row_key", "column"] + PROV[:1] + ["vintage", "retrieved", "method", "basis", "confidence", "est_level"]]
    write_csv(prov_cells, out / "provenance_cells.csv")        # sidecar: the loader does not read it yet
    write_csv(assumptions, out / "assumptions.csv")            # sidecar: explicit assumption / gap register
    tables = {name: {"file": fn, "sha256": sha256(out / fn)} for name, (fn, _) in files.items()}
    tables["deflator"] = {"file": "../../data/common/deflator.csv", "sha256": sha256(REPO / "data/common/deflator.csv")}
    manifest = {"case_id": "rts_gmlc",
                "description": "RTS-GMLC fixed fleet, 3 zones (areas), full year 2020 as 122 weight-1 blocks of 72 h; Gate 4 dispatch check",
                "schema_version": "S-0.1", "formulation_version": "F-0.2", "base_dollar_year": BASE_YEAR, "model_year": MODEL_YEAR,
                "dt_h": 1.0, "voll_usd_mwh": 10000, "voll_dollar_year": 2024, "finance_default": "rts_unused", "seed": 0,
                "solver": {"name": "highs"}, "switches": {}, "tables": tables}
    (out / "case.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    # ------------------------------------------------------------------------------------------ summary
    print(f"zones={len(zones)} links={len(links)} resources={len(resources)} by type:",
          resources.groupby("type").size().to_dict(), "load_rows=", len(load), "hours/zone=", n_h, "periods=", len(periods))
    print("availability rows", len(availability), "tiny(<1e-3, zeroed by loader):", n_tiny)
    cap = resources.groupby(["type", "tech"])["k0_mw"].agg(["count", "sum"])
    print(cap.to_string())
    print("total MW", resources["k0_mw"].sum())


if __name__ == "__main__":
    main()
