"""Verifier tests: gate-1.md section 3 audit-mutation tests ("a fault that no check catches is a gate failure").

Six faults are injected by monkeypatching the production pipeline (capex.run.build_lp or the HiGHS adapter) while the
case data and the audit layer stay untouched; each must make at least one health check FAIL. Every test also runs a
control (no fault, same case) that must pass, and a vacuity guard showing that the fault really changed the LP / duals.
A mutation that no check catches is left as a plain FAILING test (it is a gate finding, not a skip).

  M1 flip a dual sign in the adapter          M4 swap eta_c / eta_d in st_soc
  M2 drop one `bal` row                       M5 wrong weight on one period
  M3 scale one cost by 1.001                  M6 IPM solution without crossover
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import capex.run as run_mod
import capex.solver as solver_mod
from capex.data import DataError
from capex.solver import HighsSolver
from healthlib import CASES, W1, failing, non_pass, soc_residual, solve_audit, toy_spec, write_case

_ORIG_BUILD = run_mod.build_lp
_ORIG_SOLVE = HighsSolver.solve


def _control(case_dir):
    sv, h = solve_audit(case_dir)
    assert h.status == "pass", f"control run must be clean:\n{non_pass(h)}"
    return sv


def _caught(h, expect_any=None):
    f = failing(h)
    assert h.status == "fail" and f, f"fault NOT caught by any health check (status {h.status})"
    if expect_any is not None:
        assert set(f) & set(expect_any), f"caught only by {f}, expected one of {expect_any}"
    return f


def _patch_build(monkeypatch, fn):
    monkeypatch.setattr(run_mod, "build_lp", lambda case, scaling=None: fn(case, scaling, _ORIG_BUILD))


# ---------------------------------------------------------------- M1: dual sign flipped in the adapter
@pytest.mark.parametrize("family,expect", [
    ("gen_max", {"dual_sign", "zero_profit", "revenue_identity"}),       # a <= row given a positive dual
    ("bal", {"strong_duality", "revenue_identity", "price_setter.unexplained"}),   # free row, wrong sign
])
def test_m1_flip_one_dual_sign_in_adapter(monkeypatch, family, expect):
    _control(CASES / "T1")

    def bad_solve(self, lp):
        sol = _ORIG_SOLVE(self, lp)
        y = sol.row_dual.copy()
        b = lp.rows[family]
        i = b.offset + int(np.argmax(np.abs(y[b.offset:b.offset + b.size])))
        assert y[i] != 0.0, "vacuity guard: the flipped dual must be nonzero"
        y[i] = -y[i]
        return dataclasses.replace(sol, row_dual=y)
    monkeypatch.setattr(HighsSolver, "solve", bad_solve)
    _, h = solve_audit(CASES / "T1")
    _caught(h, expect)


def test_m1_flip_column_dual_sign_in_adapter(monkeypatch):
    def bad_solve(self, lp):
        sol = _ORIG_SOLVE(self, lp)
        s = sol.col_dual.copy()
        i = int(np.argmax(np.abs(s)))
        assert s[i] != 0.0
        s[i] = -s[i]
        return dataclasses.replace(sol, col_dual=s)
    monkeypatch.setattr(HighsSolver, "solve", bad_solve)
    _, h = solve_audit(CASES / "T4")            # flow_ub column dual is the largest
    _caught(h)


# ---------------------------------------------------------------- M2: one balance row dropped
@pytest.mark.parametrize("name,hour", [("T1", 72), ("T4", 10)])
def test_m2_drop_one_bal_row(monkeypatch, name, hour):
    _control(CASES / name)

    def build(case, scaling, orig):
        lp = orig(case, scaling) if scaling is not None else orig(case)
        lo, hi = lp.row_lo.copy(), lp.row_hi.copy()
        i = lp.rows["bal"].idx(0, 0, hour - 1)
        lo[i], hi[i] = -np.inf, np.inf                    # row removed from the feasible set (layout kept)
        return dataclasses.replace(lp, row_lo=lo, row_hi=hi)
    _patch_build(monkeypatch, build)
    sv, h = solve_audit(CASES / name)
    _caught(h, {"balance", "conditioning.bal_residual_mw"})


# ---------------------------------------------------------------- M3: one cost scaled by 1.001
@pytest.mark.parametrize("target", ["mc_base_all_hours", "single_column_g", "cfix_base"])
def test_m3_scale_one_cost_by_1_001(monkeypatch, target):
    ctrl = _control(CASES / "T1")

    def build(case, scaling, orig):
        lp = orig(case, scaling) if scaling is not None else orig(case)
        c = lp.c.copy()
        if target == "mc_base_all_hours":
            c[lp.cols["g"].idx(0, 0, np.arange(72))] *= 1.001
        elif target == "single_column_g":
            c[lp.cols["g"].idx(0, 0, 40)] *= 1.001
        else:
            c[lp.cols["x"].idx(0)] *= 1.001
        return dataclasses.replace(lp, c=c)
    _patch_build(monkeypatch, build)
    sv, h = solve_audit(CASES / "T1")
    assert abs(sv.z_total - ctrl.z_total) > 0, "vacuity guard: objective must move"
    _caught(h, {"decomposition", "revenue_identity", "zero_profit", "price_setter.unexplained"})


# ---------------------------------------------------------------- M4: eta_c / eta_d swapped in st_soc
def _swap_eta(case, scaling, orig):
    lp = orig(case, scaling) if scaling is not None else orig(case)
    a = lp.a.tolil()
    stg, rb, ch, dis = case.storage, lp.rows["st_soc"], lp.cols["ch"], lp.cols["dis"]
    for s in range(len(stg.ids)):
        for p in range(len(case.periods)):
            for t in range(72):
                r = rb.idx(s, p, t)
                a[r, ch.idx(s, p, t)] = -stg.eta_d[s]          # was -eta_c
                a[r, dis.idx(s, p, t)] = 1.0 / stg.eta_c[s]    # was 1/eta_d
    return dataclasses.replace(lp, a=a.tocsr())


@pytest.mark.parametrize("toy", ["S2asym", "T2asym"])
def test_m4_swap_eta_in_st_soc_audit_layer_catches(monkeypatch, toy, tmp_path):
    """The audit layer's health checks must catch the swap. eta_c = .95 / eta_d = .80 so that the swap is not a no-op
    (with eta_c = eta_d, as in T2, it is invisible by construction)."""
    case_dir = write_case(toy_spec(toy), tmp_path, case_id=toy)
    ctrl = _control(case_dir)
    assert soc_residual(ctrl) <= 1e-6
    _patch_build(monkeypatch, _swap_eta)
    sv, h = solve_audit(case_dir)
    # vacuity guard: the SOC rows in the LP no longer match the case's efficiencies
    assert soc_residual(sv) > 1e-3, "mutation must break the SOC dynamics of the case data"
    _caught(h)


@pytest.mark.parametrize("toy", ["S2asym", "T2asym"])
def test_m4_independent_soc_recomputation_would_catch(monkeypatch, toy, tmp_path):
    """Reference check (verifier-side): recomputing e_t - (1-sigma)e_t- - eta_c c + d/eta_d from the case data flags the
    swap on both toys. This is the check the audit layer is missing if test_m4_swap... fails for T2asym."""
    case_dir = write_case(toy_spec(toy), tmp_path, case_id=toy)
    _patch_build(monkeypatch, _swap_eta)
    sv, _ = solve_audit(case_dir)
    assert soc_residual(sv) > 1e-3


# ---------------------------------------------------------------- M5: wrong weight on one period
def test_m5_wrong_weight_on_one_period_in_model(monkeypatch, tmp_path):
    case_dir = write_case(toy_spec("P2"), tmp_path, case_id="P2")
    ctrl = _control(case_dir)

    def build(case, scaling, orig):
        lp = orig(case, scaling) if scaling is not None else orig(case)
        c = lp.c.copy()
        for name in ("g", "use", "dis"):                   # w_2 -> 1.5 w_2 in the objective only
            b = lp.cols[name]
            if b.size:
                c[b.idx(np.arange(b.shape[0])[:, None], np.array([[1]]), np.arange(72)[None, :])] *= 1.5
        return dataclasses.replace(lp, c=c)
    _patch_build(monkeypatch, build)
    sv, h = solve_audit(case_dir)
    assert abs(sv.z_total - ctrl.z_total) > 1.0
    _caught(h, {"decomposition", "revenue_identity", "price_setter.unexplained", "zero_profit"})


def _periods_edit(case_dir, w):
    import pandas as pd
    p = case_dir / "periods.csv"
    df = pd.read_csv(p)
    df["weight_blocks"] = w
    df["days_represented"] = 3 * np.asarray(w)
    df.to_csv(p, index=False, float_format="%.17g")


@pytest.mark.parametrize("w", [[80.0 + 1.0, W1 - 80.0], [0.5, W1 - 0.5]], ids=["sum_off_by_one", "weight_below_one"])
def test_m5_wrong_weight_in_input_rejected_at_load(tmp_path, w):
    """A wrong period weight in the input (sum != D_y/3 or w < 1) is rejected by load validation (DataError)."""
    case_dir = write_case(toy_spec("P2"), tmp_path, case_id="P2")
    _periods_edit(case_dir, w)
    with pytest.raises(DataError):
        solve_audit(case_dir)


# ---------------------------------------------------------------- M6: IPM without crossover
def test_m6_ipm_without_crossover_solution(monkeypatch):
    _control(CASES / "T1")
    monkeypatch.setitem(solver_mod.DEFAULT_HIGHS_OPTIONS, "solver", "ipm")
    monkeypatch.setitem(solver_mod.DEFAULT_HIGHS_OPTIONS, "run_crossover", "off")
    sv, h = solve_audit(CASES / "T1")
    assert not sv.sol.basis_valid
    _caught(h, {"basis_valid", "price_setter.basis"})
