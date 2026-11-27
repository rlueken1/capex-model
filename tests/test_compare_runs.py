"""Verifier test of scripts/compare_runs.py compare_exact under formulation 8.10a (no solver)."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "tests" / "golden" / "gate2" / "T1"
_spec = importlib.util.spec_from_file_location("compare_runs", REPO / "scripts" / "compare_runs.py")
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)


def _tree(root: Path, name: str) -> Path:
    d = root / name
    shutil.copytree(GOLD, d)
    (d / "components.json").unlink()
    (d / "run.json").write_text(json.dumps({"fingerprint": "abc"}))
    return d


def test_compare_exact_accepts_health_noise_rejects_flip(tmp_path):
    a, b = _tree(tmp_path, "a"), _tree(tmp_path, "b")
    assert cr.compare_exact(a, b) == []
    for f, old, new in (("health.csv", b"1.7405024881444741e-16", b"0.0"),
                        ("health_report.md", b"| 1.7405e-16 |", b"| 0 |")):
        t = (b / f).read_bytes()
        assert old in t
        (b / f).write_bytes(t.replace(old, new))
    assert cr.compare_exact(a, b) == []
    (b / "health.csv").write_bytes((b / "health.csv").read_bytes().replace(b"strong_duality,strong_duality,pass", b"strong_duality,strong_duality,warn"))
    assert any("health.csv" in p for p in cr.compare_exact(a, b))


def test_compare_exact_rejects_value_and_other_file_changes(tmp_path):
    a, b = _tree(tmp_path, "a"), _tree(tmp_path, "b")
    (b / "health.csv").write_bytes((b / "health.csv").read_bytes().replace(b"1.7405024881444741e-16", b"1e-09"))
    assert any("health.csv" in p for p in cr.compare_exact(a, b))
    b2 = _tree(tmp_path, "b2")
    d = (b2 / "dispatch.csv").read_bytes()
    (b2 / "dispatch.csv").write_bytes(d.replace(b"0", b"1", 1))
    assert cr.compare_exact(a, b2) == ["dispatch.csv differs"]
