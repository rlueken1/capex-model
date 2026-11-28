"""G4-7-fix3 (F4-4): performance-ledger rows for T1-T4 and pjm5 transport/angle/PTDF.

Spec: docs/gates/gate-4.md section 8 ("first rows: T1-T4, pjm5 (Gate 3 reference = gate-3-evidence section 8)") and
docs/gates/README.md "Performance budget" (size identical to the previous gate, time <= 2x).
References: Gate 3 sizes and times from reports/gate-3-evidence.md section 8; T1-T4 LP shapes from the golden
`conditioning.json` (tests/golden/gate2/<case>/, generated from main at Gate 2). T1-T4 have no Gate 3 timing, so
their previous-gate cell stays empty (n/a). Reads the committed ledger and rebuilds each LP (no solve) for size."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "reports" / "performance-ledger.md"
TOYS = ["T1", "T2a", "T2b", "T2c", "T3a", "T3b", "T4"]
# reports/gate-3-evidence.md section 8: (rows, cols, nnz, solve s median)
GATE3 = {"pjm5-transport": (720, 1157, 2304, 0.0032), "pjm5-dcpf": (1224, 1517, 3672, 0.0115),
         "pjm5-ptdf": (864, 1157, 4896, 0.0044)}
PJM5_SWITCHES = {"pjm5-transport": {"tx.model": "transport"}, "pjm5-dcpf": None,
                 "pjm5-ptdf": {"tx.model": "dcpf", "tx.dcpf_form": "ptdf", "tx.ref_bus": "A"}}
PJM5_GOLDEN = {"pjm5-dcpf": "angle", "pjm5-ptdf": "ptdf"}


def ledger_rows() -> dict[tuple[str, str], dict[str, str]]:
    lines = [ln for ln in LEDGER.read_text().splitlines() if ln.startswith("| ")]
    head = [c.strip() for c in lines[0].strip("|").split("|")]
    out = {}
    for ln in lines[1:]:
        cells = dict(zip(head, (c.strip() for c in ln.strip("|").split("|"))))
        out[(cells["case"], cells["run"])] = cells
    return out


def num(cell: str) -> float:
    return float(cell.replace(",", ""))


def size(cells: dict[str, str]) -> tuple[int, int, int]:
    return int(num(cells["rows"])), int(num(cells["cols"])), int(num(cells["nnz"]))


def golden_size(path: Path) -> tuple[int, int, int]:
    m = json.loads(path.read_text())["metrics"]
    return m["rows"], m["cols"], m["nnz"]


@pytest.mark.parametrize("case", TOYS)
def test_toy_row_present_and_size_identical_to_golden(case):
    rows = ledger_rows()
    assert (case, case) in rows, f"no ledger row for {case}"
    cells = rows[(case, case)]
    assert size(cells) == golden_size(REPO / "tests" / "golden" / "gate2" / case / "conditioning.json")
    assert cells["previous gate s"] == "" and cells["ratio"] == "", "T1-T4 have no Gate 3 timing (n/a)"
    assert num(cells["solve s (median)"]) > 0 and int(cells["n"]) >= 3


@pytest.mark.parametrize("run", list(GATE3))
def test_pjm5_row_size_identical_and_time_within_2x(run):
    rows = ledger_rows()
    assert ("pjm5bus", run) in rows, f"no ledger row for pjm5bus {run}"
    cells = rows[("pjm5bus", run)]
    r, c, n, prev = GATE3[run]
    assert size(cells) == (r, c, n)
    assert num(cells["previous gate s"]) == pytest.approx(prev, rel=1e-9)
    ratio = num(cells["solve s (median)"]) / prev
    assert num(cells["ratio"]) == pytest.approx(ratio, abs=0.006)
    assert ratio <= 2.0, f"{run}: solve time {ratio:.2f}x the Gate 3 reference (README rule <= 2x)"
    if run in PJM5_GOLDEN:
        g = REPO / "tests" / "golden" / "gate3" / "pjm5bus" / PJM5_GOLDEN[run] / "conditioning.json"
        assert size(cells) == golden_size(g)


def test_note_records_toy_previous_as_na():
    text = LEDGER.read_text()
    assert re.search(r"n/a \(not measured at Gate 3\)", text)


def _rebuilt_size(case_dir: Path, switches, tmp_path) -> tuple[int, int, int]:
    import shutil

    import yaml
    from capex.config import Scaling
    from capex.data import load_case
    from capex.model import build_lp
    if switches is not None:
        cd = tmp_path / "cases" / case_dir.name
        shutil.copytree(case_dir, cd)
        (tmp_path / "data").symlink_to(REPO / "data")
        cfg = yaml.safe_load((cd / "case.yaml").read_text())
        cfg["switches"] = switches
        (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
        case_dir = cd
    case = load_case(case_dir)
    lp = build_lp(case, Scaling() if case.switches.get("scaling", True) else Scaling.off())
    return lp.n_rows, lp.n_cols, int(lp.a.nnz)


@pytest.mark.parametrize("key", TOYS + list(GATE3))
def test_current_lp_size_equals_ledger_row(key, tmp_path):
    """The ledger size is the LP the code builds now (not a stale copy)."""
    if key in TOYS:
        got = _rebuilt_size(REPO / "cases" / key, None, tmp_path)
        want = size(ledger_rows()[(key, key)])
    else:
        got = _rebuilt_size(REPO / "cases" / "pjm5bus", PJM5_SWITCHES[key], tmp_path)
        want = size(ledger_rows()[("pjm5bus", key)])
    assert got == want
