"""Verifier tests: gate-1.md section 3 health-check table, rows 1-10 (and the W4a gap closures).

Written from docs/formulation.md (1.3, 3, 4, 6, 8, 10) and docs/gates/gate-1.md (2, 3); DECISIONS 25 and 30.
Expected values and pass rules come from the spec; the audit layer's own verdicts are cross-checked by independent
recomputation in tests/healthlib.py (balance, complementary slackness, strong duality, rents, SOC dynamics, price checks).

Tolerances are the spec's and are never loosened here.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import capex.audit.conditioning as cond
import capex.solver as solver_mod
from capex.config import Scaling
from capex.model import LP
from capex.solver import HighsSolver, make_solver
from healthlib import (CANON_CASES, CASES, W1, Spec, cs_and_signs, failing, independent_balance,
                       non_pass, price_setter_violations, rent_violations, soc_residual, solve_audit,
                       stationarity_residual, st, th, toy_spec, write_case)

import scipy.sparse as sp

ALL = CANON_CASES + ["S1", "S2"]


def close(a, b, rel, abs_=1e-6):
    return abs(a - b) <= max(abs_, rel * abs(b))


# ================================================================== row 1: balance residual
@pytest.mark.parametrize("name", CANON_CASES)
def test_balance_residual(canon, name):
    c = canon(name)
    # independent: injections rebuilt from OUTPUT tables and INPUT csv files, not from the audit layer
    assert independent_balance(c.case_dir, c.tables) <= 1e-6, "formulation 3.1 check 1 / gate-1 section 3: <= 1e-6 MW"
    row = c.health.checks.set_index("check_id").loc["balance"]
    assert row["status"] == "pass" and row["value"] <= 1e-6 and row["tolerance"] <= 1e-6
    assert c.tables["zone_hourly"]["bal_residual_mw"].abs().max() <= 1e-6


# ================================================================== row 2: dual-sign adapter
def _lp(a, c, row_lo, row_hi, col_lo, col_hi) -> LP:
    return LP(a=sp.csr_matrix(np.asarray(a, float)), c=np.asarray(c, float), row_lo=np.asarray(row_lo, float),
              row_hi=np.asarray(row_hi, float), col_lo=np.asarray(col_lo, float), col_hi=np.asarray(col_hi, float),
              rows={}, cols={}, scaling=Scaling.off())


INF = np.inf
# Each LP is 2-variable with one binding row and one binding bound; closed-form optimum and duals (y = dZ/db, s = c - A'y).
ADAPTER_LPS = {
    # min -x1-x2  s.t. x1+2x2 <= 4, 0<=x1<=1.  x=(1,1.5) Z=-2.5; y=-0.5 (<=0), s=(-0.5 at upper, 0)
    "le_row_and_upper_bound": (_lp([[1, 2]], [-1, -1], [-INF], [4], [0, 0], [1, INF]),
                               dict(x=[1, 1.5], z=-2.5, y=[-0.5], s=[-0.5, 0.0], row_kind="le")),
    # min 3x1+x2  s.t. x1+2x2 >= 4, x1>=1.  x=(1,1.5) Z=4.5; y=+0.5 (>=0), s=(2.5 at lower, 0)
    "ge_row_and_lower_bound": (_lp([[1, 2]], [3, 1], [4], [INF], [1, 0], [INF, INF]),
                               dict(x=[1, 1.5], z=4.5, y=[0.5], s=[2.5, 0.0], row_kind="ge")),
    # min x1+2x2  s.t. x1+x2 = 3, 0<=x1<=2.  x=(2,1) Z=4; y=+2 (free sign), s=(-1 at upper, 0)
    "eq_row_positive_dual_and_upper_bound": (_lp([[1, 1]], [1, 2], [3], [3], [0, 0], [2, INF]),
                                             dict(x=[2, 1], z=4.0, y=[2.0], s=[-1.0, 0.0], row_kind="eq")),
    # min -2x1-x2 s.t. x1+x2 = 3, 0<=x1<=2.  x=(2,1) Z=-5; y=-1 (free sign), s=(-1 at upper, 0)
    "eq_row_negative_dual_and_upper_bound": (_lp([[1, 1]], [-2, -1], [3], [3], [0, 0], [2, INF]),
                                             dict(x=[2, 1], z=-5.0, y=[-1.0], s=[-1.0, 0.0], row_kind="eq")),
    # min -x1+x2 s.t. x1+x2 <= 4, x2>=1.  x=(3,1) Z=-2; y=-1, s=(0, 2 at lower)
    "le_row_and_lower_bound": (_lp([[1, 1]], [-1, 1], [-INF], [4], [0, 1], [INF, INF]),
                               dict(x=[3, 1], z=-2.0, y=[-1.0], s=[0.0, 2.0], row_kind="le")),
}


@pytest.mark.parametrize("solver_name", ["highs", "scipy"])
@pytest.mark.parametrize("lp_name", list(ADAPTER_LPS))
def test_adapter_dual_signs_and_values(solver_name, lp_name):
    """formulation 1.3: y_i = dZ*/db_i (<=0 on binding <=, >=0 on binding >=, free on =); column duals
    s_j = c_j - sum a_ij y_i (>=0 at lower, <=0 at upper). Exact values on closed-form 2-variable LPs."""
    lp, e = ADAPTER_LPS[lp_name]
    sol = make_solver({"name": solver_name}).solve(lp)
    assert sol.optimal
    assert np.allclose(sol.x, e["x"], atol=1e-9) and abs(sol.objective - e["z"]) <= 1e-9
    assert np.allclose(sol.row_dual, e["y"], atol=1e-9), f"row dual {sol.row_dual} expected {e['y']}"
    assert np.allclose(sol.col_dual, e["s"], atol=1e-9), f"column dual {sol.col_dual} expected {e['s']}"
    y = sol.row_dual[0]
    assert {"le": y <= 1e-12, "ge": y >= -1e-12, "eq": True}[e["row_kind"]]
    # reduced cost definition holds exactly
    assert np.allclose(lp.c - lp.a.T @ sol.row_dual, sol.col_dual, atol=1e-9)
    # sensitivity meaning of y: re-solve with b perturbed
    d = 1e-3
    lo, hi = lp.row_lo.copy(), lp.row_hi.copy()
    lo, hi = (lo + d if np.isfinite(lo[0]) else lo), (hi + d if np.isfinite(hi[0]) else hi)
    pert = dataclasses.replace(lp, row_lo=lo, row_hi=hi)
    z2 = make_solver({"name": solver_name}).solve(pert).objective
    assert abs((z2 - sol.objective) / d - y) <= 1e-6, "y must equal dZ*/db"


@pytest.mark.parametrize("name,flip", [("T1", "rows"), ("T1", "cols"), ("T4", "rows"), ("T4", "cols")])
def test_broken_adapter_rejects_run(name, flip):
    """An adapter returning the wrong dual convention must make the run fail its health checks."""
    class Broken(HighsSolver):
        def solve(self, lp):
            sol = super().solve(lp)
            return dataclasses.replace(sol, row_dual=-sol.row_dual if flip == "rows" else sol.row_dual,
                                       col_dual=-sol.col_dual if flip == "cols" else sol.col_dual)
    _, health = solve_audit(CASES / name, solver=Broken())
    assert health.status == "fail", f"broken adapter ({flip}) accepted: {non_pass(health)}"


# ================================================================== row 3 + 4: strong duality, complementary slackness
@pytest.mark.parametrize("name", ALL)
def test_strong_duality(canon, name):
    c = canon(name)
    cs, viol, gap = cs_and_signs(c.sv)           # gap = |Z~ - dual objective| / max(1,|Z~|), recomputed here
    assert gap <= 1e-7, f"strong duality gap {gap}"
    row = c.health.checks.set_index("check_id").loc["strong_duality"]
    assert row["status"] == "pass" and row["value"] <= 1e-7
    # Z in $ equals the dual objective in $ (excl. Z0, DECISIONS 25)
    z0 = float(c.sv.z0)
    assert abs((c.sv.z_total - z0) - c.sv.z_lp) <= 1e-9 * max(1.0, abs(c.sv.z_total))
    assert stationarity_residual(c.sv) <= 1e-9, "s_j = c_j - sum a_ij y_i must hold in the returned duals"


@pytest.mark.parametrize("name", ALL)
def test_complementary_slackness_and_signs(canon, name):
    c = canon(name)
    cs, viol, gap = cs_and_signs(c.sv)
    assert cs <= 1e-8, f"|y*slack|/max(1,|Z~|) = {cs}"
    assert viol <= 1e-9, f"dual sign violation {viol} (formulation 1.3 / section 3 table)"
    ch = c.health.checks.set_index("check_id")
    assert ch.loc["comp_slack", "status"] == "pass" and ch.loc["dual_sign", "status"] == "pass"


# ================================================================== row 5: zero-profit / revenue identity
@pytest.mark.parametrize("name", ALL)
def test_zero_profit_revenue_identity_storage_reduced_costs(canon, name):
    c = canon(name)
    assert rent_violations(c.sv) == []
    ch = c.health.checks.set_index("check_id")
    for k in ("zero_profit", "revenue_identity", "storage_reduced_costs"):
        assert ch.loc[k, "status"] == "pass", k


def test_zero_profit_rule_detects_wrong_cost():
    """Negative control: the independent rent check flags a candidate whose cost the LP did not use (cost x1.01 in
    the evaluation only)."""
    from healthlib import CASES as CS
    sv, _ = solve_audit(CS / "T1")
    gen = sv.case.gen
    bumped = dataclasses.replace(gen, cfix=gen.cfix * 1.01)
    sv2 = dataclasses.replace(sv, case=dataclasses.replace(sv.case, gen=bumped))
    assert rent_violations(sv2), "interior candidate with R != C must be flagged"


# ================================================================== row 6: dual unscaling
def _compare(a, b, rel, what, abs_=1e-6):
    err = np.abs(np.asarray(a) - np.asarray(b))
    bad = err > np.maximum(abs_, rel * np.abs(b))
    assert not bad.any(), f"{what}: max abs diff {err.max():.3g} at {np.argwhere(bad)[:3].tolist()}"


def _unscaling(name):
    s1, h1 = solve_audit(CASES / name)
    s0, h0 = solve_audit(CASES / name, scaling=Scaling.off())
    return s1, h1, s0, h0


@pytest.mark.parametrize("name", CANON_CASES)
def test_dual_unscaling_primal_and_prices(name):
    """Scaled (k_P=1e-3, k_C=1e-6) vs unscaled (1,1): primal rel 1e-6, economic duals pi, rho, rho^P rel 1e-5."""
    s1, h1, s0, h0 = _unscaling(name)
    assert s1.lp.scaling == Scaling() and s0.lp.scaling == Scaling.off()
    assert close(s1.z_total, s0.z_total, 1e-6)
    for v in ("x", "xP", "xE"):
        _compare(s1.var(v), s0.var(v), 1e-6, f"primal {v}")
    w = s1.case.w
    for v in ("g", "ch", "dis"):                          # annual energy per resource (hourly storage schedule not unique)
        _compare((s1.var(v) * w[None, :, None]).sum(axis=(1, 2)), (s0.var(v) * w[None, :, None]).sum(axis=(1, 2)),
                 1e-6, f"annual energy {v}")
    e1, e0 = h1.audit.economics, h0.audit.economics
    _compare(e1.pi, e0.pi, 1e-5, "pi")
    _compare(e1.rho, e0.rho, 1e-5, "rho")
    _compare(e1.rho_p, e0.rho_p, 1e-5, "rho^P")
    if name != "T2c":      # T2c: x^E = 0, storage duals dual-degenerate (formulation 3 check 7, DECISIONS 31)
        _compare(e1.rho_e, e0.rho_e, 1e-5, "rho^E")
        _compare(e1.v, e0.v, 1e-5, "water value v")
    if name in ("T4",):
        _compare(e1.mu_link, e0.mu_link, 1e-5, "mu")


@pytest.mark.parametrize("scaling", [None, Scaling.off()], ids=["scaled", "unscaled"])
def test_t2c_combined_rent_inside_degenerate_interval(scaling):
    """gate-1 section 2 T2c / formulation 10: x = 0, storage duals dual-degenerate, combined rent R^P + 4 R^E lies in
    [15,465.19, 20,000] (rent <= cost, not <). Interval is the spec's; no slack beyond float noise (1e-6 USD)."""
    sv, h = solve_audit(CASES / "T2c", scaling=scaling)
    assert float(sv.var("xP").max()) <= 1e-6 and float(sv.var("xE").max()) <= 1e-6
    r = h.audit.rents.set_index("resource_id").loc["bat"]
    rp, re_ = float(r["rent_pwr"]), float(r["rent_en"])
    assert rp >= -1e-9 and re_ >= -1e-9
    comb = rp + 4 * re_
    assert 15465.19 - 1e-2 <= comb <= 20000.0 + 1e-6, f"combined rent {comb} outside [15465.19, 20000]"
    assert rent_violations(sv) == []


