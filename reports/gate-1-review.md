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
_Placeholder: formulation lead fills in (code vs spec §2-§6, dual conventions, price-setter logic)._

## Markets and consulting review (W6)
_Placeholder: markets reviewer (economic sense of T1-T4) and consulting reviewer (audit and assumptions-book readability)._

## Owner decision list (W6)
_Placeholder: PM writes the 7 items required by gate-1.md §6, format `N. <question>? **Recommendation: yes/no** - evidence: <link>. If no: <consequence>.`_
