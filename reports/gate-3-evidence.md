# Gate 3 evidence: PJM 5-bus, DC power flow option

Item G3-5 (verifier, 2026-11-27). Criteria: `docs/gates/gate-3.md` §2-§5 (approved, DECISIONS 47). Format after `reports/gate-2-evidence.md`.
Commit under test: `b82a8b4` (gate-3 head; code = `2563d52`, later commits are PLAN-only). Working tree clean at start (`git status --short` empty).
All numbers below come from commands run in this session (command lines given) or from cited files. Scratch outputs: session scratchpad; the
pytest log is kept as `reports/gate-3-pytest.log`.

**Bottom line.** Local suite 637 passed, 0 failed, 0 skipped, 0 xfail. CI run 150 on `2563d52` is success (4 jobs). P5a-P5f, all section-4 health checks,
M7-M10, K2 pass. `dcpf` reproduces the independent scipy route to ~1e-13 and the published rounded values to 0.0045 $/MWh and 0.0048 MW. Also:
K1 and K3 pass on Actions data-download run 45981948446 (section 10). Seven findings for G3-6/G3-7 in section 12 (none is a failed criterion).

## 1. Environment and test run
- Python 3.13.18, numpy 2.5.3, scipy 1.18.1, pandas 3.0.5, highspy 1.16.0 (HiGHS 1.16.0, git f3f113d), pytest 9.1.1; Linux 6.18.44 x86_64.
  Installed from `requirements-ci.txt` (pins identical to CI). CI uses Python 3.12.16; I ran 3.13 only (limitation 3).
- `pytest -v --disable-socket --durations=10 --junitxml=<scratch>/junit.xml | tee reports/gate-3-pytest.log` -> **637 passed in 49.15 s**, 0 failed/skipped/xfail/error.
  `tests/test_pjm5bus.py`: 103 passed (P5: 16, section-4 health: 13, M7-M10: 6, K2: 3, loader: 8, transport identity: 21, reference route and others).
- `python -I scripts/check_markers.py` -> exit 0 ("all xfail/skip markers carry a DECISIONS/Gate reference"); `python scripts/check_workflows.py` -> ok for `ci.yml`, `data-download.yml`.
- CI: run 150 (id 45974548149, head `2563d52`) conclusion success; jobs `test`, `health-run (0)`, `health-run (12345)`, `compare` all success
  (jobs API; `test` step "Test" 09:32:46-09:33:41Z = 55 s). I did not read the pytest count from the CI log (log tail only returned post-job cleanup).

## 2. Reference data: source hashes and P3 provenance (`pjm5`)
Command: python hashing of `cases/pjm5bus/case.yaml` pins and `cases/raw/pjm5bus/*`; `git show` not needed.
| File | sha256 | bytes |
|---|---|---|
| `cases/raw/pjm5bus/case5.m` | `ed9072089d080debde2aa029ed8a95491c311b08ff4f45ad7bf06882d86fe279` | 1,921 |
| `cases/raw/pjm5bus/LICENSE_MATPOWER` | `5d14c09b3e4f2adf62c0373e6320163697aa4603186f8925c07c6b84201e1750` | 2,074 |
| `cases/raw/pjm5bus/powermodels_case5.m` (cross-check only, unpinned master) | `1415fed30ae24df9d1a56773d3106e0b9dcd0536803f1907bed77b86370e1ee5` | 2,695 |
Both pinned hashes equal `data/manifests/pjm5.csv` and `cases/raw/pjm5bus/MANIFEST.csv`; K2 tests pass (3). All 9 `case.yaml` table sha256 pins equal the files on disk (checked: all True).
Source: F. Li and R. Bo, IEEE PES GM 2010, via MATPOWER `data/case5.m`, MATPOWER commit `b6c85b0323d20fb801cab3377c803a285d730847` (repo HEAD at retrieval 2026-11-26, not the last commit touching the file; `cases/raw/pjm5bus/README.md`).
Provenance: every row `source_id=pjm5`, vintage `matpower-b6c85b0`, retrieved 2026-11-26, method `observed`, confidence `high`; exceptions in `cases/pjm5bus/provenance_cells.csv`
(dollar year 2024 `assumed`/low; blank rating = unlimited `observed`; reactance/base_mva `observed`). P3 verified every gate-3.md §2 input against `case5.m` (table in the raw README; no discrepancies).
**Licence (decision-list item 6):** MATPOWER LICENSE is BSD-3 for code but excludes case files ("included with permission"; `case5.m` says "Distributed with permission"). Scope undocumented -> `license_class=verify`,
internal test use; cite Li & Bo 2010 and MATPOWER (`docs/data-sources.md` pjm5 row). Li & Bo's own paper (generator/bus names) was not fetchable (paywall); names mapped by row order.