# ================================================================== row 7: objective decomposition
@pytest.mark.parametrize("name", ALL)
def test_objective_decomposition(canon, name):
    c = canon(name)
    sv, obj = c.sv, c.tables["objective"]
    case, w = sv.case, sv.case.w
    parts = obj[obj["component"] != "total"]
    total = float(obj.loc[obj["component"] == "total", "value_usd_yr"].iloc[0])
    assert abs(parts["value_usd_yr"].sum() - total) <= 1e-9 * max(1.0, abs(total))
    assert abs(total - sv.z_total) <= 1e-9 * max(1.0, abs(sv.z_total))
    # independent recomputation of each component from the primal solution and the case data
    gen, stg = case.gen, case.storage
    x, xp, xe, g, dis, u = sv.var("x"), sv.var("xP"), sv.var("xE"), sv.var("g"), sv.var("dis"), sv.var("use")
    inv = obj[obj["component"] == "Z_inv"].set_index("id")["value_usd_yr"]
    for i, rid in enumerate(gen.ids):
        assert close(inv[rid], gen.cfix[i] * x[i], 1e-9, 1e-6), f"Z_inv {rid}"
    for i, rid in enumerate(stg.ids):
        assert close(inv[rid], stg.cp[i] * xp[i] + stg.ce[i] * xe[i], 1e-9, 1e-6), f"Z_inv {rid}"
    var = obj[obj["component"] == "Z_var"].groupby("id")["value_usd_yr"].sum()
    for i, rid in enumerate(gen.ids):
        assert close(var[rid], float((w[:, None] * gen.mc[i] * g[i]).sum()), 1e-9, 1e-6), f"Z_var {rid}"
    for i, rid in enumerate(stg.ids):
        assert close(var[rid], float((w[:, None] * stg.vom[i] * dis[i]).sum()), 1e-9, 1e-6), f"Z_var {rid}"
    use = obj[obj["component"] == "Z_use"].set_index("id")["value_usd_yr"]
    for i, z in enumerate(case.zones):
        assert close(use[z], float(case.voll * (w[:, None] * u[i]).sum()), 1e-9, 1e-6), f"Z_use {z}"
    assert close(float(obj.loc[obj["component"] == "Z0", "value_usd_yr"].sum()), sv.z0, 1e-9, 1e-6)
    assert c.health.checks.set_index("check_id").loc["decomposition", "status"] == "pass"


