# Gate 4 evidence: RTS-GMLC fixed-fleet dispatch vs the PLEXOS reference

Items G4-6a (window runs) and G4-6b (full year, ledgers; verifier, 2026-11-28). Criteria: `docs/gates/gate-4.md` sections 2, 5, 6, 8, 9. Remaining placeholders: A1-A10 block checklist and assumptions-book excerpts go to G4-7 (section 11).
All numbers come from runs in this session: `python -m pytest tests/test_gate4_comparison.py` (harness `tests/rts_compare.py`, no capex import) and a driver using the same
`make_window_case` + `capex.run.run_case` route that dumped every metric (scratch; the values below are its output). Window runs use blocks p063-p067 (360 h); comparison uses the 336 h of section 2.
Environment: HiGHS 1.16.0 (highspy 1.16.0), dual simplex. Solve + audit wall time: R4-Z 1.9 s, R4-C 2.0 s, R4-N 30.4 s, R4-NS 33.1 s (all <= 60 s [P]).
Code under test: working tree on `gate-4` after G4-5 (no `src/capex/` change in this item).

## Bottom line
- F0, C0, C2 (exact closure), G2 (unserved = 0 MWh), and all health checks (no fail, no warn, UNEXPLAINED = 0 on R4-Z, R4-C, R4-N, R4-NS) **pass**.
- **C1 FAILS on all three judged runs** (7.10% R4-Z, 7.14% R4-C, 6.97% R4-N vs <= 5% [P]) and **G1 FAILS on all three** (coal +8.3 to +8.4 pp, gas CC -10.2 to -10.4 pp vs <= 3 pp [P]). No threshold was changed.
  gate-4.md has no "explained gap" marker for C1/G1: only L1 is "reported, not judged"; section 3 S5 and benchmarks.md section 6 keep C1/G1 as pass/fail [P] ("tighten to 2%/2 pp after the UC gate").
  The tests therefore fail honestly (`test_c1_like_for_like_cost_gap_within_5pct[*]`, `test_g1_generation_share_by_tech[*]`: 6 red test ids). Owner decision at G4-8 (section 11 item 1).
- U0 attributes the gap: in R4-C 38.8% of PLEXOS gas-CC energy and 15.0% of coal energy is committed units at Pmin with MC above the bus price (section 5).
- S2b stays a strict xfail (no fixture reaches price-setter case (c) naturally); S2c, M13, M16 now pass through a forced interval-LP route (section 8).

## 1. Section 2 facts re-verified (tests `test_section2_*`, `test_k6_*`, all pass)
336 complete hours from p063 t1; 156 generation/cost columns, 73 price columns, 121 flow columns (120 AC + `113_316_1`); no `313_storage_1` / `212_csp_1` column; generation = load every hour (1,793,948 MWh);
DC1 303 h at +100, 20 h at -100, mean 85.41 MW; noTX DC1 from -155 to -62; price min -6.87, max 111.59, mean 21.79; 7 negative bus-hours; 13 congested hours (max spread 43.34); CB-1 at 500 MW in 10 h; noTX has one price per hour;
cost file $27.01 M vs $25.70 M at our MC (4.9% basis gap). **Not re-verified** (needs the upstream HTML reports, not vendored): whether PLEXOS modelled storage/CSP at all, what the cost file contains.

## 2. F0: PLEXOS dispatch feasible in our LP (judged, limit 1 MW)
| Run | gen < 0 | gen > cap | balance | flow > limit | result |
|---|---|---|---|---|---|
| R4-Z (allTX) | 0 | 4.1e-4 MW | 5.0e-5 MW | 0 | pass (margin 1 MW / 4.1e-4) |
| R4-C (noTX) | 0 | 4.1e-4 MW | 1.2e-4 MW | 0 | pass |

