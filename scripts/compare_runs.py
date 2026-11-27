"""Gate 2 C7: compare two health-run output trees (formulation 8.10 amendment 4, DECISIONS 36).

Canonical outputs = every output file except run.json, with the single `- run_id:` line of assumptions.md removed.
Two modes:
  compare_runs.py A B                     identical fingerprints (run.json) and byte-identical canonical outputs
  compare_runs.py A B --numeric           objective and price (pi) agree at rel 1e-9; fingerprints may differ
                                          (OS/package fields), for a local-vs-CI check
A and B each contain one sub-directory per case (as written by ci_health_run.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REL_TOL = 1e-9


def canonical(path: Path) -> bytes:
    data = path.read_bytes()
    if path.name == "assumptions.md":
        data = b"".join(line for line in data.splitlines(keepends=True) if not line.startswith(b"- run_id:"))
    return data


def output_files(case_dir: Path) -> dict[str, Path]:
    return {p.relative_to(case_dir).as_posix(): p for p in sorted(case_dir.rglob("*"))
            if p.is_file() and p.name != "run.json"}


def compare_exact(a: Path, b: Path) -> list[str]:
    problems: list[str] = []
    fa = json.loads((a / "run.json").read_text())["fingerprint"]
    fb = json.loads((b / "run.json").read_text())["fingerprint"]
    if fa != fb:
        problems.append(f"fingerprint differs: {fa} vs {fb}")
    files_a, files_b = output_files(a), output_files(b)
    if files_a.keys() != files_b.keys():
        problems.append(f"file sets differ: {sorted(files_a.keys() ^ files_b.keys())}")
    problems += [f"{name} differs" for name in sorted(files_a.keys() & files_b.keys())
                 if canonical(files_a[name]) != canonical(files_b[name])]
    return problems


def _close(x: np.ndarray, y: np.ndarray) -> bool:
    return x.shape == y.shape and bool(np.all(np.abs(x - y) <= REL_TOL * np.maximum(np.abs(x), np.abs(y)) + 1e-12))


def compare_numeric(a: Path, b: Path) -> list[str]:
    """Objective ($/yr, z_total) and zone prices pi at rel 1e-9 (absolute floor 1e-12 for exact zeros)."""
    problems: list[str] = []
    za = json.loads((a / "run.json").read_text())["z_total_usd_yr"]
    zb = json.loads((b / "run.json").read_text())["z_total_usd_yr"]
    if not _close(np.array([za]), np.array([zb])):
        problems.append(f"objective differs: {za!r} vs {zb!r}")
    pa, pb = pd.read_csv(a / "price_setter.csv")["price"].to_numpy(), pd.read_csv(b / "price_setter.csv")["price"].to_numpy()
    if not _close(pa, pb):
        problems.append("pi (price_setter.csv price) differs beyond rel 1e-9")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--numeric", action="store_true", help="objective and pi at rel 1e-9 instead of byte identity")
    args = parser.parse_args(argv)
    cases_a = sorted(p.name for p in args.a.iterdir() if p.is_dir())
    cases_b = sorted(p.name for p in args.b.iterdir() if p.is_dir())
    if cases_a != cases_b or not cases_a:
        print(f"case sets differ or empty: {cases_a} vs {cases_b}")
        return 1
    compare = compare_numeric if args.numeric else compare_exact
    failed = False
    for case in cases_a:
        problems = compare(args.a / case, args.b / case)
        failed |= bool(problems)
        print(f"[{case}] {'DIFF: ' + '; '.join(problems) if problems else 'identical'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
