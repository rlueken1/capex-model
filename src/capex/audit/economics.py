"""Hooks 4-6, 8: objective decomposition, revenue/rent table, storage report, curtailment and unserved energy."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .duals import Economics
from .solved import Solved


def objective_decomposition(sv: Solved) -> pd.DataFrame:
    """Z^inv by resource, Z^var by resource and fuel, Z^use by zone, Z^0 by resource, plus a total row (hook 4)."""
    case, gen, st = sv.case, sv.case.gen, sv.case.storage
    wt = case.w[None, :, None]
    var_gen = (wt * gen.mc * sv.var("g")).sum(axis=(1, 2))
    var_st = (wt * st.vom[:, None, None] * sv.var("dis")).sum(axis=(1, 2))
    inv_gen = gen.cfix * sv.var("x")
    inv_st = st.cp * sv.var("xP") + st.ce * sv.var("xE")
    use = (wt * case.voll * sv.var("use")).sum(axis=(1, 2))
    rows = (
        [("Z_inv", i, "", v) for i, v in zip(gen.ids, inv_gen)] + [("Z_inv", i, "", v) for i, v in zip(st.ids, inv_st)]
        + [("Z_var", i, f, v) for i, f, v in zip(gen.ids, gen.fuel, var_gen)]
        + [("Z_var", i, "storage", v) for i, v in zip(st.ids, var_st)]
        + [("Z_use", z, "", v) for z, v in zip(case.zones, use)]
        + [("Z0", i, "", v) for i, v in zip(gen.ids, gen.fom0)] + [("Z0", i, "", v) for i, v in zip(st.ids, st.fom0)])
    table = pd.DataFrame(rows, columns=["component", "id", "fuel", "value_usd_yr"])
    return pd.concat([table, pd.DataFrame([{"component": "total", "id": "", "fuel": "",
                                            "value_usd_yr": table["value_usd_yr"].sum()}])], ignore_index=True)


def _status(x: np.ndarray, xmax: np.ndarray, tol: np.ndarray) -> np.ndarray:
    return np.where(x <= tol, "at_zero", np.where(x >= xmax - tol, "at_max", "interior"))


def _zero_profit_ok(excess: np.ndarray, cost: np.ndarray, status: np.ndarray, rel: float) -> np.ndarray:
    """Section 3 check 5 on excess rent R - C: =0 interior, <=0 at zero, >=0 at max."""
    tol = rel * np.maximum(np.abs(cost), 1.0)
    return np.where(status == "interior", np.abs(excess) <= tol,
                    np.where(status == "at_zero", excess <= tol, excess >= -tol))


def _tol_q(sv: Solved, cap: np.ndarray) -> np.ndarray:
    t = sv.case.tolerances
    return np.maximum(t.tol_q_abs_mw, t.tol_q_rel * cap)


def gen_rents(sv: Solved, eco: Economics) -> pd.DataFrame:
    gen, w = sv.case.gen, sv.case.w[None, :, None]
    x = sv.var("x")
    k = gen.k0 + x
    price = eco.pi[gen.zone]
    energy_rev = (w * price * sv.var("g")).sum(axis=(1, 2))
    var_cost = (w * gen.mc * sv.var("g")).sum(axis=(1, 2))
    rent = (w * gen.avail * eco.rho).sum(axis=(1, 2))
    status = _status(x, gen.xmax, _tol_q(sv, k))
    candidate = gen.status == "candidate"
    ok = np.where(candidate, _zero_profit_ok(rent - gen.cfix, gen.cfix, status, sv.case.tolerances.zero_profit_rel), True)
    fixed = gen.cfix * x + gen.fom0
    return pd.DataFrame({
        "resource_id": gen.ids, "kind": gen.kind, "energy_revenue": energy_rev, "variable_cost": var_cost,
        "rent_cap_usd_mw_yr": rent, "rent_pwr": np.nan, "rent_en": np.nan, "cfix": gen.cfix,
        "fixed_cost": fixed, "profit": energy_rev - var_cost - fixed, "build_status": np.where(candidate, status, "existing"),
        "excess_rent": np.where(candidate, rent - gen.cfix, np.nan), "zero_profit_ok": ok,
        "revenue_identity_residual": energy_rev - var_cost - rent * k})


def storage_rents(sv: Solved, eco: Economics) -> pd.DataFrame:
    st, w = sv.case.storage, sv.case.w[None, :, None]
    xp, xe = sv.var("xP"), sv.var("xE")
    p_cap, e_cap = st.p0 + xp, st.e0 + xe
    price = eco.pi[st.zone]
    energy_rev = (w * price * (sv.var("dis") - sv.var("ch"))).sum(axis=(1, 2))
    var_cost = (w * st.vom[:, None, None] * sv.var("dis")).sum(axis=(1, 2))
    r_p = (w * eco.rho_p).sum(axis=(1, 2))
    r_e = (w * eco.rho_e).sum(axis=(1, 2))
    status = _status(xp, st.xp_max, _tol_q(sv, p_cap))
    candidate = st.status == "candidate"
    fixed_dur = candidate & (st.dur_lo == st.dur_hi)           # NaN != NaN -> False
    delta = np.nan_to_num(st.dur_lo)
    excess = (r_p + delta * r_e) - (st.cp + delta * st.ce)
    ok = np.where(fixed_dur, _zero_profit_ok(excess, st.cp + delta * st.ce, status, sv.case.tolerances.zero_profit_rel),
                  np.where(candidate, _column_sign_ok(sv, status), True))
    fixed = st.cp * xp + st.ce * xe + st.fom0
    return pd.DataFrame({
        "resource_id": st.ids, "kind": "ST", "energy_revenue": energy_rev, "variable_cost": var_cost,
        "rent_cap_usd_mw_yr": np.nan, "rent_pwr": r_p, "rent_en": r_e, "cfix": st.cp + delta * st.ce,
        "fixed_cost": fixed, "profit": energy_rev - var_cost - fixed, "build_status": np.where(candidate, status, "existing"),
        "excess_rent": np.where(candidate, excess, np.nan), "zero_profit_ok": ok,
        "revenue_identity_residual": energy_rev - var_cost - (r_p * p_cap + r_e * e_cap)})


def _column_sign_ok(sv: Solved, status: np.ndarray) -> np.ndarray:
    """Storage without a fixed duration: the solver's own reduced costs have the sign its build status requires."""
    tol = sv.case.tolerances.zero_profit_rel
    s = sv.col_dual("xP")
    return np.where(status == "interior", np.abs(s) <= tol, np.where(status == "at_zero", s >= -tol, s <= tol))