## 3. Independent route and P5a (base, `dcpf`, angle, reference bus A)
Independent route: `solve_opf` in `tests/test_pjm5bus.py` (scipy `linprog(method="highs")` from the raw CSVs, no `capex` import). Obtained: `run_case` on `cases/pjm5bus`
(`python -m capex run cases/pjm5bus --out <dir>` gives the same outputs; fingerprint `29d3c09e...` for the CLI run, `5bb79442...` for the test-harness copy, differ; the harness stages a copy under a temp dir, cause not investigated).
Evidence script (not committed): scratchpad `evidence.py`; the rows below are its printed output.

| Quantity | Published/expected | Independent route | Obtained | max abs diff vs independent (tol) | max abs diff vs published (tol) |
|---|---|---|---|---|---|
| LMP A..E ($/MWh) | 16.98 / 26.38 / 30.00 / 39.94 / 10.00 | 16.977359 / 26.384460 / 30.000000 / 39.942736 / 10.000000 | identical to independent | 1.1e-14 (1e-4) | 0.00446 (0.01) |
| Dispatch Alta, Park City, Solitude, Sundance, Brighton (MW) | 40 / 170 / 323.49 / 0 / 466.51 | 40 / 170 / 323.494846 / 0 / 466.505154 | identical | 1.7e-13 (1e-4) | 0.00485 (0.01) |
| Flows ab, ad, ae, bc, cd, de (MW) | de = -240 (E to D) | 249.7168 / 186.7884 / -226.5052 / -50.2832 / -26.7884 / -240 | identical | 1.7e-13 | de: 0 |
| mu_de ($/MWh) | about -62.32 | -62.322042 | -62.322042 | 4e-14 | n/a |
| Hourly cost ($/h) | 17,479.90 | 17,479.896925 | Z/(24*365) = 17,479.896925 | rel 1.9e-16 (1e-7) | |
| Annual Z ($) | 17,479.90 x 24 x 365 | 153,123,897.066338 | 153,123,897.066338 | rel 1.9e-16 (1e-7) | |
| Congestion surplus ($/h) | 14,957.29 | 14,957.2901 (= 62.322042 x 240) | n/a | | |
| Binding lines | only D-E | de | `at_bound` true only for de, 72 of 72 hours | | |
Margins: LMP tolerance used 0.01, obtained 0.0045 (45% of the allowance); dispatch 0.01 MW (DECISIONS 47), obtained 0.0048 (48%). Against the independent route the margin is 10 orders of magnitude.

**Per-bus LMP decomposition (P5a hour 1; reference A, lambda = 16.977359; loss = 0)**
| Bus | LMP | energy lambda | congestion | loss | congestion recomputed -H_{de,n} mu_de (independent PTDF) | LMP - (energy + cong + loss) |
|---|---|---|---|---|---|---|
| A | 16.977359 | 16.977359 | 0.000000 | 0 | 0.000000 | 0 |
| B | 26.384460 | 16.977359 | 9.407101 | 0 | 9.407101 | 1.8e-15 |
| C | 30.000000 | 16.977359 | 13.022641 | 0 | 13.022641 | 0 |
| D | 39.942736 | 16.977359 | 22.965377 | 0 | 22.965377 | -3.6e-15 |
| E | 10.000000 | 16.977359 | -6.977359 | 0 | -6.977359 | 8.9e-16 |

