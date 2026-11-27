"""End-to-end run: load case, build LP, solve, audit, write output tables."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import SCHEMA_VERSION
from .audit import assumptions, duals, network
from .audit.fingerprint import Fingerprint, run_fingerprint
from .audit.report import HealthReport, health_report
from .audit.solved import Solved
from .config import Scaling
from .data import Case, load_case
from .model import build_lp
from .solver import Solver, SolverError, make_solver


def solve_case(case: Case, scaling: Scaling | None = None, solver: Solver | None = None) -> Solved:
    """Build the LP and solve it; raises SolverError unless optimal."""
    scaling = scaling or (Scaling() if case.switches.get("scaling", True) else Scaling.off())
    lp = build_lp(case, scaling)
    sol = (solver or make_solver(case.solver_config)).solve(lp)
    if not sol.optimal:
        raise SolverError(f"{case.case_id}: solver status {sol.status}")
    return Solved(case, lp, sol)


def _dispatch(sv: Solved) -> pd.DataFrame:
    gen = sv.case.gen
    curt = np.where((gen.kind == "VRE")[:, None, None],
                    gen.avail * (gen.k0 + sv.var("x"))[:, None, None] - sv.var("g"), 0.0)
    g = sv.lp.cols["g"].frame().drop(columns="label").assign(g_mw=sv.var("g").ravel(), curtail_mw=curt.ravel())
    s = sv.lp.cols["soc"].frame().drop(columns="label").assign(
        charge_mw=sv.var("ch").ravel(), discharge_mw=sv.var("dis").ravel(), soc_mwh=sv.var("soc").ravel())
    return pd.concat([g, s], ignore_index=True)


def _capacity(sv: Solved) -> pd.DataFrame:
    gen, st = sv.case.gen, sv.case.storage
    x, xp, xe = sv.var("x"), sv.var("xP"), sv.var("xE")
    g = pd.DataFrame({"resource_id": gen.ids, "existing_mw": gen.k0, "new_mw": x, "existing_mwh": np.nan,
                      "new_mwh": np.nan, "at_xmax": np.isfinite(gen.xmax) & (gen.xmax > 0) & (x >= gen.xmax - 1e-6),
                      "x_reduced_cost_usd_mw_yr": sv.col_dual("x")})
    s = pd.DataFrame({"resource_id": st.ids, "existing_mw": st.p0, "new_mw": xp, "existing_mwh": st.e0, "new_mwh": xe,
                      "at_xmax": (st.xp_max > 0) & (xp >= st.xp_max - 1e-6) & (xe >= st.xe_max - 1e-6),
                      "x_reduced_cost_usd_mw_yr": sv.col_dual("xP")})
    return pd.concat([g, s], ignore_index=True)


def _flows(sv: Solved, eco: duals.Economics) -> pd.DataFrame:
    lk = sv.case.links
    flow = sv.var("flow")
    at_bound = (flow >= lk.f_plus[:, None, None] - 1e-6) | (flow <= -lk.f_minus[:, None, None] + 1e-6)
    return sv.lp.cols["flow"].frame().drop(columns="label").assign(
        flow_mw=flow.ravel(), congestion_rent_usd_mwh=eco.mu_link.ravel(), at_bound=at_bound.ravel())


def run_json(sv: Solved, health: HealthReport, fp: Fingerprint) -> dict:
    c, sol = sv.case, sv.sol
    comps = fp.components
    return {
        "run_id": uuid.uuid4().hex, "fingerprint": str(fp), "fingerprint_sha256": fp.sha256, "valid": fp.valid,
        "case_id": c.case_id, "formulation_version": c.formulation_version, "schema_version": SCHEMA_VERSION,
        "git_commit": comps["git_commit"], "dirty_diff_hash": comps["dirty_diff_hash"], "solver": sol.solver_name,
        "solver_version": sol.solver_version, "solver_options": sol.options, "python": comps["python"],
        "packages": comps["packages"], "seed": c.seed, "timestamp": datetime.now(timezone.utc).isoformat(),
        "solve_time_s": sol.solve_time_s, "rows": sv.lp.n_rows, "cols": sv.lp.n_cols, "nnz": int(sv.lp.a.nnz),
        "status": sol.status, "crossover_ran": sol.crossover_ran, "iterations": sol.iterations,
        "z_total_usd_yr": sv.z_total, "z0_usd_yr": sv.z0, "health": health.status, "scaling": comps["scaling"]}


def fingerprint_of(sv: Solved, health: HealthReport) -> Fingerprint:
    s = sv.lp.scaling
    return run_fingerprint(sv.case, sv.sol, {"k_p": s.k_p, "k_c": s.k_c, "s_obj": s.s_obj},
                           valid=health.audit.conditioning.worst != "fail")


def output_tables(sv: Solved, health: HealthReport) -> dict[str, pd.DataFrame]:
    a = health.audit
    tables = {
        "dispatch": _dispatch(sv), "zone_hourly": duals.economic_table(sv, a.economics),
        "flows": _flows(sv, a.economics), "capacity": _capacity(sv), "duals_raw": a.raw_duals,
        "reduced_costs": a.reduced_costs, "rents": a.rents, "objective": a.objective, "binding": a.binding,
        "binding_bounds": a.binding_bounds, "annualization": sv.case.annualization, "storage": a.storage.hourly,
        "storage_closure": a.storage.closure, "curtailment": a.curtail_unserved["curtailment"],
        "unserved": a.curtail_unserved["unserved"], "health": health.checks}
    if a.price_setter is not None:
        tables |= {"price_setter": a.price_setter.table, "price_setter_summary": a.price_setter.summary,
                   "link_issues": a.price_setter.link_issues}
    if a.network is not None:
        tables["zone_hourly"] = tables["zone_hourly"].assign(**network.zone_hourly_columns(sv, a.network))
        tables |= {"angles": network.angles_table(sv, a.network), "islands": network.islands_table(sv.case, a.network)}
        if a.price_setter is not None:
            tables["price_setter_loop"] = a.price_setter.loop
    return tables


def write_outputs(out_dir: Path, sv: Solved, health: HealthReport) -> Fingerprint:
    """Write all output tables (CSV), conditioning.json, run.json, assumptions.md and health_report.md."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, table in output_tables(sv, health).items():
        table.to_csv(out_dir / f"{name}.csv", index=False)
    fp = fingerprint_of(sv, health)
    run = run_json(sv, health, fp)
    (out_dir / "run.json").write_text(json.dumps(run, indent=2, default=str))
    (out_dir / "conditioning.json").write_text(json.dumps(
        {"metrics": health.audit.conditioning.metrics, "status": health.audit.conditioning.status}, indent=2, default=str))
    (out_dir / "assumptions.md").write_text(assumptions.assumptions_book(sv.case, run["run_id"], run["fingerprint"]))
    (out_dir / "health_report.md").write_text(health.to_markdown(sv.case.case_id))
    return fp


def run_case(case_dir: str | Path, out_dir: str | Path) -> tuple[Solved, HealthReport, Fingerprint]:
    sv = solve_case(load_case(case_dir))
    health = health_report(sv)
    return sv, health, write_outputs(Path(out_dir), sv, health)
