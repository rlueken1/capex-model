"""Solver adapters. Every adapter returns duals in the canonical convention of formulation 1.3:
y_i = dZ*/db_i for rows, s_j = c_j - sum_i a_ij y_i for columns (all in scaled units of the LP it was given)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from importlib.metadata import version
from typing import Protocol

import numpy as np
import scipy.optimize as spo
import scipy.sparse as sp

from .model import LP

DEFAULT_HIGHS_OPTIONS: dict = {
    "solver": "simplex", "simplex_strategy": 1, "presolve": "off", "run_crossover": "on", "parallel": "off",
    "threads": 1, "random_seed": 0, "primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9,
}


class SolverError(RuntimeError):
    """Raised when a solve does not end optimal."""


@dataclass(frozen=True)
class Solution:
    x: np.ndarray
    row_dual: np.ndarray
    col_dual: np.ndarray
    row_activity: np.ndarray
    objective: float
    status: str
    iterations: int
    basis_valid: bool
    crossover_ran: bool
    solver_name: str
    solver_version: str
    options: dict = field(default_factory=dict)
    solve_time_s: float = 0.0

    @property
    def optimal(self) -> bool:
        return self.status == "Optimal"


class Solver(Protocol):
    name: str

    def solve(self, lp: LP) -> Solution:
        ...


class HighsSolver:
    """HiGHS via highspy, dual simplex by default (a basic solution is required by the price-setter)."""
    name = "highs"

    def __init__(self, options: dict | None = None) -> None:
        self.options = {**DEFAULT_HIGHS_OPTIONS, **(options or {})}

    def solve(self, lp: LP) -> Solution:
        import highspy
        inf = highspy.kHighsInf
        model = highspy.HighsLp()
        model.num_col_, model.num_row_ = lp.n_cols, lp.n_rows
        model.col_cost_ = lp.c
        model.col_lower_, model.col_upper_ = np.nan_to_num(lp.col_lo, neginf=-inf), np.nan_to_num(lp.col_hi, posinf=inf)
        model.row_lower_, model.row_upper_ = np.nan_to_num(lp.row_lo, neginf=-inf), np.nan_to_num(lp.row_hi, posinf=inf)
        csc = sp.csc_matrix(lp.a)
        model.a_matrix_.format_ = highspy.MatrixFormat.kColwise
        model.a_matrix_.start_, model.a_matrix_.index_, model.a_matrix_.value_ = csc.indptr, csc.indices, csc.data
        h = highspy.Highs()
        for key, value in {"output_flag": False, **self.options}.items():
            h.setOptionValue(key, value)
        h.passModel(model)
        t0 = time.perf_counter()
        h.run()
        elapsed = time.perf_counter() - t0
        info, sol = h.getInfo(), h.getSolution()
        status = h.modelStatusToString(h.getModelStatus())
        return Solution(
            x=np.array(sol.col_value), row_dual=np.array(sol.row_dual), col_dual=np.array(sol.col_dual),
            row_activity=np.array(sol.row_value), objective=float(info.objective_function_value), status=status,
            iterations=int(info.simplex_iteration_count + info.ipm_iteration_count),
            basis_valid=info.basis_validity == highspy.BasisValidity.kBasisValidityValid,
            crossover_ran=info.crossover_iteration_count > 0, solver_name=self.name, solver_version=h.version(),
            options=dict(self.options), solve_time_s=elapsed)


class ScipyHighsSolver:
    """Independent route: scipy.optimize.linprog(method='highs-ds'); marginals already follow the convention."""
    name = "scipy-highs-ds"

    def solve(self, lp: LP) -> Solution:
        a = lp.a.tocsr()
        eq = lp.row_lo == lp.row_hi
        le = ~eq & np.isfinite(lp.row_hi)
        ge = ~eq & np.isfinite(lp.row_lo)
        a_ub = sp.vstack([a[le], -a[ge]]).tocsr()
        b_ub = np.concatenate([lp.row_hi[le], -lp.row_lo[ge]])
        t0 = time.perf_counter()
        res = spo.linprog(lp.c, A_ub=a_ub, b_ub=b_ub, A_eq=a[eq], b_eq=lp.row_lo[eq],
                          bounds=np.column_stack([lp.col_lo, lp.col_hi]), method="highs-ds")
        elapsed = time.perf_counter() - t0
        if res.status != 0:
            raise SolverError(res.message)
        row_dual = np.zeros(lp.n_rows)
        row_dual[eq] = res.eqlin.marginals
        row_dual[le] = res.ineqlin.marginals[:le.sum()]
        row_dual[ge] = -res.ineqlin.marginals[le.sum():]
        return Solution(
            x=res.x, row_dual=row_dual, col_dual=res.lower.marginals + res.upper.marginals,
            row_activity=a @ res.x, objective=float(res.fun), status="Optimal", iterations=int(res.nit),
            basis_valid=True, crossover_ran=False, solver_name=self.name, solver_version=version("scipy"),
            options={"method": "highs-ds"}, solve_time_s=elapsed)


def make_solver(config: dict) -> Solver:
    """Adapter factory from the case's `solver:` map (name, options)."""
    name = config.get("name", "highs")
    if name == "highs":
        return HighsSolver(config.get("options"))
    if name == "scipy":
        return ScipyHighsSolver()
    raise ValueError(f"unknown solver '{name}'")
