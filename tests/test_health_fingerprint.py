"""Verifier tests: gate-1.md section 3 row "Run fingerprint determinism" (formulation 8.10) and DECISIONS 20.

Rules under test:
  same inputs / config / commit / solver options -> identical SHA-256 and byte-identical canonical outputs across
  3 in-process runs and 2 separate processes with different PYTHONHASHSEED; changing any input float by 1e-12, any
  switch, any solver option, the formulation version or a dirty-tree diff changes the fingerprint; a conditioning
  `fail` marks the fingerprint invalid.
`run.json` carries run_id / timestamp / solve time by design and is excluded from the byte comparison (its
fingerprint fields are compared separately).
"""
from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

import capex.audit.fingerprint as fpmod
from capex.run import run_case
from healthlib import CASES, W1, REPO, Spec, st, th, write_case
import numpy as np


def _outputs(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.name != "run.json"}


def _assert_same_outputs(a: Path, b: Path):
    oa, ob = _outputs(a), _outputs(b)
    assert oa.keys() == ob.keys()
    diff = [k for k in oa if oa[k] != ob[k]]
    assert not diff, f"outputs differ byte-wise: {diff}"


def _copy_case(src: Path, dst: Path, mutate=None) -> Path:
    """Copy a case to `dst`, rewrite its tables with full float precision, drop manifest sha256 (edited tables), make
    external table paths absolute; `mutate(man, tables)` may edit the manifest dict and the dict of DataFrames."""
    shutil.copytree(src, dst)
    man = yaml.safe_load((dst / "case.yaml").read_text())
    tables = {}
    for name, ent in man["tables"].items():
        ent.pop("sha256", None)
        if ent["file"].startswith("../"):
            ent["file"] = str((src / ent["file"]).resolve())
        tables[name] = pd.read_csv(dst / ent["file"]) if not Path(ent["file"]).is_absolute() else None
    if mutate:
        mutate(man, tables)
    for name, df in tables.items():
        if df is not None:
            df.to_csv(dst / man["tables"][name]["file"], index=False, float_format="%.17g")
    (dst / "case.yaml").write_text(yaml.safe_dump(man, sort_keys=False))
    return dst


def _fp(case_dir: Path, out: Path):
    return run_case(case_dir, out)[2]


# ---------------------------------------------------------------- determinism
def test_three_runs_identical_hash_and_bytes(tmp_path):
    outs = [tmp_path / f"r{i}" for i in range(3)]
    fps = [_fp(CASES / "T1", o) for o in outs]
    assert len({f.sha256 for f in fps}) == 1 and all(f.valid for f in fps)
    assert len(fps[0].sha256) == 64
    _assert_same_outputs(outs[0], outs[1])
    _assert_same_outputs(outs[0], outs[2])
    # run.json: fingerprint fields identical even though run_id / timestamp differ
    import json
    j = [json.loads((o / "run.json").read_text()) for o in outs]
    assert len({x["fingerprint_sha256"] for x in j}) == 1 and all(x["valid"] for x in j)


@pytest.mark.parametrize("name", ["T1", "T2b", "T4"])
def test_two_processes_different_hashseed(tmp_path, name):
    here = _fp(CASES / name, tmp_path / "here")
    outs = []
    for seed in ("1", "98765"):
        out = tmp_path / f"proc{seed}"
        env = {**os.environ, "PYTHONHASHSEED": seed}
        r = subprocess.run([sys.executable, "-m", "capex", "run", str(CASES / name), "--out", str(out)],
                           capture_output=True, text=True, env=env, cwd=REPO)
        assert r.returncode == 0, r.stdout + r.stderr
        line = [l for l in r.stdout.splitlines() if l.startswith("fingerprint: ")][-1]
        assert line.split(": ", 1)[1].strip() == here.sha256, "fingerprint must not depend on PYTHONHASHSEED or process"
        outs.append(out)
    _assert_same_outputs(tmp_path / "here", outs[0])
    _assert_same_outputs(outs[0], outs[1])


