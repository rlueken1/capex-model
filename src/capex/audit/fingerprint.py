"""Hook 10: run fingerprint (SHA-256 over canonical inputs, config, code state, solver and environment)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd

from .. import FORMULATION_VERSION
from ..data import Case
from ..solver import Solution

REPO_ROOT = Path(__file__).resolve().parents[3]
CODE_PATHS = ["src", "cases", "data", "docs", "pyproject.toml"]
PACKAGES = ["numpy", "scipy", "pandas", "highspy", "pyyaml", "capex"]


@dataclass(frozen=True)
class Fingerprint:
    sha256: str
    valid: bool                # False when the conditioning check failed
    components: dict

    def __str__(self) -> str:
        return self.sha256 if self.valid else f"{self.sha256}-INVALID"


def _cell(value) -> str:
    return format(value, ".17g") if isinstance(value, float) else str(value)


def canonical_table(df: pd.DataFrame) -> str:
    """Columns sorted by name, rows sorted lexicographically, floats at 17 significant digits."""
    cols = sorted(df.columns)
    rows = sorted("\x1f".join(_cell(v) for v in row) for row in df[cols].astype(object).itertuples(index=False))
    return "\x1e".join(["\x1f".join(cols), *rows])


def _git(args: list[str]) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, check=True).stdout


def git_state() -> tuple[str, str]:
    """(commit, hash of uncommitted changes under code/data paths including untracked files)."""
    try:
        commit = _git(["rev-parse", "HEAD"]).decode().strip()
        diff = _git(["diff", "HEAD", "--", *CODE_PATHS])
        untracked = sorted(_git(["ls-files", "--others", "--exclude-standard", "-z", "--", *CODE_PATHS]).decode().split("\0")[:-1])
    except (OSError, subprocess.CalledProcessError):
        return "unknown", "unknown"
    digest = hashlib.sha256(diff)
    for name in untracked:
        digest.update(name.encode() + (REPO_ROOT / name).read_bytes())
    return commit, digest.hexdigest()


def package_versions() -> dict[str, str]:
    out = {}
    for name in PACKAGES:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = "not-installed"
    return out


def fingerprint_components(case: Case, solution: Solution, scaling: dict) -> dict:
    commit, dirty = git_state()
    return {
        "tables": {k: hashlib.sha256(canonical_table(v).encode()).hexdigest() for k, v in sorted(case.tables.items())},
        "config": json.loads(json.dumps(case.config, sort_keys=True, default=str)),
        "tolerances": case.tolerances.as_dict(), "scaling": scaling, "formulation_version": FORMULATION_VERSION,
        "git_commit": commit, "dirty_diff_hash": dirty,
        "solver": {"name": solution.solver_name, "version": solution.solver_version,
                   "options": json.loads(json.dumps(solution.options, sort_keys=True))},
        "python": sys.version, "packages": package_versions(), "seed": case.seed}


def run_fingerprint(case: Case, solution: Solution, scaling: dict, valid: bool) -> Fingerprint:
    components = fingerprint_components(case, solution, scaling)
    digest = hashlib.sha256(json.dumps(components, sort_keys=True).encode()).hexdigest()
    return Fingerprint(sha256=digest, valid=valid, components=components)
