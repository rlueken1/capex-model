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

(Prep items also run when the next gate item is already claimed; see "Concurrent runs".)
If `PLAN.md` says `STATUS: AWAITING_OWNER_REVIEW`, do **no** gate work. Instead do the next
unchecked item under "Prep while awaiting owner review" in PLAN.md, on branch `prep`
(create it from the current gate branch if missing; fetch and rebase before pushing). If
none is left, append one line to `reports/session-log.md` ("skipped: awaiting review") and stop.

## Concurrent runs (burst schedules) — claim before you work
Runs may start every 20 minutes and overlap. Before doing any work:
1. Pick the item: the next unchecked gate item in PLAN.md. If it is already claimed (by a
   live, non-stale claim), or STATUS is AWAITING_OWNER_REVIEW, take instead the next
   unchecked, unclaimed prep item whose "Needs Px done" prerequisite is ticked, whatever
   STATUS says (owner, 2026-11-26). Prep stays on branch `prep` and never touches `src/capex/`. Gate items stay strictly in order: never start a
   later gate item while an earlier one is unchecked.
2. Claim it on the gate branch: change `- [ ]` to `- [~]` and append `(claimed <ISO UTC>)`
   on that item's line, commit "claim <item>", push. If the push is rejected, fetch,
   rebase, re-read PLAN.md and pick again.
3. A claim older than 60 minutes with no completing commit is stale and may be taken over.
4. When done, replace `[~] … (claimed …)` with `[x]`. Always fetch + rebase before every push.
5. If nothing is claimable, log "skipped: nothing claimable" and stop (cheap exit).
Dashboard writes: on a version conflict, re-read and retry once.

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
- **Buy nothing; simplest model first** (owner, DECISIONS 26): no paid data or services. Add a feature only in
  its own gate, and only after the simpler model passes its gate.
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