def test_fixture_case_round_trip_is_deterministic(tmp_path):
    """The copy/rewrite helper itself must not change the fingerprint (guards the perturbation tests below)."""
    a = _fp(_copy_case(CASES / "T1", tmp_path / "a"), tmp_path / "oa")
    b = _fp(_copy_case(CASES / "T1", tmp_path / "b"), tmp_path / "ob")
    assert a.sha256 == b.sha256


# ---------------------------------------------------------------- sensitivity
@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    base = tmp_path_factory.mktemp("fpbase")
    return _fp(_copy_case(CASES / "T1", base / "case"), base / "out")


def _variant(tmp_path, mutate):
    return _fp(_copy_case(CASES / "T1", tmp_path / "case", mutate), tmp_path / "out")


def test_input_float_perturbation_1e12_changes_fingerprint(tmp_path_factory, baseline):
    def bump(df, col, mask):
        df[col] = df[col].astype(float)
        df.loc[mask, col] += 1e-12

    def mc(man, t):
        bump(t["resources"], "mc_override_usd_mwh", t["resources"]["resource_id"] == "base")

    def demand(man, t):
        bump(t["load"], "demand_mw", t["load"].index == 0)

    def cfix(man, t):      # 6e4 has ulp 7.3e-12, so an absolute 1e-12 would be lost in float64: use a relative 1e-12
        df = t["resources"]
        df["cfix_override_usd_mw_yr"] = df["cfix_override_usd_mw_yr"].astype(float)
        df.loc[df["resource_id"] == "peaker", "cfix_override_usd_mw_yr"] *= 1 + 1e-12
    for fn in (mc, demand, cfix):
        fp = _variant(tmp_path_factory.mktemp(fn.__name__), fn)
        assert fp.sha256 != baseline.sha256, f"1e-12 change of an input float ({fn.__name__}) not reflected"


def test_switch_changes_fingerprint(tmp_path_factory, baseline):
    fp = _variant(tmp_path_factory.mktemp("sw"), lambda man, t: man["switches"].update({"audit.verifier_flag": True}))
    assert fp.sha256 != baseline.sha256
    fp2 = _variant(tmp_path_factory.mktemp("sw2"), lambda man, t: man["switches"].update({"scaling": False}))
    assert fp2.sha256 != baseline.sha256 and fp2.sha256 != fp.sha256


def test_solver_option_changes_fingerprint(tmp_path_factory, baseline):
    fp = _variant(tmp_path_factory.mktemp("opt"),
                  lambda man, t: man["solver"].update({"options": {"time_limit": 12345.0}}))
    assert fp.sha256 != baseline.sha256
    fp2 = _variant(tmp_path_factory.mktemp("opt2"),
                   lambda man, t: man["solver"].update({"options": {"time_limit": 12346.0}}))
    assert fp2.sha256 not in (baseline.sha256, fp.sha256)


def test_formulation_version_changes_fingerprint(tmp_path, monkeypatch, baseline):
    case = _copy_case(CASES / "T1", tmp_path / "case")
    monkeypatch.setattr(fpmod, "FORMULATION_VERSION", "F-9.9")
    fp = _fp(case, tmp_path / "out")
    assert fp.sha256 != baseline.sha256


def test_git_commit_changes_fingerprint(tmp_path, monkeypatch, baseline):
    case = _copy_case(CASES / "T1", tmp_path / "case")
    real = fpmod.git_state()
    monkeypatch.setattr(fpmod, "git_state", lambda: ("0" * 40, real[1]))
    assert _fp(case, tmp_path / "out").sha256 != baseline.sha256


def _git(repo: Path, *args):
    subprocess.run(["git", "-c", "user.name=v", "-c", "user.email=v@example.invalid", *args], cwd=repo, check=True,
                   capture_output=True)


