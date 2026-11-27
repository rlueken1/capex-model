# Gate 2 evidence — CI + data-download workflow

Item G2-7 (verifier, 2026-11-26) and G2-7b (verifier, 2026-11-27 UTC). Criteria: `docs/gates/gate-2.md` §2–§5 (approved, DECISIONS 38).
Commit under test for CI (§1–§2, §5): `c975ea4` on `gate-2` (code identical to G2-6 `ee5f3e7`). Commit under test for §3: `cafcff0` on `gate-2` (claim G2-7b; no code change since G2-7a).

**Bottom line.** CI (C1–C9) passes on Actions. G2-7 found that `data-download.yml` was invalid YAML (V2-1) so it could not be
dispatched; it was fixed in G2-7a (DECISIONS 41) and G2-7b now has the Actions evidence: two `gate-2` dispatches of `pjm5`
both succeeded and uploaded an artifact (D5), and a dispatch from a throwaway branch with a corrupted pjm5 hash failed at
"Fetch and verify" with all later steps skipped and no artifact (D3). Limits: the artifact contents and the step summary could not
be read from this workspace (blob host blocked), so `provenance.json` fields (D4) are not observed on Actions, and the D5 "equal
hashes" is shown through the pinned-hash verification in both job logs, not by reading hashes out of the artifacts.

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

## 3. Data-download dispatch and repeat (D5)
Workflow `data-download` (path `.github/workflows/data-download.yml`, workflow id 431840597), `workflow_dispatch`, `ref=gate-2`,
input `source_id=pjm5` (`vintage` blank, `pin_mode` default `verify`). Dispatch accepted both times (HTTP 204).

