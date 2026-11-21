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
