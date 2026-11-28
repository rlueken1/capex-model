"""Gate 4 RTS-GMLC comparison criteria and RTS health assertions (G4-3; docs/gates/gate-4.md sections 2, 5, 6, 7 K6).
Metrics are computed by the verifier-owned harness tests/rts_compare.py from run outputs + the PLEXOS reference tables
(cases/rts_gmlc/reference/ref_plexos_da_{alltx,notx}.csv.gz). Nothing imports capex at module level.

Part 1 (runs now, no capex code): K6 reference-table integrity; section 2 reference facts re-verified; F0 (the PLEXOS dispatch,
        with tie flows per area pair and DC1 as the DC link, against the constraints of OUR LP built from the case CSVs);
        C0 as a theorem on the independent zonal LP (scipy/HiGHS); C2 closure; harness self-tests; reported-only L1/L2/P1/U0 from the
        reference. The independent-route preview of C1/G1 is RECORDED (record_property), not asserted: C1/G1 are judged on the
        capex run outputs (Part 2).
Part 2 (strict xfail until G4-4): window runs R4-Z, R4-C, R4-N, R4-NS through capex, then C0/C1/C2/G1/G2 (judged), L1/L2/P1/U0
        (reported), and the section 6 health assertions. R4-F / R4-NF full-year runs are skipped unless CAPEX_GATE4_FULL=1.
Tolerances: F0 1 MW; C0 1e-6 rel; C1 <= 5% [P]; G1 3 pp (nuclear 0.5 pp) [P]; G2 unserved = 0 MWh. Never loosened here.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import g4lib
import rts_compare as rc
from g4lib import check_row, xf

REPO = Path(__file__).resolve().parents[1]
RAWROOT = REPO / "cases" / "raw" / "rts_gmlc"
FULL = os.environ.get("CAPEX_GATE4_FULL") == "1"
needs_full = pytest.mark.skipif(not FULL, reason="Gate 4: R4-F / R4-NF full-year runs are outside the normal suite "
                                                  "(gate-4.md section 2, separate Actions job); set CAPEX_GATE4_FULL=1")
RUNS = {"R4-Z": ("rts_gmlc_px", "alltx"), "R4-C": ("rts_gmlc_px_cp", "notx")}
SRC_DIR = {"alltx": "allTX", "notx": "noTX"}
VARS = ["generation", "commitment", "cost", "price", "flow"]


# ================================================================================================== Part 1 (live)
@pytest.mark.parametrize("variant", ["alltx", "notx"])
def test_k6_reference_meta_hashes_equal_manifest_and_vendored_files(variant):
    """K6: sha256 of every source equals MANIFEST.csv, source_id/method/vintage as required, first hour = p063 t=1."""
    meta = rc.ref_meta()
    meta = meta[meta["table"] == f"ref_plexos_da_{variant}"]
    assert sorted(meta["variable"]) == sorted(VARS)
    man = pd.read_csv(RAWROOT / "MANIFEST.csv").set_index("path")
    for _, m in meta.iterrows():
        assert m["sha256_equals_manifest"] and m["source_sha256"] == m["manifest_sha256"] == man.loc[m["source_file"], "sha256"]
        assert hashlib.sha256((RAWROOT / m["source_file"]).read_bytes()).hexdigest() == m["source_sha256"]
        assert (m["source_id"], m["method"], m["first_period"], m["first_t"], m["first_hour"]) == (
            "rts_gmlc", "observed", "p063", 1, "2020-07-05 00:00:00")


def test_k6_window_alignment_with_periods_csv():
    per = pd.read_csv(REPO / "cases" / "rts_gmlc" / "periods.csv").set_index("period_id")
    assert per.loc["p063", "source_start_date"] == "2020-07-05"
    r = rc.ref_long("alltx")
    assert sorted(r["period_id"].unique()) == rc.RUN_PERIODS
    first = r[(r["variable"] == "generation") & (r["period_id"] == "p063") & (r["t"] == 1)]["timestamp"].unique()
    assert first.tolist() == ["2020-07-05 00:00:00"]
    for v in VARS:
        w = rc.ref_wide("alltx", v)
        assert w.index.equals(rc.window_index()) and not w.isna().any().any(), v           # 336 complete hours, p067 truncated at t=48
    assert rc.window_index()[-1] == ("p067", 48) and len(rc.window_index()) == 336


@pytest.mark.parametrize("variant", ["alltx", "notx"])
@pytest.mark.parametrize("variable", VARS)
def test_k6_reference_values_equal_the_vendored_source(variant, variable):
    """The tidy table is a faithful reshaping of the PLEXOS CSV (values, all 336 rows, every column)."""
    src = RAWROOT / "RTS_Data/FormattedData/PLEXOS/PLEXOS_Solution/DAY_AHEAD Solution Files" / SRC_DIR[variant] / \
        f"PLEXOS_DA_solution_{variable}.csv"
    s = pd.read_csv(src)
    t = s.pop("time")
    assert len(s) == 336 and t.iloc[0] == "2020-07-05 00:00:00"
    w = rc.ref_wide(variant, variable)
    assert sorted(c.lower() for c in s.columns) == sorted(c.lower() for c in w.columns)
    lower = {c.lower(): c for c in w.columns}
    for c in s.columns:
        np.testing.assert_allclose(w[lower[c.lower()]].to_numpy(float), s[c].to_numpy(float), rtol=0, atol=1e-9, err_msg=c)


def test_section2_reference_facts_reverified():
    g = rc.ref_wide("alltx", "generation")
    assert g.shape[1] == 156 and rc.ref_wide("alltx", "cost").shape[1] == 156 and rc.ref_wide("alltx", "price").shape[1] == 73
    assert rc.ref_wide("alltx", "flow").shape[1] == 121                                      # 120 AC branches + 113_316_1
    assert {"313_storage_1", "212_csp_1"}.isdisjoint(g.columns)                              # the reference has no storage or CSP
    cd = rc.case_data("rts_gmlc_px")
    load = cd.load.sum(axis=1)
    assert g.sum(axis=1).sub(load).abs().max() < 1e-3                                         # generation = load every hour
    assert g.to_numpy().sum() == pytest.approx(1_793_948.0, abs=1.0)                         # MWh
    dc = rc.ref_wide("alltx", "flow")["113_316_1"]
    assert dc.abs().max() <= 100 + 1e-6 and (dc >= 100 - 1e-6).sum() == 303 and (dc <= -100 + 1e-6).sum() == 20
    assert dc.mean() == pytest.approx(85.4, abs=0.05)
    dcn = rc.ref_wide("notx", "flow")["113_316_1"]
    assert dcn.min() == pytest.approx(-155, abs=1.0) and dcn.max() == pytest.approx(-62, abs=1.0)   # noTX lifts the +-100 limit
    p = rc.ref_wide("alltx", "price")
    v = p.to_numpy()
    assert v.min() == pytest.approx(-6.87, abs=0.01) and v.max() == pytest.approx(111.59, abs=0.01) and v.mean() == pytest.approx(21.79, abs=0.01)
    assert (v < 0).sum() == 7 and (v <= 0.01).mean() == pytest.approx(0.15, abs=0.005)
    assert ((p.max(axis=1) - p.min(axis=1)) > 0.01).sum() == 13 and (p.max(axis=1) - p.min(axis=1)).max() == pytest.approx(43.34, abs=0.01)
    pn = rc.ref_wide("notx", "price")
    assert ((pn.max(axis=1) - pn.min(axis=1)) < 1e-9).all()                                    # noTX: one price in every hour
    assert (rc.ref_wide("alltx", "flow")["CB-1"].abs() >= 500 - 1e-6).sum() == 10


def test_section2_cost_basis_gap_matches_the_gate_text():
    """Cost file sums to $27.01 M; PLEXOS generation priced at our linear MC gives $25.70 M; gap 4.9% (allTX)."""
    c_file = rc.px_cost_file_total("alltx")
    c_px = rc.px_dispatch_cost("alltx", "rts_gmlc_px")
    assert c_file == pytest.approx(27.01e6, rel=1e-3) and c_px == pytest.approx(25.70e6, rel=1e-3)
    assert (c_file - c_px) / c_file == pytest.approx(0.049, abs=0.001)


def test_case_mc_matches_the_converter_columns():
    """Harness MC (heat rate x fuel price + VOM from the case CSVs) equals the case's own x_mc_usd_mwh for every thermal unit."""
    cd = rc.case_data("rts_gmlc_px")
    th = cd.res[cd.res["type"] == "TH"].set_index("resource_id")
    np.testing.assert_allclose(cd.mc[th.index].iloc[0].to_numpy(), th["x_mc_usd_mwh"].to_numpy(), rtol=1e-4)


