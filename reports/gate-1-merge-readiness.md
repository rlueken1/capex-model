# Gate 1 merge readiness (W7a, PM, 2026-11-26)

**Verdict: ready to merge `gate-1` → `main`. Merge not executed by this run — needs the owner (W7b).**

## Checks
| Check | Result |
|---|---|
| W6-spec1 (M1, C1, M6; DECISIONS 35) | done |
| W6-fix1 (M1, M2, C2) | done |
| W6-spec2 (canonical outputs; DECISIONS 36) | done |
| W6-fix1-test (verifier tests M1/M2/C2, determinism) | done |
| CI on final gate-1 work commit 7c7837f | run 58 **green** (run 57 on ca92d50 green) |
| Local pytest at f4c99f9 | 460 passed, 0 failed, 0 xfail |
| `git merge-tree origin/main origin/gate-1` | 1 conflict: `CLAUDE.md` only (43 commits, 103 files) |

## The one conflict
`main` has the older "Concurrent runs" wording; `gate-1` has the newer owner rule (2026-11-26) that prep items also run
when the next gate item is claimed. Resolution: take `gate-1`'s `CLAUDE.md` as is (`git checkout --theirs CLAUDE.md`).

## Why the merge was not done
DECISIONS 33 item 7 pre-approves the merge, executed by W7. But the scheduled-task prompt that starts these unattended
runs says "Never mark a gate done or merge to main", and CLAUDE.md hard rules say the same. The run prompt wins for
unattended runs, so this run stopped at the check.

## Owner steps (W7b)
1. `git checkout main && git merge --no-ff gate-1` → resolve `CLAUDE.md` with gate-1's version → push.
2. PLAN.md: Gate 1 DONE; create `gate-2` from `gate-1`; PM scrum plans Gate 2 items (P2 drafts gate-2.md / gate-3.md).
