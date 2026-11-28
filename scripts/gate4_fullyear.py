"""Helpers for .github/workflows/gate4-fullyear.yml (Gate 4, G4-5; gate-4.md sections 2 and 8).

  solve CASE_DIR --out DIR      run `python -m capex run` in a child process; write DIR/<case>/ and DIR/<case>.perf.json
                                (wall seconds, peak RSS of the child, exit code)
  summary DIR [--budget-s S --budget-gb G]   markdown for $GITHUB_STEP_SUMMARY from the perf and run.json files in DIR
"""
from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path


def solve(case_dir: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    proc = subprocess.run([sys.executable, "-m", "capex", "run", str(case_dir), "--out", str(out / case_dir.name)], check=False)
    wall = time.monotonic() - start
    peak_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0
    perf = {"case": case_dir.name, "wall_s": wall, "peak_rss_mb": peak_mb, "returncode": proc.returncode}
    (out / f"{case_dir.name}.perf.json").write_text(json.dumps(perf, indent=2))
    print(json.dumps(perf))
    return proc.returncode


def summary(directory: Path, budget_s: float | None, budget_gb: float | None) -> str:
    lines = ["| case | wall s | peak RSS MB | solve s | objective USD/yr | health | exit |", "|---|---|---|---|---|---|---|"]
    warnings: list[str] = []
    for perf_file in sorted(directory.glob("*.perf.json")):
        perf = json.loads(perf_file.read_text())
        run_file = directory / perf["case"] / "run.json"
        run = json.loads(run_file.read_text()) if run_file.exists() else {}
        lines.append(f"| {perf['case']} | {perf['wall_s']:.0f} | {perf['peak_rss_mb']:.0f} | {run.get('solve_time_s', float('nan')):.0f} "
                     f"| {run.get('z_total_usd_yr', float('nan')):,.0f} | {run.get('health', 'n/a')} | {perf['returncode']} |")
        if budget_s is not None and perf["wall_s"] > budget_s:
            warnings.append(f"{perf['case']}: wall {perf['wall_s']:.0f} s exceeds {budget_s:.0f} s budget")
        if budget_gb is not None and perf["peak_rss_mb"] > budget_gb * 1024:
            warnings.append(f"{perf['case']}: peak RSS {perf['peak_rss_mb']:.0f} MB exceeds {budget_gb:g} GB budget")
    return "\n".join(lines + [""] + [f"WARNING {w}" for w in warnings]) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gate4_fullyear")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("solve")
    s.add_argument("case_dir", type=Path)
    s.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("summary")
    m.add_argument("directory", type=Path)
    m.add_argument("--budget-s", type=float)
    m.add_argument("--budget-gb", type=float)
    args = parser.parse_args(argv)
    if args.command == "solve":
        return solve(args.case_dir, args.out)
    print(summary(args.directory, args.budget_s, args.budget_gb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