**Price-setter table (P5a, identical every hour; UNEXPLAINED = 0 of 360 bus-hours)**
| Bus | Class | Setter(s) | price | setter cost | residual | alpha (obtained) | alpha (independent, 7.4a.7 case a) |
|---|---|---|---|---|---|---|---|
| A | CONGESTION_LOOP | solitude, brighton | 16.977359 | 16.977359 | 1.8e-14 | 0.348868 / 0.651132 | 0.348868 / 0.651132 |
| B | CONGESTION_LOOP | solitude, brighton | 26.384460 | 26.384460 | 2.5e-14 | 0.819223 / 0.180777 | 0.819223 / 0.180777 |
| C | MARGINAL_UNIT | solitude | 30.000000 | 30.000000 | 3.6e-15 | n/a | n/a |
| D | CONGESTION_LOOP | solitude, brighton | 39.942736 | 39.942736 | 2.8e-14 | 1.497137 / -0.497137 | 1.497137 / -0.497137 |
| E | MARGINAL_UNIT | brighton | 10.000000 | 10.000000 | 3.6e-15 | n/a | n/a |
sum alpha = 1 per bus; max |alpha - independent| = 1.1e-15; binding link `de`; flags `IMPORT,CONGESTED` on loop buses. D's alpha is outside [0,1] (weights are extrapolations; expected with a loop-flow price above the dearest marginal unit; economic reading is for the markets reviewer).
Price-setter shares (weighted hours 8,760): A, B, D 100% CONGESTION_LOOP; C, E 100% MARGINAL_UNIT.

**Health report P5a:** all 30 checks pass (balance 2.0e-13 MW; strong_duality 3.7e-16; kvl.recompute 2.3e-13 (tol 1e-6); ptdf.recompute 1.4e-13; lmp.decomposition 1.4e-14; congestion_rent 3.6e-16 (rel, tol 1e-7);
dcpf.line_duals 0; dcpf.islands 0 ("1 islands: i1 ref A"); price_setter.loop_alpha 2.8e-14; conditioning matrix_ratio 15.6, objective_ratio 1000, rhs_ratio 15, bound_max 0.4; no warn). Binding report: `gen_max` 144/360 rows, `de` flow bound in 72/72 hours.
Run facts (`run.json`): HiGHS simplex (dual, strategy 1), presolve off, crossover on, `crossover_ran=false`, 1,121 iterations, status Optimal.

## 4. P5b to P5f
| Case | Expected | Obtained (max abs unless noted) | Margin | Result |
|---|---|---|---|---|
| P5b PTDF form | same primal/LMP as P5a (rel 1e-9 / abs 1e-6) | Z rel 5.8e-16; LMP 7.1e-15; dispatch 2.3e-13; flows 2.8e-13; mu 7.1e-15; classes equal; vs independent PTDF route LMP 7.1e-15; health pass; angles `recomputed` | >= 7 orders | pass |
| P5c reference bus (5 refs x angle/ptdf = 10 runs) | LMP and dispatch unchanged (1e-6); lambda_ref changes; congestion shifts by a constant | dLMP <= 1.4e-14; dg <= 5.7e-13; lambda_ref = LMP at ref bus (16.977359, 26.384460, 30, 39.942736, 10); congestion-shift error <= 1.2e-14; classes `CONG,CONG,MARG,CONG,MARG` in all 10; UNEXPLAINED 0; health pass | 8 orders | pass |
| P5d D-E limit removed | one price 30.00; Brighton 600, Alta 40, Park City 170, Solitude 190 | LMP all 30 (vs independent 2.5e-14); dispatch error 8.5e-14; congestion component 0.0; no `at_bound`; max abs mu 0; all 5 buses MARGINAL_UNIT solitude; no `price_setter_loop` rows; health pass | exact | pass |
| P5e load scan (72 h, factors 0.50..1.10 `np.linspace`) | each hour vs independent route; UNEXPLAINED 0; class per bus-hour = independent class | max dLMP 1.4e-14; max dg 1.2e-12; max dalpha 1.8e-15; class mismatches 0 hours of 72; UNEXPLAINED 0; 51 congested hours (factor >= 0.6775), 21 uncongested; class counts MARGINAL_UNIT 207, CONGESTION_LOOP 153 of 360 bus-hours; health pass | 8+ orders | pass |
| P5f transport contrast | reported, not judged | section 6 | | reported |
Pytest counterparts: `test_p5a_*`, `test_p5b_*`, `test_p5c_*` (10), `test_p5d_*`, `test_p5e_*`, `test_p5f_*` all pass.

