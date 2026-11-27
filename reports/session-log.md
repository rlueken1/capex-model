# Session log

- 2026-11-19 kickoff: repo set up with CLAUDE.md, PLAN.md, DECISIONS.md, role files. Next: W1 (Fri night).
- 2026-11-20 W1 (formulation lead, Opus) on `gate-0`: wrote docs/formulation.md (F-0.1, 484 lines): conventions, Gate 1 toy LP with labelled constraints, dual interpretations, price-setter algorithm, dollar-year rules + single `annualize` (CRF), scaling/conditioning, Gate 5–10 sketches with ablation switches, audit hooks, known-answer cases T1–T4.
  Tests: none yet (no code). Toy answers checked with scipy HiGHS; highspy not installed here; dual-sign adapter test specified but not run.
  Finding: T1 hourly prices non-unique at capacity → spec tests block averages/intervals; new CAPACITY_RENT price-setter class.
  Needs owner: 3 questions added to PLAN.md "Needs owner" (financing CRF, non-unique prices, base $ year/scarcity price). Next: W2.
- 2026-11-21 W2 (formulation lead; 2 Sonnet subagents) on `gate-0`: wrote docs/data-schema.md, docs/data-sources.md (26 sources), docs/benchmarks.md (M1–M8, proposed targets), docs/client-questions.md (14), docs/gates/gate-1.md, reports/gate-0-review.md.
  Tests: none (docs only). No network: URLs/licences marked "verify".
  Findings: fuel price must be daily φ(f,p,t); PJM 5-bus needs DC power flow; formulation.md not yet updated for DECISIONS 22–24; VOLL price-setter blackout gap → F-0.2 patch at start of W3.
  Needs owner: 12 yes/no decisions in reports/gate-0-review.md. Next: W3.
- 2026-11-22 W3 (formulation lead Opus for F-0.2 patch; builder Sonnet subagent) on new branch `gate-1` (from `gate-0`): formulation F-0.2 (findings 1–5, DECISIONS 22–25, §7.4a DC power-flow sketch); toy LP + `capex.econ` + `capex.audit` (11 hooks, health_report, price-setter, conditioning, fingerprint), solver adapter (HiGHS dual simplex, presolve off), cases T1–T4, CLI `python -m capex run`.
  Tests: 9/9 builder smoke tests pass (not gate evidence); T1–T4 objectives/prices match §10 informally; 120 random instances pass all health checks, UNEXPLAINED=0. Verifier tests not yet written (W4).
  Findings: T1 degenerate hours classed TIE_AT_BOUND vs gate-1.md's CAPACITY_RENT; presolve flips degenerate duals; CAPACITY_RENT ignores storage at power cap; provenance overrides and monthly deflation not implemented.
  Needs owner: STATUS set AWAITING_OWNER_REVIEW; 3 new items in PLAN.md "Needs owner". Next: owner review, then W4.
- 2026-11-22 PM scrum (Sonnet-role PM, scheduled, no subagents) on `gate-1`: STATUS awaiting review → no build work. Checked Gate 0/1 against exit criteria; split W4 into W4a–c + W5 + W6; reports/scrum-2026-11-22.md; gate-0-review.md updated with current state and consolidated 16-item decision list.
  Tests: none run. Finding: CI red on `gate-1` (run 12) — `.[dev]` extra missing, pytest not installed; dashboard had said "passing", corrected.
  Needs owner: decision 16 (CI fix in W4a) added. Next: owner review Mon, then W4a.
