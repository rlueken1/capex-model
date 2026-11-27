# Gate 2 review — CI + data-download workflow

Item G2-8, 2026-11-27 UTC. PM (main session) + markets reviewer [Sonnet, 1 subagent]. Criteria: `docs/gates/gate-2.md`
(approved, DECISIONS 38). Evidence: [gate-2-evidence.md](gate-2-evidence.md) (verifier, G2-7/G2-7b).
Note: gate-2.md §6 names verifier + PM as reviewers and says markets is not needed; PLAN G2-8 added a markets reviewer for a
forward look at data sources. The verifier's pass/fail table is the evidence file; this file confirms it and adds the PM checks.

## 1. Final commit and CI
- Last code change on `gate-2`: `fc90b77` (G2-7a: data-download.yml fix + "Parse workflow files" CI step — evidence §8 item 1
  asked whether it landed: **it did**, `ci.yml` line 34). Later commits are reports/PLAN only.
- CI on the newest completed gate-2 commit `0564164`: run [#121](https://github.com/rlueken1/capex-model/actions/runs/45917047189)
  **success** (all jobs). Evidence §1 counts (547 pass / 30 skip / 0 fail) come from #107 at `c975ea4`; #117–#121 after G2-7a are
  all green, so the test set did not regress. The CI on the claim commit (#122) was still running at review time.

## 2. Pass/fail table
| # | Verifier | PM / markets | Note |
|---|---|---|---|
| C1–C9 | pass | agree | C3 fingerprint equality and C7 local-vs-CI π are by construction, not inspected (artifact download blocked here) |
| D1, D2, D3, D6 | pass | agree | D3 is the strongest evidence (run 45916853288: HASH MISMATCH, 0 artifacts) |
| D4 | pass (partial) | **limitation, not a block** | `provenance.json` fields never read from an Actions artifact; seen locally only (G2-7) |
| D5 | pass (via pins) | **limitation, not a block** | equal hashes follow from pin enforcement; valid for pinned `pjm5`, not yet shown for record-mode sources |
| D7 | pass (static) | **limitation, not a block** | keyed-source skip path not run on Actions (pjm5 needs no key) |
| D8 | pass (local) | agree, local only | never run against a real Actions artifact |
| F3, F4, F5, P1-a | closed | agree | fixes G2-4, tests G2-5 (10 fail on pre-fix code) |
| P1-b | closed | agree | exclude registry from manifest pins (DECISIONS 40) |

## 3. PM checks (gate-2.md §6)
- **CI cost:** ≈ 63 s wall per run, 4 jobs (test, 2× health-run, compare), ~4 billable runner-minutes per push; ~120 runs so far.
  Well inside the 10-min budget (C8). Session tokens: no CI-driven retries in this gate except V2-1 (G2-7 → G2-7a → G2-7b).
- **Secrets in git history** (full history, 124 commits, all branches fetched): no token/key patterns (GitHub PAT, AWS, Anthropic,
  private keys, `api_key = "…"`), no `.env`/credential/key files. **Pass.**
- **Raw data in git history:** none from the download workflow (no `download/` or `data/raw/` paths ever committed; workflow has
  `contents: read`, no push). Vendored test-system raw data is present by owner approval: `cases/raw/rts_gmlc/` (9 MB, DECISIONS 34)
  and `cases/raw/pjm5bus/` (P3, owner yes 2026-11-26). Pack size 5.3 MiB; largest blob 2.6 MB. **Pass.**

## 4. Markets reviewer (forward look; verdict **yes**, nothing blocks)
Should-fix, none for Gate 2: (a) print `provenance.json` and per-file sha256 to the job log so D4/D5 can be read from logs
(Gate 3, small); (b) CI test that `cases/raw/pjm5bus/case5.m` equals the sha256 in `data/manifests/pjm5.csv` (Gate 3);
(c) policy for sources that are revised after posting (PJM Data Miner 2 resettlements, EIA early-release): a `snapshot` pin mode with
retrieval date as vintage, plus durable storage beyond the 90-day artifact expiry (e.g. GitHub Release asset, hashes in manifest)
— settle before Gate 4/11; (d) Data Miner 2 rate limits/paging and EIA API key-in-URL redaction (Gate 11/16); (e) daily hub gas
has no free source identified under "buy nothing" — owner decision before Gate 16; (f) NREL ATB size check before enabling.

## Owner decision list (G2-8)
1. Do C1–C9 pass on the final commit? **Recommendation: yes** — evidence §1–§2, §5; CI #107 and #117–#121 green after the last code
   change. If no: name the criterion; it returns to the builder.
2. Do D1–D8 pass, with no raw data committed? **Recommendation: yes, with D4/D5/D7 as carried limitations** — evidence §3–§4, this
   file §2–§3. If no: one verifier item to read the artifact (owner downloads one) or add log printing (markets item a) first.
3. Are F3–F5, P1-a/b closed? **Recommendation: yes** — evidence §6, DECISIONS 40. If no: name the finding.
4. Accept the pinned versions (Python 3.12, numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, highspy/HiGHS 1.16.0, ubuntu-24.04,
   `requirements-ci.txt`) as the supported environment? **Recommendation: yes.** If no: say which to change; one builder item.
5. Accept the spec/DECISIONS changes (DECISIONS 38–41; data-schema §5/§6.1)? **Recommendation: yes** — evidence §7.
6. Will you enable branch protection on `main` requiring the `ci` check (GitHub setting, owner only)? **Recommendation: yes.**
7. Merge `gate-2` into `main` and mark Gate 2 DONE? **Recommendation: yes** — first delete throwaway branch `g2-7b-broken-hash`
   (never merge it). If no: Gate 2 stays open; prep lane continues.
8. Add markets items (a)+(b) to the Gate 3 criteria and record (c)–(f) as later-gate notes (Gate 4/11/16)? **Recommendation: yes.**
   If no: they stay as notes in this file only.
9. Bump `actions/checkout@v4`, `setup-python@v5`, `upload/download-artifact@v4` (Node 20 deprecated) in Gate 3? **Recommendation: yes.**
