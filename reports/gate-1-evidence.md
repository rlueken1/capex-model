# Gate 1 evidence (W4c, verifier)

Commit under test: `a3182e4` (branch `gate-1`), clean tree at run time (`dirty_diff_hash` = SHA-256 of empty string).
Formulation F-0.2 + amendment 1 (DECISIONS 31). Criteria: `docs/gates/gate-1.md` (§5 numbering below).
Verifier did not edit `src/capex/`, any test, or any tolerance.

## 1. Command, log, versions, counts
Command (run by verifier): `pytest -v --durations=10 --junitxml=reports/gate-1-junit.xml | tee reports/gate-1-pytest.log`
Artifacts: `reports/gate-1-pytest.log` (40 KB), `reports/gate-1-junit.xml` (49 KB).

| Run | Result | Time | Environment |
|---|---|---|---|
| Local (this session, 3 runs) | **428 passed, 0 failed, 0 skipped, 0 xfail** | 28.2 / 28.8 / 29.2 s | Linux 6.18.44, Python 3.13.18, numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, highspy 1.16.0 (HiGHS 1.16.0, git f3f113d) |
| CI run #32 (id 45743468520), commit a3182e4 | **428 passed**, conclusion success | 21.33 s | ubuntu-latest, Python 3.12.16, numpy 2.5.5, scipy 1.18.1, highspy 1.16.0, pandas 3.1.1 |

Prior red CI runs (history, not current): #22 = M4 mutation uncaught by design, closed by DECISIONS 31 (new
`storage.soc_recompute`); #30 = test-helper bug (inf x noise in CS helper), fixed in #31; #18 = numpy-version
index-dtype bug (W4a-fix). Passing on two Python/numpy/pandas stacks is additional evidence beyond what gate-1.md
required (it accepted a local log in place of CI).

Counts by file: test_health_random 172, test_health_checks 132, test_econ 57, test_health_mutations 16,
test_health_fingerprint 14, test_load_validation 14, test_known_answers 10, tests/builder/test_smoke 13 (builder smoke,
**not counted as evidence** per gate-1.md §1). Judging tests = 415 of 428.
Slowest: random-mix coverage 6.44 s; two-process fingerprint tests 1.6-1.8 s each; all others < 0.8 s.