- 2026-11-24 scheduled work session on `gate-1`: skipped: awaiting review (STATUS: AWAITING_OWNER_REVIEW; Gate 0 decisions in reports/gate-0-review.md still unanswered). No build work. Next: owner sign-off, then W4a.
- 2026-11-24 owner review (live): owner accepted all 16 Gate 0 recommendations with overrides 'buy nothing' and 'simplest model first' → DECISIONS 26–30; Gate 0 approved; STATUS IN_PROGRESS; gas licence and futures purchase dropped (free fallbacks); daily fuel price deferred to Gate 5, DC power flow to Gate 3. Tests: none run. Needs owner: go-ahead to merge gate-0 into main. Next: W4a.
- 2026-11-24 owner go-ahead (live): merged `gate-0` into `main` (no-ff, clean). F-0.2 patch and DECISIONS 25–30 stay on `gate-1` until Gate 1 is approved. Tests: none run. Next: W4a.
- 2026-11-25 W4a (verifier, Sonnet subagent) on `gate-1`: CI install line fixed (`.[dev]` → `.[test]`); wrote tests/test_known_answers.py (T1–T4, closed-form expected values, gate-1.md §2 tolerances, price-setter classes, binding sets), tests/test_econ.py (CRF, PFF/MACRS, Fisher, deflation, static annuity scan), tests/test_load_validation.py (one bad input each).
  Tests: 90/90 pass locally (81 verifier + 9 builder smoke); CI run 18: install fixed, 81 pass / 9 fail — `TypeError: only int indices permitted` in model.py:36 (`Block.idx`, empty object-dtype arrays into ravel_multi_index) under runner numpy; local numpy 2.5.3 passes. Builder fix added as item W4a-fix.
  Gaps noted: storage STORAGE_CH/DIS tie never triggers in T2a/b (discharge at P cap); T2c rent_en=4380 (degenerate dual at x=0, spec doesn't pin it) — only rent<cost asserted.
  Needs owner: nothing new. Next: W4a-fix, then W4b.
- 2026-11-25 W4a-fix (builder, Sonnet subagent; extra owner-requested run) on `gate-1`: root cause was pandas `.map().to_numpy()` returning object dtype for empty gen/storage subsets, which `np.ravel_multi_index` rejects on the CI runner (not numpy itself — 2.5.5 passed locally). Fixed in data.py (int64) and `Block.idx` (cast + empty-index guard); builder regression test added; verifier tests untouched; no spec change, no pin.
  Tests: 91/91 local (numpy 2.5.3 and 2.5.5); CI run 20 green — first green CI on gate-1.
  Needs owner: nothing. Next: W4b.
- 2026-11-25 W4b (verifier, Sonnet subagent) on `gate-1`: wrote tests/test_health_{checks,fingerprint,random,mutations}.py + tests/healthlib.py (independent scipy linprog LP from spec, 50 seeded random instances, storage-tie toys S1/S2) + conftest.py; all 13 §3 rows and 6 mutations covered (adapter row via five 2-var LPs, since the literal spec LP is degenerate).
  Tests: 411 pass, 1 fail, 4 xfail (strict) locally (~27 s). FAIL = gate finding: mutation M4 (swap η^c/η^d in st_soc) caught by no health check on T2asym. xfails: T2c x^E=0 dual degeneracy breaks unscaling rel 1e-5 and "rent < cost" (spec); STORAGE_DIS setter residual uses π−VOM not π−VOM−v/η_d (code); VRE loader KeyError('fuel') (code).
  CI on gate-1 will be red until W4b-fix. Needs owner: nothing yet (spec wording changes go via formulation lead in W4b-fix). Next: W4b-fix, then W4c.
- 2026-11-25 PM scrum (PM role, scheduled, no subagents) on `gate-1`: STATUS IN_PROGRESS; Gate 1 ~60% (scope + tests done; M4 uncaught, 4 xfails, evidence and reviews to go). Split W4b-fix into W4b-fix1 (spec, Opus), W4b-fix2 (code, Sonnet), W4b-v (verifier test update, Sonnet); reports/scrum-2026-11-25.md.
  Tests: none run. CI run 22 red by design (M4 finding) until W4b-v. Dashboard: Gate 2 evidence line corrected (CI install fixed in W4a).
  Needs owner: nothing. Next: W4b-fix1.
- 2026-11-25 W4b-fix1 (formulation lead role, Opus, main session, no subagents) on `gate-1`: spec-only amendment 1 to F-0.2 (LP unchanged, version string kept) + DECISIONS 31. (a) `storage.soc_recompute` health check: st_soc residual recomputed from case-data η^c/η^d/σ, ≤1e-6 MWh on toys (formulation §3 check 8, §8.6; gate-1.md §3) — catches M4. (b) Confirmed STORAGE_DIS cost = VOM + v/η^d; setter_cost/residual defined per class (§4 Outputs). (c) `fuel` optional for VRE/ST, VRE without mc_override → MC=0 (data-schema §3.3, §6.5). (d) T2c: proved storage duals at x=0 are dual-degenerate, combined rent ∈ [15,465.19, 20,000] (lower end = T2a arbitrage value); T2c tests assert the interval and compare primal/π/generator ρ only across scalings.
  Tests: 411 pass / 1 fail (M4 on T2asym, expected until W4b-fix2) / 4 xfail locally — unchanged, docs only. CI stays red by design.
  Needs owner: nothing now; amendment confirmed at Gate 1 review item 5. Next: W4b-fix2.
- 2026-11-26 W4b-fix2 (builder, Sonnet subagent; main session reviewed diff) on `gate-1`: implemented DECISIONS 31 (a)–(c). `economics.soc_recompute_residual` + health check `storage.soc_recompute` (case-data η^c/η^d/σ, ≤1e-6 MWh) feeds audit status; price-setter STORAGE_DIS cost = VOM + v/η^d, STORAGE_CH = η^c·v; loader accepts VRE/ST without `fuel` (MC 0). 3 builder smoke tests added; verifier tests untouched.
  Tests: 415 pass / 2 fail (strict XPASS, expected: STORAGE_DIS setter columns, VRE no-fuel loader) / 2 xfail (T2c degenerate duals). M4 now caught (4/4). CI red by design until W4b-v.
  Note for W5: builder smoke tests import helpers from tests/healthlib.py (verifier file) — harmless, but W5 may ask for separation.
  Needs owner: nothing. Next: W4b-v.
- 2026-11-26 W4b-v (verifier, Sonnet subagent; main session re-ran pytest) on `gate-1`: from amended spec (DECISIONS 31) — removed 2 strict xfails now passing (STORAGE_DIS setter_cost = VOM + v/η^d with residual check; VRE without fuel → MC 0); replaced T2c xfails with `test_t2c_combined_rent_inside_degenerate_interval` (R^P+4R^E ∈ [15,465.19, 20,000], scaled + unscaled; 1e-2 slack on the 2-dp lower bound); added direct `storage.soc_recompute` tests (6 toys pass; η swap on S2asym/T2asym and σ dropped on an S2 σ=0.02 variant fail).
  CI run 30 then failed 2 random seeds (7, 9; not touched by this item): test helper `cs_and_signs` multiplied a ~1e-16 noise dual by an infinite slack → cs = inf. Verifier fixed the helper per formulation §1.3 (CS only against a finite side; a dual on an infinite side counts as a sign violation) — thresholds unchanged — plus a synthetic unit test.
  Tests: 428 pass / 0 fail / 0 xfail / 0 XPASS locally (~30 s). No xfail markers left in tests/. CI run 31 green.
  Needs owner: nothing. Next: W4c.
- 2026-11-26 W4c (verifier, Sonnet subagent; main session re-ran pytest) on `gate-1`: wrote reports/gate-1-evidence.md (gate-1.md §5 parts 1–8, from CLI runs of T1–T4 + test suite), reports/gate-1-review.md (verifier pass/fail table; W5/W6 sections left as placeholders), and §5(1) artifacts gate-1-pytest.log + gate-1-junit.xml. All rows PASS or N-A (scoreboard/ledger start Gate 5); no failures, so no DECISIONS entry. Fingerprints identical across 2 processes for all 7 cases.
  Tests: 428 pass / 0 fail / 0 xfail locally (~29 s); CI #32 green (428, 21 s) on a3182e4 (same code).
  Notes for W5/W6: fingerprint is environment-bound (local ≠ CI hash); builder smoke tests import tests/healthlib.py; gate-1.md still says CI comes in Gate 2 though CI is live.
  Needs owner: nothing. Next: W5.
- 2026-11-25 W5 (formulation lead, Opus subagent; main session reviewed) on `gate-1`: line-by-line code-vs-spec trace §2–§6,
  dual conventions, price-setter logic → "Formulation trace (W5)" in reports/gate-1-review.md. Verdict: code implements F-0.2
  amendment 1 for the toy scope; dual signs match §1.3 on T1–T4; no blockers. Should-fix: F1 price-setter hours failing the
  primary class's price check keep that class in the summary (code+test) → W5-fix1/W5-fix1-test; F2 §6.2 wording → W5-spec1.
  Later-gate F3–F5 noted in PLAN Next. Tests: none changed; T1–T4 re-solved, all health checks pass. Needs owner: nothing.
- 2026-11-26 W5-fix1 (builder, Sonnet subagent; main session verified) on `gate-1`: `pricesetter.py:record` now labels an hour
  UNEXPLAINED whenever it fails its primary class's price check (formulation §4 Step 2), so its weighted hours go to
  UNEXPLAINED in `price_setter_summary`. One-line change; builder smoke test `tests/builder/test_builder_pricesetter_unexplained.py`
  (perturbed T1 price). Tests: 429 passed, 0 failed, 0 xfail locally. Verifier tests untouched. Needs owner: nothing.
- 2026-11-26 W5-fix1-test (verifier, Sonnet subagent; main session verified) on `gate-1`: new `tests/test_health_pricesetter_unexplained.py`
  written from formulation §4 Step 2 / gate-1 §3 (builder tests not read). Perturbs π by +5 $/MWh in up to 3 MARGINAL_UNIT hours of T1/S1/S2:
  asserts primary_class=UNEXPLAINED, summary moves exactly those weighted hours from MARGINAL_UNIT to UNEXPLAINED, zone totals = Σw·72; control has 0 UNEXPLAINED.
  Tests: 438 passed / 0 failed / 0 xfail locally. Mutation check (price check ignored in `record`) → 6/9 new tests fail as intended (3 controls pass). Needs owner: nothing. Next: W5-spec1.
- 2026-11-26 W5-spec1 (formulation lead, Opus, main session, no subagents) on `gate-1`: spec wording only. formulation §6.2 now says
  infeasibilities are measured on the scaled LP and splits "RHS ratio / any finite bound" into RHS ratio + largest finite bound
  (absolute, scaled) — the code's reading ratified (F2); §5.2 ANN ≥ I/n check limited to PFF ≥ 1 (F6). DECISIONS 32. No code change.
  Tests: 438 passed / 0 failed locally. Needs owner: confirm DECISIONS 32 at Gate 1 review. Next: W6.
- 2026-11-26 W6 (PM, main session; markets + consulting reviewers, Opus subagents) on `gate-1`: reviews added to
  reports/gate-1-review.md — both verdict yes, no blockers. Should-fix: M1 CAPACITY_RENT attribution to at-cap baseload,
  M2 non-unique x=0 rents unflagged, C1 rents units in schema, C2 assumptions-book header. 9-item owner decision list written.
  STATUS: AWAITING_OWNER_REVIEW. Tests: 438 passed / 0 failed locally. Needs owner: Gate 1 decisions 1–9.
- 2026-11-26 P1 (data lead, main session, no subagents) on `prep`: cloned GridMod/RTS-GMLC at commit 3ece0d3 (209 files, 218 MB);
  vendored 43 files / 9 MB unmodified in `cases/raw/rts_gmlc/` (SourceData, DA hourly 2020 series, PLEXOS DA allTX/noTX reference
  solutions), `MANIFEST.csv` (sha256 of every upstream file, vendored flag), `PROVENANCE.md`; data-sources.md registry row updated.
  Tests: 438 passed / 0 failed. Found: fingerprint breaks on untracked paths with spaces; sources.csv edit breaks case manifests (row deferred to P5).
  Needs owner: RTS-GMLC licence unverified (no LICENSE file) — OK for internal test use? Next: P2.

2026-11-26 W6-spec1 (formulation lead, Opus, gate-1) — spec only, no code.
- F-0.2 amendment 3 / DECISIONS 35: CAPACITY_RENT hours attributed to INVESTMENT_MARGIN units, else highest-MC rent-set unit; full set in `rent_ids` (M1).
- `rents.rent_note` = `non-unique (bound)` for x = 0 candidates (M2); every `rents` column's unit named in data-schema §5 (C1); assumptions-book header + toy banner (C2); T2a typo 60·0.9 (M6).
- Tests not run (no code change). Next: W6-fix1 builder. Nothing needs the owner.

2026-11-26 W6-fix1 (builder, Sonnet subagent; main session Opus) on `gate-1`.
- M1: CAPACITY_RENT setters = rent-set units with interior build, else highest-MC; full set in new `rent_ids` column. M2: `rents.rent_note`. C2: assumptions-book run header + toy banner.
- Tests: 435 passed / 4 failed — fingerprint determinism tests compare assumptions.md bytes, which now carries the random run_id (spec conflict, not a code bug).
- Added W6-spec2 (formulation lead) to define canonical outputs; W6-fix1-test then updates the test. CI red until then (planned). Nothing needs the owner.

2026-11-26 W6-spec2 (formulation lead, Opus, main session, no subagents) on `gate-1`.
- F-0.2 amendment 4 / DECISIONS 36: canonical outputs = every output file except `run.json`; `assumptions.md` compared without its single `- run_id:` line.
- data-schema §5: output tables carry no `run_id` column (matches code). gate-1.md §3, data-sources.md, formulation §8.10 amended.
- Tests not run (spec only; CI still red on 4 determinism tests until W6-fix1-test, planned). Nothing needs the owner.

2026-11-26 W6-fix1-test (verifier, Sonnet subagent; main session Opus) on `gate-1`.
- New `tests/test_reporting_w6.py` (21 cases): M1 setter attribution + `rent_ids` (designed interior-build case, T3b closed form, degenerate highest-MC branch), M2 `rent_note` on x = 0 candidates, C2 assumptions header/banner, no `run_id` columns.
- `tests/test_health_fingerprint.py`: byte-identity now on canonical outputs per §8.10 / DECISIONS 36 (assumptions.md minus its `- run_id:` line, checked equal to run.json).
- Tests: 460 passed / 0 failed / 0 xfail locally; CI run 57 green on ca92d50; no spec-vs-code failures. Next: W7 merge. Nothing needs the owner.

2026-11-26 W7a (PM, main session; no subagents) on `gate-1`.
- Confirmed W6-spec1/fix1/spec2/fix1-test done; CI run 58 green on 7c7837f; 460 pass locally. gate-1 → main has 1 trivial conflict (CLAUDE.md, take gate-1's).
- Merge NOT done: scheduled-run prompt forbids runs from merging to main / marking a gate done. Split W7 → W7a (done) + W7b (owner action). STATUS: AWAITING_OWNER_REVIEW.
- Needs owner: do the merge + Gate 1 DONE + create gate-2 (reports/gate-1-merge-readiness.md), or amend the run prompt.

2026-11-26 P2 (formulation lead, main session Opus; no subagents) on `prep` (07bd44a).
- DRAFT `docs/gates/gate-2.md`: CI criteria C1–C9 (pinned env after the W4a-fix numpy break, strict xfail, health-run artifacts, 2-job determinism), data-download D1–D8 (dispatch-only, manifest hashes, provenance.json, never commit data), carried F3–F5 + P1-a/b.
- DRAFT `docs/gates/gate-3.md`: pjm5 cases P5a–P5f, KVL/PTDF/LMP-decomposition/rent-identity checks, mutations M7–M10, work order incl. §7.4a completion (F-0.3).
- Published 5-bus LMPs reproduced by an independent scipy DC-OPF; case inputs were written from memory → P3 must verify. No tests run (docs only).
- Needs owner (at boundary): approve/amend both drafts; gate-3 dispatch tolerance 0.01 vs 0.1 MW.
- 2026-11-26 P3 (data lead, Sonnet subagent) on `prep` (23d0d47): MATPOWER `data/case5.m` fetched from GitHub (HEAD b6c85b0, sha256
  ed907208…), vendored in `cases/raw/pjm5bus/` with LICENSE, MANIFEST.csv, README provenance, parsed CSVs, PowerModels copy as cross-check only.
  All gate-3.md draft inputs match; independent DC-OPF gives LMPs 16.98/26.38/30.00/39.94/10.00, cost 17,479.90. No model code; no tests run
  (raw data only). Needs owner: case-file licence ("with permission", not BSD) — internal test use OK? rec yes.

2026-11-26 09:20Z — P4 (builder role, prep lane; STATUS awaiting owner review). Branch `prep` 707cee7.
Result: draft data-download workflow (workflow_dispatch only, read-only perms, artifact upload) + 4 manifests + fetch/verify scripts + D8 doc.
Tests: no pytest change (no src/ edits); local script checks 6/6 as expected (pjm5 fetch+verify, same hashes twice, tampered file fails, broken pin fails & removes output, unknown source exit 2, disabled/missing-key skip).
Owner: workflow can only be dispatched once its file is on `main` (Gate 2 evidence); EIA/ATB URLs still to verify.

- 2026-11-26 P5 (data lead, Sonnet, branch `prep` 0386daa): RTS-GMLC → `cases/rts_gmlc/` in model input schema with provenance; conversion script reproducible.
  155 resources, 3 zones, 4 links, 8784 h as 122×72-h blocks; capacity matches gen.csv. Loader smoke ok (not solved); pytest 438 pass.
  Needs owner: `rts_gmlc` row in common sources.csv requires re-hashing T1–T4 manifests (rec yes, at Gate 4).
- 2026-11-26 P6 (verifier, Sonnet subagent; main session verified) on `prep` (5fd6057): DRAFT `tests/draft/test_pjm5bus.py` from gate-3.md draft
  only (src not read). Independent scipy DC-OPF self-checks: 21 pass, 1 strict xfail (gate-3.md surplus 14,957.28 vs 14,957.29, rounding).
  Model-facing P5a–P5f, §4 health checks, M7–M10: 29 skipped until Gate 3; 12 SPEC-GAP notes for Gate 3 W-spec.
  Tests: full suite 459 passed / 29 skipped / 1 xfailed / 0 failed. Needs owner: nothing new (fix 14,957.29 when approving gate-3.md).

## 2026-11-26 — P7 (prep, formulation lead [Opus])
- Item: Gate 5 representative-period spec draft. Result: `docs/drafts/gate5-rep-periods-spec.md` + DRAFT `docs/gates/gate-5.md` on `prep` (d5eca74).
- Choices: Ward + medoid (no seed, byte-deterministic), forced extreme blocks at weight 1, annual-total rescaling switch, Kotzur superposition SOC linking.
- Tests: none run (spec only); toy T5 expected values cross-checked with an independent scipy LP.
- Owner: 10 yes/no items at end of gate-5.md, notably a test-only full-chronology expansion run on RTS-GMLC (exception to DECISIONS 3). Next prep: P8.

## 2026-11-26 — P8 (prep, markets reviewer [Sonnet])
- Item: PJM RPM notes for Gate 14. Result: DRAFT `docs/drafts/pjm-rpm-notes.md` on `prep` (6c1e9c7), 481 lines, 23 sources, 37 "(verify)".
- Findings: 2026/27–2028/29 BRAs cleared at the collar cap everywhere; 2029/30 BRA due Dec 2026; new VRR curve from 2028/29; ELCC class ratings tabulated.
- Tests: none (notes only; no code). IMM State of the Market not yet consulted.
- Owner: new Needs-owner item — use 2024/25 + 2025/26 as M7.1 pass/fail years (capped years report-only); rec yes. Next prep: P9.

2026-11-26 10:55Z — P9 (consulting reviewer, Sonnet), branch `prep` 8c68935
- DRAFT docs/drafts/storage-study-outline.md: questions, design, revenue stack, 6–10 charts, sanity ranges, validation, 6 owner decisions.
- 258 lines, 8 sources, 25 "(verify)"; no code changed, no tests run (docs only).
- Gaps: PJM has no 2 h storage ELCC class; no public arbitrage/reserve revenue ranges found. Owner: 6 yes/no items (Needs owner).

2026-11-26 11:25Z — P10 (data lead, Sonnet), branch `prep` 458d67e
- DRAFT docs/drafts/eia-mapping.md: EIA-860/860M/923 + PUDL → data-schema mapping, PM/fuel code maps, heat-rate derivation, estimation hierarchy (heat rate, min gen, ramp, outage, start), back-test plan, provenance.
- 397 lines, 49 "(verify)" (written offline; column names from memory); no code changed, no tests run (docs only).
- 9 schema gaps found. Owner: 10 yes/no items (Needs owner). Prep list now exhausted; runs will skip until W7b.

2026-11-26T11:35Z — skipped: nothing claimable (AWAITING_OWNER_REVIEW; W7b owner-only; prep P1–P10 done)

2026-11-26 — G2-1 (builder, Sonnet), branch `gate-2`
- ci.yml: push all branches + PR into main; ubuntu-24.04, Py 3.12; exact pins in new requirements-ci.txt; version block (C3); pytest -v --disable-socket --junitxml + log artifacts 30 d (C4, C9); wall-time summary, warn >10 min (C8).
- Local fresh 3.12 venv, network disabled: 481 pass / 29 skip / 1 xfail / 0 fail. CI result on GitHub: see next run on gate-2.
- Nothing needs the owner. Next: G2-2.
- 2026-11-26 G2-2 (builder, Sonnet): CI C5–C7 — xfail_strict, scripts/check_markers.py (+ --self-test), health-run matrix job (2 PYTHONHASHSEEDs, T1–T4, artifacts), compare job (scripts/compare_runs.py, byte-identical canonical outputs; --numeric for local vs CI). Commit d734cc5.
  Tests: 481 pass / 29 skip / 1 xfail / 0 fail locally; health 7/7 pass; seed compare identical. Checker flags 1 verifier draft marker (tests/draft/test_pjm5bus.py:118, xfail without Gate ref) → new item G2-2-fix (verifier); CI test job red on C5 step until then (planned).
  Needs owner: nothing.
- 2026-11-26 G2-2-fix (verifier): tests/draft/test_pjm5bus.py congestion-surplus marker changed from strict xfail to skip citing "Gate 3" (draft 14,957.28 vs independent 14,957.29 note kept for Gate 3 approval).
  Tests: check_markers.py exit 0, --self-test exit 1; full pytest 481 pass / 30 skip / 0 xfail / 0 fail locally (network disabled). CI: see next gate-2 run.
  Needs owner: nothing. Next: G2-3 (builder, data-download workflow for pjm5).
- 2026-11-26 G2-3 (builder, Sonnet): data-download workflow gate-grade for pjm5 (D1–D8): ubuntu-24.04, step-summary provenance, skip note; verify_artifact `--against`/`--summary`; new scripts/fetch_artifact.py consumer; tests/builder/test_data_download_smoke.py (16).
  Tests: 497 pass / 30 skip / 0 fail locally (network disabled); check_markers clean. Live pjm5 fetch from workspace matched both pinned hashes. Not yet run on Actions.
  Needs owner: data-download.yml must be on `main` before any dispatch (G2-7 evidence) — copy the file to main? rec yes. Next: G2-4.
- 2026-11-26 owner (live): yes to copying data-download.yml onto main → done (main f123ad1, DECISIONS 39). G2-7 can now dispatch with --ref gate-2.

2026-11-26 G2-4 (builder, Sonnet subagent), branch gate-2
- Fixed carried findings F3 (eliminate_zeros in _triplets), F4 (free-duration storage checks s_xP and s_xE), F5 (scipy ranged-row dual no longer overwritten), P1-a (git_state NUL-separated untracked paths).
- 4 builder smoke tests added; local 501 pass / 30 skip / 0 fail; check_markers OK; T1–T4 health runs ok, outputs unchanged.
- No spec change; nothing needs the owner. Next: G2-5 verifier tests.

## 2026-11-26 — G2-5 (verifier, Sonnet)
- Added `tests/test_gate2_findings.py` (27 cases: F3, F4, F5, P1-a) and `tests/test_check_markers.py` (19 cases: C5), written from gate-2.md §2/§4 and formulation.md.
- Result: 46/46 pass on gate-2; 10 F3–F5/P1-a cases fail on the pre-fix commit (faaa9cd^), so the tests catch the original bugs.
- Full suite 547 pass / 30 skip / 0 fail (network off); check_markers exit 0. Nothing needs the owner. Next: G2-6 (Opus).

## 2026-11-26 — G2-6 (formulation lead, Opus, no subagents)
- P1-b decided: exclude `data/common/sources.csv` from case-manifest sha256 pins (DECISIONS 40); registry still hashed in the run fingerprint; ids append-only.
- Edited T1–T4 `case.yaml` (dropped the `sources` sha256), data-schema §5 + §6 rule 1, gate-2.md P1-b row + [P] note, rts_gmlc README follow-up.
- Full suite 547 pass / 30 skip / 0 fail (network off); check_markers exit 0. Nothing needs the owner. Next: G2-7 (verifier).

2026-11-26 G2-7 (verifier, main session, no subagents): wrote `reports/gate-2-evidence.md`.
CI #107 on c975ea4 green: 547 pass / 30 skip / 0 fail, ~63 s, version block = pins, 7/7 health cases identical across PYTHONHASHSEED 0/12345, objectives = local exactly.
Data-download dispatch refused ("no workflow_dispatch trigger"): data-download.yml is invalid YAML at line 79 (V2-1), on main and gate-2. Local fetch/verify pass D2–D5. Added G2-7a (builder fix + workflow-parse CI step) and G2-7b (dispatch evidence) before G2-8.
Needs owner: copy the fixed data-download.yml to main after G2-7a. Artifact downloads blocked in this workspace (C3 run.json / C7 π not inspected).

2026-11-26 G2-7a (builder, Sonnet subagent) on `gate-2` fc90b77.
- Fixed V2-1: data-download.yml line 79 `run:` → block scalar; both workflow files now parse.
- New `scripts/check_workflows.py` + ci.yml step "Parse workflow files" (fails exit 1 on line-79 regression, demonstrated). Local 547 pass / 30 skip / 0 fail.
- NOT done: copy to `main` (DECISIONS 41) — push to main blocked in this unattended run; scheduled prompt says never on main. Owner action; G2-7b waits.

2026-11-26T22:24Z skipped: nothing claimable — G2-7b blocked (fixed data-download.yml still not on `main`, owner action in Needs owner); all prep items P1–P10 done.

2026-11-26T23:25Z skipped: nothing claimable — G2-7b still blocked (main data-download.yml unchanged at f123ad1; owner action in Needs owner); prep P1–P10 done.
2026-11-26T23:30Z live session (owner): copied fixed data-download.yml to `main` (9671c02, DECISIONS 41); workflow `data-download` registered/active. G2-7b unblocked.

## 2026-11-27 — G2-7b (verifier, Sonnet)
- Dispatched data-download (pjm5): runs 45916594450 + 45916775025 on gate-2 success, identical pinned hashes (D5 pass); broken-hash run 45916853288 fails at verify, 0 artifacts (D3 pass).
- reports/gate-2-evidence.md §3–§4 + D table filled (440fe60, 3f58682). No code/tests changed.
- Needs owner: delete branch `g2-7b-broken-hash` (403 from workspace); artifact contents/step summary not readable here (D4 partial).

## 2026-11-27 — G2-8 (PM, main session + markets reviewer Sonnet)
- Wrote reports/gate-2-review.md: pass/fail table (C1–C9, D1–D8, F3–F5, P1-a/b all pass; D4/D5/D7 carried limitations), PM checks, 9-item owner decision list.
- Full-history audit: no secrets, no downloaded raw data (vendored test-system data owner-approved). CI #121 green on last completed commit; ~63 s/run.
- Markets reviewer: verdict yes; should-fix for later gates (log provenance/hashes, case5.m hash test, revised-data vintage policy, >90-day storage, hub gas source).
- STATUS: AWAITING_OWNER_REVIEW. Needs owner: answer the 9 items; delete branch g2-7b-broken-hash.
- 2026-11-27 (live, owner instruction): Gate 2 merged gate-2 → main; g2-7b-broken-hash neutralized (not deletable, 403); branch protection pending owner.
- 2026-11-27T02:24Z skipped: nothing claimable (STATUS AWAITING_OWNER_REVIEW; Gate 3 not started; prep P1–P10 all done)

2026-11-27 — G3-1 (formulation lead, Opus), branch gate-3
- formulation.md → F-0.3: full §7.4a dcpf spec (angle + PTDF forms, islands, μ sign, LMP decomposition, CONGESTION_LOOP α + DEGENERATE, 7 network check ids, M7–M10 hooks, SPEC-GAP table); data-schema links.csv reactance_pu/base_mva + rule 11; DECISIONS 48; gate-3.md surplus 14,957.29.
- Tests: 547 pass / 30 skip / 0 fail (spec only, no code change).
- Owner: Gate-2 output key column names vs schema (later bump?); uppercase pjm5 zone ids OK?

2026-11-27 — owner reply (live): yes to both G3-1 questions → DECISIONS 49 (column rename later; uppercase pjm5 zone ids OK).

2026-11-27 — G3-2 (verifier, Sonnet subagent), branch `gate-3`
- Promoted `tests/test_pjm5bus.py` from draft; 44 strict xfails (Gate 3 G3-3) for P5a–P5f, §4 checks, loader rules, M7–M10; K2 case5.m hash test passes.
- Golden Gate-2 outputs in `tests/golden/gate2/` (from main 450f29c) + byte-identity test under `transport`: passes.
- Tests: 578 pass / 44 xfail / 0 fail; check_markers exit 0.
- Open (non-blocking): multi-element `binding_links` format unspecified; K1/K3 untested ("current majors" undefined); golden made on Python 3.13 vs CI 3.12 (version components compared only if equal).

2026-11-27 — G3-3 (builder, Sonnet subagent; verifier Sonnet subagent removed markers), branch `gate-3`
- `tx.model=dcpf` angle + PTDF, `cases/pjm5bus/` with provenance, CONGESTION_LOOP α weights, new health checks; transport golden byte-identical.
- pjm5: LMPs 16.98/26.38/30.00/39.94/10.00, D–E binding at 240 MW (μ −62.32); health pass.
- Tests: 628 pass / 0 fail (44 former strict xfails now pass, markers removed by verifier); check_markers exit 0.
- Open (non-blocking, for G3-5/G3-6): F-0.2 fingerprint constant; §7.4a.6 non-toy warn/fail split missing; pjm5 sources.csv/periods.csv provenance columns thin.