def storage_reduced_cost_residual(sv: Solved, eco: Economics) -> float:
    """Max |recomputed - solver| reduced cost of xP and xE over candidate storage (section 3 check 5), $/yr per unit."""
    st, w = sv.case.storage, sv.case.w[None, :, None]
    cand = np.flatnonzero(st.status == "candidate")
    if len(cand) == 0:
        return 0.0
    r_p = (w * eco.rho_p).sum(axis=(1, 2))[cand]
    r_e = (w * eco.rho_e).sum(axis=(1, 2))[cand]
    y_lo = np.zeros(len(st.ids))
    y_hi = np.zeros(len(st.ids))
    y_lo[np.flatnonzero(~np.isnan(st.dur_lo) & (st.status == "candidate"))] = sv.row_dual("st_dur_lo")
    y_hi[np.flatnonzero(~np.isnan(st.dur_hi) & (st.status == "candidate"))] = sv.row_dual("st_dur_hi")
    s_p = st.cp[cand] - r_p + np.nan_to_num(st.dur_lo[cand]) * y_lo[cand] + np.nan_to_num(st.dur_hi[cand]) * y_hi[cand]
    s_e = st.ce[cand] - r_e - y_lo[cand] - y_hi[cand]
    return float(max(np.abs(s_p - sv.col_dual("xP")[cand]).max(), np.abs(s_e - sv.col_dual("xE")[cand]).max()))


