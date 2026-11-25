"""Verifier tests: formulation section 10 known-answer cases T1, T2a-c, T3a-b, T4.

Written from docs/formulation.md (sections 1-4, 10) and docs/gates/gate-1.md (sections 2-3) only.
Expected values are computed below from the closed forms in the spec, not pasted from solver output.

Interface files consulted (names/signatures/field names only, no implementation logic):
  src/capex/run.py   (run_case, output_tables; output table names)
  src/capex/cli.py   (how a case is run)
  cases/*/           (case file formats), and the CSV column headers written by `python -m capex run`.
Not consulted: tests/builder/, model/audit implementation bodies.

Tolerances (gate-1.md section 2): objective/capacities/rents/revenue rel 1e-6 (abs floor 1e-6);
block-average prices rel 1e-5; unique hourly prices abs 1e-4 $/MWh; hourly prices inside degenerate
blocks only against the allowed interval.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from capex.run import output_tables, run_case

CASES = Path(__file__).resolve().parents[1] / "cases"

W = 365.0 / 3.0            # weight of the single period (spec section 10 preamble)
REL = 1e-6                 # objective / capacity / rent / revenue
ABS_FLOOR = 1e-6
REL_BLOCK = 1e-5           # block-average prices
ABS_PRICE = 1e-4           # unique hourly prices
TOL_SLACK = 1e-6           # MW; row counted as binding when slack <= this


# ---------------------------------------------------------------- helpers
class Res:
    def __init__(self, name: str, out: Path):
        self.sv, self.health, self.fp = run_case(CASES / name, out)
        self.t = output_tables(self.sv, self.health)
        self.z = float(self.sv.z_total)

    def cap(self, rid, col="new_mw"):
        c = self.t["capacity"].set_index("resource_id")
        return float(c.loc[rid, col])

    def lmp(self, zone="A"):
        zh = self.t["zone_hourly"]
        zh = zh[zh["zone"] == zone].sort_values("t")
        return zh["lmp_usd_mwh"].to_numpy(), zh["weight_hours"].to_numpy()

    def disp(self, rid, col):
        d = self.t["dispatch"]
        d = d[d["resource"] == rid].sort_values("t") if "resource" in d else d[d["resource_id"] == rid].sort_values("t")
        return d[col].to_numpy(dtype=float)

    def ps(self, zone="A"):
        p = self.t["price_setter"]
        return p[p["zone"] == zone].sort_values("t").reset_index(drop=True)

    def rent(self, rid):
        return self.t["rents"].set_index("resource_id").loc[rid]

    def binding_rows(self, label, resource):
        d = self.t["duals_raw"]
        d = d[(d["label"] == label) & (d["resource"] == resource)]
        return set(int(t) for t in d.loc[d["slack"] <= TOL_SLACK, "t"])

    def bound_labels(self):
        return self.t["binding_bounds"]["label"].tolist()


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    cache: dict[str, Res] = {}

    def _run(name: str) -> Res:
        if name not in cache:
            cache[name] = Res(name, tmp_path_factory.mktemp(name))
        return cache[name]
    return _run


def close(a, b, rel, abs_=ABS_FLOOR):
    return abs(a - b) <= max(abs_, rel * abs(b))


def assert_close(a, b, rel, what, abs_=ABS_FLOOR):
    assert close(a, b, rel, abs_), f"{what}: obtained {a!r}, expected {b!r} (rel {rel}, abs floor {abs_})"


def assert_unique_prices(obtained, expected, what):
    err = np.abs(np.asarray(obtained) - np.asarray(expected))
    assert err.max() <= ABS_PRICE, f"{what}: max abs hourly price error {err.max():.3g} > {ABS_PRICE}"


def block_avg(price, weight, mask):
    return float(np.average(price[mask], weights=weight[mask]))


def common_health(res: Res):
    """Gate-1 section 3: every check passes, conditioning has no warn/fail, UNEXPLAINED = 0."""
    chk = res.health.checks
    bad = chk[chk["status"] != "pass"]
    assert bad.empty, f"non-pass health checks:\n{bad[['check_id', 'status', 'value', 'detail']]}"
    row = chk[chk["check_id"] == "price_setter.unexplained"]
    assert len(row) == 1 and float(row["value"].iloc[0]) == 0.0
    ps = res.t["price_setter"]
    assert not (ps["primary_class"] == "UNEXPLAINED").any()
    assert not ps["all_classes"].fillna("").str.contains("UNEXPLAINED").any()
    assert res.health.status != "fail"
    # shares per zone sum to one
    s = res.t["price_setter_summary"].groupby("zone")["share_weighted_hours"].sum()
    assert np.allclose(s.to_numpy(), 1.0, atol=1e-9)


def hours(a, b):
    return np.arange(a, b + 1)


# ---------------------------------------------------------------- T1
# Spec: demand 80 (t1-36), 120 (t37-60), 150 (t61-72); Base C=150000 MC=20; Peaker C=60000 MC=80; VOLL=10000.
T1_D = np.r_[np.full(36, 80.0), np.full(24, 120.0), np.full(12, 150.0)]
T1 = dict(cb=150_000.0, mcb=20.0, cp=60_000.0, mcp=80.0, voll=10_000.0)


def t1_expected():
    p = T1
    # load-duration slices: (upper level - lower level, annual hours the slice is needed)
    levels = [0.0, 80.0, 120.0, 150.0]
    be_bp = (p["cb"] - p["cp"]) / (p["mcp"] - p["mcb"])        # Base/Peaker breakeven hours (1500)
    be_pv = p["cp"] / (p["voll"] - p["mcp"])                    # Peaker/USE breakeven hours (6.05)
    xb = xp = 0.0
    for lo, hi in zip(levels[:-1], levels[1:]):
        dur = W * float(np.sum(T1_D > lo))                      # annual hours with D above the slice
        if dur >= be_bp:
            xb += hi - lo
        elif dur >= be_pv:
            xp += hi - lo
        else:
            raise AssertionError("slice would be unserved; not the spec case")
    g_b = np.minimum(T1_D, xb)
    g_p = np.minimum(T1_D, xb + xp) - g_b
    z = p["cb"] * xb + p["cp"] * xp + W * (p["mcb"] * g_b.sum() + p["mcp"] * g_p.sum())
    h_pk, h_mid = 12 * W, 24 * W
    pi_pk = p["mcp"] + p["cp"] / h_pk                           # Peaker zero profit
    pi_mid = p["mcb"] + (p["cb"] - h_pk * (pi_pk - p["mcb"])) / h_mid   # Base zero profit
    return dict(xb=xb, xp=xp, z=z, pi_off=p["mcb"], pi_mid=pi_mid, pi_pk=pi_pk, g_b=g_b, g_p=g_p)


def test_t1_closed_form_sanity():
    e = t1_expected()                       # cross-check the closed form against gate-1.md table numbers
    assert (e["xb"], e["xp"]) == (120.0, 30.0)
    assert abs(e["z"] - 40.824e6) < 1.0
    assert abs(e["pi_pk"] - 121.096) < 5e-4 and abs(e["pi_mid"] - 20.822) < 5e-4


def test_t1(run):
    r, e = run("T1"), t1_expected()
    common_health(r)
    # inputs reproduce the spec demand profile
    zh = r.t["zone_hourly"].sort_values("t")
    assert np.array_equal(zh["demand_mw"].to_numpy(), T1_D)
    # capacities, unserved, objective
    assert_close(r.cap("base"), e["xb"], REL, "x_base")
    assert_close(r.cap("peaker"), e["xp"], REL, "x_peak")
    assert float(zh["unserved_mw"].abs().max()) <= 1e-6
    assert_close(r.z, e["z"], REL, "Z")
    # block-average prices
    pi, wt = r.lmp()
    t = np.arange(1, 73)
    assert_unique_prices(pi[t <= 36], e["pi_off"], "off-peak hourly price")
    assert_close(block_avg(pi, wt, t <= 36), e["pi_off"], REL_BLOCK, "off-peak block price")
    assert_close(block_avg(pi, wt, (t >= 37) & (t <= 60)), e["pi_mid"], REL_BLOCK, "mid block average price")
    assert_close(block_avg(pi, wt, t >= 61), e["pi_pk"], REL_BLOCK, "peak block average price")
    # hourly intervals only
    mid, pk = (t >= 37) & (t <= 60), t >= 61
    assert (pi[mid] >= T1["mcb"] - ABS_PRICE).all() and (pi[mid] <= T1["mcp"] + ABS_PRICE).all(), "mid hourly price outside [20,80]"
    assert (pi[pk] >= T1["mcp"] - ABS_PRICE).all(), "peak hourly price below 80"
    # strong duality / revenue adequacy: sum w D pi = Z
    assert_close(float(np.sum(wt * T1_D * pi)), e["z"], REL, "sum w*D*pi vs Z")
    # zero-profit rents R = C_fix (audit table) and independent revenue identity from dispatch and prices
    for rid, c, mc, g in (("base", T1["cb"], T1["mcb"], e["g_b"]), ("peaker", T1["cp"], T1["mcp"], e["g_p"])):
        assert_close(float(r.rent(rid)["rent_cap_usd_mw_yr"]), c, REL, f"R_{rid}")
        gd = r.disp(rid, "g_mw")
        assert np.allclose(gd, g, atol=1e-6)
        x = r.cap(rid)
        assert_close(float(np.sum(wt * (pi - mc) * gd)), c * x, REL, f"revenue-VC {rid} = Cfix*x")
    # price-setter classes (DECISIONS 30)
    ps = r.ps()
    off = ps[ps["t"] <= 36]
    assert (off["primary_class"] == "MARGINAL_UNIT").all() and (off["setter_ids"] == "base").all()
    hi = ps[ps["t"] >= 37]
    assert set(hi["primary_class"]) <= {"CAPACITY_RENT", "TIE_AT_BOUND"}, set(hi["primary_class"])
    cr = hi[hi["primary_class"] == "CAPACITY_RENT"]
    assert cr["flags"].fillna("").str.contains("INVESTMENT_MARGIN").all()
    # binding set: gen_max Base in mid+peak, Peaker in peak, no x_ub
    assert r.binding_rows("gen_max", "base") == set(hours(37, 72).tolist())
    assert r.binding_rows("gen_max", "peaker") == set(hours(61, 72).tolist())
    assert r.bound_labels() == [], r.bound_labels()


# ---------------------------------------------------------------- T2
# Existing G1 100 MW MC 20, G2 200 MW MC 60; demand 50 (t1-36), 150 (t37-72); storage eta 0.9/0.9, VOM 0.
T2 = dict(g1=100.0, mc1=20.0, mc2=60.0, d_lo=50.0, d_hi=150.0, ec=0.9, ed=0.9, E=40.0, P=10.0, dur=4.0)


def t2_expected():
    p = T2
    # no-storage system cost per period: low hours G1 serves 50; high hours G1 100 + G2 50
    z_ns = W * (36 * p["d_lo"] * p["mc1"] + 36 * (p["g1"] * p["mc1"] + (p["d_hi"] - p["g1"]) * p["mc2"]))
    assert p["d_lo"] < p["g1"] and p["d_hi"] > p["g1"]                    # G1 / G2 marginal as stated
    assert p["mc2"] * p["ed"] * p["ec"] > p["mc1"]                       # arbitrage profitable => full cycle
    charge = p["E"] / p["ec"]                                             # MWh charged per period
    discharge = p["E"] * p["ed"]                                          # MWh discharged per period
    assert discharge / 36 <= p["P"] and charge / 36 <= p["P"]
    net_rev = W * (p["mc2"] * discharge - p["mc1"] * charge)
    r_e = W * (p["mc2"] * p["ed"] - p["mc1"] / p["ec"])                   # w (54 - 22.2222)
    return dict(z_ns=z_ns, charge=charge, discharge=discharge, net_rev=net_rev, r_e=r_e,
                v_ch=p["mc1"] / p["ec"], v_dis=p["mc2"] * p["ed"])


def test_t2_closed_form_sanity():
    e = t2_expected()
    assert abs(e["z_ns"] - 26_280_000.0) < 1e-6
    assert abs(e["r_e"] - 3866.30) < 5e-3 and abs(e["net_rev"] - 154_651.85) < 5e-3
    assert abs(e["charge"] - 44.4444444) < 1e-6 and abs(e["discharge"] - 36.0) < 1e-12


def t2_common(r: Res, e):
    common_health(r)
    pi, wt = r.lmp()
    t = np.arange(1, 73)
    assert_unique_prices(pi, np.where(t <= 36, T2["mc1"], T2["mc2"]), "hourly price (20 / 60)")
    ps = r.ps()
    assert (ps["primary_class"] == "MARGINAL_UNIT").all()
    assert ps.loc[ps["t"] <= 36, "setter_ids"].eq("g1").all() and ps.loc[ps["t"] >= 37, "setter_ids"].eq("g2").all()


def t2_storage_ties(r: Res, p_cap, e):
    """Ties with STORAGE_CH / STORAGE_DIS are recorded in all_classes wherever the storage is interior."""
    ps = r.ps()
    ch, dis = r.disp("bat", "charge_mw"), r.disp("bat", "discharge_mw")
    tol_q = max(1e-3, 1e-6 * p_cap)
    for i in range(72):
        if tol_q < ch[i] < p_cap - tol_q:
            assert "STORAGE_CH" in str(ps.loc[i, "all_classes"]), f"t={i + 1}"
        if tol_q < dis[i] < p_cap - tol_q:
            assert "STORAGE_DIS" in str(ps.loc[i, "all_classes"]), f"t={i + 1}"


def test_t2a(run):
    r, e = run("T2a"), t2_expected()
    t2_common(r, e)
    assert_close(r.z, e["z_ns"] - e["net_rev"], REL, "Z")
    ch, dis = r.disp("bat", "charge_mw"), r.disp("bat", "discharge_mw")
    assert_close(float(ch.sum()), e["charge"], REL, "charge MWh per period")
    assert_close(float(dis.sum()), e["discharge"], REL, "discharge MWh per period")
    # water value: pi/eta_c while charging, eta_d*pi while discharging
    sto = r.t["storage"].sort_values("t")
    v = sto["water_value_usd_mwh"].to_numpy()
    assert np.abs(v[ch > 1e-6] - e["v_ch"]).max() <= ABS_PRICE
    assert np.abs(v[dis > 1e-6] - e["v_dis"]).max() <= ABS_PRICE
    rent = r.rent("bat")
    assert_close(float(rent["rent_en"]), e["r_e"], REL, "R^E")
    assert abs(float(rent["rent_pwr"])) <= 1e-6, "R^P"
    assert_close(float(rent["rent_en"]) * T2["E"], e["net_rev"], REL, "R^E * E0 = net revenue")
    pi, wt = r.lmp()
    assert_close(float(np.sum(wt * pi * (dis - ch))), e["net_rev"], REL, "storage net revenue from prices and dispatch")
    t2_storage_ties(r, T2["P"], e)


def test_t2b(run):
    r, e = run("T2b"), t2_expected()
    t2_common(r, e)
    ce, cp = 3000.0, 0.0
    # build decision from the closed form: combined rent per MW (4 h) vs combined cost
    assert T2["dur"] * e["r_e"] >= cp + T2["dur"] * ce
    assert_close(r.cap("bat", "new_mw"), T2["P"], REL, "xP")
    assert_close(r.cap("bat", "new_mwh"), T2["E"], REL, "xE")
    assert_close(r.z, e["z_ns"] - e["net_rev"] + ce * T2["E"], REL, "Z")
    rent = r.rent("bat")
    excess = (float(rent["rent_pwr"]) + T2["dur"] * float(rent["rent_en"])) - (cp + T2["dur"] * ce)
    assert_close(excess, T2["dur"] * (e["r_e"] - ce), REL, "excess rent")
    assert excess >= -1e-9
    assert sorted(r.bound_labels()) == ["xE_ub", "xP_ub"], r.bound_labels()
    t2_storage_ties(r, T2["P"], e)


def test_t2c(run):
    r, e = run("T2c"), t2_expected()
    t2_common(r, e)
    ce, cp = 5000.0, 0.0
    assert T2["dur"] * e["r_e"] < cp + T2["dur"] * ce            # not worth building (closed form)
    assert abs(r.cap("bat", "new_mw")) <= ABS_FLOOR and abs(r.cap("bat", "new_mwh")) <= ABS_FLOOR
    assert_close(r.z, e["z_ns"], REL, "Z")
    rent = r.rent("bat")
    combined = float(rent["rent_pwr"]) + T2["dur"] * float(rent["rent_en"])
    assert combined < cp + T2["dur"] * ce, f"combined rent {combined} must be < cost {cp + T2['dur'] * ce}"


# ---------------------------------------------------------------- T3
# Existing G 100 MW MC 30; demand 80 except t=48: 120; VOLL 1000; candidate Peaker MC 100.
T3 = dict(kg=100.0, mcg=30.0, d=80.0, d48=120.0, voll=1000.0, mcp=100.0)


def t3_expected(cfix):
    p = T3
    be = cfix / (p["voll"] - p["mcp"])                  # annual hours at which peaker pays vs USE
    shortfall = p["d48"] - p["kg"]
    hours_exposed = W * 1.0                               # one modelled hour = W real hours
    if be > hours_exposed:
        x, u = 0.0, shortfall
    else:
        x, u = shortfall, 0.0
    energy_g = 71 * p["d"] + min(p["d48"], p["kg"])
    z = W * (p["mcg"] * energy_g + p["mcp"] * x + p["voll"] * u) + cfix * x     # peaker output = x in hour 48
    return dict(be=be, x=x, u=u, z=z)


def test_t3_closed_form_sanity():
    a, b = t3_expected(150_000.0), t3_expected(100_000.0)
    assert abs(a["be"] - 166.667) < 1e-3 and a["x"] == 0.0 and a["u"] == 20.0
    assert abs(a["z"] - 23_530_333.33) < 5e-3 and abs(b["z"] - 23_340_333.33) < 5e-3 and b["x"] == 20.0


def test_t3a(run):
    r, cfix = run("T3a"), 150_000.0
    e = t3_expected(cfix)
    common_health(r)
    assert_close(r.cap("peaker"), e["x"], REL, "x_peaker")
    zh = r.t["zone_hourly"].sort_values("t")
    u = zh["unserved_mw"].to_numpy()
    assert_close(float(u[47]), e["u"], REL, "u_48")
    assert np.abs(np.delete(u, 47)).max() <= 1e-6
    assert_close(r.z, e["z"], REL, "Z")
    pi, wt = r.lmp()
    assert_close(float(pi[47]), T3["voll"], 1e-6, "pi_48 (VOLL)", abs_=ABS_PRICE)
    assert_unique_prices(np.delete(pi, 47), T3["mcg"], "other hours")
    assert_close(float(r.rent("g")["rent_cap_usd_mw_yr"]), W * (T3["voll"] - T3["mcg"]), REL, "G rent")
    assert_close(r.cap("peaker", "x_reduced_cost_usd_mw_yr"), cfix - W * (T3["voll"] - T3["mcp"]), REL, "Peaker reduced cost")
    ps = r.ps()
    assert ps.loc[47, "primary_class"] == "VOLL"
    assert (ps.drop(index=47)["primary_class"] == "MARGINAL_UNIT").all()


def test_t3b(run):
    r, cfix = run("T3b"), 100_000.0
    e = t3_expected(cfix)
    common_health(r)
    assert e["x"] == 20.0 and e["u"] == 0.0
    assert_close(r.cap("peaker"), e["x"], REL, "x_peaker")
    zh = r.t["zone_hourly"].sort_values("t")
    assert zh["unserved_mw"].abs().max() <= 1e-6
    assert_close(r.z, e["z"], REL, "Z")
    pi, wt = r.lmp()
    assert_unique_prices(pi[47:48], T3["mcp"] + cfix / W, "pi_48 = MC + C/w")
    assert_unique_prices(np.delete(pi, 47), T3["mcg"], "other hours")
    ps = r.ps()
    assert ps.loc[47, "primary_class"] == "CAPACITY_RENT"
    assert "INVESTMENT_MARGIN" in str(ps.loc[47, "flags"])
    assert (ps.drop(index=47)["primary_class"] == "MARGINAL_UNIT").all()
    assert_close(float(r.rent("peaker")["rent_cap_usd_mw_yr"]), cfix, REL, "Peaker zero-profit rent")


# ---------------------------------------------------------------- T4
T4 = dict(mca=20.0, mcb=50.0, da=50.0, db=100.0, ntc=50.0, ka=1000.0)


def test_t4(run):
    r, p = run("T4"), T4
    common_health(r)
    # closed form: B is the dearer zone, so flow A->B runs to the smaller of NTC, A headroom and B demand
    f = min(p["ntc"], p["ka"] - p["da"], p["db"])
    ga, gb = p["da"] + f, p["db"] - f
    pia, pib = p["mca"], p["mcb"]
    mu = pib - pia
    n = 72
    z = W * n * (p["mca"] * ga + p["mcb"] * gb)
    cong = W * n * f * mu
    assert f == 50.0 and abs(z - 39_420_000.0) < 1e-6 and abs(cong - 13_140_000.0) < 1e-6   # gate-1 cross-check
    assert_close(r.z, z, REL, "Z")
    fl = r.t["flows"]
    assert np.allclose(fl["flow_mw"].to_numpy(), f, atol=1e-6)
    assert fl["at_bound"].all()
    assert np.allclose(fl["congestion_rent_usd_mwh"].to_numpy(), mu, atol=ABS_PRICE)
    assert np.allclose(r.disp("g_a", "g_mw"), ga, atol=1e-6) and np.allclose(r.disp("g_b", "g_mw"), gb, atol=1e-6)
    pa, wa = r.lmp("A")
    pb, wb = r.lmp("B")
    assert_unique_prices(pa, pia, "pi_A")
    assert_unique_prices(pb, pib, "pi_B")
    assert_close(float(np.sum(wa * f * fl["congestion_rent_usd_mwh"].to_numpy())), cong, REL, "congestion rent (mu)")
    assert_close(float(np.sum(wa * f * (pb - pa))), cong, REL, "congestion rent (price difference)")
    # price setters, islands, binding link
    psa, psb = r.ps("A"), r.ps("B")
    assert (psa["primary_class"] == "MARGINAL_UNIT").all() and (psa["setter_ids"] == "g_a").all()
    assert (psb["primary_class"] == "MARGINAL_UNIT").all() and (psb["setter_ids"] == "g_b").all()
    isl = set(psa["island_id"]) | set(psb["island_id"])
    assert len(isl) == 2 and set(psa["island_id"]).isdisjoint(set(psb["island_id"]))
    for q in (psa, psb):
        assert q["binding_links"].fillna("").str.contains("ab").all(), "binding link must be listed"
    assert r.t["link_issues"].empty
    # binding set: flow_ub on every hour of the link, nothing else
    bb = r.t["binding_bounds"]
    assert set(bb["label"]) == {"flow_ub"} and len(bb) == n and set(bb["link"]) == {"ab"}
