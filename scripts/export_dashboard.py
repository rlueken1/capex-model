"""Export model results into compact JSON tables for the owner's status dashboard.

Usage:
    python scripts/export_dashboard.py OUT_DIR [--runs RUNS_DIR] [--cases T1,T2a,...] [--skip-solve]

For each case it runs `python -m capex run cases/<case> --out RUNS_DIR/<case>` (unless --skip-solve),
then reads the run's output tables and writes, into OUT_DIR, one JSON file per table:

    res_cases.json      one row per case: size, cost, prices, health, fingerprint
    res_prices.json     zone x hour for small cases: LMP, demand, unserved, price-setter class/tech
    res_prices_large.json  the same for large cases (> 60 resources, e.g. RTS-GMLC), loaded only when viewed
    res_resources.json  per resource (small cases) or per zone x tech (large cases): capacity, energy, economics
    res_setters.json    price-setter shares by zone, class, tech
    res_links.json      per link: utilisation, hours at limit, congestion rent
    res_binding.json    constraint families: rows, binding rows, weighted share binding
    res_health.json     every health check with value, tolerance, status

Each file is {"rows": [...], "meta": [...]} with this script's source in meta, so the dashboard shows how
every number was made. Numbers come straight from the run outputs; only sums, weighted means and
shares are computed here.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ["T1", "T2a", "T2b", "T2c", "T3a", "T3b", "T4", "pjm5bus", "rts_gmlc"]
AGG_THRESHOLD = 60  # more resources than this -> aggregate by zone x tech


def rd(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def num(v, default=0.0):
    try:
        x = float(v)
        return default if math.isnan(x) else x
    except (TypeError, ValueError):
        return default


def clean(x, nd=6):
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return None
        return round(x, nd)
    return x


def solve(case: str, runs: Path) -> None:
    out = runs / case
    subprocess.run([sys.executable, "-m", "capex", "run", str(REPO / "cases" / case), "--out", str(out)],
                   check=True, cwd=REPO, stdout=subprocess.DEVNULL)


def export_case(case: str, run: Path, acc: dict) -> None:
    cy = yaml.safe_load((REPO / "cases" / case / "case.yaml").read_text())
    rj = json.loads((run / "run.json").read_text())
    res_in = {r["resource_id"]: r for r in rd(REPO / "cases" / case / "resources.csv")}
    zh = rd(run / "zone_hourly.csv")
    ps = {(r["zone"], r["period_id"], r["t"]): r for r in rd(run / "price_setter.csv")}
    health = rd(run / "health.csv")
    disp = rd(run / "dispatch.csv")
    cap = {r["resource_id"]: r for r in rd(run / "capacity.csv")}
    rents = {r["resource_id"]: r for r in rd(run / "rents.csv")}
    flows = rd(run / "flows.csv")
    big = len(res_in) > AGG_THRESHOLD

    # period weights (hours represented per modelled hour)
    w = {}
    for r in zh:
        w[(r["period"], r["t"])] = num(r["weight_hours"], 1.0)

    # prices
    seq = defaultdict(int)
    dem_w = lmp_dem_w = unserved_mwh = 0.0
    peak = -1e99
    unexplained = 0
    zones = sorted({r["zone"] for r in zh})
    for r in zh:
        z = r["zone"]
        seq[z] += 1
        p = ps.get((z, r["period"], r["t"]), {})
        lmp = num(r["lmp_usd_mwh"])
        d = num(r["demand_mw"])
        wt = num(r["weight_hours"], 1.0)
        dem_w += d * wt
        lmp_dem_w += lmp * d * wt
        unserved_mwh += num(r["unserved_mw"]) * wt
        peak = max(peak, lmp)
        cls = p.get("primary_class", "")
        if cls == "UNEXPLAINED":
            unexplained += 1
        acc["prices_large" if big else "prices"].append({
            "case": case, "zone": z, "i": seq[z], "weight": clean(wt, 4), "lmp": clean(lmp, 2),
            "demand_mw": clean(d, 1), "unserved_mw": clean(num(r["unserved_mw"]), 2),
            "setter_class": cls, "setter_tech": p.get("setter_tech", ""),
        })

    # energy by resource (weighted)
    energy = defaultdict(float)
    charge = defaultdict(float)
    discharge = defaultdict(float)
    for r in disp:
        wt = w.get((r["period"], r["t"]), 1.0)
        energy[r["resource"]] += num(r["g_mw"]) * wt
        charge[r["resource"]] += num(r["charge_mw"]) * wt
        discharge[r["resource"]] += num(r["discharge_mw"]) * wt
    total_h = sum(w.values()) / max(1, len(zones)) if w else 0.0

    rows = []
    for rid, ri in res_in.items():
        c = cap.get(rid, {})
        rt = rents.get(rid, {})
        mw = num(c.get("existing_mw")) + num(c.get("new_mw"))
        e = energy[rid] if ri.get("type") != "ST" else discharge[rid]
        rows.append({
            "case": case, "resource": rid, "zone": ri.get("zone", ""), "tech": ri.get("tech", ""),
            "fuel": ri.get("fuel", ""), "type": ri.get("type", ""), "status": ri.get("status", ""),
            "existing_mw": num(c.get("existing_mw")), "new_mw": num(c.get("new_mw")),
            "existing_mwh": num(c.get("existing_mwh")), "new_mwh": num(c.get("new_mwh")),
            "energy_mwh": e, "charge_mwh": charge[rid],
            "energy_revenue": num(rt.get("energy_revenue")), "variable_cost": num(rt.get("variable_cost")),
            "fixed_cost": num(rt.get("fixed_cost")), "rent_cap": num(rt.get("rent_cap_usd_mw_yr")),
            "profit": num(rt.get("profit")),
            "zero_profit_ok": str(rt.get("zero_profit_ok", "")).lower() in ("true", "1"),
            "build_status": rt.get("build_status", ""), "_mw": mw,
        })
    if big:
        agg = {}
        for r in rows:
            k = (r["zone"], r["tech"], r["fuel"], r["type"])
            a = agg.setdefault(k, {"case": case, "resource": f"{r['tech']} ({r['zone']})", "zone": r["zone"],
                                   "tech": r["tech"], "fuel": r["fuel"], "type": r["type"], "status": "",
                                   "units": 0, "zero_profit_ok": True, "build_status": ""})
            a["units"] += 1
            for f in ("existing_mw", "new_mw", "existing_mwh", "new_mwh", "energy_mwh", "charge_mwh",
                      "energy_revenue", "variable_cost", "fixed_cost", "profit", "_mw"):
                a[f] = a.get(f, 0.0) + r[f]
            a["rent_cap"] = None
            a["zero_profit_ok"] = a["zero_profit_ok"] and r["zero_profit_ok"]
            stats = {r["build_status"] for r in rows if (r["zone"], r["tech"]) == (a["zone"], a["tech"])}
            a["build_status"] = "/".join(sorted(s for s in stats if s))
        rows = list(agg.values())
    for r in rows:
        mw = r.pop("_mw")
        r["cf"] = clean(r["energy_mwh"] / (mw * total_h)) if mw > 0 and total_h > 0 and r["type"] != "ST" else None
        r["avg_revenue_usd_mwh"] = clean(r["energy_revenue"] / r["energy_mwh"]) if r["energy_mwh"] > 0 else None
        r["units"] = r.get("units", 1)
        acc["resources"].append({k: clean(v, 3) if isinstance(v, float) else v for k, v in r.items()})

    for r in rd(run / "price_setter_summary.csv"):
        acc["setters"].append({"case": case, "zone": r["zone"], "class": r["class"], "tech": r["tech"],
                               "fuel": r["fuel"], "hours": clean(num(r["weighted_hours"]), 2),
                               "share": clean(num(r["share_weighted_hours"]))})

    # links
    lk = defaultdict(lambda: {"n": 0, "wt": 0.0, "at": 0.0, "absf": 0.0, "maxf": 0.0, "rent": 0.0})
    for r in flows:
        wt = w.get((r["period"], r["t"]), 1.0)
        a = lk[r["link"]]
        f = num(r["flow_mw"])
        a["n"] += 1
        a["wt"] += wt
        a["at"] += wt if str(r["at_bound"]).lower() == "true" else 0.0
        a["absf"] += abs(f) * wt
        a["maxf"] = max(a["maxf"], abs(f))
        a["rent"] += abs(num(r["congestion_rent_usd_mwh"])) * abs(f) * wt
    congested_share = 0.0
    for link, a in lk.items():
        acc["links"].append({"case": case, "link": link, "share_at_limit": clean(a["at"] / a["wt"]) if a["wt"] else None,
                             "avg_abs_flow_mw": clean(a["absf"] / a["wt"], 2) if a["wt"] else None,
                             "max_abs_flow_mw": clean(a["maxf"], 2), "congestion_rent_usd_yr": clean(a["rent"], 0)})
        congested_share = max(congested_share, a["at"] / a["wt"] if a["wt"] else 0.0)

    for r in rd(run / "binding.csv"):
        acc["binding"].append({"case": case, "family": r["family"], "rows": int(num(r["n_rows"])),
                               "binding": int(num(r["n_binding"])),
                               "share": clean(num(r["weighted_share_binding"]))})
    for r in health:
        acc["health"].append({"case": case, "check": r["check_id"], "family": r["family"], "status": r["status"],
                              "value": clean(num(r["value"], float("nan")), 9), "tolerance": r["tolerance"],
                              "detail": r.get("detail", "")})

    lmps = [num(r["lmp_usd_mwh"]) for r in zh]
    acc["cases"].append({
        "case": case, "description": " ".join(str(cy.get("description", "")).split()),
        "formulation": rj.get("formulation_version"), "tx_model": (cy.get("switches") or {}).get("tx.model", "transport"),
        "zones": len(zones), "resources": len(res_in), "modelled_hours": len({(r["period"], r["t"]) for r in zh}),
        "represented_hours": clean(total_h, 1), "status": rj.get("status"),
        "z_total_usd_yr": clean(num(rj.get("z_total_usd_yr")), 0), "z0_usd_yr": clean(num(rj.get("z0_usd_yr")), 0),
        "avg_lmp": clean(lmp_dem_w / dem_w, 3) if dem_w else None, "peak_lmp": clean(peak, 2),
        "min_lmp": clean(min(lmps), 2) if lmps else None,
        "unserved_mwh": clean(unserved_mwh, 2), "load_mwh": clean(dem_w, 0),
        "max_link_share_at_limit": clean(congested_share, 4), "unexplained_hours": unexplained,
        "health_pass": sum(r["status"] == "pass" for r in health),
        "health_warn": sum(r["status"] == "warn" for r in health),
        "health_fail": sum(r["status"] == "fail" for r in health), "health_total": len(health),
        "lp_rows": rj.get("rows"), "lp_cols": rj.get("cols"), "lp_nnz": rj.get("nnz"),
        "solve_s": clean(num(rj.get("solve_time_s")), 3), "solver": f"{rj.get('solver')} {rj.get('solver_version')}",
        "fingerprint": str(rj.get("fingerprint", ""))[:12], "git_commit": str(rj.get("git_commit", ""))[:10],
        "run_at": rj.get("timestamp"),
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--runs", default="/tmp/capex_runs")
    ap.add_argument("--cases", default=",".join(DEFAULT_CASES))
    ap.add_argument("--skip-solve", action="store_true")
    a = ap.parse_args()
    out, runs = Path(a.out), Path(a.runs)
    out.mkdir(parents=True, exist_ok=True)
    acc = {k: [] for k in ("cases", "prices", "prices_large", "resources", "setters", "links", "binding", "health")}
    for case in [c for c in a.cases.split(",") if c]:
        if not a.skip_solve:
            solve(case, runs)
        export_case(case, runs / case, acc)
    src = Path(__file__).read_text()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    meta = [
        {"label": "export_dashboard.py", "value": src, "type": "code", "lang": "python"},
        {"label": "Repo", "value": f"rlueken1/capex-model @ {branch} {commit}"},
        {"label": "Exported", "value": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"label": "Inputs", "value": "outputs of `python -m capex run cases/<case>` for each case"},
    ]
    for k, rows in acc.items():
        (out / f"res_{k}.json").write_text(json.dumps({"rows": rows, "meta": meta}, separators=(",", ":"), allow_nan=False))
        print(f"res_{k}.json rows={len(rows)}")


if __name__ == "__main__":
    main()
