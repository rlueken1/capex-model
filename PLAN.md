# PLAN

STATUS: IN_PROGRESS
CURRENT GATE: 0 (weekend run, branch work only)
OWNER REVIEW: Monday 2026-11-23 (Gate 0 spec + Gate 1 toy model draft)

## Gates (each ends in owner sign-off; criteria in docs/gates/; rules in docs/gates/README.md)
| # | Gate | Core exit evidence |
|---|------|--------------------|
| 0 | Formulation spec | formulation.md, data-schema.md, benchmarks.md, client-questions.md, gate-1 criteria |
| 1 | Toy model + audit layer | known-answer tests; health checks incl. marginal price-setter report |
| 2 | CI | GitHub Actions runs tests on every push; data-download workflow skeleton |
| 3 | Minimal data slice | PJM 2023 load, gas prices, EIA-860 fleet by tech (via Actions) |
| 4 | Scoreboard v0 | crude PJM-wide 2023 fixed-fleet backcast; baseline errors recorded |
| 5 | Rep periods + storage + renewables | weighted 3-day periods (clustered, forced peak/scarcity), inter-period SOC; scoreboard ≥ baseline; complexity ledger |
| 6 | Reserves + shortage pricing | ORDC-style; scoreboard; ledger |
| 7 | Zonal transmission + expansion | interfaces, congestion price-setters; scoreboard; ledger |
| 8 | Clustered linear UC | min gen, startup, ramp; scoreboard; ledger |
| 9 | Capacity market | VRR curve, ELCC accreditation; vs RPM prices; ledger |
| 10 | First client deliverable | storage value study (arbitrage, capacity, reserves vs cost) |
| 11 | Full data pipeline | EIA-860/923, PUDL, ATB, fuels, PJM/NYISO load & LMP, versioned |
| 12 | Calibration + hold-out | 2022–24, calibrate/hold-out split, regression rule, one-off full-year fixed-fleet check |
| 13 | PJM zonal scale | PJM zones, 50+ clusters, multi-year horizon, runtime target |
| 14 | Local web UI | inputs, run, outputs, audit views, scenario manager |
| 15 | NYISO | footprint, ICAP demand curves, benchmarks |
| 16 | Continuous accuracy | scoreboard trend per version |

First use case: **storage value**. Focus throughout: **benchmarking / backcast accuracy**.

## Weekend work items — one per session
- [ ] W1 (Fri) Formulation lead [Opus], branch `gate-0`: `docs/formulation.md` only — full toy scope with dual interpretations, plus Gate 5–9 extensions sketched. Include the marginal price-setter logic.
- [ ] W2 (Sat) Formulation lead [Sonnet], branch `gate-0`: `docs/data-schema.md`, `docs/benchmarks.md` (incl. IMM marginal-fuel metric), `docs/client-questions.md` (10–15), `docs/gates/gate-1.md` (numeric tolerances). Write `reports/gate-0-review.md` with a yes/no decision list.
- [ ] W3 (Sun) Builder [Sonnet], branch `gate-1` (created from `gate-0`; weekend exception: may start before Gate 0 sign-off): toy LP in `src/capex/` + `capex.audit` (balance residuals, duals, binding constraints, objective decomposition, marginal price-setter report). Then set STATUS: AWAITING_OWNER_REVIEW.
- [ ] W4 (after owner review) Verifier [Sonnet], branch `gate-1`: `tests/` from the spec only; run; write `reports/gate-1-evidence.md` and `reports/gate-1-review.md`.

## Next
W1.

## Needs owner
- (none yet)
