"""Gate 4 mutation tests M13-M16 (docs/gates/gate-4.md section 4; formulation 7.4a.10 "F-0.4 mutation points").
Each mutant injects a fault into the LP or the audit adapter only and must make at least one named check FAIL (not raise);
every test has a clean control run and a vacuity guard (the mutated code path must have been hit), as for M7-M10.

| id  | hook used here                                                              | fault                                        | must fail                          |
| M13 | wrap capex.audit.loop.interval (the interval-LP entry; Bound.sense of rows) | flip the sense of the S2 storage row(s)      | price_setter.loop_interval         |
| M14 | wrap capex.run.build_lp                                                     | DC link gets a kvl row with x = 0.01 pu      | price_setter.link_inconsistent     |
| M15 | wrap capex.run.build_lp (PTDF form)                                         | drop f_k from the ptdf_flow rows             | ptdf.recompute                     |
| M16 | wrap capex.audit.loop.interval + highspy status stub                        | UNBOUNDED_OR_INFEASIBLE side mapped to NaN   | price_setter.loop_interval         |

SPEC-GAP-3 (hook names): formulation 7.4a.10 names `capex.run.build_lp` (M14/M15) but for M13/M16 only "the S2 row builder" and
"the adapter status map", with no module path. The F-0.3 code exposes `capex.audit.loop.interval(solver, marginal_phi, cost_b,
sign_k, bounds: list[Bound(phi, cost, sense)], target_phi)`; M13/M16 here wrap that public function (a storage row is recognised
by a Bound cost that is not any generator marginal cost). If G4-4 moves the interval LP, only the `_wrap_interval` helper needs
the new name; the vacuity guards fail loudly when the wrapped path is not hit. M16's effect (adapter returns NaN for an
unbounded side) is emulated by replacing +-inf in the returned interval by NaN, while a highspy-boundary stub forces
kUnboundedOrInfeasible on every tiny LP so that such a side exists.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest
import scipy.sparse as sp

import g4lib
from g4lib import check_row, dc_row, make_fixture, xf
from test_gate4_known_answers import b_h1a, b_s2b

GEN_MC = [14.0, 15.0, 30.0, 40.0, 10.0]


def _failing(h) -> list[str]:
    return h.checks.loc[h.checks["status"] == "fail", "check_id"].tolist()


def _run(cd, out):
    from capex.run import run_case
    _sv, h, _fp = run_case(cd, out)
    return h


def _control_clean(cd, out):
    h = _run(cd, out / "control")
    assert h.status == "pass", f"control run must be clean:\n{h.checks[h.checks['status'] != 'pass'][['check_id', 'status', 'detail']]}"


def append_row(lp, entries: dict, lo=0.0, hi=0.0):
    """Return a copy of `lp` with one extra row (column index -> coefficient) appended to a, row_lo, row_hi."""
    cols = list(entries)
    row = sp.csr_matrix(([entries[c] for c in cols], ([0] * len(cols), cols)), shape=(1, lp.a.shape[1]))
    return dataclasses.replace(lp, a=sp.vstack([lp.a, row]).tocsr(), row_lo=np.r_[lp.row_lo, lo], row_hi=np.r_[lp.row_hi, hi])


def test_mutation_plumbing_append_row_keeps_a_clean_run_clean(tmp_path, monkeypatch):
    """Runs now: appending an empty equality row (the M14 mechanism) must not by itself break the pjm5 run."""
    import capex.run as run_mod
    cd = make_fixture(tmp_path, form="angle", formulation="F-0.3")
    orig = run_mod.build_lp

    def build(case, scaling=None):
        lp = orig(case) if scaling is None else orig(case, scaling)
        return append_row(lp, {}, 0.0, 0.0)
    monkeypatch.setattr(run_mod, "build_lp", build)
    assert _run(cd, tmp_path / "out").status == "pass"


# ------------------------------------------------------------------------------------------------ M14
def test_m14_dc_link_given_a_kvl_row(tmp_path, monkeypatch):
    import capex.run as run_mod
    cd = b_h1a(50.0)(tmp_path)
    _control_clean(cd, tmp_path)
    orig = run_mod.build_lp
    seen = {}

    def build(case, scaling=None):
        lp = orig(case) if scaling is None else orig(case, scaling)
        a = lp.a.tolil()
        k = 6                                                       # dc_be is the 7th row of links.csv (6 AC rows first)
        fac = (1 / 0.01) / (1 / 0.0281)                             # x = 0.01 pu instead of ab's 0.0281 pu
        for t in range(72):
            r = lp.rows["kvl"].idx(0, 0, t)                         # reuse ab's scaled coefficients
            cf, ca, cb = (a[r, lp.cols["flow"].idx(0, 0, t)], a[r, lp.cols["theta"].idx(0, 0, t)], a[r, lp.cols["theta"].idx(1, 0, t)])
            assert cf != 0 and ca != 0 and cb != 0, "vacuity guard: ab kvl coefficients must exist"
            lp = append_row(lp, {lp.cols["flow"].idx(k, 0, t): cf, lp.cols["theta"].idx(1, 0, t): ca * fac,
                                 lp.cols["theta"].idx(4, 0, t): cb * fac})
        seen["hit"] = True
        return lp
    monkeypatch.setattr(run_mod, "build_lp", build)
    h = _run(cd, tmp_path / "mut")
    assert seen.get("hit")
    assert "price_setter.link_inconsistent" in _failing(h), f"M14 not caught; failing: {_failing(h)}"


# ------------------------------------------------------------------------------------------------ M15
def test_m15_dc_flow_dropped_from_ptdf_flow(tmp_path, monkeypatch):
    import capex.run as run_mod
    cd = b_h1a(50.0, form="ptdf")(tmp_path)
    _control_clean(cd, tmp_path)
    orig = run_mod.build_lp
    seen = {"n": 0}

    def build(case, scaling=None):
        lp = orig(case) if scaling is None else orig(case, scaling)
        a = lp.a.tolil()
        k = 6
        for t in range(72):
            c = lp.cols["flow"].idx(k, 0, t)
            for l in range(6):
                r = lp.rows["ptdf_flow"].idx(l, 0, t)
                if a[r, c] != 0:
                    a[r, c] = 0.0
                    seen["n"] += 1
        return dataclasses.replace(lp, a=a.tocsr())
    monkeypatch.setattr(run_mod, "build_lp", build)
    h = _run(cd, tmp_path / "mut")
    assert seen["n"] > 0, "vacuity guard: the DC flow must appear in ptdf_flow rows"
    assert "ptdf.recompute" in _failing(h), f"M15 not caught; failing: {_failing(h)}"


# ------------------------------------------------------------------------------------------------ M13 / M16
def _wrap_interval(monkeypatch, post=None, pre=None):
    """Wrap capex.audit.loop.interval; `pre(bounds) -> bounds` mutates the rows, `post(result) -> result` the returned interval."""
    import capex.audit.loop as loop
    orig = loop.interval
    hits = {"calls": 0, "mutated": 0}

    def wrapped(*args, **kwargs):
        args = list(args)
        if pre is not None:
            for i, a in enumerate(args):
                if isinstance(a, list) and a and hasattr(a[0], "sense"):
                    args[i] = pre(a, hits)
            for k, v in list(kwargs.items()):
                if isinstance(v, list) and v and hasattr(v[0], "sense"):
                    kwargs[k] = pre(v, hits)
        out = orig(*args, **kwargs)
        hits["calls"] += 1
        return post(out, hits) if post is not None else out
    monkeypatch.setattr(loop, "interval", wrapped)
    return hits


@xf("S2: storage rows in the case-(c) interval LP and the loop_interval check")
def test_m13_storage_row_sense_flipped(tmp_path, monkeypatch):
    cd = b_s2b(vom=100.0)(tmp_path)
    _control_clean(cd, tmp_path)

    def pre(bounds, hits):
        out = []
        for b in bounds:
            if min(abs(b.cost - mc) for mc in GEN_MC) > 1e-6:           # a storage row: its cost is v-based, not a generator MC
                b = b._replace(sense=-b.sense)
                hits["mutated"] += 1
            out.append(b)
        return out
    hits = _wrap_interval(monkeypatch, pre=pre)
    h = _run(cd, tmp_path / "mut")
    assert hits["calls"] > 0 and hits["mutated"] > 0, f"vacuity guard: no storage row reached the interval LP ({hits})"
    assert "price_setter.loop_interval" in _failing(h), f"M13 not caught; failing: {_failing(h)}"


@xf("S2c/F3-13: interval-LP status map (UNBOUNDED_OR_INFEASIBLE -> +-inf) and loop_interval")
def test_m16_unbounded_or_infeasible_mapped_to_nan(tmp_path, monkeypatch):
    import highspy
    cd = b_s2b(vom=100.0)(tmp_path)
    _control_clean(cd, tmp_path)
    orig_status = highspy.Highs.getModelStatus
    forced = {"n": 0}

    def fake(self):
        st = orig_status(self)
        if self.getNumCol() <= 6:                                  # the interval LPs are the only tiny LPs
            forced["n"] += 1
            return highspy.HighsModelStatus.kUnboundedOrInfeasible
        return st
    monkeypatch.setattr(highspy.Highs, "getModelStatus", fake)

    def post(out, hits):
        out = np.array(out, float)
        if np.isinf(out).any():
            hits["mutated"] += 1
            out[np.isinf(out)] = np.nan                           # the mutant: status UNBOUNDED_OR_INFEASIBLE -> NaN
        return out
    hits = _wrap_interval(monkeypatch, post=post)
    h = _run(cd, tmp_path / "mut")
    assert forced["n"] > 0 and hits["mutated"] > 0, f"vacuity guard: no unbounded side produced ({forced}, {hits})"
    assert "price_setter.loop_interval" in _failing(h), f"M16 not caught; failing: {_failing(h)}"
