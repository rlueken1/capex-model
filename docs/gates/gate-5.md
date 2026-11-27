# Gate 5 — Representative periods + inter-period storage: exit criteria

Status: **DRAFT (prep item P7, 2026-11-26) — not approved. Owner approves (or amends) at the Gate 4 → Gate 5 boundary.**
Criteria are frozen once approved (docs/gates/README.md). Branch `gate-5`, created from `gate-4`.
Spec: `docs/drafts/gate5-rep-periods-spec.md` (DRAFT replacement for formulation §7.1–§7.2, §8 additions), copied into
formulation.md by step W-spec (§6). First gate under the scoreboard and complexity-review rules (README §3–4);
judged on RTS-GMLC (benchmarks.md §6 row G5, test ladder) until Gate 12.

## 1. Scope
In: `capex.ts` aggregation (blocks, features, z-score, Ward + medoid, forced periods, weights, remainder, rescale,
fit report, `block_map`); daily fuel price $\phi_{f,p,t}$ data path (DECISIONS 29); `storage.inter_period`
(`st_link*`, `st_imax/imin`); new health checks and audit hook 12; reference run `full_blocks` + `inter_period=all`;
an expansion variant `rts_gmlc_x` (owner decision 5); complexity-ledger rows for every `ts.*` / `storage.*` switch.
Out: k-means/k-medoids, iterative re-selection with the built fleet (risk R1), multi-year weather, outages in
features (`min_margin` stays off), reserves (G7), UC (G9), PJM data.

## 2. Reference runs (RTS-GMLC 2020, $D=366$, $J=122$, no remainder)
| Id | Case | Config | Role |
|---|---|---|---|
| R0 | `rts_gmlc` fixed fleet | `ts.mode=full_blocks`, `storage.inter_period=all` | exact chronological full year (truth for §4) |
| R0c | same | `full_blocks`, `inter_period=off` | Gate 4 result; must be unchanged (regression) |
| C(n) | same | `clustered`, `n_periods=n`, defaults | candidate, $n\in\{4,8,12,16,24,32,48,61,122\}$ |
| X0 | `rts_gmlc_x` (expansion) | `full_blocks`, `inter_period=all` | one-off full-chronology **capex** reference — needs owner decision 4 (DECISIONS 3) |
| X(n) | `rts_gmlc_x` | `clustered`, `n_periods=n` | candidate expansion runs |
Default `n_periods` = smallest $n$ in the sweep for which every §4 criterion passes (on both C and X); it is then
fixed for later gates. If X0 exceeds 4 h in CI, thermal units are aggregated by (zone, tech, MC rounded to $1/MWh)
in **both** X0 and X(n) and the evidence says so.

## 3. Known-answer tests (verifier, from the spec; expected values computed independently, never via `capex` model code)
Toy family T5 (seasonal storage): one zone, $D_y=366$, 122 blocks, demand 100 MW all hours; VRE (`tech=wind`, $K^0=150$ MW) MC 0 with
availability 150 MW in type-A blocks and 50 MW in type-B blocks (zero cost, curtailable); gas 100 MW, MC 50;
storage existing $P^0=100$ MW, $\eta^c=\eta^d=1$, $\sigma=0$, VOM 0, `long_duration=true`; VOLL 10,000 (must not bind).
"blocked" = blocks 1–61 A, 62–122 B; "alt" = A, B alternating starting with A. Values below were reproduced by an
independent 8784-h chronological LP (`scipy.optimize.linprog(highs)`, 2026-11-26). Tolerances: $Z$ rel $10^{-7}$,
energy abs $10^{-3}$ MWh, $w$ exact.

