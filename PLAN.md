# PLAN

STATUS: IN_PROGRESS
CURRENT GATE: 0 → 1 (weekend run, branch work only)
OWNER REVIEW: Monday 2026-11-23

## Gates
| # | Gate | Exit criteria (owner signs off) |
|---|------|---------------------------------|
| 0 | Spec & metrics | formulation.md, data-schema.md, benchmarks.md, client question list approved |
| 1 | Toy model + audit layer | LP builds/solves on toy cases; energy balance residual = 0; duals = prices; binding-constraint report; known-answer tests pass |
| 2 | Sophistication | weighted 3-day rep periods (clustered, forced peak/scarcity periods), inter-period SOC linking, renewables, storage, reserves/regulation, zonal transmission expansion, linearized clustered UC, VRR capacity demand curve, ORDC/shortage pricing; each feature has tests |
| 3 | Data pipeline | EIA-860/923, PUDL, NREL ATB, fuel prices, PJM/NYISO load & LMP ingested to schema, versioned |
| 4 | Backcast harness + scoreboard | 2022–2024 backcasts; calibrate vs hold-out years; regression rule; one-off full-year fixed-fleet dispatch check of rep periods |
| 5 | Scale to PJM zonal | ~50+ gen clusters, PJM zones, multi-year horizon; runtime target met |
| 6 | Local web UI | inputs, run, outputs, audit views, scenario manager |
| 7 | Continuous accuracy improvement | scoreboard trend tracked per version |

First use case: **storage value** (energy arbitrage, capacity/ELCC, reserves vs build cost).
Focus throughout: **benchmarking and backcast accuracy**.

## Weekend work items (branch `gate-0`, then `gate-1`) — one per session
- [ ] W1 (Fri) Formulation lead [Opus]: draft `docs/formulation.md` (toy scope + Gate 2 extensions sketched), `docs/data-schema.md`, `docs/benchmarks.md`, `docs/client-questions.md` (10–15 questions; consulting + markets reviewers may be consulted once). Commit to `gate-0`.
- [ ] W2 (Sat) Builder [Sonnet]: on branch `gate-1` (from `gate-0`), implement toy LP in `src/capex/` (linopy or plain highspy; single zone, ~4 techs, 1 rep period, capacity + dispatch, unserved energy) plus audit report (balance residuals, duals, binding constraints, objective decomposition).
- [ ] W3 (Sun) Verifier [Sonnet]: write `tests/` from the spec only: screening-curve case, merit-order case, duals = marginal cost, zero-profit for built units, infeasibility/unbounded guards. Run them, record results. Then PM: write `reports/gate-0-review.md` (one page: built, passed, decisions needed) and set STATUS: AWAITING_OWNER_REVIEW.

## Next
W1.

## Needs owner
- (none yet)
