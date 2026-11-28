"""CONGESTION_LOOP weights and price interval (formulation 7.4a.7, 7.4a.12): pure linear algebra on marginal buses,
binding AC lines and free DC links, with phi_n = [e_{i(n)}, -H_{K,n}^T] (one lambda column per island of the price
component) and the marginal units imposing Phi [lambda; mu_K] = c_B."""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import scipy.sparse as sp

from ..config import Scaling
from ..model import LP
from ..solver import Solver

SV_TOL = 1e-9          # singular values <= SV_TOL sigma_max count as zero
TIE_EPS = 1e-7         # $/MWh: a TIE_AT_BOUND unit joins M_i only at |pi_m - c_m| <= TIE_EPS (7.4a.7, DECISIONS 60(a))
UNIQUE, NONUNIQUE, INTERVAL = "unique", "weights_nonunique", "interval"
SIDES = (1.0, -1.0)    # minimise, then maximise the target price


class Bound(NamedTuple):
    """A resource at a bound at some bus: pi_m = phi_m z must be >= cost (sense +1, at its cap) or <= cost (-1)."""
    phi: np.ndarray
    cost: float
    sense: int


def phi(h_binding: np.ndarray, nodes: np.ndarray, island_ix: np.ndarray | None = None, n_islands: int = 1) -> np.ndarray:
    """Rows phi_n = [e_{i(n)}, -H_{K,n}] for each node n, shape (len(nodes), n_islands+|K|); h_binding is H[K] (|K|,N).
    `island_ix` is the local island index (0..n_islands-1) of each node within its price component (None: one island)."""
    onehot = np.ones((len(nodes), 1)) if island_ix is None else np.eye(n_islands)[island_ix]
    return np.hstack([onehot, -h_binding[:, nodes].T])


def classify(marginal_phi: np.ndarray) -> str:
    """Case (a) unique, (b) weights non-unique or (c) interval, from Phi (rows: marginal buses, free DC links)."""
    sigma = np.linalg.svd(marginal_phi, compute_uv=False)
    rank = int((sigma > SV_TOL * sigma.max()).sum())
    if rank < marginal_phi.shape[1]:
        return INTERVAL
    return UNIQUE if marginal_phi.shape[0] == marginal_phi.shape[1] else NONUNIQUE


def weights(marginal_phi: np.ndarray, target_phi: np.ndarray) -> np.ndarray:
    """alpha_n^T = phi_n Phi^+ for each target, shape (n_targets, rows of Phi) (= phi_n Phi^-1 when Phi is square)."""
    return target_phi @ np.linalg.pinv(marginal_phi, rcond=SV_TOL)


def _interval_lp(marginal_phi: np.ndarray, cost_b: np.ndarray, sign_k: np.ndarray, bounds: list[Bound],
                 objective: np.ndarray) -> LP:
    """min objective.z over z = [lambda; mu_K]: Phi z = c_B, mu_l sgn f_l >= 0, resources at their bounds."""
    rows = np.vstack([marginal_phi, *(b.phi[None] for b in bounds)])
    lo = np.r_[cost_b, [b.cost if b.sense > 0 else -np.inf for b in bounds]]
    hi = np.r_[cost_b, [b.cost if b.sense < 0 else np.inf for b in bounds]]
    n_lambda = marginal_phi.shape[1] - len(sign_k)
    col_lo = np.r_[np.full(n_lambda, -np.inf), np.where(sign_k > 0, 0.0, -np.inf)]
    col_hi = np.r_[np.full(n_lambda, np.inf), np.where(sign_k > 0, np.inf, 0.0)]
    return LP(a=sp.csr_matrix(rows), c=objective, row_lo=lo, row_hi=hi, col_lo=col_lo, col_hi=col_hi, rows={}, cols={},
              scaling=Scaling.off())


def _point_feasible(marginal_phi: np.ndarray, cost_b: np.ndarray, bounds: list[Bound], point: np.ndarray, tol: float
                    ) -> bool:
    """The solved (lambda, mu_K) satisfies every row of the interval LP within tol (it must, by stationarity)."""
    if np.abs(marginal_phi @ point - cost_b).max(initial=0.0) > tol:
        return False
    return all((b.phi @ point >= b.cost - tol) if b.sense > 0 else (b.phi @ point <= b.cost + tol) for b in bounds)


def side_value(status: str, objective: float, sense: float) -> float:
    """Adapter status map (formulation 7.4a.7): OPTIMAL gives the objective; UNBOUNDED and UNBOUNDED_OR_INFEASIBLE give
    -inf (min) / +inf (max), the LP being feasible; anything else is a failed solve (NaN)."""
    if status == "Optimal":
        return sense * objective
    if status in ("Unbounded", "Primal infeasible or unbounded"):
        return -sense * np.inf
    return np.nan


def interval(solver: Solver, marginal_phi: np.ndarray, cost_b: np.ndarray, sign_k: np.ndarray,
             bounds: list[Bound], target_phi: np.ndarray, point: np.ndarray | None = None, tol: float = 0.0
             ) -> np.ndarray:
    """(n_targets, 2) min and max of pi_n = phi_n z over the feasible set. +-inf if unbounded; NaN marks a failed solve
    (every side is NaN when the solved `point` violates a row, which means the system is mis-built)."""
    out = np.full((len(target_phi), 2), np.nan)
    if point is not None and not _point_feasible(marginal_phi, cost_b, bounds, point, tol):
        return out
    for i, row in enumerate(target_phi):
        for side, sense in enumerate(SIDES):
            sol = solver.solve(_interval_lp(marginal_phi, cost_b, sign_k, bounds, sense * row))
            out[i, side] = side_value(sol.status, sol.objective, sense)
    return out