## 3. C0, C1, C2 (dollars over the 336-h window; Z = our variable cost from run dispatch x MC)
| Run | C^PX_our | Z^our | C0 Z <= C(1+1e-6) | C1 gap (target <= 5%) | PLEXOS cost file | basis gap | dispatch gap | C2 closes |
|---|---|---|---|---|---|---|---|---|
| R4-Z | 25,704,132 | 23,879,956 | pass | **7.10% FAIL** (margin -2.10 pp) | 27,012,409 | 1,308,277 (4.84%) | 1,824,176 | exact (rel < 1e-12) |
| R4-C | 25,714,970 | 23,879,956 | pass | **7.14% FAIL** (margin -2.14 pp) | 26,905,935 | 1,190,965 (4.43%) | 1,835,014 | exact (rel < 1e-12) |
| R4-N | 25,704,132 | 23,912,107 | pass (not judged) | **6.97% FAIL** (margin -1.97 pp) | 27,012,409 | 1,308,277 (4.84%) | 1,792,025 | exact (rel < 1e-12) |

C2 decomposition (each row): (PLEXOS cost - C^PX_our) + (C^PX_our - Z^our) = PLEXOS cost - Z^our. R4-Z and R4-C have the identical optimum (Z = $23,879,955.60): the three-zone network never binds on the window (test `test_zonal_lp_is_the_same_optimum_for_zonal_and_copper_plate`).
R4-N (nodal, DC1 controllable) costs $32,152 more than R4-Z (+0.13%), as expected from line limits.
The independent scipy zonal LP predicted C1 7.1% (G4-3); the capex runs reproduce it (7.10%, 7.14%).

## 4. G1 generation share by tech and G2 (judged)

**R4-Z** (vs allTX); G1 FAIL

| tech | ours % | PLEXOS % | abs pp | limit pp | result |
|---|---|---|---|---|---|
| coal | 40.23 | 31.79 | 8.44 | 3.0 | **FAIL** |
| gas_cc | 14.32 | 24.69 | 10.36 | 3.0 | **FAIL** |
| gas_ct | 1.33 | 0.14 | 1.19 | 3.0 | pass |
| oil | 0.00 | 0.02 | 0.02 | 3.0 | pass |
| nuclear | 7.49 | 7.48 | 0.01 | 0.5 | pass |
| hydro | 12.21 | 12.21 | 0.00 | 3.0 | pass |
| wind | 10.04 | 9.44 | 0.60 | 3.0 | pass |
| pv | 8.71 | 8.57 | 0.14 | 3.0 | pass |
| rtpv | 5.66 | 5.66 | 0.00 | 3.0 | pass |

**R4-C** (vs noTX); G1 FAIL

| tech | ours % | PLEXOS % | abs pp | limit pp | result |
|---|---|---|---|---|---|
| coal | 40.23 | 31.86 | 8.37 | 3.0 | **FAIL** |
| gas_cc | 14.32 | 24.61 | 10.29 | 3.0 | **FAIL** |
| gas_ct | 1.33 | 0.15 | 1.18 | 3.0 | pass |
| oil | 0.00 | 0.02 | 0.02 | 3.0 | pass |
| nuclear | 7.49 | 7.48 | 0.01 | 0.5 | pass |
| hydro | 12.21 | 12.21 | 0.00 | 3.0 | pass |
| wind | 10.04 | 9.49 | 0.55 | 3.0 | pass |
| pv | 8.71 | 8.51 | 0.19 | 3.0 | pass |
| rtpv | 5.66 | 5.66 | 0.00 | 3.0 | pass |

**R4-N** (vs allTX); G1 FAIL

| tech | ours % | PLEXOS % | abs pp | limit pp | result |
|---|---|---|---|---|---|
| coal | 40.13 | 31.79 | 8.34 | 3.0 | **FAIL** |
| gas_cc | 14.44 | 24.69 | 10.25 | 3.0 | **FAIL** |
| gas_ct | 1.36 | 0.14 | 1.21 | 3.0 | pass |
| oil | 0.00 | 0.02 | 0.02 | 3.0 | pass |
| nuclear | 7.49 | 7.48 | 0.01 | 0.5 | pass |
| hydro | 12.21 | 12.21 | 0.00 | 3.0 | pass |
| wind | 9.99 | 9.44 | 0.56 | 3.0 | pass |
| pv | 8.71 | 8.57 | 0.14 | 3.0 | pass |
| rtpv | 5.66 | 5.66 | 0.00 | 3.0 | pass |

