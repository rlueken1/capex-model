"""Command line: `python -m capex run <case_dir> --out <dir>`."""
from __future__ import annotations

import argparse
import sys

from .run import run_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capex")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="solve a case and write outputs and the health report")
    run.add_argument("case_dir")
    run.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    sv, health, fp = run_case(args.case_dir, args.out)
    print(health.to_markdown(sv.case.case_id))
    print(f"fingerprint: {fp}")
    return 0 if health.status != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
