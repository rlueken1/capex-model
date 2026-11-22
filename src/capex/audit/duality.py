"""Strong duality, complementary slackness and dual-sign checks (section 3 checks 2-4), in scaled units."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .solved import Solved


@dataclass(frozen=True)
class DualityReport:
    primal_obj: float       # scaled LP objective c~'x~
    dual_obj: float         # sum b y + sum bound s
    rel_gap: float
    comp_slack: float       # max |y slack| / max(1, |Z~|) over rows and bounds
    sign_violation: float   # max dual-sign violation (scaled)
    z_primal_usd: float     # unscaled, excludes Z0
    z_dual_usd: float


def _active_side(dual: np.ndarray, lo: np.ndarray, hi: np.ndarray, value: np.ndarray
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each dual: the bound it prices (lo if dual>0, hi if dual<0), the distance of `value` to it, and the sign
    violation (dual pricing an infinite bound)."""
    bound = np.where(dual > 0, lo, np.where(dual < 0, hi, 0.0))
    violation = np.where(np.isfinite(bound), 0.0, np.abs(dual))
    bound = np.where(np.isfinite(bound), bound, 0.0)
    return bound, np.abs(value - bound), violation


def duality_report(sv: Solved) -> DualityReport:
    lp, sol = sv.lp, sv.sol
    rb, rdist, rviol = _active_side(sol.row_dual, lp.row_lo, lp.row_hi, sol.row_activity)
    cb, cdist, cviol = _active_side(sol.col_dual, lp.col_lo, lp.col_hi, sol.x)
    primal = float(lp.c @ sol.x)
    dual = float(sol.row_dual @ rb + sol.col_dual @ cb)
    scale = max(1.0, abs(primal))
    cs = max(np.max(np.abs(sol.row_dual) * rdist, initial=0.0), np.max(np.abs(sol.col_dual) * cdist, initial=0.0))
    k = lp.scaling.k_c * lp.scaling.s_obj
    return DualityReport(primal_obj=primal, dual_obj=dual, rel_gap=abs(primal - dual) / scale,
                         comp_slack=float(cs / scale), sign_violation=float(max(rviol.max(initial=0.0), cviol.max(initial=0.0))),
                         z_primal_usd=primal / k, z_dual_usd=dual / k)
