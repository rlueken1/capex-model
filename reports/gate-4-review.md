# Gate 4 review: RTS-GMLC fixed-fleet dispatch vs PLEXOS

Item G4-8, 2026-11-28 UTC. PM (main session) + markets reviewer [Opus, 1 subagent, read-only]. Criteria: `docs/gates/gate-4.md`
(approved, DECISIONS 55). Evidence: [gate-4-evidence.md](gate-4-evidence.md) (G4-6a/6b); trace: [gate-4-spec-trace.md](gate-4-spec-trace.md)
(G4-7, 10 findings); fixes G4-7-fix1/1b/2/3 (DECISIONS 60); ledgers: [performance-ledger.md](performance-ledger.md), [complexity-ledger.md](complexity-ledger.md).

## 1. Final commit and CI
- Last code/test change on `gate-4`: `b6b6c04` (G4-7-fix3). CI run [#213](https://github.com/rlueken1/capex-model/actions/runs/46130716287)
  **red on exactly the 6 known C1/G1 test ids** (833 pass / 6 fail / 1 xfail (S2b) / 6 skip; check_markers ok). The red is honest:
  thresholds unchanged, no xfail added (counts from the G4-7-fix3 session log; CI runs #203–#213 all concluded failure, consistent with these 6).
- Full-year workflow: run [46107908584](https://github.com/rlueken1/capex-model/actions/runs/46107908584) (120-min limit, DECISIONS 59):
  `r4f` and `r4f-tests` **green** (R4-F solves 6.1 min for two cases; health + B1 pass). `r4nf` **cancelled at 120 min** — the nodal
  full year (≈3.7 M cols, dcpf) still does not finish. Report-only (gate-4.md §8); recorded as "did not finish in 120 min".

## 2. Pass/fail table (gate-4.md §11 items 1–8)
| # | Criterion | Verifier | PM / markets | Note |
|---|---|---|---|---|
| 1 | F0, C0 | pass | agree | F0 max 4.1e-4 MW (tol 1 MW) |
| 1 | C1 ≤ 5% [P] | **FAIL** 7.10 / 7.14 / 6.97% | agree, **explained** | §3 below; decision 1 |
| 1 | G1 ≤ 3 pp [P] | **FAIL** coal +8.4, gas CC −10.3 pp | agree, **explained** | nuclear 0.01 pp, hydro/RTPV exact |
| 1 | G2 unserved 0 | pass | agree | |
| 2 | L1/L2/P1/U0 reported, gap-labelled | reported | agree | no unexplained gross mismatch (§3) |
| 3 | Health, UNEXPLAINED = 0, R4-NS storage, S2a–c | pass (S2b strict xfail) | agree | R4-NX 31/31 after F4-1 fix |
| 4 | H1a–e, A1, U1, B1, N1; M13–M16 | pass / caught | agree | M13/M16/S2c via forced interval route |
| 5 | T1–T4 + pjm5 golden identity; F-0.4 | pass | agree | pjm5 Gate-3 golden stored (F4-2); F-0.4 amendment 1 |
| 6 | Performance ledger, [P] budgets | pass | agree | window ≤ 30.1 s; R4-F 169–252 s / ≤ 2.7 GB (thin local margin); R4-NF did not finish (reported) |
| 7 | Complexity rows `tx.dc_links`, `tx.model` | rows present | agree with proposals | DECISIONS 59(4) |
| 8 | K4–K6, provenance | pass | agree | book lacks cell-level provenance (F4-3, carry) |

## 3. UC / reserve gap narrative (C1, G1, L1, U0, P1)
Our model is an LP with one linear cost per unit (secant heat rate, no no-load, DECISIONS 57). PLEXOS solved day-ahead with unit
commitment, Pmin, no-load and start costs, 7 reserve products and fixed hydro/RTPV. The window is two summer weeks.
- **Cost (C1/C2).** C1 is the dispatch gap alone: $1.82 M of $25.70 M = 7.1%. The basis gap ($1.31 M, 4.8%) is what PLEXOS's cost
  file adds over its own dispatch at our MC; the markets reviewer recomputed **no-load cost = $1.248 M = 95% of it** (rest starts and curve shape).
  Total gap to the cost file: $3.13 M (11.6%); C2 closes exactly.
- **Mix (G1/U0).** Gas CC −10.36 pp = −185.9 GWh, offset by coal +151.4, gas CT +21.3, VRE +13.4 GWh. U0: 171.2 GWh of gas-CC energy
  is committed at Pmin above the bus price in PLEXOS — **92% of the gas-CC shift**. The VRE part equals PLEXOS's zero-price curtailment
  (10.9 GWh wind, 2.6 GWh PV, 63 h), caused by must-run plus fixed hydro/RTPV. Reserves act through which units are committed; no separate line.
- **Prices (L1/P1).** Ours are flat (21.7–28.6 $/MWh); PLEXOS 0–111.6 with ~51 zero-price hours (matches nuclear-at-Pmin hours, 19,800 MWh / 396 MW
  ≈ 50 h) and UC-driven spikes. PLEXOS setters coal 58% (inferred against *our* MC ±0.5, indicative only) vs ours gas CC 67%: with gas CC
  held at Pmin, coal sits on the margin. Expected for an LP; LMPs are reported, not judged (O4).
- **Not UC:** gas CT runs 1.33% vs 0.14% and sets 6% of hours because the secant heat rate puts some CTs (25.9–28.9) below the top CCs (29.5).
  Heat-rate artefact, within G1's 3 pp, not a bug. ~$0.6 M of the dispatch gap is within-tech re-dispatch (plausible, not yet shown).
- **No sign of a data or alignment error:** F0 passes, basis gap reproduced from no-load, hydro/RTPV/nuclear match, the independent
  scipy route reproduces C1 (G4-3), and the spec trace finds nothing in code that contributes (trace §5).

## 4. Markets reviewer (Opus) — verdict **yes, conditional**
- Attribution credible and the energy balance essentially complete (§3).
- **C1/G1:** accept as "fail as measured, explained", **after one diagnostic**: the verifier reruns R4-C in the independent scipy harness
  with PLEXOS commitment fixed (g ∈ [Pmin·u^PX, Pmax·u^PX]); no `src/capex/` change. If C1 ≲ 2% and coal/gas CC ≤ 3 pp, UC is shown, not
  asserted; if not, keep Gate 4 open and look for a data cause. Then convert the 6 red ids to `xfail(strict=True)` citing the DECISIONS entry
  (thresholds unchanged; they XPASS-fail when UC lands, Gate 11), plus a non-judging regression pin (C1 7.1 ± 0.5 pp, coal/gas CC ± 0.5 pp)
  so the xfail cannot hide drift. No min-gen proxy in the model at this gate (DECISIONS 26).
- **Reference:** right published figures (PLEXOS DA at the pinned commit). Cost file now consistent with fuel + VOM + no-load + starts;
  storage/CSP removal supported (gen = load exactly). The window is not annual: R4-F has coal setting price 51% of hours vs 27% in the window.
- **S2b:** accept the strict xfail; carry the constructive candidate-build fixture to Gate 5 (case (c) is structurally unreachable in a fixed fleet;
  a hook-level test would test linear algebra, not price formation).
- **Complexity:** agree — `tx.dc_links` keep, default `controllable`; `tx.model` dcpf option, `transport` default.
- **Forward (Gate 5+, none blocking):** (a) one heat-rate convention for PJM consistent with the setter benchmark; (b) report the PJM DA price
  duration curve unjudged until Gates 9/11; (c) PJM load is net of BTM solar — no double-counting of rooftop PV; (d) state the missing loss
  component in LMP comparisons; (e) watch nuclear/coal must-run in PJM backcasts; a min-gen proxy could be its own gated feature before Gate 11.

## 5. PM checks
- **Secrets** (210 commits on `gate-4` history): no token/key patterns, no `.env`/credential files. **Pass.**
- **Raw data:** no `download/`/`data/raw/` paths ever committed; `.git` 18 MB (vendored test systems only). **Pass.**
- **Cost:** 14 gate items incl. 5 fix items; CI ≈ 2.5 min/run; full-year workflow ≈ 12 min (R4-F) + 120 min wasted on R4-NF per push of the workflow file.
- **Carry to Gate 5 (items for the Gate 5 plan):** F4-3 cell-level provenance → assumptions book (golden refresh at the boundary);
  F4-5 solver-status enum (later builder item); S2b candidate-build fixture (F4-10); F4-8/F4-9 narrative notes; optional R4-C sizing of the
  secant heat-rate effect on G1 (DECISIONS 57; markets: gas CT order).

## Owner decision list (gate-4.md §11; recommendation in bold)
1. C1/G1 fail as measured on R4-Z/C/N. Accept as an **explained UC gap** (DECISIONS entry; 6 ids → strict xfail citing it, thresholds unchanged;
   regression pin; targets carry to Gate 11 at 2%/2 pp)? **Recommendation: yes, conditional on one verifier item G4-9** (fixed-commitment
   diagnostic in the scipy harness, ~1 session, Sonnet) confirming C1 ≲ 2% and G1 ≤ 3 pp. If no: Gate 4 stays open as fail.
2. L1/L2/P1/U0 reported with gap labels and no unexplained gross mismatch? **Yes** (§3).
3. Health all pass, UNEXPLAINED = 0, storage under dcpf correct (R4-NS, S2a/S2c)? **Yes.**
4. H1a–e, A1, U1, B1, N1 pass and M13–M16 caught (M13/M16 via forced interval route)? **Yes.**
5. Golden identity T1–T4 + pjm5 holds; F-0.4 with amendment 1 (DECISIONS 60) accepted? **Yes.**
6. Performance ledger present and within [P] budgets; R4-NF recorded as "did not finish in 120 min", report-only, no further CI minutes spent on it
   (remove the r4nf jobs from push triggers, keep dispatch)? **Yes.**
7. `tx.dc_links` keep, default `controllable`; `tx.model` dcpf option, `transport` default? **Yes.**
8. K4–K6 done, provenance complete (cell-level book deferred to Gate 5 as F4-3)? **Yes.**
9. S2b: accept the strict xfail and carry the candidate-build fixture to Gate 5 (not a hook-level test)? **Yes.**
10. Merge `gate-4` to `main` and mark Gate 4 DONE, after G4-9 and the xfail conversion turn CI green? **Yes.** If no: Gate 4 stays open; prep lane continues.
11. Approve the Gate 5 carry list (§5) and the markets forward notes (a)–(e) as inputs to the Gate 5 criteria draft? **Yes.**
