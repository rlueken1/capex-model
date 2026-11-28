"""Verifier tests for G4-7-fix1b (finding F4-1, DECISIONS 60(a); formulation 7.4a.7, F-0.4 amendment 1, health row
`price_setter.loop_alpha`). Written from the spec, not from the audit code.

Rule under test: a `TIE_AT_BOUND` unit (at a bound, |MC - pi| <= tol_pi = max(0.01, 1e-5|pi|)) joins the CONGESTION_LOOP marginal
set only at an exact tie |pi_m - c_m| <= 1e-7. Otherwise it keeps its bus-local class and is NOT among the CONGESTION_LOOP
`setter_ids` / `price_setter_loop` rows; its reduced cost is nonzero, so it would make Phi z = c inconsistent.

Fixture: pjm5 (dcpf angle, F-0.4), flat 72 h load, line `de` congested in every hour. `sundance` (bus D, Pmax 200, mc 40) sits at 0 MW
at the bound with pi_D = 39.94273632... in the first solve. Re-solving with sundance mc = pi_D + delta leaves the dispatch and the
duals unchanged (sundance stays off, its reduced cost is delta), which the tests assert as a precondition (not vacuous):
  * delta = 0.005  : inside tol_pi (so sundance IS a local TIE_AT_BOUND at D), outside 1e-7 -> excluded from the loop set.
  * delta = 1e-9   : exact tie -> still eligible (control)."""
from __future__ import annotations

import os

import numpy as np
import pytest
import yaml

import g4lib
from g4lib import T, check_row, g4run, make_fixture  # noqa: F401  (g4run is a fixture)

FULL = os.environ.get("CAPEX_GATE4_FULL") == "1"
needs_full = pytest.mark.skipif(not FULL, reason="Gate 4: R4-NX window run is outside the normal suite (gate-4.md section 2; "
                                                  "set CAPEX_GATE4_FULL=1 to run it)")
UNIT, BUS = "sundance", "D"


def _pi_d(t, hour=1):
    z = t["zone_hourly"]
    return float(z[(z["zone"] == BUS) & (z["t"] == hour)]["lmp_usd_mwh"].iloc[0])


def _g(t, hour=1):
    d = t["dispatch"]
    return float(d[(d["resource"] == UNIT) & (d["t"] == hour)]["g_mw"].iloc[0])


def _builder(mc):
    def edit(rs):
        rs.loc[rs["resource_id"] == UNIT, "mc_override_usd_mwh"] = mc
        return rs
    return lambda tmp: make_fixture(tmp, gen_edit=edit)


@pytest.fixture(scope="module")
def base_pi(tmp_path_factory):
    """pi at bus D from the unmodified pjm5 solve (mc of sundance = 40)."""
    from capex.run import output_tables, run_case
    cd = make_fixture(tmp_path_factory.mktemp("f1b_base"))
    sv, h, _ = run_case(cd, tmp_path_factory.mktemp("f1b_base_out"))
    t = output_tables(sv, h)
    assert _g(t) == 0.0
    return t, _pi_d(t)


@pytest.fixture(scope="module")
def near(g4run, base_pi):
    """sundance mc = pi_D + 0.005 (0.005 inside tol_pi = 0.01, far outside the 1e-7 tie)."""
    t0, pi = base_pi
    return pi, g4run("f1b_near", _builder(pi + 0.005))


@pytest.fixture(scope="module")
def tie(g4run, base_pi):
    t0, pi = base_pi
    return pi, g4run("f1b_tie", _builder(pi + 1e-9))


def _loop_rows(t, hour):
    ps = t["price_setter"]
    return ps[(ps["t"] == hour) & (ps["primary_class"] == "CONGESTION_LOOP")]


def _in_ids(ids, unit):
    return unit in str(ids).split(",")


# ------------------------------------------------------------------------------------------------------ the fixture is real
def test_precondition_unit_at_bound_priced_0p005_below_mc_in_congested_hours(near):
    """Non vacuous: the unit is at Pmin = 0 in every hour, mc - pi_D = 0.005 (1e-6), the hour is congested (line `de` carries a
    nonzero rent), and the unit is a bus-local TIE_AT_BOUND candidate at D (|mc - pi| <= tol_pi) but not interior."""
    pi, r = near
    t = r.t
    for hour in (1, 36, T):
        assert _g(t, hour) == 0.0                                                    # at the lower bound
        assert (_pi_d(t, hour) + 0.005) - _pi_d(t, hour) == pytest.approx(0.005, abs=1e-12)
    fl = t["flows"]
    assert (fl[fl["t"] == 1]["congestion_rent_usd_mwh"].abs() > 1e-3).any()          # congested
    # mc actually read by the model: unit mc is the override, = pi_D + 0.005 (reduced cost of the unit's column is 0.005)
    mc = float(__import__("pandas").read_csv(r.cd / "resources.csv").set_index("resource_id").loc[UNIT, "mc_override_usd_mwh"])
    assert mc - _pi_d(t, 1) == pytest.approx(0.005, abs=1e-6)
    ps = t["price_setter"]
    d1 = ps[(ps["zone"] == BUS) & (ps["t"] == 1)].iloc[0]
    assert "TIE_AT_BOUND" in str(d1["all_classes"]) and d1["primary_class"] == "TIE_AT_BOUND"      # bus-local class kept
    assert _in_ids(d1["setter_ids"], UNIT)


