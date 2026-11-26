# Gate 2 — CI + data-download workflow: exit criteria

Status: **APPROVED by owner 2026-11-26 (DECISIONS 38).** Drafted in prep item P2.
Criteria are frozen once approved (docs/gates/README.md). Branch `gate-2`, created from `gate-1` after the owner merges Gate 1.
Spec: docs/formulation.md F-0.2 (amendments 1–4). No LP change in this gate (DECISIONS 26: simplest model first).

## 1. Scope
In: (a) the existing `ci.yml` made a gate-grade test runner (pinned environment, artifacts, strict xfail rule);
(b) a `workflow_dispatch`-only data-download skeleton that fetches one small, free, pinned source, checks its hash
and writes provenance, caching to an Actions artifact — never committing raw data (CLAUDE.md "Network");
(c) the later-gate code findings carried from Gate 1 that CI can expose now (§4).
Out: any model feature, PJM data, scheduled downloads, paid sources (DECISIONS 26–28), EIA/ATB parsing (Gate 16),
branch protection settings (owner action, §6 item 6).

Note: CI already exists since W4a (runs 18–58, Gate 1 evidence came from CI). Gate 2 therefore tightens and documents
it rather than creating it; the README "CI on every push" rule becomes binding from this gate on.

## 2. CI criteria (`.github/workflows/ci.yml`)
| # | Criterion | Pass rule |
|---|---|---|
| C1 | Triggers | `push` on every branch and `pull_request` into `main`; one run per push visible in the Actions list |
| C2 | Pinned environment | Python 3.12, `ubuntu-24.04` (not `-latest`); dependencies installed from a committed lock/constraints file (`requirements-ci.txt` with exact versions incl. numpy, scipy, highspy, pandas, pytest). Reason: W4a-fix (numpy 2.5.5 on runner vs 2.5.3 locally broke 9 tests). The same file is the documented local install |
| C3 | Version record | job log prints python, numpy, scipy, highspy, HiGHS and OS versions; they equal the versions in the run fingerprint (§8.10) of the CI health run (C6) |
| C4 | Full suite | `pytest -v --junitxml=…` over all of `tests/` (incl. `tests/builder/`); job fails on any fail or error; junit XML and log uploaded as artifacts (retention ≥ 30 days) |
| C5 | Strict xfail | `xfail_strict = true` in pytest config; a test script fails CI if any `xfail`/`skip` marker lacks a `reason` containing `DECISIONS <n>` or `Gate <n>` (drafts under `tests/draft/` must be skip with `Gate <n>`) |
| C6 | Health run | a second job runs cases T1–T4 through the CLI/run entry point and uploads each case's outputs dir (audit tables, `run.json`, `assumptions.md`) as an artifact; job fails if any health check is `fail` or UNEXPLAINED > 0 |
| C7 | Reproducibility on CI | C6 run twice in the same workflow (two jobs, different `PYTHONHASHSEED`): identical fingerprints and byte-identical canonical outputs (formulation §8.10 amendment 4, DECISIONS 36). Local vs CI: objective and π agree at rel 1e-9 (fingerprints may differ via OS/package fields; that is expected, not a failure) |
| C8 | Runtime | total CI wall time reported per run; budget ≤ 10 min [P] (warn only) |
| C9 | No secrets in logs; no network in tests | tests pass with network disabled for the pytest step (e.g. `--disable-socket` via `pytest-socket` or equivalent); CI uses no secrets |

