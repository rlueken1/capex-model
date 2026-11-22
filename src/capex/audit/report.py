"""Aggregates all audit hooks for one solve and runs the health checks (section 8, gate-1 section 3)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import conditioning as cond
from . import duals, economics
from .duality import DualityReport, duality_report
from .pricesetter import PriceSetter, price_setter
from .solved import Solved


@dataclass(frozen=True)
class Audit:
    """Every hook output for one solve."""
    economics: duals.Economics
    balance_residual: np.ndarray
    duality: DualityReport
    conditioning: cond.Conditioning
    raw_duals: pd.DataFrame
    reduced_costs: pd.DataFrame
    binding: pd.DataFrame
    binding_bounds: pd.DataFrame
    objective: pd.DataFrame
    rents: pd.DataFrame
    storage: economics.StorageReport
    storage_rc_residual: float
    curtail_unserved: dict[str, pd.DataFrame]
    price_setter: PriceSetter | None      # None when the solution has no valid basis


def run_audit(sv: Solved) -> Audit:
    eco = duals.economic_duals(sv)
    return Audit(
        economics=eco, balance_residual=duals.balance_residuals(sv), duality=duality_report(sv),
        conditioning=cond.conditioning_report(sv), raw_duals=duals.raw_duals(sv), reduced_costs=duals.reduced_costs(sv),
        binding=duals.binding_report(sv), binding_bounds=duals.binding_bounds(sv),
        objective=economics.objective_decomposition(sv), rents=economics.rent_table(sv, eco),
        storage=economics.storage_report(sv, eco), storage_rc_residual=economics.storage_reduced_cost_residual(sv, eco),
        curtail_unserved=economics.curtailment_unserved(sv),
        price_setter=price_setter(sv, eco) if sv.sol.basis_valid else None)


def _check(check_id: str, family: str, value: float, tolerance: float, detail: str = "") -> dict:
    return {"check_id": check_id, "family": family, "status": "pass" if value <= tolerance else "fail",
            "value": float(value), "tolerance": float(tolerance), "detail": detail}


def _info(check_id: str, family: str, value: float, detail: str) -> dict:
    return {"check_id": check_id, "family": family, "status": "pass", "value": float(value), "tolerance": np.nan,
            "detail": detail}


def _decomposition_gap(sv: Solved, audit: Audit) -> float:
    total = audit.objective.loc[audit.objective["component"] == "total", "value_usd_yr"].iloc[0]
    reference = sv.sol.objective / (sv.lp.scaling.k_c * sv.lp.scaling.s_obj) + sv.z0
    return abs(total - reference) / max(abs(reference), 1.0)


def _price_setter_checks(sv: Solved, audit: Audit) -> list[dict]:
    ps = audit.price_setter
    if ps is None:
        return [{"check_id": "price_setter.basis", "family": "price_setter", "status": "fail", "value": np.nan,
                 "tolerance": np.nan, "detail": "no valid basis; price-setter skipped (section 4)"}]
    share = ps.summary.groupby("zone")["share_weighted_hours"].sum()
    return [_check("price_setter.unexplained", "price_setter", ps.unexplained, 0, "UNEXPLAINED zone-hours"),
            _check("price_setter.link_inconsistent", "price_setter", ps.link_inconsistent, 0,
                   "link-hours with inconsistent price gap / bound / congestion rent"),
            _check("price_setter.shares_sum_to_one", "price_setter", float(np.abs(share - 1.0).max()), 1e-9)]


def _rent_checks(sv: Solved, audit: Audit) -> list[dict]:
    rents, tol = audit.rents, sv.case.tolerances
    failed = rents.loc[~rents["zero_profit_ok"].astype(bool), "resource_id"].tolist()
    scale = np.maximum(1.0, np.maximum(rents["energy_revenue"].abs(), rents["variable_cost"].abs()))
    identity = float((rents["revenue_identity_residual"].abs() / scale).max())
    return [_check("zero_profit", "zero_profit", len(failed), 0, f"failing: {failed}" if failed else "all candidates ok"),
            _check("revenue_identity", "revenue_identity", identity, tol.revenue_identity_rel),
            _check("storage_reduced_costs", "zero_profit",
                   audit.storage_rc_residual / sv.lp.scaling.dual_factor, 1e-6,
                   "recomputed vs solver reduced costs of xP, xE (scaled units)")]


def _conditioning_checks(audit: Audit) -> list[dict]:
    c = audit.conditioning
    return [{"check_id": f"conditioning.{k}", "family": "conditioning", "status": status, "value": c.metrics[k],
             "tolerance": cond.THRESHOLDS[k][0], "detail": f"warn>{cond.THRESHOLDS[k][0]:g} fail>{cond.THRESHOLDS[k][1]:g}"}
            for k, status in c.status.items()]


def health_checks(sv: Solved, audit: Audit) -> pd.DataFrame:
    """All checks as a table with status pass | warn | fail."""
    tol, d = sv.case.tolerances, audit.duality
    closure = float(np.abs(audit.storage.closure["closure_residual_mwh"].to_numpy()).max(initial=0.0))
    n_simul = int(audit.storage.hourly["simul_chdis"].sum())
    checks = [
        _check("solver.optimal", "solver", float(not sv.sol.optimal), 0, sv.sol.status),
        _check("balance", "balance", float(np.abs(audit.balance_residual).max(initial=0.0)), tol.bal_residual_mw, "max |LHS-D| MW"),
        _check("strong_duality", "strong_duality", d.rel_gap, tol.strong_duality_rel,
               f"primal {d.z_primal_usd:.6f} dual {d.z_dual_usd:.6f} $ (excl. Z0)"),
        _check("comp_slack", "comp_slack", d.comp_slack, tol.comp_slack_scaled),
        _check("dual_sign", "dual_sign", d.sign_violation, tol.dual_sign_scaled),
        *_rent_checks(sv, audit),
        _check("decomposition", "decomposition", _decomposition_gap(sv, audit), tol.decomposition_rel,
               f"Z total {sv.z_total:.6f} incl. Z0 {sv.z0:.6f}"),
        _check("storage.closure", "storage", closure, 1e-6, "cyclic energy closure, MWh"),
        _info("storage.simul_chdis", "storage", n_simul, "hours with simultaneous charge and discharge (not an error)"),
        _check("basis_valid", "price_setter", float(not sv.sol.basis_valid), 0, "basic solution required (section 4)"),
        *_price_setter_checks(sv, audit), *_conditioning_checks(audit)]
    return pd.DataFrame(checks)


@dataclass(frozen=True)
class HealthReport:
    checks: pd.DataFrame
    audit: Audit = field(repr=False)

    @property
    def status(self) -> str:
        values = set(self.checks["status"])
        return "fail" if "fail" in values else "warn" if "warn" in values else "pass"

    def to_markdown(self, title: str) -> str:
        lines = [f"# Health report: {title}", f"Overall: **{self.status}**", "",
                 "| check | status | value | tolerance | detail |", "|---|---|---|---|---|"]
        lines += [f"| {r.check_id} | {r.status} | {r.value:.6g} | {r.tolerance:.6g} | {r.detail} |"
                  for r in self.checks.itertuples()]
        return "\n".join(lines) + "\n"


def health_report(sv: Solved) -> HealthReport:
    """Run every audit hook and health check; returns pass/warn/fail per check."""
    audit = run_audit(sv)
    return HealthReport(checks=health_checks(sv, audit), audit=audit)
