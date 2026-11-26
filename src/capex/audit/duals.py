"""Hooks 1-3: balance residuals, raw and economic duals, binding report."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..model import Block
from .solved import Solved

# bound family label -> (column block, side)
BOUND_FAMILIES = {"x_ub": ("x", "hi"), "xP_ub": ("xP", "hi"), "xE_ub": ("xE", "hi"), "flow_ub": ("flow", "hi"),
                  "flow_lb": ("flow", "lo"), "use_ub": ("use", "hi")}


@dataclass(frozen=True)
class Economics:
    """Economic duals of formulation section 3 (all >= 0 in normal operation)."""
    pi: np.ndarray        # (Z,P,T) energy price, $/MWh
    rho: np.ndarray       # (G,P,T) capacity scarcity rent per available MW-hour
    rho_p: np.ndarray     # (S,P,T) storage power rent
    rho_e: np.ndarray     # (S,P,T) storage energy rent
    v: np.ndarray         # (S,P,T) water value, $/MWh stored
    mu_link: np.ndarray   # (L,P,T) signed congestion rent pi_e - pi_o
    mu_use: np.ndarray    # (Z,P,T) blackout rent (use_ub), <= 0 side only


def economic_duals(sv: Solved) -> Economics:
    w = sv.case.w[None, :, None]
    return Economics(
        pi=sv.row_dual("bal") / w, rho=-sv.row_dual("gen_max") / w, rho_p=-sv.row_dual("st_pwr") / w,
        rho_e=-sv.row_dual("st_emax") / w, v=-sv.row_dual("st_soc") / w, mu_link=-sv.col_dual("flow") / w,
        mu_use=-np.minimum(sv.col_dual("use"), 0.0) / w)


def balance_residuals(sv: Solved) -> np.ndarray:
    """LHS - D of `bal` recomputed from the primal solution and case data, unscaled MW, shape (Z,P,T)."""
    case, gen, st, lk = sv.case, sv.case.gen, sv.case.storage, sv.case.links
    lhs = sv.var("use").copy()
    np.add.at(lhs, gen.zone, sv.var("g"))
    np.add.at(lhs, st.zone, sv.var("dis") - sv.var("ch"))
    np.add.at(lhs, lk.end, sv.var("flow"))
    np.add.at(lhs, lk.origin, -sv.var("flow"))
    return lhs - case.demand


def _frame(block: Block, **columns: np.ndarray) -> pd.DataFrame:
    return block.frame().assign(**{k: v.ravel() for k, v in columns.items()})


def raw_duals(sv: Solved) -> pd.DataFrame:
    """Canonical raw duals per row family and per bound family, with slack and weight (hook 2)."""
    frames = [_frame(b, dual=sv.row_dual(n), slack=sv.row_slack(n), weight=sv.weights(b)) for n, b in sv.lp.rows.items()]
    for label, (col, side) in BOUND_FAMILIES.items():
        blk, x, s = sv.lp.cols[col], sv.var(col), sv.col_dual(col)
        bound = (sv.col_hi if side == "hi" else sv.col_lo)[blk.offset:blk.offset + blk.size].reshape(blk.shape)
        dual = np.minimum(s, 0.0) if side == "hi" else np.maximum(s, 0.0)
        slack = np.abs(bound - x)
        finite = np.isfinite(bound).ravel()
        frame = _frame(blk, dual=dual, slack=slack, weight=sv.weights(blk))[finite]
        frames.append(frame.assign(label=label))
    return pd.concat(frames, ignore_index=True)


def reduced_costs(sv: Solved) -> pd.DataFrame:
    """Column reduced costs s_j (and primal value) for every column family."""
    return pd.concat([_frame(b, value=sv.var(n), reduced_cost=sv.col_dual(n)) for n, b in sv.lp.cols.items()],
                     ignore_index=True)


def economic_table(sv: Solved, eco: Economics) -> pd.DataFrame:
    """Hourly prices and balance residuals per (zone, period, t) (output zone_hourly)."""
    blk = sv.lp.rows["bal"]
    return _frame(blk, demand_mw=sv.case.demand, unserved_mw=sv.var("use"), lmp_usd_mwh=eco.pi,
                  bal_residual_mw=balance_residuals(sv), weight_hours=sv.weights(blk)).drop(columns="label")


def _binding_rows(sv: Solved, tol: float) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """(family, binding mask, weights) over members whose bound is present."""
    out = []
    for name, blk in sv.lp.rows.items():
        out.append((name, sv.row_slack(name) <= tol, sv.weights(blk)))
    for label, (col, side) in BOUND_FAMILIES.items():
        blk = sv.lp.cols[col]
        lo, hi = (v[blk.offset:blk.offset + blk.size].reshape(blk.shape) for v in (sv.col_lo, sv.col_hi))
        bound = hi if side == "hi" else lo
        # a bound of zero (xmax=0, D=0, NTC=0) is trivially binding and carries no information
        present = np.isfinite(bound) & ((hi > 0) if side == "hi" else (lo < 0))
        slack = np.abs(bound - sv.var(col))
        out.append((label, present & (slack <= tol), np.where(present, sv.weights(blk), 0.0)))
    return out


def binding_report(sv: Solved) -> pd.DataFrame:
    """Per label family: count and w_p-weighted share of binding rows/bounds (hook 3)."""
    tol = sv.case.tolerances.binding_slack
    rows = []
    for name, binding, weights in _binding_rows(sv, tol):
        total = weights.sum()
        n_members = int(np.count_nonzero(weights)) if name in BOUND_FAMILIES else binding.size
        rows.append({"family": name, "n_rows": n_members, "n_binding": int(binding.sum()),
                     "weighted_share_binding": float((weights * binding).sum() / total) if total else 0.0})
    return pd.DataFrame(rows)


def binding_bounds(sv: Solved) -> pd.DataFrame:
    """List of binding bounds (x_ub, xP_ub, xE_ub, flow_*, use_ub) with their members."""
    tol = sv.case.tolerances.binding_slack
    frames = []
    for name, binding, _ in _binding_rows(sv, tol):
        if name in BOUND_FAMILIES and binding.any():
            blk = sv.lp.cols[BOUND_FAMILIES[name][0]]
            frames.append(blk.frame()[binding.ravel()].assign(label=name))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["label"])