def test_precondition_dispatch_and_prices_unchanged_vs_base(near, base_pi):
    """Changing only sundance's mc (staying off) must not change dispatch or any LMP: the bound status is unchanged."""
    t0, pi0 = base_pi
    pi, r = near
    assert pi == pi0
    for u in ("alta", "park_city", "solitude", "sundance", "brighton"):
        a = t0["dispatch"].query("resource == @u").sort_values("t")["g_mw"].to_numpy()
        b = r.t["dispatch"].query("resource == @u").sort_values("t")["g_mw"].to_numpy()
        assert np.allclose(a, b, atol=1e-6), u
    a = t0["zone_hourly"].sort_values(["zone", "t"])["lmp_usd_mwh"].to_numpy()
    b = r.t["zone_hourly"].sort_values(["zone", "t"])["lmp_usd_mwh"].to_numpy()
    assert np.allclose(a, b, atol=1e-6)


# ------------------------------------------------------------------------------------------------------ the rule
def test_loop_alpha_passes_with_near_tie_unit_at_bound(near):
    pi, r = near
    row = check_row(r.h, "price_setter.loop_alpha")
    assert len(row) == 1 and row["status"].iloc[0] == "pass", row.to_dict("records")
    assert float(row["value"].iloc[0]) <= 1e-6
    assert g4lib.non_pass(r.h).empty, g4lib.non_pass(r.h)[["check_id", "status", "value"]]


def test_near_tie_unit_not_in_any_congestion_loop_setter_ids(near):
    pi, r = near
    t = r.t
    for hour in range(1, T + 1):
        loop = _loop_rows(t, hour)
        assert len(loop) >= 1, f"hour {hour}: expected CONGESTION_LOOP rows (congested island)"
        assert not loop["setter_ids"].map(lambda s: _in_ids(s, UNIT)).any(), (hour, loop[["zone", "setter_ids"]])
    assert UNIT not in set(t["price_setter_loop"]["resource_id"])                    # nor in the weights table
    assert t["price_setter_loop"]["alpha"].notna().all()


def test_loop_weights_sum_to_one_and_reproduce_price_without_near_tie_unit(near):
    """alpha rows over {solitude, brighton} only: sum alpha = 1 and pi_n = sum alpha c to 1e-6, per bus-hour."""
    pi, r = near
    lp, z = r.t["price_setter_loop"], r.t["zone_hourly"]
    pr = z.set_index(["zone", "t"])["lmp_usd_mwh"]
    for (zone, hour), g in lp.groupby(["zone", "t"]):
        assert g["alpha"].sum() == pytest.approx(1.0, abs=1e-6)
        assert (g["alpha"] * g["cost_usd_mwh"]).sum() == pytest.approx(pr[(zone, hour)], abs=1e-6)


def test_control_exact_tie_unit_at_bound_is_still_eligible(tie):
    """|pi - mc| = 1e-9 <= 1e-7 at the bound: the unit joins the loop set (appears in CONGESTION_LOOP setter_ids and weights) and
    the identities still hold (loop_alpha passes)."""
    pi, r = tie
    t = r.t
    assert _g(t) == 0.0                                                              # at bound (precondition)
    assert abs(_pi_d(t) - (pi + 1e-9)) <= 1e-7
    loop = _loop_rows(t, 1)
    assert loop["setter_ids"].map(lambda s: _in_ids(s, UNIT)).any(), loop[["zone", "setter_ids"]]
    assert UNIT in set(t["price_setter_loop"]["resource_id"])
    row = check_row(r.h, "price_setter.loop_alpha")
    assert row["status"].iloc[0] == "pass" and float(row["value"].iloc[0]) <= 1e-6
    g = t["price_setter_loop"].query("t == 1 and zone == 'A'")
    assert g["alpha"].sum() == pytest.approx(1.0, abs=1e-6)


def test_sensitivity_widening_tie_to_tol_pi_breaks_loop_alpha(base_pi, tmp_path, monkeypatch):
    """Guard against a vacuous fixture: with the pre-fix behaviour (tie band = tol_pi = 0.01) the same near-tie fixture must FAIL
    `loop_alpha`. This is what the rule exists to prevent (F4-1)."""
    import capex.audit.loop as loop
    from capex.run import run_case
    t0, pi = base_pi
    monkeypatch.setattr(loop, "TIE_EPS", 0.01)
    cd = _builder(pi + 0.005)(tmp_path)
    sv, h, _ = run_case(cd, tmp_path / "out")
    row = check_row(h, "price_setter.loop_alpha")
    assert row["status"].iloc[0] == "fail", "fixture does not exercise the F4-1 rule (pre-fix band would also pass)"


# ------------------------------------------------------------------------------------------------------ R4-NX window
@needs_full
def test_r4_nx_window_all_health_checks_pass(tmp_path_factory):
    """R4-NX = nodal RTS-GMLC window (rts_compare.RUN_PERIODS, p063-p067) with tx.dc_links: exclude (gate-4.md section 2). F4-1: the
    unit `321_cc_1` at 0 MW with c - pi = 3.6e-3 failed loop_alpha at 2.4e-3. All health checks must pass, loop_alpha <= 1e-6."""
    import rts_compare as rc
    from capex.run import output_tables, run_case
    win = rc.make_window_case("rts_gmlc_nodal_px", tmp_path_factory.mktemp("r4nx"))
    cfg = yaml.safe_load((win / "case.yaml").read_text())
    cfg["switches"] = {"tx.model": "dcpf", "tx.dcpf_form": "angle", "tx.dc_links": "exclude"}
    (win / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    sv, h, _ = run_case(win, tmp_path_factory.mktemp("r4nx_out"))
    t = output_tables(sv, h)
    bad = g4lib.non_pass(h)
    assert bad.empty, bad[["check_id", "status", "value"]].to_string()
    la = check_row(h, "price_setter.loop_alpha")
    assert la["status"].iloc[0] == "pass" and float(la["value"].iloc[0]) <= 1e-6
    assert not check_row(h, "price_setter.loop_interval").empty
    assert (t["price_setter"]["primary_class"] != "UNEXPLAINED").all()
