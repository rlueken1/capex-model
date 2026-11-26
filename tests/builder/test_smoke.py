"""Builder smoke tests: every case loads, solves and produces a health report. They do not judge correctness
against the spec's known answers (that is the verifier's job)."""
import json
from pathlib import Path

import pytest

from capex.cli import main
from capex.data import DataError, load_case
from capex.run import solve_case
from capex.audit.report import health_report

CASES = Path(__file__).resolve().parents[2] / "cases"
NAMES = ["T1", "T2a", "T2b", "T2c", "T3a", "T3b", "T4"]


@pytest.mark.parametrize("name", NAMES)
def test_case_solves_and_health_report_runs(name: str) -> None:
    sv = solve_case(load_case(CASES / name))
    report = health_report(sv)
    assert set(report.checks["status"]) <= {"pass", "warn", "fail"}
    assert len(report.checks) > 10


def test_cli_writes_outputs(tmp_path: Path) -> None:
    assert main(["run", str(CASES / "T4"), "--out", str(tmp_path)]) in (0, 1)
    for name in ("run.json", "health_report.md", "price_setter.csv", "duals_raw.csv", "assumptions.md"):
        assert (tmp_path / name).exists()
    assert json.loads((tmp_path / "run.json").read_text())["case_id"] == "T4"


def test_bad_weight_is_rejected(tmp_path: Path) -> None:
    import shutil
    shutil.copytree(CASES / "T1", tmp_path / "T1")
    (tmp_path / "T1" / "periods.csv").write_text(
        (tmp_path / "T1" / "periods.csv").read_text().replace("121.66666666666667", "120.0"))
    with pytest.raises(DataError):
        load_case(tmp_path / "T1")


def test_block_idx_empty_index_arrays_any_dtype():
    """Regression (W4a-fix): empty object-dtype index arrays must not reach ravel_multi_index."""
    import numpy as np
    from capex.model import Block
    blk = Block("bal", ("zone", "period", "t"), (("a", "b"), ("p",), ("t0", "t1")), offset=5)
    out = blk.idx(np.empty((0, 1, 2), dtype=object), np.zeros((0, 1, 2), dtype=np.int64), np.zeros((0, 1, 2), dtype=np.int64))
    assert out.shape == (0, 1, 2) and out.dtype == np.int64
    full = blk.idx(np.array([1]), np.array([0]), np.array([1]))
    assert full.tolist() == [5 + 3]


def _asym_solved(tmp_path: Path):
    from healthlib import solve_audit, toy_spec, write_case
    return solve_audit(write_case(toy_spec("S2asym"), tmp_path, case_id="S2asym"))


def test_soc_recompute_passes_on_toy_and_fails_on_swapped_eta(tmp_path: Path) -> None:
    import dataclasses
    from capex.audit.economics import soc_recompute_residual
    sv, h = _asym_solved(tmp_path)
    row = h.checks[h.checks["check_id"] == "storage.soc_recompute"].iloc[0]
    assert row["status"] == "pass" and row["value"] <= 1e-6
    st = sv.case.storage
    swapped = dataclasses.replace(st, eta_c=st.eta_d, eta_d=st.eta_c)
    bad = dataclasses.replace(sv, case=dataclasses.replace(sv.case, storage=swapped))
    assert soc_recompute_residual(bad) > 1e-3


def test_storage_setter_cost_uses_water_value(tmp_path: Path) -> None:
    import numpy as np
    sv, h = _asym_solved(tmp_path)
    tab = h.audit.price_setter.table
    dis = tab[tab["primary_class"] == "STORAGE_DIS"]
    assert len(dis) and np.allclose(dis["residual"], dis["price"] - dis["setter_cost"])
    assert (dis["residual"].abs() <= 0.01 + 1e-5 * dis["price"].abs()).all()


def test_vre_without_fuel_column_has_zero_mc(tmp_path: Path) -> None:
    import numpy as np
    from healthlib import W1, Spec, th, write_case
    prof = np.full((1, 72), 0.5)
    spec = Spec(["A"], [W1], np.full((1, 1, 72), 60.0),
                [th("g", "A", k0=100, mc=20.0), th("w", "A", k0=50, kind="VRE", mc=None, avail=prof)])
    assert float(load_case(write_case(spec, tmp_path)).gen.mc[1].max()) == 0.0