## 3. Data-download workflow skeleton (`.github/workflows/data-download.yml`; drafted in prep item P4)
| # | Criterion | Pass rule |
|---|---|---|
| D1 | Trigger | `workflow_dispatch` only (inputs: `source_id`, optional `vintage`); no `schedule:` key |
| D2 | Registry-driven | the source URL, expected file list and SHA-256 come from a committed manifest (`data/manifests/<source_id>.csv`), keyed by `source_id` in docs/data-sources.md; an unknown `source_id` fails |
| D3 | First source | one free, small, pinned source end to end: `pjm5` (MATPOWER `data/case5.m` at a pinned commit) or the RTS-GMLC subset at commit 3ece0d3 (P1). Hash mismatch ⇒ job fails, nothing uploaded |
| D4 | Provenance record | job writes `provenance.json` next to the files: `source_id`, `vintage`, URL, retrieved_at (UTC), SHA-256 per file, workflow run id, git commit; uploaded with the data |
| D5 | Cache as artifact | output uploaded with `actions/upload-artifact` (retention stated); a second dispatch with the same inputs reproduces the same hashes |
| D6 | Never commit raw data | the workflow has `contents: read` permission only; no `git push` step |
| D7 | Secrets pattern | keyed sources (EIA API, PJM Data Miner 2) are declared but disabled: the job reads `${{ secrets.<NAME> }}` only if set, never echoes it, and skips with a clear message when absent (P4 drafts EIA-860/923 and ATB steps this way) |
| D8 | Consumer side | a documented local step (`scripts/fetch_artifact.md` or script) that downloads the artifact and verifies `provenance.json` hashes before a case loader reads it |

## 4. Carried findings (Gate 1 review F3–F5, P1 finding; DECISIONS 33 item 9)
Each is closed in this gate by a builder fix plus a verifier test written from the spec, or explicitly deferred with a
DECISIONS entry naming the gate that needs it.
| ID | Finding | Gate 2 action |
|---|---|---|
| F3 | `_triplets` keeps explicit zeros when $A_{r,p,t}=0$ (inflates nnz, `tiny_coefficients`) | fix (`eliminate_zeros()`); test: a VRE with a zero-availability hour gives the same nnz as without the column entry. Needed before Gate 4 profiles |
| F4 | zero-profit check for free-duration candidate storage checks only $s_{xP}$ sign | fix + test with a free-duration candidate (both $s_{xP}$, $s_{xE}$ checked) |
| F5 | `ScipyHighsSolver`: ranged row lands in both `le` and `ge`, ≤ dual overwritten | fix + adapter test with one ranged row binding at each end. **Needed before Gate 3** if the PTDF form writes flow limits as ranged rows |
| P1-a | fingerprint `git_state` splits untracked paths on whitespace | fix (NUL-separated `git status -z`); test with a path containing a space |
| P1-b | `data/common/sources.csv` is hashed by case manifests; registry edits re-hash every case | decision: keep (re-hash is the correct signal) or exclude from case manifests; DECISIONS entry either way |

## 5. Evidence file `reports/gate-2-evidence.md`
Links and excerpts: (1) the CI run URL on the final gate-2 commit with pass/fail counts and the version block (C3);
(2) the C6 health artifacts and C7 two-job fingerprint comparison; (3) a `data-download` dispatch run URL with
`provenance.json` and a second run showing equal hashes (D5); (4) a deliberately broken-hash dispatch (manifest
edited on a throwaway branch) showing failure (D3); (5) proof of C5 (a marker without a reason fails the check);
(6) F3–F5, P1-a/b outcomes; (7) spec/DECISIONS changes made in the gate; (8) known limitations.

## 6. Review and sign-off
- **Verifier [Sonnet]:** C1–C9, D1–D8 pass/fail table and the §4 tests, in `reports/gate-2-review.md`.
- **PM [Sonnet]:** token/runtime cost of CI; checks no raw data or secrets landed in git history.
- Formulation lead: only if §4 fixes touch formulation semantics (F5 dual signs). Markets/consulting reviewers: not needed.
- Decision list for the owner, format as gate-1.md §6. Required items: (1) C1–C9 pass on the final commit? (2) D1–D8
  pass, no raw data committed? (3) F3–F5, P1-a/b closed or deferred with reasons? (4) pinned versions accepted as the
  supported environment? (5) spec/DECISIONS changes accepted? (6) owner enables branch protection on `main` requiring
  the `ci` check (owner-only GitHub setting)? (7) merge `gate-2` to `main` and mark Gate 2 DONE?

[P] = proposed number, owner to confirm.
