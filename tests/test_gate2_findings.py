"""Verifier tests for the Gate 2 carried findings F3, F4, F5, P1-a (docs/gates/gate-2.md section 4).

Written from the spec only: docs/gates/gate-2.md section 4, docs/formulation.md (1.3 dual convention, 2.x gen_max row
`g - A x <= A K0`, 3 check 5 zero-profit / storage reduced costs, 6.1b), docs/data-schema.md (case layout).
"""
from __future__ import annotations

import dataclasses
import hashlib
import subprocess

import numpy as np
import pytest
import scipy.sparse as sp

import capex.audit.fingerprint as fpmod
import capex.run as run_mod
from capex.config import Scaling
from capex.data import load_case
from capex.model import LP, build_lp
from capex.solver import HighsSolver, ScipyHighsSolver
from healthlib import T, W1, Spec, failing, flat_demand, non_pass, solve_audit, st, th, write_case


# ------------------------------------------------------------------ F3: no explicit zeros in the constraint matrix
def _vre_spec(avail_row):
    """Backstop thermal + candidate VRE with the given 72-hour availability profile (single period)."""
    return Spec(["A"], [W1], flat_demand({"A": [50.0] * T}),
                [th("g1", "A", k0=100, mc=60.0),
                 th("wind", "A", xmax=np.inf, mc=0.0, cfix=50_000.0, kind="VRE", avail=[avail_row])])


def _lp(tmp_path, name, avail_row):
    return build_lp(load_case(write_case(_vre_spec(avail_row), tmp_path / name, case_id=name)), Scaling())


def test_f3_zero_availability_hour_stores_no_entry(tmp_path):
    base = np.full(T, 0.4)
    zero_hours = [5, 6, 40]
    prof = base.copy()
    prof[zero_hours] = 0.0
    lp_zero, lp_pos = _lp(tmp_path, "zero", prof), _lp(tmp_path, "pos", base)
    # gen_max row: g - A x <= A K0 ; the x-column entry -A exists only when A != 0. Each zero hour removes exactly one.
    assert lp_pos.a.nnz - lp_zero.a.nnz == len(zero_hours)
    assert lp_zero.a.nnz < lp_pos.a.nnz
    for lp in (lp_zero, lp_pos):
        a = sp.csr_matrix(lp.a)
        assert not np.any(a.data == 0.0), "explicit zero stored in the constraint matrix"
        assert a.nnz == np.count_nonzero(a.toarray())


@pytest.mark.parametrize("case", ["T1", "T2a", "T2b", "T3a", "T4"])
def test_f3_canonical_cases_have_no_stored_zeros(case):
    from healthlib import CASES
    a = sp.csr_matrix(build_lp(load_case(CASES / case), Scaling()).a)
    assert not np.any(a.data == 0.0)


# ------------------------------------------------------------------ F4: free-duration candidate storage zero-profit
def _storage_spec(cp, ce, xp=10.0, xe=40.0):
    """T2-style arbitrage (G1 20, G2 60; demand 50 then 150) with a FREE-duration candidate battery (no dmin/dmax)."""
    d = np.r_[np.full(36, 50.0), np.full(36, 150.0)]
    return Spec(["A"], [W1], np.array([[d]]),
                [th("g1", "A", k0=100, mc=20.0), th("g2", "A", k0=200, mc=60.0),
                 st("bat", "A", xp=xp, xe=xe, cp=cp, ce=ce)])


_ORIG_SOLVE = HighsSolver.solve


def _mutate_col_dual(monkeypatch, block, bump):
    def bad(self, lp):
        sol = _ORIG_SOLVE(self, lp)
        s = sol.col_dual.copy()
        s[lp.cols[block].offset] += bump
        return dataclasses.replace(sol, col_dual=s)
    monkeypatch.setattr(HighsSolver, "solve", bad)


