"""Fixtures for the verifier health tests (tests/test_health_*.py). See tests/healthlib.py for the helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from capex.audit.fingerprint import Fingerprint
from capex.audit.report import HealthReport
from capex.audit.solved import Solved
from capex.run import output_tables, run_case
from healthlib import CASES, TOYS, toy_spec, write_case


@dataclass
class Canon:
    name: str
    case_dir: Path
    out_dir: Path
    sv: Solved
    health: HealthReport
    fp: Fingerprint
    tables: dict


@pytest.fixture(scope="session")
def canon(tmp_path_factory):
    """canon("T1") (or a toy name from healthlib.TOYS) -> Canon with the Solved run, HealthReport, fingerprint and output tables (cached per session)."""
    cache: dict[str, Canon] = {}

    def get(name: str) -> Canon:
        if name not in cache:
            out = tmp_path_factory.mktemp(f"canon_{name}")
            case_dir = CASES / name if name not in TOYS else write_case(
                toy_spec(name), tmp_path_factory.mktemp(f"toy_{name}"), case_id=name)
            sv, health, fp = run_case(case_dir, out)
            cache[name] = Canon(name, case_dir, out, sv, health, fp, output_tables(sv, health))
        return cache[name]
    return get