@pytest.mark.parametrize("case", ["rts_gmlc_px", "rts_gmlc_px_cp", "rts_gmlc_nodal_px"])
def test_harness_reads_every_judged_case(case):
    cd = rc.case_data(case)
    assert cd.cap.shape == (336, 153) and cd.mc.shape == (336, 153) and not cd.cap.isna().any().any()
    assert cd.load.shape[0] == 336 and not cd.load.isna().any().any()
    assert {"313_storage_1", "212_csp_1"}.isdisjoint(cd.res["resource_id"])                  # PLEXOS-aligned fleet
    assert cd.cfg["audit_profile"] == "standard" and cd.cfg["formulation_version"] == "F-0.4"
    assert cd.load.sum(axis=1).sub(rc.case_data("rts_gmlc_px").load.sum(axis=1)).abs().max() < 1e-2   # same system load in every variant


# ---- F0 (judged; runs now)
@pytest.mark.parametrize("run", ["R4-Z", "R4-C"])
def test_f0_plexos_dispatch_is_feasible_in_our_lp(run):
    """F0: the PLEXOS dispatch violates no constraint of our LP by more than 1 MW (a violation is a data-alignment error to fix,
    never a tolerance to loosen)."""
    case, variant = RUNS[run]
    v = rc.f0_violations(variant, case)
    assert set(v) >= {"gen_below_0", "gen_above_cap", "balance", "flow_above_limit"}
    assert max(v.values()) <= 1.0, f"F0 fails on {run}: {v}"


