"""CONGESTION_LOOP weights and price interval (formulation 7.4a.7): pure linear algebra on marginal buses and
binding lines, with phi_n = [1, -H_{K,n}^T] and the marginal units imposing Phi [lambda; mu_K] = c_B."""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import scipy.sparse as sp

from ..config import Scaling
from ..model import LP
from ..solver import Solver

SV_TOL = 1e-9          # singular values <= SV_TOL sigma_max count as zero
UNIQUE, NONUNIQUE, INTERVAL = "unique", "weights_nonunique", "interval"


class Bound(NamedTuple):
    """A resource at a bound at some bus: pi_m = phi_m z must be >= cost (sense +1, at its cap) or <= cost (-1)."""
    phi: np.ndarray
    cost: float
    sense: int


def phi(h_binding: np.ndarray, nodes: np.ndarray) -> np.ndarray:
    """Rows phi_n = [1, -H_{K,n}] for each node n, shape (len(nodes), 1+|K|); h_binding is H[K] of shape (|K|,N)."""
    return np.hstack([np.ones((len(nodes), 1)), -h_binding[:, nodes].T])


def classify(marginal_phi: np.ndarray) -> str:
    """Case (a) unique, (b) weights non-unique or (c) interval, from Phi = marginal_phi (|B| x (1+|K|))."""
    sigma = np.linalg.svd(marginal_phi, compute_uv=False)
    rank = int((sigma > SV_TOL * sigma.max()).sum())
    if rank < marginal_phi.shape[1]:
        return INTERVAL
    return UNIQUE if marginal_phi.shape[0] == marginal_phi.shape[1] else NONUNIQUE


def weights(marginal_phi: np.ndarray, target_phi: np.ndarray) -> np.ndarray:
    """alpha_n^T = phi_n Phi^+ for each target, shape (n_targets, |B|) (= phi_n Phi^-1 when Phi is square)."""
    return target_phi @ np.linalg.pinv(marginal_phi, rcond=SV_TOL)


def _interval_lp(marginal_phi: np.ndarray, cost_b: np.ndarray, sign_k: np.ndarray, bounds: list[Bound],
                 objective: np.ndarray) -> LP:
    """min objective.z over z = [lambda; mu_K]: Phi z = c_B, mu_l sgn f_l >= 0, resources at their bounds."""
    rows = np.vstack([marginal_phi, *(b.phi[None] for b in bounds)])
    lo = np.r_[cost_b, [b.cost if b.sense > 0 else -np.inf for b in bounds]]
    hi = np.r_[cost_b, [b.cost if b.sense < 0 else np.inf for b in bounds]]
    col_lo = np.r_[-np.inf, np.where(sign_k > 0, 0.0, -np.inf)]
    col_hi = np.r_[np.inf, np.where(sign_k > 0, np.inf, 0.0)]
    return LP(a=sp.csr_matrix(rows), c=objective, row_lo=lo, row_hi=hi, col_lo=col_lo, col_hi=col_hi, rows={}, cols={},
              scaling=Scaling.off())


def interval(solver: Solver, marginal_phi: np.ndarray, cost_b: np.ndarray, sign_k: np.ndarray,
             bounds: list[Bound], target_phi: np.ndarray) -> np.ndarray:
    """(n_targets, 2) min and max of pi_n = phi_n z over the feasible set (+-inf if unbounded, NaN if infeasible)."""
    out = np.empty((len(target_phi), 2))
    for i, row in enumerate(target_phi):
        for side, sense in enumerate((1.0, -1.0)):
            sol = solver.solve(_interval_lp(marginal_phi, cost_b, sign_k, bounds, sense * row))
            out[i, side] = sense * sol.objective if sol.optimal else (-sense * np.inf if sol.status == "Unbounded"
                                                                      else np.nan)
    return out
