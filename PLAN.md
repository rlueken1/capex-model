# PLAN

STATUS: IN_PROGRESS
CURRENT GATE: 1 (Toy model + audit layer), branch `gate-1`
GATE 0: approved by owner 2026-11-24 (DECISIONS 26–30); merged into `main` 2026-11-24 on owner go-ahead

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
- [x] W3 (Sun) Builder [Sonnet], branch `gate-1` (from `gate-0`; weekend exception: may start before Gate 0 sign-off): toy LP in `src/capex/` + `capex.audit` (balance residuals, duals, binding constraints, objective decomposition, price-setter report, conditioning check, run fingerprint). Then set STATUS: AWAITING_OWNER_REVIEW.

Gate 1 items — start only after owner sign-off on Gate 0 (each one session, branch `gate-1`):
- [x] W4a Verifier [Sonnet]: if decision 16 = yes, fix CI install line first; then `tests/test_known_answers.py`
  (T1–T4 per gate-1.md §2, expected values from closed forms), `tests/test_econ.py`, load-validation tests. Run; CI result.
- [x] W4a-fix Builder [Sonnet]: CI run 18 (numpy 2.5.5 on runner vs 2.5.3 local): `model.py:36 Block.idx` → `np.ravel_multi_index` gets empty *object*-dtype index arrays → `TypeError: only int indices permitted`; 9 tests fail (T1, T3a, T3b, T4 + 5 builder smoke). Cast index arrays to int64; pin/record numpy in fingerprint. Do not edit verifier tests. CI must go green.
- [ ] W4b Verifier [Sonnet]: `tests/test_health.py` — every §3 health check, dual-sign adapter, scaled/unscaled,
  50 seeded random instances vs `scipy linprog(highs)`, fingerprint determinism (2 processes), 6 audit mutations.
- [ ] W4c Verifier [Sonnet]: full pytest run + CI; `reports/gate-1-evidence.md` (all 8 parts of gate-1.md §5) and
  pass/fail table in `reports/gate-1-review.md`. Failures → spec-or-code decision in DECISIONS, never tolerance edits.
- [ ] W5 Formulation lead [Opus]: line-by-line code-vs-spec trace (§2–§6), dual conventions, price-setter logic;
  section in gate-1-review.md. Any builder fix found here becomes its own item.
- [ ] W6 PM [Sonnet] + markets reviewer [Opus] + consulting reviewer [Opus] (2 subagents): economic sense of
  T1–T4 and audit readability; PM writes the 7-item owner decision list; STATUS: AWAITING_OWNER_REVIEW.

## Next
W4b (verifier): `tests/test_health.py` — §3 health checks, dual-sign adapter, scaled/unscaled, 50 random instances vs scipy, fingerprint determinism, 6 audit mutations. Also cover the gaps W4a noted: storage tie (STORAGE_CH/DIS) never exercised in T2a/b; T2c rent_en degenerate (4380 vs 3866.30).
Rule (DECISIONS 26): buy nothing; simplest model first — add complexity only in its gate, after the simpler model passes.

## Needs owner
- (answered 2026-11-24) — all Gate 0 review items 1–16; see DECISIONS.md 26–30.
- (answered 2026-11-24) — merge `gate-0` into `main`: yes, done.
- (answered) 2026-11-21 W2: Gate 0 review decision list (12 yes/no items) in reports/gate-0-review.md — for Monday review.
- (answered) 2026-11-22 W3: confirm F-0.2 spec patch (DECISIONS 25, incl. HiGHS presolve=off default)? rec yes.
- (answered) 2026-11-22 W3: gate-1.md expects CAPACITY_RENT for all T1 mid/peak hours, but degenerate hourly duals make some
  hours TIE_AT_BOUND (price = an at-cap unit's MC). Amend gate-1.md so T1 mid/peak accept CAPACITY_RENT *or*
  TIE_AT_BOUND (block averages still exact)? rec yes.
- (answered) 2026-11-22 W3: deflator table is a 2024-only placeholder (index 100, method=assumed) until the data lead loads BEA
  NIPA 1.1.9 — fine for Gate 1 (toys are 2024$)? rec yes.
- (answered) 2026-11-22 scrum: CI red on `gate-1` (`.[dev]` extra missing; pytest not installed). Let the verifier fix the
  install line at the start of W4a so Gate 1 evidence can come from CI? rec yes.
- (answered) — 2026-11-20 owner answered W1's 3 questions; see DECISIONS.md 22–24.
