"""Verifier tests for capex.econ (formulation section 5; gate-1.md section 3 "econ" row).

Written from the spec only. Interface files consulted (public names/signatures only): src/capex/econ.py
(crf, annualize -> Annuity(ann, crf, kappa, pff), fisher_real_rate, to_base_dollars, Deflator,
nominal_wacc, atb_pff). Not consulted: econ implementation bodies, tests/builder/.
"""
from __future__ import annotations

import itertools
import re
from pathlib import Path

import numpy as np
import pytest

from capex import econ

SRC = Path(__file__).resolve().parents[1] / "src" / "capex"


def crf_closed(r, n):
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


# --------------------------------------------------------------- CRF
def test_crf_table_value():
    assert econ.crf(0.07, 20) == pytest.approx(crf_closed(0.07, 20), rel=1e-12)
    assert abs(econ.crf(0.07, 20) - 0.09439) < 5e-6          # table value to 5 decimals


@pytest.mark.parametrize("r,n", [(0.03, 1), (0.05, 10), (0.07, 30), (0.12, 7), (-0.02, 15)])
def test_crf_closed_form(r, n):
    assert econ.crf(r, n) == pytest.approx(crf_closed(r, n), rel=1e-12)


@pytest.mark.parametrize("n", [1, 5, 20, 40])
def test_crf_zero_rate_is_one_over_n(n):
    assert econ.crf(0.0, n) == pytest.approx(1.0 / n, rel=1e-12)


@pytest.mark.parametrize("r", [1e-10, -1e-10, 5e-10, -9e-10, 1e-12])
def test_crf_tiny_rate_uses_zero_branch(r):
    # |r| < 1e-9: exactly the r = 0 branch (the closed form would lose precision / divide by ~0)
    assert econ.crf(r, 20) == pytest.approx(1.0 / 20, rel=1e-12)


@pytest.mark.parametrize("r,n", [(0.07, 0), (0.07, 0.5), (0.07, -3), (0.0, 0), (-1.0, 10), (-1.5, 10)])
def test_crf_invalid_raises(r, n):
    with pytest.raises(ValueError):
        econ.crf(r, n)


def test_annualize_invalid_raises():
    with pytest.raises(ValueError):
        econ.annualize(1000.0, 0.07, 0)
    with pytest.raises(ValueError):
        econ.annualize(1000.0, -1.0, 20)
    with pytest.raises(ValueError):
        econ.annualize(1000.0, 0.07, 20, profile=[1.2, -0.2])          # phi_k >= 0 required


# --------------------------------------------------------------- annualize (simple CRF and ATB-style PFF)
GRID = list(itertools.product([0.0, 0.01, 0.07, 0.15], [1, 5, 20, 40]))


@pytest.mark.parametrize("r,n", GRID)
def test_ann_at_least_i_over_n(r, n):
    I = 1_234_567.0
    for pff in (1.0, 1.1, 1.35):
        a = econ.annualize(I, r, n, pff=pff)
        assert a.ann >= I / n * (1 - 1e-12)


def test_simple_crf_setting():
    I, r, n = 1_000_000.0, 0.07, 20
    a = econ.annualize(I, r, n)                         # PFF = 1, no profile: simple_crf
    assert a.pff == 1.0 and a.kappa == pytest.approx(1.0, rel=1e-15)
    assert a.crf == pytest.approx(crf_closed(r, n), rel=1e-12)
    assert a.ann == pytest.approx(I * crf_closed(r, n), rel=1e-12)


def test_idc_profile():
    I, r, n = 1_000_000.0, 0.07, 20
    phi = [0.3, 0.4, 0.3]
    L = len(phi)
    kappa = sum(p * (1 + r) ** (L - k + 0.5) for k, p in enumerate(phi, start=1))
    a = econ.annualize(I, r, n, profile=phi)
    assert a.kappa == pytest.approx(kappa, rel=1e-12)
    assert a.ann == pytest.approx(I * kappa * crf_closed(r, n), rel=1e-12)
    assert kappa > 1.0


# MACRS half-year tables (IRS Pub. 946, percent), used to recompute PVD independently
MACRS = {5: [20.00, 32.00, 19.20, 11.52, 11.52, 5.76],
         7: [14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46]}


def pff_closed(T, cls, i):
    m = np.array(MACRS[cls]) / 100.0
    pvd = sum(m[k - 1] / (1 + i) ** k for k in range(1, len(m) + 1))
    return (1 - T * pvd) / (1 - T)


@pytest.mark.parametrize("T,cls,i", [(0.26, 5, 0.08), (0.21, 7, 0.065), (0.30, 5, 0.10)])
def test_atb_pff_formula(T, cls, i):
    assert econ.atb_pff(T, cls, i) == pytest.approx(pff_closed(T, cls, i), rel=1e-4)   # IRS tables rounded to 2 dp
    assert econ.atb_pff(T, cls, i) > 1.0                # depreciation shield < 1 => PFF > 1


def test_atb_pff_zero_tax_is_one():
    assert econ.atb_pff(0.0, 5, 0.08) == pytest.approx(1.0, rel=1e-12)


