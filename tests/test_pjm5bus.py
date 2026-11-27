"""Gate 3 verifier tests (G3-2): PJM 5-bus `dcpf` option. Written from docs/gates/gate-3.md and formulation F-0.3
section 7.4a only (never from src/capex expected values).

Part 1 (passes now): independent DC-OPF reference route (scipy/HiGHS, angle and PTDF form) from cases/raw/pjm5bus,
        self-checks of gate-3.md section 2, the spec's alpha example, and K2 (case5.m sha256 = manifests).
Part 2 (G3-3, markers removed at G3-3): model-facing tests P5a-P5f, section 4 health checks, islands fixture, loader rules,
        mutations M7-M10. They need `tx.model = dcpf` and `cases/pjm5bus/`; they were strict xfail until G3-3 landed and the
        verifier removed the markers once all passed.
Part 3 (passes now): Gate-2 identity under `transport` against tests/golden/gate2/ (7.4a.9).

Sign conventions (7.4a.5): f_l = b_l (theta_o - theta_e), + = zone_from -> zone_to. pi_n = dCost/dD_n. mu_l signed with
mu_l f_l >= 0 (D-E: f = -240, mu = -62.32). PTDF H_{l,n} = d f_l / d inj_n, balancing withdrawal at the reference bus;
pi_n = lambda_ref - sum_l H_{l,n} mu_l. Never loosen a tolerance to make a test pass.
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml
from scipy.optimize import linprog

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "cases" / "raw" / "pjm5bus"
CASE_DIR = REPO / "cases" / "pjm5bus"
GOLDEN = REPO / "tests" / "golden" / "gate2"
BASE_MVA = 100.0
LETTERS = list("ABCDE")
LINKS = ["ab", "ad", "ae", "bc", "cd", "de"]                    # 7.4a.11: from -> to as case5
RES_IDS = ["alta", "park_city", "solitude", "sundance", "brighton"]
D_Y = 365.0                                                     # pjm5 model_year 2025 (7.4a.11)



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


def solve_opf(form="angle", ref=0, drop_de=False, scale=1.0, c=None, drop=()):
    """Independent DC-OPF. `drop` = line indices removed (angle form only; `ref` may then be a list, one per island)."""
    c = c or load_raw()
    if drop:
        keep = [i for i in range(len(c["x"])) if i not in set(drop)]
        c = {**c, **{k: (np.asarray(c[k])[keep] if k != "lname" else [c[k][i] for i in keep])
                     for k in ("frm", "to", "x", "rate", "lname")}}
    L, G = len(c["x"]), len(c["gmax"])
    rate = c["rate"].copy()
    if drop_de:
        rate[L - 1] = np.inf
    D = c["load"] * scale
    A, b = incidence(c), BASE_MVA / c["x"]                     # b in MW/rad (angles in rad, flows in MW)
    Cg = np.zeros((5, G))
    Cg[c["gbus"], np.arange(G)] = 1.0
    cost = np.r_[c["gcost"], np.zeros(5 if form == "angle" else 0)]
    refs = list(ref) if isinstance(ref, (list, tuple)) else [ref]
    if form == "angle":                                        # vars [g (G), theta (5)]; theta_ref fixed 0 by bounds
        Fm = np.diag(b) @ A                                    # flow = Fm @ theta
        Aeq = np.hstack([Cg, -A.T @ Fm])                       # G_n - sum_l A_ln f_l = D_n
        bounds = [(0, m) for m in c["gmax"]] + [(0, 0) if n in refs else (None, None) for n in range(5)]
        fl = np.hstack([np.zeros((L, G)), Fm])
    else:                                                      # vars [g]; f = PTDF (Cg g - D)
        P = ptdf(c, refs[0])
        Aeq = np.ones((1, G))
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
    mu[fin] = -mf + mr                                         # mu f >= 0 (signed shadow price)
    if form == "angle":
        lmp = res.eqlin.marginals
    else:                                                      # lambda = balance dual; congestion via PTDF
        lmp = res.eqlin.marginals[0] - ptdf(c, refs[0]).T @ mu
    return dict(obj=float(res.fun), g=g, flow=flow, mu=mu, lmp=np.asarray(lmp), D=D, rate=rate, ref=ref, c=c,
                inj=Cg @ g - D, binding=np.where(fin & (np.abs(np.abs(flow) - rate) < 1e-6))[0])


def marginal_set(r):
    """Generators strictly between their bounds in the independent solution."""
    g, c = r["g"], r["c"]
    return np.where((g > 1e-6) & (g < c["gmax"] - 1e-6))[0]


def congested_lines(r):
    return np.where(np.abs(r["mu"]) > 1e-7)[0]


def alpha_ref(r):
    """Loop weights alpha_n = phi_n Phi^{-1} (7.4a.7 case (a)), independent of capex. Returns {bus: {gen_idx: alpha}} or
    None when |marginal buses| != |binding lines| + 1 (not case (a))."""
    c, marg, K = r["c"], marginal_set(r), congested_lines(r)
    buses = sorted({int(c["gbus"][i]) for i in marg})
    if len(K) == 0 or len(buses) != len(K) + 1:
        return None
    H = ptdf(c, r["ref"] if isinstance(r["ref"], int) else 0)
    Phi = np.array([np.r_[1.0, -H[K, b]] for b in buses])
    Pinv = np.linalg.inv(Phi)
    out = {}
    for n in range(5):
        a = np.r_[1.0, -H[K, n]] @ Pinv
        out[n] = {int(i): float(a[buses.index(int(c["gbus"][i]))] / sum(int(c["gbus"][j]) == int(c["gbus"][i]) for j in marg))
                  for i in marg}
    return out


@pytest.fixture(scope="module")
def base():
    return solve_opf("angle", 0)


PUB_LMP = np.array([16.98, 26.38, 30.00, 39.94, 10.00])
PUB_G = np.array([40.0, 170.0, 323.49, 0.0, 466.51])


def test_ref_ids_match_spec_resolution():
    c = load_raw()
    assert [n.lower().replace(" ", "_") for n in c["gname"]] == RES_IDS
    assert [n.lower().replace("-", "") for n in c["lname"]] == LINKS
    assert [round(float(v), 4) for v in c["x"]] == [0.0281, 0.0304, 0.0064, 0.0108, 0.0297, 0.0297]
    np.testing.assert_allclose(c["load"], [0, 300, 300, 400, 0])


def test_ref_published_values(base):
    assert base["obj"] == pytest.approx(17479.90, abs=0.01)
    np.testing.assert_allclose(base["lmp"], PUB_LMP, atol=0.01)
    np.testing.assert_allclose(base["g"], PUB_G, atol=0.01)


def test_ref_only_de_binds_flow_e_to_d(base):
    assert base["binding"].tolist() == [5]
    assert base["flow"][5] == pytest.approx(-240.0, abs=1e-6)             # from D to E negative: E -> D


def test_ref_congestion_surplus_published(base):
    rent = float(base["lmp"] @ (base["D"] - np.bincount(base["c"]["gbus"], base["g"], 5)))
    assert rent == pytest.approx(14957.29, abs=0.01)                      # gate-3.md section 2 (G3-1 correction, DECISIONS 48)
    assert rent == pytest.approx(62.32204 * 240, abs=0.01)


def test_gate3_doc_states_corrected_surplus():
    txt = (REPO / "docs" / "gates" / "gate-3.md").read_text()
    stated = txt.split("Merchandising (congestion) surplus")[1].split("so the D")[0]
    assert "14,957.29" in stated and "14,957.28" not in stated


def test_ref_de_shadow_price_and_sign(base):
    assert base["mu"][5] == pytest.approx(-62.32, abs=0.01)               # 7.4a.11: f = -240, mu ~ -62.32
    assert np.count_nonzero(np.abs(base["mu"]) > 1e-9) == 1
    assert base["mu"][5] * base["flow"][5] > 0                            # mu f >= 0


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
    # theta from the reduced B system (independent of the LP angles), then f_l - b_l (th_o - th_e) = 0
    c = base["c"]
    A, b = incidence(c), BASE_MVA / c["x"]
    keep = [1, 2, 3, 4]
    Bbus = A.T @ np.diag(b) @ A
    th = np.zeros(5)
    th[keep] = np.linalg.solve(Bbus[np.ix_(keep, keep)], base["inj"][keep])
    np.testing.assert_allclose(base["flow"] - b * (A @ th), 0.0, atol=1e-6)
    np.testing.assert_allclose(ptdf(c, 0) @ base["inj"], base["flow"], atol=1e-6)


def test_ref_alpha_matches_spec_example_and_is_reference_invariant():
    """7.4a.7 example: M={solitude, brighton}, K={de}; A (.348868,.651132), B (.819223,.180777), D (1.497137,-.497137)."""
    want = {0: (0.348868, 0.651132), 1: (0.819223, 0.180777), 3: (1.497137, -0.497137)}
    for ref in range(5):
        a = alpha_ref(solve_opf("angle", ref))
        for n, (s, b) in want.items():
            assert a[n][2] == pytest.approx(s, abs=1e-6) and a[n][4] == pytest.approx(b, abs=1e-6)
        for n in range(5):
            assert sum(a[n].values()) == pytest.approx(1.0, abs=1e-12)
        assert a[2] == pytest.approx({2: 1.0, 4: 0.0}, abs=1e-12) and a[4] == pytest.approx({2: 0.0, 4: 1.0}, abs=1e-12)
    r = solve_opf("angle", 0)
    for n in range(5):                                            # pi_n = sum alpha c  (loop price)
        assert sum(w * r["c"]["gcost"][i] for i, w in alpha_ref(r)[n].items()) == pytest.approx(r["lmp"][n], abs=1e-6)


def test_ref_islands_fixture_known_answer():
    """pjm5 minus ad, bc, de: islands {A,B,E} (ref A) and {C,D} (ref C); LMP 10 and 40; 25,800 $/h (7.4a.11)."""
    r = solve_opf("angle", [0, 2], drop=(1, 3, 5))
    np.testing.assert_allclose(r["lmp"], [10, 10, 40, 40, 10], atol=1e-6)
    np.testing.assert_allclose(r["g"], [0, 0, 520, 180, 300], atol=1e-6)               # Brighton serves B; solitude at max
    assert r["obj"] == pytest.approx(25800.0, rel=1e-9)


# ---- K2 (gate-3.md 4a): case5.m sha256 equals the pin in the manifests
def _manifest_sha(path: Path, file: str) -> str:
    rows = pd.read_csv(path)
    key = "file"
    return rows.loc[rows[key] == file, "sha256"].iloc[0]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_k2_case5m_hash_equals_manifests():
    got = _sha(RAW / "case5.m")
    assert got == _manifest_sha(RAW / "MANIFEST.csv", "case5.m")
    assert got == _manifest_sha(REPO / "data" / "manifests" / "pjm5.csv", "case5.m")
    assert (RAW / "case5.m").stat().st_size == int(pd.read_csv(RAW / "MANIFEST.csv").set_index("file").loc["case5.m", "bytes"])


def test_k2_licence_hash_equals_manifests():
    got = _sha(RAW / "LICENSE_MATPOWER")
    assert got == _manifest_sha(RAW / "MANIFEST.csv", "LICENSE_MATPOWER")
    assert got == _manifest_sha(REPO / "data" / "manifests" / "pjm5.csv", "LICENSE_MATPOWER")


def test_k2_detects_a_changed_file(tmp_path):
    """The comparison used above must fail when the file changes (K2: 'fails if the file changes')."""
    p = tmp_path / "case5.m"
    p.write_bytes((RAW / "case5.m").read_bytes() + b"\n% tampered")
    assert _sha(p) != _manifest_sha(RAW / "MANIFEST.csv", "case5.m")


def test_ref_scan_hours_are_uncongested_or_unique_alpha():
    """P5e precondition: no hour is degenerate (marginal buses = binding lines + 1, nothing within 1e-3 MW of a bound),
    so the expected class and alpha per bus-hour are well defined from the independent route."""
    n_loop = 0
    for s in np.linspace(0.50, 1.10, 72):
        r = solve_opf("angle", 0, scale=float(s))
        g, gmax = r["g"], r["c"]["gmax"]
        assert not ((np.abs(g) < 1e-3) & (np.abs(g) > 0)).any() and not ((np.abs(g - gmax) < 1e-3) & (np.abs(g - gmax) > 0)).any()
        assert len(marginal_set(r)) >= 1
        if len(congested_lines(r)) == 0:
            continue
        assert alpha_ref(r) is not None
        n_loop += 1
    assert n_loop == 51                                            # factors >= 0.6775 are congested (D-E binding)


# =============================================================== Part 2: model-facing (markers removed at G3-3)
LOAD_FACTORS = np.linspace(0.50, 1.10, 72)                    # P5e, fixed list
TOL = dict(obj_rel=1e-7, g=1e-4, lmp=1e-4, pub_lmp=0.01, pub_g=0.01)


def stage_case(src: Path, tmp: Path, name: str | None = None) -> Path:
    """Copy a case into tmp/cases/<name> with tmp/data -> repo data, so relative '../../data/...' table paths resolve."""
    dst = tmp / "cases" / (name or src.name)
    shutil.copytree(src, dst)
    if not (tmp / "data").exists():
        (tmp / "data").symlink_to(REPO / "data")
    return dst


def repin(cd: Path) -> None:
    """Refresh case.yaml table sha256 pins for tables that live inside the case dir (after the test edits a CSV)."""
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    for spec in cfg.get("tables", {}).values():
        f = spec.get("file", "")
        if "sha256" in spec and not f.startswith(".."):
            spec["sha256"] = _sha(cd / f)
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))


def make_pjm5(tmp: Path, form="angle", ref=0, drop_de=False, scale=None, tx="dcpf", drop_links=(), switches=None,
              links_edit=None) -> Path:
    cd = stage_case(CASE_DIR, tmp)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    if switches is not None:
        cfg["switches"] = switches
    elif tx == "dcpf":
        cfg["switches"] = {"tx.model": "dcpf", "tx.dcpf_form": form, "tx.ref_bus": LETTERS[ref] if isinstance(ref, int) else list(ref)}
    else:
        cfg["switches"] = {"tx.model": tx}
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    ln = pd.read_csv(cd / "links.csv")
    if drop_de:
        ln.loc[ln["link_id"].eq("de"), ["ntc_fwd_mw", "ntc_rev_mw"]] = np.nan          # blank = unlimited (7.4a.11)
    if drop_links:
        ln = ln[~ln["link_id"].isin(drop_links)]
    if links_edit is not None:
        ln = links_edit(ln)
    ln.to_csv(cd / "links.csv", index=False)
    if scale is not None:
        ld = pd.read_csv(cd / "load.csv")                                              # load factors per t (7.4a.11)
        ld["demand_mw"] *= np.asarray(scale)[ld["t"].to_numpy() - 1] if np.ndim(scale) else scale
        ld.to_csv(cd / "load.csv", index=False)
    repin(cd)
    return cd


@pytest.fixture(scope="session")
def pj(tmp_path_factory):
    """pj(**make_pjm5 kwargs) -> SimpleNamespace(t=tables, h=health, sv=Solved, case_dir, out); cached per session."""
    from capex.run import output_tables, run_case          # lazily: Part 1 must not need capex
    cache: dict = {}

    def get(**kw):
        key = repr(sorted((k, tuple(v) if isinstance(v, np.ndarray) else v) for k, v in kw.items()))
        if key not in cache:
            tmp = tmp_path_factory.mktemp("pjm5")
            cd = make_pjm5(tmp, **kw)
            sv, health, fp = run_case(cd, tmp / "out")
            cache[key] = SimpleNamespace(t=output_tables(sv, health), h=health, sv=sv, fp=fp, case_dir=cd, out=tmp / "out")
        return cache[key]
    return get


def _hr(df, hour=1):
    return df[df["t"] == hour]


def _bus_hour(t, col, hour=1):
    return _hr(t["zone_hourly"], hour).set_index("zone").loc[LETTERS, col].to_numpy(float)


def _flows(t, hour=1):
    return _hr(t["flows"], hour).set_index("link").loc[LINKS]


def _dispatch(t, hour=1):
    return _hr(t["dispatch"], hour).set_index("resource").loc[RES_IDS, "g_mw"].to_numpy(float)


def _check(h, cid):
    c = h.checks
    return c[c["check_id"] == cid]


def _compare(t, ref, hour=1):
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh", hour), ref["lmp"], atol=TOL["lmp"])
    np.testing.assert_allclose(_dispatch(t, hour), ref["g"], atol=TOL["g"])


def _classes_expected(ref):
    """Class per bus from the independent solution (7.4a.7 / 7.4a.11): an island-hour with no mu != 0 is uncongested and
    follows the island rule (all buses MARGINAL_UNIT); otherwise a bus with a marginal unit is MARGINAL_UNIT, others
    CONGESTION_LOOP (case (a))."""
    c = ref["c"]
    if len(congested_lines(ref)) == 0:
        return ["MARGINAL_UNIT"] * 5
    has = np.isin(np.arange(5), c["gbus"][marginal_set(ref)])
    return ["MARGINAL_UNIT" if h else "CONGESTION_LOOP" for h in has]


def _setters_expected(ref):
    c, marg = ref["c"], marginal_set(ref)
    if len(congested_lines(ref)) == 0:
        return [RES_IDS[marg[0]] if len(marg) == 1 else None] * 5
    return [next((RES_IDS[i] for i in marg if c["gbus"][i] == n), None) for n in range(5)]


def _assert_price_setters(t, ref, hour=1):
    ps = _hr(t["price_setter"], hour).set_index("zone").loc[LETTERS]
    assert not (ps["primary_class"] == "UNEXPLAINED").any()
    assert ps["primary_class"].tolist() == _classes_expected(ref)
    for n, want in enumerate(_setters_expected(ref)):
        if want is not None and ps["primary_class"].iloc[n] == "MARGINAL_UNIT":
            assert ps["setter_ids"].iloc[n] == want
    pl = _hr(t["price_setter_loop"], hour)
    loops = [n for n in range(5) if ps["primary_class"].iloc[n] == "CONGESTION_LOOP"]
    assert sorted(pl["zone"].unique()) == sorted(LETTERS[n] for n in loops)
    if not loops:
        return
    al = alpha_ref(ref)
    assert al is not None, "scan hour is not case (a): independent route cannot give unique alpha"
    marg = marginal_set(ref)
    for n in loops:
        rows = pl[pl["zone"] == LETTERS[n]].set_index("resource_id")
        assert sorted(rows.index) == sorted(RES_IDS[i] for i in marg)
        w = np.array([rows.loc[RES_IDS[i], "alpha"] for i in marg], float)
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        assert float(w @ ref["c"]["gcost"][marg]) == pytest.approx(ref["lmp"][n], abs=1e-6)
        for i in marg:
            assert rows.loc[RES_IDS[i], "alpha"] == pytest.approx(al[n][int(i)], abs=1e-6)
        assert ps["binding_links"].iloc[n] == "de" and "CONGESTED" in str(ps["flags"].iloc[n])


def _assert_all_health_pass(h):
    bad = h.checks[h.checks["status"] != "pass"]
    assert bad.empty, bad


def test_p5a_base_angle(pj, base):
    r = pj(form="angle")
    t, h = r.t, r.h
    _compare(t, base)
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), PUB_LMP, atol=TOL["pub_lmp"])
    np.testing.assert_allclose(_dispatch(t), PUB_G, atol=TOL["pub_g"])
    f = _flows(t)
    assert f["flow_mw"]["de"] == pytest.approx(-240.0, abs=1e-4)
    assert f["congestion_rent_usd_mwh"]["de"] == pytest.approx(base["mu"][5], abs=1e-4)         # signed, mu f >= 0
    assert (f["congestion_rent_usd_mwh"].abs() > 1e-9).sum() == 1
    assert f["at_bound"].astype(bool).tolist() == [False] * 5 + [True]
    obj = t["objective"].query("component == 'total'")["value_usd_yr"].iloc[0]
    assert obj == pytest.approx(base["obj"] * 24 * D_Y, rel=TOL["obj_rel"])                    # 17,479.90 x 24 x D_y
    _assert_price_setters(t, base)
    _assert_all_health_pass(h)
    for cid in ("kvl.recompute", "ptdf.recompute", "lmp.decomposition", "congestion_rent", "dcpf.line_duals",
                "dcpf.islands", "price_setter.loop_alpha"):
        assert len(_check(h, cid)) == 1 and (_check(h, cid)["status"] == "pass").all(), cid


def test_p5a_defaults_are_angle_and_first_zone_reference(pj, base):
    r = pj(switches={"tx.model": "dcpf"})                     # tx.dcpf_form and tx.ref_bus absent (7.4a.1)
    _compare(r.t, base)
    assert (r.t["islands"]["ref_zone"] == "A").all() and r.t["islands"]["island_id"].nunique() == 1
    assert (r.t["angles"]["theta_source"] == "lp").all()
    assert set(r.fp.components["config"]["switches"]) == {"tx.model"}                              # builder writes no defaults


def test_p5b_ptdf_equals_angle(pj, base):
    a, b = pj(form="angle"), pj(form="ptdf")
    za = a.t["objective"].query("component == 'total'")["value_usd_yr"].iloc[0]
    zb = b.t["objective"].query("component == 'total'")["value_usd_yr"].iloc[0]
    assert zb == pytest.approx(za, rel=1e-9)
    np.testing.assert_allclose(_bus_hour(b.t, "lmp_usd_mwh"), _bus_hour(a.t, "lmp_usd_mwh"), atol=1e-6)
    np.testing.assert_allclose(_dispatch(b.t), _dispatch(a.t), atol=1e-6)
    np.testing.assert_allclose(_flows(b.t)["flow_mw"].to_numpy(float), _flows(a.t)["flow_mw"].to_numpy(float), atol=1e-6)
    np.testing.assert_allclose(_flows(b.t)["congestion_rent_usd_mwh"].to_numpy(float),
                               _flows(a.t)["congestion_rent_usd_mwh"].to_numpy(float), atol=1e-6)
    assert _hr(b.t["price_setter"])["primary_class"].tolist() == _hr(a.t["price_setter"])["primary_class"].tolist()
    _assert_price_setters(b.t, base)
    _assert_all_health_pass(b.h)
    assert (b.t["angles"]["theta_source"] == "recomputed").all()


@pytest.mark.parametrize("form", ["angle", "ptdf"])
@pytest.mark.parametrize("ref", range(5))
def test_p5c_reference_bus_invariance(pj, base, form, ref):
    r = pj(form=form, ref=ref)
    t = r.t
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), base["lmp"], atol=1e-6)
    np.testing.assert_allclose(_dispatch(t), base["g"], atol=1e-6)
    en, cg = _bus_hour(t, "lmp_energy_usd_mwh"), _bus_hour(t, "lmp_congestion_usd_mwh")
    np.testing.assert_allclose(en, base["lmp"][ref], atol=1e-6)                                    # lambda = pi at reference bus
    np.testing.assert_allclose(cg, base["lmp"] - base["lmp"][ref], atol=1e-6)                     # shifts by a constant
    np.testing.assert_allclose(_bus_hour(t, "lmp_loss_usd_mwh"), 0.0, atol=1e-12)
    assert (t["islands"]["ref_zone"] == LETTERS[ref]).all()
    _assert_price_setters(t, base)                                                                 # classes and alpha unchanged
    _assert_all_health_pass(r.h)


def test_p5d_uncongested(pj):
    ref = solve_opf("angle", 0, drop_de=True)
    r = pj(form="angle", drop_de=True)
    t = r.t
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), 30.0, atol=0.01)
    np.testing.assert_allclose(_dispatch(t), [40, 170, 190, 0, 600], atol=0.01)
    _compare(t, ref)
    ps = _hr(t["price_setter"])
    assert (ps["primary_class"] == "MARGINAL_UNIT").all() and (ps["setter_ids"] == "solitude").all()
    assert (_flows(t)["congestion_rent_usd_mwh"].abs() < 1e-9).all()
    assert (_flows(t)["at_bound"].astype(bool) == False).all()                                    # noqa: E712  no binding line
    np.testing.assert_allclose(_bus_hour(t, "lmp_congestion_usd_mwh"), 0.0, atol=1e-6)            # decomposition in P5d
    assert t["price_setter_loop"].empty
    _assert_all_health_pass(r.h)


def test_p5e_load_scan(pj):
    r = pj(form="angle", scale=LOAD_FACTORS)
    t = r.t
    for hr, s in enumerate(LOAD_FACTORS, start=1):
        ref = solve_opf("angle", 0, scale=float(s))
        _compare(t, ref, hr)
        _assert_price_setters(t, ref, hr)
    assert (t["price_setter"]["primary_class"] != "UNEXPLAINED").all()
    _assert_all_health_pass(r.h)


def test_p5f_transport_contrast_reported_only(pj):
    r = pj(tx="transport")                                    # NTC = rating; reported, not judged
    t = r.t
    assert len(_hr(t["flows"])) == 6 and "flow_mw" in t["flows"]                                  # runs and writes flows
    # under transport the F-0.2 outputs are unchanged: no dcpf columns/tables/checks (7.4a.9)
    assert "lmp_energy_usd_mwh" not in t["zone_hourly"].columns
    assert not ({"angles", "islands", "price_setter_loop"} & set(t))
    assert not r.h.checks["check_id"].isin(["kvl.recompute", "ptdf.recompute", "lmp.decomposition", "congestion_rent",
                                            "dcpf.line_duals", "dcpf.islands", "price_setter.loop_alpha"]).any()
    print("P5f transport LMP", _bus_hour(t, "lmp_usd_mwh"), "flows", _flows(t)["flow_mw"].to_numpy(float))


# ---- section 4 health checks: each driven by an independent recomputation, not by the audit layer's verdict
@pytest.mark.parametrize("form", ["angle", "ptdf"])
def test_h_kvl_recomputation(pj, base, form):
    r = pj(form=form)
    c = base["c"]
    A, b = incidence(c), BASE_MVA / c["x"]
    an = _hr(r.t["angles"]).set_index("zone").loc[LETTERS]
    th = an["theta_rad"].to_numpy(float)
    f = _flows(r.t)["flow_mw"].to_numpy(float)
    assert np.abs(f - b * (A @ th)).max() <= 1e-6                                                  # case reactances, not the LP
    assert an["is_ref"].astype(bool).tolist() == [True, False, False, False, False] and th[0] == 0.0
    row = _check(r.h, "kvl.recompute")
    assert len(row) == 1 and row["status"].iloc[0] == "pass" and row["value"].iloc[0] <= 1e-6


@pytest.mark.parametrize("form", ["angle", "ptdf"])
def test_h_ptdf_recomputation(pj, base, form):
    r = pj(form=form)
    c = base["c"]
    inj = np.bincount(c["gbus"], _dispatch(r.t), 5) - c["load"]
    f = _flows(r.t)["flow_mw"].to_numpy(float)
    assert np.abs(ptdf(c, 0) @ inj - f).max() <= 1e-6
    row = _check(r.h, "ptdf.recompute")
    assert len(row) == 1 and row["status"].iloc[0] == "pass" and row["value"].iloc[0] <= 1e-6


@pytest.mark.parametrize("drop", [False, True])
@pytest.mark.parametrize("ref_bus", [0, 3])
def test_h_lmp_decomposition_and_congestion_rent(pj, drop, ref_bus):
    ref = solve_opf("angle", 0, drop_de=drop)
    r = pj(form="angle", ref=ref_bus, drop_de=drop)
    t = r.t
    mu = _flows(t)["congestion_rent_usd_mwh"].to_numpy(float)
    pi = _bus_hour(t, "lmp_usd_mwh")
    P = ptdf(ref["c"], ref_bus)
    assert np.abs(pi - (pi[ref_bus] - P.T @ mu)).max() <= 1e-6
    np.testing.assert_allclose(_bus_hour(t, "lmp_energy_usd_mwh") + _bus_hour(t, "lmp_congestion_usd_mwh"), pi, atol=1e-9)
    np.testing.assert_allclose(_bus_hour(t, "lmp_congestion_usd_mwh"), -P.T @ mu, atol=1e-6)
    f = _flows(t)["flow_mw"].to_numpy(float)
    assert float(pi @ -ref["inj"]) == pytest.approx(float(mu @ f), rel=1e-7, abs=1e-9)
    if drop:
        assert np.abs(_bus_hour(t, "lmp_congestion_usd_mwh")).max() <= 1e-6
    for cid in ("lmp.decomposition", "congestion_rent"):
        assert len(_check(r.h, cid)) == 1 and (_check(r.h, cid)["status"] == "pass").all()


def test_h_line_duals_complementary_slackness(pj, base):
    f = _flows(pj(form="angle").t)
    rate = pd.Series(base["rate"], index=LINKS)
    nb = f["flow_mw"].abs() < rate - 1e-6
    assert nb.sum() == 5 and (f.loc[nb, "congestion_rent_usd_mwh"].abs() < 1e-9).all()             # mu != 0 only at a rating
    at = ~nb
    assert (f.loc[at, "congestion_rent_usd_mwh"] * f.loc[at, "flow_mw"] >= 0).all()                # sign table: mu f >= 0
    row = _check(pj(form="angle").h, "dcpf.line_duals")
    assert len(row) == 1 and row["status"].iloc[0] == "pass"


def test_h_islands_fixture_one_ref_angle_per_island(pj):
    """pjm5 minus ad, bc, de: islands {A,B,E} (ref A) and {C,D} (ref C) (7.4a.11)."""
    from capex.data import load_case
    from capex.run import build_lp
    ref = solve_opf("angle", [0, 2], drop=(1, 3, 5))
    r = pj(form="angle", drop_links=("ad", "bc", "de"), switches={"tx.model": "dcpf", "tx.dcpf_form": "angle",
                                                                  "tx.ref_bus": ["A", "C"]})
    t = r.t
    isl = t["islands"].set_index("zone")
    assert isl["island_id"].nunique() == 2 and set(isl["ref_zone"]) == {"A", "C"}
    assert isl.loc[["A", "B", "E"], "island_id"].nunique() == 1 and isl.loc[["C", "D"], "island_id"].nunique() == 1
    lp = build_lp(load_case(r.case_dir))
    assert lp.rows["ref_angle"].size == 2 * 72                                                     # one row per island-hour
    row = _check(r.h, "dcpf.islands")
    assert len(row) == 1 and row["status"].iloc[0] == "pass" and row["value"].iloc[0] == 0
    assert "2 islands" in str(row["detail"].iloc[0])
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), ref["lmp"], atol=TOL["lmp"])
    np.testing.assert_allclose(_bus_hour(t, "lmp_usd_mwh"), [10, 10, 40, 40, 10], atol=1e-6)
    np.testing.assert_allclose(_dispatch(t), ref["g"], atol=TOL["g"])
    cost_hr = t["objective"].query("component == 'total'")["value_usd_yr"].iloc[0] / (24 * D_Y)
    assert cost_hr == pytest.approx(25800.0, rel=1e-7)
    ps = _hr(t["price_setter"]).set_index("zone")
    assert (ps["primary_class"] == "MARGINAL_UNIT").all()
    assert ps.loc[["A", "B", "E"], "setter_ids"].tolist() == ["brighton"] * 3
    assert ps.loc[["C", "D"], "setter_ids"].tolist() == ["sundance"] * 2
    _assert_all_health_pass(r.h)


def test_h_conditioning_no_warn_on_p5a_to_p5e(pj):
    for kw in (dict(), dict(form="ptdf"), dict(drop_de=True), dict(scale=LOAD_FACTORS)):
        c = pj(**kw).h.checks
        cond = c[c["check_id"].str.startswith("conditioning")]
        assert len(cond) >= 1 and not cond["status"].isin(["warn", "fail"]).any(), (kw, cond)


@pytest.mark.parametrize("form", ["ptdf", "angle"])
def test_h_ranged_rows_none_written(pj, form):
    """7.4a.4/7.4a.11: flow limits stay column bounds; no row with -inf < lo < hi < inf (F5 vacuous)."""
    from capex.data import load_case
    from capex.run import build_lp
    lp = build_lp(load_case(pj(form=form).case_dir))
    ranged = np.isfinite(lp.row_lo) & np.isfinite(lp.row_hi) & (lp.row_lo < lp.row_hi)
    assert not ranged.any()


def _cases_t(name):
    return REPO / "cases" / name


def test_loader_accepts_f03_and_requires_it_for_dcpf(tmp_path):
    from capex.data import DataError, load_case
    cd = stage_case(_cases_t("T4"), tmp_path)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    cfg["formulation_version"] = "F-0.3"
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    load_case(cd)                                             # F-0.3 accepted (superset), transport
    bad = stage_case(_cases_t("T4"), tmp_path / "x")
    cfg = yaml.safe_load((bad / "case.yaml").read_text())
    cfg["switches"] = {"tx.model": "dcpf"}                    # F-0.2 case + dcpf
    (bad / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    with pytest.raises(DataError):
        load_case(bad)


def test_loader_rejects_unknown_tx_model_value(tmp_path):
    from capex.data import DataError, load_case
    cd = stage_case(_cases_t("T4"), tmp_path)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    cfg["switches"] = {"tx.model": "ac"}
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    with pytest.raises(DataError, match="tx.model"):
        load_case(cd)


def _bad_links(name):
    def edit(ln):
        ln = ln.copy()
        if name == "missing_reactance":
            ln.loc[ln["link_id"].eq("ab"), "reactance_pu"] = np.nan
        elif name == "zero_base":
            ln.loc[ln["link_id"].eq("ab"), "base_mva"] = 0.0
        elif name == "asymmetric_rating":
            ln.loc[ln["link_id"].eq("ab"), "ntc_rev_mw"] = 300.0
        elif name == "zero_rating":
            ln.loc[ln["link_id"].eq("ab"), ["ntc_fwd_mw", "ntc_rev_mw"]] = 0.0
        return ln
    return edit


@pytest.mark.parametrize("bad", ["missing_reactance", "zero_base", "asymmetric_rating", "zero_rating"])
def test_loader_dcpf_link_validation_errors(tmp_path, bad):
    """data-schema 3.2 / rule 11: under dcpf these are load errors."""
    from capex.data import DataError, load_case
    cd = make_pjm5(tmp_path, links_edit=_bad_links(bad))
    with pytest.raises(DataError):
        load_case(cd)


@pytest.mark.parametrize("refs", [["Z"], ["A", "B"]])
def test_loader_rejects_bad_ref_bus(tmp_path, refs):
    """tx.ref_bus must be zone ids, at most one per island (7.4a.1)."""
    from capex.data import DataError, load_case
    cd = make_pjm5(tmp_path, ref=refs)
    with pytest.raises(DataError):
        load_case(cd)


def test_audit_network_does_not_import_builder_network():
    """7.4a.10: the audit's case-data route must not import capex.network (verifier static check, as 5.1)."""
    path = REPO / "src" / "capex" / "audit" / "network.py"
    assert path.exists()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            assert all(a.name != "capex.network" and not a.name.startswith("capex.network.") for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod, lvl = node.module or "", node.level
            assert not (lvl == 0 and (mod == "capex.network" or mod.startswith("capex.network.")))
            assert not (lvl == 2 and (mod == "network" or mod.startswith("network.")))                # from ..network import
            assert not (lvl == 2 and mod == "" and any(a.name == "network" for a in node.names))      # from .. import network
            assert not (lvl == 0 and mod == "capex" and any(a.name == "network" for a in node.names))


# ---- mutations M7-M10 (7.4a.10): each must make at least one check FAIL (not raise); control run + vacuity guard
def _mutation_env():
    import capex.network as net_mod                           # noqa: F401  (absent until G3-3)
    import capex.run as run_mod
    import capex.solver as solver_mod
    return net_mod, run_mod, solver_mod


def _failing(h):
    return h.checks.loc[h.checks["status"] == "fail", "check_id"].tolist()


def _control_and_run(case_dir):
    from healthlib import solve_audit
    _sv, h = solve_audit(case_dir)
    assert h.status == "pass", f"control run must be clean:\n{h.checks[h.checks['status'] != 'pass']}"
    return solve_audit


@pytest.mark.parametrize("form", ["angle", "ptdf"])
def test_m7_reactance_scaled_in_lp_only(tmp_path, monkeypatch, form):
    net_mod, _run, _solver = _mutation_env()
    cd = make_pjm5(tmp_path, form=form)
    solve_audit = _control_and_run(cd)
    orig = net_mod.susceptance_mw_rad
    seen = {}

    def bad(case, *a, **k):
        b = np.array(orig(case, *a, **k), float)
        b[0] = b[0] / 1.01                                    # ab: reactance x 1.01 in the LP only
        seen["hit"] = True
        return b
    monkeypatch.setattr(net_mod, "susceptance_mw_rad", bad)
    _sv, h = solve_audit(cd)
    assert seen.get("hit"), "vacuity guard: the mutated susceptance must be used"
    f = _failing(h)
    assert set(f) & {"kvl.recompute", "ptdf.recompute"}, f"M7 not caught; failing: {f}"


def test_m8_kvl_row_sign_flip(tmp_path, monkeypatch):
    import dataclasses
    _net, run_mod, _solver = _mutation_env()
    cd = make_pjm5(tmp_path, form="angle")
    solve_audit = _control_and_run(cd)
    orig = run_mod.build_lp

    def build(case, scaling=None):
        lp = orig(case) if scaling is None else orig(case, scaling)
        a = lp.a.tolil()
        r = lp.rows["kvl"].idx(0, 0, 0)                       # kvl[ab, p1, t1]
        for z in (0, 1):                                      # theta_A, theta_B
            col = lp.cols["theta"].idx(z, 0, 0)
            assert a[r, col] != 0.0, "vacuity guard: theta coefficient must be nonzero"
            a[r, col] = -a[r, col]
        return dataclasses.replace(lp, a=a.tocsr())
    monkeypatch.setattr(run_mod, "build_lp", build)
    _sv, h = solve_audit(cd)
    f = _failing(h)
    assert set(f) & {"kvl.recompute", "ptdf.recompute"}, f"M8 not caught; failing: {f}"


def test_m9_reference_row_dropped(tmp_path, monkeypatch):
    import dataclasses
    _net, run_mod, _solver = _mutation_env()
    cd = make_pjm5(tmp_path, form="angle")
    solve_audit = _control_and_run(cd)
    orig = run_mod.build_lp

    def build(case, scaling=None):
        lp = orig(case) if scaling is None else orig(case, scaling)
        lo, hi = lp.row_lo.copy(), lp.row_hi.copy()
        i = lp.rows["ref_angle"].idx(0, 0, 0)                 # ref_angle[i1, p1, t1]
        assert np.isfinite(lo[i]) and lo[i] == hi[i], "vacuity guard: ref_angle must be an active equality row"
        lo[i], hi[i] = -np.inf, np.inf                        # row dropped, angles free
        return dataclasses.replace(lp, row_lo=lo, row_hi=hi)
    monkeypatch.setattr(run_mod, "build_lp", build)
    _sv, h = solve_audit(cd)                                  # must not raise: detected, not silently solved
    assert "dcpf.islands" in _failing(h), f"M9 must be caught by dcpf.islands; failing: {_failing(h)}"


@pytest.mark.parametrize("form", ["angle", "ptdf"])
def test_m10_one_line_mu_sign_flipped(tmp_path, monkeypatch, form):
    import dataclasses
    _net, run_mod, solver_mod = _mutation_env()
    cd = make_pjm5(tmp_path, form=form)
    solve_audit = _control_and_run(cd)
    orig = solver_mod.HighsSolver.solve

    def bad_solve(self, lp):
        sol = orig(self, lp)
        s = sol.col_dual.copy()
        i = lp.cols["flow"].idx(5, 0, 0)                      # flow[de, p1, t1]
        assert s[i] != 0.0, "vacuity guard: the flipped dual must be nonzero"
        s[i] = -s[i]
        return dataclasses.replace(sol, col_dual=s)
    monkeypatch.setattr(solver_mod.HighsSolver, "solve", bad_solve)
    _sv, h = solve_audit(cd)
    f = _failing(h)
    assert set(f) & {"dual_sign", "dcpf.line_duals", "lmp.decomposition", "congestion_rent"}, f"M10 not caught; failing: {f}"


# =============================================================== Part 3: Gate-1/Gate-2 identity under `transport` (7.4a.9)
CANON = ["T1", "T2a", "T2b", "T2c", "T3a", "T3b", "T4"]


def _mask_assumptions(text: str) -> str:
    return "".join(l for l in text.splitlines(keepends=True) if not l.startswith(("- run_id: ", "- fingerprint: ")))


def _same_env(a: dict, b: dict) -> bool:
    return (a.get("python") == b.get("python") and a.get("packages") == b.get("packages")
            and a.get("solver", {}).get("version") == b.get("solver", {}).get("version"))


def _mask_components(comp: dict, golden: dict, drop_tx_model: bool = False, same_env: bool | None = None) -> dict:
    """Drop the fields 7.4a.9 allows to differ: formulation_version, git_commit, dirty_diff_hash; environment entries
    (python, packages, solver.version) only if the environment differs from the golden one; config.switches['tx.model']
    only when the key is written explicitly. `same_env` (if given) is decided once from the (new, golden) pair so both
    sides are masked alike (G3-3-fix: masking only the new side failed whenever CI's Python differed from golden's)."""
    comp = json.loads(json.dumps(comp, sort_keys=True, default=str))
    for k in ("formulation_version", "git_commit", "dirty_diff_hash"):
        comp.pop(k, None)
    if same_env is None:
        same_env = _same_env(comp, golden)
    if not same_env:
        comp.pop("python", None), comp.pop("packages", None), comp.get("solver", {}).pop("version", None)
    if drop_tx_model:
        comp.get("config", {}).get("switches", {}).pop("tx.model", None)
    return comp


def _golden_components(name):
    return json.loads((GOLDEN / name / "components.json").read_text())


def test_golden_source_recorded():
    txt = (GOLDEN / "SOURCE.txt").read_text()
    assert "450f29c6ac4c99233cb8c55ca2c6a3dfe56b0a79" in txt and "highspy 1.16.0" in txt
    assert sorted(p.name for p in GOLDEN.iterdir() if p.is_dir()) == sorted(CANON)


@pytest.mark.parametrize("name", CANON)
def test_transport_canonical_outputs_byte_identical_to_gate2(canon, name):
    c = canon(name)
    gold = GOLDEN / name
    gold_files = sorted(p.name for p in gold.iterdir() if p.name != "components.json")
    new_files = sorted(p.name for p in c.out_dir.iterdir() if p.name != "run.json")
    assert new_files == gold_files, "canonical output file set changed under transport"
    for f in gold_files:
        a, b = (gold / f).read_bytes(), (c.out_dir / f).read_bytes()
        if f == "assumptions.md":
            a, b = _mask_assumptions(a.decode()).encode(), _mask_assumptions(b.decode()).encode()
        assert a == b, f"{name}/{f} differs from golden Gate-2 output"


@pytest.mark.parametrize("name", CANON)
def test_transport_fingerprint_components_equal_to_gate2(canon, name):
    g = _golden_components(name)
    raw = canon(name).fp.components
    env = _same_env(raw, g)
    new = _mask_components(raw, g, same_env=env)
    assert new == _mask_components(g, g, same_env=env)
    assert "tx.model" not in canon(name).fp.components["config"]["switches"]                       # builder writes no default


@pytest.mark.parametrize("name", CANON)
def test_transport_explicit_key_changes_only_the_tx_model_component(tmp_path, name):
    """Writing `tx.model: transport` explicitly: tables identical, components equal except config.switches['tx.model']."""
    from capex.run import run_case
    cd = stage_case(_cases_t(name), tmp_path)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    cfg["switches"] = {**(cfg.get("switches") or {}), "tx.model": "transport"}
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    _sv, _h, fp = run_case(cd, tmp_path / "out")
    g = _golden_components(name)
    env = _same_env(fp.components, g)
    new = _mask_components(fp.components, g, drop_tx_model=True, same_env=env)
    assert fp.components["config"]["switches"]["tx.model"] == "transport"
    assert new == _mask_components(g, g, same_env=env)
    for f in (p.name for p in (GOLDEN / name).glob("*.csv")):
        assert (tmp_path / "out" / f).read_bytes() == (GOLDEN / name / f).read_bytes(), f
