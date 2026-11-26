# Gate 1 review

Branch `gate-1`, commit under test `a3182e4`. Criteria: `docs/gates/gate-1.md` (frozen). Evidence: `reports/gate-1-evidence.md`
(sections referenced as E1-E8). Full local run: 428 passed, 0 failed (28 s); CI #32 green (428 passed, 21 s).

## Verifier pass/fail table
PASS = covered by passing judging tests (not builder smoke tests) and/or reproduced output. No row failed.

| # | Criterion (gate-1.md) | Evidence | Result |
|---|---|---|---|
| 1 | Scope: toy LP, HiGHS adapter (simplex), scaling, audit hooks, econ, load validation, assumptions-book stub | E1, E8; cases T1-T4 run end to end via CLI | PASS |
| 1b | Builder does not write judging tests; smoke tests not evidence | E1 (13 smoke excluded); E8 notes smoke tests import `tests/healthlib.py` | PASS (with note) |
| 2 T1 | x 120/30, Z 40.824 M$, block prices 20/20.822/121.096, sum w*D*pi = Z, hourly intervals, R = C^fix | `test_known_answers.py::test_t1`; E2 | PASS |
| 2 T2a | charge 44.44, discharge 36, prices 20/60, v 22.22/54, R^E 3866.30, Z | `::test_t2a`; E2 | PASS |
| 2 T2b | build 10 MW/40 MWh at xP_ub, xE_ub; excess rent 3465.19; Z | `::test_t2b`; E2 | PASS |
| 2 T2c | x=0, Z = 26,280,000, rent in [15,465.19, 20,000] | `::test_t2c`, `test_health_checks.py::test_t2c_combined_rent_inside_degenerate_interval`; E2 | PASS (interval per DECISIONS 31d) |
| 2 T3a | x=0, u_48=20, pi_48=1000, G rent, Peaker reduced cost 40,500, Z | `::test_t3a`; E2 | PASS |
| 2 T3b | x=20, pi_48=921.92, Z | `::test_t3b`; E2 | PASS |
| 2 T4 | f=50 at ub, pi 20/50, mu 30, congestion rent 13.14 M, Z 39.42 M, islands | `::test_t4`; E2 | PASS |
| 2 | Price-setter report per case (class columns of §2) | `test_health_checks.py::test_price_setter_*`; E4 | PASS |
| 2 | 50 random instances pass all checks and match `linprog(highs)` at rel 1e-7 | `test_health_random.py` (172 tests); E6 | PASS |
| 3 | Balance residual <= 1e-6 MW | `test_balance_residual`; max 3.4e-13 on T1-T4 (E3) | PASS |
| 3 | Dual-sign adapter on 2-var LP; broken adapters rejected | `test_adapter_dual_signs_and_values`, `test_broken_adapter_rejects_run` | PASS |
| 3 | Strong duality <= 1e-7 | `test_strong_duality`; max 2.7e-16 | PASS |
| 3 | Complementary slackness <= 1e-8, dual signs | `test_complementary_slackness_and_signs`; CS = 0 on T1-T4 | PASS |
| 3 | Zero-profit / revenue identity / storage reduced costs | `test_zero_profit_revenue_identity_storage_reduced_costs`; E2 rents | PASS |
| 3 | Dual unscaling (scaled vs unscaled; T2c and random limited to primal, pi, generator rho) | `test_dual_unscaling_primal_and_prices` | PASS (exception per DECISIONS 31d) |
| 3 | SOC-row recomputation <= 1e-6 MWh, cyclic wrap | `test_storage_soc_consistency_recomputed_from_case_data`, `test_soc_recompute_check_*`; T2a 1.6e-14 | PASS |
| 3 | Objective decomposition <= 1e-9 rel | `test_objective_decomposition`; max 1.8e-16 | PASS |
| 3 | Binding-constraint report equals expected set per case | `test_binding_report_t1..t4`; E3 | PASS |
| 3 | Price-setter: UNEXPLAINED = 0, price vs setter cost, shares sum to 1, non-basic rejected | `test_price_setter_*`, `test_non_basic_solution_rejected`, `test_ipm_with_crossover_is_accepted` | PASS |
| 3 | Conditioning: report each solve; T1-T4 no warn/fail; ratio>1e9 fixture fails and invalidates run; thresholds per §6.2 | `test_conditioning_*`, `test_conditioning_fail_marks_fingerprint_invalid` | PASS |
| 3 | Fingerprint determinism (3 runs, 2 processes, perturbations, invalidation) | `test_health_fingerprint.py` (14); E5 (7 cases x 2 CLI runs, identical) | PASS |
| 3 | Load validation: weight sum, w<1, dollar year, dt != 1 | `test_load_validation.py` (14) | PASS |
| 3 | econ: CRF 0.09439, r=0 branch, |r|<1e-9, invalid raises, ANN >= I/n, Fisher, deflation, static scan | `test_econ.py` (57) | PASS |
| 3 | Audit mutations M1-M6 each caught (M4 with eta_c != eta_d, by `storage.soc_recompute`) | `test_health_mutations.py` (16); E6 | PASS |
| 4 | Spec assumptions 1-5 applied; amendment 1 (a)-(d) | E7; DECISIONS 30, 31; tests assert amended spec | PASS (owner confirms, item 5) |
| 5(1) | pytest log + junit with counts and versions | `reports/gate-1-pytest.log`, `gate-1-junit.xml`; E1 | PASS |
| 5(2) | T1-T4 expected vs obtained with margins | E2 | PASS |
| 5(3) | One health-report excerpt per case | E3 | PASS |
| 5(4) | Price-setter class table | E4 | PASS |
| 5(5) | Fingerprint determinism log | E5 | PASS |
| 5(6) | Mutation results | E6 | PASS |
| 5(7) | Spec changes with DECISIONS numbers | E7 | PASS |
| 5(8) | Known limitations | E8 | PASS |
| 6 | Verifier writes tests and per-row pass/fail | this table | PASS |
| 6 | Formulation trace, markets, consulting reviews; owner decision list | sections below | N-A (pending W5/W6) |
| README 3 | Scoreboard no-regression | starts Gate 5 per README | N-A |
| README 4 | Complexity ledger, ablation switches | starts Gate 5 per README | N-A |
| README 1 | CI runs | CI #32 green; gate-1.md header accepts local log | PASS |