G2: unserved energy 0 MWh in R4-Z, R4-C, R4-N, R4-NS (pass). Curtailment (reported): 0 MWh in R4-Z and R4-C; R4-N wind 868.2 MWh (868 MWh at pi = 0 on nodal buses); R4-NS wind 833.6 MWh, storage 0.
Reading: coal is over-dispatched (cheapest thermal MC) and gas CC under-dispatched; the shortfall is the Pmin/commitment of PLEXOS gas CC (U0). Nuclear (0.012 pp), hydro, RTPV match to 1e-8.

## 5. L1, L2, P1, U0 (all `reported`; label `expected gap: UC/reserves/fixed hydro+RTPV`)
**L1 prices ($/MWh).** Ours is an LP (one price per hour in R4-Z/R4-C); PLEXOS has UC, 7 reserve products and fixed hydro/RTPV.
| Run | mean ours | mean PLEXOS | min / max ours | min / max PLEXOS | p5 / p50 / p95 / p99 ours | p5 / p50 / p95 / p99 PLEXOS | node-h <= 0.01 ours / PX | node-h < 0 ours / PX | spread hours ours / PX |
|---|---|---|---|---|---|---|---|---|---|
| R4-Z (area) | 25.59 | 21.79 | 21.69 / 28.59 | 0.00 / 111.59 | 22.18 / 25.41 / 28.53 / 28.59 | 0.00 / 22.58 / 33.95 / 87.37 | 0 / 153 | 0 / 0 | 0 / 13 |
| R4-C (area) | 25.59 | 21.90 | 21.69 / 28.59 | 0.00 / 111.59 | 22.18 / 25.41 / 28.53 / 28.59 | 0.00 / 22.65 / 33.95 / 98.07 | 0 / 150 | 0 / 0 | 0 / 0 |
| R4-N (bus) | 25.60 | 21.79 | 0.00 / 42.21 | -6.87 / 111.59 | 22.18 / 25.41 / 28.53 / 28.59 | 0.00 / 22.58 / 33.95 / 87.37 | 9 / 3745 | 0 / 7 | 18 / 13 |

PLEXOS area rows are the mean of bus prices per area (R4-Z, R4-C); R4-N compares 73 buses. Quantiles p10/p25/p75/p90 are in the test properties (`-rP`). Ours has no negative price (MC >= 0), PLEXOS has 7 negative bus-hours.
R4-C is compared with noTX, whose reference price is one per hour; R4-Z/R4-N with allTX.

**L2 binding sets.**
| Item | PLEXOS allTX | R4-Z ours | R4-N ours |
|---|---|---|---|
| CB-1 / `ac_r2_r3` hours at limit | 10 (CB-1) | `ac_r2_r3` 191 h at flow = limit, zero price spread | `ac_cb_1` 3 h |
| DC1 hours at +-limit | 323 (303 at +100, 20 at -100; mean +85.41 MW) | `dc_r1_r3` 291 h | `dc_113_316` 326 h (268 at +100, 58 at -100; mean 63.3 MW) |
| congested hours (bus spread > 0.01) | 13 | 0 (3 zones, one price per hour) | 18 |
| other AC lines at limit (hours) | n/a | `ac_r1_r3` 188, `ac_r1_r2` 2 (all at zero rent) | `ac_c6` 19, `ac_a11` 5, `ac_c29` 4, `ac_a27` 1 |
Not a gross mismatch: DC1 is at a limit in 326 of 336 h (PLEXOS 323); the direction split (268 at +100 / 58 at -100) is more balanced than PLEXOS (303 / 20) and the mean is lower (63.3 vs 85.4 MW), a data point for the UC/reserve gap, not a bug. R4-Z `ac_r2_r3`/`ac_r1_r3` are at their rating with zero shadow price (no spread). Counts are over the 336-h window.
Nodal congested hours 18 vs 13 PLEXOS.