## 5. Section 4 health checks and mutation tests
| Check | Evidence | Result |
|---|---|---|
| Gate 1 checks (balance, duality, CS, dual sign, decomposition, price-setter, fingerprint, conditioning) keep thresholds | `health.csv` P5a above; T1-T4 section 7 | pass |
| KVL recomputation | 2.3e-13 <= 1e-6; `test_h_kvl_recomputation[angle,ptdf]` | pass |
| PTDF recomputation | 1.4e-13 <= 1e-6; `test_h_ptdf_recomputation` | pass |
| LMP decomposition | 1.4e-14 <= 1e-6; congestion component 0 in P5d (section 4) | pass |
| Congestion rent identity | 3.6e-16 <= 1e-7 rel | pass |
| Line duals | `dcpf.line_duals` 0; mu nonzero only on de at rating | pass |
| Islands | `dcpf.islands` 0; fixture `test_h_islands_fixture_one_ref_angle_per_island` (drops ad, bc, de; refs A and C) pass | pass |
| Conditioning | no warn/fail on P5a-P5e (`test_h_conditioning_no_warn_on_p5a_to_p5e`; matrix ratio 15.6) | pass |
| Ranged rows | `test_h_ranged_rows_none_written[angle,ptdf]`: none written, so the F5 path is not exercised by dcpf (F5 itself closed in Gate 2) | pass (n/a) |
| Default unchanged | 21 `test_transport_*` identity tests vs `tests/golden/gate2` pass (canonical outputs byte-identical per 8.10a; fingerprint components equal except allowed fields) | pass |
| M7 reactance x1.01 in LP only | `test_m7[angle]`, `[ptdf]` pass (a check fails) | caught |
| M8 `kvl` row sign flip | `test_m8` pass | caught |
| M9 reference row dropped | `test_m9` pass | caught |
| M10 mu sign flipped in adapter | `test_m10[angle]`, `[ptdf]` pass | caught |

## 6. P5f transport vs dcpf contrast (same case, NTC = rating, blank = unlimited)
Command: same case with `switches: {tx.model: transport}` (harness `make_pjm5(tx="transport")`). Health pass; no dcpf columns/tables/checks written.
| Bus | LMP dcpf | LMP transport | diff | class dcpf | class transport |
|---|---|---|---|---|---|
| A | 16.977 | 30.000 | +13.023 | CONGESTION_LOOP | MARGINAL_UNIT solitude |
| B | 26.384 | 30.000 | +3.616 | CONGESTION_LOOP | MARGINAL_UNIT |
| C | 30.000 | 30.000 | 0 | MARGINAL_UNIT | MARGINAL_UNIT |
| D | 39.943 | 30.000 | -9.943 | CONGESTION_LOOP | MARGINAL_UNIT |
| E | 10.000 | 30.000 | +20.000 | MARGINAL_UNIT | MARGINAL_UNIT |
| Link | flow dcpf (MW) | flow transport (MW) | mu dcpf | mu transport |
|---|---|---|---|---|
| ab | 249.717 | 400 (at bound) | 0 | 0 |
| ad | 186.788 | 650 | 0 | 0 |
| ae | -226.505 | -840 | 0 | 0 |
| bc | -50.283 | 100 | 0 | 0 |
| cd | -26.788 | -10 | 0 | 0 |
| de | -240 (at bound) | +240 (at bound) | -62.322 | 0 |
Dispatch: Solitude 323.49 vs 190, Brighton 466.51 vs 600 (others equal). Annual Z: dcpf 153,123,897.07 vs transport 129,735,600.00; difference -23,388,297.07 $/yr (-2,669.90 $/h, -15.3%).
Reading: with a pipe-and-bubble network the only limits are ab 400 and de 240 , so the system clears at one price 30 with Brighton at its 600 MW cap; the loop flow
physics that makes D-E bind at 240 E-to-D under KVL is absent. Transport flows are one of many equal-cost solutions at a single price (all mu = 0 even on `ab`/`de` at bound, which is degenerate) and violate KVL
(best-fit angles leave 523 MW residual, computed from case reactances). Flow and sign differences are therefore indicative only. Reported, not judged.