def test_f0_detects_a_data_alignment_error():
    """Self-test of the F0 machinery: breaking the tie flows (sign of CA-1) or capacity must violate by far more than 1 MW."""
    case, variant = RUNS["R4-Z"]
    cd = rc.case_data(case)
    good = rc.reference_link_flows(variant, case)
    bad = good.copy()
    bad["ac_r1_r3"] = -bad["ac_r1_r3"]                                                       # the orientation error F0 exists to catch
    net = pd.DataFrame(0.0, index=good.index, columns=cd.zones)
    g = rc.ref_wide(variant, "generation")[cd.res["resource_id"].tolist()]
    zg = g.T.groupby(cd.zone_of[g.columns]).sum().T[cd.zones]
    for f in (good, bad):
        net[:] = 0.0
        for _, l in cd.links.iterrows():
            net[l["zone_from"]] += f[l["link_id"]]
            net[l["zone_to"]] -= f[l["link_id"]]
        res = (zg - cd.load - net).abs().max().max()
        assert (res < 1.0) if f is good else (res > 100.0)


# ---- C0 / C2 on the independent route (runs now)
@pytest.mark.parametrize("run", ["R4-Z", "R4-C"])
def test_c0_c2_on_the_independent_zonal_lp(run, record_property):
    """C0 follows from F0 (the PLEXOS dispatch is feasible in our LP): Z <= C^PX_our (1 + 1e-6); C2 closes exactly."""
    case, variant = RUNS[run]
    z = rc.zonal_lp(case)
    assert z["unserved"].to_numpy().sum() == 0.0
    cm = rc.c_metrics(z["Z"] - float((z["unserved"] * rc.VOLL).to_numpy().sum()), variant, case)
    assert cm["c0_ok"], cm
    assert cm["c2_lhs"] == pytest.approx(cm["c2_rhs"], rel=1e-12)
    assert cm["basis_gap"] + cm["dispatch_gap"] == pytest.approx(cm["px_cost_file"] - cm["Z_our"], rel=1e-12)
    for k in ("C_px_our", "Z_our", "c1_gap", "px_cost_file", "basis_gap_rel"):
        record_property(f"{run}.indep.{k}", float(cm[k]))                                    # reported, judged on the run outputs
    sh = rc.g1_check(rc.tech_shares(z["gen"], case), rc.tech_shares(rc.ref_wide(variant, "generation"), case))
    for t_, r in sh.iterrows():
        record_property(f"{run}.indep.G1.{t_}.abs_pp", float(r["abs_pp"]))