**P1 marginal tech shares (R4-Z, R4-C; ours from `price_setter_summary` weighted hours, PLEXOS-inferred per section 5).** Ours (fuel): coal 27.2%, gas 72.8% (R4-Z and R4-C identical; gas CC 66.7%, gas CT 6.1%).
| tech | ours | PLEXOS-inferred R4-Z (allTX) | PLEXOS-inferred R4-C (noTX) |
|---|---|---|---|
| coal | 27.2% | 57.8% | 58.9% |
| gas_cc | 66.7% | 16.5% | 18.6% |
| gas_ct | 6.1% | 0.0% | 0.0% |
| oil | 0.0% | 0.0% | 0.0% |
| nuclear | 0.0% | 0.0% | 0.4% |
| hydro | 0.0% | 12.4% | 11.6% |
| wind | 0.0% | 4.0% | 2.1% |
| pv | 0.0% | 4.0% | 3.3% |
| rtpv | 0.0% | 5.4% | 5.1% |

PLEXOS' setters include hydro, wind, PV and RTPV (fixed schedules inside their ranges with MC 0 near a zero price) and coal 58-59% of hours; ours is an all-thermal marginal set (gas CC 67%). Consistent with U0: PLEXOS gas CC sits at Pmin, so coal rather than gas CC is on the margin.

**U0 UC must-run (R4-C vs noTX): committed units at Pmin with MC > bus price.**
| tech | must-run MWh | tech MWh | share |
|---|---|---|---|
| coal | 85,856 | 571,500 | 15.0% |
| gas_cc | 171,190 | 441,549 | 38.8% |
| gas_ct | 528 | 2,637 | 20.0% |
| oil | 40 | 446 | 9.0% |
| nuclear | 19,800 | 134,198 | 14.8% |
| hydro | 0 | 219,104 | 0.0% |
| wind | 0 | 170,198 | 0.0% |
| pv | 0 | 152,748 | 0.0% |
| rtpv | 0 | 101,569 | 0.0% |

Gas CC 171,190 MWh (38.8% of its energy) and coal 85,856 MWh (15.0%) are held at Pmin although cheaper-than-price units are not all used: the same energy that our LP gives to coal (coal +8.4 pp) while gas CC drops 10.3 pp. Nuclear 19,800 MWh at Pmin (flat in both models, 0.01 pp apart).

## 6. Health checks (section 6) on the window runs
| Run | checks pass / warn / fail | UNEXPLAINED | primary class shares | notes |
|---|---|---|---|---|
| R4-Z | 23 / 0 / 0 | 0 | MARGINAL_UNIT 100.0% | zone-hours |
| R4-C | 23 / 0 / 0 | 0 | MARGINAL_UNIT 100.0% | zone-hours |
| R4-N | 31 / 0 / 0 | 0 | MARGINAL_UNIT 94.9%, CONGESTION_LOOP 5.1% | bus-hours |
| R4-NS | 31 / 0 / 0 | 0 | MARGINAL_UNIT 92.7%, CONGESTION_LOOP 5.4%, STORAGE_CH 1.9%, STORAGE_DIS 0.0% | bus-hours |

No warn on any run (nothing to explain). Tests: `test_health_zonal_runs[R4-Z, R4-C]`, `test_health_nodal_dcpf_runs[R4-N, R4-NS]` pass: `audit_profile=standard warn>0.001 fail>0.1` in detail for balance/soc/kvl/ptdf,
conditioning not `fail`, the nine dcpf checks present (loop_interval value 0, `dcpf.islands` "1 island", 73 buses). R4-NS shows 513 storage bus-hours ({'STORAGE_CH': 512, 'STORAGE_DIS': 1}) and every one passes its price check (residual within max(0.01, 1e-5 |pi|));
only 1 STORAGE_DIS hour (DA window prices barely pay for discharge on the aligned fleet: informational). CONGESTION_LOOP is 5.1% (R4-N) and 5.4% (R4-NS) of bus-hours; no CONGESTION_LOOP row has an interval (price_lo = price_hi everywhere), i.e. no case-(c) hour occurred; DEGENERATE interval widths are therefore all 0.

