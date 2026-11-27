# PLAN

STATUS: AWAITING_OWNER_REVIEW
CURRENT GATE: 3 (PJM 5-bus) — not started: waiting for owner approval of docs/gates/gate-3.md (draft); branch `gate-3` to be created from `gate-2` on approval
GATE 2: approved by owner 2026-11-27 (DECISIONS 42); merged into `main` 2026-11-27 on owner instruction (live session)
GATE 1: approved by owner 2026-11-26 (DECISIONS 33, 37); merged into `main` 2026-11-26 on owner instruction
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
- [x] W7a PM [Sonnet], branch `gate-1`: confirm W6-spec1/fix1/fix1-test done and CI green on the final gate-1 commit;
  merge-readiness note `reports/gate-1-merge-readiness.md`. Done 2026-11-26: all done, CI run 58 green on 7c7837f, 460 pass
  locally; one trivial CLAUDE.md conflict vs `main` (take gate-1's version). Merge NOT done: the scheduled-run prompt says
  runs never merge to main or mark a gate done, which overrides DECISIONS 33 item 7 for unattended runs.
- [x] W7b OWNER ACTION: merged `gate-1` into `main` 2026-11-26 (owner instruction); Gate 1 DONE; `gate-2` created from `main` with prep P1–P10 merged in
  (or tell runs they may, by changing the scheduled-task prompt). Then the PM scrum plans Gate 2 items.

## Gate 2 work items — branch `gate-2` (criteria: docs/gates/gate-2.md, approved 2026-11-26, DECISIONS 38)
One per session, strictly in order; claim before work (CLAUDE.md).
- [x] G2-1 Builder [Sonnet]: CI criteria C1–C4, C8–C9 — `requirements-ci.txt` (exact pins), `ubuntu-24.04`, version block,
  junit XML + log artifacts, runtime report, pytest-socket (no network in tests). Builder smoke checks only.
- [x] G2-2 Builder [Sonnet]: CI criteria C5–C7 — `xfail_strict`, marker-reason checker script, health-run job over T1–T4 with
  output artifacts, two-job fingerprint comparison with different PYTHONHASHSEED.
- [x] G2-2-fix Verifier [Sonnet]: `tests/draft/test_pjm5bus.py:118` is a strict xfail with no `Gate <n>`/`DECISIONS <n>` in its
  reason and drafts must be skips (C5) → make it a skip citing `Gate 3` (keep the 14,957.28 vs .29 note). CI `test` job is red on
  the C5 marker step until then (planned, not a regression). Run `scripts/check_markers.py` + full pytest; CI green.
- [x] G2-3 Builder [Sonnet]: data-download workflow D1–D8 end to end for `pjm5` (pinned MATPOWER case5.m) using the P4 draft;
  consumer-side verify script. EIA/ATB steps stay declared-but-disabled.
- [x] G2-4 Builder [Sonnet]: carried code findings F3, F4, F5, P1-a (gate-2.md §4). No verifier tests here.
- [x] G2-5 Verifier [Sonnet]: tests from the spec for F3, F4, F5, P1-a and for the C5 checker (a marker without a reason fails).
- [x] G2-6 Formulation lead [Opus]: P1-b decision (keep or exclude `sources.csv` from case manifests) + DECISIONS entry; refresh
  gate-2.md header to "approved".
- [x] G2-7 Verifier [Sonnet]: `reports/gate-2-evidence.md` (§5 parts 1–8). Done 2026-11-26: C1–C9 pass on CI #107; parts 3–4
  (Actions dispatches) blocked by V2-1 — `data-download.yml` is invalid YAML (line 79), so GitHub has no dispatch trigger.
- [x] G2-7a Builder [Sonnet]: fix V2-1 — line 79 of `.github/workflows/data-download.yml` as a block scalar (`run: |`); add a
  `ci.yml` step that parses every `.github/workflows/*.yml` (PyYAML `safe_load`) and fails on error. No verifier tests here.
  Then copy **only** that fixed file onto `main` (commit "copy fixed data-download.yml to main (DECISIONS 41)"; owner-approved
  2026-11-26, DECISIONS 41 — the one exception to "never touch main"; no other file, no merge) and confirm the dispatch API accepts it.
- [x] G2-7b Verifier [Sonnet]: unblocked — fixed data-download.yml copied to `main` 2026-11-26 (9671c02, owner live approval; workflow registered as `data-download`, active). Dispatch `data-download.yml` (ref `gate-2`,
  `source_id=pjm5`) twice (D5 equal hashes) and once from a throwaway branch with a corrupted manifest hash (D3 fails,
  nothing uploaded; delete the branch after); fill gate-2-evidence.md §3–§4 and the D table.
- [x] G2-8 PM [Sonnet] + markets reviewer [Sonnet] (1 subagent): `reports/gate-2-review.md` pass/fail table and owner yes/no
  list; STATUS: AWAITING_OWNER_REVIEW.

## Prep while awaiting owner review (owner-approved 2026-11-25) — branch `prep`, never merged without owner sign-off
Use when STATUS is AWAITING_OWNER_REVIEW, or when the next gate item is already claimed by another run (owner, 2026-11-26). One item per session, in order. Drafts and raw data only:
no changes to `src/capex/`, no gate branch edits except ticking these boxes and the session log.
- [x] P1 Data lead [Sonnet]: fetch RTS-GMLC (github.com/GridMod/RTS-GMLC) into `cases/raw/rts_gmlc/` (or record
  the pinned commit + file list if too large); add registry rows with provenance per docs/data-sources.md. No model code.
- [x] P2 Formulation lead [Opus]: draft `docs/gates/gate-2.md` (CI + data-download workflow) and `docs/gates/gate-3.md`
  (PJM 5-bus: DC power flow per §7.4a, expected LMPs/congestion with sources and tolerances). Marked DRAFT for owner.
- [x] P3 Data lead [Sonnet]: PJM 5-bus case data into `cases/raw/pjm5bus/` from a published source available offline or
  on GitHub (e.g. a MATPOWER/PowerModels case file); provenance; note any source that needs owner download.
- [x] P4 Builder [Sonnet]: draft `.github/workflows/data-download.yml` (EIA-860/923, NREL ATB) as `workflow_dispatch`
  only, not scheduled; caches to artifacts; never commits raw data. Draft for Gate 2 review.
- [x] P5 Data lead [Sonnet]: convert the P1 RTS-GMLC raw data into the model's input schema (docs/data-schema.md) under
  `cases/rts_gmlc/` with provenance; loader smoke check only. Needs P1 done.
- [x] P6 Verifier [Sonnet]: draft `tests/draft/test_pjm5bus.py` from the P2 Gate 3 draft (expected LMPs/congestion),
  marked skip until Gate 3. Needs P2 done.
- [x] P7 Formulation lead [Opus]: detail §7.1 representative-period selection (clustering features incl. daily fuel
  price, forced peak/scarcity/extreme periods, weights, inter-period SOC linking) into a Gate 5 spec draft.
- [x] P8 Markets reviewer [Sonnet]: notes on PJM RPM mechanics for Gate 14 (VRR curve parameters, Net CONE, ELCC
  classes, BRA timing) as `docs/drafts/pjm-rpm-notes.md`, every number cited or marked "verify".
- [x] P9 Consulting reviewer [Sonnet]: outline of the Gate 15 storage value study (`docs/drafts/storage-study-outline.md`):
  client questions, outputs, charts, sanity ranges.
- [x] P10 Data lead [Sonnet]: EIA-860/923 field mapping to data-schema.md (`docs/drafts/eia-mapping.md`), incl. the
  estimation hierarchy for missing heat rates, min gen, ramp, outage rates.


## Next
Gate 2 DONE 2026-11-27: merged `gate-2` → `main` on owner instruction. Throwaway branch `g2-7b-broken-hash` neutralized (correct hash restored, 3a8872a) but not deleted (403) — owner deletes when at GitHub. Branch protection on `main` still owner action. Next: owner approves gate-3.md (incl. 0.01 MW dispatch tolerance, P5e load scan), then PM writes Gate 3 items (add markets a/b + Actions bump, DECISIONS 42).
Owner answered Gate 2 review 2026-11-27: yes to all 9 (DECISIONS 42). Remaining owner actions before Gate 2 DONE: delete `g2-7b-broken-hash`, enable branch protection on `main` (require `ci`), merge `gate-2` → `main`. Then: PM drafts Gate 3 items (incl. markets a/b, Actions bump).
G2-8 done 2026-11-27 on `gate-2`: `reports/gate-2-review.md` — all C1–C9, D1–D8, F3–F5, P1-a/b pass (D4/D5/D7 carried limitations); history audit clean (no secrets, no downloaded raw data); markets reviewer yes, 6 forward should-fix notes. STATUS: AWAITING_OWNER_REVIEW — 9 yes/no items for the owner. Next: owner review; prep lane only.
G2-7b done 2026-11-27 on `gate-2` (440fe60, 3f58682): Actions runs 45916594450 + 45916775025 (gate-2, pjm5) both success, all_verified=True with identical pinned file hashes (D5 pass; zip digests differ, likely provenance timestamps/run id — not inspected); run 45916853288 on throwaway branch fails at "Fetch and verify" (HASH MISMATCH case5.m), later steps skipped, 0 artifacts (D3 pass). D1–D8 pass (D2/D8 local, D4 partial: artifact contents/step summary not readable here, blob 403). Throwaway branch NOT deleted (403) → Needs owner. Next: G2-8.
Owner action done 2026-11-26: fixed data-download.yml on `main` (9671c02), dispatch trigger registered. Next: G2-7b (verifier) dispatch evidence, then G2-8.
G2-7a done 2026-11-26 on `gate-2` (fc90b77): data-download.yml line 79 → `run: |` block scalar; new `scripts/check_workflows.py` (PyYAML safe_load, already pinned 6.0.3) as CI step "Parse workflow files"; shown to fail (exit 1, line 79) with the fix reverted. Local 547 pass / 30 skip / 0 fail; check_markers exit 0. **Copy to `main` NOT done**: the run's push to `main` was refused by the session's safety guard and the scheduled prompt says "never on main" → owner action (Needs owner). Next: owner copies the file to `main`, then G2-7b.
G2-7a (builder, Sonnet): fix V2-1 (data-download.yml YAML error, line 79) + workflow-parse CI step; then copy just that file to `main` (DECISIONS 41); then G2-7b dispatch evidence; then G2-8.
G2-7 done 2026-11-26: `reports/gate-2-evidence.md`. CI #107 green (547 pass / 30 skip / 0 fail, ≈63 s, versions = pins, 7/7 cases identical across seeds, objectives = local exactly). Dispatch refused: data-download.yml does not parse (V2-1), on `main` and `gate-2`; local fetch/verify pass D2–D5 (repeat hashes equal; corrupted hash exits 1, nothing kept). C3/C7-π not inspected directly (artifact download blocked here).
G2-7 (verifier, Sonnet): `reports/gate-2-evidence.md` (§5 parts 1–8); trigger the data-download dispatches (pjm5, then broken-hash on a throwaway branch) if the session can.
G2-6 done 2026-11-26: P1-b = exclude `data/common/sources.csv` from manifest sha256 pins (DECISIONS 40); T1–T4 `case.yaml` edited, data-schema §5/§6.1 amended, gate-2.md P1-b closed + [P] note confirmed (header already "approved"). Registry stays in the run fingerprint; append-only ids. Local 547 pass / 30 skip / 0 fail; check_markers exit 0.
G2-5 done 2026-11-26: verifier tests `tests/test_gate2_findings.py` (27: F3 nnz/no stored zeros, F4 xE- and xP-only reduced-cost corruption flagged by zero_profit for free-duration candidate storage, F5 ranged-row dual −2 upper / +1 lower and = HighsSolver, P1-a spaced untracked paths) + `tests/test_check_markers.py` (19, C5). Run against pre-fix code (faaa9cd^): 10 of the F3–F5/P1-a tests fail, so they catch the original bugs. Local 547 pass / 30 skip / 0 fail; check_markers exit 0.
G2-4 done 2026-11-26: F3 `_triplets` → `eliminate_zeros()` (shape kept); F4 free-duration candidate storage checks both s_xP and s_xE vs own build status (§3 check 5); F5 `ScipyHighsSolver` ranged row keeps ≤ dual and adds ≥ dual (`+=`); P1-a `git_state` untracked list via `ls-files -z`, split on NUL. 4 builder smoke tests in `tests/builder/test_builder_g2_4_smoke.py`. Local 501 pass / 30 skip / 0 fail; T1–T4 health runs ok, outputs unchanged. No spec change.
G2-3 done 2026-11-26: data-download.yml gate-grade (ubuntu-24.04, dispatch only, `contents: read`, provenance + hash table in step summary, skip note for disabled/keyless sources); `verify_artifact.py --against <vendored dir>` and `--summary`; new consumer `scripts/fetch_artifact.py` (gh run download → verify); 16 builder smoke tests (offline, file:// URLs). Live fetch of pjm5 from this workspace verified both pinned hashes. Local 497 pass / 30 skip / 0 fail. Not yet run on Actions: dispatch needs data-download.yml on `main` (Needs owner).
G2-2-fix done 2026-11-26: `tests/draft/test_pjm5bus.py` congestion-surplus marker is now `skip` citing `Gate 3` (14,957.28 vs .29 note kept; fix the value at Gate 3 approval). `check_markers.py` exit 0, `--self-test` exit 1; local 481 pass / 30 skip / 0 xfail / 0 fail.
G2-2 done 2026-11-26 (d734cc5): `xfail_strict = true`; `scripts/check_markers.py` (ast; `--self-test` must exit 1) as a CI step; `health-run` matrix job (PYTHONHASHSEED 0/12345) runs T1, T2a–c, T3a–b, T4 via `python -m capex run` with `scripts/ci_health_run.py` (fails on health `fail` or UNEXPLAINED), uploads `health-seed-<seed>`; `compare` job runs `scripts/compare_runs.py` (fingerprints + canonical outputs byte-identical; `--numeric` = local-vs-CI obj/π rel 1e-9). Local: 481 pass / 29 skip / 1 xfail / 0 fail; 7/7 cases healthy and identical across seeds. Not yet proven on Actions.
G2-2 (builder): CI criteria C5–C7 (xfail_strict, marker-reason checker, health-run job, two-job fingerprint comparison).
G2-1 done 2026-11-26: ci.yml on ubuntu-24.04/Py 3.12, installs from exact-pinned `requirements-ci.txt` (numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, highspy 1.16.0, pytest 9.1.1, pytest-socket 0.8.1) + `-e . --no-deps`; version block via `capex.audit.fingerprint.package_versions()` + HiGHS; `pytest -v --disable-socket --junitxml`, junit+log artifacts 30 d; wall time in step summary (warn >10 min); `contents: read`, no secrets. Local, network off: 481 pass / 29 skip / 1 xfail / 0 fail. Note: pyproject `test` extra lacks pytest-socket/pandas (CI uses the pins).
P9 done 2026-11-26 on `prep` (8c68935): DRAFT `docs/drafts/storage-study-outline.md` (258 lines, 8 sources, 25 "(verify)"). Revenue stack energy+reserves+capacity (ELCC×BRA) vs ATB annualized cost by 2/4/6/8 h; 4 h capacity ≈ $60–71/kW-yr at collared 2026/27–2028/29 BRAs, $119.5 uncollared sim (computed); perfect-foresight haircut; 6 owner decisions at end. Gaps: no PJM 2 h ELCC class; no public PJM arbitrage/reserve revenue ranges found (IMM SOM to read). Next prep: P10.
P8 done 2026-11-26 on `prep` (6c1e9c7): DRAFT `docs/drafts/pjm-rpm-notes.md` (481 lines, 23 sources, 37 "(verify)"). 2028/29 BRA held (Jul 2026): $325.00 cap in every LDA, 6,831 MW short; 2029/30 BRA due Dec 2026 (cap $337.83/floor $181.91). Collar 2026/27–2029/30 (FERC ER26-1556); new VRR points 99/101.5/106% from 2028/29 (ER26-455); CT reference resource kept; ELCC class tables 2026/27–2028/29. Next prep: P9.
P7 done 2026-11-26 on `prep` (d5eca74): DRAFT `docs/drafts/gate5-rep-periods-spec.md` (replacement §7.1–§7.2 + §8 additions) and `docs/gates/gate-5.md`. Ward hierarchical + medoid (deterministic, no seed); per-zone 72-h load/wind/solar/net-load + daily fuel features, z-scored, group-weighted; forced peak/net-peak/VRE-drought/fuel-spike/event blocks at weight 1; optional annual-total rescaling (default on); Kotzur superposition inter-period SOC; prices = dual/w_p, link-row dual = water value; 6 new health checks, M11–M15; toy T5 answers checked by an independent 8784-h LP. 10-item owner decision list at end of gate-5.md (incl. a test-only full-chronology expansion run on RTS-GMLC as an exception to DECISIONS 3). Next prep: P8.
P6 done 2026-11-26 on `prep` (5fd6057): DRAFT `tests/draft/test_pjm5bus.py` + README. Independent scipy DC-OPF (angle + PTDF, any reference bus) reproduces gate-3.md §2 (LMPs, dispatch, cost, only D–E binding, μ≈62.32, decomposition, rent identity, KVL): 21 pass now; 1 strict xfail — draft surplus 14,957.28 should read 14,957.29 (= 62.32204×240; fix in gate-3.md at approval). P5a–P5f, §4 checks, M7–M10: 29 skipped until Gate 3, with 12 SPEC-GAP notes for W-spec (config keys, output columns, μ sign, check ids, α output, mutation hooks). Full suite 459 pass / 29 skip / 1 xfail. Next prep: P7.
P5 done 2026-11-26 on `prep` (0386daa): `cases/rts_gmlc/` (3 zones, 4 links, 155 resources: 73 TH/81 VRE/1 ST; 14,549.8 MW = gen.csv), 8784 h as 122 consecutive 72-h blocks (loader fixes T=72), gzipped availability, per-cell provenance + assumptions register; `scripts/convert_rts_gmlc.py` regenerates byte-identically. Loader validates; 438 pass; not solved. Choices for Gate 4: heat rate = secant incremental PMin→PMax (no no-load term), hydro/RTPV as curtailable VRE, CSP as VRE capped at 200 MW, thermal availability 1.0 (FOR kept as x_ cols), link ratings = summed Cont Rating; PLEXOS reference covers only 336 h. Next prep: P6.
P4 done 2026-11-26 on `prep` (707cee7): DRAFT `.github/workflows/data-download.yml` (dispatch only, `contents: read`, 90-day artifact), `data/manifests/{pjm5,eia860,eia923,atb}.csv`, `scripts/fetch_source.py` + `verify_artifact.py` (stdlib) + `fetch_artifact.md` (D8). pjm5 pinned+enabled; EIA/ATB declared, disabled, unpinned (`pin_mode=record` for first pin); EIA_API_KEY skip pattern. Local checks pass (fetch, repeat-hash, broken pin, unknown id, skips); not yet run on Actions. Gate 2 note: GitHub only dispatches a workflow whose file is on the default branch, so the D5/D3 evidence runs need it on `main` first. Next prep: P5.
P3 done 2026-11-26 on `prep` (23d0d47): MATPOWER `case5.m` vendored in `cases/raw/pjm5bus/` (sha256-pinned, MANIFEST, parsed CSVs); every gate-3.md draft input matches and an independent DC-OPF reproduces LMPs 16.98/26.38/30.00/39.94/10.00 (D-E binds at 240 MW). Case-file licence unverified (see Needs owner). Next prep: P4.
P2 done 2026-11-26 on `prep` (07bd44a): DRAFT `docs/gates/gate-2.md` (CI C1–C9, data-download D1–D8, carried F3–F5 + P1 findings) and `docs/gates/gate-3.md` (pjm5 P5a–P5f; LMPs 16.98/26.38/30.00/39.94/10.00 reproduced by an independent scipy DC-OPF; inputs written from memory → P3 must verify vs MATPOWER case5). Next prep: P3 (P6 now unblocked).
W7a done 2026-11-26: gate-1 is merge-ready (all W6 fixes done, CI run 58 green, 460 pass; one trivial CLAUDE.md conflict). Merge + Gate 1 DONE left to the owner (W7b) because the scheduled-run prompt forbids runs from merging to main or marking a gate done. STATUS: AWAITING_OWNER_REVIEW → runs take prep items (next: P2).
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
- 2026-11-27 Gate 3: approve docs/gates/gate-3.md draft (open: dispatch tolerance 0.01 vs 0.1 MW, rec 0.01; keep P5e load scan, rec yes). Also still open: delete `g2-7b-broken-hash` (neutralized), enable branch protection on `main` requiring `ci`.
- (answered 2026-11-27, yes to all, DECISIONS 42) 2026-11-27 G2-8: Gate 2 review — 9 yes/no decisions in reports/gate-2-review.md (all rec yes; delete `g2-7b-broken-hash` before merging; enable branch protection on `main`).
- 2026-11-27 G2-7b: please delete throwaway branch `g2-7b-broken-hash` (origin, 6894418; only corrupts the case5.m hash in `data/manifests/pjm5.csv`) — deletion returned HTTP 403 from the cloud workspace. Never merge it. Optional: glance at artifact `data-pjm5-default-45916594450` provenance.json (not readable from here) to close D4 fully.
- (answered 2026-11-26, done: copied to `main` at 9671c02 in a live session on owner instruction) 2026-11-26 G2-7a: fixed `.github/workflows/data-download.yml` is on `gate-2` (fc90b77) but could not be copied to `main` — the unattended run's push to `main` was blocked, and the scheduled prompt forbids working on main (conflicts with DECISIONS 41). Please either copy it yourself (`git checkout origin/gate-2 -- .github/workflows/data-download.yml` on main, commit "copy fixed data-download.yml to main (DECISIONS 41)", push) or amend the scheduled prompt to allow exactly this. G2-7b waits on it. rec: copy it yourself.
- (answered 2026-11-26, yes, DECISIONS 41: the G2-7a run copies the fixed file to `main`) 2026-11-26 G2-7: `.github/workflows/data-download.yml` on `main` (f123ad1) is invalid YAML (line 79, `: ` inside an unquoted `run:`), so GitHub never registered its dispatch trigger and logs a failed run on every push. After G2-7a fixes it on `gate-2`, OK to copy the fixed file onto `main` again (same scope as DECISIONS 39), so G2-7b can run the D3/D5 dispatches? rec yes (owner action, or allow a run to do it).
- (answered 2026-11-26, yes, DECISIONS 39; done: file on `main` at f123ad1) 2026-11-26 G2-3: GitHub dispatches a workflow only if its file is on the default branch; `main` lacks `.github/workflows/data-download.yml`, so G2-7 cannot run the D3/D5 evidence dispatches. OK to copy just that one file (dispatch-only, `contents: read`, inert until dispatched) onto `main` now, then `gh workflow run data-download.yml --ref gate-2 -f source_id=pjm5`? rec yes (owner action, or allow a run to do it).
- (answered 2026-11-26, DECISIONS 37–38: yes to all) P3, P5, P8, P9, P10 items and W7a (owner: merge gate-1 now); Gate 2 criteria approved.
- (answered 2026-11-26, yes) 2026-11-26 P10: EIA mapping draft (docs/drafts/eia-mapping.md §end) has 10 yes/no items, all rec yes — e.g. summer net capacity as k0_mw; PUDL preferred over raw EIA; hand-built PJM TO→zone map; 860 Minimum Load accepted only after CEMS cross-check; run pin_mode=record eia860/eia923 workflows to clear verify list. Also: prep list is exhausted — add prep items or do W7b.
- (answered 2026-11-26, yes) 2026-11-26 P9: storage study outline (docs/drafts/storage-study-outline.md §end) has 6 yes/no items, all rec yes — e.g. headline = perfect-foresight value × haircut; capacity shown collar on and off; extend M8.1 to 2/4/6/8 h; 2 h ELCC assumed (no PJM class). Review at Gate 15.
- (answered 2026-11-26, yes) 2026-11-26 P8: 2026/27–2028/29 BRAs all cleared at the collar cap, so M7.1 (≤$25 or ≤20%) would pass trivially. Use 2024/25 and 2025/26 as the pass/fail M7.1 years and report capped years only vs PJM's uncollared simulation + MW shortfall? rec yes. (Also: model year y ↔ delivery year June y–May y+1; details in docs/drafts/pjm-rpm-notes.md.)
- (answered 2026-11-26, yes) 2026-11-26 P5: `data/common/sources.csv` lacks an `rts_gmlc` row; adding it changes the sha256 pinned in T1–T4 manifests. P5 uses a case-local sources copy. OK to append the row + re-hash T* manifests in one commit (at Gate 4)? rec yes. Also: heat-rate choice (secant incremental, no no-load) wants a DECISIONS entry at Gate 4.
- (answered 2026-11-26, yes) 2026-11-26 P3: MATPOWER's LICENSE excludes case files from BSD-3 (`case5.m` is "distributed with permission"). OK to use it as an internal test system (vendored, cited Li & Bo 2010 + MATPOWER, not in client deliverables) as with RTS-GMLC (DECISIONS 34)? rec yes.
- (answered 2026-11-26, yes) 2026-11-26 W7a: gate-1 is merge-ready. The scheduled-task prompt says runs must never merge to main or mark a gate done, so W7's merge (pre-approved in DECISIONS 33 item 7) was not executed. Either (a) merge `gate-1` → `main` yourself (resolve CLAUDE.md by taking gate-1's version), mark Gate 1 DONE, create `gate-2`; or (b) amend the scheduled prompt to allow it and re-open W7b for a run. rec (a). Details: reports/gate-1-merge-readiness.md.
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