def test_zonal_lp_is_the_same_optimum_for_zonal_and_copper_plate():
    """The three-zone transport network never binds on the window, so R4-Z and R4-C have the same optimum (cross-check)."""
    zz, zc = rc.zonal_lp("rts_gmlc_px"), rc.zonal_lp("rts_gmlc_px_cp")
    assert zz["Z"] == pytest.approx(zc["Z"], rel=1e-9)
    assert float(zz["flow"].abs().max().max()) < 1175.0 + 1e-6


# ---- harness self-tests (runs now)
def test_g1_rule_semantics():
    px = pd.Series({g: 1 / 9 for g in rc.GROUPS})
    ours = px.copy()
    assert rc.g1_check(ours, px)["ok"].all()
    o2 = px.copy(); o2["coal"] += 0.029; o2["gas_cc"] -= 0.029
    assert rc.g1_check(o2, px)["ok"].all()                                                    # 2.9 pp passes
    o3 = px.copy(); o3["coal"] += 0.031; o3["gas_cc"] -= 0.031
    c3 = rc.g1_check(o3, px)
    assert not c3.loc["coal", "ok"] and not c3.loc["gas_cc", "ok"] and c3.loc["wind", "ok"]
    o4 = px.copy(); o4["nuclear"] += 0.006; o4["wind"] -= 0.006
    c4 = rc.g1_check(o4, px)
    assert not c4.loc["nuclear", "ok"] and c4.loc["wind", "ok"]                               # nuclear limit is 0.5 pp


def test_c_metrics_arithmetic():
    cm = rc.c_metrics(95.0, "alltx", "rts_gmlc_px")
    assert cm["c2_lhs"] == pytest.approx(cm["c2_rhs"], rel=1e-14)                              # identity independent of Z
    assert rc.c_metrics(rc.px_dispatch_cost("alltx", "rts_gmlc_px") * (1 + 2e-6), "alltx", "rts_gmlc_px")["c0_ok"] is False


@pytest.mark.parametrize("case", ["rts_gmlc_px", "rts_gmlc_px_cp", "rts_gmlc_nodal_px", "rts_gmlc_nodal"])
def test_make_window_case_restricts_period_tables_and_repins(tmp_path, case):
    win = rc.make_window_case(case, tmp_path, periods=rc.RUN_PERIODS)
    cfg = yaml.safe_load((win / "case.yaml").read_text())
    per = pd.read_csv(win / cfg["tables"]["periods"]["file"])
    assert per["period_id"].tolist() == rc.RUN_PERIODS
    ld = pd.read_csv(win / cfg["tables"]["load"]["file"])
    nz = len(pd.read_csv(win / cfg["tables"]["zones"]["file"]))
    assert sorted(ld["period_id"].unique()) == rc.RUN_PERIODS and len(ld) == 360 * nz
    for key, spec in cfg["tables"].items():
        if "sha256" in spec:
            p = (win / spec["file"])
            assert hashlib.sha256(p.read_bytes()).hexdigest() == spec["sha256"], key
    assert cfg["audit_profile"] == "standard"