# ================================================================== row 8: binding-constraint report
def _binding(c, family):
    b = c.tables["binding"].set_index("family").loc[family]
    return int(b["n_rows"]), int(b["n_binding"]), float(b["weighted_share_binding"])


def _binding_hours(c, label, resource):
    d = c.tables["duals_raw"]
    d = d[(d["label"] == label) & (d["resource"] == resource)]
    return set(int(t) for t in d.loc[d["slack"] <= 1e-6, "t"])


def test_binding_report_t1(canon):
    c = canon("T1")
    assert _binding_hours(c, "gen_max", "base") == set(range(37, 73))      # mid + peak
    assert _binding_hours(c, "gen_max", "peaker") == set(range(61, 73))    # peak only
    n, nb, share = _binding(c, "gen_max")
    assert (n, nb) == (144, 36 + 12) and abs(share - 48 / 144) <= 1e-12     # weights equal within one period
    assert _binding(c, "bal")[:2] == (72, 72)                              # equalities always bind
    assert len(c.tables["binding_bounds"]) == 0, "no x_ub: both builds are interior"
    assert _binding(c, "x_ub")[1] == 0


def test_binding_report_t2(canon):
    a, b, cc = canon("T2a"), canon("T2b"), canon("T2c")
    assert len(a.tables["binding_bounds"]) == 0 and len(cc.tables["binding_bounds"]) == 0
    assert sorted(b.tables["binding_bounds"]["label"]) == ["xE_ub", "xP_ub"]
    assert _binding(b, "xP_ub")[:2] == (1, 1) and _binding(b, "xE_ub")[:2] == (1, 1)
    # fixed 4 h duration: x^E = 4 x^P binds both duration rows (10 MW / 40 MWh)
    assert _binding(b, "st_dur_lo")[:2] == (1, 1) and _binding(b, "st_dur_hi")[:2] == (1, 1)
    assert _binding(cc, "xP_ub")[1] == 0 and _binding(cc, "xE_ub")[1] == 0
    for c in (a, b, cc):
        n, nb, _ = _binding(c, "st_soc")
        assert n == nb == 72, "st_soc is an equality"
    for c in (a, b):   # discharge 36 MWh = 0.9 x 40 MWh uses the full energy rating: SOC reaches E in >= 1 hour
        assert _binding(c, "st_emax")[1] >= 1


