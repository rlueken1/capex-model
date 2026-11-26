"""Verifier tests: gate-1.md section 2 "50 randomized small instances" and section 3 row for random instances.

50 fixed-seed instances (1-3 zones, 1-3 periods, mixed thermal / VRE / storage / links; tests/healthlib.random_spec)
must (a) pass every health check, (b) pass the independently recomputed checks (balance, complementary slackness,
strong duality, rents, SOC dynamics, price-setter rules, decomposition), and (c) match a second solve through an
independent route (scipy.optimize.linprog(method="highs") on an LP built in healthlib.linprog_z straight from
formulation 2.1-2.3) at rel 1e-7.
"""
from __future__ import annotations

import numpy as np
import pytest

from capex.audit.report import health_report
from capex.config import Scaling
from capex.data import load_case
from capex.run import output_tables, solve_case
from healthlib import (cs_and_signs, independent_balance, linprog_z, non_pass, price_setter_violations,
                       random_spec, rent_violations, soc_residual, solve_audit, stationarity_residual, th,
                       write_case, Spec, W1)

SEEDS = list(range(50))


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    cache = {}

    def get(seed):
        if seed not in cache:
            spec = random_spec(seed)
            d = write_case(spec, tmp_path_factory.mktemp(f"rnd{seed}"), case_id=f"rnd{seed}")
            sv, h = solve_audit(d)
            cache[seed] = (spec, d, sv, h)
        return cache[seed]
    return get


def test_random_instances_cover_the_requested_mix(solved):
    zones = {len(solved(s)[0].zones) for s in SEEDS}
    periods = {len(solved(s)[0].weights) for s in SEEDS}
    assert zones == {1, 2, 3} and periods == {1, 2, 3}
    kinds = {r["type"] for s in SEEDS for r in solved(s)[0].resources}
    assert kinds == {"TH", "VRE", "ST"}
    assert any(solved(s)[0].links for s in SEEDS)
    assert any(r["type"] == "ST" and r["status"] == "candidate" for s in SEEDS for r in solved(s)[0].resources)
    assert any(r["type"] == "ST" and r["status"] == "existing" for s in SEEDS for r in solved(s)[0].resources)


@pytest.mark.parametrize("seed", SEEDS)
def test_random_instance_passes_every_health_check(solved, seed):
    spec, d, sv, h = solved(seed)
    assert h.status == "pass", f"seed {seed}:\n{non_pass(h)}"
    ch = h.checks.set_index("check_id")
    assert float(ch.loc["price_setter.unexplained", "value"]) == 0.0
    assert len(h.checks[h.checks["family"] == "conditioning"]) == 7
    ps = h.audit.price_setter
    assert ps is not None and (ps.summary.groupby("zone")["share_weighted_hours"].sum().sub(1.0).abs() <= 1e-9).all()
    t = output_tables(sv, h)
    assert price_setter_violations(sv, t["price_setter"]) == []


@pytest.mark.parametrize("seed", SEEDS)
def test_random_instance_independent_recomputation(solved, seed):
    spec, d, sv, h = solved(seed)
    t = output_tables(sv, h)
    assert independent_balance(d, t) <= 1e-6
    cs, viol, gap = cs_and_signs(sv)
    assert gap <= 1e-7 and cs <= 1e-8 and viol <= 1e-9, (gap, cs, viol)
    assert stationarity_residual(sv) <= 1e-9
    assert rent_violations(sv) == [], f"seed {seed}"
    assert soc_residual(sv) <= 1e-6
    obj = t["objective"]
    parts = obj[obj["component"] != "total"]["value_usd_yr"].sum()
    assert abs(parts - sv.z_total) <= 1e-9 * max(1.0, abs(sv.z_total))


@pytest.mark.parametrize("seed", SEEDS)
def test_random_instance_matches_independent_linprog(solved, seed):
    spec, d, sv, h = solved(seed)
    z_ref = linprog_z(spec)
    assert abs(sv.z_total - z_ref) <= 1e-7 * abs(z_ref), f"seed {seed}: model {sv.z_total!r} vs linprog {z_ref!r}"


@pytest.mark.parametrize("seed", SEEDS[:20])
def test_random_instance_unscaled_solve_agrees(solved, seed):
    """Dual unscaling on random instances: primal objective rel 1e-6, energy prices pi and generator rents rho rel 1e-5.
    Storage duals (v, rho^P, rho^E) are excluded: they are dual-degenerate whenever a storage idles or sits at a bound
    (formulation 3 check 7; T2c in test_health_checks.py)."""
    spec, d, sv, h = solved(seed)
    sv0, h0 = solve_audit(d, scaling=Scaling.off())
    assert abs(sv.z_total - sv0.z_total) <= 1e-6 * abs(sv.z_total)
    e, e0 = h.audit.economics, h0.audit.economics
    assert np.all(np.abs(e.pi - e0.pi) <= np.maximum(1e-6, 1e-5 * np.abs(e0.pi))), "pi differs between scalings"
    assert np.all(np.abs(e.rho - e0.rho) <= np.maximum(1e-6, 1e-5 * np.abs(e0.rho))), "rho differs between scalings"


def test_vre_without_mc_override_or_fuel_column_loads(tmp_path):
    prof = np.full((1, 72), 0.5)
    spec = Spec(["A"], [W1], np.full((1, 1, 72), 60.0),
                [th("g", "A", k0=100, mc=20.0), th("w", "A", k0=50, kind="VRE", mc=None, avail=prof)])
    case = load_case(write_case(spec, tmp_path))
    assert float(case.gen.mc[1].max()) == 0.0
