# Gate 3 review — PJM 5-bus, DC power flow option

Item G3-7, 2026-11-27 UTC. PM (main session) + markets reviewer [Opus, 1 subagent, read-only]. Criteria: `docs/gates/gate-3.md`
(approved, DECISIONS 47). Evidence: [gate-3-evidence.md](gate-3-evidence.md) (verifier, G3-5); trace:
[gate-3-spec-trace.md](gate-3-spec-trace.md) (formulation lead, G3-6). The verifier's pass/fail table is the evidence file §13;
this file confirms it, records the G3-6 fixes that came after it and adds PM and markets checks.

## 1. Final commit and CI
- Last code change on `gate-3`: `b250c3b` (G3-6-fix5). CI run [#166](https://github.com/rlueken1/capex-model/actions/runs/46033770431)
  **success**; #162–#166 (G3-6-fix4/fix5 and claims) all green. Later commits are PLAN/reports only.
- Evidence §1 counts (637 pass) are from `2563d52`. After the G3-6 fixes the suite is **671 pass / 0 xfail / 0 fail**
  (G3-6-fix5 session log), check_markers ok; T1–T4 golden and pjm5 outputs unchanged apart from the one-time F-0.3 fingerprint change
  (DECISIONS 52(2)).

## 2. Pass/fail table (gate-3.md §3, §4, §4a)
| Criterion | Verifier | PM / markets | Note |
|---|---|---|---|
| P5a base (angle) | pass | agree | vs independent ~1e-13; vs published 0.0045 $/MWh, 0.0048 MW (tol 0.01) |
| P5b PTDF = angle | pass | agree | ≤ 7e-15 |
| P5c reference-bus invariance (10 runs) | pass | agree | |
| P5d uncongested | pass | agree | one price 30, congestion 0 |
| P5e load scan (72 h) | pass | agree | 0 class mismatches; no degenerate hour on pjm5 (DEGENERATE covered by G3-6-fix3 fixture) |
| P5f transport contrast | reported | agree | §4 below |
| §4 health checks (KVL, PTDF, decomposition, rent, line duals, islands, conditioning, ranged rows) | pass | agree | islands: isolated node now runs (G3-6-fix5) |
| §4 default unchanged (`transport`) | pass | agree | outputs byte-identical per §8.10a (DECISIONS 50); fingerprints change once for F-0.3 (DECISIONS 52) |
| M7–M10 mutations | all caught | agree | |
| K1 / K2 / K3 | pass | agree | K1/K3 on data-download run 45981948446 |
| pjm5 provenance (P3) | pass | agree, **licence `verify`** | MATPOWER case files "distributed with permission"; internal test use only |
| G3-6 trace | 15 findings, 0 blockers | agree | 8 should-fix closed by G3-6-fix1…fix5; F3-3/F3-9/F3-12/F3-13 → Gate 4, F3-4 → schema bump (DECISIONS 49, 52) |

## 3. PM checks
- **Secrets in git history** (171 commits, all 7 branches fetched): no token/key patterns (GitHub PAT, AWS, Anthropic, private keys,
  `api_key = "…"`), no `.env`/credential files. **Pass.**
- **Raw data:** no `download/` or `data/raw/` path ever committed; vendored test-system data only (`cases/raw/rts_gmlc/`, `cases/raw/pjm5bus/`,
  both owner-approved). Pack 10.2 MiB. **Pass.**
- **Housekeeping:** throwaway branch `g2-7b-broken-hash` still exists on origin (Gate 2 item 7 asked to delete it) — owner item 9.
- **Cost:** 14 gate items incl. 6 fix items; CI ≈ 70 s/run. Fix churn came from cross-environment float noise (G3-3-fix/fix2) and strict
  key/spec gaps; both are now settled by rule (DECISIONS 50–53), not by test tweaks.

## 4. Markets reviewer (Opus; verdict **yes**, nothing blocks)
- **Faithfulness:** LMPs 16.98/26.38/30/39.94/10, D–E binding E→D, μ ≈ −62.32, surplus 14,957.29 = 62.322 × 240 re-checked by hand;
  Sundance (40) correctly off at LMP_D 39.94. Decomposition π = λ_ref − H·μ, loss 0, matches PJM's congestion component convention.
  **Caveat:** inputs are checked against pinned `case5.m`; the "published" LMP row was written from memory and reproduced by our own
  independent solve — Li & Bo's table itself was not accessed (paywall). Values agree with the widely cited results.
- **Reference bus:** PJM's energy component uses a load-weighted distributed reference (here λ ≈ 32.89, not 16.98). Totals, spreads,
  rent unchanged (P5c); only the energy/congestion split moves. Irrelevant now; matters when comparing to PJM/IMM component tables.
- **Bus D α (1.497 Solitude, −0.497 Brighton):** correct. Client reading: one more MW at D, with D–E full, is served by raising Solitude
  ~1.5 MW and backing Brighton ~0.5 MW → 1.5×30 − 0.5×10 ≈ $39.94; a price above the dearest running unit is normal loop-flow pricing,
  not an error or market power. Call α "re-dispatch factors", never "% shares".
- **P5f:** with line ratings as transfer limits, `transport` hides the loop flow, the price separation and 15% of cost, and breaks KVL
  by 523 MW. `transport` stays the right default for zonal/interface models **only if** interface limits come from transfer-capability
  data that already reflects KVL (PJM CETL / published interface limits), never summed line ratings; blank = unlimited must not be
  allowed for zonal interfaces; zonal rent is a lower bound on PJM congestion; hurdle spreads are reported apart from congestion rent.
- **Keep `dcpf` for Gate 4 RTS-GMLC:** yes (line data published, small, 1.2× end-to-end).
- **Forward should-fix (none blocking):** (a) [Gate 4] RTS-GMLC has storage → close F3-9/F3-13 before dcpf + storage is reported;
  (b) [Gate 4] RTS-GMLC has an HVDC link (113–316); formulation §7.4a excludes "HVDC/transport links mixed with lines" → add to the
  Gate 4 spec; (c) [Gate 4] RTS-GMLC reference results include UC and reserves (our Gates 9/11) → compare cost and mix, label LMP gaps
  as expected; (d) [PJM zonal] optional distributed load-weighted reference; compare to PJM energy+congestion, state the missing loss
  component; (e) [PJM zonal] client outputs show shadow prices as positive $/MWh with direction ("D–E, E→D, 62.32"); (f) near-ties
  (Sundance 0.06 $/MWh from marginal) are common in real cases, so the DEGENERATE path (tested on fixtures, G3-6-fix3) will matter.

## Owner decision list (G3-7; gate-3.md §7 items 1–8, plus 9–10)
Already answered 2026-11-27 (DECISIONS 52): strict switch keys; one-time F-0.3 fingerprint change; F3-3/F3-9/F3-12/F3-13 to Gate 4;
§8.10a reading of C7. Not asked again.
1. P5a–P5f within tolerance and published LMPs matched at 0.01? **Recommendation: yes** — evidence §3–§4; note "published" = widely
   cited values reproduced independently, Li & Bo table not read (§4 caveat). If no: one data-lead item to obtain the paper table.
2. All health checks pass, UNEXPLAINED = 0, CONGESTION_LOOP weights correct? **Recommendation: yes** — evidence §3, §5; markets §4.
3. Mutation tests M7–M10 all caught? **Recommendation: yes** — evidence §5.
4. `transport` default and all Gate 1 results unchanged? **Recommendation: yes** — outputs byte-identical (§8.10a), Z values equal
   gate-1.md; fingerprints changed once for F-0.3 as you approved.
5. §7.4a completion and F-0.3 (amendments 1–3, DECISIONS 48, 50, 51, 53) accepted? **Recommendation: yes.**
6. `pjm5` provenance complete, licence `verify` (internal test use, cite Li & Bo 2010 + MATPOWER)? **Recommendation: yes**; never ship
   `case5.m` in client deliverables. If no: one data-lead item to ask MATPOWER for case-file terms.
7. Keep `dcpf` as an option for Gate 4 RTS-GMLC? **Recommendation: yes** (markets §4); `transport` stays default (DECISIONS 29).
8. Merge `gate-3` into `main` and mark Gate 3 DONE? **Recommendation: yes.** If no: Gate 3 stays open; prep lane (P11, P12) continues.
9. Delete branch `g2-7b-broken-hash` (Gate 2 throwaway, never merge)? **Recommendation: yes.**
10. Add markets notes (a)–(c) to the Gate 4 criteria draft (P12) and record (d)–(f) as later-gate notes (PJM zonal gates)?
    **Recommendation: yes.** If no: they stay as notes in this file.