def test_binding_report_t3(canon):
    for name in ("T3a", "T3b"):
        c = canon(name)
        assert len(c.tables["binding_bounds"]) == 0, name       # u_48 = 20 < D_48 = 120: use_ub not binding
        assert _binding_hours(c, "gen_max", "g") == {48}, "existing G at 100 MW only in the shortage hour"
    assert _binding_hours(canon("T3b"), "gen_max", "peaker") == {48}, "Peaker output 20 MW = build only in t=48"


def test_binding_report_t4(canon):
    c = canon("T4")
    bb = c.tables["binding_bounds"]
    assert set(bb["label"]) == {"flow_ub"} and len(bb) == 72 and set(bb["link"]) == {"ab"}
    n, nb, share = _binding(c, "flow_ub")
    assert (n, nb) == (72, 72) and abs(share - 1.0) <= 1e-12
    assert _binding(c, "flow_lb")[1] == 0
    assert _binding(c, "gen_max")[1] == 0, "1000 MW units far from capacity"


# ================================================================== row 9: price-setter report
@pytest.mark.parametrize("name", ALL)
def test_price_setter_unexplained_zero_and_checks(canon, name):
    c = canon(name)
    ps = c.tables["price_setter"]
    assert not (ps["primary_class"] == "UNEXPLAINED").any()
    assert not ps["all_classes"].fillna("").str.contains("UNEXPLAINED").any()
    assert price_setter_violations(c.sv, ps) == []
    ch = c.health.checks.set_index("check_id")
    assert float(ch.loc["price_setter.unexplained", "value"]) == 0.0
    assert ch.loc["price_setter.link_inconsistent", "status"] == "pass"
    # price is the LMP of the zone-hour (the table is not an independent source of prices)
    zh = c.tables["zone_hourly"].merge(ps, left_on=["zone", "period", "t"], right_on=["zone", "period_id", "t"])
    assert np.allclose(zh["lmp_usd_mwh"], zh["price"], atol=1e-9)


