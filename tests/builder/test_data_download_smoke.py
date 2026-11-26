"""Builder smoke tests for the data-download workflow scripts (Gate 2, G2-3). Offline: file:// URLs only."""
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_source  # noqa: E402
import verify_artifact  # noqa: E402

VENDORED = ROOT / "cases" / "raw" / "pjm5bus"
WORKFLOW = ROOT / ".github" / "workflows" / "data-download.yml"
VINTAGE = "v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(mdir: Path, source_id: str = "pjm5", *, sha: str | None = None, enabled: str = "true",
              auth_env: str = "", url_suffix: str = "") -> None:
    mdir.mkdir(exist_ok=True)
    with (mdir / f"{source_id}.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fetch_source.COLUMNS)
        for name in ("case5.m", "LICENSE_MATPOWER"):
            f = VENDORED / name
            w.writerow([source_id, VINTAGE, name, f.as_uri() + url_suffix, sha or _sha(f),
                        f.stat().st_size, auth_env, enabled, "test"])


def _run(tmp_path: Path, source_id: str = "pjm5") -> tuple[int, Path]:
    out = tmp_path / "out"
    rc = fetch_source.main([source_id, "--manifest-dir", str(tmp_path / "m"), "--out-dir", str(out)])
    return rc, out


def test_happy_path_writes_provenance(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_SHA", "abc")
    _manifest(tmp_path / "m")
    rc, out = _run(tmp_path)
    assert rc == 0
    prov = json.loads((out / "provenance.json").read_text())
    for key in ("source_id", "vintage", "retrieved_at", "workflow_run_id", "git_commit"):
        assert prov[key]
    assert (prov["source_id"], prov["vintage"], prov["workflow_run_id"], prov["git_commit"]) == ("pjm5", VINTAGE, "123", "abc")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", prov["retrieved_at"])
    assert {f["file"] for f in prov["files"]} == {"case5.m", "LICENSE_MATPOWER"}
    for f in prov["files"]:
        assert f["url"].startswith("file://") and f["sha256"] == _sha(VENDORED / f["file"]) and f["verified"]


def test_wrong_hash_fails_and_removes_output(tmp_path: Path) -> None:
    _manifest(tmp_path / "m", sha="0" * 64)
    rc, out = _run(tmp_path)
    assert rc == 1
    assert not out.exists()


def test_unknown_source_exits_2(tmp_path: Path) -> None:
    _manifest(tmp_path / "m")
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, "nope")
    assert exc.value.code == 2


def test_disabled_source_skips_cleanly(tmp_path: Path, capsys) -> None:
    _manifest(tmp_path / "m", enabled="false")
    rc, out = _run(tmp_path)
    assert rc == 0 and not out.exists()
    assert "disabled" in capsys.readouterr().out


def test_missing_key_skips_and_never_prints_key(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("TEST_KEY", raising=False)
    _manifest(tmp_path / "m", auth_env="TEST_KEY")
    rc, out = _run(tmp_path)
    assert rc == 0 and not out.exists()
    assert "TEST_KEY" in capsys.readouterr().out


def test_key_is_redacted_in_logs_on_failed_download(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("TEST_KEY", "s3cr3tvalue")
    mdir = tmp_path / "m"
    _manifest(mdir, auth_env="TEST_KEY", url_suffix="?k={TEST_KEY}")
    rc, out = _run(tmp_path)
    captured = capsys.readouterr()
    assert rc == 1 and not out.exists()  # file:// handler cannot serve a query string
    assert "s3cr3tvalue" not in captured.out + captured.err
    assert "***" in captured.out


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    _manifest(tmp_path / "m")
    rc, out = _run(tmp_path)
    assert rc == 0
    return out


def test_verify_accepts_clean_artifact(artifact: Path, tmp_path: Path) -> None:
    assert verify_artifact.verify(artifact, tmp_path / "m") == []
    assert verify_artifact.main([str(artifact), "--manifest-dir", str(tmp_path / "m"), "--against", str(VENDORED)]) == 0


def test_verify_catches_tampered_file(artifact: Path, tmp_path: Path) -> None:
    (artifact / "case5.m").write_bytes(b"tampered")
    assert verify_artifact.verify(artifact, tmp_path / "m")


def test_verify_catches_extra_file(artifact: Path, tmp_path: Path) -> None:
    (artifact / "extra.txt").write_text("x")
    assert any("extra.txt" in p for p in verify_artifact.verify(artifact, tmp_path / "m"))


def test_verify_against_mismatch(artifact: Path, tmp_path: Path) -> None:
    other = tmp_path / "vend"
    shutil.copytree(VENDORED, other)
    (other / "case5.m").write_bytes(b"different")
    assert verify_artifact.verify_against(artifact, VENDORED) == []
    assert verify_artifact.verify_against(artifact, other)
    assert verify_artifact.main([str(artifact), "--manifest-dir", str(tmp_path / "m"), "--against", str(other)]) == 1


def test_summary_contains_provenance(artifact: Path) -> None:
    text = verify_artifact.summary_markdown(artifact)
    assert "provenance.json" in text and _sha(VENDORED / "case5.m") in text


def test_committed_pjm5_manifest_matches_vendored_bytes() -> None:
    with (ROOT / "data" / "manifests" / "pjm5.csv").open(newline="") as fh:
        rows = {r["file"]: r for r in csv.DictReader(fh)}
    assert set(rows) == {"case5.m", "LICENSE_MATPOWER"}
    for name, r in rows.items():
        assert r["sha256"] == _sha(VENDORED / name)
        assert int(r["bytes"]) == (VENDORED / name).stat().st_size


@pytest.mark.parametrize("source_id", ["eia860", "eia923", "atb"])
def test_other_manifests_declared_but_disabled(source_id: str) -> None:
    with (ROOT / "data" / "manifests" / f"{source_id}.csv").open(newline="") as fh:
        assert {r["enabled"] for r in csv.DictReader(fh)} == {"false"}


def test_workflow_text_policy() -> None:
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert not re.search(r"^\s*schedule:", text, re.M)
    assert re.search(r"^permissions:\s*\n\s+contents: read\b", text, re.M)
    assert "git push" not in text and "contents: write" not in text
    assert "runs-on: ubuntu-24.04" in text and "ubuntu-latest" not in text
    assert "retention-days:" in text
    assert "GITHUB_STEP_SUMMARY" in text
    assert text.count("steps.fetch.outputs.fetched == 'true'") >= 2
