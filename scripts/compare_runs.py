"""Gate 2 C7: compare two health-run output trees (formulation 8.10 amendment 4, DECISIONS 36).

Canonical outputs = every output file except run.json, with the single `- run_id:` line of assumptions.md removed.
Two modes:
  compare_runs.py A B                     identical fingerprints (run.json) and byte-identical canonical outputs, except health
                                          values within 1e-12 (formulation 8.10a, DECISIONS 50)
  compare_runs.py A B --numeric           objective and price (pi) agree at rel 1e-9; fingerprints may differ
                                          (OS/package fields), for a local-vs-CI check
A and B each contain one sub-directory per case (as written by ci_health_run.py).
"""
from __future__ import annotations

import argparse
import csv
import io
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


def _floats_close(x: str, y: str) -> bool:
    """8.10a: |a-b| <= 1e-12 absolute or relative; non-finite must match exactly. Keep in sync with tests/test_pjm5bus.py."""
    if x == y:
        return True
    try:
        a, b = float(x), float(y)
    except ValueError:
        return False
    if not (np.isfinite(a) and np.isfinite(b)):
        return bool((np.isnan(a) and np.isnan(b)) or a == b)
    d = abs(a - b)
    return d <= 1e-12 or d <= 1e-12 * max(abs(a), abs(b))


def health_diff(fname: str, a: bytes, b: bytes) -> str | None:
    """Formulation 8.10a (DECISIONS 50): None if equal, else the first difference. Only the `value` field of
    health.csv and the value cell of the health_report.md check table are compared as floats; all else byte-exact."""
    if a == b:
        return None
    if fname == "health.csv":
        ra = list(csv.reader(io.StringIO(a.decode(), newline="")))
        rb = list(csv.reader(io.StringIO(b.decode(), newline="")))
        if not ra or not rb or ra[0] != rb[0]:
            return "header differs"
        if len(ra) != len(rb):
            return f"row count {len(ra)} vs {len(rb)}"
        if "value" not in ra[0]:
            return "no value column"
        iv = ra[0].index("value")
        for n, (x, y) in enumerate(zip(ra[1:], rb[1:]), start=1):
            if len(x) != len(y):
                return f"row {n} ({x[0]}) field count differs"
            for j, (p, q) in enumerate(zip(x, y)):
                if (j == iv and not _floats_close(p, q)) or (j != iv and p != q):
                    return f"check_id {x[0]!r} field {ra[0][j]}: {p!r} vs {q!r}"
        if (b"\r\n" in a) != (b"\r\n" in b) or a.count(b"\n") != b.count(b"\n"):
            return "line endings differ"
        return None
    la, lb = a.decode().split("\n"), b.decode().split("\n")
    if len(la) != len(lb):
        return f"line count {len(la)} vs {len(lb)}"

    def is_row(s: str) -> bool:
        return s.startswith("| ") and not s.startswith("| check |") and not s.startswith("|---")

    for n, (x, y) in enumerate(zip(la, lb), start=1):
        if x == y:
            continue
        if not (is_row(x) and is_row(y)):
            return f"line {n} differs: {x!r} vs {y!r}"
        px, py = x.split("|", 5), y.split("|", 5)
        if len(px) != 6 or len(py) != 6:
            return f"line {n} malformed table row"
        if any(px[k] != py[k] for k in (0, 1, 2, 4, 5)) or not _floats_close(px[3].strip(), py[3].strip()):
            return f"check {px[1].strip()!r} (line {n}): {x!r} vs {y!r}"
    return None


def compare_exact(a: Path, b: Path) -> list[str]:
    """Fingerprints and all files byte-identical, except the health `value` cells under formulation 8.10a."""
    problems: list[str] = []
    fa = json.loads((a / "run.json").read_text())["fingerprint"]
    fb = json.loads((b / "run.json").read_text())["fingerprint"]
    if fa != fb:
        problems.append(f"fingerprint differs: {fa} vs {fb}")
    files_a, files_b = output_files(a), output_files(b)
    if files_a.keys() != files_b.keys():
        problems.append(f"file sets differ: {sorted(files_a.keys() ^ files_b.keys())}")
    for name in sorted(files_a.keys() & files_b.keys()):
        ca, cb = canonical(files_a[name]), canonical(files_b[name])
        if ca == cb:
            continue
        if name in ("health.csv", "health_report.md"):
            why = health_diff(name, ca, cb)
            if why is not None:
                problems.append(f"{name} differs: {why}")
        else:
            problems.append(f"{name} differs")
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
