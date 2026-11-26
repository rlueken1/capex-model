"""Verifier tests for load-time validation (formulation 1.1, 1.2, 5.1; gate-1.md section 3 "Load validation").

One bad input each must raise: weight sum != D_y/3 beyond 1e-9, w < 1, missing dollar year, dt != 1.
Each test copies cases/T1 (and the second-period variants) to a temp dir, edits ONE thing, re-hashes
the edited file in case.yaml, and calls `capex.data.load_case`.

Interface files consulted: src/capex/data.py (load_case, DataError), cases/T1 file formats (case.yaml
manifest with sha256 per table, periods.csv, load.csv, resources.csv). No implementation logic read.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from capex.data import load_case

ROOT = Path(__file__).resolve().parents[1]
T1 = ROOT / "cases" / "T1"
D_Y = 365                                  # model_year 2025 in T1


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class CaseEdit:
    def __init__(self, tmp: Path):
        self.dir = tmp / "case"
        shutil.copytree(T1, self.dir)
        self.man = yaml.safe_load((self.dir / "case.yaml").read_text())
        for ent in self.man["tables"].values():      # external tables referenced relative to the repo
            if ent["file"].startswith("../"):
                ent["file"] = str((T1 / ent["file"]).resolve())

    def table(self, name) -> pd.DataFrame:
        return pd.read_csv(self.dir / self.man["tables"][name]["file"])

    def put(self, name, df: pd.DataFrame):
        p = self.dir / self.man["tables"][name]["file"]
        df.to_csv(p, index=False, float_format="%.17g")
        self.man["tables"][name]["sha256"] = _sha(p)

    def load(self):
        (self.dir / "case.yaml").write_text(yaml.safe_dump(self.man, sort_keys=False))
        return load_case(self.dir)


@pytest.fixture
def edit(tmp_path):
    return CaseEdit(tmp_path)


def two_periods(e: CaseEdit, w1: float, w2: float):
    per = pd.DataFrame({"period_id": ["p1", "p2"], "weight_blocks": [w1, w2], "rep_kind": ["single", "single"],
                        "days_represented": [3 * w1, 3 * w2]})
    e.put("periods", per)
    load = e.table("load")
    e.put("load", pd.concat([load, load.assign(period_id="p2")], ignore_index=True))


# ------------------------------------------------------------- controls (the harness itself is sound)
def test_control_unmodified_case_loads(edit):
    assert edit.load().case_id == "T1"


def test_control_valid_two_period_case_loads(edit):
    two_periods(edit, D_Y / 3 - 60.0, 60.0)
    assert len(edit.load().periods) == 2


# ------------------------------------------------------------- weight identity
@pytest.mark.parametrize("delta", [1e-6, -1e-6, 0.5, -3.0])
def test_weight_sum_not_dy_over_3_raises(edit, delta):
    w = D_Y / 3 + delta
    per = edit.table("periods")
    per["weight_blocks"] = w
    per["days_represented"] = 3 * w
    edit.put("periods", per)
    with pytest.raises(ValueError):
        edit.load()


def test_weight_sum_within_1e9_does_not_raise(edit):
    per = edit.table("periods")
    per["weight_blocks"] = D_Y / 3 + 1e-11            # far inside the 1e-9 tolerance
    edit.put("periods", per)
    edit.load()


# ------------------------------------------------------------- weight floor
def test_weight_below_one_raises(edit):
    two_periods(edit, D_Y / 3 - 0.5, 0.5)               # sum is right; second period has w = 0.5 < 1
    with pytest.raises(ValueError):
        edit.load()


# ------------------------------------------------------------- dollar year
def test_missing_resource_dollar_year_raises(edit):
    res = edit.table("resources")
    res["dollar_year"] = res["dollar_year"].astype("float")
    res.loc[0, "dollar_year"] = float("nan")             # cost-bearing row without a dollar year
    edit.put("resources", res)
    with pytest.raises(ValueError):
        edit.load()


def test_missing_voll_dollar_year_raises(edit):
    del edit.man["voll_dollar_year"]                      # VOLL is a cost input: needs a dollar year
    with pytest.raises(ValueError):
        edit.load()


# ------------------------------------------------------------- time step
@pytest.mark.parametrize("dt", [0.5, 2.0, 0.25, 24.0])
def test_dt_not_one_raises(edit, dt):
    edit.man["dt_h"] = dt
    with pytest.raises(ValueError):
        edit.load()
