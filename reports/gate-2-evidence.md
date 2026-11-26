# Gate 2 evidence — CI + data-download workflow

Item G2-7, verifier role, 2026-11-26. Criteria: `docs/gates/gate-2.md` §2–§5 (approved, DECISIONS 38).
Commit under test: `c975ea4` on `gate-2` (code identical to G2-6 `ee5f3e7`; the claim commit changes only PLAN.md).

**Bottom line.** CI (C1–C9) passes on Actions. The data-download workflow **cannot be dispatched**:
`.github/workflows/data-download.yml` is not valid YAML (line 79, col 44), so GitHub never registered its
`workflow_dispatch` trigger. The dispatch API returns *"Workflow does not have 'workflow_dispatch' trigger"*.
Evidence parts 3 and 4 (D3/D5 on Actions) are therefore **not produced**. The same fetch/verify scripts pass the
D2–D5 checks locally (below). New items G2-7a (builder fix) and G2-7b (dispatch evidence) are added before G2-8.

## 1. CI run on the final gate-2 commit (C1–C4, C8, C9)
- Run: https://github.com/rlueken1/capex-model/actions/runs/45890836224 (ci #107, `push`, head `c975ea4`) — **success**,
  4 jobs: `test`, `health-run (0)`, `health-run (12345)`, `compare`, all on `ubuntu-24.04` (image 20261122.23.1, Ubuntu 24.04.5).
- `test` job: `pytest -v --disable-socket --junitxml=reports-ci/junit.xml` → **547 passed, 30 skipped, 0 failed, 0 errors** (35.1 s).
  Artifact `test-reports` (junit.xml + pytest.log), id 15151132902, expires 2026-12-26 (30 days).
- Version block (job log, "Print versions" step):
  ```
  python 3.12.16 | numpy 2.5.3 | scipy 1.18.1 | pandas 3.0.5 | highspy 1.16.0 | HiGHS 1.16.0 (git f3f113d)
  OS Linux-7.0.0-1020-azure-x86_64-with-glibc2.39
  ```
  Equals `requirements-ci.txt` pins (pip log: "Successfully installed … highspy-1.16.0 … numpy-2.5.3 … pandas-3.0.5 … scipy-1.18.1").
- GITHUB_TOKEN permissions: `Contents: read`, `Metadata: read`; no repository secrets referenced by `ci.yml`; token masked (`***`).
- Wall time: run created 20:24:42Z, last job done 20:25:45Z → **≈ 63 s** (budget 10 min, C8).
- Local cross-check (this workspace, Python 3.13 with the same pins, network off): 547 passed / 30 skipped / 0 failed.

