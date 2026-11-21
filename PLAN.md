# PLAN

STATUS: IN_PROGRESS
CURRENT GATE: 0 (weekend run, branch work only)
OWNER REVIEW: Monday 2026-11-23 (Gate 0 spec + Gate 1 toy model draft)

## Gates (each ends in owner sign-off; criteria in docs/gates/; rules in docs/gates/README.md)
Test ladder: analytic toys → PJM 5-bus → RTS-GMLC → GenX cross-check → one PJM zone →
PJM single node → PJM zonal. Features are proven on test systems before touching PJM data.

| # | Gate | Core exit evidence |
|---|------|--------------------|
| **A. Foundation** |||
| 0 | Formulation spec | formulation.md (incl. dollar-year/real-terms rules, single annualization function, scaling plan), data-schema.md, data-sources.md, benchmarks.md (DA LMP first, literature-based error targets, futures comparison), client-questions.md, gate-1 criteria |
| 1 | Toy model + audit layer | known-answer tests; health checks incl. price-setter report, numerical conditioning check, run fingerprint (inputs+code+solver hash) |
| 2 | CI | GitHub Actions tests on every push; data-download workflow skeleton |
| **B. Test systems** |||
| 3 | PJM 5-bus | known LMPs and congestion reproduced; price-setter report correct |
| 4 | RTS-GMLC dispatch | 3 regions, ~150 gens, full-year fixed-fleet dispatch vs published reference results |
| 5 | Rep periods + storage + renewables | weighted 3-day periods (clustered on load, wind, solar, net load, fuel price; forced peak/scarcity/extreme periods), inter-period SOC; vs RTS-GMLC full-year; complexity ledger |
| 6 | GenX cross-check | same inputs as a GenX example (e.g. 3-zone) → compare cost, capacity, prices; differences explained |
| 7 | Reserves + shortage pricing | ORDC-style; on RTS-GMLC; ledger |
| 8 | Zonal transmission + expansion | interfaces, congestion price-setters; on RTS-GMLC; ledger |
| 9 | Clustered linear UC | min gen, starts, ramps; on RTS-GMLC; ledger |
| 10 | Policy + build/retirement realism | state RPS/CES (NJ, MD, IL, VA), RGGI by state, federal credits under current law; annual build limits by tech/zone (queue reality); going-forward-cost retirements; announced retirements/RMR fixed |
| **C. PJM** |||
| 11 | PJM one-zone data slice | e.g. Dominion, 2023; daily hub gas (Tetco M3, Transco Z6, Dominion South); fleet with provenance + estimation hierarchy |
| 12 | Scoreboard v0 (one zone) | fixed-fleet backcast; outages (seasonal maintenance, forced), imports/exports, nuclear/hydro/pumped storage, DR; extreme events (e.g. Winter Storm Elliott) as forced periods; baseline errors |
| 13 | PJM single node | PJM-wide copper-plate backcast; scoreboard |
| 14 | Capacity market | VRR curve, ELCC accreditation; vs RPM clearing prices |
| 15 | First client deliverable | storage value study (arbitrage, capacity, reserves vs build cost) |
| 16 | Full data pipeline | EIA-860/923, PUDL, CEMS, NEEDS, ATB, AEO, fuels, PJM load/LMP/RPM; versioned; assumptions book |
| 17 | Calibration + hold-out | 2022–24 calibrate/hold-out; regression rule; one-off full-year check of rep periods; forward runs vs West Hub futures |
| 18 | PJM zonal + multi-year | PJM zones, 50+ clusters, multi-year horizon, runtime target |
| 19 | Local web UI | inputs, run, outputs, audit views, scenario manager |
| 20 | Continuous accuracy | scoreboard trend per version |

Other RTOs/grids added later, one at a time. First use case: **storage value**.
Focus throughout: **benchmarking / backcast accuracy**. From Gate 5 on, every feature has
an ablation switch, a complexity-ledger row, and must hold or improve its benchmark.

## Weekend work items — one per session
- [x] W1 (Fri) Formulation lead [Opus], branch `gate-0`: `docs/formulation.md` only — toy scope with dual interpretations and price-setter logic; dollar-year/real-terms rules and one annualization function (WACC, life); variable/cost scaling plan; Gate 5–10 extensions sketched (rep-period clustering features incl. fuel price, forced extreme periods, inter-period SOC, reserves, transmission, UC, policy, build limits, retirements).
- [x] W2 (Sat) Formulation lead [Sonnet], branch `gate-0`: `docs/data-schema.md` (provenance fields, dollar-year field), `docs/data-sources.md` (complete registry incl. RTS-GMLC, PJM 5-bus, GenX examples, daily hub gas), `docs/benchmarks.md` (DA LMP first; IMM marginal-fuel; literature error targets; futures comparison; test-ladder targets), `docs/client-questions.md` (10–15), `docs/gates/gate-1.md`. Write `reports/gate-0-review.md` ending in a yes/no decision list.
- [ ] W3 (Sun) Builder [Sonnet], branch `gate-1` (from `gate-0`; weekend exception: may start before Gate 0 sign-off): toy LP in `src/capex/` + `capex.audit` (balance residuals, duals, binding constraints, objective decomposition, price-setter report, conditioning check, run fingerprint). Then set STATUS: AWAITING_OWNER_REVIEW.
- [ ] W4 (after owner review) Verifier [Sonnet], branch `gate-1`: `tests/` from spec only; run; `reports/gate-1-evidence.md`, `reports/gate-1-review.md`.

## Next
W3 (Sun): builder, toy LP + `capex.audit` on `gate-1` (from `gate-0`). First apply the F-0.2 formulation patch (reports/gate-0-review.md findings 1–5) in the same commit, logged in DECISIONS.md.

## Needs owner
- 2026-11-21 W2: Gate 0 review decision list (12 yes/no items) in reports/gate-0-review.md — for Monday review.
- (none open) — 2026-11-20 owner answered W1's 3 questions; see DECISIONS.md 22–24.
