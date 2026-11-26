#!/usr/bin/env python3
"""Download a cached data-download artifact with the `gh` CLI and verify it (Gate 2, G2-3; gate-2.md D8).

    python scripts/fetch_artifact.py pjm5 [--run-id N] [--artifact NAME] [--against cases/raw/pjm5bus]

Files land directly in data/raw/<source_id>/ (git-ignored). Without --artifact the newest artifact
named data-<source_id>-* of the run is used; without --run-id the latest successful data-download run.
Exit 0 only if verify_artifact.verify() (and --against, if given) report no problem; 1 mismatch or
download error; 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_artifact import verify, verify_against  # noqa: E402


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def latest_run_id(workflow: str = "data-download.yml") -> str:
    runs = json.loads(_gh("run", "list", "--workflow", workflow, "--status", "success",
                          "--limit", "1", "--json", "databaseId"))
    if not runs:
        raise SystemExit(_err(1, f"no successful {workflow} run found"))
    return str(runs[0]["databaseId"])


def pick_artifact(run_id: str, source_id: str) -> str:
    names = _gh("api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/artifacts", "--jq",
                ".artifacts[].name").split()
    wanted = [n for n in names if n.startswith(f"data-{source_id}-")]
    if not wanted:
        raise SystemExit(_err(1, f"run {run_id} has no artifact data-{source_id}-* (found {names})"))
    return wanted[0]


def _err(code: int, msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("source_id")
    p.add_argument("--run-id", default=None)
    p.add_argument("--artifact", default=None)
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--manifest-dir", default="data/manifests")
    p.add_argument("--against", default=None, help="vendored directory the files must hash equal")
    a = p.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9_]+", a.source_id):
        return _err(2, f"invalid source_id {a.source_id!r}")
    dest = Path(a.raw_dir) / a.source_id
    try:
        run_id = a.run_id or latest_run_id()
        name = a.artifact or pick_artifact(run_id, a.source_id)
        if dest.exists():
            shutil.rmtree(dest)
        _gh("run", "download", run_id, "-n", name, "--dir", str(dest))
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return _err(1, f"gh failed: {getattr(exc, 'stderr', '') or exc}")
    problems = verify(dest, Path(a.manifest_dir))
    if a.against:
        problems += verify_against(dest, Path(a.against))
    for msg in problems:
        print(f"FAIL: {msg}", file=sys.stderr)
    if not problems:
        print(f"OK: {dest} (artifact {name}, run {run_id}) verified")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
