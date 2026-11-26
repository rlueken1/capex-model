"""Gate 2 C6: run the T1-T4 toy cases through the CLI and fail on any health `fail` or UNEXPLAINED price-setter hour.

Usage: python scripts/ci_health_run.py --out <dir> [--cases-dir cases] [--cases T1 T2a ...]
Each case's outputs land in <dir>/<case>/ (audit tables, run.json, assumptions.md). Exit 1 if any check fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

DEFAULT_CASES = ("T1", "T2a", "T2b", "T2c", "T3a", "T3b", "T4")


def run_case_cli(case_dir: Path, out_dir: Path) -> int:
    """Run `python -m capex run`; returns its exit code (non-zero when the health report fails)."""
    return subprocess.run([sys.executable, "-m", "capex", "run", str(case_dir), "--out", str(out_dir)]).returncode


def check_outputs(out_dir: Path) -> list[str]:
    """Problems found in one case's output dir: health `fail` rows and UNEXPLAINED price-setter hours."""
    problems: list[str] = []
    health = pd.read_csv(out_dir / "health.csv")
    problems += [f"health check {r.check_id} status=fail ({r.detail})" for r in health.itertuples() if r.status == "fail"]
    unexplained = int((pd.read_csv(out_dir / "price_setter.csv")["primary_class"] == "UNEXPLAINED").sum())
    if unexplained > 0:
        problems.append(f"price-setter UNEXPLAINED zone-hours = {unexplained}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--cases-dir", default=Path("cases"), type=Path)
    parser.add_argument("--cases", nargs="+", default=list(DEFAULT_CASES))
    args = parser.parse_args(argv)
    failed: dict[str, list[str]] = {}
    for case in args.cases:
        out = args.out / case
        code = run_case_cli(args.cases_dir / case, out)
        problems = check_outputs(out) if (out / "health.csv").exists() else ["no outputs written"]
        if code != 0 and not problems:
            problems = [f"CLI exit code {code}"]
        if problems:
            failed[case] = problems
        print(f"[{case}] {'FAIL' if problems else 'ok'}")
    for case, problems in failed.items():
        print(f"::error::{case}: " + "; ".join(problems))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
