"""W6-fix1-test: reporting amendments 3 and 4 (DECISIONS 35, 36; formulation F-0.2 section 4 CAPACITY_RENT attribution,
section 8 items 5, 10, 11; data-schema section 5; data-sources "Assumptions book format").

Expected values come from the spec and closed-form toy cases, not from the implementation:
  M1  a CAPACITY_RENT hour's setters = the rent-set units with an interior build (INVESTMENT_MARGIN); else the highest-MC
      unit(s) of the rent set (DEGENERATE); only setters share the hour in the summary; the whole rent set is in
      `rent_ids`; `setter_cost` stays the lower interval end, max MC of the at-cap units.
  M2  candidates with build_status `at_zero` carry rent_note `non-unique (bound)`; nothing else carries a note.
  C2  assumptions.md header: run_id / fingerprint equal to run.json, case, base dollar year, and the toy banner iff no
      input cell is observed/derived/estimated.
  Output tables carry no `run_id` column.
"""
from __future__ import annotations

import dataclasses
import json

import numpy as np
import pandas as pd
import pytest

from capex.audit.duals import economic_duals
from capex.audit.pricesetter import price_setter
from capex.run import run_case
from healthlib import CASES, W1, Spec, th, write_case

BANNER = "Toy case: all inputs assumed; numbers are illustrative, not PJM estimates."


def _split(s):
    return [] if not isinstance(s, str) or s == "" else s.split(",")


def _run(case_dir, out):
    run_case(case_dir, out)
    return out


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """Output directories of T1, T2c, T3b and a designed M1 case."""
    out = {n: _run(CASES / n, tmp_path_factory.mktemp(f"w6_{n}")) for n in ("T1", "T2c", "T3b", "T4")}
    # M1: candidate `base` (MC 20, cfix 150k, interior build) + existing `old` (30 MW, MC 40).  In the peak hour both are
    # at cap with rho > 0: rent set {base, old}.  base has the interior build, old the HIGHER MC, so the two rules differ.
    d = np.r_[np.full(36, 80.0), np.full(24, 120.0), np.full(12, 200.0)]
    spec = Spec(["A"], [W1], np.array([[d]]), [th("base", "A", xmax=np.inf, mc=20.0, cfix=150_000.0),
                                                th("old", "A", k0=30, mc=40.0)], voll=10_000.0)
    out["M1"] = _run(write_case(spec, tmp_path_factory.mktemp("w6_M1_case")), tmp_path_factory.mktemp("w6_M1"))
    return out


def _tab(runs, case, name):
    return pd.read_csv(runs[case] / f"{name}.csv", dtype={"setter_ids": str, "rent_ids": str})


# --------------------------------------------------------------------------- M1
def test_m1_interior_build_is_setter_rent_set_is_full(runs):
    """Designed case: rent set {base, old}; interior build `base` is the setter although `old` has the higher MC."""
    ps = _tab(runs, "M1", "price_setter")
    cr = ps[ps.primary_class == "CAPACITY_RENT"]
    assert len(cr) >= 1, "fixture must contain a CAPACITY_RENT hour"
    for r in cr.itertuples():
        assert _split(r.rent_ids) == ["base", "old"], "full rent set (sorted ids) belongs in rent_ids"
        assert _split(r.setter_ids) == ["base"], "setter = interior build, not the highest-MC at-cap unit"
        assert "INVESTMENT_MARGIN" in _split(r.flags)
        assert "DEGENERATE" not in _split(r.flags)
        assert r.setter_cost == pytest.approx(40.0, abs=1e-9), "setter_cost stays the interval lower end (max MC at cap)"
        assert r.price_lo == pytest.approx(40.0, abs=1e-9) and r.price_hi == pytest.approx(10_000.0)
        assert r.price >= r.setter_cost - 0.01 and r.residual == pytest.approx(r.price - 40.0, abs=1e-6)
    # the summary credits only the setter: `old` gets no CAPACITY_RENT hours, `base` gets all of them
    sm = _tab(runs, "M1", "price_setter_summary")
    cr_rows = sm[sm["class"] == "CAPACITY_RENT"]
    assert set(cr_rows.tech) == {"base"}
    assert cr_rows.weighted_hours.sum() == pytest.approx(W1 * len(cr), rel=1e-9)