def test_dirty_tree_diff_changes_fingerprint(tmp_path, monkeypatch):
    """Real git behaviour: the fingerprint's code state moves when a tracked or untracked code file is edited and returns
    to the original when the edit is reverted (same commit)."""
    repo = tmp_path / "repo"
    for d in fpmod.CODE_PATHS:
        if d.endswith(".toml"):
            (repo / d).parent.mkdir(parents=True, exist_ok=True)
            (repo / d).write_text("[project]\n")
        else:
            (repo / d).mkdir(parents=True, exist_ok=True)
            (repo / d / "m.py").write_text("x = 1\n")
    _git(repo.parent, "init", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    monkeypatch.setattr(fpmod, "REPO_ROOT", repo)
    case = _copy_case(CASES / "T1", tmp_path / "case")
    clean = _fp(case, tmp_path / "o0")
    assert _fp(case, tmp_path / "o0b").sha256 == clean.sha256
    (repo / "src" / "m.py").write_text("x = 2\n")                       # tracked file edited, not committed
    dirty = _fp(case, tmp_path / "o1")
    assert dirty.sha256 != clean.sha256
    assert dirty.components["dirty_diff_hash"] != clean.components["dirty_diff_hash"]
    assert dirty.components["git_commit"] == clean.components["git_commit"]
    (repo / "src" / "m.py").write_text("x = 1\n")                       # revert
    assert _fp(case, tmp_path / "o2").sha256 == clean.sha256
    (repo / "src" / "new_untracked.py").write_text("y = 1\n")           # untracked code file
    assert _fp(case, tmp_path / "o3").sha256 != clean.sha256


def test_package_and_python_versions_are_recorded(baseline):
    c = baseline.components
    assert c["python"] and set(c["packages"]) >= {"numpy", "scipy", "pandas", "highspy"}
    assert c["solver"]["name"] == "highs" and c["solver"]["version"] and c["solver"]["options"]
    assert c["formulation_version"] == "F-0.2" and "seed" in c and c["git_commit"]


# ---------------------------------------------------------------- conditioning fail invalidates
def _ill_conditioned(dmax: float) -> Spec:
    d = np.r_[np.full(36, 50.0), np.full(36, 150.0)]
    return Spec(["A"], [W1], np.array([[d]]), [
        th("g1", "A", k0=100, mc=20.0), th("g2", "A", k0=200, mc=60.0),
        st("bat", "A", xp=10, xe=40, cp=0.0, ce=3000.0, dmin=4.0, dmax=dmax)])


def test_conditioning_fail_marks_fingerprint_invalid(tmp_path):
    case = write_case(_ill_conditioned(2e9), tmp_path / "bad")
    sv, h, fp = run_case(case, tmp_path / "bad_out")
    assert h.checks.set_index("check_id").loc["conditioning.matrix_ratio", "status"] == "fail"
    assert fp.valid is False and str(fp).endswith("-INVALID")
    import json
    run = json.loads((tmp_path / "bad_out" / "run.json").read_text())
    assert run["valid"] is False and run["health"] == "fail"
    # a healthy run is valid, and the invalid flag is not the only difference (the hash covers the inputs)
    good = write_case(_ill_conditioned(4.0), tmp_path / "good")
    fp_good = run_case(good, tmp_path / "good_out")[2]
    assert fp_good.valid and not str(fp_good).endswith("-INVALID")
    assert fp_good.sha256 != fp.sha256


def test_conditioning_warn_keeps_fingerprint_valid(tmp_path):
    case = write_case(_ill_conditioned(1e7), tmp_path / "warn")
    sv, h, fp = run_case(case, tmp_path / "warn_out")
    assert h.checks.set_index("check_id").loc["conditioning.matrix_ratio", "status"] == "warn"
    assert fp.valid, "section 6.2: only a fail marks the run invalid; a warn is listed in the health report"