## 7. Known-answer tests H1a-H1e, S2a-S2c, A1, U1, B1, N1
Status in the suite (default env): H1a-e, S2a, A1, U1 pass; S2c passes through the forced route (section 8); **S2b strict xfail**. With `CAPEX_GATE4_FULL=1` (G4-6b, local):
- **B1** (R4-F restricted to p063-p067 equals R4-Z) **pass**; **N1** (nodal interior-bus price vs marginal-unit cost; vacuity guard 300 interior bus-hours) **pass** (47.9 s).
- Expected-vs-obtained tables for H1a-e, S2a, A1, U1 are the assertions of `tests/test_gate4_known_answers.py` (independent scipy route, `tests/g4lib.py`); the tests pass at the spec tolerances. Per-hour tables were not reproduced here: the independent route is the oracle and the test is its report.

## 8. Mutations M13-M16 and the case-(c) fixture
- M14, M15: pass (suite). M13 (S2 inequality sign flipped), M16 (UNBOUNDED_OR_INFEASIBLE mapped to NaN) and S2c (stub status): **now pass, through a forced interval-LP route.** `g4lib.force_interval` patches `capex.audit.loop.classify` to return `INTERVAL` so the interval LP runs on every congested hour. Reason: price-setter case (c) needs a degenerate dual vertex; the simplex vertex that HiGHS returns always has the cost-matching units (including units at a bound whose bus price equals their cost, `TIE_AT_BOUND`) as rows, so rows >= columns. About 300 pjm5 and chain variants (ratings set to the exact unconstrained flows, generator caps equal to dispatch, with/without storage, radial chains: 150 random variants in G4-6a plus the ~150 of G4-4v) gave no case-(c) hour; IPM without crossover gives no basis and the audit skips the price-setter report.
  Mutation tests assert their vacuity guards (calls > 0, mutated > 0) and pass. What the forced route proves: the status map (+-inf, no NaN), `loop_interval` firing on a flipped row and on a NaN side. What it does not prove: that a naturally arising case-(c) hour gets the right interval.
- **S2b remains strict xfail** (test text unchanged, reason updated): with the interval path forced on a case-(a) hour the equality rows pin the point, so the S2 storage rows cannot bite, and S2b's own vacuity guard (storage rows must tighten the interval) cannot be met. Closing it needs a fixture with a degenerate dual vertex that HiGHS actually returns, or a unit-level test of `capex.audit.loop.interval` against `g4lib.analyse` on a hand-built rank-deficient system (a test of a code unit, no run). Owner/G4-8 decision whether Gate 4 needs the second; no code finding.

## 9. Full-year R4-F / R4-NF, B1, N1
**Dispatched-job evidence.** `gate4-fullyear.yml` cannot be dispatched yet (it is not on `main`; owner action open), so the evidence is the push-triggered run **46095301368** on `gate-4` (head 7c85228, ubuntu-24.04, HiGHS 1.16.0, 4 jobs). Job logs read with the GitHub MCP tools.

| Job | Result | Detail |
|---|---|---|
| `r4f` | **green** (11 min) | solve step 01:53:12 to 01:58:55 = 5.7 min for 2 full-year solves; ledger step 01:58:55 to 02:04:02; artifact `gate4-r4f` (id 15242598447, 50 files) |
| `r4f-tests` | red, only XPASS(strict) | R4-F health tests passed but carried a strict xfail marker (removed in this item); B1 passed |
| `r4nf` | **cancelled at the 30-min limit** | nodal full-year solve did not finish; no ledger row produced |
| `r4nf-tests` | cancelled at 30 min | N1 passes locally (above); the R4-NF test did not finish |

