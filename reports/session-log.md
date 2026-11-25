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
  Tests: 90/90 pass locally (81 verifier + 9 builder smoke); CI result on push below/in dashboard.
  Gaps noted: storage STORAGE_CH/DIS tie never triggers in T2a/b (discharge at P cap); T2c rent_en=4380 (degenerate dual at x=0, spec doesn't pin it) — only rent<cost asserted.
  Needs owner: nothing new. Next: W4b.