## 2. T1-T4 expected vs obtained
Obtained values are from `python -m capex run cases/<T>` (HiGHS dual simplex, presolve off). Expected values are
closed forms computed inside `tests/test_known_answers.py` (`test_t1`, `test_t2a/b/c`, `test_t3a/b`, `test_t4` plus
`*_closed_form_sanity`), asserted at the gate-1.md §2 tolerances (obj/cap/rent rel 1e-6; block prices rel 1e-5;
unique hourly prices abs 1e-4). All 10 tests pass. "Margin" = how far inside tolerance the obtained value sits (my
recomputation against the spec's rounded numbers; exact closed forms are in the tests).

| Case | Quantity | Expected | Obtained | Margin |
|---|---|---|---|---|
| T1 | x_Base / x_Peak / u | 120 / 30 / 0 | 120.0 / 30.0 / 0 | exact |
| T1 | Z | 40.824 M$ | 40,824,000.000000 | exact (strong-duality gap 1.7e-16) |
| T1 | block prices off/mid/peak | 20 / 20.822 / 121.096 | 20.0000 / 20.8219 / 121.0959 | < 1e-5 rel (spec values rounded at 3 dp) |
| T1 | sum w*D*pi vs Z | = Z | 40,824,000.000000 | rel < 1e-15 |
| T1 | hourly mid / peak pi | in [20,80] / >=80 | mid 20..39.73; peak 80..573.15 | inside intervals |
| T1 | rents R vs C^fix | equal | base 150,000 = 150,000; peaker 60,000 = 60,000 /MW-yr | abs < 1e-9 |
| T2a | charge / discharge per period | 44.44 / 36 MWh | 44.444 / 36.000 | exact |
| T2a | prices; v | 20/60; 22.22/54 | 20.0/60.0; 22.222/54.0 | exact |
| T2a | R^E, R^P, Z | 3866.30, 0, 26,125,348.15 | 3866.2963, 0, 26,125,348.148148 | rel < 1e-7 |
| T2b | build; Z | 10 MW/40 MWh; 26,245,348.15 | 10.0/40.0; 26,245,348.148148 | exact |
| T2b | excess rent | 3465.19 | 3465.1852 | rel < 1e-7 |
| T2c | x; Z | 0; 26,280,000 | 0; 26,280,000.0 | exact |
| T2c | R^P+4R^E | in [15,465.19, 20,000] | 17,520 (R^E 4380, R^P 0 -> 4*4380) | inside interval (lower bound is a tested assertion) |
| T3a | x; u_48; pi_48 | 0; 20; 1000 | 0; at hour 48 only; 1000.0 | exact |
| T3a | G rent; Peaker red. cost; Z | 118,016.67; 40,500; 23,530,333.33 | 118,016.6667; 40,500.0; 23,530,333.333333 | rel < 1e-9 |
| T3b | x; pi_48; Z | 20; 921.92; 23,340,333.33 | 20.0; 921.9178; 23,340,333.333333 | pi: abs < 1e-4 vs closed form |
| T4 | f; pi_A, pi_B | 50 at ub; 20, 50 | 50.0 (72/72 hours); 20.0, 50.0 | exact |
| T4 | mu; congestion rent; Z | 30; 13,140,000; 39,420,000 | 30.0; 13,140,000 (=108,000 $/h x 121.667 h); 39,420,000.0 | exact |

Gap noted: expected numbers in this table are the spec's; the tests, not this table, hold the tolerance
assertions. "Margin" is informational.

## 3. Health-report excerpts (one per case)
All seven cases: Overall **pass**; 23 checks per report (`health_report.md`), 0 warn, 0 fail. Key values:

| Case | balance max (MW) | strong-duality rel gap | CS | decomposition rel | binding families (n rows) | UNEXPLAINED | conditioning (matrix ratio / obj / rhs / bound) |
|---|---|---|---|---|---|---|---|
| T1 | 0 | 1.7e-16 | 0 | 1.8e-16 | bal 72, gen_max 48 | 0 | 1 / 500 / 1.875 / 0.15 |
| T2a | 3.4e-13 | 2.7e-16 | 0 | 0 | bal 72, gen_max 36, st_pwr 7, st_soc 72, st_emax 1 | 0 | 1.23 / 500 / 20 / 0.15 |
| T2b | 2.8e-14 | 0 | 0 | 0 | + st_dur_lo 1, st_dur_hi 1, **xP_ub 1, xE_ub 1** (bounds: bat xP, xE) | 0 | 4.4 / 500 / 4 / 0.15 |
| T2c | 2.8e-14 | 1.4e-16 | 0 | 1.4e-16 | bal 72, gen_max 36, st_pwr 72, st_soc 72, st_emax 72, st_dur_lo/hi 1 | 0 | 4.4 / 500 / 4 / 0.15 |
| T3a | 1.4e-14 | 0 | 0 | 0 | bal 72, gen_max 73 (incl. hour-48 VOLL) | 0 | 1 / 41.1 / 1.5 / 0.12 |
| T3b | 1.4e-14 | 1.5e-16 | 0 | 0 | bal 72, gen_max 2 | 0 | 1 / 33.3 / 1.5 / 0.12 |
| T4 | 1.4e-14 | 1.8e-16 | 0 | 0 | bal 144, **flow_ub 72** (link ab, every hour) | 0 | 1 / 500 / 20 / 0.10 |

Verbatim T1 and T2a tables were printed by the CLI; the other cases print the same 23 rows, all `pass`.
Other checks present and passing on every case: `solver.optimal`, `dual_sign`, `zero_profit`, `revenue_identity`,
`storage_reduced_costs`, `storage.closure`, `storage.soc_recompute` (T2a residual 1.6e-14 MWh vs 1e-6 tol),
`basis_valid`, `price_setter.link_inconsistent` (0), `price_setter.shares_sum_to_one`. Conditioning: no warn or fail on
T1-T4 (matrix ratio <= 1.23 vs warn 1e6). Proved by `test_health_checks.py` (balance, strong duality, CS + signs,
zero-profit/revenue identity, decomposition, binding_report_t1..t4, conditioning_*) at the §3 tolerances.
Raw outputs per run: `annualization.csv assumptions.md binding.csv capacity.csv conditioning.json dispatch.csv
health_report.md objective.csv price_setter.csv price_setter_summary.csv rents.csv run.json ...` (kept in scratchpad,
not committed).

## 4. Price-setter class table (weighted hours, 8760 h per case)
| Case | MARGINAL_UNIT | CAPACITY_RENT | TIE_AT_BOUND | VOLL | UNEXPLAINED |
|---|---|---|---|---|---|
| T1 | 4380.0 (off-peak, Base, 50%) | 243.3 | 4136.7 | 0 | 0 |
| T2a | 8760.0 (G1/G2; storage ties recorded in `all_classes`) | 0 | 0 | 0 | 0 |
| T2b | 8760.0 | 0 | 0 | 0 | 0 |
| T2c | 8760.0 | 0 | 0 | 0 | 0 |
| T3a | 8638.3 | 0 | 0 | 121.7 (hour 48, pi = VOLL 1000) | 0 |
| T3b | 8638.3 | 121.7 (hour 48, pi 921.92) | 0 | 0 | 0 |
| T4 | 17,520 (2 zones x 8760: G_A in A, G_B in B) | 0 | 0 | 0 | 0 |

T1 mid and peak hours land in CAPACITY_RENT or TIE_AT_BOUND, as allowed by DECISIONS 30. Marginal-fuel shares sum
to 1 per zone (9 cases in `test_price_setter_shares_sum_to_one`; known answers in
`test_price_setter_marginal_fuel_shares_known_answers`). Storage setter cost/residual per §4 (VOM + v/eta_d;
eta_c * v) in `test_storage_setter_cost_and_residual_columns_consistent_with_section_4`; ties in
`test_storage_tie_s1/s2`. T4 binding link is listed (`binding_links`, `price_setter.link_inconsistent` = 0).

## 5. Fingerprint determinism log
Each case run twice via the CLI in separate processes (`python -I`), `PYTHONHASHSEED` 1 vs 7. SHA-256 fingerprint
identical in all 7 pairs; every output file byte-identical except `run.json` (differs only in `run_id`,
`timestamp`, `solve_time_s`, which are excluded from the fingerprint by design). Solve time per case about 0.75-0.9 s
wall including interpreter start (HiGHS itself < 1 ms; reported, not gated).

| Case | Fingerprint (SHA-256, commit a3182e4, clean tree) |
|---|---|
| T1 | 60ab07b4e09d815f3c209af0560b6dca837ba587b3a8da9fc23940c6af47395d |
| T2a | a066ccc5eb10c9684c2ea3c03065a47b8c0bba815b3d5a60c6c71a39b745c5dd |
| T2b | 03f40428c74dccc02af2c344c215a5d3551d3766699edc23f398c6ba87ced78e |
| T2c | 216298dc1bd91860ed655f37467a632f49adf6c6cc322a11e15ff3ec924a50ac |
| T3a | 4010a03f0f6877bed6702745ed682474de1f1daaf6d4393d26ffd88c637c3520 |
| T3b | 8e96ee97a3d1468a1d1495da74c27d008b708a622018b587c3ecdbbeb3098ec7 |
| T4 | 3476ea75cffa18bed7dcafce5e97c3dcf5f3b46dc1325bb07610f96131e32eec |

Tests (`tests/test_health_fingerprint.py`, 14, all pass): 3 runs identical hash and bytes; two processes with
different hash seeds (T1, T2b, T4); 1e-12 float perturbation, switch, solver option, formulation version, git commit
and dirty-tree diff each change the hash; package/Python versions recorded; conditioning `fail` marks the fingerprint
invalid, `warn` keeps it valid. Note: `run.json` records `packages` and `python`, so fingerprints are
environment-specific (the CI fingerprints differ from the table above; not compared). The table above is only valid
for this local stack.

## 6. Mutation-test results (`tests/test_health_mutations.py`, 16 tests, all pass)
Each mutation has a no-fault control (must pass) and a vacuity guard.
| Mutation | Tests | Caught by |
|---|---|---|
| M1 flip dual sign in adapter | 3 (gen_max, bal rows; a column dual) | dual-sign adapter / CS & sign checks (asserted among expected set) |
| M2 drop one `bal` row (T1, T4) | 2 | `balance` or `conditioning.bal_residual_mw` |
| M3 scale one cost by 1.001 (3 targets) | 3 | one of decomposition, revenue_identity, zero_profit, price_setter.unexplained |
| M4 swap eta_c/eta_d in `st_soc` (eta_c != eta_d; S2asym, T2asym) | 4 | `storage.soc_recompute` (added by DECISIONS 31); independent recomputation test also passes |
| M5 wrong weight on one period | 3 | model-level: one of decomposition/revenue/price-setter/zero-profit; input-level: rejected at load |
| M6 IPM without crossover | 1 | `basis_valid` / `price_setter.basis` |
Result: 6/6 faults caught. M4 was the one gate-1 finding (uncaught in CI #22); it is closed by a spec-level check,
not by any tolerance change. Also covered: `test_soc_recompute_check_fails_when_eta_swapped_in_lp`,
`..._sigma_ignored_in_lp`, `..._passes_on_correct_storage_solves`.

Other §2/§3 tests in the run: 50 seeded random instances x (all health checks, objective vs `scipy linprog(highs)`
at rel 1e-7, mix coverage of 1-3 zones / 1-3 periods / thermal+VRE+storage+links) = 172 tests in
`test_health_random.py`; dual-sign adapter (10) and broken-adapter rejection (4); dual unscaling (7);
load validation (14); econ (57, incl. static scan for annuity math outside `capex/econ.py`).

## 7. Spec changes in the gate and DECISIONS numbers
| Change | DECISIONS | Where |
|---|---|---|
| Gate 1 built on F-0.2: daily fuel price, ATB-style PFF default, etc. | 22-25 (Gate 0) | formulation F-0.2 |
| T1 price-setter classes: mid/peak hours CAPACITY_RENT or TIE_AT_BOUND; block averages exact | 30 (item 14) | gate-1.md §2 T1 row, formulation §4 |
| Amendment 1: new `storage.soc_recompute` check (§3 check 8, §8.6) | 31(a) | formulation, gate-1.md §3 |
| STORAGE_DIS/CH `setter_cost`/`residual` per class (code residual was a bug) | 31(b) | formulation §4 Outputs; code fix W4b-fix2 |
| `fuel` optional for VRE (and ST); MC = 0 without `mc_override` | 31(c) | data-schema §3.3 |
| T2c dual degeneracy at x=0: test primal/pi/generator rho, rent in interval of §10 | 31(d) | gate-1.md §2, §3 |
No tolerance was changed. The owner confirms amendment 1 at review item 5 (gate-1.md §6).

## 8. Known limitations and open gaps
- **Hourly price degeneracy.** Within T1 mid/peak blocks the hourly pi is any value in the allowed interval (observed
  peak max 573.15 vs floor 80); only block averages and intervals are asserted. HiGHS picks a vertex; a different
  solver version may pick another, with the same block averages.
- **T2c degenerate duals (DECISIONS 31d).** v, rho^P, rho^E of zero-capacity storage are not unique and are not
  compared across scalings; T2c asserts rent in [15,465.19, 20,000]. Observed 17,520 is interior, so the interval is
  tested but the lower end is only exercised by the T2a arbitrage value assertion, not by a solver output at x=0.
- **Solver pinned.** highspy 1.16.0 (HiGHS 1.16.0); simplex dual, presolve off, 1 thread, seed 0, crossover on.
  `run.json` shows `crossover_ran: false` (a simplex solve needs none); the IPM-without-crossover path is only
  exercised by M6 and `test_non_basic_solution_rejected`.
- **Fingerprint is environment-bound** (records python and package versions): the same case yields different
  hashes on local and CI stacks. Determinism is claimed within one environment only.
- **Builder smoke tests import `tests/healthlib.py`** (`tests/builder/test_smoke.py` lines 53, 80), a verifier
  helper module, so the builder-verifier separation is not clean at the file level. Smoke tests are excluded from
  evidence (13 of 428), so judging coverage is unaffected.
- **Shared test helper.** Verifier tests, M4 recomputation and random cross-check all use `tests/healthlib.py`
  (`soc_residual`, `linprog_z`, `independent_balance`) written by the verifier from the spec, but it is one code
  path shared by many tests; a bug there (cf. CI #30) can affect many results at once.
- **Per-case tolerance margins** (§2 above) are informational; the asserted values live in the test code.
- **Gate-5+ items N/A at Gate 1.** README items 3 (scoreboard) and 4 (complexity value review, ablation switches,
  `reports/complexity-ledger.md`) start "from Gate 5" per `docs/gates/README.md`; gate-1.md lists neither. Not
  produced, not claimed.
- **Assumptions book** is a stub (annualization table and counts), as scoped by gate-1.md §1; produced per run as
  `assumptions.md` and `annualization.csv`.
- **Deviation accepted in gate-1.md header:** local log in place of CI; CI #32 is green anyway.
- **Gate 0 reviewer-only items** (formulation trace, markets, consulting readability) are W5/W6, not covered here.