**R4-F (transport, 122 blocks; budget 5 min / 4 GB [P]; a miss is a warning, not a failure).**
| Source | Case | Size (rows x cols, nnz) | Wall s (solve + audit) | Ledger solve s | Peak RSS MB | Objective USD/yr | Health | Budget |
|---|---|---|---|---|---|---|---|---|
| Actions 46095301368 (`gate4_fullyear.py` summary) | rts_gmlc | 1,405,440 x 1,440,732 | 169 | 148.4 | 2,725 | 400,788,145 | pass | pass (169 s, 2.7 GB) |
| Actions 46095301368 | rts_gmlc_px | 1,370,304 x 1,405,593 | 174 | 151 | 2,292 | 413,385,158 | pass | pass |
| Local sandbox (2 cpu, 7 GB), `gate4_fullyear.py solve` | rts_gmlc | same | 241 | 225.3 (run.json) | 2,711 | 400,788,145 (matches Actions to 1e-9 rel) | pass (23/0/0) | pass (241 s, 2.7 GB) |
| Local, `python -m capex ledger` (1 repeat) | rts_gmlc / rts_gmlc_px | nnz 3,975,461 / 3,857,838 | n/a | 225.8 / 251.7 | 2,709 / 2,313 | n/a | n/a | pass |
| Local, `pytest -k "r4f or b1"` (3 solves + audits) | both + B1 | n/a | 775 (whole run) | n/a | 2,749 (peak child) | n/a | 3 passed | n/a |

R4-F is inside the budget on both machines but with little margin on the slower local box (252 s of 300 s ledger solve). Zero health fails; rts_gmlc health 23 pass / 0 warn / 0 fail; UNEXPLAINED 0 (`test_r4f_full_year_health[rts_gmlc_px, rts_gmlc]` pass, markers removed). Fallback (per-block solves) not needed at Gate 4.
**R4-NF (nodal dcpf, ~3.7 M cols): did not finish within the 30-min job limit (run 46095301368); owner question open (raise the r4nf timeout to 120 min, or keep the row as "did not finish").** Report-only (gate-4.md section 8); not attempted locally. Its test (`test_r4nf_full_year_performance_only`) keeps its strict xfail marker; it is skipped without `CAPEX_GATE4_FULL=1` and could not be judged.
Window performance (local, median of 3, `python -m capex ledger`): R4-Z 1.06 s, R4-C 1.21 s, R4-N 27.97 s, R4-NP (PTDF) 9.82 s, R4-NX 27.11 s, R4-NS 30.1 s: all <= 60 s [P]. pjm5 dcpf angle 10.3 ms (Gate 3: 11.5 ms), same size (1,224 x 1,517, nnz 3,672). R4-NP has 9.5 M nonzeros (24x R4-N) and 1.3 GB RSS: PTDF is dense; it is faster here but not scalable (ledger finding).

## 10. Price-setter class/fuel shares for R4-F
rts_gmlc (full fleet, local run; the rts_gmlc_px artifact is on Actions only), 3 zones x 8,784 weighted hours: classes MARGINAL_UNIT 97.5%, STORAGE_CH 1.6%, STORAGE_DIS 0.9%, UNEXPLAINED 0 (zone-hours: 25,705 MARGINAL_UNIT, 415 STORAGE_CH, 232 STORAGE_DIS). By tech: coal 51.3%, gas CC 34.3%, gas CT 3.4%, nuclear 3.3%, storage 2.5%, wind 1.7%, hydro 1.3%, PV 1.1%, RTPV 0.9%, CSP 0.3%. Window shares are in section 6. Gas CC / coal ordering mirrors the window run (coal on the margin more often than in the 5-day window, 27% there).

