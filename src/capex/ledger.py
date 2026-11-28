"""Performance ledger writer (docs/gates/README.md "Performance budget", gate-4.md section 8).

One row per case x run in `reports/performance-ledger.md`: LP size, solve time (median of repeats), peak RSS, solver
method and crossover, HiGHS version, runner, git commit, and the previous gate's solve time with the ratio."""
from __future__ import annotations

import os
import platform
import resource
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit.fingerprint import git_state
from .config import Scaling
from .data import load_case
from .model import build_lp
from .solver import make_solver

LEDGER_PATH = Path("reports/performance-ledger.md")
HEADERS = {"case": "case", "run": "run", "rows": "rows", "cols": "cols", "nnz": "nnz", "solve_s": "solve s (median)",
           "repeats": "n", "peak_rss_mb": "peak RSS MB", "method": "method", "crossover": "crossover",
           "highs": "HiGHS", "runner": "runner", "commit": "git commit", "previous_s": "previous gate s", "ratio": "ratio"}


@dataclass(frozen=True)
class LedgerRow:
    case: str
    run: str
    rows: int
    cols: int
    nnz: int
    solve_s: float
    repeats: int
    peak_rss_mb: float
    method: str
    crossover: str
    highs: str
    runner: str
    commit: str
    previous_s: float | None = None

    @property
    def ratio(self) -> float | None:
        return None if not self.previous_s else self.solve_s / self.previous_s


def runner_type() -> str:
    hosted = "github-hosted " if os.environ.get("GITHUB_ACTIONS") else ""
    return f"{hosted}{platform.system()} {platform.machine()} {os.cpu_count()} cpu"


def measure(case_dir: str | Path, run: str, repeats: int = 3, previous_s: float | None = None) -> LedgerRow:
    """Build the case's LP once and solve it `repeats` times with the case's solver; the row carries the median solve
    time. Peak RSS is the process high-water mark (run each ledger row in its own process for a per-case value)."""
    case = load_case(case_dir)
    lp = build_lp(case, Scaling() if case.switches.get("scaling", True) else Scaling.off())
    solver = make_solver(case.solver_config)
    sols = [solver.solve(lp) for _ in range(repeats)]
    first = sols[0]
    return LedgerRow(
        case=case.case_id, run=run, rows=lp.n_rows, cols=lp.n_cols, nnz=int(lp.a.nnz),
        solve_s=statistics.median(s.solve_time_s for s in sols), repeats=repeats,
        peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
        method=str(first.options.get("solver", first.solver_name)),
        crossover=str(first.options.get("run_crossover", "n/a")), highs=first.solver_version, runner=runner_type(),
        commit=git_state()[0], previous_s=previous_s)


def _cell(name: str, value: object) -> str:
    if value is None:
        return ""
    if name in ("solve_s", "previous_s"):
        return f"{value:.4g}"
    if name in ("peak_rss_mb",):
        return f"{value:.0f}"
    if name == "ratio":
        return f"{value:.2f}"
    return f"{value:,}" if name in ("rows", "cols", "nnz") else str(value)


def render(rows: list[LedgerRow]) -> str:
    names = list(HEADERS)
    lines = ["# Performance ledger", "",
             "Written by `python -m capex ledger` (`capex/ledger.py`). One row per case x run; solve time is the median of `n`"
             " solves of the same LP; previous gate = the Gate 3 reference (reports/gate-3-evidence.md section 8) where one exists.",
             "", "| " + " | ".join(HEADERS[n] for n in names) + " |", "|" + "---|" * len(names)]
    for row in rows:
        values = {**asdict(row), "ratio": row.ratio}
        lines.append("| " + " | ".join(_cell(n, values[n]) for n in names) + " |")
    return "\n".join(lines) + "\n"


def _parse(cell: str, name: str) -> object:
    if name in ("rows", "cols", "nnz", "repeats"):
        return int(cell.replace(",", ""))
    if name in ("solve_s", "peak_rss_mb"):
        return float(cell)
    if name == "previous_s":
        return float(cell) if cell else None
    return cell


def read_ledger(path: Path) -> list[LedgerRow]:
    """Rows of an existing ledger file (empty when it does not exist)."""
    if not path.exists():
        return []
    table = [ln for ln in path.read_text().splitlines() if ln.startswith("| ")][1:]
    cells = [[c.strip() for c in ln.strip("|").split("|")] for ln in table]
    return [LedgerRow(**{n: _parse(v, n) for n, v in zip(HEADERS, row) if n != "ratio"}) for row in cells]


def write_ledger(path: Path, new: list[LedgerRow]) -> list[LedgerRow]:
    """Merge `new` into the ledger at `path`: a row with the same (case, run) is replaced, others are kept in order."""
    merged = {(r.case, r.run): r for r in read_ledger(path)}
    merged.update({(r.case, r.run): r for r in new})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(list(merged.values())))
    return list(merged.values())
