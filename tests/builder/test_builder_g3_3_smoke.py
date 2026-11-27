"""Builder smoke tests for G3-3 (dcpf): LP size per spec 7.4a.3, loop algebra cases (b) and (c), blank ratings."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import yaml

from capex.audit import loop
from capex.data import load_case
from capex.model import build_lp
from capex.run import solve_case
from capex.solver import HighsSolver

PJM5 = Path(__file__).resolve().parents[2] / "cases" / "pjm5bus"
HOURS = 72


def _case(tmp_path: Path, switches: dict | None) -> Path:
    cd = tmp_path / "cases" / "pjm5bus"
    (tmp_path / "data").symlink_to(PJM5.parents[1] / "data")
    cd.parent.mkdir()
    shutil.copytree(PJM5, cd)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    cfg["switches"] = switches
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return cd


def test_angle_form_adds_the_spec_sized_blocks(tmp_path):
    base = build_lp(load_case(_case(tmp_path, {"tx.model": "transport"})))
    angle = build_lp(load_case(PJM5))
    n_nodes, n_lines, n_islands = 5, 6, 1
    assert angle.n_cols - base.n_cols == n_nodes * HOURS
    assert angle.n_rows - base.n_rows == (n_lines + n_islands) * HOURS
    assert angle.a.nnz - base.a.nnz == (3 * n_lines + n_islands) * HOURS
    assert angle.rows["ref_angle"].shape == (1, 1, HOURS) and angle.rows["kvl"].shape == (6, 1, HOURS)


def test_ptdf_form_has_no_bal_rows_and_no_ranged_rows(tmp_path):
    lp = build_lp(load_case(_case(tmp_path, {"tx.model": "dcpf", "tx.dcpf_form": "ptdf"})))
    assert "bal" not in lp.rows and "theta" not in lp.cols
    assert {"bal_sys", "ptdf_flow"} <= set(lp.rows)
    assert not (np.isfinite(lp.row_lo) & np.isfinite(lp.row_hi) & (lp.row_lo < lp.row_hi)).any()


def test_blank_rating_is_unlimited_under_transport(tmp_path):
    cd = _case(tmp_path, {"tx.model": "transport"})
    sv = solve_case(load_case(cd))
    assert np.isinf(sv.case.links.f_plus[1:5]).all() and list(sv.case.links.f_plus[[0, 5]]) == [400.0, 240.0]


def test_theta_is_unscaled_radians(tmp_path):
    sv = solve_case(load_case(PJM5))
    theta = sv.var("theta")[:, 0, 0]
    assert theta[0] == 0.0 and abs(theta[1] - (-0.07017)) < 1e-4          # B vs ref A, rad (not GW-rad)


def test_weights_nonunique_with_three_marginal_buses_sum_to_one():
    h_k = np.array([[0.0, 0.5, -0.3, 0.2]])                                 # one binding line, four nodes
    phi_b, phi_n = loop.phi(h_k, np.array([0, 1, 2])), loop.phi(h_k, np.array([3]))
    assert loop.classify(phi_b) == loop.NONUNIQUE
    alpha = loop.weights(phi_b, phi_n)
    assert abs(alpha.sum() - 1.0) < 1e-12


def test_interval_when_weights_are_not_computable():
    h_k = np.array([[0.5, 0.2], [0.1, 0.4]])                                # two binding lines, two nodes
    phi_b, phi_n = loop.phi(h_k, np.array([0])), loop.phi(h_k, np.array([1]))
    assert loop.classify(phi_b) == loop.INTERVAL
    bound = loop.Bound(phi_n[0], 35.0, -1)                                  # unit at zero at node 1: pi_1 <= 35
    iv = loop.interval(HighsSolver(), phi_b, np.array([30.0]), np.array([1.0, 1.0]), [bound], phi_n)
    assert iv[0, 0] == -np.inf and abs(iv[0, 1] - 35.0) < 1e-9