## 7. Gate 1 health cases T1-T4 (default transport) and seed determinism
Commands: `PYTHONHASHSEED=0 python scripts/ci_health_run.py --out <h0>`; same with `12345` -> `<h1>`; `python scripts/compare_runs.py <h0> <h1>` -> `[T1]..[T4]` all `identical` (rc 0; 7 cases).
| Case | Z ($/yr) | rows/cols/nnz | Health | warn/fail | UNEXPLAINED | Classes (zone-hours) | fingerprint (h0) |
|---|---|---|---|---|---|---|---|
| T1 | 40,824,000.000000 | 216/218/504 | pass | 0/0 | 0 | MU 36, TIE_AT_BOUND 34, CAPACITY_RENT 2 | bb042849... |
| T2a | 26,125,348.148148 | 432/436/1296 | pass | 0/0 | 0 | MU 72 | 213f1899... |
| T2b | 26,245,348.148148 | 434/436/1300 | pass | 0/0 | 0 | MU 72 | 23855f2a... |
| T2c | 26,280,000.000000 | 434/436/1300 | pass | 0/0 | 0 | MU 72 | c5f38d80... |
| T3a | 23,530,333.333333 | 216/218/504 | pass | 0/0 | 0 | MU 71, VOLL 1 | 8fd7dcd3... |
| T3b | 23,340,333.333333 | 216/218/504 | pass | 0/0 | 0 | MU 71, CAPACITY_RENT 1 | 18089f99... |
| T4 | 39,420,000.000000 | 288/362/720 | pass | 0/0 | 0 | MU 144 | 01f4a018... |
Z values equal the gate-1.md §2 expected values (T1 40.824 M$, T2a 26,125,348.15, T2b 26,245,348.15, T2c 26,280,000, T3a 23,530,333.33, T3b 23,340,333.33, T4 39,420,000).
`pjm5` seed check: `PYTHONHASHSEED=0` vs `12345`, `python -m capex run cases/pjm5bus` into `<pj0>/pjm5bus_dcpf` and `<pj12345>/...`; `compare_runs.py` -> `[pjm5bus_dcpf] identical`.
Scoreboard no-regression: not applicable (scoreboard starts Gate 5); the Gate 1 results above are unchanged.

## 8. Runtime and problem size: `tx.model` complexity-ledger row (reported, not gated)
Command: 7 runs per model through `run_case` on the pjm5 case (72 h, 5 buses, 6 lines, 5 units), cold process after the pytest run; solve time from `run.json` `solve_time_s`, wall = `run_case` total.
| Model | rows | cols | nnz | simplex iterations (median) | solve ms median (min-max) | `run_case` s median |
|---|---|---|---|---|---|---|
| transport | 720 | 1,157 | 2,304 | 576 | 3.2 (2.9-5.1) | 0.183 |
| dcpf angle | 1,224 | 1,517 | 3,672 | 1,121 | 11.5 (10.8-15.2) | 0.219 |
| dcpf ptdf | 864 | 1,157 | 4,896 | 720 | 4.4 (4.0-5.8) | 0.201 |
Ratios dcpf-angle / transport: rows 1.70, cols 1.31, nnz 1.59, solve time 3.6x, end-to-end 1.2x. PTDF / transport: rows 1.20, cols 1.00, nnz 2.13, solve 1.4x. PTDF is denser (nnz grows with lines x buses per hour), angle is larger but sparse.
Peak memory not measured. Tiny case: absolute times are noise-dominated and say nothing about PJM scale (performance ledger starts at Gate 4). Ledger row added to `reports/complexity-ledger.md`.

