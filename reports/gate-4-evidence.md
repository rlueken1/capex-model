# Gate 4 evidence: RTS-GMLC fixed-fleet dispatch vs the PLEXOS reference

Item G4-6a (verifier, 2026-11-28; window runs). Criteria: `docs/gates/gate-4.md` sections 2, 5, 6, 9. Parts for R4-F / R4-NF, ledger rows and CI links are **G4-6b placeholders** (sections 9 to 12 below).
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
Not re-run as part of G4-6a other than as part of the full suite (800 pass); expected vs obtained tables belong to G4-6b (placeholder). Status in the suite: H1a-e, S2a, A1, U1 pass; S2c passes through the forced route (section 8); **S2b xfail**; B1, N1 skipped without `CAPEX_GATE4_FULL=1`.
Not independently re-derived here; `reports/gate-3-evidence.md` style tables to be added by G4-6b. [G4-6b PLACEHOLDER]

## 8. Mutations M13-M16 and the case-(c) fixture
- M14, M15: pass (suite). M13 (S2 inequality sign flipped), M16 (UNBOUNDED_OR_INFEASIBLE mapped to NaN) and S2c (stub status): **now pass, through a forced interval-LP route.** `g4lib.force_interval` patches `capex.audit.loop.classify` to return `INTERVAL` so the interval LP runs on every congested hour. Reason: price-setter case (c) needs a degenerate dual vertex; the simplex vertex that HiGHS returns always has the cost-matching units (including units at a bound whose bus price equals their cost, `TIE_AT_BOUND`) as rows, so rows >= columns. About 300 pjm5 and chain variants (ratings set to the exact unconstrained flows, generator caps equal to dispatch, with/without storage, radial chains: 150 random variants in G4-6a plus the ~150 of G4-4v) gave no case-(c) hour; IPM without crossover gives no basis and the audit skips the price-setter report.
  Mutation tests assert their vacuity guards (calls > 0, mutated > 0) and pass. What the forced route proves: the status map (+-inf, no NaN), `loop_interval` firing on a flipped row and on a NaN side. What it does not prove: that a naturally arising case-(c) hour gets the right interval.
- **S2b remains strict xfail** (test text unchanged, reason updated): with the interval path forced on a case-(a) hour the equality rows pin the point, so the S2 storage rows cannot bite, and S2b's own vacuity guard (storage rows must tighten the interval) cannot be met. Closing it needs a fixture with a degenerate dual vertex that HiGHS actually returns, or a unit-level test of `capex.audit.loop.interval` against `g4lib.analyse` on a hand-built rank-deficient system (a test of a code unit, no run). Owner/G4-8 decision whether Gate 4 needs the second; no code finding.

## 9. Full-year R4-F / R4-NF, B1, N1 [G4-6b PLACEHOLDER]
## 10. Price-setter class/fuel shares for R4-F [G4-6b PLACEHOLDER] (window shares are in section 6)
## 11. A1-A10 checklist for `tx.dc_links`, ledger rows, CI run links, assumptions-book excerpts [G4-6b / G4-7 PLACEHOLDER]

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
| Window solve time <= 60 s [P] | pass (max 33.1 s) |
