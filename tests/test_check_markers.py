"""Verifier tests for Gate 2 item C5 (docs/gates/gate-2.md section 2 row C5): scripts/check_markers.py fails CI if any
xfail/skip marker lacks a reason containing `DECISIONS <n>` or `Gate <n>`; drafts under tests/draft/ must be skip with
`Gate <n>`. Exercised black-box through the CLI (`python scripts/check_markers.py [tests_dir]`, `--self-test`)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_markers.py"


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, cwd=cwd)


def tree(tmp_path, body, draft=False):
    d = tmp_path / "tests"
    (d / "draft" if draft else d).mkdir(parents=True, exist_ok=True)
    (d / "draft" / "test_x.py" if draft else d / "test_x.py").write_text("import pytest\n" + body)
    return d


def test_clean_tree_passes(tmp_path):
    r = run(tree(tmp_path, "def test_a():\n    assert True\n"))
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("body", [
    "@pytest.mark.xfail\ndef test_a(): ...\n",
    "@pytest.mark.skip\ndef test_a(): ...\n",
    "@pytest.mark.xfail()\ndef test_a(): ...\n",
    "@pytest.mark.skip(reason='')\ndef test_a(): ...\n",
    "@pytest.mark.skipif(True)\ndef test_a(): ...\n",
    "def test_a():\n    pytest.skip()\n",
    "def test_a():\n    pytest.xfail()\n",
])
def test_marker_without_reason_fails(tmp_path, body):
    r = run(tree(tmp_path, body))
    assert r.returncode != 0, "marker with no reason must fail"
    assert "test_x.py" in r.stdout + r.stderr


@pytest.mark.parametrize("body", [
    "@pytest.mark.skip(reason='flaky')\ndef test_a(): ...\n",
    "@pytest.mark.xfail(reason='known bug')\ndef test_a(): ...\n",
    "@pytest.mark.xfail(reason='see DECISIONS')\ndef test_a(): ...\n",
    "@pytest.mark.skip(reason='Gate later')\ndef test_a(): ...\n",
    "@pytest.mark.skipif(True, reason='Decisions 3')\ndef test_a(): ...\n",
    "def test_a():\n    pytest.skip('not now')\n",
])
def test_reason_without_reference_fails(tmp_path, body):
    assert run(tree(tmp_path, body)).returncode != 0


@pytest.mark.parametrize("body", [
    "@pytest.mark.skip(reason='deferred, DECISIONS 33')\ndef test_a(): ...\n",
    "@pytest.mark.xfail(reason='Gate 3 PTDF form')\ndef test_a(): ...\n",
    "@pytest.mark.xfail(strict=True, reason='Gate 4 profiles')\ndef test_a(): ...\n",
    "@pytest.mark.skipif(1 > 2, reason='DECISIONS 7 optional dep')\ndef test_a(): ...\n",
    "def test_a():\n    pytest.skip('Gate 2 not applicable')\n",
])
def test_valid_reason_passes(tmp_path, body):
    r = run(tree(tmp_path, body))
    assert r.returncode == 0, r.stdout + r.stderr


def test_draft_xfail_fails_even_with_valid_reason(tmp_path):
    r = run(tree(tmp_path, "@pytest.mark.xfail(reason='Gate 3')\ndef test_a(): ...\n", draft=True))
    assert r.returncode != 0


def test_draft_skip_needs_gate_reference(tmp_path):
    assert run(tree(tmp_path, "@pytest.mark.skip(reason='DECISIONS 5 only')\ndef test_a(): ...\n", draft=True)).returncode != 0
    r = run(tree(tmp_path, "@pytest.mark.skip(reason='Gate 3 not built yet')\ndef test_a(): ...\n", draft=True))
    assert r.returncode == 0, r.stdout + r.stderr


def test_same_xfail_outside_draft_is_allowed(tmp_path):
    assert run(tree(tmp_path, "@pytest.mark.xfail(reason='Gate 3')\ndef test_a(): ...\n")).returncode == 0


def test_self_test_exits_1():
    r = run("--self-test")
    assert r.returncode == 1, r.stdout + r.stderr


def test_default_run_on_repo_tests_passes():
    r = run(cwd=SCRIPT.parents[1])
    assert r.returncode == 0, r.stdout + r.stderr