## 11. A1-A10, ledger rows, CI links, assumptions book
- **Ledger rows:** `reports/performance-ledger.md` (9 rows: R4-Z, R4-C, R4-N, R4-NP, R4-NX, R4-NS, pjm5 dcpf, R4-F x2; local 2-cpu sandbox; Actions values in section 9). `reports/complexity-ledger.md`: `tx.dc_links`, `tx.model` (RTS) rows, values below.
- **Complexity values (window p063-p067, 360 h solved, local):**
| Pair | rows x cols x nnz | solve s | C1 gap | G1 coal / gas CC pp | LMP / L2 |
|---|---|---|---|---|---|
| R4-Z (transport 3 zones) | 56,160 x 57,753 x 159,615 | 1.06 | 7.10% | 8.44 / 10.36 | 0 congested hours; mean 25.645 |
| R4-N (dcpf, DC1 controllable) | 124,920 x 151,353 x 399,015 | 27.97 | 6.97% | 8.34 / 10.25 | 19 hours with bus spread > 0.01 (PLEXOS 13 in 336 h); DC1 at bound 350 h; mean 25.649 |
| R4-NX (`tx.dc_links: exclude`) | 124,920 x 150,993 x 398,295 | 27.11 | 6.96% | 8.36 / 10.26 | 22 spread hours; DC1 absent; mean 25.649 |
  R4-N vs R4-NX: Z +$2,610 (+0.011%) when DC1 is excluded; bus LMP differs by > 0.01 in 10 of 360 hours (max 13.19 $/MWh); +360 cols, +720 nnz, +0.9 s. R4-N vs R4-Z: rows 2.2x, cols 2.6x, nnz 2.5x, solve 26x; Z +$32,152 (+0.13%); C1 -0.13 pp, G1 <= 0.1 pp; the only run that shows bus congestion.
- **A1-A10 block checklist, assumptions-book excerpts (lossless DC1, aligned fleet, heat-rate choice):** deferred to G4-7 (formulation-lead spec trace, `reports/gate-4-spec-trace.md`); not verified here.
- **CI run links:** Actions run 46095301368 (full-year, section 9). CI on push of this commit is the judge for the window cases.

## 12. Pass/fail by gate-4.md criterion (window part)
| Criterion | Result |
|---|---|
| F0 | pass |
| C0 | pass (R4-Z, R4-C) |
| C1 <= 5% [P] | **FAIL** 7.10 / 7.14 / 6.97% |
| C2 closes | pass (exact) |
| G1 <= 3 pp (nuclear 0.5) [P] | **FAIL** coal, gas CC on all three runs (nuclear 0.01 pp pass) |
| G2 unserved 0 | pass |
| L1, L2, P1, U0 | reported (section 5); no unexplained gross mismatch beyond the UC gap |
| Health, UNEXPLAINED = 0, dcpf checks, R4-NS storage rows | pass |
| M13, M16, S2c | pass via forced route; S2b xfail (section 8) |
| Window solve time <= 60 s [P] | pass (max 33.1 s with audit; ledger 27.97 s R4-N, 30.1 s R4-NS) |
| R4-F health, UNEXPLAINED = 0, B1 | pass (Actions + local) |
| R4-F full year <= 5 min / 4 GB [P] | pass: Actions 169-174 s, 2.3-2.7 GB; local 241 s, 2.7 GB (252 s ledger solve, thin margin) |
| R4-NF (reported) | did not finish within 30-min job limit (run 46095301368); owner question open |
| N1 | pass (CAPEX_GATE4_FULL=1) |

## 14. Addendum from the duplicate G4-6b run (takeover at 04:24Z; the original run finished first)
- **Finding on the R4-NX ablation (for G4-7):** `tx.dc_links: exclude`, window p063-p067, local 2-cpu run: health 30 pass / **1 fail, `price_setter.loop_alpha` 2.4e-3 vs tolerance 1e-6** (`max(|Σα − 1|, |π − Σα c|)` over CONGESTION_LOOP rows). R4-N (controllable DC1) passes all 31. gate-4.md §5 does not judge R4-NX, so no gate criterion fails, but it is a health fail on a supported switch value. No threshold changed. Single run, not yet reproduced by a second verifier.
- **`rts_gmlc_px` full-year price-setter shares** (local re-run, 245 s wall, 2.3 GB, 23/23 health pass, UNEXPLAINED 0 of 26,352 zone-hours): all MARGINAL_UNIT; by fuel coal 52.3%, gas 39.8%, nuclear 3.5%, none 4.4%. Complements §10 (full-fleet `rts_gmlc`).