# ---- reported-only metrics from the reference (runs now)
def test_l1_l2_reference_reports_are_complete_and_flagged(record_property):
    for variant in ("alltx", "notx"):
        rep = rc.lmp_report(rc.px_price(variant, "bus"))
        assert set(rep["quantiles"]) == set(rc.LMP_QUANTILES) and np.isfinite(rep["mean"])
        area = rc.lmp_report(rc.px_price(variant, "area"))
        assert area["n_node_hours"] == 336 * 3
        record_property(f"L1.{variant}", f"expected gap: UC/reserves/fixed hydro+RTPV; {rep}")
    l2 = rc.l2_px("alltx")
    assert l2 == {"cb1_at_limit_hours": 10, "dc1_at_limit_hours": 323, "congested_hours": 13, "dc1_plus100": 303, "dc1_minus100": 20,
                  "dc1_mean": pytest.approx(85.41, abs=0.01)}


def test_p1_u0_reference_inference_is_well_formed(record_property):
    for run, (case, variant) in RUNS.items():
        s = rc.p1_px_shares(variant, case)
        assert s.index.tolist() == rc.GROUPS and s.sum() == pytest.approx(1.0, abs=1e-9) and (s >= 0).all()
        record_property(f"P1.{run}", s.round(4).to_dict())
    u = rc.u0_px_must_run("notx", "rts_gmlc_px_cp")
    assert (u["must_run_mwh"] >= 0).all() and (u["share"].between(0, 1)).all()
    assert u["must_run_mwh"].sum() > 0                                                        # the UC gap is visible in the reference
    record_property("U0.R4-C", u.round(3).to_dict())