| | Run 1 | Run 2 |
|---|---|---|
| Run | [45916594450](https://github.com/rlueken1/capex-model/actions/runs/45916594450) (#14) | [45916775025](https://github.com/rlueken1/capex-model/actions/runs/45916775025) (#15) |
| Head | `cafcff0` (gate-2) | `cafcff0` (gate-2) |
| Conclusion | **success** (job `download`, ubuntu-24.04, 6 s) | **success** (job `download`, 17 s) |
| Fetch and verify | success: `OK: 2 file(s) in download/pjm5; all_verified=True` | same line |
| Re-verify before upload | success: `OK: download/pjm5 matches provenance.json and manifest` | same line |
| Provenance summary | success (summary page not readable here) | success |
| Note skipped source | skipped | skipped |
| Upload artifact | success, 3 files (case5.m, LICENSE_MATPOWER, provenance.json) | success, 3 files |
| Artifact | `data-pjm5-default-45916594450`, id 15162192600, 2,706 B, retention 90 d (expires 2027-02-25) | `data-pjm5-default-45916775025`, id 15161949978, 2,704 B, retention 90 d (expires 2027-02-25) |
| Artifact zip sha256 | `2ed26ce4c671a3cdfab6f13b90525ff7ae8bb7f5f155b121ae8b48e748955346` | `9e4925bbec35db6b54356cf0fa503068592f46dd19ff4ffbddd40bec12cb226b` |

Both fetches GET the pinned URLs `raw.githubusercontent.com/MATPOWER/matpower/b6c85b0…/data/case5.m` and `/LICENSE` and passed
verification against `data/manifests/pjm5.csv`, whose pins are case5.m `ed9072089d080debde2aa029ed8a95491c311b08ff4f45ad7bf06882d86fe279`
(1,921 B) and LICENSE_MATPOWER `5d14c09b3e4f2adf62c0373e6320163697aa4603186f8925c07c6b84201e1750` (2,074 B). So both runs produced
files with identical per-file SHA-256 (equal to the pins, which `fetch_source.py` enforces and `verify_artifact.py` re-checks).
**Not observed:** the per-file hashes as printed in the step summary or in `provenance.json` (the job logs do not contain the
summary, and the artifact download URL is blocked by this workspace's proxy: `productionresultssa1.blob.core.windows.net` HTTP 403).
The two artifact zip digests differ; that is expected because `provenance.json` carries `retrieved_at` and the run id (inference,
the archive size differs by 2 B, not inspected). D5 is judged on per-file hashes, not zip digests.
Earlier local substitute (G2-7, same scripts): two fetches equal per-file hashes; superseded by the above.

## 4. Broken-hash dispatch (D3)
- Throwaway branch `g2-7b-broken-hash` from `gate-2` (commit `6894418`), one change: `data/manifests/pjm5.csv` case5.m sha256
  set to 64 zeros. (Workflow file identical to gate-2; dispatch trigger comes from `main`'s registration.)
- Run [45916853288](https://github.com/rlueken1/capex-model/actions/runs/45916853288) (#16), `ref=g2-7b-broken-hash`, `source_id=pjm5`: **failure**, job `download` 11 s.
- Steps: checkout success, setup-python success, **Fetch and verify: failure**, then Re-verify, Provenance summary, Note skipped
  source, Upload artifact, Post setup-python all **skipped**.
- Job log (failed step):
  ```
  HASH MISMATCH case5.m: got ed9072089d080debde2aa029ed8a95491c311b08ff4f45ad7bf06882d86fe279, manifest 0000000000000000000000000000000000000000000000000000000000000000
  ERROR: hash/size check failed; output removed, nothing will be uploaded
  ##[error]Process completed with exit code 1.
  ```
- Artifacts for run 45916853288: `total_count: 0` (list API) — **nothing uploaded**.
- Local substitute from G2-7 (unknown `source_id` `nosuch` → `ERROR: unknown source_id`, exit 2; D2). Not re-run on Actions.
- **Cleanup status:** deleting the throwaway branch was attempted (`git push origin --delete g2-7b-broken-hash`, twice) and the
  push was refused with HTTP 403 from this workspace. The branch **still exists** on origin at `6894418`; the owner must delete it
  (the branch contains only the corrupted manifest and must never be merged).

| # | Result | Evidence |
|---|---|---|
| D1 | pass | file parses and is registered: dispatched twice on `gate-2` and once on a throwaway branch (HTTP 204); `on:` has only `workflow_dispatch`, no `schedule:` |
| D2 | pass | manifest-driven (log shows pinned URLs and file list from `pjm5.csv`); unknown id exits 2 (local, G2-7); not re-run on Actions |
| D3 | **pass** | run 45916853288: HASH MISMATCH, step failed, exit 1, all later steps skipped, 0 artifacts |
| D4 | pass (partial) | Actions: `verify_artifact.py` logged "matches provenance.json and manifest" and upload shows 3 files (2 data + `provenance.json`); field contents (`retrieved_at`, run id, commit) verified locally in G2-7 only, **not read from the Actions artifact** |
| D5 | **pass** (hashes via pins) | runs 45916594450 and 45916775025 both success, artifacts uploaded with 90-day retention, both verified to the same pinned per-file SHA-256; artifact/summary hashes not read directly (see §3) |
| D6 | pass | `permissions: contents: read`, no `git push` step, `persist-credentials: false`; run logs show token scope unchanged |
| D7 | pass (static + log) | `EIA_API_KEY` / `PJM_DATAMINER_KEY` appear empty in the run env; `pjm5` needs no key; keyed-source skip path not exercised on Actions |
| D8 | pass (local, G2-3) | `scripts/fetch_artifact.py` / `fetch_artifact.md`; `verify_artifact.py --against`; not exercised against these Actions artifacts (download blocked) |

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
1. V2-1 (data-download.yml invalid YAML) fixed in G2-7a (DECISIONS 41); D1/D3/D5 now shown on Actions (§3, §4). A CI step that
   parses every `.github/workflows/*.yml` was proposed so this cannot recur; whether it landed is not checked here.
2. Throwaway branch `g2-7b-broken-hash` could not be deleted from this workspace (HTTP 403 on branch deletion); owner action.
3. C3 fingerprint-version equality and C7 local-vs-CI π not inspected directly: this workspace cannot download
   Actions artifacts (blob-storage host blocked by the proxy). Objectives agree exactly.
4. Local checks ran on Python 3.13 (same package pins), not 3.12; CI is the reference environment.
5. Actions warns that `actions/checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `download-artifact@v4` target
   Node 20 (deprecated, forced to Node 24). Works today; bump to current majors in a later gate.
6. No secrets/raw-data audit of git history here (PM item in gate-2.md §6).