@pytest.mark.parametrize("cp,ce,status", [(1_000.0, 2_000.0, "at_max"), (1_000.0, 9_000.0, "at_zero")])
def test_f4_clean_free_duration_storage_passes(tmp_path, cp, ce, status):
    case_dir = write_case(_storage_spec(cp, ce), tmp_path / "c")
    sv, h = solve_audit(case_dir)
    assert np.isnan(sv.case.storage.dur_lo[0]) and np.isnan(sv.case.storage.dur_hi[0]), "fixture must be free-duration"
    if status == "at_max":
        assert sv.var("xP")[0] > 1e-6 and sv.var("xE")[0] > 1e-6
    else:
        assert sv.var("xP")[0] <= 1e-6 and sv.var("xE")[0] <= 1e-6
    assert h.status == "pass", non_pass(h)
    assert "zero_profit" not in failing(h)


@pytest.mark.parametrize("cp,ce,block,bump", [
    (1_000.0, 2_000.0, "xE", +1e6),    # xE built to its max (needs s <= 0): reduced cost far positive
    (1_000.0, 9_000.0, "xE", -1e6),    # xE at zero (needs s >= 0): reduced cost far negative
    (1_000.0, 2_000.0, "xP", +1e6),
    (1_000.0, 9_000.0, "xP", -1e6),
])
def test_f4_wrong_sign_on_one_side_is_flagged(tmp_path, monkeypatch, cp, ce, block, bump):
    case_dir = write_case(_storage_spec(cp, ce), tmp_path / "c")
    _, h0 = solve_audit(case_dir)
    assert h0.status == "pass", "control must be clean"
    _mutate_col_dual(monkeypatch, block, bump)            # only ONE of s_xP / s_xE is wrong
    _, h = solve_audit(case_dir)
    assert "zero_profit" in failing(h), f"corrupted s_{block} not flagged by zero_profit; failing={failing(h)}"


def test_f4_interior_xe_nonzero_reduced_cost_flagged(tmp_path, monkeypatch):
    """Interior energy build (0 < xE < xmax): s_xE must be ~0; a nonzero one fails while s_xP stays fine."""
    d = np.r_[np.full(36, 50.0), np.full(36, 150.0)]
    # xE upper bound far above what P=10 MW can use (36 h x 10 MW / eta = 400 MWh discharge side) -> interior xE
    spec = _storage_spec(0.0, 2_000.0, xp=10.0, xe=1_000.0)
    case_dir = write_case(spec, tmp_path / "c")
    sv, h0 = solve_audit(case_dir)
    xe = sv.var("xE")[0]
    if not (1e-6 < xe < 1_000.0 - 1e-6):
        pytest.skip("Gate 2: fixture did not yield an interior xE with this data; interior case covered by at_max/at_zero rows")
    assert h0.status == "pass", non_pass(h0)
    _mutate_col_dual(monkeypatch, "xE", +1e6)
    _, h = solve_audit(case_dir)
    assert "zero_profit" in failing(h)


# ------------------------------------------------------------------ F5: ranged row duals in ScipyHighsSolver
def _ranged_lp(c, lo, hi, extra_row=True):
    """min c'x s.t. [extra row x1 <= 100 (slack)], lo <= x1 + x2 <= hi, 0 <= x <= 50."""
    rows = [[1.0, 0.0]] if extra_row else []
    rows.append([1.0, 1.0])
    a = sp.csr_matrix(np.array(rows))
    r_lo = ([-np.inf] if extra_row else []) + [lo]
    r_hi = ([100.0] if extra_row else []) + [hi]
    return LP(a=a, c=np.array(c, float), row_lo=np.array(r_lo), row_hi=np.array(r_hi),
              col_lo=np.zeros(2), col_hi=np.full(2, 50.0), rows={}, cols={}, scaling=Scaling.off())