Failures: none. Open notes for reviewers (not failures): hourly degeneracy and T2c duals (DECISIONS 30, 31), fingerprint is
environment-bound (local vs CI hashes differ), builder smoke tests import a verifier helper, E8 has the full list.

## Formulation trace (W5)
Formulation lead, 2026-11-25. Spec F-0.2 amendment 1 vs `src/capex/` at `a3182e4`. I read every module once and re-solved
T1-T4 with HiGHS 1.16.0 (stationarity $|c-A^\top y-s|_\infty \le 5.3\times10^{-15}$ scaled on every case, all health checks
pass, no explicit zeros in A). Paths below are relative to `src/capex/`; `audit/` holds `capex.audit`.

**(1) Trace table**

| Spec ref | Code location | Match | Note |
|---|---|---|---|
| §1.1 Δt=1 asserted | `data.py:read_manifest` l.152 | yes | `dt_h != 1` is a load error |
| §1.2 weight identity 1e-9, $w_p\ge1$ | `data.py:check_periods` l.210-220 | yes | also checks days = 3w |
| **§2** data rule existing xor candidate | `data.py:_check_resource_row` l.279-282 | yes | |
| §2.1 cols `x xP xE g ch dis soc flow use`, bounds | `model.py:_layouts` l.86-95, `_col_bounds` l.168-177 | yes | `flow` in $[-F^-,F^+]$, `use` in $[0,D]$; xmax inf allowed, finite ≥1e6 rejected (`data.py` l.267) |
| §2.1 bound labels | `audit/duals.py:BOUND_FAMILIES` l.13 | yes | raw dual = $\min(s,0)$ on ub, $\max(s,0)$ on lb |
| §2.1 curtailment reported, not a variable | `run.py:_dispatch` l.35, `audit/economics.py:curtailment_unserved` l.155 | yes | |
| §2.2 `bal` | `model.py:_matrix` l.124-129, `_row_bounds` l.184-185 | yes | equality, RHS = D |
| §2.2 `gen_max` $g-Ax\le AK^0$ | l.131-132, l.186 | yes | rows for existing units too, as spec says |
| §2.2 `st_pwr`, `st_emax` | l.134-136, 143-144, 187-189 | yes | |
| §2.2 `st_soc`, cyclic $t^-$ | l.138-141 (`t_prev=(t-1)%T`), l.188 | yes | coefficients $1,-(1-\sigma),-\eta^c,1/\eta^d$ |
| §2.2 `st_dur_lo/hi`, candidates only, omitted if absent | `model.py:build_lp` l.198-200, l.146-149, l.190-191 | yes | |
| §2.2 `simul_chdis` reported, not an error | `audit/economics.py:storage_report` l.129; `audit/report.py` `_info` | yes | |
| §2.3 $Z^{inv}+Z^{var}+Z^{use}$ | `model.py:_costs` l.154-165 | yes | storage VOM on `dis`; MC = HR·φ + VOM or override (`data.py:build_gen` l.420-426) |
| §2.3 $Z^0$ outside LP and duality, in total | `audit/solved.py:z0, z_lp, z_total` l.55-65; `audit/duality.py` | yes | `fom0` = FOM·K0, FOM^P·P0 + FOM^E·E0 |
| **§3** unscaling $y=S\tilde y$ | `audit/solved.py:y, s` l.27-32; `config.py:Scaling.dual_factor` | yes | $S=k_P/(k_C s_{obj})$ |
| §3 table conversions π, ρ, ρ^P, ρ^E, v, μ, μ^use | `audit/duals.py:economic_duals` l.29-34 | yes | μ is signed $\pi_e-\pi_o$ (negative on `flow_lb`), consistent with the table |
| §3 $R_r=\sum w A\rho$; $R^P,R^E$ | `audit/economics.py:gen_rents` l.49, `storage_rents` l.69 | yes | uses case $A$, not matrix |
| check 1 `bal` residual from case D, unscaled MW | `audit/duals.py:balance_residuals` l.37 | yes | ≤1e-6 in `report.py` |
| check 2 strong duality, excl. $Z^0$ | `audit/duality.py:duality_report` l.32 | yes | scaled, rel. to $\max(1,|\tilde Z|)$ |
| check 3 CS rows and bounds | same | yes | normalised by $\max(1,|\tilde Z|)$, tol per gate-1.md |
| check 4 dual signs | `audit/duality.py:_active_side` l.22 | yes | generic form: a dual may only price a finite bound; equivalent to the table |
| check 5 zero-profit; storage s_xP, s_xE recomputed | `audit/economics.py:_zero_profit_ok`, `storage_reduced_cost_residual` l.101 | yes* | *free-duration storage: see F4 |
| check 6 revenue identity (gen and storage) | `gen_rents`, `storage_rents` (`revenue_identity_residual`) | yes | uses case $K,P,E$, so it also catches a wrong capacity RHS whenever that row binds |
| check 7 degeneracy policy | tests only (DECISIONS 30, 31d) | yes | not a code check, by design |
| check 8 `storage.soc_recompute` from case η, σ | `audit/economics.py:soc_recompute_residual` l.144 | yes | ≤1e-6 MWh; closure check also present |
| **§4** basis required, simplex dual, presolve off | `solver.py:DEFAULT_HIGHS_OPTIONS` l.16, l.85; `audit/pricesetter.py:price_setter` l.236 | yes | no basis means the price-setter is skipped and the health check fails |
| §4 $tol_q$, $tol_\pi$ | `pricesetter.py:_classes` l.91, `price_setter` l.240 | yes | $tol_q$ on $K$, not $AK$ (as spec) |
| §4 Step 0 islands, `LINK_INCONSISTENT` | `_link_state` l.58, `_components` l.46 | yes | at-bound test uses case NTC |
| §4 Step 1 class order and conditions | `_classes` l.109-130, `CLASS_ORDER` | yes | all matches go to `all_classes`; primary = first match |
| §4 `CAPACITY_RENT` interval, `INVESTMENT_MARGIN`/`DEGENERATE` | l.117-123, `record` l.202-207 | yes | generators only (F7) |
| §4 Step 2 `UNEXPLAINED` | `price_setter` l.247; `report.py` check | partial | count correct; label/summary wrong (F1) |
| §4 Outputs setter_cost/residual per class (DECISIONS 31b) | `record` l.196-219, `_storage_costs` l.177 | yes | DIS $VOM+v/\eta^d$, CH $\eta^c v$, CR $\max MC_{cap}$, BLACKOUT VOLL; the π−VOM bug is fixed |
| §4 shares by $\sum w_p$, ties split | `_summary` l.257, `record` l.228-230 | yes | |
| **§5.1** single deflator, real rates, Fisher | `econ.py:deflator_factor, to_base_dollars, fisher_real_rate`; `data.py:_factors, finance_params` | yes | VOLL and fuel prices deflated too |
| §5.2 CRF, r=0 / $|r|<10^{-9}$, κ, ATB PFF, FOM after ANN | `econ.py:crf, idc_factor, atb_pff, annualize`; `data.py:_annualize_part` | yes* | *ANN ≥ I/n only checked when PFF ≥ 1 (F6) |
| **§6.1** $\tilde c = c\,k_C s_{obj}/k_P$, RHS and bounds × $k_P$, matrix unscaled | `model.py:build_lp` l.204-206; `config.py:Scaling` | yes | every coefficient is a ratio (MW/MW, MWh/MW = h), so A needs no scaling |
| §6.1 rules a-e | weights only in `_costs`; `data.py:build_availability` l.404-405 (zeroed, counted in assumptions book); sentinel check; VOLL only in c | yes | |
| §6.2 conditioning metrics, warn/fail, fail invalidates fingerprint | `audit/conditioning.py:conditioning_report` l.58, `THRESHOLDS` l.15; `run.py:fingerprint_of` | yes* | *two spec ambiguities resolved in code (F2) |

