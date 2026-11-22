"""Hook 9: numerical conditioning report on the scaled LP (section 6.2)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .duality import duality_report
from .duals import balance_residuals
from .solved import Solved

# metric -> (warn threshold, fail threshold)
# SPEC-AMBIGUITY: section 6.2 row "RHS ratio / any finite bound" lists 1e6/1e5 (warn) and 1e9/1e7 (fail); read as
# a ratio threshold for the RHS and an absolute-magnitude threshold (scaled units) for finite bounds.
THRESHOLDS = {
    "matrix_ratio": (1e6, 1e9), "objective_ratio": (1e8, 1e11), "rhs_ratio": (1e6, 1e9),
    "bound_max": (1e5, 1e7), "primal_infeasibility": (1e-7, 1e-5), "dual_infeasibility": (1e-7, 1e-5),
    "bal_residual_mw": (1e-3, 1e-1),
}
TINY_COEFFICIENT = 1e-6


@dataclass(frozen=True)
class Conditioning:
    metrics: dict[str, float]
    status: dict[str, str]          # per thresholded metric: pass | warn | fail

    @property
    def worst(self) -> str:
        values = set(self.status.values())
        return "fail" if "fail" in values else "warn" if "warn" in values else "pass"


def _ratio(values: np.ndarray) -> tuple[float, float, float]:
    """(min, max, max/min) of the nonzero finite magnitudes; (0,0,1) if none."""
    mag = np.abs(values[np.isfinite(values) & (values != 0)])
    return (float(mag.min()), float(mag.max()), float(mag.max() / mag.min())) if mag.size else (0.0, 0.0, 1.0)


def primal_infeasibility(sv: Solved) -> float:
    lp, sol = sv.lp, sv.sol
    rows = np.maximum(lp.row_lo - sol.row_activity, sol.row_activity - lp.row_hi)
    cols = np.maximum(lp.col_lo - sol.x, sol.x - lp.col_hi)
    return float(max(rows.max(initial=0.0), cols.max(initial=0.0), 0.0))


def dual_infeasibility(sv: Solved) -> float:
    """Max of stationarity residual |c - A'y - s| and dual-sign violations (scaled)."""
    lp, sol = sv.lp, sv.sol
    residual = np.abs(lp.c - lp.a.T @ sol.row_dual - sol.col_dual).max(initial=0.0)
    return float(max(residual, duality_report(sv).sign_violation))


def classify(metrics: dict[str, float]) -> dict[str, str]:
    return {k: "fail" if metrics[k] > hi else "warn" if metrics[k] > lo else "pass" for k, (lo, hi) in THRESHOLDS.items()}


def conditioning_report(sv: Solved) -> Conditioning:
    lp, sol = sv.lp, sv.sol
    a_min, a_max, a_ratio = _ratio(lp.a.data)
    c_min, c_max, c_ratio = _ratio(lp.c)
    rhs = np.concatenate([lp.row_lo[np.isfinite(lp.row_lo)], lp.row_hi[np.isfinite(lp.row_hi)]])
    b_min, b_max, b_ratio = _ratio(rhs)
    bounds = np.concatenate([lp.col_lo, lp.col_hi])
    bnd_min, bnd_max, _ = _ratio(bounds)
    metrics = {
        "rows": lp.n_rows, "cols": lp.n_cols, "nnz": lp.a.nnz, "matrix_min": a_min, "matrix_max": a_max,
        "matrix_ratio": a_ratio, "objective_min": c_min, "objective_max": c_max, "objective_ratio": c_ratio,
        "rhs_min": b_min, "rhs_max": b_max, "rhs_ratio": b_ratio, "bound_min": bnd_min, "bound_max": bnd_max,
        "tiny_coefficients": int((np.abs(lp.a.data) < TINY_COEFFICIENT).sum()),
        "primal_infeasibility": primal_infeasibility(sv), "dual_infeasibility": dual_infeasibility(sv),
        "bal_residual_mw": float(np.abs(balance_residuals(sv)).max(initial=0.0)),
        "iterations": sol.iterations, "crossover_ran": sol.crossover_ran}
    return Conditioning(metrics=metrics, status=classify(metrics))