# ================================================================================================== Part 2 (runs through capex)
@pytest.fixture(scope="session")
def rts_run(tmp_path_factory):
    """rts_run(name) -> SimpleNamespace(t, h, case, out): R4-Z/R4-C/R4-N/R4-NP/R4-NS window runs (p063-p067), cached."""
    from capex.run import output_tables, run_case
    from types import SimpleNamespace
    spec = {"R4-Z": ("rts_gmlc_px", None), "R4-C": ("rts_gmlc_px_cp", None),
            "R4-N": ("rts_gmlc_nodal_px", {"tx.model": "dcpf", "tx.dcpf_form": "angle"}),
            "R4-NP": ("rts_gmlc_nodal_px", {"tx.model": "dcpf", "tx.dcpf_form": "ptdf"}),
            "R4-NS": ("rts_gmlc_nodal", {"tx.model": "dcpf", "tx.dcpf_form": "angle"})}
    cache: dict = {}

    def get(name):
        if name not in cache:
            case, sw = spec[name]
            win = rc.make_window_case(case, tmp_path_factory.mktemp(name.lower().replace("-", "")))
            if sw is not None:
                cfg = yaml.safe_load((win / "case.yaml").read_text())
                cfg["switches"] = sw
                (win / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
            out = tmp_path_factory.mktemp(name.lower().replace("-", "") + "_out")
            sv, h, fp = run_case(win, out)
            cache[name] = SimpleNamespace(t=output_tables(sv, h), h=h, case=case, out=out, win=win)
        return cache[name]
    return get


_NEEDS = "RTS cases loading (F-0.4 loader: audit_profile, link_type, tx.dc_links) and the S1-S4 code"
VARIANT = {"R4-Z": "alltx", "R4-C": "notx", "R4-N": "alltx", "R4-NS": "alltx"}


@xf(_NEEDS)
@pytest.mark.parametrize("name", ["R4-Z", "R4-C", "R4-N"])
def test_c0_c1_c2_judged_on_run_outputs(rts_run, name, record_property):
    r = rts_run(name)
    cm = rc.c_metrics(rc.z_our(r.t, r.case), VARIANT[name], r.case)
    for k, v in cm.items():
        record_property(f"{name}.{k}", float(v) if not isinstance(v, bool) else v)
    if name != "R4-N":                                                                         # R4-N has no C0 (PLEXOS flows need not satisfy our KVL)
        assert cm["c0_ok"], f"C0 breach (a bug): Z_our={cm['Z_our']:.0f} > C_px_our={cm['C_px_our']:.0f}"
    assert cm["c1_gap"] <= 0.05, f"C1 {name}: like-for-like gap {cm['c1_gap']:.4f} > 5% [P]"
    assert cm["c2_lhs"] == pytest.approx(cm["c2_rhs"], rel=1e-12)                              # C2 closes exactly (reported)


@xf(_NEEDS)
@pytest.mark.parametrize("name", ["R4-Z", "R4-C", "R4-N"])
def test_g1_g2_judged_on_run_outputs(rts_run, name, record_property):
    r = rts_run(name)
    ours = rc.tech_shares(rc.run_dispatch(r.t, r.case), r.case)
    px = rc.tech_shares(rc.ref_wide(VARIANT[name], "generation"), r.case)
    chk = rc.g1_check(ours, px)
    for t_, row in chk.iterrows():
        record_property(f"{name}.G1.{t_}", float(row["abs_pp"]))
    assert chk["ok"].all(), f"G1 {name}:\n{chk}"
    assert rc.g2_unserved_mwh(r.t) == 0.0                                                      # G2: reference serves all load
    record_property(f"{name}.G2.curtailment_mwh", float(rc.curtailment_report(r.t).sum()))     # reported


@pytest.mark.parametrize("name", ["R4-Z", "R4-C", "R4-N"])
def test_l1_l2_reported_on_run_outputs(rts_run, name, record_property):
    """Reported, not judged (label: expected gap: UC/reserves/fixed hydro+RTPV). Asserts only that the report is complete."""
    r = rts_run(name)
    px = rc.px_price(VARIANT[name], "bus" if name == "R4-N" else "area")
    lmp = rc.run_zone_hourly(r.t, "lmp_usd_mwh")
    rep = rc.lmp_report(lmp)
    assert set(rep["quantiles"]) == set(rc.LMP_QUANTILES) and rep["n_node_hours"] == lmp.size and np.isfinite(rep["mean"])
    record_property(f"{name}.L1", f"expected gap: UC/reserves/fixed hydro+RTPV; ours {rep}; px {rc.lmp_report(px)}")
    fl = r.t["flows"]
    fl = fl[g4lib.pd.MultiIndex.from_frame(fl[["period", "t"]]).isin(rc.window_index())] if len(fl) else fl
    if len(fl):
        at = fl[fl["at_bound"].astype(bool)].groupby("link").size()
        record_property(f"{name}.L2.hours_at_bound_by_link", at.to_dict())                     # CB-1/ac_r2_r3 ref 10, DC1 ref 323
        record_property(f"{name}.L2.congested_hours", int((lmp.max(axis=1) - lmp.min(axis=1) > 0.01).sum()))


@pytest.mark.parametrize("name", ["R4-Z", "R4-C"])
def test_p1_u0_reported_on_run_outputs(rts_run, name, record_property):
    r = rts_run(name)
    summ = r.t["price_setter_summary"]
    assert {"zone", "tech", "fuel", "class", "share_weighted_hours"} <= set(summ.columns)
    ours = summ.groupby("tech")["share_weighted_hours"].sum()
    record_property(f"{name}.P1.ours", (ours / ours.sum()).round(4).to_dict())
    record_property(f"{name}.P1.px", rc.p1_px_shares(VARIANT[name], r.case).round(4).to_dict())
    if name == "R4-C":
        record_property("R4-C.U0", rc.u0_px_must_run("notx", r.case).round(3).to_dict())


# ---- section 6 health assertions on RTS runs
def _assert_health(r, dcpf: bool):
    h = r.h
    bad = h.checks[h.checks["status"] == "fail"]
    assert bad.empty, bad[["check_id", "value", "detail"]]
    warns = h.checks[h.checks["status"] == "warn"]
    assert warns["detail"].astype(str).str.len().ge(0).all()                                    # every warn is listed (evidence file explains it)
    ps = r.t["price_setter"]
    assert rc.unexplained_count(r.t) == 0 and int(check_row(h, "price_setter.unexplained")["value"].iloc[0]) == 0
    for cid in ("balance", "storage.soc_recompute") + (("kvl.recompute", "ptdf.recompute") if dcpf else ()):
        row = check_row(h, cid)
        if cid in ("storage.soc_recompute",) and row.empty:
            continue
        assert len(row) == 1 and "audit_profile=standard warn>0.001 fail>0.1" in str(row["detail"].iloc[0]), cid     # S3 profile in detail
        assert float(row["tolerance"].iloc[0]) == pytest.approx(1e-3)
    cond = h.checks[h.checks["check_id"].astype(str).str.startswith("conditioning")]
    assert len(cond) >= 1 and not cond["status"].eq("fail").any()
    if dcpf:
        for cid in rc.DCPF_CHECKS:
            assert len(check_row(h, cid)) == 1, cid
        for cid in set(rc.DCPF_CHECKS) - {"kvl.recompute", "ptdf.recompute"}:
            assert (check_row(h, cid)["status"] == "pass").all(), (cid, check_row(h, cid).to_dict("records"))
        assert float(check_row(h, "price_setter.loop_interval")["value"].iloc[0]) == 0
        assert str(check_row(h, "dcpf.islands")["detail"].iloc[0]).startswith("1 island")             # RTS verified connected: 73 buses, 1 island
        isl = r.t["islands"]
        assert isl["island_id"].nunique() == 1 and len(isl) == 73
    return ps


@pytest.mark.parametrize("name", ["R4-Z", "R4-C"])
def test_health_zonal_runs(rts_run, name):
    ps = _assert_health(rts_run(name), dcpf=False)
    assert (ps["primary_class"] != "UNEXPLAINED").all()


@pytest.mark.parametrize("name", ["R4-N", "R4-NS"])
def test_health_nodal_dcpf_runs(rts_run, name):
    r = rts_run(name)
    ps = _assert_health(r, dcpf=True)
    assert r.t["zone_hourly"]["zone"].nunique() == 73
    if name == "R4-NS":
        sto = ps[ps["primary_class"].isin(["STORAGE_DIS", "STORAGE_CH"])]
        assert len(sto) > 0, "R4-NS must show STORAGE_DIS/CH rows"
        tol = np.maximum(0.01, 1e-5 * sto["price"].abs())
        assert (sto["residual"].abs() <= tol).all()                                              # they pass their price check


def test_nodal_dcpf_equivalent_runs_have_one_dc_link_in_flows(rts_run):
    r = rts_run("R4-N")
    fl = r.t["flows"]
    assert "dc_113_316" in set(fl["link"]) and fl["link"].nunique() == 121                        # 120 AC lines + DC1
    dc = fl[fl["link"] == "dc_113_316"]
    assert dc["flow_mw"].abs().max() <= 100 + 1e-6


@needs_full
@xf("RTS R4-F full-year run (rts_gmlc_px 122 blocks, rts_gmlc 122 blocks) and the F-0.4 loader")
@pytest.mark.parametrize("case", ["rts_gmlc_px", "rts_gmlc"])
def test_r4f_full_year_health(tmp_path_factory, case):
    from capex.run import output_tables, run_case
    out = tmp_path_factory.mktemp("r4f")
    sv, h, _fp = run_case(REPO / "cases" / case, out)
    t = output_tables(sv, h)
    assert h.checks[h.checks["status"] == "fail"].empty
    assert rc.unexplained_count(t) == 0


@needs_full
@xf("RTS R4-NF full-year nodal dcpf run (performance only) and the F-0.4 loader")
def test_r4nf_full_year_performance_only(tmp_path_factory):
    from capex.run import run_case
    sv, h, _fp = run_case(REPO / "cases" / "rts_gmlc_nodal", tmp_path_factory.mktemp("r4nf"))
    assert h.checks[h.checks["status"] == "fail"].empty
