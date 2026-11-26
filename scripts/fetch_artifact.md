# Fetching a cached data artifact (Gate 2, G2-3; gate-2.md D8)

Raw data is never committed (D6). The `data-download` workflow caches each source as a
GitHub Actions artifact named `data-<source_id>-<vintage|default>-<run_id>` (kept 90 days).

## 1. Produce the artifact (GitHub web UI or `gh`)
Actions → data-download → Run workflow → `source_id` (e.g. `pjm5`), optional `vintage`,
`pin_mode=verify`. For a source whose manifest says `sha256=unpinned`, the first run uses
`pin_mode=record`; commit the hashes from its `provenance.json` to `data/manifests/<source_id>.csv`
(and set `enabled=true`) before any case depends on it.

    gh workflow run data-download.yml --ref gate-2 -f source_id=pjm5

GitHub only dispatches a workflow whose file exists on the default branch. `main` currently lacks
`data-download.yml`, so the command above (and the web UI Run button) works only after the file is on
`main`. The job's summary page shows `provenance.json` and a file/hash table.

## 2. Download and verify in one step
    python scripts/fetch_artifact.py pjm5 --against cases/raw/pjm5bus

Needs the `gh` CLI, authenticated. It takes the latest successful `data-download` run (or `--run-id N`),
the artifact `data-pjm5-*` (or `--artifact NAME`), downloads it with `gh run download <id> -n <artifact>`
directly into `data/raw/pjm5/` (git-ignored), then runs the verification below. Exit 0 means safe to read.

## 3. Verify by hand (or re-verify later)
    python scripts/verify_artifact.py data/raw/pjm5 --against cases/raw/pjm5bus

Rechecks every file's SHA-256 and size against `provenance.json`, flags extra files, and for pinned rows
checks the committed manifest. `--against <dir>` additionally requires each file to hash equal to the
same-named vendored file (for `pjm5`, `cases/raw/pjm5bus`), proving artifact == vendored copy. A case
loader may read the files only after exit code 0.

## Keyed sources (D7)
`eia923` vintage `2023-api` uses the EIA API v2 and needs repository secret `EIA_API_KEY`
(free key from EIA). `PJM_DATAMINER_KEY` is declared for later PJM Data Miner 2 pulls. Without
the secret the job prints a SKIP line and uploads nothing. Keys are substituted into the URL
at request time and appear as `***` in logs and `provenance.json`.

## Status of the manifests (2026-11-26)
| source_id | enabled | pinned | note |
|---|---|---|---|
| `pjm5` | yes | yes (G2-3, end to end) | MATPOWER `case5.m` + LICENSE at commit b6c85b0 (same bytes as `cases/raw/pjm5bus/`) |
| `eia860` | no (declared) | no | 2023 annual zip; URL to verify; enable at Gate 11/16 |
| `eia923` | no (declared) | no | 2023 annual zip + keyed API example |
| `atb` | no (declared) | no | ATB 2024 electricity CSV via OEDI; URL, terms and size to verify |
