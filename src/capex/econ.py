"""Dollar-year conversion and annualization (formulation section 5). All annuity math lives here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

R_ZERO_TOL = 1e-9

# MACRS half-year-convention depreciation tables (percent per year, M+1 entries); normalised on use.
MACRS_PERCENT: dict[int, tuple[float, ...]] = {
    5: (20.00, 32.00, 19.20, 11.52, 11.52, 5.76),
    7: (14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46),
    15: (5.00, 9.50, 8.55, 7.70, 6.93, 6.23, 5.90, 5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 2.95),
    20: (3.750, 7.219, 6.677, 6.177, 5.713, 5.285, 4.888, 4.522, 4.462, 4.461, 4.462, 4.461, 4.462,
         4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 2.231),
}


@dataclass(frozen=True)
class Deflator:
    """BEA GDP implicit price deflator index by calendar year (DEF(y)), plus the projection flag."""
    index: Mapping[int, float]
    is_projection: Mapping[int, bool]
    base_year: int

    def __post_init__(self) -> None:
        if self.base_year not in self.index:
            raise ValueError(f"base year {self.base_year} missing from deflator")


@dataclass(frozen=True)
class Annuity:
    """Result of `annualize` with the pieces printed in the assumptions book."""
    ann: float
    crf: float
    kappa: float
    pff: float


def deflator_factor(dollar_year: int | Sequence[int] | np.ndarray, deflator: Deflator) -> float | np.ndarray:
    """DEF(B)/DEF(y); raises on years missing from the table or future non-projection years."""
    years = np.atleast_1d(np.asarray(dollar_year, dtype=int))
    missing = sorted({int(y) for y in years if int(y) not in deflator.index})
    if missing:
        raise ValueError(f"dollar_year not in deflator table: {missing}")
    future = sorted({int(y) for y in years if y > deflator.base_year and not deflator.is_projection[int(y)]})
    if future:
        raise ValueError(f"dollar_year after base year without projection flag: {future}")
    factor = deflator.index[deflator.base_year] / np.array([deflator.index[int(y)] for y in years])
    return factor if np.ndim(dollar_year) else float(factor[0])


def to_base_dollars(value, dollar_year, deflator: Deflator):
    """Convert real `value` expressed in `dollar_year` dollars to base-year dollars (scalars or arrays)."""
    return value * deflator_factor(dollar_year, deflator)


def fisher_real_rate(nominal: float, inflation: float) -> float:
    """Real rate r = (1+i)/(1+pi) - 1."""
    if nominal <= -1 or inflation <= -1:
        raise ValueError("rates must exceed -1")
    return (1.0 + nominal) / (1.0 + inflation) - 1.0


def crf(r: float, n: float) -> float:
    """Capital recovery factor; r=0 branch (also for |r|<1e-9) is 1/n."""
    if n < 1:
        raise ValueError("life n must be >= 1")
    if r <= -1:
        raise ValueError("rate must exceed -1")
    if abs(r) < R_ZERO_TOL:
        return 1.0 / n
    growth = (1.0 + r) ** n
    return r * growth / (growth - 1.0)


def idc_factor(r: float, profile: Sequence[float] | None) -> float:
    """Interest during construction factor kappa (mid-year spending); 1 without profile."""
    if profile is None:
        return 1.0
    phi = np.asarray(profile, dtype=float)
    if (phi < 0).any() or abs(phi.sum() - 1.0) > 1e-9:
        raise ValueError("construction profile must be non-negative and sum to 1")
    lead = len(phi) - np.arange(1, len(phi) + 1) + 0.5
    return float(np.sum(phi * (1.0 + r) ** lead))


def macrs_shares(class_life: int) -> np.ndarray:
    """MACRS half-year shares for the class life (sum = 1)."""
    if class_life not in MACRS_PERCENT:
        raise ValueError(f"unsupported MACRS class {class_life}")
    pct = np.asarray(MACRS_PERCENT[class_life])
    return pct / pct.sum()


def nominal_wacc(debt_frac: float, debt_rate: float, equity_rate: float, tax_rate: float) -> float:
    """After-tax nominal WACC i = f_d i_d (1-T) + (1-f_d) i_e."""
    return debt_frac * debt_rate * (1.0 - tax_rate) + (1.0 - debt_frac) * equity_rate


def atb_pff(tax_rate: float, macrs_class: int, nominal_rate: float) -> float:
    """NREL ATB-style project finance factor (1 - T PVD)/(1 - T)."""
    shares = macrs_shares(macrs_class)
    pvd = float(np.sum(shares / (1.0 + nominal_rate) ** np.arange(1, len(shares) + 1)))
    return (1.0 - tax_rate * pvd) / (1.0 - tax_rate)


def annualize(overnight: float, r: float, n: float, profile: Sequence[float] | None = None,
              pff: float = 1.0) -> Annuity:
    """ANN(I) = I * kappa * PFF * CRF(r, n) in $/MW-yr (or $/MWh-yr)."""
    if pff <= 0:
        raise ValueError("PFF must be positive")
    factor, kappa = crf(r, n), idc_factor(r, profile)
    ann = overnight * kappa * pff * factor
    if r >= 0 and pff >= 1.0 and ann < overnight / n - 1e-9 * max(1.0, abs(overnight)):
        raise ValueError("ANN < I/n for r >= 0")
    return Annuity(ann=ann, crf=factor, kappa=kappa, pff=pff)
