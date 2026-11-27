"""A solved run: case + LP + solution, with everything unscaled to I/O units (formulation 1.1, 6.1)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np

from ..data import Case
from ..model import LP, Block
from ..solver import Solution


@dataclass(frozen=True)
class Solved:
    case: Case
    lp: LP
    sol: Solution

    @cached_property
    def x(self) -> np.ndarray:
        return self.sol.x / self.lp.col_scale

    @cached_property
    def y(self) -> np.ndarray:
        """Row duals in $/yr per unit of row RHS (canonical convention, section 1.3)."""
        return self.sol.row_dual * self.lp.scaling.dual_factor

    @cached_property
    def s(self) -> np.ndarray:
        """Column reduced costs in $/yr per unit of the variable."""
        return self.sol.col_dual * self.lp.scaling.dual_factor

    @cached_property
    def row_activity(self) -> np.ndarray:
        return self.sol.row_activity / self.lp.scaling.k_p

    @cached_property
    def row_lo(self) -> np.ndarray:
        return self.lp.row_lo / self.lp.scaling.k_p

    @cached_property
    def row_hi(self) -> np.ndarray:
        return self.lp.row_hi / self.lp.scaling.k_p

    @cached_property
    def col_lo(self) -> np.ndarray:
        return self.lp.col_lo / self.lp.col_scale

    @cached_property
    def col_hi(self) -> np.ndarray:
        return self.lp.col_hi / self.lp.col_scale

    @cached_property
    def z0(self) -> float:
        return float(self.case.gen.fom0.sum() + self.case.storage.fom0.sum())

    @cached_property
    def z_lp(self) -> float:
        """LP objective in $/yr (excludes the constant Z0)."""
        return float(self.lp.c @ self.sol.x) / (self.lp.scaling.k_c * self.lp.scaling.s_obj)

    @property
    def z_total(self) -> float:
        return self.z_lp + self.z0

    def var(self, name: str) -> np.ndarray:
        return self.lp.cols[name].view(self.x)

    def row_dual(self, name: str) -> np.ndarray:
        return self.lp.rows[name].view(self.y)

    def col_dual(self, name: str) -> np.ndarray:
        return self.lp.cols[name].view(self.s)

    def row_slack(self, name: str) -> np.ndarray:
        """Distance to the nearest finite row bound (0 for equalities)."""
        blk = self.lp.rows[name]
        act, lo, hi = blk.view(self.row_activity), blk.view(self.row_lo), blk.view(self.row_hi)
        return np.minimum(act - lo, hi - act)

    def weights(self, block: Block) -> np.ndarray:
        """w_p broadcast to a block's shape (1 for blocks without a period dimension)."""
        if "period" not in block.dims:
            return np.ones(block.shape)
        shape = [1] * len(block.shape)
        shape[block.dims.index("period")] = len(self.case.periods)
        return np.broadcast_to(self.case.w.reshape(shape), block.shape)