## 9. Spec and DECISIONS changes in this gate
DECISIONS 47 (criteria, 0.01 MW), 48 (G3-1: formulation F-0.3 section 7.4a complete, surplus 14,957.29), 49 (owner: output key columns later; uppercase A-E zone ids OK), 50 (F-0.3 amendment 1, section 8.10a health-value rule 1e-12 abs-or-rel).
Item-level history: `PLAN.md` G3-1..G3-3-fix2. `docs/data-schema.md` links.csv `reactance_pu`, `base_mva` and rule 11.

## 10. K1 / K2 / K3 (carried items)
- **K2** pass: `tests/test_pjm5bus.py::test_k2_case5m_hash_equals_manifests`, `test_k2_licence_hash_equals_manifests`, `test_k2_detects_a_changed_file` pass; hashes in section 2.
- **K1 local:** `python scripts/fetch_source.py pjm5 --out-dir <dl>/pjm5` -> "OK: 2 file(s) ...; all_verified=True" (live fetch from raw.githubusercontent.com worked here);
  `python scripts/verify_artifact.py <dl>/pjm5 --print` printed `provenance.json` (fields source_id, vintage `matpower-b6c85b0`, manifest, pin_mode `verify`, retrieved_at, workflow_run_id `local`, workflow_run_attempt, git_commit `local`,
  files[] with file, url, sha256, bytes, pinned, verified) and:
  ```
  ed9072089d080debde2aa029ed8a95491c311b08ff4f45ad7bf06882d86fe279  1921  .../case5.m
  5d14c09b3e4f2adf62c0373e6320163697aa4603186f8925c07c6b84201e1750  2074  .../LICENSE_MATPOWER
  ```
  `verify_artifact.py ... --against cases/raw/pjm5bus` -> OK (vendored files equal fetched). The workflow step "Print provenance and hashes" exists in `data-download.yml` (runs after "Provenance summary", before upload).
