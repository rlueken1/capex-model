"""Builder smoke tests for the G2-4 code fixes (F3, F4, F5, P1-a). The verifier's tests come in G2-5."""
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest
import scipy.sparse as sp

from capex.audit import fingerprint
from capex.model import _triplets
from capex.solver import HighsSolver, ScipyHighsSolver


def test_triplets_drop_explicit_zeros_but_keep_shape() -> None:
    part = (np.array([0, 1]), np.array([0, 1]), np.array([1.0, 0.0]))
    mat = _triplets([part], (2, 2))
    assert mat.nnz == 1 and mat.shape == (2, 2)


def _ranged_lp(c: float) -> SimpleNamespace:
    """min c*x s.t. 1 <= x <= 3 as a single ranged row (free column)."""
    return SimpleNamespace(a=sp.csr_matrix([[1.0]]), c=np.array([c]), row_lo=np.array([1.0]), row_hi=np.array([3.0]),
                           col_lo=np.array([-np.inf]), col_hi=np.array([np.inf]), n_rows=1, n_cols=1)


@pytest.mark.parametrize("c, expected", [(1.0, 1.0), (-1.0, -1.0)])
def test_ranged_row_dual_matches_native_at_either_end(c: float, expected: float) -> None:
    lp = _ranged_lp(c)
    scipy_dual = ScipyHighsSolver().solve(lp).row_dual
    native_dual = HighsSolver().solve(lp).row_dual
    assert native_dual == pytest.approx([expected])
    assert scipy_dual == pytest.approx([expected])


def test_git_state_keeps_untracked_path_with_space() -> None:
    path = fingerprint.REPO_ROOT / "src" / "capex" / "tmp file g2 4.py"
    try:
        path.write_text("x = 1\n")
        before = fingerprint.git_state()[1]
        path.write_text("x = 2\n")
        assert fingerprint.git_state()[1] != before
    finally:
        path.unlink(missing_ok=True)
