# Gate 1 — toy model + audit layer: exit criteria

Status: **proposed — owner approves at Gate 0 review.** Criteria are frozen once approved (docs/gates/README.md).
Spec: docs/formulation.md F-0.1 (plus the clarifications in "Spec assumptions" below). Branch `gate-1`, created from `gate-0`.
Deviation from README rule 1: CI arrives in Gate 2, so Gate 1 evidence is a **local pytest run log**, not a CI run. Owner accepts this by approving this file.

## 1. Scope
In: toy LP per §2 (thermal, VRE, storage, links, VOLL), solver adapter (HiGHS via `highspy`, simplex only), scaling (§6.1), `capex.audit` hooks 1–10 (§8), `capex.econ` (`annualize`, `to_base_dollars`, §5), load-time validation (weights, dollar year, Δt). Assumptions book (§8.11) as a stub that prints the annualization table and counts.
Out: reserves, UC, policy, retirements, capacity market, PJM data, rep-period clustering (weights are inputs), CI, UI.
Rules: tests are written by the verifier from the spec (builder does not write or edit judging tests; builder-side smoke tests live in `tests/builder/` and do not count as evidence). A failing test leads to a spec-or-code decision logged in DECISIONS, never a tolerance edit by the builder.

## 2. Known-answer tests (formulation §10)
Expected values are computed in the tests from the closed forms (not pasted rounded numbers). Tolerances: objective and capacities rel 1e-6 (abs floor 1e-6); rents and revenue rel 1e-6; **block-average prices** (weight-averaged over the block's hours) rel 1e-5; unique hourly prices abs 1e-4 $/MWh. Hourly prices inside a degenerate block are tested only against the allowed interval from the price-setter class (§3.7, §4).

| Case | Must reproduce | Expected price-setter report |
|---|---|---|
| T1 | x_Base=120, x_Peak=30, u=0; Z=40.824 M$; block prices 20 / 20.822 / 121.096; Σ w·D·π = Z; hourly mid π∈[20,80], peak π≥80; zero-profit rents R=C^fix for both builds | off-peak: MARGINAL_UNIT Base; mid and peak: CAPACITY_RENT/INVESTMENT_MARGIN or TIE_AT_BOUND per hour (DECISIONS 30; block averages exact); UNEXPLAINED=0 |
| T2a | storage charge 44.44, discharge 36 MWh per period; prices 20/60; v=22.22 / 54; R^E=3866.30, R^P=0; Z=26,125,348.15 | G1 / G2 MARGINAL_UNIT; ties with STORAGE_CH/DIS recorded |
| T2b | builds 10 MW/40 MWh (at xP_ub, xE_ub); excess rent (R^P+4R^E)−(C^P+4C^E)=3465.19 ≥0; Z=26,245,348.15 | as T2a |
| T2c | x=0; Z=26,280,000; prices 20/60; combined rent R^P+4R^E ∈ [15,465.19, 20,000] (dual-degenerate at x=0, formulation §10; i.e. rent ≤ cost, not <; no point value asserted) | as T2a |
| T3a | x=0, u_48=20; π_48=1000; G rent 118,016.67; Peaker reduced cost 40,500; Z=23,530,333.33 | hour 48 VOLL; others MARGINAL_UNIT |
| T3b | x=20, u=0; π_48=921.92 (unique); Z=23,340,333.33 | hour 48 CAPACITY_RENT/INVESTMENT_MARGIN |
| T4 | f=50 at flow_ub; π_A=20, π_B=50, μ=30; congestion rent 13,140,000; Z=39,420,000; two islands | A: G_A; B: G_B; binding link listed; UNEXPLAINED=0 |

Plus: 50 randomized small instances (fixed seeds; 1–3 zones, 1–3 periods, mixed thermal/VRE/storage/links) must pass every health check in §3 below, and their objective must match a second solve through an independent route (`scipy.optimize.linprog(method="highs")` or equivalent) at rel 1e-7.

## 3. Health checks (each runs on every solve; tolerances below)
| Check | Pass rule |
|---|---|
| Balance residual (`bal`) | max abs ≤ 1e-6 MW on toy cases (formulation §3.1). §6.2 warn/fail (1e-3 / 1e-1 MW) is the general rule; Gate 1 is stricter |
| Dual-sign adapter | on a 2-variable LP with one binding ≤, ≥, = row and one binding bound, raw duals have the §1.3 signs and exact values; failing adapters reject the run |
| Strong duality | \|Z_primal−Z_dual\|/\|Z\| ≤ 1e-7 (§3.2) |
| Complementary slackness | every row and bound: \|y·slack\| / max(1, \|Z̃\|) ≤ 1e-8 in scaled units (proposed); dual signs per §3 table; no violations |
| Zero-profit / revenue identity | §3 checks 5–6 within rel 1e-6 for every candidate; storage reduced costs recomputed from duals equal solver column duals within 1e-6 scaled |
| Dual unscaling | solve once scaled and once with scaling off (k_P=k_C=1): primal rel 1e-6, economic duals (π, ρ, v) rel 1e-5. Exception (formulation §3 check 7): storage duals v, ρ^P, ρ^E of a storage with zero capacity (T2c) are dual-degenerate — T2c compares primal, π and generator ρ only; random instances compare π and generator ρ only |
| SOC-row recomputation | `storage.soc_recompute` (formulation §3 check 8): residual of e_t−(1−σ)e_{t−}−η^c c_t+d_t/η^d recomputed from case-data η^c, η^d, σ (not from the LP matrix), cyclic wrap included; max abs ≤ 1e-6 MWh on toy and random cases; produced on every solve with storage |
| Objective decomposition | Z^inv, Z^var (by resource/fuel), Z^use, Z^0 sum to Z within 1e-9 rel (§8.4) |
| Binding-constraint report | produced; the binding families and bounds equal the expected set listed per case in the verifier tests (e.g. T1: gen_max binding for Base in mid+peak, Peaker in peak, no x_ub; T2b: xP_ub, xE_ub; T4: flow_ub) |
| Price-setter report | UNEXPLAINED = 0 on T1–T4 and random instances; price within tol_π of setter cost (per-class setter cost as formulation §4 Outputs, e.g. STORAGE_DIS: VOM + v/η^d) or inside the CAPACITY_RENT interval; marginal-fuel shares sum to 1 per zone; solution rejected if not basic (IPM without crossover) |
| Conditioning check (§6.2) | report produced for every solve; T1–T4 have no `fail` and no `warn`; a fixture with matrix ratio >1e9 produces `fail` and marks the run invalid; thresholds exactly as §6.2 table |
| Run fingerprint determinism | same inputs/config/commit/solver options → identical SHA-256, and byte-identical canonical outputs, across 3 runs and 2 separate processes with different `PYTHONHASHSEED`; changing any input float by 1e-12, any switch, any solver option, formulation version, or a dirty-tree diff changes the fingerprint; a conditioning `fail` marks the fingerprint invalid |
| Load validation | weight sum ≠ D_y/3 beyond 1e-9, w<1, missing dollar year, or Δt≠1 raises; tested with one bad input each |
| econ | CRF table values (r=0.07, n=20 → 0.09439); r=0 branch =1/n; |r|<1e-9 uses r=0 branch; invalid n/r raise; ANN ≥ I/n for r ≥0; Fisher conversion; deflation round-trip; static scan finds no annuity math outside `capex/econ.py` |

Audit-mutation tests (verifier): inject each of 6 faults and require at least one check to fail: flip a dual sign in the adapter; drop one `bal` row; scale one cost by 1.001; swap η^c and η^d in `st_soc`; set a wrong weight on one period; use an IPM-no-crossover solution. A fault that no check catches is a gate failure. M4 must be caught with η^c ≠ η^d (with η^c = η^d the swap is a no-op); the check expected to catch it is `storage.soc_recompute`.

## 4. Spec assumptions (formulation lead applies at Gate 0 review; Gate 1 is built on them)
1. §4 `VOLL` class accepts u = D (total blackout, `use_ub` binding) as well as 0<u<D.
2. §3.1 residual tolerance and §6.2 thresholds are reconciled as in the table above.
3. §5.2 default PFF follows DECISIONS 22 (ATB-style CRF with tax/depreciation default); tests cover both settings.
4. Solver config forces simplex (dual) with crossover; fingerprint records it.
5. Z^0 is excluded from the LP and from strong-duality checks and included in reported Z and the decomposition.
Any other spec change during the gate follows the CLAUDE.md "spec first" rule.

**Amendment 1 (W4b-fix1, 2026-11-25, DECISIONS 31; owner confirms in §6 item 5).** Found by the W4b verifier tests:
(a) new §3 row "SOC-row recomputation" (formulation §3 check 8) — no existing check caught mutation M4;
(b) T2c storage duals are dual-degenerate at $x=0$, so T2c's §2 row and the §3 dual-unscaling row test primal, π
and generator ρ only, and T2c rents against the interval of formulation §10 (rent ≤ cost, not <). This is a
degeneracy fact proven in formulation §10 (both observed HiGHS values lie inside the interval), not a tolerance
change; the lower end of the interval (T2a arbitrage value) is added as a test, so the criterion is not weakened;
(c) price-setter `setter_cost`/`residual` defined per class (formulation §4 Outputs); (d) `fuel` optional for VRE
(data-schema §3.3).

## 5. Evidence file `reports/gate-1-evidence.md`
Must contain, with commit hash and fingerprint of each case: (1) command and full log `pytest -v --durations=10 --junitxml=reports/gate-1-junit.xml | tee reports/gate-1-pytest.log` (verifier runs, builder does not) with pass/fail count; python, highspy and OS versions; (2) a T1–T4 table of expected vs obtained values and tolerance margins; (3) one health-report excerpt per case (balance, duality gap, CS, decomposition, binding, price-setter, conditioning); (4) price-setter class table for T1–T4; (5) fingerprint determinism log; (6) mutation-test results; (7) list of spec changes made in the gate and their DECISIONS numbers; (8) known limitations (hourly price degeneracy, solver version pinned). Run time per case is reported, not gated.

## 6. Review and sign-off
- **Verifier [Sonnet]:** writes tests from the spec, runs them, writes pass/fail per row of §2–§3 in `reports/gate-1-review.md`.
- **Formulation lead [Opus]:** line-by-line trace of code against §2–§6, confirms every deviation is in the spec and in DECISIONS, checks the dual conventions and the price-setter logic.
- **Markets (PJM) reviewer [Opus]:** reads the price-setter classes and dual interpretations for economic sense (prices, rents, congestion), confirms T1–T4 narratives.
- **Consulting reviewer [Opus]:** checks that audit and assumptions-book output are understandable to a client-facing reader.
- UI and client-panel reviewers: not needed at Gate 1.
- Review ends with a decision list for the owner, format: `N. <question>? **Recommendation: yes/no** — evidence: <link>. If no: <consequence>.` Required items: (1) all T1–T4 within tolerance? (2) all health checks pass, UNEXPLAINED=0? (3) fingerprint deterministic? (4) mutation tests all caught? (5) spec changes accepted? (6) local pytest log accepted in place of CI? (7) merge `gate-1` to `main` and mark Gate 1 DONE?
- Only the owner sets Gate 1 DONE and merges to `main`. At the end of the work the PM sets `STATUS: AWAITING_OWNER_REVIEW`.