def test_storage_setter_cost_and_residual_columns_consistent_with_section_4(canon):
    ps = canon("S2").tables["price_setter"]
    row = ps[ps["primary_class"] == "STORAGE_DIS"]
    assert len(row) == 1
    # formulation 4 Outputs / DECISIONS 31(b): STORAGE_DIS setter_cost = VOM + v/eta_d, residual = pi - setter_cost
    c = canon("S2")
    stg = c.sv.case.storage
    r = row.iloc[0]
    wv = c.tables["storage"]
    v = float(wv.loc[wv["t"] == int(r["t"]), "water_value_usd_mwh"].iloc[0])   # independent source of v
    assert abs(float(r["setter_cost"]) - (float(stg.vom[0]) + v / float(stg.eta_d[0]))) <= 1e-6
    assert abs(float(r["residual"]) - (float(r["price"]) - float(r["setter_cost"]))) <= 1e-9
    assert abs(float(r["residual"])) <= max(0.01, 1e-5 * abs(float(r["price"])))
    assert abs(float(r["price"]) - 20.0 / (0.9 * 0.9)) <= 1e-4          # MC/(eta_c eta_d) = 24.691
    ch = ps[ps["all_classes"].fillna("").str.contains("STORAGE_CH")]
    for rr in ch.itertuples():                                           # STORAGE_CH tie: setter_cost = eta_c v
        assert abs(float(rr.price) - 20.0) <= 1e-4


@pytest.mark.parametrize("name", ALL)
def test_price_setter_shares_sum_to_one(canon, name):
    c = canon(name)
    summ = c.tables["price_setter_summary"]
    per_zone = summ.groupby("zone")["share_weighted_hours"].sum()
    assert np.allclose(per_zone.to_numpy(), 1.0, atol=1e-9)
    hours = summ.groupby("zone")["weighted_hours"].sum()
    assert np.allclose(hours.to_numpy(), 8760.0, atol=1e-6), "sum w_p x 72 = H_y = 8760 h (365 days)"
    assert c.health.checks.set_index("check_id").loc["price_setter.shares_sum_to_one", "status"] == "pass"


def test_price_setter_marginal_fuel_shares_known_answers(canon):
    def share(c, zone, rid_class):
        s = c.tables["price_setter_summary"]
        s = s[(s["zone"] == zone) & (s["tech"] == rid_class[0]) & (s["class"] == rid_class[1])]
        return float(s["share_weighted_hours"].sum())
    t1 = canon("T1")
    assert abs(share(t1, "A", ("base", "MARGINAL_UNIT")) - 36 / 72) <= 1e-9        # off-peak
    t2 = canon("T2a")
    assert abs(share(t2, "A", ("g1", "MARGINAL_UNIT")) - 0.5) <= 1e-9 and abs(share(t2, "A", ("g2", "MARGINAL_UNIT")) - 0.5) <= 1e-9
    t3 = canon("T3a")
    s = t3.tables["price_setter_summary"]
    assert abs(float(s.loc[s["class"] == "VOLL", "weighted_hours"].sum()) - W1) <= 1e-9, "one VOLL hour"
    assert abs(share(t3, "A", ("g", "MARGINAL_UNIT")) - 71 / 72) <= 1e-9
    t4 = canon("T4")
    assert abs(share(t4, "A", ("g_a", "MARGINAL_UNIT")) - 1.0) <= 1e-9 and abs(share(t4, "B", ("g_b", "MARGINAL_UNIT")) - 1.0) <= 1e-9


def test_non_basic_solution_rejected(monkeypatch):
    """IPM without crossover returns no basis: run is rejected (formulation 4, gate-1 price-setter row)."""
    monkeypatch.setitem(solver_mod.DEFAULT_HIGHS_OPTIONS, "solver", "ipm")
    monkeypatch.setitem(solver_mod.DEFAULT_HIGHS_OPTIONS, "run_crossover", "off")
    sv, h = solve_audit(CASES / "T1")
    assert not sv.sol.basis_valid, "IPM without crossover must not report a valid basis"
    assert h.status == "fail"
    f = failing(h)
    assert "basis_valid" in f or "price_setter.basis" in f, f


def test_ipm_with_crossover_is_accepted(monkeypatch):
    """DECISIONS 25: if IPM is chosen, crossover is mandatory; with it on the basis is valid and prices are explained."""
    monkeypatch.setitem(solver_mod.DEFAULT_HIGHS_OPTIONS, "solver", "ipm")
    monkeypatch.setitem(solver_mod.DEFAULT_HIGHS_OPTIONS, "run_crossover", "on")
    sv, h = solve_audit(CASES / "T4")
    assert sv.sol.basis_valid     # (crossover_ran is not asserted: HiGHS may need 0 crossover iterations on a vertex IPM solution)
    assert h.status != "fail", non_pass(h)


# ================================================================== row 10: conditioning
SPEC_6_2 = {  # section 6.2 table: metric -> (warn, fail), strict '>'
    "matrix_ratio": (1e6, 1e9), "objective_ratio": (1e8, 1e11), "rhs_ratio": (1e6, 1e9),
    "bound_max": (1e5, 1e7), "primal_infeasibility": (1e-7, 1e-5), "dual_infeasibility": (1e-7, 1e-5),
    "bal_residual_mw": (1e-3, 1e-1),
}