def rent_table(sv: Solved, eco: Economics) -> pd.DataFrame:
    """Revenue/rent table per resource with zero-profit flags (hook 5, section 3 checks 5-6)."""
    return pd.concat([gen_rents(sv, eco), storage_rents(sv, eco)], ignore_index=True)


@dataclass(frozen=True)
class StorageReport:
    hourly: pd.DataFrame      # soc, charge, discharge, water value, simul_chdis per (resource, period, t)
    closure: pd.DataFrame     # cyclic closure residual per (resource, period)


def storage_report(sv: Solved, eco: Economics) -> StorageReport:
    st = sv.case.storage
    ch, dis, soc = sv.var("ch"), sv.var("dis"), sv.var("soc")
    blk = sv.lp.cols["soc"]
    q = np.maximum(sv.case.tolerances.tol_q_abs_mw, sv.case.tolerances.tol_q_rel * (st.p0 + sv.var("xP")))
    hourly = blk.frame().drop(columns="label").assign(
        soc_mwh=soc.ravel(), charge_mw=ch.ravel(), discharge_mw=dis.ravel(), water_value_usd_mwh=eco.v.ravel(),
        simul_chdis=(np.minimum(ch, dis) > q[:, None, None]).ravel())
    prev = np.roll(soc, 1, axis=2)
    net = (st.eta_c[:, None, None] * ch - dis / st.eta_d[:, None, None] - st.sigma[:, None, None] * prev).sum(axis=2)
    closure = pd.DataFrame({"resource": np.repeat(st.ids, len(sv.case.periods)),
                            "period": np.tile(sv.case.periods, len(st.ids)), "closure_residual_mwh": net.ravel()})
    return StorageReport(hourly=hourly, closure=closure)


def soc_recompute_residual(sv: Solved) -> float:
    """Max |e_t - (1-sigma) e_t- - eta_c c_t + d_t/eta_d| in MWh from case data and the primal (section 3 check 8)."""
    st = sv.case.storage
    if not len(st.ids):
        return 0.0
    sig, eta_c, eta_d = (a[:, None, None] for a in (st.sigma, st.eta_c, st.eta_d))
    e = sv.var("soc")
    resid = e - (1 - sig) * np.roll(e, 1, axis=2) - eta_c * sv.var("ch") + sv.var("dis") / eta_d
    return float(np.abs(resid).max())


def curtailment_unserved(sv: Solved) -> dict[str, pd.DataFrame]:
    """Curtailment (VRE) and unserved energy, weighted annual MWh (hook 8)."""
    case, gen, wt = sv.case, sv.case.gen, sv.case.w[None, :, None]
    vre = np.flatnonzero(gen.kind == "VRE")
    curt = gen.avail[vre] * (gen.k0[vre] + sv.var("x")[vre])[:, None, None] - sv.var("g")[vre]
    zone_of = np.asarray(case.zones, dtype=object)[gen.zone[vre]]
    curtailment = pd.DataFrame({"resource_id": np.asarray(gen.ids, dtype=object)[vre], "zone": zone_of,
                                "curtailed_mwh": (wt * curt).sum(axis=(1, 2)),
                                "available_mwh": (wt * gen.avail[vre] * (gen.k0[vre] + sv.var("x")[vre])[:, None, None]
                                                  ).sum(axis=(1, 2))})
    u = sv.var("use")
    unserved = pd.DataFrame({"zone": np.repeat(case.zones, len(case.periods)),
                             "period": np.tile(case.periods, len(case.zones)),
                             "unserved_mwh": (case.w[None, :] * u.sum(axis=2)).ravel()})
    return {"curtailment": curtailment, "unserved": unserved}