**(2) Dual conventions: correct.** `HighsSolver` passes `row_dual`/`col_dual` through unchanged. HiGHS minimisation duals are
§1.3's $y=\partial Z^*/\partial b$, and every solve confirms this with the stationarity residual (`dual_infeasibility`, ~1e-15)
plus the 2-variable adapter tests. `ScipyHighsSolver` maps `linprog` marginals correctly (≥ rows negated, l.110) except for
ranged rows (F5). Unscaling by $S$ is uniform for rows and columns. Every §3 stationarity relation re-derives from the
assembled coefficients, including the storage $s_{xP}$, $s_{xE}$ formulas. CS and sign checks are applied in scaled units
over all rows and finite bounds.

**(3) Price-setter logic: correct for Gate 1 scope.** Class order, conditions and price checks match §4. The CAPACITY_RENT
interval is $[\max MC_{cap},\ \min(\text{VOLL}, \min MC_{room})]$, and the violator test is "no unit with room below π".
Setter cost and residual follow the per-class rule of DECISIONS 31b: on the toys the residual is 0 for MARGINAL_UNIT, TIE and
VOLL, and it equals the scarcity rent for CAPACITY_RENT (T1 493.15, T3b 821.92 $/MWh). One reporting defect (F1).

**(4) Findings**
- **F1** should-fix before Gate 1 sign-off · code bug + test gap. If the first matched class fails its price check, the
  hour is counted UNEXPLAINED (the health check is right) but keeps `primary_class` = that class (`pricesetter.py:record`
  l.191). Its weighted hours also go into `price_setter_summary` under that class, which the IMM shares later read.
  `test_known_answers.py:109` asserts on `primary_class` and so cannot see this. No Gate 1 case triggers it.
