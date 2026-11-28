"""Command line: `python -m capex run <case_dir> --out <dir>` and `python -m capex ledger <case_dir> --run <label>`."""
from __future__ import annotations

import argparse
import sys

from pathlib import Path

from .ledger import LEDGER_PATH, measure, write_ledger
from .run import run_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capex")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="solve a case and write outputs and the health report")
    run.add_argument("case_dir")
    run.add_argument("--out", required=True)
    ledger = sub.add_parser("ledger", help="measure a case and add its row to the performance ledger")
    ledger.add_argument("case_dir")
    ledger.add_argument("--run", required=True, help="run label, e.g. R4-Z")
    ledger.add_argument("--repeats", type=int, default=3)
    ledger.add_argument("--previous-s", type=float, default=None, help="previous gate's solve time in seconds")
    ledger.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    args = parser.parse_args(argv)
    if args.command == "ledger":
        row = measure(args.case_dir, args.run, args.repeats, args.previous_s)
        write_ledger(args.ledger, [row])
        print(f"{row.case} {row.run}: {row.rows} x {row.cols}, solve {row.solve_s:.4g} s (median of {row.repeats})")
        return 0
    sv, health, fp = run_case(args.case_dir, args.out)
    print(health.to_markdown(sv.case.case_id))
    print(f"fingerprint: {fp}")
    return 0 if health.status != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