| Case | Config | Must reproduce |
|---|---|---|
| T5a blocked, $E^0=109{,}800$ | linked (`all`), `full_blocks` | $Z=5{,}490{,}000$; gas 109,800 MWh; one cycle/yr; $R^E E^0$ = storage net revenue (revenue identity), $R^E=50$ $/MWh-yr; $\pi=0$ in A hours, 50 in B hours with gas running |
| T5b blocked, $E^0=1{,}800$ | linked | $Z=10{,}890{,}000$; gas 217,800 MWh |
| T5c alt, $E^0=1{,}800$ | linked | $Z=5{,}490{,}000$; gas 109,800 MWh; $R^E=3{,}050$ (61 cycles × 50) — chronology matters (vs T5b) |
| T5d any of the above | `inter_period=off` | $Z=10{,}980{,}000$; gas 219,600 MWh (no transfer across periods) |
| T5e T5a–c | `clustered`, `n_periods=2`, forced off | partition = {A blocks}, {B blocks}; medoids = earliest block of each type; $w_A=w_B=61$; $Z$ identical to the `full_blocks` result (rel $10^{-9}$) |
| T5f T5a with $\sigma=10^{-4}$/h | linked | independent chronological $Z=6{,}017{,}174.77$; superposition is conservative: model $Z\ge$ that value and within 1% **[P]**; `storage.link_recompute` passes |
| T6a identity | any case, `clustered`, `n_periods=J`, forced off | `block_map.csv` and all period data tables **byte-identical** to `full_blocks` (rescale snaps to 1); `periods.csv` identical except `rep_kind`/`cluster_size_blocks`; LP identical (same fingerprint apart from the `ts.*` config) |
| T6b remainder | synthetic 365-day case ($J=121$, $r_y=2$, $h_r=48$) | $\sum_pw_p=365/3$ (1e-9); remainder on the nearest **non-forced** period, its weight $+2/3$; `st_link` uses $h_r=48$ for $\bar J$ |
| T6c Ward unit test | `ward_medoid(X=[[0],[1],[10],[11],[30]], k)` | $k=3$: {1,2},{3,4},{5}, medoids 1,3,5 (ties → earliest); $k=2$: {1,2,3,4},{5}, medoid 2 (tie 2 vs 3 → earliest); merge order (1,2) before (3,4) by tie-break; partition equals scipy `linkage(…,"ward")` on 20 random tie-free matrices |
| T6d forced | synthetic year with a unique load peak in block 40, net-load peak in 77, VRE drought in 95, 3-day gas spike in 12 (daily-gas fixture) | forced = {12, 40, 77, 95} with reasons; each $w=1$, not rescaled, excluded from clustering; coinciding peaks → one forced period with joined reasons; `n_periods ≤ n_F` → error `ts.too_many_forced` |
| T6e rescale | synthetic case, `rescale` on/off | weighted annual load energy and time-weighted fuel mean equal actual (rel 1e-12) when on; $s_q$ matches a hand formula; clipping residual reported when $A$ hits 1 |
| T6f fuel mapping | daily-gas fixture | $\phi_{f,p,t}$ equals the representative block's day $\lceil t/24\rceil$ price × $s_f$; constant-price series is dropped from features (`ts.feature_dropped`) and `max_fuel_price` is skipped |
| T6g determinism | C(16) run twice, and with rows of the source tables shuffled on disk | byte-identical `periods.csv`, `block_map.csv`, objective bit-identical |

## 4. RTS-GMLC full year vs clustered (criteria; [P] = proposed from benchmarks.md G5 row)
Metrics compare C(n) with R0 (fixed fleet) and X(n) with X0 (expansion). Prices at capacity are non-unique
(DECISIONS 23): hourly price metrics use fixed-fleet runs only; X runs use block/monthly averages.
| Metric | Definition | Tolerance |
|---|---|---|
| Annual variable cost (fixed fleet) | $\lvert Z^{var}_{C}-Z^{var}_{R0}\rvert/Z^{var}_{R0}$ | ≤ 2% [P] |
| Total system cost (expansion) | $\lvert Z_X - Z_{X0}\rvert/Z_{X0}$ | ≤ 2% [P] |
| Capacity mix (expansion) | per tech: $\lvert x_{X}-x_{X0}\rvert \le \max(0.10\,x_{X0},\ 0.02\sum x_{X0})$ | all techs [P] |
| Net-load duration curve | system `dc_w1_rel` (ts_fit) | ≤ 3% [P] |
| Peak net load | `peak_err` system net load | ≤ 1% [P] (0 by construction with forced peak on) |
| Generation by tech (fixed fleet) | share of annual MWh | ≤ 2 pp per tech [P] |
| Price duration curve (fixed fleet) | W1 / mean, zonal hourly $\pi$ reconstructed via `block_map` vs R0 | ≤ 10% [P] |
| Monthly average price (both) | MAE over zone-months / mean | ≤ 5% [P] |
| Marginal fuel shares | max abs share diff over fuel groups vs R0 (price-setter report) | ≤ 5 pp [P] |
| Storage revenue | per storage resource, $\sum w\,\pi(d-c)$ vs R0 / X0 | ≤ 10% [P] |
| Storage cycling | equivalent full cycles/yr vs R0 / X0 | ≤ 10% [P] |
| Unserved energy | MWh vs reference | reported; must be 0 if reference is 0 |
| Correlation preservation | `corr_max_abs` | ≤ 0.10 [P] |
Also reported (not judged): error-vs-$n$ curves for every metric, solve time and size vs $n$, `profile_nrmse`, ramp
duration error, rescale factors.

## 5. Health checks (all Gate 1–4 checks keep their thresholds) plus
| Check | Pass rule |
|---|---|
| `ts.weights`, `ts.assignment`, `ts.data_copy` | spec §8 table; hard fail |
| `ts.fit` | warn-level only; every warn explained in the evidence |
| `storage.link_recompute` | ≤ 1e-6 MWh on T5/T6; §6.2 thresholds on RTS |
| `storage.link_bounds`, `storage.link_duals` | spec §8 table |
| Price-setter | UNEXPLAINED = 0 on every run in §2–§3; STORAGE_* class checks use $v=-y/w_p$ for linked storage |
| Strong duality / CS / zero-profit / revenue identity | Gate 1 rules, with $R^E$ from `st_link_hi` for linked storage |
| Conditioning (§6.2) | no `fail` on any run; `warn` explained (B and $(1-\sigma)^{72}$ coefficients) |
| Defaults unchanged | `ts.mode=full_blocks`, `inter_period=off`: T1–T4, Gate 3 and Gate 4 results and fingerprints unchanged apart from config fields |