@pytest.mark.parametrize("case", ["T1", "T3b", "M1"])
def test_m1_structural_invariants(runs, case):
    """Spec invariants on every case: rent_ids empty outside CAPACITY_RENT; setters subset of rent set; interior builds
    in the rent set are exactly the setters when present (T1/T3b: the interior builds are base, peaker)."""
    ps = _tab(runs, case, "price_setter")
    rents = pd.read_csv(runs[case] / "rents.csv").set_index("resource_id")
    interior = {r for r, s in rents.build_status.items() if s == "interior"}
    non_cr = ps[ps.primary_class != "CAPACITY_RENT"]
    assert all(_split(x) == [] for x in non_cr.rent_ids), "rent_ids must be empty for every other class"
    cr = ps[ps.primary_class == "CAPACITY_RENT"]
    assert len(cr) >= 1
    for r in cr.itertuples():
        S, setters = _split(r.rent_ids), _split(r.setter_ids)
        assert S == sorted(S) and set(setters) <= set(S) and setters
        if set(S) & interior:
            assert set(setters) == set(S) & interior
            assert "INVESTMENT_MARGIN" in _split(r.flags)


def test_m1_t3b_closed_form(runs):
    """T3b (gate-1.md section 2): hour 48 CAPACITY_RENT/INVESTMENT_MARGIN, pi = 921.92; the interior-built peaker sets it."""
    ps = _tab(runs, "T3b", "price_setter")
    cr = ps[ps.primary_class == "CAPACITY_RENT"]
    assert list(cr.t) == [48]
    r = cr.iloc[0]
    assert r.price == pytest.approx(921.92, abs=0.01)
    assert _split(r.setter_ids) == ["peaker"] and "INVESTMENT_MARGIN" in _split(r["flags"])
    assert "peaker" in _split(r.rent_ids)


def test_m1_degenerate_highest_mc_setter(tmp_path):
    """No interior build (all existing): the setter is the highest-MC unit of the rent set; ties share; sub-tag DEGENERATE.

    The solver reports the lower interval end on real solves (tie class), so the degenerate vertex is made explicit: the
    solved fixed-fleet case (t=72 demand = total capacity, every unit at cap) is classified with pi moved to 100 inside the
    optimal interval [60, VOLL] and rho_r = pi - MC_r (stationarity for at-cap units)."""
    k = {"g1": (100, 20.0), "g2": (50, 60.0), "g2b": (30, 60.0), "g3": (40, 40.0)}
    d = np.full(72, 50.0)
    d[71] = sum(v[0] for v in k.values())
    spec = Spec(["A"], [W1], np.array([[d]]), [th(i, "A", k0=c, mc=m) for i, (c, m) in k.items()], voll=10_000.0)
    sv, _, _ = run_case(write_case(spec, tmp_path / "c"), tmp_path / "o")
    eco = economic_duals(sv)
    ids = list(sv.case.gen.ids) if hasattr(sv.case.gen, "ids") else [r["id"] for r in spec.resources]
    pi_new = 100.0
    pi = eco.pi.copy()
    pi[0, 0, 71] = pi_new
    rho = eco.rho.copy()
    for i, rid in enumerate(ids):
        rho[i, 0, 71] = pi_new - k[rid][1]
    ps = price_setter(sv, dataclasses.replace(eco, pi=pi, rho=rho))
    row = ps.table[(ps.table.t == 72)].iloc[0]
    assert row.primary_class == "CAPACITY_RENT", row.to_dict()
    assert _split(row.rent_ids) == ["g1", "g2", "g2b", "g3"]
    assert _split(row.setter_ids) == ["g2", "g2b"], "highest MC (60), tie within tol_pi shares"
    assert "DEGENERATE" in _split(row["flags"]) and "INVESTMENT_MARGIN" not in _split(row["flags"])
    assert row.setter_cost == pytest.approx(60.0) and row.price_lo == pytest.approx(60.0)
    assert ps.unexplained == 0
    sm = ps.summary
    cr = sm[sm["class"] == "CAPACITY_RENT"].set_index("tech").weighted_hours
    assert set(cr.index) == {"g2", "g2b"}
    assert cr["g2"] == pytest.approx(W1 / 2) and cr["g2b"] == pytest.approx(W1 / 2), "hour split equally among setters only"


# --------------------------------------------------------------------------- M2
@pytest.mark.parametrize("case", ["T1", "T2c", "T3b", "T4"])
def test_m2_rent_note_exactly_for_at_zero(runs, case):
    r = pd.read_csv(runs[case] / "rents.csv", dtype={"rent_note": str})
    assert "rent_note" in r.columns and "build_status" in r.columns
    note = r.rent_note.fillna("")
    at_zero = r.build_status == "at_zero"
    assert (note[at_zero] == "non-unique (bound)").all()
    assert (note[~at_zero] == "").all(), "no other row may carry a rent_note"


def test_m2_t2c_storage_at_zero_is_flagged(runs):
    r = pd.read_csv(runs["T2c"] / "rents.csv").set_index("resource_id")
    assert r.loc["bat", "build_status"] == "at_zero" and r.loc["bat", "rent_note"] == "non-unique (bound)"
    assert r.loc[["g1", "g2"], "rent_note"].isna().all()
    # interval of formulation section 10: combined rent R^P + 4 R^E in [15,465.19, 20,000]; rent <= cost
    assert r.loc["bat", "excess_rent"] <= 1e-6