- **K1/K3 Actions dispatch** (`pjm5`, `pin_mode=verify`, `workflow_dispatch` on `gate-3` @ b82a8b4, queued by the G3-5 session): run 45981948446 (data-download #17), job 140447798417, conclusion **success**, ubuntu-24.04, Py 3.12.16. Step "Fetch and verify": `OK: 2 file(s) in download/pjm5; all_verified=True`; "Re-verify before upload": `OK: download/pjm5 matches provenance.json and manifest`. Step "Print provenance and hashes" printed the full provenance.json (source_id, vintage `matpower-b6c85b0`, manifest, pin_mode, retrieved_at, workflow_run_id/attempt, git_commit, per-file url/sha256/bytes/pinned/verified) and `ed907208…fe279  1921  download/pjm5/case5.m`, `5d14c09b…1750  2074  download/pjm5/LICENSE_MATPOWER` — both equal to the pins → **K1 pass**. Artifact `data-pjm5-default-45981948446` (id 15188669333, 2,704 B). Log uses checkout@v6, setup-python@v6, upload-artifact@v7; no Node 20 deprecation warning in the job log tail (post-job cleanup through "Cleaning up orphan processes"; annotations API not read) → **K3 pass** (log evidence).
- **K3 static:** `ci.yml` and `data-download.yml` use checkout@v6, setup-python@v6, upload-artifact@v7, download-artifact@v8 (grep). CI run 150 green; whether it carries a Node 20 annotation was not readable from the job API (no annotations returned).
- **download-artifact@v8 `pattern:` layout:** the `compare` job (run 150, success) passes `$RUNNER_TEMP/seeds/health-seed-0` and `.../health-seed-12345` and printed `[T2a]..[T4] identical`, so the layout is `seeds/<artifact-name>/` (no merge-multiple). Closed.

## 11. Known limitations
1. Local run is Python 3.13, CI is 3.12 (same pins). Golden/identity tests passed locally and on CI run 150.
2. Run 150 pytest count and Node 20 annotations not read; run 150 `test` job success is the evidence.
3. Memory not measured; timings from a 5-bus case.
4. The independent route is also by the verifier role (tests/test_pjm5bus.py); alpha reference uses the same 7.4a.7 formula (pseudo-inverse of the PTDF system), so alpha is an implementation check, not an external published value.
5. Published values are rounded 2-decimal values from gate-3.md §2 (reproduced by independent route; P3 matched `Pg` of `case5.m`); Li & Bo's table itself was not accessible.
6. P5e is a smooth scan; no hour is degenerate (`test_ref_scan_hours_are_uncongested_or_unique_alpha`), so the DEGENERATE sub-tag path is not exercised on pjm5.

## 12. Findings for G3-6 / G3-7 (observations, no fixes made)
1. **FORMULATION_VERSION** constant still `F-0.2` (`src/capex/__init__.py:3`). The fingerprint component `formulation_version` reads F-0.2 for the pjm5 dcpf run while `run.json` says F-0.3 (both checked). By design for T1-T4 identity (7.4a.9) but a dcpf fingerprint does not carry F-0.3.
2. **Unknown switch keys accepted**: a case with `tx.nonsense` and `tx.dcpf_formm: ptdf` loaded, solved and passed health (angle form silently used). A typo in a switch name silently gives the default.
3. **7.4a.6 non-toy warn/fail** for the two MW checks (`kvl.recompute`, `ptdf.recompute`) is not implemented: only `kvl_residual_mw` 1e-6 exists in `config.py`; the spec says non-toy runs use 1e-3/1e-1.
4. **pjm5 provenance columns**: `cases/pjm5bus/sources.csv` has only `source_id, description` (no vintage/licence); `periods.csv` has no provenance columns (provenance for period weights sits in `load_meta`/README only). Licence is in `docs/data-sources.md` and `cases/raw/pjm5bus/README.md`.
5. **Blank `ntc_*` = unlimited under both models**: under transport, pjm5 has only ab 400 and de 240 limits (section 6), which is why transport and dcpf differ so much; a rating of 0 is an error per data-schema rule. Document in the P5f narrative.
6. **C7 byte-identity** now reads per formulation 8.10a (DECISIONS 50): health `value` compared at 1e-12 abs-or-rel, all other bytes exact. Owner yes/no item.
7. **Alpha outside [0,1]**: bus D weights (1.497, -0.497) are valid under 7.4a.7 (sum 1, price reproduced) but a markets reviewer should confirm the narrative. Also `price_setter` has multi-element `setter_ids` "solitude,brighton" and `setter_zone` "C,E" (format open since G3-2).
8. Housekeeping: no `reports/performance-ledger.md` exists (starts Gate 4 per README); `reports/complexity-ledger.md` created by this item with the `tx.model` row only.

## 13. Pass/fail by gate-3.md criterion
| Criterion | Result | Evidence |
|---|---|---|
| §3 P5a base (angle) | pass | section 3 |
| §3 P5b PTDF equals angle | pass | section 4 |
| §3 P5c reference-bus invariance (10 runs) | pass | section 4 |
| §3 P5d uncongested | pass | section 4 |
| §3 P5e load scan (72 h) | pass | section 4 |
| §3 P5f transport contrast | reported | section 6 |
| §4 Gate 1 checks keep thresholds | pass | sections 3, 7 |
| §4 KVL recomputation | pass | section 5 |
| §4 PTDF recomputation | pass | section 5 |
| §4 LMP decomposition (and 0 in P5d) | pass | sections 3-5 |
| §4 Congestion rent identity | pass | section 3 |
| §4 Line duals | pass | section 5 |
| §4 Islands | pass | section 5 |
| §4 Conditioning no warn/fail P5a-P5e | pass | section 5 |
| §4 Ranged rows | pass (none written) | section 5 |
| §4 Default unchanged (transport) | pass | sections 5, 7 |
| §4 Mutations M7, M8, M9, M10 | all caught | section 5 |
| §4a K1 print provenance and hashes | pass (local + Actions run 45981948446) | section 10 |
| §4a K2 case5.m hash vs manifest | pass | sections 2, 10 |
| §4a K3 off Node 20 | pass (static; dispatch run 45981948446 log shows no Node 20 warning) | section 10 |
| §5 evidence contents | complete | this file |
| §2 pjm5 inputs/provenance (P3) | pass; licence `verify` (owner item 6) | section 2 |
| CI run 150 | success | section 1 |
Tally: 22 pass, 1 reported (P5f), 0 pending, 0 fail.
