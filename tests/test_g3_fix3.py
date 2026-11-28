"""Verifier tests for G3-6-fix3: formulation F-0.3 amendment 2 (DECISIONS 51, 52), written from the spec only.

Spec clauses: 7.4a.1 (switch and tolerance keys), 4 "List cells", 7.4a.6 (`congestion_rent` per island-hour),
7.4a.7 (`CONGESTION_LOOP` cases (a)-(c), M_i without BLACKOUT, blackout bound pi >= VOLL), 8.10 (fingerprint carries the
code's formulation version, run.json the case's). Expected values come from the spec, from the published P5a example
(7.4a.7), or from independent numpy computation (PTDF from reactances, Moore-Penrose weights, hand-derived intervals);
none is copied from code output.

Synthetic fixtures (tmp_path, healthlib `write_case` + `links.csv` reactances):
  net4 : buses W (load 240), X, Y, Z (gens at 20 / 22.5 / 25), lines xy, yz, zx, wx (limit 125), wz, reactance 0.1 pu on
         100 MVA. Costs are built so that lambda = 20, mu_wx = -20 (reference X) price all three gens: c_n = lambda -
         H_{wx,n} mu. Three marginal buses, one binding line: r = 2 < 3 = |B|, case (b), the only non-marginal bus is W.
  blk  : buses X (load 50, gen 10 $/MWh), W (no load, no gen), Z (load 100); lines xw (rating 1e-4 MW) and wz.
         Z is a total blackout, K = {xw}, B = {X}: Phi = [1, 0] has rank 1 < 2, case (c) at W. Hand derivation (reference
         X, line oriented X->W, f > 0 so mu >= 0): pi_W = pi_Z = lambda + mu, lambda = 10, and the blackout bound
         pi_Z >= VOLL gives pi_W in [VOLL, +inf).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import capex
from capex.audit import loop as loopmod
from healthlib import CASES, T, W1, Spec, link, th, write_case
from test_pjm5bus import LETTERS, make_pjm5, stage_case

VOLL = 10_000.0


def _edit_cfg(cd: Path, fn) -> None:
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    fn(cfg)
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))


def _run(cd: Path, out: Path):
    from capex.run import output_tables, run_case
    sv, health, fp = run_case(cd, out)
    return sv, health, fp, output_tables(sv, health)


def _row(df: pd.DataFrame, zone: str, hour: int = 1) -> pd.Series:
    return df[(df["zone"] == zone) & (df["t"] == hour)].iloc[0]


# =================================================================== 7.4a.1: strict keys (amendment 2a)
@pytest.mark.parametrize("sw,key", [
    ({"tx.model": "dcpf", "tx.dcpf_formm": "ptdf"}, "tx.dcpf_formm"),          # typo must not run as the default
    ({"tx.model": "dcpf", "tx.losses": True}, "tx.losses"),                    # reserved for a later gate
    ({"tx.model": "dcpf", "reserves.enabled": False}, "reserves.enabled"),     # strict even at its default-off value
    ({"tx.model": "transport", "tx.losses": True}, "tx.losses"),
])
def test_loader_rejects_unimplemented_switch_keys(tmp_path, sw, key):
    from capex.data import DataError, load_case
    cd = make_pjm5(tmp_path, switches=sw)
    with pytest.raises(DataError, match=key.replace(".", r"\.")):
        load_case(cd)


@pytest.mark.parametrize("model", ["transport", "dcpf"])
def test_loader_rejects_unknown_tolerance_key(tmp_path, model):
    from capex.data import DataError, load_case
    cd = make_pjm5(tmp_path, switches={"tx.model": model})
    _edit_cfg(cd, lambda c: c.__setitem__("tolerances", {"tol_pi_abss": 0.01}))
    with pytest.raises(DataError):
        load_case(cd)


def test_network_tolerance_keys_only_under_dcpf(tmp_path):
    """7.4a.6: the network tolerance keys exist only under dcpf; under transport they are not fields of the set."""
    from capex.data import DataError, load_case
    cd = make_pjm5(tmp_path / "d", switches={"tx.model": "dcpf"})
    _edit_cfg(cd, lambda c: c.__setitem__("tolerances", {"kvl_residual_mw": 1e-6, "loop_alpha": 1e-6}))
    load_case(cd)
    cd = make_pjm5(tmp_path / "t", switches={"tx.model": "transport"})
    _edit_cfg(cd, lambda c: c.__setitem__("tolerances", {"kvl_residual_mw": 1e-6}))
    with pytest.raises(DataError):
        load_case(cd)


@pytest.mark.parametrize("bad", [3, ["A", 3]])
@pytest.mark.parametrize("model", ["dcpf", "transport"])
def test_loader_rejects_non_string_ref_bus(tmp_path, model, bad):
    """7.4a.1: `tx.ref_bus` must be a string or a list of strings; `tx.ref_bus: 3` is a DataError, not a TypeError."""
    from capex.data import DataError, load_case
    cd = make_pjm5(tmp_path, switches={"tx.model": model, "tx.ref_bus": bad})
    with pytest.raises(DataError):
        load_case(cd)


def test_loader_empty_ref_bus_list_is_rejected(tmp_path):
    """7.4a.1 / data-schema rule 11 (F-0.3 amendment 3, DECISIONS 53): `tx.ref_bus: []` names no zone, so it is a DataError.
    The default reference rule applies only when the key is omitted."""
    from capex.data import DataError, load_case
    cd = make_pjm5(tmp_path, switches={"tx.model": "dcpf", "tx.ref_bus": []})
    with pytest.raises(DataError):
        load_case(cd)


def test_implemented_switch_keys_still_load(tmp_path):
    from capex.data import load_case
    cd = make_pjm5(tmp_path, switches={"tx.model": "dcpf", "tx.dcpf_form": "ptdf", "tx.ref_bus": "D", "scaling": True})
    load_case(cd)


# =================================================================== 8.10: fingerprint vs run.json version
def test_formulation_version_constant_is_f04():
    assert capex.FORMULATION_VERSION == "F-0.4"


def test_fingerprint_carries_code_version_and_run_json_the_case_version(tmp_path):
    _sv, _h, fp, _t = _run(CASES / "T1", tmp_path / "o")                 # T1 declares F-0.2
    run = json.loads((tmp_path / "o" / "run.json").read_text())
    assert fp.components["formulation_version"] == "F-0.4"
    assert run["formulation_version"] == "F-0.2"


def test_fingerprint_and_run_json_both_f03_for_an_f03_case(tmp_path):
    cd = make_pjm5(tmp_path / "c", form="angle", ref=0)
    _sv, _h, fp, _t = _run(cd, tmp_path / "o")
    run = json.loads((tmp_path / "o" / "run.json").read_text())
    assert fp.components["formulation_version"] == "F-0.4" and run["formulation_version"] == "F-0.3"


# =================================================================== 4 "List cells", P5a and T4
@pytest.fixture(scope="module")
def p5a(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p5a")
    cd = make_pjm5(tmp / "c", form="angle", ref=0)
    return _run(cd, tmp / "o")


def test_p5a_list_cells_bus_a(p5a):
    """P5a hour 1, bus A: CONGESTION_LOOP, M = {solitude (C), brighton (E)}; setter_ids grouped by bus in zones.csv order
    (C before E), setter_zone distinct sorted, island_id = k of i<k> (one island: 1), binding_links `de`."""
    ps = p5a[3]["price_setter"]
    a = _row(ps, "A")
    assert a["primary_class"] == "CONGESTION_LOOP"
    assert a["setter_ids"] == "solitude,brighton"
    assert a["setter_zone"] == "C,E"
    assert int(a["island_id"]) == 1
    assert a["binding_links"] == "de"
    assert a["flags"] == "IMPORT,CONGESTED"
    assert a["all_classes"] == "CONGESTION_LOOP,CAPACITY_RENT"            # evaluation order: LOOP before CAPACITY_RENT


def test_p5a_island_id_is_integer_one_everywhere(p5a):
    ps = p5a[3]["price_setter"]
    assert pd.api.types.is_integer_dtype(ps["island_id"])
    assert (ps["island_id"] == 1).all()


def test_p5a_loop_rows_follow_setter_id_order(p5a):
    """setter_ids order for CONGESTION_LOOP = row order of price_setter_loop (by bus, then id within a bus)."""
    t = p5a[3]
    for z in ("A", "B", "D"):
        ids = _row(t["price_setter"], z)["setter_ids"].split(",")
        rows = t["price_setter_loop"].query("zone == @z and t == 1")["resource_id"].tolist()
        assert rows == ids == ["solitude", "brighton"]


def test_t4_transport_island_id_is_zero_based(tmp_path):
    """Under transport `island_id` is the 0-based component label of the hour's price island: zone A (first) is 0 in
    every hour; zone B is 0 when the link does not bind (one island) and 1 when it binds (two islands)."""
    _sv, _h, _fp, t = _run(CASES / "T4", tmp_path / "o")
    ps, fl = t["price_setter"], t["flows"]
    assert pd.api.types.is_integer_dtype(ps["island_id"])
    assert (ps[ps["zone"] == "A"]["island_id"] == 0).all()
    bound = fl.set_index("t")["at_bound"].groupby(level=0).any()
    b = ps[ps["zone"] == "B"].set_index("t")["island_id"]
    assert (b[~bound.reindex(b.index)] == 0).all() and (b[bound.reindex(b.index)] == 1).all()


# =================================================================== 7.4a.6: congestion_rent per island-hour
def _limit_cd(ln: pd.DataFrame) -> pd.DataFrame:
    ln = ln.copy()
    ln.loc[ln["link_id"].eq("cd"), ["ntc_fwd_mw", "ntc_rev_mw"]] = 100.0        # C (cheap) exports to D at most 100 MW
    return ln


ISLANDS = dict(drop_links=("ad", "bc", "de"), links_edit=_limit_cd,
               switches={"tx.model": "dcpf", "tx.dcpf_form": "angle", "tx.ref_bus": ["A", "C"]})


@pytest.fixture(scope="module")
def islands(tmp_path_factory):
    """pjm5 without ad, bc, de: islands i1 = {A,B,E} (ref A, ab ae) and i2 = {C,D} (ref C, cd limited to 100 MW)."""
    tmp = tmp_path_factory.mktemp("isl")
    cd = make_pjm5(tmp / "c", **ISLANDS)
    return cd, *_run(cd, tmp / "o")


def test_congestion_rent_identity_per_island(islands):
    """sum_{n in i} pi (-inj) = sum_{l in i} mu f for each island-hour, from the outputs (mu from `flows`, 8.12)."""
    cd, _sv, health, _fp, t = islands
    zh, fl = t["zone_hourly"], t["flows"]
    isl_of = {z: ("i1" if z in "ABE" else "i2") for z in LETTERS}
    link_isl = {"ab": "i1", "ae": "i1", "cd": "i2"}
    assert set(zh["island_id"]) == {"i1", "i2"}
    assert all(zh[zh["zone"] == z]["island_id"].eq(isl_of[z]).all() for z in LETTERS)
    gen_zone = pd.read_csv(cd / "resources.csv").set_index("resource_id")["zone"]
    disp = t["dispatch"].assign(zone=lambda d: d["resource"].map(gen_zone))
    gen = disp.groupby(["zone", "t"])["g_mw"].sum()
    worst, rent_total = 0.0, 0.0
    for hour in (1, 10, 36, 72):
        z = zh[zh["t"] == hour].set_index("zone")
        for isl in ("i1", "i2"):
            zs = [n for n in LETTERS if isl_of[n] == isl]
            lhs = sum(z.loc[n, "lmp_usd_mwh"] * (z.loc[n, "demand_mw"] - z.loc[n, "unserved_mw"] - gen.get((n, hour), 0.0))
                      for n in zs)                                    # pi (-inj), inj = g + u - D
            f = fl[fl["t"] == hour].set_index("link")
            rhs = sum(f.loc[k, "congestion_rent_usd_mwh"] * f.loc[k, "flow_mw"] for k in f.index if link_isl.get(k) == isl)
            worst = max(worst, abs(lhs - rhs) / max(1.0, abs(rhs)))
            rent_total += abs(rhs)
    assert worst <= 1e-7
    assert rent_total > 0, "fixture must carry congestion rent in at least one island"
    assert any(abs(f.loc["cd", "congestion_rent_usd_mwh"]) > 1e-6 for f in (fl[fl["t"] == h].set_index("link") for h in (1, 10, 36, 72)))
    row = health.checks.set_index("check_id").loc["congestion_rent"]
    assert row["status"] == "pass" and row["value"] <= 1e-7


def test_congestion_rent_residual_is_per_island_not_summed():
    """7.4a.6 (amendment 2): residuals of two islands must not cancel. Constructed arrays on the islands fixture grid
    (pjm5 minus ad, bc, de: islands {A,B,E} with ab, ae and {C,D} with cd): island 1 has rent +5, island 2 rent -5, all
    prices and injections 0. Per island-hour: |0 - (+-5)| / max(1, 5) = 1 for each; a sum over islands would give 0."""
    import tempfile
    from capex.audit.network import _rent_residual, grid
    from capex.data import load_case
    with tempfile.TemporaryDirectory() as d:
        cd = make_pjm5(Path(d), drop_links=("ad", "bc", "de"),
                       switches={"tx.model": "dcpf", "tx.ref_bus": ["A", "C"]})
        case = load_case(cd)
    g = grid(case)
    shape_n, shape_l = (5, 1, T), (3, 1, T)
    pi, inj = np.zeros(shape_n), np.zeros(shape_n)
    mu, f = np.zeros(shape_l), np.zeros(shape_l)
    mu[0], f[0] = 1.0, 5.0                      # ab (island 1): mu f = +5
    mu[2], f[2] = -1.0, 5.0                     # cd (island 2): mu f = -5
    assert _rent_residual(g, pi, inj, mu, f) == pytest.approx(1.0, abs=1e-12)


def test_isolated_node_is_its_own_island_and_runs(tmp_path):
    """7.4a.2: 'an isolated node is its own island' (reference = itself, no lines, no rent). pjm5 minus bc, cd leaves C alone."""
    cd = make_pjm5(tmp_path / "c", drop_links=("bc", "cd"),
                   switches={"tx.model": "dcpf", "tx.dcpf_form": "angle", "tx.ref_bus": ["A", "C"]})
    _sv, health, _fp, t = _run(cd, tmp_path / "o")
    assert set(t["islands"]["island_id"]) == {"i1", "i2"}
    assert health.status == "pass"


# =================================================================== 7.4a.7: CONGESTION_LOOP case (b)
BUSES4 = ["W", "X", "Y", "Z"]
LINES4 = [("X", "Y", 0.1, None), ("Y", "Z", 0.1, None), ("Z", "X", 0.1, None), ("W", "X", 0.1, 125.0),
          ("W", "Z", 0.1, None)]


def _net_case(tmp: Path, zones, lines, gens, demand) -> Path:
    spec = Spec(zones, [W1], np.array([[[demand.get(z, 0.0)] * T] for z in zones]),
                [th(f"g_{z}", z, k0=cap, mc=mc) for z, cap, mc in gens],
                [link(f"{a.lower()}{b.lower()}", a, b, math.nan if lim is None else lim) for a, b, _x, lim in lines])
    cd = write_case(spec, tmp / "case")
    ln = pd.read_csv(cd / "links.csv")
    ln["reactance_pu"], ln["base_mva"] = [x for _a, _b, x, _l in lines], 100.0
    ln.to_csv(cd / "links.csv", index=False)

    def edit(c):
        c["formulation_version"], c["switches"] = "F-0.3", {"tx.model": "dcpf"}
    _edit_cfg(cd, edit)
    return cd


def _ptdf(zones, lines, ref: str) -> np.ndarray:
    """Independent PTDF H[l, n] = d f_l / d inj_n with the balancing withdrawal at `ref` (b = 100 / x MW per rad)."""
    ix = {z: i for i, z in enumerate(zones)}
    a = np.zeros((len(lines), len(zones)))
    for l, (o, e, _x, _lim) in enumerate(lines):
        a[l, ix[o]], a[l, ix[e]] = 1.0, -1.0
    b = np.array([100.0 / x for *_oe, x, _lim in lines])
    bus = a.T @ np.diag(b) @ a
    keep = [n for n in range(len(zones)) if n != ix[ref]]
    xinv = np.zeros_like(bus)
    xinv[np.ix_(keep, keep)] = np.linalg.inv(bus[np.ix_(keep, keep)])
    return np.diag(b) @ a @ xinv


@pytest.fixture(scope="module")
def net4(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("net4")
    cd = _net_case(tmp, BUSES4, LINES4, [("X", 300, 20.0), ("Y", 300, 22.5), ("Z", 300, 25.0)], {"W": 240.0})
    return _run(cd, tmp / "o")


def test_case_b_weights_are_min_norm_and_reproduce_price(net4):
    """Marginal buses B = {X,Y,Z} (one gen each; a unit at zero with pi = mc is TIE_AT_BOUND and counts), K = {wx}:
    |B| = 3 > r = |K| + 1 = 2. alpha_W^T = phi_W Phi^+ with phi_n = [1, -H_{wx,n}]."""
    _sv, health, _fp, t = net4
    assert health.checks.set_index("check_id").loc["price_setter.loop_alpha", "status"] == "pass"
    lines = [(o, e, x, lim) for o, e, x, lim in LINES4]
    lam, mu = 20.0, -20.0                                      # designed duals, reference X; mu has the sign of f_wx < 0
    h = _ptdf(BUSES4, lines, "X")[3]
    pi = lam - h * mu                                          # pi_n = lambda - H_{wx,n} mu; X,Y,Z equal the gen costs
    np.testing.assert_allclose(pi[1:], [20.0, 22.5, 25.0], atol=1e-12)
    ps = t["price_setter"]
    w = _row(ps, "W")
    assert w["primary_class"] == "CONGESTION_LOOP"
    assert w["price"] == pytest.approx(pi[0], abs=1e-6) and pi[0] == pytest.approx(32.5)
    assert set(ps[ps["zone"] != "W"]["primary_class"]) <= {"MARGINAL_UNIT", "TIE_AT_BOUND"}
    # independent weights, for two different reference buses (alpha is reference-bus invariant)
    c = np.array([20.0, 22.5, 25.0])
    alphas = []
    for ref in ("W", "X"):
        hk = _ptdf(BUSES4, lines, ref)[[3]]                   # H_K, shape (1, N)
        phi = lambda n: np.r_[1.0, -hk[:, n]]
        big = np.array([phi(n) for n in (1, 2, 3)])           # Phi, 3 x 2
        assert np.linalg.matrix_rank(big) == 2
        alphas.append(phi(0) @ np.linalg.pinv(big))
    np.testing.assert_allclose(alphas[0], alphas[1], atol=1e-10)
    alpha = alphas[0]
    assert alpha.sum() == pytest.approx(1.0, abs=1e-12) and alpha @ c == pytest.approx(pi[0], abs=1e-9)
    rows = t["price_setter_loop"].query("zone == 'W' and t == 1")
    assert rows["resource_id"].tolist() == ["g_X", "g_Y", "g_Z"]
    assert rows["setter_zone"].tolist() == ["X", "Y", "Z"] and set(rows["case"]) == {"weights_nonunique"}
    np.testing.assert_allclose(rows["cost_usd_mwh"], c, atol=1e-12)
    np.testing.assert_allclose(rows["alpha"], alpha, atol=1e-6)
    assert rows["alpha"].sum() == pytest.approx(1.0, abs=1e-6)
    assert (rows["alpha"] * rows["cost_usd_mwh"]).sum() == pytest.approx(w["price"], abs=1e-6)
    # min-norm: alpha is orthogonal to the null space of Phi^T (the only freedom in alpha); here null(Phi^T) is 1-dim
    big = np.array([np.r_[1.0, -_ptdf(BUSES4, lines, "W")[3, n]] for n in (1, 2, 3)])
    null = np.linalg.svd(big.T)[2][-1]
    assert abs(big.T @ null).max() < 1e-12
    assert abs(rows["alpha"].to_numpy() @ null) < 1e-6
    assert (rows["alpha"] < 0).any() and (rows["alpha"] > 1).any()    # weights are not convex (spec)


def test_case_b_row_cells(net4):
    ps = net4[3]["price_setter"]
    w = _row(ps, "W")
    assert w["setter_ids"] == "g_X,g_Y,g_Z" and w["setter_zone"] == "X,Y,Z"
    assert w["binding_links"] == "wx"
    assert w["flags"] == "DEGENERATE,IMPORT,CONGESTED"            # order: DEGENERATE, IMPORT, CONGESTED
    assert w["price_lo"] == pytest.approx(w["price"], abs=1e-6) and w["price_hi"] == pytest.approx(w["price"], abs=1e-6)
    assert w["setter_cost"] == pytest.approx(w["price_lo"], abs=1e-12)
    assert abs(w["residual"]) <= 1e-6
    n_loop = len(net4[3]["price_setter_loop"])
    assert n_loop == 3 * 72 and set(net4[3]["price_setter_loop"]["zone"]) == {"W"}


# =================================================================== 7.4a.7: case (c) and the blackout bound
@pytest.fixture(scope="module")
def blk(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("blk")
    lines = [("X", "W", 0.1, 1e-4), ("W", "Z", 0.1, None)]
    cd = _net_case(tmp, ["X", "W", "Z"], lines, [("X", 200, 10.0)], {"X": 50.0, "Z": 100.0})
    return _run(cd, tmp / "o")


def test_blackout_bus_is_not_a_marginal_member_and_not_a_setter_of_the_loop(blk):
    """M_i excludes BLACKOUT: unserved:Z is not in W's setter_ids, no price_setter_loop row names it, and
    B = {X} only (a member at Z would make Phi square, case (a), with loop rows)."""
    t = blk[3]
    ps = t["price_setter"]
    z, w = _row(ps, "Z"), _row(ps, "W")
    assert z["primary_class"] == "VOLL" and z["all_classes"].startswith("VOLL:BLACKOUT") and "BLACKOUT" in z["flags"].split(",")
    assert w["primary_class"] == "CONGESTION_LOOP"
    assert w["setter_ids"] == "g_X" and w["setter_zone"] == "X"
    assert "unserved" not in str(w["setter_ids"])
    assert not t["price_setter_loop"]["resource_id"].astype(str).str.startswith("unserved").any()


def test_case_c_is_degenerate_with_interval_and_no_loop_rows(blk):
    """Case (c) (r = 1 < |K| + 1 = 2): sub-tag DEGENERATE, no weights written, price_lo = setter_cost, price_hi = hi."""
    _sv, health, _fp, t = blk
    w = _row(t["price_setter"], "W")
    assert w["flags"] == "DEGENERATE,IMPORT,CONGESTED"
    assert w["binding_links"] == "xw"
    assert t["price_setter_loop"].empty                              # no rows for case (c)
    assert w["setter_cost"] == w["price_lo"]
    assert abs(w["residual"]) <= 1e-6
    assert (t["price_setter"]["primary_class"] != "UNEXPLAINED").all()
    assert health.checks.set_index("check_id").loc["price_setter.loop_alpha", "status"] == "pass"


def test_case_c_total_blackout_bound_gives_voll_lower_end_and_infinite_upper_end(blk):
    """Hand-derived (module docstring): pi_W in [VOLL, +inf). The only finite end comes from the blackout bound at Z."""
    t = blk[3]
    w = _row(t["price_setter"], "W")
    assert w["price_lo"] == pytest.approx(VOLL, abs=1e-6)
    assert np.isposinf(w["price_hi"])
    assert w["price"] >= VOLL - 1e-2                                 # pi = VOLL + mu^use >= VOLL at the blackout side
    z = _row(t["price_setter"], "Z")
    assert z["price"] >= VOLL - 1e-2 and abs(z["price"] - w["price"]) <= 1e-2     # no congestion between W and Z


# =================================================================== 7.4a.7: interval LP, direct (constructed inputs)
def _solver():
    from capex.solver import make_solver
    return make_solver({"name": "highs"})


def _iv(phi_b, cost_b, sign_k, bounds, targets):
    return loopmod.interval(_solver(), np.atleast_2d(np.array(phi_b, float)), np.array(cost_b, float),
                            np.array(sign_k, float), bounds, np.array(targets, float))


# Two buses X (reference) and Y, one line X->Y, f > 0 (mu >= 0). H_{l,Y} = -1, so phi_X = [1, 0], phi_Y = [1, 1].
PHI_X, PHI_Y = [1.0, 0.0], [1.0, 1.0]


def test_classify_cases_a_b_c():
    sq = np.array([[1.0, 0.0], [1.0, 1.0]])
    tall = np.array([[1.0, 0.0], [1.0, 1.0], [1.0, 2.0]])
    assert loopmod.classify(sq) == loopmod.UNIQUE                            # (a) |B| = |K|+1 = r
    assert loopmod.classify(tall) == loopmod.NONUNIQUE                       # (b) r = |K|+1 < |B|
    assert loopmod.classify(np.array([[1.0, 1.0]])) == loopmod.INTERVAL      # (c) r = 1 < 2
    assert loopmod.classify(np.array([[1.0, 1.0], [2.0, 2.0]])) == loopmod.INTERVAL    # rank 1 with |B| = 2


def test_interval_unbounded_below_without_bounds():
    iv = _iv([PHI_Y], [30.0], [1], [], [PHI_X, PHI_Y])           # lambda = 30 - mu, mu >= 0
    assert np.isneginf(iv[0, 0]) and iv[0, 1] == pytest.approx(30.0)
    np.testing.assert_allclose(iv[1], [30.0, 30.0], atol=1e-9)


def test_interval_unbounded_above_for_reverse_flow_sign():
    iv = _iv([PHI_Y], [30.0], [-1], [], [PHI_X])                  # mu <= 0: lambda = 30 - mu >= 30
    assert iv[0, 0] == pytest.approx(30.0) and np.isposinf(iv[0, 1])


def test_interval_finite_with_unit_at_cap_and_at_zero():
    cap = loopmod.Bound(np.array(PHI_X), 10.0, 1)                 # unit at X at its cap: pi_X >= 10
    np.testing.assert_allclose(_iv([PHI_Y], [30.0], [1], [cap], [PHI_X])[0], [10.0, 30.0], atol=1e-9)
    zero = loopmod.Bound(np.array(PHI_X), 20.0, -1)               # unit at X at zero: pi_X <= 20
    iv = _iv([PHI_Y], [30.0], [1], [zero], [PHI_X])[0]
    assert np.isneginf(iv[0]) and iv[1] == pytest.approx(20.0)


def test_interval_total_blackout_bound_pi_ge_voll():
    """Blackout fixture algebra: B = {X} (Phi = [1, 0], cost 10), K = {xw}, f > 0; targets W (= [1, 1]); a blackout bus Z
    behind W has phi_Z = [1, 1] and the bound pi_Z >= VOLL: interval for pi_W is [VOLL, +inf)."""
    bound = loopmod.Bound(np.array([1.0, 1.0]), VOLL, 1)
    iv = _iv([[1.0, 0.0]], [10.0], [1], [bound], [[1.0, 1.0], [1.0, 0.0]])
    assert iv[0, 0] == pytest.approx(VOLL, abs=1e-6) and np.isposinf(iv[0, 1])
    np.testing.assert_allclose(iv[1], [10.0, 10.0], atol=1e-9)          # pi_X pinned by its marginal unit


def test_weights_are_min_norm_sum_to_one_and_reproduce_pi():
    """Direct (b): Phi 3 x 2 from costs on a line, weights phi_n Phi^+ (numpy pinv), sum 1, alpha . c = pi_n."""
    phi_b = np.array([[1.0, 0.0], [1.0, 0.5], [1.0, 1.0]])
    c = np.array([10.0, 14.0, 18.0])                 # consistent: lambda = 10, mu = 8
    target = np.array([[1.0, 0.25], [1.0, 2.0], [1.0, -1.0]])
    alpha = loopmod.weights(phi_b, target)
    np.testing.assert_allclose(alpha, target @ np.linalg.pinv(phi_b), atol=1e-12)
    np.testing.assert_allclose(alpha.sum(axis=1), 1.0, atol=1e-12)
    np.testing.assert_allclose(alpha @ c, 10.0 + 8.0 * target[:, 1], atol=1e-10)
