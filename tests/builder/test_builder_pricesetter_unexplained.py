"""Builder smoke test (W5-fix1): a zone-hour whose first matched class fails its price check is UNEXPLAINED
(formulation section 4, step 2), both in the table and in the summary."""
import dataclasses
from pathlib import Path

import numpy as np

from capex.audit.duals import economic_duals
from capex.audit.pricesetter import price_setter
from capex.data import load_case
from capex.run import solve_case

CASES = Path(__file__).resolve().parents[2] / "cases"


def test_failed_price_check_is_unexplained() -> None:
    sv = solve_case(load_case(CASES / "T1"))
    eco = economic_duals(sv)
    base = price_setter(sv, eco)
    assert base.unexplained == 0
    pi = eco.pi.copy()
    pi[0, 0, 0] += 5.0                                   # MARGINAL_UNIT hour, price now off the unit's MC
    res = price_setter(sv, dataclasses.replace(eco, pi=pi))
    row = res.table.iloc[0]
    assert "MARGINAL_UNIT" in row["all_classes"] and row["primary_class"] == "UNEXPLAINED"
    assert res.unexplained >= 1
    hours = lambda s, c: s.loc[s["class"] == c, "weighted_hours"].sum()
    w = sv.case.w[0]
    unexplained_w = res.table.loc[res.table["primary_class"] == "UNEXPLAINED", "weight_hours"].sum()
    assert np.isclose(hours(res.summary, "UNEXPLAINED"), unexplained_w)
    assert np.isclose(hours(res.summary, "MARGINAL_UNIT"), hours(base.summary, "MARGINAL_UNIT") - w)
