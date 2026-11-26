# PLAN

STATUS: IN_PROGRESS (Gate 1 review answered yes to all, DECISIONS 33; closing W6 fixes, then W7 merge)
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
- [x] W4b Verifier [Sonnet]: `tests/test_health*.py` — every §3 health check, dual-sign adapter, scaled/unscaled,
  50 seeded random instances vs `scipy linprog(highs)`, fingerprint determinism (2 processes), 6 audit mutations.
- [x] W4b-fix1 Formulation lead [Opus], branch `gate-1`, no subagents, **spec only, no code**: (a) add an SOC-row
  recomputation health check (rebuild `st_soc` residuals from case η^c, η^d, σ; catches M4) to formulation §8.6 and
  gate-1.md §3; (b) confirm §4 STORAGE_DIS residual = π−VOM−v/η_d; (c) data-schema §3: `fuel` optional for VRE
  (zero-fuel when no `mc_override`); (d) T2c: x^E=0 duals are degenerate → gate-1.md §2/§3 test T2c unscaling on
  primal + π only and "rent ≤ cost". One DECISIONS entry (31). Deliverable: spec diff + DECISIONS 31.
- [x] W4b-fix2 Builder [Sonnet], branch `gate-1`: implement W4b-fix1 (a)–(c) in `capex.audit` / loader; builder smoke
  tests only; do not edit verifier tests. Done when the M4 mutation test passes and the STORAGE_DIS and VRE xfails
  XPASS. Expect CI red on strict XPASS until W4b-v (planned, not a failure).
- [x] W4b-v Verifier [Sonnet], branch `gate-1`: from the amended spec only — remove fixed xfail markers; rewrite T2c
  tests to gate-1.md as amended; add a direct test of the new SOC check (positive + negative case). Full pytest +
  CI must be green (0 fail, 0 xfail left without a DECISIONS reference).
- [x] W4c Verifier [Sonnet], branch `gate-1`: full pytest run + CI; `reports/gate-1-evidence.md` (all 8 parts of
  gate-1.md §5) and pass/fail table in `reports/gate-1-review.md`. Failures → spec-or-code decision in DECISIONS, never tolerance edits.
- [x] W5 Formulation lead [Opus], branch `gate-1`: line-by-line code-vs-spec trace (§2–§6), dual conventions,
  price-setter logic; section in gate-1-review.md. Any builder fix found here becomes its own item.
- [x] W5-fix1 Builder [Sonnet], branch `gate-1`: price-setter (`audit/pricesetter.py:record`) — an hour whose first
  matched class fails its price check must get primary_class=UNEXPLAINED and count as UNEXPLAINED in
  `price_setter_summary` (W5 finding F1). Builder smoke tests only; do not edit verifier tests.
- [x] W5-fix1-test Verifier [Sonnet], branch `gate-1`: from the spec, a fixture where the first matched class fails its
  price check; assert primary_class and summary show UNEXPLAINED (F1). Full pytest + CI green.
- [x] W5-spec1 Formulation lead [Opus], branch `gate-1`, spec only: §6.2 wording — infeasibility scaled vs unscaled
  (text vs table) and the "RHS ratio / any finite bound" row; ratify the code's reading; fold in §5.2 "ANN ≥ I/n" only
  holds for PFF ≥ 1 (F2, F6). One DECISIONS entry.
- [x] W6 PM [Sonnet] + markets reviewer [Opus] + consulting reviewer [Opus] (2 subagents), branch `gate-1`: economic
  sense of T1–T4 and audit readability; PM writes the 7-item owner decision list (gate-1.md §6); STATUS: AWAITING_OWNER_REVIEW.

Owner answered decision 8 = yes on 2026-11-26 (DECISIONS 33) — do these in order:
- [x] W6-spec1 Formulation lead [Opus], branch `gate-1`, spec only: §4 CAPACITY_RENT hour attributed to the INVESTMENT_MARGIN
  unit, else the highest-MC at-cap unit, full list in a separate column (M1); data-schema `rents` per-column units (C1); §10 T2a
  typo 60·0.9 (M6). One DECISIONS entry.
