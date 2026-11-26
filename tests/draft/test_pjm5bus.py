"""Draft Gate 3 tests (prep P6), from docs/gates/gate-3.md (DRAFT) and formulation 7.4a. Never imports capex at module level.

Part 1: independent DC-OPF (scipy linprog/HiGHS) from cases/raw/pjm5bus CSVs, angle and PTDF form, plus self-checks
        against gate-3.md section 2 (these run now).
Part 2: model-facing tests, skipped until Gate 3 (P5a-P5f, section 4 health checks, M7-M10).
Sign conventions (documented): f_l = b_l (theta_o - theta_e) is positive from -> to. pi_n = dCost/dD_n (equality-row
dual; scipy `eqlin.marginals` is d obj / d b_eq, so no sign change). mu_l is the signed shadow price of line l's limit
with mu_l * f_l >= 0: mu_l = -m_fwd + m_rev where m_* are the (<=0) `ineqlin.marginals` of rows f<=F and -f<=F.
PTDF_{l,n} = d f_l / d inj_n with the withdrawal at the reference bus. Then pi_n = lambda_ref - sum_l PTDF_{l,n} mu_l.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import linprog

RAW = Path(__file__).resolve().parents[2] / "cases" / "raw" / "pjm5bus"
BASE_MVA = 100.0
LETTERS = list("ABCDE")


# =============================================================== Part 1: independent reference route
def load_raw():
    b = pd.read_csv(RAW / "case5_buses.csv")
    g = pd.read_csv(RAW / "case5_gens.csv")
    br = pd.read_csv(RAW / "case5_branches.csv")
    lim = br["rateA_MW_0_means_unlimited"].to_numpy(float)
    return dict(load=b["Pd_MW"].to_numpy(float), gbus=g["bus"].to_numpy(int) - 1, gmax=g["Pmax_MW"].to_numpy(float),
                gcost=g["c1_usd_per_MWh"].to_numpy(float), gname=g["li_bo_name"].tolist(),
                frm=br["from"].to_numpy(int) - 1, to=br["to"].to_numpy(int) - 1, x=br["x_pu"].to_numpy(float),
                rate=np.where(lim > 0, lim, np.inf), lname=(br["from_label"] + "-" + br["to_label"]).tolist())


def incidence(c):
    A = np.zeros((len(c["x"]), 5))
    A[np.arange(len(c["x"])), c["frm"]] = 1.0
    A[np.arange(len(c["x"])), c["to"]] = -1.0
    return A                                                   # (L, N): row = e_o - e_e


def ptdf(c, ref=0):
    """PTDF_{l,n} = d f_l / d inj_n, withdrawal at `ref` (column ref = 0). Built from reactances, not from the LP."""
    A, b = incidence(c), BASE_MVA / c["x"]                     # MW per rad: b_l = base/x
    Bbus = A.T @ np.diag(b) @ A
    keep = [n for n in range(5) if n != ref]
    X = np.zeros((5, 5))
    X[np.ix_(keep, keep)] = np.linalg.inv(Bbus[np.ix_(keep, keep)])
    return (np.diag(b) @ A) @ X


def solve_opf(form="angle", ref=0, drop_de=False, scale=1.0, c=None):
    c = c or load_raw()
    L, G = len(c["x"]), len(c["gmax"])
    rate = c["rate"].copy()
    if drop_de:
        rate[L - 1] = np.inf
    D = c["load"] * scale
    A, b = incidence(c), BASE_MVA / c["x"]                     # b in MW/rad (angles in rad, flows in MW)
    Cg = np.zeros((5, G))
    Cg[c["gbus"], np.arange(G)] = 1.0
    cost = np.r_[c["gcost"], np.zeros(5 if form == "angle" else 0)]
    if form == "angle":                                        # vars [g (G), theta (5)]; theta_ref fixed 0 by bounds
        Fm = np.diag(b) @ A                                    # flow = Fm @ theta
        Aeq = np.hstack([Cg, -A.T @ Fm])                       # G_n - sum_l A_ln f_l = D_n
        bounds = [(0, m) for m in c["gmax"]] + [(0, 0) if n == ref else (None, None) for n in range(5)]
        fl = np.hstack([np.zeros((L, G)), Fm])
    else:                                                      # vars [g]; f = PTDF (Cg g - D)
        P = ptdf(c, ref)
        Aeq = np.vstack([np.ones((1, G))])
        Aeq_b = np.array([D.sum()])
        bounds = [(0, m) for m in c["gmax"]]
        fl = P @ Cg
    fin = np.isfinite(rate)
    Aub = np.vstack([fl[fin], -fl[fin]])
    if form == "angle":
        res = linprog(cost, A_ub=Aub, b_ub=np.r_[rate[fin], rate[fin]], A_eq=Aeq, b_eq=D, bounds=bounds, method="highs")
    else:
        off = P @ D                                            # f = fl g - P D
        res = linprog(cost, A_ub=Aub, b_ub=np.r_[rate[fin] + off[fin], rate[fin] - off[fin]], A_eq=Aeq,
                      b_eq=Aeq_b, bounds=bounds, method="highs")
    assert res.status == 0, res.message
    g = res.x[:G]
    flow = (fl @ res.x) if form == "angle" else (fl @ g - P @ D)
    mf, mr = res.ineqlin.marginals[:fin.sum()], res.ineqlin.marginals[fin.sum():]
    mu = np.zeros(L)
    mu[fin] = -mf + mr
    if form == "angle":
        lmp = res.eqlin.marginals
    else:                                                      # lambda = balance dual; congestion via PTDF
        lmp = res.eqlin.marginals[0] - ptdf(c, ref).T @ mu
    return dict(obj=float(res.fun), g=g, flow=flow, mu=mu, lmp=np.asarray(lmp), D=D, rate=rate, ref=ref, c=c,
                inj=Cg @ g - D, binding=np.where(fin & (np.abs(np.abs(flow) - rate) < 1e-6))[0])


@pytest.fixture(scope="module")
def base():
    return solve_opf("angle", 0)


PUB_LMP = np.array([16.98, 26.38, 30.00, 39.94, 10.00])
PUB_G = np.array([40.0, 170.0, 323.49, 0.0, 466.51])


def test_ref_published_values(base):
    assert base["obj"] == pytest.approx(17479.90, abs=0.01)
    np.testing.assert_allclose(base["lmp"], PUB_LMP, atol=0.01)
    np.testing.assert_allclose(base["g"], PUB_G, atol=0.01)


def test_ref_only_de_binds_flow_e_to_d(base):
    assert base["binding"].tolist() == [5]
    assert base["flow"][5] == pytest.approx(-240.0, abs=1e-6)             # from D to E negative: E -> D


@pytest.mark.xfail(strict=True, reason="gate-3.md draft value 14,957.28 disagrees with independent route: got 14,957.2901 "
                   "(= 62.32204 x 240; off by 0.0101, just outside abs 0.01; likely rounding in the draft)")
def test_ref_congestion_surplus_published(base):
    rent = float(base["lmp"] @ (base["D"] - np.bincount(base["c"]["gbus"], base["g"], 5)))
    assert rent == pytest.approx(14957.28, abs=0.01)


def test_ref_de_shadow_price(base):
    assert abs(base["mu"][5]) == pytest.approx(62.32, abs=0.01)
    assert np.count_nonzero(np.abs(base["mu"]) > 1e-9) == 1
    assert base["mu"][5] * base["flow"][5] > 0                                # sign convention mu*f >= 0


def test_ref_vs_check_csv(base):
    chk = pd.read_csv(RAW / "case5_dcopf_check.csv")
    v = lambda item: chk[chk["item"] == item].set_index("id")["value"]
    assert base["obj"] == pytest.approx(float(v("cost_usd_per_h")["total"]), abs=1e-4)
    np.testing.assert_allclose(base["g"], v("Pg_MW").loc[base["c"]["gname"]].to_numpy(), atol=1e-4)
    np.testing.assert_allclose(base["lmp"], v("LMP_usd_per_MWh").loc[LETTERS].to_numpy(), atol=1e-4)
    np.testing.assert_allclose(base["flow"], v("flow_MW_from_to").loc[base["c"]["lname"]].to_numpy(), atol=1e-4)


def test_ref_angle_equals_ptdf(base):
    p = solve_opf("ptdf", 0)
    assert p["obj"] == pytest.approx(base["obj"], rel=1e-9)
    np.testing.assert_allclose(p["g"], base["g"], atol=1e-6)
    np.testing.assert_allclose(p["lmp"], base["lmp"], atol=1e-6)
    np.testing.assert_allclose(p["flow"], base["flow"], atol=1e-6)


@pytest.mark.parametrize("form", ["angle", "ptdf"])
@pytest.mark.parametrize("ref", range(5))
def test_ref_reference_bus_invariance(base, form, ref):
    r = solve_opf(form, ref)
    np.testing.assert_allclose(r["lmp"], base["lmp"], atol=1e-6)
    np.testing.assert_allclose(r["g"], base["g"], atol=1e-6)


def test_ref_uncongested():
    r = solve_opf("angle", 0, drop_de=True)
    np.testing.assert_allclose(r["lmp"], 30.0, atol=1e-6)
    np.testing.assert_allclose(r["g"], [40, 170, 190, 0, 600], atol=1e-6)    # Alta, Park City, Solitude, Sundance, Brighton
    assert len(r["binding"]) == 0 and np.abs(r["mu"]).max() < 1e-9


@pytest.mark.parametrize("form,ref", [("angle", 0), ("angle", 3), ("ptdf", 2)])
def test_ref_lmp_decomposition_identity(form, ref):
    r = solve_opf(form, ref)
    P = ptdf(r["c"], ref)
    np.testing.assert_allclose(r["lmp"], r["lmp"][ref] - P.T @ r["mu"], atol=1e-6)


def test_ref_congestion_rent_identity(base):
    for kw in [dict(), dict(scale=0.9), dict(scale=1.05)]:
        r = solve_opf("angle", 0, **kw)
        rent = float(r["lmp"] @ -r["inj"])
        assert rent == pytest.approx(float(r["mu"] @ r["flow"]), rel=1e-7)


def test_ref_kvl_from_reactances(base):
    # theta from the PTDF system (independent of the LP angles), then f_l - b_l (th_o - th_e) = 0
    c = base["c"]
    A, b = incidence(c), BASE_MVA / c["x"]
    keep = [1, 2, 3, 4]
    Bbus = A.T @ np.diag(b) @ A
    th = np.zeros(5)
    th[keep] = np.linalg.solve(Bbus[np.ix_(keep, keep)], base["inj"][keep])
    np.testing.assert_allclose(base["flow"] - b * (A @ th), 0.0, atol=1e-6)
    np.testing.assert_allclose(ptdf(c, 0) @ base["inj"], base["flow"], atol=1e-6)


# =============================================================== Part 2: model-facing (skipped until Gate 3)
LOAD_FACTORS = np.linspace(0.50, 1.10, 72)                    # P5e, fixed list
CASE_DIR = Path(__file__).resolve().parents[2] / "cases" / "pjm5bus"
SKIP = pytest.mark.skip(reason="DRAFT until Gate 3 (gate-3.md approved, tx.model=dcpf implemented)")
TOL = dict(obj_rel=1e-7, g=1e-4, lmp=1e-4, pub_lmp=0.01, pub_g=0.01)


def run_pjm5(tmp_path, form="angle", ref=0, drop_de=False, scale=None, tx="dcpf"):
    """Run capex on cases/pjm5bus with overrides; returns (tables dict, health, solved)."""
    import shutil
    import yaml
    from capex.run import output_tables, run_case          # imported lazily: Part 1 must not need capex
    cd = tmp_path / "case"
    shutil.copytree(CASE_DIR, cd)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    # SPEC-GAP: config key names for tx.model, dcpf form (angle|ptdf), reference bus, per-hour load factors.
    cfg["switches"] = {"tx.model": tx, "tx.dcpf_form": form, "tx.ref_bus": LETTERS[ref]}
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    if drop_de or scale is not None:
        # SPEC-GAP: pjm5 links.csv column for rating (ntc_fwd_mw/ntc_rev_mw assumed; blank = unlimited) and load.csv layout.
        ln = pd.read_csv(cd / "links.csv")
        if drop_de:
            ln.loc[ln["link_id"].eq("D-E"), ["ntc_fwd_mw", "ntc_rev_mw"]] = np.nan
            ln.to_csv(cd / "links.csv", index=False)
        if scale is not None:
            ld = pd.read_csv(cd / "load.csv")
            ld["demand_mw"] *= np.asarray(scale)[ld["t"].to_numpy() - 1] if np.ndim(scale) else scale
            ld.to_csv(cd / "load.csv", index=False)
    sv, health, _fp = run_case(cd, tmp_path / "out")
    return output_tables(sv, health), health, sv


def _bus_hour(t, col, hour=1):
    # SPEC-GAP: table `zone_hourly` with zone = bus letter, `lmp_usd_mwh` (as Gate 1); bus-level `zone_hourly` assumed.
    zh = t["zone_hourly"]
    return zh[zh["t"] == hour].set_index("zone").loc[LETTERS, col].to_numpy(float)


def _flows(t, hour=1):
    # SPEC-GAP: line output table name/columns: `line_hourly` with link_id, t, flow_mw, mu_usd_mwh assumed.
    lh = t["line_hourly"]
    return lh[lh["t"] == hour].set_index("link_id")


def _dispatch(t, hour=1):
    # SPEC-GAP: dispatch table column for MW output (`dispatch_mw` assumed), resource_id = Li & Bo name.
    d = t["dispatch"]
    return d[d["t"] == hour].set_index("resource_id").loc[load_raw()["gname"], "dispatch_mw"].to_numpy(float)


def _check(h, cid):
    c = h.checks
    return c[c["check_id"].str.startswith(cid)]               # SPEC-GAP: check ids kvl.recompute, ptdf.recompute, lmp.decomposition, ...


def _compare(t, ref, hour=1):
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh", hour), ref["lmp"], atol=TOL["lmp"])
    np.testing.assert_allclose(_dispatch(t, hour), ref["g"], atol=TOL["g"])


def _classes_expected(ref):
    """Class per bus from the independent solution: marginal units = gens strictly between bounds; a bus with a marginal
    unit is MARGINAL_UNIT, otherwise CONGESTION_LOOP when any line binds, else (uncongested) it follows the island."""
    g, c = ref["g"], ref["c"]
    marg = (g > 1e-6) & (g < c["gmax"] - 1e-6)
    has = np.isin(np.arange(5), c["gbus"][marg])
    if len(ref["binding"]) == 0:
        return ["MARGINAL_UNIT"] * 5
    return ["MARGINAL_UNIT" if h else "CONGESTION_LOOP" for h in has]


def _assert_price_setters(t, ref, hour=1):
    ps = t["price_setter"]
    ps = ps[ps["t"] == hour].set_index("zone").loc[LETTERS]
    assert not (ps["primary_class"] == "UNEXPLAINED").any()
    assert ps["primary_class"].tolist() == _classes_expected(ref)
    marg = (ref["g"] > 1e-6) & (ref["g"] < ref["c"]["gmax"] - 1e-6)
    mc = ref["c"]["gcost"][marg]
    for n in np.where(np.array(ps["primary_class"]) == "CONGESTION_LOOP")[0]:
        # SPEC-GAP: how alpha is exposed (column `loop_alpha` as {resource_id: alpha} dict per bus-hour assumed).
        a = ps.iloc[n]["loop_alpha"]
        w = np.array([a[nm] for nm in np.array(ref["c"]["gname"])[marg]], float)
        assert w.sum() == pytest.approx(1.0, abs=1e-9)
        assert float(w @ mc) == pytest.approx(ref["lmp"][n], abs=1e-6)       # tol_pi: SPEC-GAP value (1e-6 used)


def _assert_all_health_pass(h):
    bad = h.checks[h.checks["status"] != "pass"]
    assert bad.empty, bad


@SKIP
def test_p5a_base_angle(tmp_path, base):
    t, h, sv = run_pjm5(tmp_path, "angle")
    _compare(t, base)
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), PUB_LMP, atol=TOL["pub_lmp"])
    np.testing.assert_allclose(_dispatch(t), PUB_G, atol=TOL["pub_g"])
    f = _flows(t)
    assert f["flow_mw"]["D-E"] == pytest.approx(-240.0, abs=1e-4)
    assert (f["mu_usd_mwh"].abs() > 1e-9).sum() == 1
    # annual Z = hourly cost * 24 * D_y  (one 3-day period of 72 identical hours, w = D_y/3 -> sum = 17479.90*72*D_y/3)
    D_y = 365.0   # SPEC-GAP: D_y (days per modelled year) assumed 365
    assert float(sv.z_total) == pytest.approx(base["obj"] * 24 * D_y, rel=TOL["obj_rel"])
    _assert_price_setters(t, base)
    _assert_all_health_pass(h)


@SKIP
def test_p5b_ptdf_equals_angle(tmp_path, base):
    ta, _, sa = run_pjm5(tmp_path / "a", "angle")
    tb, hb, sb = run_pjm5(tmp_path / "b", "ptdf")
    assert float(sb.z_total) == pytest.approx(float(sa.z_total), rel=1e-9)
    np.testing.assert_allclose(_bus_hour(tb, "lmp_usd_mwh"), _bus_hour(ta, "lmp_usd_mwh"), atol=1e-6)
    np.testing.assert_allclose(_dispatch(tb), _dispatch(ta), atol=1e-6)
    _assert_price_setters(tb, base)
    _assert_all_health_pass(hb)


@SKIP
@pytest.mark.parametrize("ref", range(5))
def test_p5c_reference_bus_invariance(tmp_path, base, ref):
    t, h, _ = run_pjm5(tmp_path, "angle", ref=ref)
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), base["lmp"], atol=1e-6)
    np.testing.assert_allclose(_dispatch(t), base["g"], atol=1e-6)
    # SPEC-GAP: output column for the energy component (`lmp_energy_usd_mwh`) and congestion component.
    en, cg = _bus_hour(t, "lmp_energy_usd_mwh"), _bus_hour(t, "lmp_congestion_usd_mwh")
    assert en[0] == pytest.approx(base["lmp"][ref], abs=1e-6)               # lambda_ref = pi at the reference bus
    np.testing.assert_allclose(cg, base["lmp"] - base["lmp"][ref], atol=1e-6)
    _assert_price_setters(t, base)


@SKIP
def test_p5d_uncongested(tmp_path):
    ref = solve_opf("angle", 0, drop_de=True)
    t, h, _ = run_pjm5(tmp_path, "angle", drop_de=True)
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), 30.0, atol=0.01)
    np.testing.assert_allclose(_dispatch(t), [40, 170, 190, 0, 600], atol=0.01)
    _compare(t, ref)
    ps = t["price_setter"]
    assert (ps["primary_class"] == "MARGINAL_UNIT").all() and (ps["marginal_resource"] == "Solitude").all()  # SPEC-GAP column name
    assert (_flows(t)["mu_usd_mwh"].abs() < 1e-9).all()
    np.testing.assert_allclose(_bus_hour(t, "lmp_congestion_usd_mwh"), 0.0, atol=1e-6)    # decomposition in P5d
    _assert_all_health_pass(h)


@SKIP
def test_p5e_load_scan(tmp_path):
    t, h, _ = run_pjm5(tmp_path, "angle", scale=LOAD_FACTORS)
    for hr, s in enumerate(LOAD_FACTORS, start=1):
        ref = solve_opf("angle", 0, scale=float(s))
        _compare(t, ref, hr)
        _assert_price_setters(t, ref, hr)
    assert (t["price_setter"]["primary_class"] != "UNEXPLAINED").all()
    _assert_all_health_pass(h)


@SKIP
def test_p5f_transport_contrast_reported_only(tmp_path):
    t, h, _ = run_pjm5(tmp_path, tx="transport")           # NTC = rating; reported, not judged
    assert len(_flows(t)) == 6 and "flow_mw" in _flows(t)   # runs and writes flows; no assertion on values


# ---- section 4 health checks (each driven by an independent recomputation, not by the audit layer's verdict)
@SKIP
def test_h_kvl_recomputation(tmp_path, base):
    t, h, _ = run_pjm5(tmp_path)
    c = base["c"]
    A, b = incidence(c), BASE_MVA / c["x"]
    inj = np.bincount(c["gbus"], _dispatch(t), 5) - c["load"]
    # SPEC-GAP: bus angle output (`angle` table, theta_rad) needed for the f - B(theta_o - theta_e) recomputation.
    th = t["angle"].query("t == 1").set_index("zone").loc[LETTERS, "theta_rad"].to_numpy(float)
    f = _flows(t).loc[c["lname"], "flow_mw"].to_numpy(float)
    assert np.abs(f - b * (A @ th)).max() <= 1e-6
    assert (_check(h, "kvl")["status"] == "pass").all() and len(_check(h, "kvl")) >= 1


@SKIP
def test_h_ptdf_recomputation(tmp_path, base):
    t, h, _ = run_pjm5(tmp_path)
    c = base["c"]
    inj = np.bincount(c["gbus"], _dispatch(t), 5) - c["load"]
    f = _flows(t).loc[c["lname"], "flow_mw"].to_numpy(float)
    assert np.abs(ptdf(c, 0) @ inj - f).max() <= 1e-6
    assert (_check(h, "ptdf")["status"] == "pass").all() and len(_check(h, "ptdf")) >= 1


@SKIP
@pytest.mark.parametrize("drop", [False, True])
def test_h_lmp_decomposition_and_congestion_rent(tmp_path, base, drop):
    ref = solve_opf("angle", 0, drop_de=drop)
    t, h, _ = run_pjm5(tmp_path, drop_de=drop)
    mu = _flows(t).loc[ref["c"]["lname"], "mu_usd_mwh"].to_numpy(float)       # SPEC-GAP: mu sign convention under dcpf
    pi = _bus_hour(t, "lmp_usd_mwh")
    assert np.abs(pi - (pi[0] - ptdf(ref["c"], 0).T @ mu)).max() <= 1e-6
    f = _flows(t).loc[ref["c"]["lname"], "flow_mw"].to_numpy(float)
    assert float(pi @ -ref["inj"]) == pytest.approx(float(mu @ f), rel=1e-7)
    for cid in ("lmp.decomposition", "congestion_rent"):                         # SPEC-GAP: check ids
        assert (_check(h, cid)["status"] == "pass").all() and len(_check(h, cid)) >= 1


@SKIP
def test_h_line_duals_complementary_slackness(tmp_path, base):
    t, _h, _ = run_pjm5(tmp_path)
    f = _flows(t)
    rate = pd.Series(base["rate"], index=base["c"]["lname"]).loc[f.index]
    nb = f["flow_mw"].abs() < rate - 1e-6
    assert (f.loc[nb, "mu_usd_mwh"].abs() < 1e-9).all()                        # mu != 0 only at a rating


@SKIP
def test_h_islands_fixture_one_ref_angle_per_island(tmp_path):
    # SPEC-GAP: fixture = pjm5 with lines A-B, A-D... removed so buses split into two islands; how the audit layer
    # reports the `ref_angle` row count (check `dcpf.islands`: value = island count) is for the W-spec to define.
    t, h, sv = run_pjm5(tmp_path)
    pytest.fail("write fixture: two electrically separate parts; expect ref_angle count == island count == 2")


@SKIP
def test_h_conditioning_no_warn_on_p5a_to_p5e(tmp_path):
    for kw in (dict(), dict(form="ptdf"), dict(drop_de=True), dict(scale=LOAD_FACTORS)):
        _t, h, _ = run_pjm5(tmp_path / str(len(kw)) / str(kw.get("form", "")), **{k: v for k, v in kw.items()})
        c = h.checks
        assert not c[c["check_id"].str.startswith("conditioning")]["status"].isin(["warn", "fail"]).any()


@SKIP
def test_h_ranged_rows_f5_fix_in(tmp_path):
    # SPEC-GAP: only applies if PTDF writes flow limits as ranged rows; adapter test lives in gate-2 F5 tests.
    t, h, _ = run_pjm5(tmp_path, "ptdf")
    _assert_all_health_pass(h)


@SKIP
@pytest.mark.parametrize("name", ["T1", "T2a", "T2b", "T2c", "T3a", "T3b", "T4"])
def test_h_default_unchanged(tmp_path, name):
    from capex.run import run_case
    cd = Path(__file__).resolve().parents[2] / "cases" / name
    _sv, _h, fp = run_case(cd, tmp_path)
    # SPEC-GAP: compare against stored Gate-1 fingerprints (location of golden files) ignoring the tx.model config field.
    pytest.fail("compare fp to Gate 1 golden fingerprint except config.tx.model")


# ---- mutations M7-M10: each must make at least one health check fail (or the run raise a detected error)
# SPEC-GAP: mutation hook points (builder module/function names) are defined once the dcpf builder exists.
def _mutated_run(tmp_path, mutation):
    pytest.fail(f"SPEC-GAP: hook for mutation {mutation}")


@SKIP
@pytest.mark.parametrize("mutation", ["M7_reactance_x1.01_in_LP_only", "M8_kvl_sign_flip", "M9_ref_row_dropped",
                                      "M10_mu_sign_flipped_one_line"])
def test_mutations_caught(tmp_path, mutation):
    h = _mutated_run(tmp_path, mutation)
    failing = h.checks[h.checks["status"] == "fail"]
    assert not failing.empty, f"{mutation} was not caught by any health check"   # M9 may instead raise: SPEC-GAP