# (costs, lo, hi, expected x, expected objective, expected dual of the ranged row = dZ*/db at the binding end)
_F5 = {
    # min -x1 - 2 x2, 1 <= x1+x2 <= 4: x2 = 4, Z = -8; raising hi by 1 lowers Z by 2 -> y = -2 (<= binding: y <= 0)
    "upper": ([-1.0, -2.0], 1.0, 4.0, [0.0, 4.0], -8.0, -2.0),
    # min x1 + 2 x2, 3 <= x1+x2 <= 10: x1 = 3, Z = 3; raising lo by 1 raises Z by 1 -> y = +1 (>= binding: y >= 0)
    "lower": ([1.0, 2.0], 3.0, 10.0, [3.0, 0.0], 3.0, 1.0),
}


@pytest.mark.parametrize("end", ["upper", "lower"])
@pytest.mark.parametrize("extra_row", [True, False])
def test_f5_scipy_ranged_row_dual_at_each_end(end, extra_row):
    c, lo, hi, x, z, y = _F5[end]
    lp = _ranged_lp(c, lo, hi, extra_row)
    sol = ScipyHighsSolver().solve(lp)
    assert sol.optimal and sol.objective == pytest.approx(z, abs=1e-7)
    np.testing.assert_allclose(sol.x, x, atol=1e-7)
    ranged = lp.n_rows - 1
    assert sol.row_dual[ranged] != 0.0, "ranged row dual lost (overwritten by the other side)"
    assert sol.row_dual[ranged] == pytest.approx(y, abs=1e-7)
    assert np.sign(sol.row_dual[ranged]) == (-1 if end == "upper" else 1)
    if extra_row:
        assert sol.row_dual[0] == pytest.approx(0.0, abs=1e-9)
    # reduced costs s_j = c_j - a_j' y
    expected_s = lp.c - lp.a.T @ sol.row_dual
    np.testing.assert_allclose(sol.col_dual, expected_s, atol=1e-7)


@pytest.mark.parametrize("end", ["upper", "lower"])
def test_f5_scipy_matches_highs_direct(end):
    c, lo, hi, *_ = _F5[end]
    lp = _ranged_lp(c, lo, hi)
    a = ScipyHighsSolver().solve(lp)
    b = HighsSolver().solve(lp)
    np.testing.assert_allclose(a.row_dual, b.row_dual, atol=1e-7)
    np.testing.assert_allclose(a.col_dual, b.col_dual, atol=1e-7)
    assert a.objective == pytest.approx(b.objective, abs=1e-8)


def test_f5_scipy_equals_highs_on_ranged_row_case_scaled():
    """Same ranged LP with the production scaling: duals still agree between the two adapters."""
    lp = dataclasses.replace(_ranged_lp(*_F5["upper"][:3]), scaling=Scaling())
    a, b = ScipyHighsSolver().solve(lp), HighsSolver().solve(lp)
    np.testing.assert_allclose(a.row_dual, b.row_dual, atol=1e-7)


# ------------------------------------------------------------------ P1-a: git_state with whitespace in untracked paths
def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": __import__("os").environ["PATH"],
                        "HOME": str(cwd)})


def test_p1a_untracked_paths_with_spaces_not_split(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "data" / "tracked.csv").write_text("a\n")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    (repo / "data" / "my dir").mkdir()
    files = {"data/my dir/raw file.csv": b"x,y\n1,2\n", "data/two  spaces.csv": b"z\n", "data/plain.csv": b"p\n"}
    for rel, content in files.items():
        (repo / rel).write_bytes(content)
    monkeypatch.setattr(fpmod, "REPO_ROOT", repo)
    commit, digest = fpmod.git_state()
    assert commit != "unknown" and digest != "unknown"
    expected = hashlib.sha256(b"")                      # no tracked diff
    for rel in sorted(files):
        expected.update(rel.encode() + files[rel])
    assert digest == expected.hexdigest(), "untracked list must hold the exact paths (not whitespace-split pieces)"


def test_p1a_digest_changes_when_spaced_file_changes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("1\n")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    f = repo / "src" / "new file.py"
    f.write_text("v1")
    monkeypatch.setattr(fpmod, "REPO_ROOT", repo)
    d1 = fpmod.git_state()[1]
    f.write_text("v2")
    assert fpmod.git_state()[1] != d1
