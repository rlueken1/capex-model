# Status dashboard — update at the end of every session

Owner-facing page: https://claude.ai/artifact/PM7HNA9PDasBx9DXSEK46P
(artifact slug `b4f7cc24-94bc-44ab-a210-7059bee5c564`, a Data-type dashboard).

Update it as the **last step of every session** (work session or scrum), after pushing to
git. Use the artifact data tool: load it with ToolSearch `"select:ArtifactData"` (or the
`db_get` / `db_write` / `db_list` tools if those are what the session has), with the url
above. One batch write per session. Every write to a document that exists needs its
current version (`if_version` / `ifVersion`): read the documents you will change first.
Never write `files/*`, `datasets/*` or `dash/*` — only the `data/...` documents below.
Keep text short (one line per field). If the write fails, note it in
`reports/session-log.md` and carry on; never retry more than once.

## Documents (all text in plain English for the owner)

`data/summary` — one document, overwrite the fields:
- `status`: "In progress" | "Awaiting your review" | "Blocked" | "Paused"
- `headline`: one sentence on where things stand now
- `current_gate`: e.g. "0"; `current_gate_name`; `branch`
- `next_run`: e.g. "Sun Nov 22, 12:41pm"; `next_item`: e.g. "W3: toy model"
- `last_run_at`: ISO UTC time this session finished; `updated_at`: same

`data/board/gates/gNN` (g00…g20) — update only gates whose status changed:
- `status`: "planned" | "active" | "review" (awaiting owner) | "done" (owner signed off only)
- `evidence`: one line (files, CI result, scoreboard numbers)
- keep `num`, `name`, `phase`

`data/board/items/<id>` — the work items in PLAN.md "Work items":
- fields `id`, `order`, `title`, `role`, `model`, `status` ("pending" | "in_progress" | "done" | "blocked")
- when the PM rewrites the plan, add new items and delete finished items older than the
  previous gate

`data/board/decisions/dNN` — every question raised under PLAN.md "Needs owner":
- `id`, `asked` (date), `status` ("open" | "answered"), `question`, `recommendation`,
  `answer` (empty while open). Mark answered when DECISIONS.md records the answer.

`data/board/sessions/s<YYYY-MM-DDTHHMM>` — create one per session (UTC start time). This
is the owner's **full run report**, so keep notes as you work (who was spawned, what was
debated, what was decided) and write them here at the end. Multi-line fields are plain
text with one point per line (newline-separated), each line one short sentence:
- `id`, `at` (ISO UTC start), `duration_min` (number)
- `task` ("Work session" | "PM scrum"), `item` (e.g. "W2 Data schema & benchmarks")
- `result` ("ok" | "partial" | "failed" | "skipped"), `summary` (≤ 30 words)
- `agents`: each role involved, its model, and what it did — the main session's role first,
  then every subagent and reviewer (e.g. "Verifier (Sonnet) — wrote T1–T4 tests")
- `discussion`: the questions and trade-offs the agents weighed, incl. disagreements
- `decisions`: what was decided and why (one line each); mark anything that needs owner
  approval with "(needs you)"
- `work_done`: concrete outputs (files, functions, tests, data pulled)
- `progress`: progress against the item and the current gate's exit criteria, incl. what
  was NOT finished; `gate_progress_pct` (0–100, your honest estimate for the current gate)
- `next_steps`: what the next session(s) should do
- `challenges`: problems hit, failed attempts, tool/network/usage-limit issues, risks
- `needs_owner`: questions raised for Roger (also add them as `decisions/dNN` rows)
- `tests`: test and CI results with counts (e.g. "14/14 pass; CI green")
- `files_changed`: main files added or changed
A skipped run still writes a row (result "skipped", summary saying why). The PM scrum's
`discussion` and `decisions` hold the scrum's agenda, which reviewers it convened and why,
the priorities it set, and how it re-planned the work items.

## Upcoming runs — `data/board/schedule/*` (every session and scrum)

Keeps the owner's "Upcoming scheduled runs" table current. Two kinds of rows:

- `kind: "run"` — one per upcoming run in the next 7 days, id `r<YYYYMMDDTHHMM>` (UTC):
  `id`, `kind`, `at` (ISO UTC), `task` ("Work session" | "PM scrum" | "Schedule reset"),
  `role` (expected role and model, or "Per plan"), `plan` (one line: the PLAN.md item it
  should pick up, or "Expected to skip: waiting for your sign-off"), `notes` (optional).
- `kind: "cadence"` — the standing weekly schedule, ids `c1`, `c2`, …: `id`, `kind`,
  `task`, `when` (e.g. "Sat & Sun 12:41pm & 8:41pm" ET), `trigger` (scheduled task name), `notes`.

At the end of each run: delete `run` rows whose `at` is in the past, and re-map the plan
of the remaining rows to the PLAN.md items in order (one item per work session; after the
item that pauses for owner review, later work sessions are "Expected to skip"). Get run
times from `list_triggers` (Claude_Code_Remote) if that tool is available — names start
with "capex"; convert cron (CRON_TZ=America/New_York) to the next 7 days — and refresh the
`cadence` rows if the cron changed. If it isn't available, keep the existing times. The PM
scrum always rebuilds the full 7-day list.