- [x] W6-fix1 Builder [Sonnet], branch `gate-1`: implement M1; flag x = 0 candidate rents `non-unique (bound)` (M2);
  assumptions-book header (run_id, fingerprint, base $ year, "toy case, illustrative only") (C2). Builder smoke tests only.
- [x] W6-spec2 Formulation lead [Opus], branch `gate-1`, spec only: resolve the conflict W6-fix1 found — gate-1.md §3 needs
  byte-identical canonical outputs across runs, but data-sources.md/§8.11 put the per-run random `run_id` in `assumptions.md`.
  Rec: canonical outputs = every output file except `run.json` and the `run_id` line of `assumptions.md`. One DECISIONS entry.
  (CI red on 4 fingerprint-determinism tests until W6-fix1-test; planned, not a regression.)
- [x] W6-fix1-test Verifier [Sonnet], branch `gate-1`: tests for M1, M2, C2 from the amended spec; update the byte-identity
  test to canonical outputs per formulation §8.10 (amendment 4, DECISIONS 36); full pytest + CI green.
- [ ] W7 PM [Sonnet], branch `gate-1`: confirm W6-spec1/fix1/fix1-test done and CI green on the final gate-1 commit; then
  merge `gate-1` into `main` (owner pre-approved, DECISIONS 33 item 7), mark Gate 1 DONE, start `gate-2` from `gate-1`, and
  set STATUS: AWAITING_OWNER_REVIEW until the PM scrum plans Gate 2 items. If CI is red, do not merge: add a fix item instead.

## Prep while awaiting owner review (owner-approved 2026-11-25) — branch `prep`, never merged without owner sign-off
Use when STATUS is AWAITING_OWNER_REVIEW, or when the next gate item is already claimed by another run (owner, 2026-11-26). One item per session, in order. Drafts and raw data only:
no changes to `src/capex/`, no gate branch edits except ticking these boxes and the session log.
- [x] P1 Data lead [Sonnet]: fetch RTS-GMLC (github.com/GridMod/RTS-GMLC) into `cases/raw/rts_gmlc/` (or record
  the pinned commit + file list if too large); add registry rows with provenance per docs/data-sources.md. No model code.
- [ ] P2 Formulation lead [Opus]: draft `docs/gates/gate-2.md` (CI + data-download workflow) and `docs/gates/gate-3.md`
  (PJM 5-bus: DC power flow per §7.4a, expected LMPs/congestion with sources and tolerances). Marked DRAFT for owner.
- [ ] P3 Data lead [Sonnet]: PJM 5-bus case data into `cases/raw/pjm5bus/` from a published source available offline or
  on GitHub (e.g. a MATPOWER/PowerModels case file); provenance; note any source that needs owner download.
- [ ] P4 Builder [Sonnet]: draft `.github/workflows/data-download.yml` (EIA-860/923, NREL ATB) as `workflow_dispatch`
  only, not scheduled; caches to artifacts; never commits raw data. Draft for Gate 2 review.
- [ ] P5 Data lead [Sonnet]: convert the P1 RTS-GMLC raw data into the model's input schema (docs/data-schema.md) under
  `cases/rts_gmlc/` with provenance; loader smoke check only. Needs P1 done.
- [ ] P6 Verifier [Sonnet]: draft `tests/draft/test_pjm5bus.py` from the P2 Gate 3 draft (expected LMPs/congestion),
  marked skip until Gate 3. Needs P2 done.
- [ ] P7 Formulation lead [Opus]: detail §7.1 representative-period selection (clustering features incl. daily fuel
  price, forced peak/scarcity/extreme periods, weights, inter-period SOC linking) into a Gate 5 spec draft.
- [ ] P8 Markets reviewer [Sonnet]: notes on PJM RPM mechanics for Gate 14 (VRR curve parameters, Net CONE, ELCC
  classes, BRA timing) as `docs/drafts/pjm-rpm-notes.md`, every number cited or marked "verify".
- [ ] P9 Consulting reviewer [Sonnet]: outline of the Gate 15 storage value study (`docs/drafts/storage-study-outline.md`):
  client questions, outputs, charts, sanity ranges.
- [ ] P10 Data lead [Sonnet]: EIA-860/923 field mapping to data-schema.md (`docs/drafts/eia-mapping.md`), incl. the
  estimation hierarchy for missing heat rates, min gen, ramp, outage rates.


