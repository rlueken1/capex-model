"""Tolerances and scaling constants shared by model, solver adapter and audit."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Tolerances:
    """Tolerances of formulation section 4 and docs/gates/gate-1.md section 3."""
    tol_q_abs_mw: float = 1e-3       # tol_q = max(tol_q_abs_mw, tol_q_rel * K_r)
    tol_q_rel: float = 1e-6
    tol_pi_abs: float = 1e-2         # tol_pi = max(tol_pi_abs, tol_pi_rel * |pi|)
    tol_pi_rel: float = 1e-5
    bal_residual_mw: float = 1e-6    # Gate 1 toy requirement (section 3 check 1)
    strong_duality_rel: float = 1e-7
    comp_slack_scaled: float = 1e-8  # |y*slack| / max(1, |Z~|) in scaled units
    dual_sign_scaled: float = 1e-9
    zero_profit_rel: float = 1e-6
    revenue_identity_rel: float = 1e-6
    decomposition_rel: float = 1e-9
    binding_slack: float = 1e-6      # slack (I/O units) at or below which a row/bound is binding

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class Scaling:
    """Section 6.1: x~ = k_P x, Z~ = k_C s_obj Z. Duals unscale with S = k_P / (k_C s_obj)."""
    k_p: float = 1e-3
    k_c: float = 1e-6
    s_obj: float = 1.0

    @property
    def cost_factor(self) -> float:
        """Multiplier on cost coefficients: c~ = c k_C s_obj / k_P."""
        return self.k_c * self.s_obj / self.k_p

    @property
    def dual_factor(self) -> float:
        """S: raw (scaled) duals times S give $/(unit of RHS)."""
        return self.k_p / (self.k_c * self.s_obj)

    @classmethod
    def off(cls) -> "Scaling":
        return cls(1.0, 1.0, 1.0)
