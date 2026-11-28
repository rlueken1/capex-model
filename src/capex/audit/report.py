"""Aggregates all audit hooks for one solve and runs the health checks (section 8, gate-1 section 3)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import conditioning as cond
from . import duals, economics
from .duality import DualityReport, duality_report
from .loopsetter import alpha_residual, dcpf_price_setter
from .network import NetworkReport, network_report
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
    soc_residual: float
    curtail_unserved: dict[str, pd.DataFrame]
    price_setter: PriceSetter | None      # None when the solution has no valid basis
    network: NetworkReport | None = None  # dcpf only


def _setter(sv: Solved, eco: duals.Economics, net: NetworkReport | None) -> PriceSetter | None:
    if not sv.sol.basis_valid:
        return None
    return price_setter(sv, eco) if net is None else dcpf_price_setter(sv, eco, net)


def run_audit(sv: Solved) -> Audit:
    eco = duals.economic_duals(sv)
    net = network_report(sv, eco) if sv.case.dcpf else None
    return Audit(
        economics=eco, balance_residual=duals.balance_residuals(sv), duality=duality_report(sv),
        conditioning=cond.conditioning_report(sv), raw_duals=duals.raw_duals(sv), reduced_costs=duals.reduced_costs(sv),
        binding=duals.binding_report(sv), binding_bounds=duals.binding_bounds(sv),
        objective=economics.objective_decomposition(sv), rents=economics.rent_table(sv, eco),
        storage=economics.storage_report(sv, eco), storage_rc_residual=economics.storage_reduced_cost_residual(sv, eco),
        soc_residual=economics.soc_recompute_residual(sv),
        curtail_unserved=economics.curtailment_unserved(sv),
        price_setter=_setter(sv, eco, net), network=net)


def _check(check_id: str, family: str, value: float, tolerance: float, detail: str = "") -> dict:
    return {"check_id": check_id, "family": family, "status": "pass" if value <= tolerance else "fail",
            "value": float(value), "tolerance": float(tolerance), "detail": detail}


def _profile_check(sv: Solved, check_id: str, family: str, value: float, exact_tol: float, detail: str) -> dict:
    """A recomputation check whose thresholds follow the case's audit profile (formulation 3): `exact` pass <= exact_tol;
    `standard` warn > 1e-3, fail > 1e-1 (the section 6.2 `bal` pair). Key absent: bytes of F-0.3."""
    profile = sv.case.audit_profile
    if profile != "standard":
        return _check(check_id, family, value, exact_tol, detail + (f"; audit_profile={profile}" if profile else ""))
    warn, fail = cond.THRESHOLDS["bal_residual_mw"]
    status = "fail" if value > fail else "warn" if value > warn else "pass"
    return {"check_id": check_id, "family": family, "status": status, "value": float(value), "tolerance": float(warn),
            "detail": f"{detail}; audit_profile=standard warn>{warn:g} fail>{fail:g}"}


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
    link_detail = "link-hours with inconsistent price gap / bound / congestion rent"
    if sv.case.dcpf:
        link_detail = ("DC links only under dcpf (AC lines: see lmp.decomposition, dcpf.line_duals)"
                       if sv.case.links.is_dc.any() else "n/a under dcpf (see lmp.decomposition, dcpf.line_duals)")
    checks = [_check("price_setter.unexplained", "price_setter", ps.unexplained, 0, "UNEXPLAINED zone-hours"),
              _check("price_setter.link_inconsistent", "price_setter", ps.link_inconsistent, 0,
                     link_detail),
              _check("price_setter.shares_sum_to_one", "price_setter", float(np.abs(share - 1.0).max()), 1e-9)]
    if sv.case.dcpf:
        checks.append(_check("price_setter.loop_alpha", "price_setter", alpha_residual(ps),
                             sv.case.tolerances.loop_alpha, "max(|sum alpha - 1|, |pi - sum alpha c|) over CONGESTION_LOOP"))
        checks.append(_check("price_setter.loop_interval", "price_setter", ps.loop_interval, 0,
                             "storage rows conditional on solved v" if ps.storage_rows_used else ""))
    return checks


def _network_checks(sv: Solved, audit: Audit) -> list[dict]:
    """Formulation 7.4a.6: recomputations from case data (dcpf only)."""
    rep, tol = audit.network, sv.case.tolerances
    m = rep.metrics
    return [_profile_check(sv, "kvl.recompute", "network", m["kvl"], tol.kvl_residual_mw,
                           "max |f - b(theta_o - theta_e)| MW, case b, theta from output angles"),
            _profile_check(sv, "ptdf.recompute", "network", m["ptdf"], tol.kvl_residual_mw,
                           "max |f - f_rc| MW, f_rc from B_red theta = inj (case b, solved inj)"),
            _check("lmp.decomposition", "network", m["lmp"], tol.lmp_decomposition_usd_mwh,
                   "max |pi - (lambda - sum_l H mu)| $/MWh, H from case data"),
            _check("congestion_rent", "network", m["rent"], tol.congestion_rent_rel,
                   "max |sum pi (-inj) - sum mu f| / max(1, |sum mu f|)"),
            _check("dcpf.line_duals", "network", m["line_duals"], tol.line_dual_usd_mwh,
                   "mu != 0 only at a rating, mu sgn f >= 0"),
            _check("dcpf.islands", "network", rep.island_violations, 0, rep.island_detail)]


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
        _profile_check(sv, "balance", "balance", float(np.abs(audit.balance_residual).max(initial=0.0)),
                       tol.bal_residual_mw, "max |LHS-D| MW"),
        _check("strong_duality", "strong_duality", d.rel_gap, tol.strong_duality_rel,
               f"primal {d.z_primal_usd:.6f} dual {d.z_dual_usd:.6f} $ (excl. Z0)"),
        _check("comp_slack", "comp_slack", d.comp_slack, tol.comp_slack_scaled),
        _check("dual_sign", "dual_sign", d.sign_violation, tol.dual_sign_scaled),
        *_rent_checks(sv, audit),
        _check("decomposition", "decomposition", _decomposition_gap(sv, audit), tol.decomposition_rel,
               f"Z total {sv.z_total:.6f} incl. Z0 {sv.z0:.6f}"),
        _check("storage.closure", "storage", closure, 1e-6, "cyclic energy closure, MWh"),
        _profile_check(sv, "storage.soc_recompute", "storage", audit.soc_residual, 1e-6,
                       "st_soc residual recomputed from case eta_c, eta_d, sigma, MWh"),
        _info("storage.simul_chdis", "storage", n_simul, "hours with simultaneous charge and discharge (not an error)"),
        _check("basis_valid", "price_setter", float(not sv.sol.basis_valid), 0, "basic solution required (section 4)"),
        *_price_setter_checks(sv, audit), *_conditioning_checks(audit), *(_network_checks(sv, audit) if sv.case.dcpf else [])]
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
