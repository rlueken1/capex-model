# Gate 0 review — Formulation spec (prepared 2026-11-21, W2)

Prepared by: formulation lead (main session, Opus) consolidating two formulation-lead
subagents (Sonnet). Independent reviewer roles (markets, consulting) have **not** yet read
the package; the owner may ask for that before sign-off.

## Exit evidence (PLAN.md Gate 0 row)
| Required | File | State |
|---|---|---|
| Formulation incl. $-year/real-terms, single annualize, scaling plan | docs/formulation.md (F-0.1, W1) | done; needs F-0.2 fixes below |
| Data schema (provenance, dollar_year) | docs/data-schema.md | done (G1 tables full, G3–18 sketched) |
| Source registry (RTS-GMLC, 5-bus, GenX, daily hub gas…) | docs/data-sources.md | done; 26 sources; URLs/licences marked "verify" (no network) |
| Benchmarks (DA LMP first, literature targets, futures) | docs/benchmarks.md | done; most targets tagged "[P] proposed" |
| Client questions (10–15) | docs/client-questions.md | done; 14 questions, storage first |
| Gate 1 criteria | docs/gates/gate-1.md | done; proposed, owner approves here |

## Findings (both subagents found these independently unless noted)
1. **Fuel price indexing (defect).** φ is indexed (fuel, period); a 3-day block holds three
   daily gas prices, so daily hub gas (DECISIONS 18) is lost. Schema uses φ(f,p,t).
2. **PJM 5-bus needs DC power flow.** It has loops; §2 transport links cannot reproduce
   published LMPs (Gate 3). Needs a PTDF/KVL option or a relaxed Gate 3 criterion.
3. **F-0.1 not updated for DECISIONS 22–24.** §5.2 still defaults PFF=1; §9 Q1–Q4 still open;
   ATB-style PFF needs tax/depreciation inputs (schema `finance.csv` has them).
4. **Price-setter gap.** §4 VOLL class needs u < D; a full blackout is "UNEXPLAINED".
5. Minor: balance-residual tolerance (§3 1e-6 vs §6.2 1e-3/1e-1); Z⁰ in/out of duality
   check; FOM^P/FOM^E undefined in notation; w_p range [1,40] vs toy w=121.67; remainder-day
   rule differs §1.2 vs §7.1; §4 assumes a basic solution (force simplex/crossover).
6. Literature on backcast error targets is thin; targets are proposals, set before any
   results exist (DECISIONS 21 satisfied only once you confirm them).

## Recommendation
Approve Gate 0 **conditional** on an F-0.2 formulation patch (items 1–5) done as the first
step of W3 on `gate-1`, logged in DECISIONS.md. Nothing here blocks the toy LP.

## Decision list for the owner (yes/no)
1. Approve Gate 0 conditional on F-0.2 fixing findings 1–5? — rec **yes**
2. Fuel price φ(f,p,t) daily within each 3-day period (not a period average)? — rec **yes**
3. Add a DC power-flow (PTDF/KVL) option for Gate 3 rather than relaxing the 5-bus criterion? — rec **yes**
4. Buy one daily regional gas index licence (backcast only) after checking terms; fallback Henry Hub + monthly basis? — rec **yes, check terms first**
5. VRE profiles from NREL WIND Toolkit/NSRDB (not Renewables.ninja, non-commercial)? — rec **yes**
6. Calibrate on 2022+2023, seal 2024 as hold-out until the Gate 13 freeze; leave-one-year-out as secondary? — rec **yes**
7. Accept proposed targets: DA monthly MAE ≤10% good / ≤20% acceptable, hourly r ≥0.60, daily-spread bias ≤20%, marginal-fuel share error ≤5 pp? — rec **yes, but you may tighten/loosen now — never after results**
8. Gate 12 records baselines only; Gate 13 is first to enforce the acceptable tier? — rec **yes**
9. Include `capex.econ` (annualize, deflate) and its tests in Gate 1? — rec **yes**
10. Approve docs/gates/gate-1.md as written (incl. local pytest log as evidence until CI in Gate 2)? — rec **yes**
11. Futures data (ICE/CME): check licence before Gate 17; never commit raw data? — rec **yes**
12. Ask markets + consulting reviewers to read the Gate 0 package before sign-off? — rec **optional (adds ~1 session)**

## Update — PM scrum 2026-11-22 (current state for the Monday review)
- Findings 1–5: fixed in formulation F-0.2 on `gate-1` (DECISIONS 25). Finding 2 is only *sketched* (§7.4a
  `tx.model`); building it waits on your answer to item 3. Finding 6 (thin literature) stands — item 7 below.
- Gate 1 draft (W3) exists on `gate-1`: toy LP, `capex.econ`, `capex.audit`, cases T1–T4. Only builder smoke
  tests so far (9/9 local) — not gate evidence. Verifier tests (W4) wait for your sign-off.
- **New: CI is red on `gate-1`** (run 12, commit b8d9859): `ci.yml` installs `.[dev]` but `pyproject.toml`
  defines the extra as `test`, so pytest is not installed ("pytest: command not found"). Code was never tested in CI.
- `docs/gates/gate-1.md` still cites F-0.1 and lists §4 "spec assumptions" that F-0.2 has now applied;
  the formulation lead should refresh that header when you approve it (no criteria change).
- Known W3 gaps that W4 may hit: CAPACITY_RENT ignores storage at its power cap (could give UNEXPLAINED on
  random storage instances); provenance overrides and monthly deflation not implemented (outside Gate 1 tests).

### Consolidated decision list for Monday (yes/no)
Items 1–12 above, plus:
13. Confirm F-0.2 spec patch (DECISIONS 25), incl. HiGHS `presolve=off` default? — rec **yes**
14. gate-1.md: T1 mid/peak hours may be CAPACITY_RENT *or* TIE_AT_BOUND (block averages stay exact)? — rec **yes**
15. 2024-only placeholder deflator for Gate 1 until BEA NIPA 1.1.9 is loaded? — rec **yes**
16. Let the verifier fix the CI install line (`.[dev]` → `.[test]`) as the first step of W4a, so Gate 1 evidence
    can come from CI rather than a local log? — rec **yes** (one-line test-infra change, no model code)
Reviewers: none needed before Monday. Item 12 (markets + consulting read of Gate 0) stays optional; the same
reviewers read Gate 1 anyway (W6), so rec **no** to keep the schedule.