def test_conditioning_thresholds_exactly_section_6_2():
    assert dict(cond.THRESHOLDS) == SPEC_6_2


@pytest.mark.parametrize("metric", list(SPEC_6_2))
def test_conditioning_classification_boundaries(metric):
    warn, fail = SPEC_6_2[metric]
    base = {k: 0.0 for k in SPEC_6_2}
    for value, expected in ((warn * 0.999, "pass"), (warn, "pass"), (warn * 1.001, "warn"),
                            (fail, "warn"), (fail * 1.001, "fail")):
        assert cond.classify({**base, metric: value})[metric] == expected, (metric, value)


@pytest.mark.parametrize("name", ALL)
def test_conditioning_report_every_solve_and_toys_clean(canon, name):
    c = canon(name)
    ch = c.health.checks
    cc = ch[ch["family"] == "conditioning"]
    assert set(cc["check_id"]) == {f"conditioning.{k}" for k in SPEC_6_2}, "one row per section 6.2 metric"
    assert (cc["status"] == "pass").all(), f"T1-T4 must have no warn and no fail:\n{cc}"
    import json
    j = json.loads((c.out_dir / "conditioning.json").read_text())
    for k in ("rows", "cols", "nnz", "matrix_min", "matrix_max", "matrix_ratio", "objective_min", "objective_max",
              "objective_ratio", "rhs_min", "rhs_max", "rhs_ratio", "tiny_coefficients", "primal_infeasibility",
              "dual_infeasibility", "bal_residual_mw", "iterations", "crossover_ran"):
        assert k in j["metrics"], f"conditioning report lacks {k} (section 6.2)"
    assert j["metrics"]["rows"] == c.sv.lp.n_rows and j["metrics"]["cols"] == c.sv.lp.n_cols


def _ratio_fixture(dmax: float) -> Spec:
    """Candidate storage with a huge maximum duration: matrix coefficient dmax next to coefficients of order 1."""
    d = np.r_[np.full(36, 50.0), np.full(36, 150.0)]
    return Spec(["A"], [W1], np.array([[d]]), [
        th("g1", "A", k0=100, mc=20.0), th("g2", "A", k0=200, mc=60.0),
        st("bat", "A", xp=10, xe=40, cp=0.0, ce=3000.0, dmin=4.0, dmax=dmax)])


@pytest.mark.parametrize("dmax,expected", [(2e9, "fail"), (1e7, "warn"), (1e3, "pass")])
def test_conditioning_matrix_ratio_fixture(tmp_path, dmax, expected):
    d = write_case(_ratio_fixture(dmax), tmp_path)
    sv, h = solve_audit(d)
    m = sv.lp.a.data
    ratio = np.abs(m).max() / np.abs(m[m != 0]).min()
    assert (ratio > 1e9) == (expected == "fail") and (1e6 < ratio <= 1e9) == (expected == "warn"), ratio
    row = h.checks.set_index("check_id").loc["conditioning.matrix_ratio"]
    assert row["status"] == expected, (ratio, row.to_dict())
    if expected == "fail":
        assert h.status == "fail", "a conditioning fail must fail the health report"
    elif expected == "warn":
        assert h.status == "warn"
    else:
        assert h.status == "pass"


# ================================================================== W4a gap: storage ties actually occurring
def _interior(x, cap):
    tol_q = max(1e-3, 1e-6 * cap)
    return (x > tol_q) & (x < cap - tol_q)


def test_storage_tie_s1_charge_and_discharge_ties(canon):
    """S1 (designed toy): storage tied with the thermal marginal units. Closed form from the spec stationarity relations."""
    c = canon("S1")
    ps = c.tables["price_setter"].sort_values("t").reset_index(drop=True)
    d = c.tables["dispatch"]
    d = d[d["resource"] == "bat"].sort_values("t")
    ch, dis = d["charge_mw"].to_numpy(float), d["discharge_mw"].to_numpy(float)
    # closed form: SOC 20 MWh needs 20/0.9 = 22.22 MWh charged (P = 20 so >= 2 charge hours, one interior);
    # discharge 20 x 0.9 = 18 MW in t = 72 (energy limited, interior since 18 < P = 20)
    assert abs(ch.sum() - 20 / 0.9) <= 1e-6 and abs(dis.sum() - 18.0) <= 1e-6
    assert abs(dis[71] - 18.0) <= 1e-6 and _interior(dis, 20.0)[71]
    ch_int = np.flatnonzero(_interior(ch, 20.0))
    assert len(ch_int) >= 1, "the toy must produce at least one interior charge hour"
    for i in ch_int:
        assert "STORAGE_CH" in ps.loc[i, "all_classes"] and ps.loc[i, "primary_class"] == "MARGINAL_UNIT"
        assert ps.loc[i, "setter_ids"] == "g1" and abs(ps.loc[i, "price"] - 20.0) <= 1e-4
    assert "STORAGE_DIS" in ps.loc[71, "all_classes"], "tie with the discharging storage in t=72"
    assert ps.loc[71, "primary_class"] == "MARGINAL_UNIT" and ps.loc[71, "setter_ids"] == "g2"
    assert abs(ps.loc[71, "price"] - 60.0) <= 1e-4
    # no spurious storage tag in hours with no interior storage action
    idle = np.flatnonzero(~_interior(ch, 20.0) & ~_interior(dis, 20.0))
    assert not ps.loc[idle, "all_classes"].str.contains("STORAGE").any()
    # water values from the closed forms: v = pi/eta_c = 22.22 (charging), v = eta_d pi = 54 (discharge)
    sto = c.tables["storage"].sort_values("t")
    v = sto["water_value_usd_mwh"].to_numpy(float)
    assert np.abs(v[ch_int] - 20 / 0.9).max() <= 1e-4 and abs(v[71] - 54.0) <= 1e-4
    # objective closed form
    g1 = 71 * 50.0 + 22.2222222222222222 + 100.0
    z = W1 * (20 * g1 + 60 * 32.0)
    assert close(c.sv.z_total, z, 1e-6)