- **F2** should-fix before sign-off · spec gap. §6.2 says infeasibility is "unscaled" in the text but "(scaled)" in the
  table. Its row "RHS ratio / any finite bound" is also ambiguous. The code chose scaled infeasibility and an absolute
  threshold on scaled bounds (`conditioning.py` l.13 `SPEC-AMBIGUITY`). Ratify that reading in §6.2 plus a DECISIONS entry;
  no code change.
- **F3** later-gate (Gate 2/3, first VRE profiles) · code bug. `_triplets` keeps explicit zeros when $A_{r,p,t}=0$
  (`gen_max` x-coefficient, `model.py` l.132). These inflate `nnz` and `tiny_coefficients`. Invisible in Gate 1, where A=1.
  Fix: `eliminate_zeros()`.
- **F4** later-gate · code + test gap. For candidate storage without a fixed duration, zero-profit checks only the sign of
  the solver's $s_{xP}$, with build status taken from xP alone (`economics.py` l.78, l.94). $s_{xE}$ is not checked.
  Recomputation equality still holds. No Gate 1 case has a free duration.
- **F5** later-gate · code bug. In `ScipyHighsSolver`, a ranged row (finite lo < hi) lands in both `le` and `ge`, so the ≤
  dual is overwritten (`solver.py` l.107-110). Gate 1 has no ranged rows.
- **F6** note · spec gap. §5.2 "ANN ≥ I/n for r ≥ 0" is false for an assumed PFF < 1, and the code skips the check in that
  case (`econ.py` l.117). Amend the wording at the next spec touch.
- **F7** note · spec gap (Gate 5/7). Storage at its `st_pwr`/`st_emax` bound, and candidates at x=0, never act as
  TIE_AT_BOUND or CAPACITY_RENT setters. This is fine while storage is small; revisit with inter-period storage and ORDC.
- **F8** note · data validation (Gate 5). σ is not range-checked. φ is accepted as an hourly grid with no check that it is
  constant within each day (§1.4). Harmless under DECISIONS 29 (one fuel price per case).
- **F9** note · no action. Apart from `bal` and `st_soc`, no row is recomputed from case data. A wrong capacity or NTC
  coefficient is still caught when the row binds, by the revenue identity (case $K,P,E$) or `LINK_INCONSISTENT` (case NTC).
  When the row is slack, the solution does not change.

**(5) Verdict: yes.** The code implements F-0.2 (amendment 1) for the Gate 1 toy scope. No blockers. F1 (code) and F2
(spec wording) are small and should close before sign-off; F3-F9 are deferred or notes.

## Markets and consulting review (W6)
_Placeholder: markets reviewer (economic sense of T1-T4) and consulting reviewer (audit and assumptions-book readability)._

## Owner decision list (W6)
_Placeholder: PM writes the 7 items required by gate-1.md §6, format `N. <question>? **Recommendation: yes/no** - evidence: <link>. If no: <consequence>.`_
