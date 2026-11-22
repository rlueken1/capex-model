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