def test_storage_tie_s2_storage_is_the_only_price_setter(canon):
    """S2 (designed toy): in t = 72 G1 is at its cap and the 10 MW shortfall is served by storage alone, so the
    price is set by storage: pi = MC/(eta_c eta_d) = 24.691 and the primary class is STORAGE_DIS."""
    c = canon("S2")
    ps = c.tables["price_setter"].sort_values("t").reset_index(drop=True)
    d = c.tables["dispatch"]
    dd = d[d["resource"] == "bat"].sort_values("t")
    ch, dis = dd["charge_mw"].to_numpy(float), dd["discharge_mw"].to_numpy(float)
    assert abs(dis[71] - 10.0) <= 1e-6 and abs(dis.sum() - 10.0) <= 1e-6
    assert abs(ch.sum() - 10 / (0.9 * 0.9)) <= 1e-6, "charged energy = d/(eta_d eta_c)"
    g1 = d[d["resource"] == "g1"].sort_values("t")["g_mw"].to_numpy(float)
    assert abs(g1[71] - 100.0) <= 1e-6, "G1 at cap in t=72"
    pi72 = 20.0 / (0.9 * 0.9)
    assert abs(ps.loc[71, "price"] - pi72) <= 1e-4
    assert ps.loc[71, "primary_class"] == "STORAGE_DIS" and ps.loc[71, "setter_ids"] == "bat"
    assert abs(ps.loc[71, "price"] - ps.loc[71, "setter_cost"] - ps.loc[71, "residual"]) <= 1e-9
    assert ps.loc[71, "primary_class"] != "UNEXPLAINED"
    ch_int = np.flatnonzero(_interior(ch, 20.0))
    assert len(ch_int) >= 1
    for i in ch_int:
        assert ps.loc[i, "primary_class"] == "MARGINAL_UNIT" and "STORAGE_CH" in ps.loc[i, "all_classes"]
        assert abs(ps.loc[i, "price"] - 20.0) <= 1e-4
    assert abs(c.tables["storage"].sort_values("t")["water_value_usd_mwh"].to_numpy(float)[71] - 20 / 0.9) <= 1e-4
    # objective: G1 serves D + c - d
    z = W1 * 20.0 * (71 * 50.0 + 110.0 + 10 / 0.81 - 10.0)
    assert close(c.sv.z_total, z, 1e-6)
    # storage rent: R^P = sum w (pi - ...) check via revenue identity already in rent_violations
    assert rent_violations(c.sv) == []


@pytest.mark.parametrize("name", ["S1", "S2", "S2asym", "T2asym"] + ["T2a", "T2b"])
def test_storage_soc_consistency_recomputed_from_case_data(canon, name):
    """Model-health: SOC dynamics e_t = (1-sigma) e_t- + eta_c c - d/eta_d recomputed with the CASE's efficiencies."""
    c = canon(name)
    assert soc_residual(c.sv) <= 1e-6
    assert float(c.tables["storage_closure"]["closure_residual_mwh"].abs().max()) <= 1e-6


# ================================================================== check 8: storage.soc_recompute (formulation 3 check 8)
def _soc_row(h):
    ck = h.checks.set_index("check_id")
    assert "storage.soc_recompute" in ck.index, "check must be produced on every solve with storage"
    return ck.loc["storage.soc_recompute"]


@pytest.mark.parametrize("name", ["S1", "S2", "S2asym", "T2asym", "T2a", "T2b"])
def test_soc_recompute_check_passes_on_correct_storage_solves(canon, name):
    c = canon(name)
    row = _soc_row(c.health)
    assert row["status"] == "pass"
    assert float(row["value"]) <= 1e-6 and float(row["tolerance"]) <= 1e-6
    assert soc_residual(c.sv) <= 1e-6                      # verifier-side recomputation agrees


def test_soc_recompute_check_absent_or_trivial_without_storage(canon):
    ck = canon("T1").health.checks.set_index("check_id")
    if "storage.soc_recompute" in ck.index:
        assert ck.loc["storage.soc_recompute", "status"] == "pass"


