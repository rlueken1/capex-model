"""W5-fix1-test (finding F1): an hour whose first matched class fails its price check is UNEXPLAINED.

Written from docs/formulation.md section 4 (Step 1: first matched class is primary; Step 2: "If no class matches, or the
matched class fails its price check, the zone-hour is UNEXPLAINED") and docs/gates/gate-1.md section 3 (price-setter
report: UNEXPLAINED = 0 on a clean solve; shares of weighted hours sum to 1 per zone).

Fixture: solve a canonical case, then call the public `price_setter(sv, eco)` with an Economics whose energy price pi is
shifted by +5 $/MWh in selected hours that are baseline MARGINAL_UNIT hours. Every MARGINAL_UNIT / storage price check
there then fails by 5 >> tol_pi, while the primal solution (and so every class condition) is untouched. Nothing is
loosened: the spec's tol_pi = max(0.01, 1e-5|pi|) is far below the shift.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from capex.audit.duals import economic_duals
from capex.audit.pricesetter import price_setter

SHIFT = 5.0
CASES_UNDER_TEST = ["T1", "S1", "S2"]


def _setup(canon, name, n_hours=3):
    c = canon(name)
    sv = c.sv
    eco = economic_duals(sv)
    base = price_setter(sv, eco)
    tab = base.table
    zone0 = sv.case.zones[0]
    cand = tab[(tab.zone == zone0) & (tab.primary_class == "MARGINAL_UNIT")]
    assert len(cand) >= 1, "fixture needs at least one baseline MARGINAL_UNIT hour"
    chosen = cand.iloc[:n_hours]
    pi = eco.pi.copy()
    pidx = {p: i for i, p in enumerate(sv.case.periods)}
    for r in chosen.itertuples():
        pi[sv.case.zones.index(r.zone), pidx[r.period_id], r.t - 1] += SHIFT
    pert = price_setter(sv, dataclasses.replace(eco, pi=pi))
    return sv, base, pert, chosen


def _key(df):
    return df.set_index(["zone", "period_id", "t"])


@pytest.mark.parametrize("name", CASES_UNDER_TEST)
def test_control_unperturbed_has_no_unexplained(canon, name):
    sv = canon(name).sv
    base = price_setter(sv, economic_duals(sv))
    assert base.unexplained == 0
    assert (base.table.primary_class != "UNEXPLAINED").all()
    assert "UNEXPLAINED" not in set(base.summary["class"])


@pytest.mark.parametrize("name", CASES_UNDER_TEST)
def test_failed_price_check_hours_are_unexplained(canon, name):
    sv, base, pert, chosen = _setup(canon, name)
    b, p = _key(base.table), _key(pert.table)
    idx = [(r.zone, r.period_id, r.t) for r in chosen.itertuples()]
    # (1) perturbed hours are labelled UNEXPLAINED (spec section 4 Step 2), and counted
    assert (p.loc[idx, "primary_class"] == "UNEXPLAINED").all()
    assert pert.unexplained == len(idx)
    # a class was matched (condition holds) yet it is not the label: the failed-check situation, not "no class matched"
    assert (p.loc[idx, "all_classes"].str.len() > 0).all()
    assert (p.loc[idx, "all_classes"].str.contains("MARGINAL_UNIT")).all()
    # (3a) every other hour keeps its baseline class
    rest = p.index.difference(idx)
    assert (p.loc[rest, "primary_class"] == b.loc[rest, "primary_class"]).all()
    assert (p.loc[rest, "primary_class"] != "UNEXPLAINED").all()


@pytest.mark.parametrize("name", CASES_UNDER_TEST)
def test_summary_attributes_failed_hours_to_unexplained(canon, name):
    sv, base, pert, chosen = _setup(canon, name)
    w_bad = float(chosen["weight_hours"].sum())
    zone0 = chosen.zone.iloc[0]
    sb, sp_ = base.summary, pert.summary

    def wh(s, cls):
        return float(s.loc[(s["class"] == cls) & (s.zone == zone0), "weighted_hours"].sum())

    # (2) UNEXPLAINED gets exactly the failed hours' weighted hours ...
    assert wh(sp_, "UNEXPLAINED") == pytest.approx(w_bad, rel=1e-12)
    # ... and the original class loses exactly that much (not credited to MARGINAL_UNIT any more)
    assert wh(sp_, "MARGINAL_UNIT") == pytest.approx(wh(sb, "MARGINAL_UNIT") - w_bad, abs=1e-9)
    # every other class is unchanged
    for cls in set(sb["class"]) - {"MARGINAL_UNIT"}:
        assert wh(sp_, cls) == pytest.approx(wh(sb, cls), abs=1e-9)
    # (3b) weights still sum to the total weighted hours, and shares to 1 per zone
    total = float(sv.case.w.sum() * 72)
    for z in sv.case.zones:
        zs = sp_[sp_.zone == z]
        assert zs["weighted_hours"].sum() == pytest.approx(total, rel=1e-12)
        assert zs["share_weighted_hours"].sum() == pytest.approx(1.0, abs=1e-12)
    # UNEXPLAINED setter list is empty: no resource is credited
    row = _key(pert.table).loc[(chosen.zone.iloc[0], chosen.period_id.iloc[0], int(chosen.t.iloc[0]))]
    assert row["setter_ids"] == ""
    assert "UNEXPLAINED" in row["flags"]