| # | Result | Evidence |
|---|---|---|
| C1 | pass | ci #103–#107 each one `push` run per commit on `gate-2`; `pull_request` into `main` declared in `ci.yml` |
| C2 | pass | `runs-on: ubuntu-24.04`, Python 3.12.16, install from exact-pinned `requirements-ci.txt` |
| C3 | pass (partial proof) | version block above. Fingerprint versions come from the same `package_versions()` call; I could not open `run.json` in the artifact (artifact download blocked by this workspace's proxy), so equality with the fingerprint is by construction, not inspected |
| C4 | pass | 547/30/0/0; junit + log artifact, 30-day retention |
| C5 | pass | see §5 |
| C6 | pass | see §2 |
| C7 | pass | see §2 |
| C8 | pass | ≈ 63 s, reported in step summary ("Report wall time") |
| C9 | pass | `--disable-socket` (pytest-socket 0.8.1 plugin loaded); no secrets in `ci.yml` |

## 2. Health artifacts (C6) and two-seed comparison (C7)
- `health-run (0)` and `health-run (12345)`: `scripts/ci_health_run.py` runs T1, T2a, T2b, T2c, T3a, T3b, T4 through
  `python -m capex run`; every case `Overall: pass`, `price_setter.unexplained = 0`; `[T1] ok … [T4] ok`.
- Artifacts: `health-seed-0` (id 15151247521, 161 files, 77,311 B) and `health-seed-12345` (id 15151611207, 77,319 B),
  30-day retention.
- `compare` job (`scripts/compare_runs.py`): `[T1] identical` … `[T4] identical` for all 7 cases — fingerprints and
  canonical outputs byte-identical across `PYTHONHASHSEED` 0 vs 12345.
- Local vs CI (C7 second half): objective values from the CI health log vs a local `ci_health_run.py` run:

| case | CI primal objective ($) | local ($) | rel. diff |
|---|---|---|---|
| T1 | 40,824,000.000000 | 40,824,000.000000 | 0 |
| T2a | 26,125,348.148148 | 26,125,348.148148 | 0 |
| T2b | 26,245,348.148148 | 26,245,348.148148 | 0 |
| T2c | 26,280,000.000000 | 26,280,000.000000 | 0 |
| T3a | 23,530,333.333333 | 23,530,333.333333 | 0 |
| T3b | 23,340,333.333333 | 23,340,333.333333 | 0 |
| T4 | 39,420,000.000000 | 39,420,000.000000 | 0 |

  Agreement is shown to the printed 6 decimals (≤ 4e-14 relative), well inside 1e-9. **π (zone prices) local vs CI was
  not compared**: it needs the CI `prices` tables from the artifact, which this workspace cannot download. Fingerprints
  differ local vs CI (OS / Python fields), as gate-2.md C7 expects.

## 3. Data-download dispatch and repeat (D5) — NOT PRODUCED
- `actions_run_trigger run_workflow data-download.yml ref=gate-2 source_id=pjm5` →
  **error: "Workflow does not have 'workflow_dispatch' trigger"**.
- Cause (verifier finding **V2-1**, blocking): line 79 of `data-download.yml`,
  `run: echo "data-download $SOURCE_ID: skipped (…)" >> "$GITHUB_STEP_SUMMARY"`, is a plain YAML scalar containing
  `": "` → `yaml.safe_load` raises *"mapping values are not allowed here, line 79, column 44"*. GitHub lists the
  workflow by its path (`.github/workflows/data-download.yml`) instead of its `name: data-download`, the usual sign
  of an unparseable file, and records a failed run on every push (runs #1–#10, all `failure`, 0 jobs). The file on
  `main` (f123ad1, DECISIONS 39) is byte-identical to `gate-2`'s, so both are broken. `ci.yml` parses.
- Why nothing caught it: G2-3's 16 builder smoke tests exercise the scripts, not the YAML; no CI step parses workflow files.
- Local substitute (same scripts the workflow calls, this workspace, live fetch from raw.githubusercontent.com):
  two fetches of `pjm5` → `all_verified=True` both times; `provenance.json` has `source_id`, `vintage`
  `matpower-b6c85b0`, URL, `retrieved_at`, per-file SHA-256, `workflow_run_id`/`git_commit` (= `local` off Actions);
  per-file hashes equal across the two fetches (case5.m `ed907208…fe279`, LICENSE_MATPOWER `5d14c09b…1750`);
  `verify_artifact.py` exit 0. This shows D2/D4/D5 logic works; it is **not** the Actions evidence §5(3) asks for.

## 4. Broken-hash dispatch (D3) — NOT PRODUCED on Actions
- Not attempted on a throwaway branch: the dispatch trigger is unregistered (§3), so it would fail for the wrong reason.
- Local substitute: manifest copy with a corrupted `case5.m` hash → `HASH MISMATCH case5.m …`,
  `ERROR: hash/size check failed; output removed, nothing will be uploaded`, **exit 1**, output dir absent.
  Unknown `source_id` (`nosuch`) → `ERROR: unknown source_id`, **exit 2** (D2).

Static D-criteria (read from the file; valid once V2-1 is fixed):

| # | Result | Evidence |
|---|---|---|
| D1 | **fail (V2-1)** | intent correct (`workflow_dispatch` only, inputs `source_id`, `vintage`, `pin_mode`; no `schedule:`), but the file does not parse, so the trigger does not exist on GitHub |
| D2 | pass (local) | manifest-driven; unknown id exits 2 |
| D3 | pass (local) / not shown on Actions | mismatch exits 1, output removed, later steps gated on `fetched == 'true'` |
| D4 | pass (local) | `provenance.json` fields above |
| D5 | pass (local) / not shown on Actions | equal hashes on repeat; `upload-artifact@v4`, `retention-days: 90` |
| D6 | pass | `permissions: contents: read`; no `git push` step; `persist-credentials: false` |
| D7 | pass (static) | `EIA_API_KEY` / `PJM_DATAMINER_KEY` passed via env from `secrets.*`, never echoed; skip note step |
| D8 | pass (local, G2-3) | `scripts/fetch_artifact.py` / `fetch_artifact.md`; `verify_artifact.py --against` |

## 5. C5 proof (a marker without a reason fails)
- CI step "Check xfail/skip markers (C5)" on run #107: `check_markers.py --self-test` rejects the bad sample
  (`<bad-sample>:4: pytest.mark.xfail lacks a reason…`, `:7` skip, `:11` `pytest.skip`, `<draft-xfail>:2` draft xfail)
  and exits 1 (step asserts exit 1); then `check_markers.py` on the repo: "all xfail/skip markers carry a DECISIONS/Gate reference".
- Local: `check_markers.py` exit 0, `--self-test` exit 1. `xfail_strict = true` in pytest config.
  Verifier tests `tests/test_check_markers.py` (19, G2-5) pass on CI.

## 6. Carried findings
| ID | Outcome | Evidence |
|---|---|---|
| F3 | closed | G2-4 `eliminate_zeros()`; G2-5 test nnz equal with/without zero entry |
| F4 | closed | G2-4 both `s_xP`, `s_xE` checked; G2-5 tests catch xE-only and xP-only corruption |
| F5 | closed | G2-4 ranged row keeps both duals; G2-5 tests −2 upper / +1 lower and = HighsSolver |
| P1-a | closed | G2-4 `ls-files -z`; G2-5 test with a spaced untracked path |
| P1-b | closed (decision) | G2-6: exclude `data/common/sources.csv` from manifest pins (DECISIONS 40) |
G2-5 ran its F3–F5/P1-a tests against pre-fix code (`faaa9cd^`): 10 failed there, so they catch the original bugs.
All in `tests/test_gate2_findings.py` (27) — pass on CI run #107.

## 7. Spec / DECISIONS changes in this gate
- DECISIONS 38 (Gate 2 criteria approved), 39 (data-download.yml copied to `main`, dispatch-only), 40 (P1-b exclusion).
- `docs/data-schema.md` §5/§6.1 amended (G2-6); T1–T4 `case.yaml` manifests list `sources` without `sha256`.
- No `docs/formulation.md` change; F5 fixes the adapter to the existing dual-sign spec.

## 8. Known limitations
1. **V2-1 (blocking for D1/D3/D5):** `data-download.yml` invalid YAML; fix = make line 79 a block scalar (`run: |`)
   or quote it; add a CI step that parses every `.github/workflows/*.yml` so this can't recur. The fixed file must
   reach `main` again before any dispatch (GitHub reads the trigger from the default branch).
2. Every push to any branch records a failed `data-download` run until V2-1 is fixed (red ✗ noise next to green CI).
3. C3 fingerprint-version equality and C7 local-vs-CI π not inspected directly: this workspace cannot download
   Actions artifacts (blob-storage host blocked by the proxy). Objectives agree exactly.
4. Local checks ran on Python 3.13 (same package pins), not 3.12; CI is the reference environment.
5. Actions warns that `actions/checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `download-artifact@v4` target
   Node 20 (deprecated, forced to Node 24). Works today; bump to current majors in a later gate.
6. No secrets/raw-data audit of git history here (PM item in gate-2.md §6).