def _swap_eta_build(case, scaling, orig):
    lp = orig(case, scaling) if scaling is not None else orig(case)
    a = lp.a.tolil()
    stg, rb, ch, dis = case.storage, lp.rows["st_soc"], lp.cols["ch"], lp.cols["dis"]
    for s_ in range(len(stg.ids)):
        for p in range(len(case.periods)):
            for t in range(72):
                r = rb.idx(s_, p, t)
                a[r, ch.idx(s_, p, t)] = -stg.eta_d[s_]
                a[r, dis.idx(s_, p, t)] = 1.0 / stg.eta_c[s_]
    return dataclasses.replace(lp, a=a.tocsr())


def _sigma_build(case, scaling, orig):
    """Drop the self-discharge term sigma from the cyclic SOC link (coefficient on e_{t-} becomes -1)."""
    lp = orig(case, scaling) if scaling is not None else orig(case)
    a = lp.a.tolil()
    rb, soc = lp.rows["st_soc"], lp.cols["soc"]
    for s_ in range(len(case.storage.ids)):
        for p in range(len(case.periods)):
            for t in range(72):
                a[rb.idx(s_, p, t), soc.idx(s_, p, (t - 1) % 72)] = -1.0
    return dataclasses.replace(lp, a=a.tocsr())


@pytest.mark.parametrize("toy", ["S2asym", "T2asym"])
def test_soc_recompute_check_fails_when_eta_swapped_in_lp(monkeypatch, toy, tmp_path):
    """Audit mutation M4 (eta_c <-> eta_d in st_soc, eta_c != eta_d): the check named in gate-1 section 3 must fail."""
    case_dir = write_case(toy_spec(toy), tmp_path, case_id=toy)
    ctrl_sv, ctrl_h = solve_audit(case_dir)
    assert _soc_row(ctrl_h)["status"] == "pass"
    import capex.run as run_mod
    real = run_mod.build_lp
    monkeypatch.setattr(run_mod, "build_lp", lambda case, scaling=None: _swap_eta_build(case, scaling, real))
    sv, h = solve_audit(case_dir)
    assert soc_residual(sv) > 1e-3, "vacuity guard: mutation must break the case-data SOC dynamics"
    row = _soc_row(h)
    assert row["status"] == "fail" and float(row["value"]) > 1e-3
    assert h.status == "fail"


def test_soc_recompute_check_fails_when_sigma_ignored_in_lp(monkeypatch, tmp_path):
    """A wrong self-discharge coefficient in st_soc (case sigma = 0.02 > 0) must also be caught by the case-data recompute."""
    spec = toy_spec("S2asym")
    spec.resources[-1] = st("bat", "A", p0=20, e0=40, eta_c=0.95, eta_d=0.80, sigma=0.02)
    case_dir = write_case(spec, tmp_path, case_id="S2sig")
    sv0, h0 = solve_audit(case_dir)
    assert float(sv0.case.storage.sigma.max()) == pytest.approx(0.02)
    assert _soc_row(h0)["status"] == "pass" and soc_residual(sv0) <= 1e-6
    import capex.run as run_mod
    real = run_mod.build_lp
    monkeypatch.setattr(run_mod, "build_lp", lambda case, scaling=None: _sigma_build(case, scaling, real))
    sv, h = solve_audit(case_dir)
    assert soc_residual(sv) > 1e-3, "vacuity guard"
    assert _soc_row(h)["status"] == "fail"


# ================================================================== helper unit test: cs_and_signs on infinite sides
def test_cs_and_signs_noise_dual_on_infinite_side_is_sign_violation_not_inf_cs():
    """Formulation 1.3: CS is defined only against a finite side. A tiny dual on an infinite side (solver noise) is a
    sign violation (reported in `viol`), never |y| * inf = inf in the CS term. Thresholds are untouched."""
    from types import SimpleNamespace as NS
    inf = np.inf
    # 2 rows: row0 is <= only (rlo=-inf), row1 is >= only (rhi=+inf); 2 cols: col0 has no lower, col1 no upper bound.
    lp = NS(a=sp.csr_matrix(np.eye(2)), c=np.zeros(2), row_lo=np.array([-inf, 1.0]), row_hi=np.array([5.0, inf]),
            col_lo=np.array([-inf, 0.0]), col_hi=np.array([10.0, inf]))
    sol = NS(x=np.array([1.0, 1.0]), row_dual=np.array([1e-16, -1e-16]), col_dual=np.array([1e-16, -1e-16]),
             row_activity=np.array([1.0, 1.0]))
    cs, viol, gap = cs_and_signs(NS(lp=lp, sol=sol))
    assert np.isfinite(cs) and cs <= 1e-8
    assert 0.0 < viol <= 1e-9
    # a genuine sign violation of size 1e-3 on an infinite side must still be reported in viol
    sol.row_dual = np.array([1e-3, 0.0])
    assert cs_and_signs(NS(lp=lp, sol=sol))[1] >= 1e-3 - 1e-15
