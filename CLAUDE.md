# capex-model — operating rules for every session

Owner: Roger (rlueken1). One-person energy consulting firm. This repo is a capacity
expansion model with **its own formulation**, in Python, built gate by gate by a small
team of role agents. The repo is the only memory between sessions.

## Start of every session (in this order, read nothing else first)
0. Find the newest gate branch (`git ls-remote --heads origin 'gate-*'`). If one exists,
   fetch it (`git fetch --depth=1 origin gate-N && git checkout gate-N`) and read the
   files below from there — the live PLAN.md lives on the newest gate branch, not on `main`.
   New gate branches (e.g. `gate-1`) are created from the previous gate branch.
1. `PLAN.md` — current gate, status, and the next work item(s).
2. `DECISIONS.md` — settled decisions. Do not reopen them without a new reason.
3. The latest file in `reports/` (if any).

If `PLAN.md` says `STATUS: AWAITING_OWNER_REVIEW`, do **no** build work: append one line
to `reports/session-log.md` ("skipped: awaiting review") and stop.

## Hard rules
- **One deliverable per session.** Pick the next unchecked item in PLAN.md, finish it,
  commit, stop. Do not start a second item.
- **Gate boundaries need the owner.** Never mark a gate DONE, never merge a gate branch
  into `main`, never start work from a later gate. At a gate boundary set
  `STATUS: AWAITING_OWNER_REVIEW` and write the review summary.
- **Builder ≠ verifier.** Tests that judge a feature are written by the verifier role
  from the spec, not by the builder of that feature.
- **Spec first.** Code implements `docs/formulation.md`. If code needs to differ, change
  the spec in the same commit and log it in DECISIONS.md.
- **Work on branch `gate-N`** (e.g. `gate-0`, `gate-1`). `main` holds only owner-approved work.
- **Token economy.** Default to Sonnet for subagents (`model: "sonnet"`); use Opus only for
  the formulation lead's spec work and gate reviews; Haiku for mechanical data cleanup.
  Spawn at most 2 subagents per session. Never re-read files you already have.
- **No 8760 capacity expansion.** Time structure is weighted representative 3-day periods
  (see DECISIONS.md). A one-off full-year *fixed-fleet dispatch* check is allowed.
- **Solver:** HiGHS via `highspy`; keep the model solver-agnostic.
- **Network:** this cloud workspace usually cannot reach data websites (EIA, PJM, NREL).
  Downloads run in GitHub Actions workflows (`.github/workflows/`), which cache data as
  artifacts. If that isn't possible, record it in PLAN.md under "Needs owner" and move on.
- **Gate rigor:** follow `docs/gates/README.md`: evidence file, health checks including the
  marginal price-setter report, scoreboard no-regression, complexity value review
  (ablation switch per feature, `reports/complexity-ledger.md`), and a review ending in a
  yes/no decision list for the owner.

- **Data provenance:** every input value carries source_id, vintage, method
  (observed/derived/estimated/assumed), basis and confidence, per `docs/data-sources.md`.
  Missing unit characteristics are estimated using that file's hierarchy (observed →
  plant-level → statistical estimate from public data → cited literature default), never
  left blank or silently defaulted. Every run writes an assumptions book.
- **Scope:** PJM only for now. Other RTOs come later, one at a time.

## End of every session
1. Commit with a clear message on the gate branch and push:
   `git -c push.negotiate=true push -u origin gate-N`
2. Tick the item in PLAN.md, update "Next".
3. Append 3–5 lines to `reports/session-log.md`: date, item, result, tests passed/failed,
   anything needing the owner.
4. Update the owner's status dashboard per `docs/status-dashboard.md` (summary, gates,
   items, decisions, one session row).
5. Send the owner a ≤5-line summary (SendUserMessage / PushNotification if available).

## Layout
- `docs/formulation.md` — math spec (sets, params, vars, constraints, objective)
- `docs/data-schema.md` — input/output tables
- `docs/benchmarks.md` — backcast metrics and scoreboard definition
- `docs/data-sources.md` — source registry, provenance rule, estimation hierarchy
- `src/capex/` — model code; `tests/` — verifier tests; `cases/` — test cases
- `.claude/agents/` — role definitions
- `reports/` — session log, scrum notes, gate review summaries
- `docs/status-dashboard.md` — how to update the owner's live status page