def test_atb_style_end_to_end():
    fd, i_d, i_e, T, infl = 0.5, 0.06, 0.10, 0.26, 0.025
    i_nom = fd * i_d * (1 - T) + (1 - fd) * i_e           # nominal WACC (spec 5.2)
    assert econ.nominal_wacc(fd, i_d, i_e, T) == pytest.approx(i_nom, rel=1e-12)
    r = (1 + i_nom) / (1 + infl) - 1                      # Fisher
    assert econ.fisher_real_rate(i_nom, infl) == pytest.approx(r, rel=1e-12)
    pff = econ.atb_pff(T, 5, i_nom)
    assert pff == pytest.approx(pff_closed(T, 5, i_nom), rel=1e-4)
    I, n = 1_500_000.0, 25
    a = econ.annualize(I, r, n, pff=pff)
    assert a.ann == pytest.approx(I * pff * crf_closed(r, n), rel=1e-12)
    assert a.pff == pytest.approx(pff, rel=1e-15) and a.crf == pytest.approx(crf_closed(r, n), rel=1e-12)
    assert a.ann > econ.annualize(I, r, n).ann            # ATB-style costs more than simple CRF


def test_fixed_om_not_annualized():
    # C_fix = ANN(I) + FOM: annualize() must not touch FOM (it has no FOM argument); sanity on linearity in I
    a1, a2 = econ.annualize(1.0e6, 0.07, 20), econ.annualize(2.0e6, 0.07, 20)
    assert a2.ann == pytest.approx(2 * a1.ann, rel=1e-12)


# --------------------------------------------------------------- Fisher
@pytest.mark.parametrize("i,pi", [(0.08, 0.02), (0.05, 0.0), (0.0, 0.03), (0.1, 0.1), (-0.01, 0.02)])
def test_fisher(i, pi):
    r = econ.fisher_real_rate(i, pi)
    assert r == pytest.approx((1 + i) / (1 + pi) - 1, rel=1e-12, abs=1e-15)
    assert (1 + r) * (1 + pi) - 1 == pytest.approx(i, abs=1e-12)          # round trip
    assert econ.fisher_real_rate(0.05, 0.05) == pytest.approx(0.0, abs=1e-15)


# --------------------------------------------------------------- deflation
def _defl(base):
    idx = {2018: 100.0, 2020: 104.0, 2022: 115.0, 2024: 123.0}
    return econ.Deflator(index=idx, is_projection={y: (y >= 2024) for y in idx}, base_year=base)


def test_deflation_factor_and_identity():
    d = _defl(2024)
    assert econ.to_base_dollars(100.0, 2020, d) == pytest.approx(100.0 * 123.0 / 104.0, rel=1e-12)
    assert econ.to_base_dollars(100.0, 2024, d) == pytest.approx(100.0, rel=1e-15)
    arr = np.array([10.0, 20.0, 30.0])
    out = econ.to_base_dollars(arr, np.array([2018, 2020, 2022]), d)
    assert np.allclose(out, arr * 123.0 / np.array([100.0, 104.0, 115.0]), rtol=1e-12)


@pytest.mark.parametrize("y", [2018, 2020, 2022])
def test_deflation_round_trip(y):
    v = 987.65
    to_2024 = econ.to_base_dollars(v, y, _defl(2024))
    # converting back: treat the 2024$ value as 2024$ and ask for base year y
    back = econ.to_base_dollars(to_2024, 2024, _defl(y))
    assert back == pytest.approx(v, rel=1e-12)


# --------------------------------------------------------------- static scan
ANNUITY_PATTERNS = [
    re.compile(r"\(\s*1(\.0*)?\s*\+\s*[\w\.\[\]\(\)]+\s*\)\s*\*\*"),      # (1 + r) ** n
    re.compile(r"\*\*\s*\(?\s*-?\s*n\b"),                                   # ... ** n / ** -n
    re.compile(r"(?:math|np|numpy)\.pow(?:er)?\(\s*1(\.0*)?\s*\+"),         # np.power(1 + r, n)
    re.compile(r"\b1(\.0*)?\s*\+\s*[\w\.]+\s*\)\s*\*\*"),
]


def _hits(path: Path):
    out = []
    for no, line in enumerate(path.read_text().splitlines(), 1):
        code = line.split("#", 1)[0]
        if any(p.search(code) for p in ANNUITY_PATTERNS):
            out.append((no, line.strip()))
    return out


def test_scan_detects_annuity_math_in_econ():
    assert _hits(SRC / "econ.py"), "scanner is vacuous: it does not even find the annuity math in econ.py"


def test_no_annuity_math_outside_econ():
    offenders = {}
    for f in sorted(SRC.rglob("*.py")):
        if f.name == "econ.py" and f.parent == SRC:
            continue
        h = _hits(f)
        if h:
            offenders[str(f.relative_to(SRC.parent.parent))] = h
    assert not offenders, f"annuity-style math outside capex/econ.py: {offenders}"
