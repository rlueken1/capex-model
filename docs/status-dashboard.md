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

`data/board/sessions/s<YYYY-MM-DDTHHMM>` — create one per session (UTC start time):
- `id`, `at` (ISO UTC), `task` ("Work session" | "PM scrum"), `item`, `result`
  ("ok" | "partial" | "failed" | "skipped"), `tests` (CI / test result), `summary` (≤ 25 words)