## Next
W6-fix1-test done 2026-11-26: verifier tests for M1/M2/C2 + canonical-output determinism (DECISIONS 36) in `tests/test_reporting_w6.py`, `tests/test_health_fingerprint.py`; 460 pass / 0 fail; CI run 57 green. Next: W7 (PM) confirms CI green on final gate-1 commit, then merges gate-1 → main (pre-approved, DECISIONS 33 item 7).
W6-spec2 done 2026-11-26 (F-0.2 amendment 4, DECISIONS 36): canonical outputs = all output files except `run.json`, `assumptions.md` minus its one `- run_id:` line; tables carry no `run_id` column (data-schema §5). Spec only. Next: W6-fix1-test (verifier) updates the determinism test + M1/M2/C2 tests; CI should then go green.
W6-fix1 done 2026-11-26: M1 (`rent_ids`, setters = INVESTMENT_MARGIN units else highest-MC), M2 `rent_note`, C2 header + toy banner. 435 pass / 4 fail: the random run_id in assumptions.md breaks the verifier's byte-identity test (spec conflict) → new item W6-spec2, then W6-fix1-test also updates that test. Next: W6-spec2.
W6-spec1 done 2026-11-26 (F-0.2 amendment 3, DECISIONS 35: M1 attribution rule + `rent_ids`, M2 `rent_note`, C1 units, C2 header/banner, M6 typo; spec only). Next: W6-fix1 (builder) implements M1, M2, C2 per the amended spec.
Owner answered Gate 1 review 2026-11-26: yes to all 9 (DECISIONS 33) and RTS-GMLC internal use (DECISIONS 34). Next: W6-spec1 (Opus), W6-fix1, W6-fix1-test, then W7 merge. Prep lane keeps running: a run that finds the next gate item claimed takes the next prep item (owner, 2026-11-26).
P1 done 2026-11-26 on `prep`: RTS-GMLC commit 3ece0d3, 43-file subset (9 MB) in `cases/raw/rts_gmlc/` incl. PLEXOS DA reference solutions; full MANIFEST.csv. Next prep: P2. Finding for Gate 2 list: fingerprint `git_state` splits untracked paths on whitespace (fails on paths with spaces); `data/common/sources.csv` is hashed by case manifests, so registry rows there need a re-hash at P5.
AWAITING OWNER REVIEW of Gate 1 (reports/gate-1-review.md, 9-item decision list). Meanwhile runs take prep items P1… on `prep`.
W6 done 2026-11-26: markets + consulting reviews (Opus) both yes, no blockers; 4 should-fix (M1, M2, C1, C2) → proposed W6-spec1/fix1/fix1-test if decision 8 = yes. 438 pass. W6 (PM + markets + consulting reviewers): economic sense, owner decision list, then STATUS: AWAITING_OWNER_REVIEW. W5-spec1 done 2026-11-26 (spec wording only, DECISIONS 32; 438 pass). W5-fix1-test done 2026-11-26 (9 verifier tests, 438 pass). W5-fix1 done 2026-11-26 (one-line fix in `record`). W5 done 2026-11-25: formulation trace in
reports/gate-1-review.md — code implements F-0.2 amendment 1 for the toy scope, no blockers; 2 should-fix (F1 code,
F2 spec) → W5-fix1, W5-fix1-test, W5-spec1; then W6. Later-gate findings for the Gate 2 criteria list (P2 draft):
F3 explicit zeros in A when availability 0 (`eliminate_zeros`), F4 zero-profit check skips xE for free-duration
storage, F5 ScipyHighsSolver loses ≤ dual on two-sided rows.
Rule (DECISIONS 26): buy nothing; simplest model first — add complexity only in its gate, after the simpler model passes.

## Needs owner
- (answered 2026-11-26, DECISIONS 34: yes) 2026-11-26 P1: RTS-GMLC has no LICENSE file and no terms in README. OK to use it as an internal test system (vendored subset in repo, cited, not in client deliverables) until terms are confirmed? rec yes.
- (answered 2026-11-26, DECISIONS 33: yes to all) 2026-11-26 W6: Gate 1 review — 9 yes/no decisions in reports/gate-1-review.md (all rec yes; merge after W6 fixes + green CI).
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
