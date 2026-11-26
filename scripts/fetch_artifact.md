# Fetching a cached data artifact (DRAFT, prep item P4; gate-2.md D8)

Raw data is never committed (D6). The `data-download` workflow caches each source as a
GitHub Actions artifact named `data-<source_id>-<vintage|default>-<run_id>` (kept 90 days).

## 1. Produce the artifact (GitHub web UI or `gh`)
Actions → data-download → Run workflow → `source_id` (e.g. `pjm5`), optional `vintage`,
`pin_mode=verify`. For a source whose manifest says `sha256=unpinned`, the first run uses
`pin_mode=record`; commit the hashes from its `provenance.json` to `data/manifests/<source_id>.csv`
(and set `enabled=true`) before any case depends on it.

    gh workflow run data-download.yml -f source_id=pjm5

## 2. Download it locally
    gh run list --workflow data-download.yml --limit 5
    gh run download <run_id> --dir data/raw/pjm5        # data/raw/ is git-ignored

## 3. Verify before any loader reads it
    python scripts/verify_artifact.py data/raw/pjm5

This rechecks every file's SHA-256 and size against `provenance.json` and, for pinned rows,
against the committed manifest. A case loader may read the files only after exit code 0.

## Keyed sources (D7)
`eia923` vintage `2023-api` uses the EIA API v2 and needs repository secret `EIA_API_KEY`
(free key from EIA). `PJM_DATAMINER_KEY` is declared for later PJM Data Miner 2 pulls. Without
the secret the job prints a SKIP line and uploads nothing. Keys are substituted into the URL
at request time and appear as `***` in logs and `provenance.json`.

## Status of the manifests (2026-11-26)
| source_id | enabled | pinned | note |
|---|---|---|---|
| `pjm5` | yes | yes | MATPOWER `case5.m` + LICENSE at commit b6c85b0 (same bytes as `cases/raw/pjm5bus/`) |
| `eia860` | no | no | 2023 annual zip; URL to verify; enable at Gate 11/16 |
| `eia923` | no | no | 2023 annual zip + keyed API example |
| `atb` | no | no | ATB 2024 electricity CSV via OEDI; URL, terms and size to verify |