Audit-mutation tests (verifier) — at least one check must fail for each: (M11) `st_link` uses $(1-\sigma)$ instead of
$(1-\sigma)^{72}$ in the LP only; (M12) `block_map` with two blocks swapped after the solve (reconstruction vs LP);
(M13) one forced period given $w=2$ with another cluster's weight reduced by 1 (identity still holds; `ts.weights`
must catch forced $w\ne1$); (M14) `st_link_hi` row dropped for one block; (M15) a period's data taken from the
wrong block (`ts.data_copy`).

## 6. Complexity value review (`reports/complexity-ledger.md`, one row each; README §4)
Each row: Δ metrics of §4 (vs the switch off, all else default), Δ solve time, Δ rows/cols/nonzeros, Δ memory,
client questions affected, verdict (keep / keep default-off / simplify / drop), owner decides.
| Row | Ablation | Note |
|---|---|---|
| `ts.mode=clustered` vs `full_blocks` | C(n*) vs R0 | the main trade: accuracy lost vs speed gained |
| `ts.n_periods` | the sweep | picks the default |
| `ts.features.fuel` | weight 0 vs 1 | **not measurable on RTS** (constant fuel): row says so; scored at G12 |
| each other `ts.features.*` | weight 0 vs 1 | |
| `ts.forced.*` | each rule off | |
| `ts.rescale.*` | off vs on | |
| `ts.zone_weighting` | `equal` vs `energy` | |
| `storage.inter_period` | `off` vs `flagged` vs `all` | on X(n*) with LDES candidate |
Regression rule (benchmarks.md): ε per owner decision 7.

## 7. Evidence file `reports/gate-5-evidence.md`
As gate-3.md §5, plus: T5/T6 expected vs obtained with margins; the $n$-sweep tables and curves; chosen
`n_periods` and why; `periods.csv`/`block_map.csv`/`ts_fit.csv` for C(n*) and X(n*); forced-period table with values;
storage SOC chronology plot R0 vs C(n*) and X0 vs X(n*); price-duration and net-load-duration overlays; ledger rows;
`rts_gmlc_x` provenance (candidate costs and the load factor, methods and confidence); run fingerprints; runtimes.

## 8. Work order (proposed; PM confirms at Gate 5 scrum)
W-spec Formulation lead [Opus]: copy the draft spec into formulation §7.1–§7.2/§8 with edits E1–E4, data-schema
changes (`remainder` kind, daily fuel source), one DECISIONS entry, new version string. → Data lead [Sonnet]: daily-gas
fixture, synthetic T6 cases, `rts_gmlc_x` (per decision 5) → Verifier [Sonnet]: T5/T6 tests and mutations from the
spec → Builder [Sonnet]: `capex.ts`, linking rows, audit → Verifier evidence + §4 sweep → Formulation trace →
Markets/consulting reviewers [Opus] (price shape, storage value plausibility) → PM decision list.

## 9. Review and sign-off — decision list (format as gate-1.md §6)
Required items at the end of Gate 5: (1) T5–T6 pass within tolerance? (2) all health checks pass, UNEXPLAINED = 0,
mutations M11–M15 caught? (3) §4 criteria met at the chosen `n_periods` — adopt that default? (4) linked storage
(`flagged`) default accepted? (5) ledger verdicts for each row accepted? (6) defaults unchanged (T1–T4, G3, G4)?
(7) spec version and DECISIONS entry accepted? (8) merge `gate-5` to `main` and mark Gate 5 DONE?

**Open for the owner when approving this draft (yes/no; recommendation in brackets):**
1. Ward hierarchical + medoid as the only clustering method; no seed (deterministic) [yes].
2. Forced-period defaults: peak load, peak net load, VRE drought, max fuel price on; `min_margin` off until outages
   (G12); every forced period has weight exactly 1 and never takes the remainder [yes].
3. Rescale load, VRE and fuel to annual totals by default (clustered periods only) [yes; ablated in the ledger].
4. Allow one full-chronology **expansion** reference run (X0, 8784 h) on RTS-GMLC as a test-only check, a narrow
   exception to DECISIONS 3; never on PJM. If no: the capacity-mix criterion is replaced by convergence over the $n$ sweep [yes].
5. Build `rts_gmlc_x`: RTS-GMLC + candidates (gas CT, gas CC, wind and PV on existing zone profiles, 4-h battery,
   100-h LDES flagged `long_duration`), load × 1.15 so new firm capacity is needed, costs from NREL ATB via the
   Actions download (est. level 4) or stylised `assumed` costs if ATB is not yet available [yes].
6. Fuel-price feature tested on a synthetic daily-gas fixture only; its accuracy value is scored at Gate 12 [yes].
7. Regression-rule ε: replace "5 clustering seeds" (no seeds exist) with the spread over `n_periods` n±2 [yes].
8. Default `n_periods` chosen by the sweep rule in §2 [yes].
9. Remainder rule wording (§1.2): nearest **non-forced** period [yes].
10. Tolerances in §4 as proposed (all [P], from benchmarks.md G5 row plus new rows for prices, fuel shares,
    cycling, generation mix) [yes].