def test_m2_t1_built_candidates_unflagged(runs):
    r = pd.read_csv(runs["T1"] / "rents.csv").set_index("resource_id")
    assert set(r.build_status) == {"interior"} and r.rent_note.isna().all()


def test_m2_generator_candidate_at_zero(tmp_path):
    """A candidate peaker too expensive to ever run is at_zero and flagged."""
    d = np.r_[np.full(36, 80.0), np.full(36, 100.0)]
    spec = Spec(["A"], [W1], np.array([[d]]), [th("g", "A", k0=200, mc=30.0),
                                                th("cand", "A", xmax=100, mc=200.0, cfix=500_000.0)])
    out = _run(write_case(spec, tmp_path / "c"), tmp_path / "o")
    r = pd.read_csv(out / "rents.csv").set_index("resource_id")
    assert r.loc["cand", "build_status"] == "at_zero" and r.loc["cand", "rent_note"] == "non-unique (bound)"
    assert r.loc["g", "build_status"] == "existing" and pd.isna(r.loc["g", "rent_note"])


# --------------------------------------------------------------------------- C2
@pytest.mark.parametrize("case", ["T1", "T2c", "T3b", "T4", "M1"])
def test_c2_assumptions_header(runs, case):
    out = runs[case]
    run = json.loads((out / "run.json").read_text())
    text = (out / "assumptions.md").read_text()
    lines = text.split("\n")
    first_section = next(i for i, l in enumerate(lines) if l.startswith("## "))
    header = lines[:first_section]
    assert lines[0].startswith("# ")
    assert header.count(f"- run_id: {run['run_id']}") == 1
    assert sum(l.startswith("- run_id: ") for l in lines) == 1, "run_id is the only per-run line, once"
    assert f"- fingerprint: {run['fingerprint']}" in header
    assert f"- case: {run['case_id']}" in header
    assert "- base dollar year: 2024" in header
    assert BANNER in header, "all-assumed toy case needs the exact banner in the run header"
    assert text.count(BANNER) == 1


def test_c2_banner_absent_when_inputs_observed(tmp_path):
    """The banner is conditional: a case with an observed input cell must not carry it."""
    import shutil
    case = tmp_path / "c"
    shutil.copytree(CASES / "T1", case)
    import yaml
    man = yaml.safe_load((case / "case.yaml").read_text())
    for ent in man["tables"].values():
        ent.pop("sha256", None)
        if ent["file"].startswith("../"):
            ent["file"] = str((CASES / "T1" / ent["file"]).resolve())
    res = pd.read_csv(case / man["tables"]["resources"]["file"])
    res["method"] = "observed"
    res.to_csv(case / man["tables"]["resources"]["file"], index=False)
    (case / "case.yaml").write_text(yaml.safe_dump(man, sort_keys=False))
    out = _run(case, tmp_path / "o")
    text = (out / "assumptions.md").read_text()
    assert BANNER not in text
    run = json.loads((out / "run.json").read_text())
    assert f"- run_id: {run['run_id']}" in text and f"- fingerprint: {run['fingerprint']}" in text


# --------------------------------------------------------------------------- DECISIONS 36
def test_no_table_has_run_id_column(runs):
    for case in ("T1", "T4"):
        for p in runs[case].glob("*.csv"):
            header = p.read_text().split("\n", 1)[0].split(",")
            assert "run_id" not in header, p.name
        assert "run_id" in json.loads((runs[case] / "run.json").read_text())


def test_per_run_values_only_in_run_json_and_run_id_line(tmp_path):
    """Two runs of one case: all files except run.json are byte-identical once the run_id line is dropped; the raw books
    differ in exactly that line (run_ids are random per run)."""
    a, b = _run(CASES / "T1", tmp_path / "a"), _run(CASES / "T1", tmp_path / "b")
    ja, jb = (json.loads((x / "run.json").read_text()) for x in (a, b))
    assert ja["run_id"] != jb["run_id"] and ja["fingerprint"] == jb["fingerprint"]
    assert sorted(p.name for p in a.iterdir()) == sorted(p.name for p in b.iterdir())
    for p in a.iterdir():
        if p.name in ("run.json", "assumptions.md"):
            continue
        assert p.read_bytes() == (b / p.name).read_bytes(), f"{p.name} must not hold per-run values"
    la, lb = (a / "assumptions.md").read_text().split("\n"), (b / "assumptions.md").read_text().split("\n")
    assert len(la) == len(lb)
    assert [i for i, (x, y) in enumerate(zip(la, lb)) if x != y] == [next(i for i, l in enumerate(la) if l.startswith("- run_id: "))]
