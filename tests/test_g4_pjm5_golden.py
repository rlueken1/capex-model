"""G4-7-fix2 (finding F4-2): Gate-4 golden identity for `pjm5bus` against the Gate-3 outputs (formulation 7.4a.9,
7.4a.13 row 6). Verifier test, written from the spec.

Golden: tests/golden/gate3/pjm5bus/{angle,ptdf}/ = canonical outputs (8.10) of cases/pjm5bus generated once from `main`
f3acf4d (F-0.3 code), recorded in SOURCE.txt next to them. Current code must reproduce them by the 8.10a rule after
(a) deleting `assumptions.md` lines starting "- run_id: " / "- fingerprint: " and (b) dropping the one health row new in
F-0.4, `price_setter.loop_interval` (health.csv and health_report.md). run.json is non-canonical (not stored).
Do not regenerate the golden to make this pass.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "tests" / "golden" / "gate3" / "pjm5bus"
LOOP_ROW = "price_setter.loop_interval"
FORMS = ["angle", "ptdf"]

# reuse the verifier's 8.10a comparison helper (same rule as the Gate-2/3 identity tests)
_spec = importlib.util.spec_from_file_location("_pj5", REPO / "tests" / "test_pjm5bus.py")
_pj5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pj5)


def drop_loop_row(fname: str, data: bytes) -> tuple[bytes, int]:
    """Remove the price_setter.loop_interval row from health.csv / health_report.md; return (data, rows removed)."""
    key = {"health.csv": LOOP_ROW + ",", "health_report.md": "| " + LOOP_ROW + " |"}[fname]
    keep, n = [], 0
    for line in data.decode().splitlines(keepends=True):
        if line.startswith(key):
            n += 1
        else:
            keep.append(line)
    return "".join(keep).encode(), n


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    from capex.run import run_case
    out = {}
    for form in FORMS:
        tmp = tmp_path_factory.mktemp("g4pjm5_" + form)
        cd = tmp / "cases" / "pjm5bus"
        shutil.copytree(REPO / "cases" / "pjm5bus", cd)
        (tmp / "data").symlink_to(REPO / "data")      # '../../data/...' table paths
        cfg = yaml.safe_load((cd / "case.yaml").read_text())
        # identical to the golden generation (SOURCE.txt): explicit form, reference bus A
        cfg["switches"] = {"tx.model": "dcpf", "tx.dcpf_form": form, "tx.ref_bus": "A"}
        (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
        run_case(cd, tmp / "out")
        out[form] = tmp / "out"
    return out


def test_golden_source_recorded_and_complete():
    txt = (GOLD / "SOURCE.txt").read_text()
    assert "f3acf4d" in txt and "Do not regenerate to make a test pass." in txt
    assert sorted(p.name for p in GOLD.iterdir() if p.is_dir()) == sorted(FORMS)
    for form in FORMS:
        names = {p.name for p in (GOLD / form).iterdir()}
        assert len(names) >= 20 and {"health.csv", "health_report.md", "assumptions.md", "dispatch.csv",
                                     "flows.csv", "zone_hourly.csv", "angles.csv"} <= names, form
        assert "run.json" not in names
        assert all((GOLD / form / n).stat().st_size > 0 for n in names if n != "unserved.csv"), form


@pytest.mark.parametrize("form", FORMS)
def test_golden_has_no_loop_interval_row_but_current_run_has_one(runs, form):
    """Vacuity guard: the drop is real (golden = F-0.3 has no such row; F-0.4 output has exactly one in each file)."""
    for f in ("health.csv", "health_report.md"):
        _, n_gold = drop_loop_row(f, (GOLD / form / f).read_bytes())
        _, n_cur = drop_loop_row(f, (runs[form] / f).read_bytes())
        assert (n_gold, n_cur) == (0, 1), f"{form}/{f}: loop_interval rows golden={n_gold} current={n_cur}"


@pytest.mark.parametrize("form", FORMS)
def test_pjm5_canonical_outputs_identical_to_gate3_golden(runs, form):
    gold, cur = GOLD / form, runs[form]
    gold_files = sorted(p.name for p in gold.iterdir())
    new_files = sorted(p.name for p in cur.iterdir() if p.name != "run.json")
    assert new_files == gold_files, (
        f"canonical file set differs: only current {sorted(set(new_files) - set(gold_files))}, "
        f"only golden {sorted(set(gold_files) - set(new_files))}")
    for f in gold_files:
        a, b = (gold / f).read_bytes(), (cur / f).read_bytes()
        if f == "assumptions.md":
            a, b = (_pj5._mask_assumptions(x.decode()).encode() for x in (a, b))
        elif f in ("health.csv", "health_report.md"):
            b, _ = drop_loop_row(f, b)
        why = _pj5._canonical_diff(f, a, b)
        assert why is None, f"{form}/{f} differs from the Gate-3 golden: {why}"
