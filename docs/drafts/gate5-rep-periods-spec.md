# DRAFT — Gate 5 spec: representative periods and inter-period storage (replaces formulation §7.1–§7.2)

Status: **DRAFT (prep item P7, 2026-11-26) — not approved, not part of `docs/formulation.md`.** Owner approves or
amends this at the Gate 4 → Gate 5 boundary; then the Gate 5 W-spec step copies it into formulation §7.1–§7.2 (and
the small edits in §9 of this file) under the next version string, with one DECISIONS entry.
Notation, units, sign and dual conventions are those of formulation §1 and §3 (F-0.2). Nothing here changes the
Gate 1 LP when `ts.mode = full_blocks` and `storage.inter_period = off`.
Settled inputs: DECISIONS 3 (weighted 3-day periods, forced peak/scarcity periods, inter-period linking, no 8760
capex), 18 (fuel price as a clustering feature, forced extreme events), 23 (block-average price scoring), 25/29
(daily fuel price $\phi_{f,p,t}$ built at Gate 5), 26 (simplest model first).

---

## 7.1 Representative periods — `ts.*`

### 7.1.1 Blocks (the candidate pool)
- Year $y$, $D_y$ days, $H_y = 24D_y$. Fixed calendar grid starting 1 Jan 00:00 local standard time (same hour
  convention as the case's series).
- Full blocks $j \in \mathcal J = \{1,\dots,J\}$, $J=\lfloor D_y/3\rfloor$; block $j$ = days $3j-2 \dots 3j$, hours
  $t=1..72$. Remainder $r_y = D_y \bmod 3 \in\{0,1,2\}$; if $r_y>0$ there is one truncated block $j=\bar J = J+1$
  of $h_r = 24 r_y$ hours. $\bar{\mathcal J} = \mathcal J \cup \{\bar J\}$ if $r_y>0$, else $\mathcal J$.
- Block fraction $\omega_j = 1$ for $j\in\mathcal J$, $\omega_{\bar J} = r_y/3$. Identity: $\sum_{j\in\bar{\mathcal J}}\omega_j = D_y/3$.
- Block boundaries are never shifted to fit events (keeps `block_map` trivial; risk R4).
- **Input contract.** Aggregation reads a *full-year source case*: $J$ periods with `rep_kind=full_block`
  ($w=1$, `source_start_date` = first day of block) plus, if $r_y>0$, one period `rep_kind=remainder` carrying
  $t=1..h_r$ only. A `remainder` period is consumed by the aggregator and never passed to the LP
  (data-schema §2.1 enum gains `remainder`; draft change). RTS-GMLC 2020: $D=366$, $J=122$, $r_y=0$.

### 7.1.2 Feature vector per block
Feature groups $g \in \mathcal G = \{\text{load}, \text{wind}, \text{solar}, \text{net\_load}, \text{fuel}\}$, group weight
$\omega_g\ge0$ (`ts.features.<g>`, default 1; $0$ = group off). Per zone $z$ and hour $h=1..72$ of block $j$:
| Group | Series $x_{g,z,j,h}$ | Unit |
|---|---|---|
| load | $D_{z,j,h}$ | MW |
| wind | $\mathrm{CF}^{wind}_{z,j,h} = \sum_{r} \kappa_r A_{r,j,h} / \sum_r \kappa_r$ over $r\in\mathcal R^{VRE}_z$ with `tech` in {`wind`, `offshore_wind`} | – |
| solar | same over `tech` in {`solar_pv`, `solar_rtpv`, `csp`} | – |
| net_load | $NL_{z,j,h} = D_{z,j,h} - \sum_{r\in\mathcal R^{VRE}_z} A_{r,j,h}K^0_r$ (all VRE incl. hydro as typed in the case) | MW |
| fuel | per fuel hub $f$ used by a thermal resource: the 3 daily prices $\phi_{f,j,d}$, $d=1,2,3$ (not 72 repeats) | $/MMBtu |
$\kappa_r = K^0_r$ if the zone-group has existing capacity, else $\kappa_r = 1$ over its candidates; a zone with no
resource of the group has no coordinate for it. Net load uses the **existing** fleet $K^0$ (risk R1).
Fuel enters only if daily prices exist (DECISIONS 29); a case with one price per year has zero variance and the
group drops out by the rule below.

**Normalisation (z-score per series, whole year).** For each series $(g,z)$ (fuel: $(f)$):
$\mu,s$ = mean and population standard deviation over all full-block values ($J\cdot72$ hours; fuel $J\cdot3$ days).
If $s \le 10^{-9}\max(1,|\mu|)$ the series is **dropped** (info `ts.feature_dropped`, listed in `periods_meta.json`).
Coordinate value $\tilde x = (x-\mu)/s \cdot \sqrt{\omega_g\,\zeta_{g,z}/n_g}$ with $n_g = 72$ (hourly) or $3$ (fuel).
So every group contributes on average $\omega_g$ to a squared distance regardless of its length or zone count.

**Multi-zone.** Zones are concatenated coordinates (no separate clustering per zone, so one medoid keeps cross-zone
correlation). Zone weights $\zeta_{g,z}$, $\sum_z\zeta_{g,z}=1$ per group, `ts.zone_weighting`:
`energy` (default) — load, net_load: zone share of annual load energy; wind, solar: zone share of $\sum\kappa_r$ of
the group; fuel: $1/|\text{hubs}|$. `equal` — $1/|\mathcal Z_g|$. Feature matrix $X\in\mathbb R^{J\times F}$, float64,
columns in a fixed order (group order above, then zone id, then hour; fuel by hub id).

### 7.1.3 Forced periods — `ts.forced.*`
Selected on the full year **before** clustering, from system (sum over zones, coincident) series on full blocks:
| Switch (default) | Rule: block $j^*$ = | `forced_reason` |
|---|---|---|
| `peak_load` (on) | $\arg\max_j \max_h \sum_z D_{z,j,h}$ | `peak_load` |
| `peak_net_load` (on) | $\arg\max_j \max_h \sum_z NL_{z,j,h}$ | `peak_net_load` |
| `min_vre` (on) | $\arg\min_j \sum_h\sum_z\sum_{g\in\{wind,solar\}} \mathrm{CF}^g_{z,j,h}\sum_{r}\kappa_r$ (72-h VRE energy drought) | `min_renewable` |
| `max_fuel_price` (on) | $\arg\max_j \frac13\sum_d \phi_{f^*,j,d}$, $f^*$ = `ts.forced.fuel_hub` (default: hub with the largest mapped thermal $K^0$); skipped if that series was dropped | `max_fuel_price` |
| `min_margin` (off) | $\arg\min_j \min_h\big[\sum_{r\in\mathcal R^{TH}\cup\mathcal R^{VRE}}A_{r,j,h}K^0_r + \sum_{r\in\mathcal R^{ST}}P^0_r - \sum_z D_{z,j,h}\big]$; equals peak net load while $A^{TH}\equiv1$, so on only once outages exist (G12) | `min_margin` |
| `events` ([]) | list of `{name, start, end}` dates: **every** full block overlapping [start, end]; an event touching the remainder block is a config error | `event:<name>` |
Ties: earliest block. A block picked by several rules is forced once, reasons joined with `|`.
$\mathcal F$ = forced set, $n_F=|\mathcal F|$. Error `ts.too_many_forced` unless $k_c = $ `ts.n_periods` $- n_F \ge 1$.
Example: Winter Storm Elliott (2022-12-23..25, days 357–359 of 2022) spans blocks 119 and 120 → 2 forced periods.

**Weight rule for extremes (avoids over-weighting):** a forced block is removed from the pool, becomes its own period
with $w_p = 1$ **exactly** (it represents only itself), is never rescaled (§7.1.6) and never receives the remainder.
This is tsam's "append"-type treatment, not "new cluster centre" (which reassigns neighbours to the extreme and
inflates its weight) (Kotzur et al. 2018a; tsam documentation — verify option names).

### 7.1.4 Clustering — `ts.method = ward_medoid` (only value at Gate 5)
Pool $\mathcal J\setminus\mathcal F$, rows of $X$. Agglomerative hierarchical clustering with Ward's criterion
(Ward 1963), cut at $k_c$ clusters; representative = medoid.
1. Start: each pool block is a cluster, id = its block index. Squared Euclidean distances computed by explicit
   element-wise differences and `sum` along the feature axis (no matmul/BLAS, so the summation order does not
   depend on threads).
2. Merge cost $\Delta(A,B)=\frac{|A||B|}{|A|+|B|}\lVert c_A-c_B\rVert^2$ (increase in within-cluster SSE; $c$ =
   centroid), updated by Lance–Williams. Merge the pair with the smallest $\Delta$; **tie** (exact float equality)
   → smallest $(\min A, \min B)$ lexicographically, where $\min A$ = smallest block index in $A$; the new cluster's id is
   $\min(A\cup B)$. Repeat until $k_c$ clusters.
3. Medoid of cluster $C$: $m_C=\arg\min_{i\in C}\sum_{i'\in C}\lVert\tilde x_i-\tilde x_{i'}\rVert^2$; tie → earliest block.
4. API (unit-testable without a case): `capex.ts.ward_medoid(X, k) -> (labels, medoids)`; a verifier may cross-check
   the partition against `scipy.cluster.hierarchy.linkage(X, "ward")` on tie-free data.

No random number is used anywhere, so there is **no seed** (fingerprint records `seed: none`, plus the full `ts.*`
config). Same inputs + code + package versions ⇒ byte-identical `periods.csv`, `block_map.csv`.
Why this method (simplicity rule, DECISIONS 26): deterministic without initialisation; nested in $k$ (the $k$ and
$k+1$ partitions differ by one split, so `n_periods` sweeps are monotone and easy to ablate); trivial cost at
$J\le122$; medoids are real blocks, keeping intra-block chronology, cross-zone and weather–fuel co-movement
(Kotzur et al. 2018a found medoid representation preserves profile extremes and correlations better than centroids —
verify exact wording; Nahmmacher et al. 2016 use Ward for representative days; Teichgraeber & Brandt 2019 compare
k-means, k-medoids and hierarchical and favour medoid representatives for optimisation outcomes — verify). GenX
(`TimeDomainReduction`, k-means/k-medoids with extreme periods) and PyPSA via tsam use similar pipelines; ReEDS uses
clustered representative days (all verify against current docs). k-medoids/k-means are **not** built (would need
seeds or MILP); can be added in a later gate with a ledger row.

### 7.1.5 Periods, assignment, weights
- Periods $\mathcal P = \mathcal F \cup \{m_C\}$, ordered by representative block index, ids `p001..`; `rep_kind` =
  `forced` or `medoid`; `source_start_date` = first day of the representative block.
- Assignment $\mathrm{rep}: \bar{\mathcal J}\to\mathcal P$: forced block → itself; pool block → its cluster's medoid
  period; remainder block $\bar J$ → the **non-forced** period whose representative's first $h_r$ hours (and first
  $r_y$ fuel days) are nearest in the same scaled feature space (coordinates truncated, same scale factors; tie →
  earliest). This is the §1.2 rule with the candidate set restricted to clustered periods (§9 edit E1).
- Weights $w_p=\sum_{j:\mathrm{rep}(j)=p}\omega_j$. Then $\sum_p w_p = D_y/3$ holds by construction (load check
  tol $10^{-9}$ still applied), $w_p\ge1$, forced $w_p = 1$, $w_p\le \bar J\le 122$ (§6 scaling range holds).
- Period data = the representative block's 72 hours of $D$, $A$ and $\phi$ ($\phi_{f,p,t}=\phi_{f,\text{rep block},\lceil t/24\rceil}$,
  formulation §1.4), then rescaled (§7.1.6).
- `ts.mode = full_blocks`: $\mathcal P = \mathcal J$, $\mathrm{rep}(j)=j$, remainder by the §1.2 rule, no rescale. Gate 4 behaviour.

### 7.1.6 Annual totals — `ts.rescale.{load, vre, fuel}` (default all on; clustered mode only)
Medoids do not preserve annual sums. For each series $q$ (load per zone; availability per resource $r\in\mathcal R^{VRE}$
as $A_r$; fuel per hub) let $T_q$ = actual annual sum over all $H_y$ hours (fuel: time-weighted, over $D_y$ days),
$F_q=\sum_{p\in\mathcal F}w_p\sum_t q_{p,t}$, $C_q=\sum_{p\notin\mathcal F}w_p\sum_t q_{p,t}$. Factor
$s_q=(T_q-F_q)/C_q$; if $|s_q-1|\le10^{-12}$ set $s_q=1$; if $C_q=0$ set $s_q = 1$. Apply to non-forced periods:
$q\leftarrow s_q q$; availability then clipped, $A\leftarrow\min(1,A)$ (no iteration; the clipping loss is reported as
`rescale_residual`). Forced periods are never rescaled. Outputs `ts_rescale.csv` (series, $s_q$, residual).
Effect: weighted annual load energy and fuel-price mean are exact; VRE energy exact up to clipping.

### 7.1.7 Objective and prices under weights (unchanged form)
Objective is formulation §2.3 with these $w_p$; investment terms are annual and unweighted. Every per-hour dual
converts with the §3 table ($\pi = y/w_p$ etc.); a forced period has $\pi=y$. Hourly chronological reconstruction
for scoring: $\hat q_{z,j,t}=q_{z,\mathrm{rep}(j),t}$ for every block, $t\le72$ ($t\le h_r$ for $\bar J$); monthly
/on-peak averages map hours to calendar via `block_map` (benchmarks.md, DECISIONS 23). Price-setter shares
(§4) are weighted by $w_p$ — identical to weighting the reconstruction by $\omega_j$.

### 7.1.8 Fit report (`ts_fit.csv`, every aggregation; computed on data, before the solve)
For each series $q$ in {load, wind, solar, net_load per zone; system load; system net load; fuel per hub}, model
distribution = values $q_{p,t}$ (after rescale) with weight $w_p$ (remainder handled exactly by the weights); actual =
all $H_y$ hours:
| Metric | Definition |
|---|---|
| `energy_err_pre` | $(\sum_p w_p\sum_t q^{\text{pre-rescale}}_{p,t} - T_q)/T_q$ |
| `peak_err` | $(\max_{p,t} q_{p,t} - \max q)/\max q$ (min for `min_vre`-type use: also `trough_err`) |
| `dc_w1_rel` | Wasserstein-1 between actual and weighted model distribution / mean$\lvert q\rvert$ (duration-curve area error) |
| `dc_nrmse` | RMSE of the two quantile functions at $u=0.005,0.015,\dots,0.995$ / mean$\lvert q\rvert$ |
| `ramp_dc_w1_rel` | `dc_w1_rel` of 1-h ramps $q_t-q_{t-1}$, $t=2..72$ (net load, system; reported) |
| `profile_nrmse` | $\sqrt{\sum_j\omega_j\sum_h(q_{j,h}-\hat q_{j,h})^2/\sum_j\omega_j h_j}$ / mean$\lvert q\rvert$ |
| `corr_max_abs` | max over series pairs of $\lvert\rho^{model}-\rho^{actual}\rvert$, Pearson, model correlations $w_p$-weighted, all hourly series of the table (fuel at daily resolution, paired with daily means) |

### 7.1.9 Outputs
`periods.csv` (data-schema §2.1 incl. `forced_reason`, `cluster_size_blocks`), `block_map.csv` (§2.2: `block_j`,
`block_start_date`, `period_id`, `weight_fraction` $=\omega_j$), `ts_fit.csv`, `ts_rescale.csv`, `periods_meta.json`
(config, feature columns and dropped series, $\mu,s$ per series, $\zeta$, forced selections with their values, the
merge history as a $(k_c..|\text{pool}|)$ linkage table, and its SHA-256).

---

## 7.2 Inter-period storage — `storage.inter_period ∈ {off, flagged, all}` (default `flagged`)

Linked set $\mathcal R^{LD}$: `off` → ∅; `flagged` → storage with `long_duration = true` (resources.csv); `all` → $\mathcal R^{ST}$.
Unlinked storage keeps the Gate 1 cyclic rows (`st_soc` with $t^-$, `st_emax`) unchanged.
Method: superposition of an intra-period trajectory and a chronological boundary state (Kotzur et al. 2018b; same
idea in Gabrielli et al. 2018; alternative "system states" linking in Tejada-Arango et al. 2018, not adopted).

**Variables** ($r\in\mathcal R^{LD}$)
| Label | Symbol | Index | Bounds | Unit |
|---|---|---|---|---|
| `soc` (reused) | $e_{r,p,t}$ = intra-period SOC change since start of the period | $p, t=1..72$ | **free** | MWh |
| `soc_hi` | $\overline e_{r,p}$ | $p$ | $\ge 0$ | MWh |
| `soc_lo` | $\underline e_{r,p}$ | $p$ | $\le 0$ | MWh |
| `soc_b` | $B_{r,j}$ = SOC at the start of block $j$ | $j\in\bar{\mathcal J}$ | $\ge 0$ | MWh |
Bounds on `soc_hi`/`soc_lo` encode $e_{r,p,0}=0$ inside the envelope.

**Constraints**
- `st_soc[r,p,t]` (non-cyclic start): $e_{r,p,t}-(1-\sigma_r)e_{r,p,t-1}-\eta^c_rc_{r,p,t}+d_{r,p,t}/\eta^d_r=0$, with $e_{r,p,0}\equiv0$.
- `st_imax[r,p,t]`: $e_{r,p,t}-\overline e_{r,p}\le0$; `st_imin[r,p,t]`: $e_{r,p,t}-\underline e_{r,p}\ge0$.
- `st_link[r,j]`, $j\in\bar{\mathcal J}$: $B_{r,j^+}-(1-\sigma_r)^{h_j}B_{r,j}-e_{r,\mathrm{rep}(j),h_j}=0$, with $h_j=72$
  ($h_{\bar J}=h_r$) and $j^+=j+1$, cyclic year $(\max\bar{\mathcal J})^+ = 1$.
- `st_link_hi[r,j]`: $B_{r,j}+\overline e_{r,\mathrm{rep}(j)}-x^E_r\le E^0_r$.
- `st_link_lo[r,j]`: $(1-\sigma_r)^{72}B_{r,j}+\underline e_{r,\mathrm{rep}(j)}\ge0$.
- `st_pwr`, `st_dur_*` unchanged; `st_emax` is **not** written for linked storage (replaced by `st_link_hi`).
Chronological SOC is $e^{chr}_{r,j,t}=(1-\sigma_r)^tB_{r,j}+e_{r,\mathrm{rep}(j),t}$ (exact superposition). With
$\sigma_r=0$ the envelope rows are exact ($0\le e^{chr}\le E_r$ ⇔ the two link rows); with $\sigma_r>0$ they are
conservative (sufficient, slightly tighter than needed). The remainder block uses the full-period envelope
(conservative) and $e$ at $h_r$; its objective weight still covers all 72 hours of its period (§1.2 mismatch, risk R7;
absent in RTS-GMLC 2020). No objective terms are added.
Size per linked resource: $|\bar{\mathcal J}|$ cols + $3|\bar{\mathcal J}|$ rows + $2|\mathcal P|$ cols + $144|\mathcal P|$ rows.

**Identities.** `ts.mode=full_blocks`, $r_y=0$, `inter_period=all` is an exact chronological full-year dispatch
(storage carried across all block boundaries, year-cyclic) — the Gate 5 reference run. `inter_period=off` with any
`ts.mode` is exactly Gate 1 storage.

**Duals (extend formulation §3 table; same canonical convention)**
| Row | Raw sign | Economic quantity | Conversion | Unit |
|---|---|---|---|---|
| `st_soc[r,p,t]` (linked) | free | water value, $w_p$-weighted mean over the blocks $p$ represents | $v=-y/w_p$ | $/MWh |
| `st_link[r,j]` | free, normally $\le0$ | inter-period water value of 1 MWh carried into block $j^+$ | $V_{r,j}=-y$ (**no** $/w$: one row per real block) | $/MWh |
| `st_link_hi[r,j]` | $\le0$ | energy-capacity rent in block $j$ | $\rho^{E}_{r,j}=-y$; $R^E_r=\sum_j\rho^E_{r,j}$ | $/MWh-yr |
| `st_link_lo[r,j]` | $\ge0$ | value of relaxing the empty limit | $y$ | $/MWh |
| `st_imax`/`st_imin` | $\le0$ / $\ge0$ | pass envelope rents to link rows | stationarity of `soc_hi`: $\sum_t y^{imax}_{r,p,t}=\sum_{j:\mathrm{rep}(j)=p}y^{hi}_{r,j}$ (if $\overline e>0$) | – |
Stationarity of $d$, $c$ is unchanged, so price-setter classes `STORAGE_DIS` ($\pi=VOM+v/\eta^d$) and `STORAGE_CH`
($\pi=\eta^cv$) apply as written in §4 with this $v$. Zero-profit (§3 check 5) and the storage revenue identity (§3
check 6) hold with $R^E$ from `st_link_hi` (the `st_link_lo` RHS is 0, so it adds no rent term).

---

## 8. Audit hooks — additions
- 6 (storage): for linked storage report $B_{r,j}$, $e^{chr}_{r,j,t}$ (8784/8760-h chronological SOC), $V_{r,j}$, link
  closure residual, equivalent full cycles/yr $=\sum_pw_p\sum_td/E_r$.
- 7 (price-setter): unchanged algorithm; adds the chronological reconstruction of class and $\pi$ by `block_map`.
- 10 (fingerprint): `ts.*` and `storage.inter_period` config, aggregation code version, `seed: none`, SHA-256 of
  `periods.csv`, `block_map.csv`.
- 12 (new) **Time-series aggregation report**: `periods.csv`, `block_map.csv`, `ts_fit.csv`, `ts_rescale.csv`,
  forced-period table (block, reason, value), dropped features.

**New health checks**
| Check | Rule |
|---|---|
| `ts.weights` | $\lvert\sum_pw_p-D_y/3\rvert\le10^{-9}$; $w_p\ge1$; forced $w_p=1$ exactly; $w_p=\sum_{\mathrm{rep}(j)=p}\omega_j$ recomputed from `block_map` |
| `ts.assignment` | every $j\in\bar{\mathcal J}$ mapped once; each representative block maps to its own period; forced blocks map to themselves; remainder not on a forced period |
| `ts.data_copy` | every period's pre-rescale $D$, $A$, $\phi$ equal the source case's representative block bit-for-bit |
| `ts.fit` | warn if system net load `dc_w1_rel` > 0.03, `energy_err_pre` > 0.05, `corr_max_abs` > 0.10, any $\lvert s_q-1\rvert$ > 0.05 or clipping residual > 0.5% (warn only, [P]) |
| `storage.link_recompute` | from **case data** $\sigma_r$ (never matrix coefficients) and the unscaled primal, run the chronological recursion over all $H_y$ hours from $B_{r,1}$ and compare to $e^{chr}$ and to every $B_{r,j}$; residual thresholds as `storage.soc_recompute` (§3 check 8) |
| `storage.link_bounds` | $-tol\le e^{chr}_{r,j,t}\le E_r+tol$ all $(j,t)$, $tol$ = §6.2 `bal` thresholds in MWh |
| `storage.link_duals` | the `soc_hi`/`soc_lo` stationarity identities above, rel $10^{-7}$ |

---

## Switches (ablation, docs/gates/README.md) — one complexity-ledger row each
| Key | Values (default) | Off state = |
|---|---|---|
| `ts.mode` | `full_blocks` \| `clustered` (capex runs: `clustered`; reference/backcast check: `full_blocks`) | all $J$ blocks |
| `ts.n_periods` | int incl. forced (default set by the Gate 5 sweep) | – |
| `ts.method` | `ward_medoid` | – |
| `ts.features.{load,wind,solar,net_load,fuel}` | weight ≥ 0 (1 each) | 0 |
| `ts.zone_weighting` | `energy` \| `equal` (`energy`) | `equal` |
| `ts.forced.{peak_load,peak_net_load,min_vre,max_fuel_price}` | bool (on) | off |
| `ts.forced.min_margin` | bool (off) | – |
| `ts.forced.events`, `ts.forced.fuel_hub` | list ([]), hub id (auto) | [] |
| `ts.rescale.{load,vre,fuel}` | bool (on) | off |
| `storage.inter_period` | `off` \| `flagged` \| `all` (`flagged`) | `off` |

---

## 9. Edits to other spec text (made at W-spec, listed here so the owner sees them)
- **E1** §1.2 remainder rule: "nearest period" → "nearest non-forced period" (clustered mode).
- **E2** data-schema §2.1: `rep_kind` gains `remainder` (source-case only); §2.2 unchanged.
- **E3** formulation §3 check 8: "§7.2 form when linked" now points to `st_soc` non-cyclic and `storage.link_recompute`.
- **E4** benchmarks.md regression rule: "5 clustering seeds" has no meaning without seeds → proposed ε = max(1% rel,
  spread of the metric over `n_periods` ∈ {n−2, …, n+2}) (owner decision, gate-5.md §7).

## Accuracy risks / open questions (owner)
- **R1** Net-load features and forced rules use the existing fleet. In expansion runs with large new VRE the critical
  periods move (future net load). Not fixed at Gate 5; candidate later fix: re-select periods once with the built fleet
  (iterative) — ledger row if tried.
- **R2** Medoids under-represent within-cluster tails; rescaling compresses shapes further. Measured by `dc_*`, `peak_err`.
- **R3** Unlinked storage wraps within 72 h: end-of-period artefacts for durations above ~12 h → flag such storage
  `long_duration`. RTS pumped storage (50 MW / 150 MWh, 3 h) stays unlinked under `flagged`.
- **R4** Fixed calendar grid splits events across blocks (Elliott → 2 forced periods), consuming the period budget.
- **R5** Daily fuel price: the medoid carries its own historical gas days, preserving weather–fuel co-movement for
  backcasts, but rescaling breaks exact history. **RTS-GMLC fuel prices are constant**, so the fuel feature and
  `max_fuel_price` cannot be scored on RTS; tested on a synthetic fixture, scored at Gate 12 (PJM daily gas).
- **R6** Forced periods count against `n_periods`; at small $n$ they dominate and few clusters remain.
- **R7** Remainder block under linking: objective weight covers 72 h, chronology uses $h_r$ h (non-leap years only).
- **R8** $\sigma>0$ linking is conservative (slightly under-uses storage).
- **R9** 3-day blocks blur weekday/weekend and miss weekly pumped-hydro cycles.
- **R10** Prices at capacity are non-unique before G7 (DECISIONS 23): price-duration comparisons use the fixed-fleet run
  or block averages.
- **R11** One weather year; inter-annual variability not represented (Pfenninger 2017).
- **R12** No thermal outages in features until G12 (RTS $A^{TH}=1$).

## References
- Ward, J. H. (1963). Hierarchical grouping to optimize an objective function. *J. Am. Stat. Assoc.* 58(301).
- Kotzur, L., Markewitz, P., Robinius, M., Stolten, D. (2018a). Impact of different time series aggregation methods on optimal energy system design. *Renewable Energy* 117.
- Kotzur, L., Markewitz, P., Robinius, M., Stolten, D. (2018b). Time series aggregation for energy system design: modeling seasonal storage. *Applied Energy* 213.
- Hoffmann, M., Kotzur, L., Stolten, D., Robinius, M. (2020). A review on time series aggregation methods for energy system models. *Energies* 13(3).
- Nahmmacher, P., Schmid, E., Hirth, L., Knopf, B. (2016). Carpe diem: A novel approach to select representative days for long-term power system modeling. *Energy* 112.
- Teichgraeber, H., Brandt, A. R. (2019). Clustering methods to find representative periods for the optimization of energy systems: An initial framework and comparison. *Applied Energy* 239.
- Poncelet, K., Höschle, H., Delarue, E., Virag, A., D'haeseleer, W. (2017). Selecting representative days for capturing the implications of integrating intermittent renewables in generation expansion planning problems. *IEEE Trans. Power Syst.* 32(3).
- Mallapragada, D. S., Papageorgiou, D. J., Venkatesh, A., Lara, C. L., Grossmann, I. E. (2018). Impact of model resolution on scenario outcomes for electricity sector system expansion. *Energy* 163.
- Merrick, J. H. (2016). On representation of temporal variability in electricity capacity planning models. *Energy Economics* 59.
- Gabrielli, P., Gazzani, M., Martelli, E., Mazzotti, M. (2018). Optimal design of multi-energy systems with seasonal storage. *Applied Energy* 219.
- Tejada-Arango, D. A., Domeshek, M., Wogrin, S., Centeno, E. (2018). Enhanced representative days and system states modeling for energy storage investment analysis. *IEEE Trans. Power Syst.* 33(6).
- Pfenninger, S. (2017). Dealing with multiple decades of hourly wind and solar data in energy models: A comparison of methods to reduce time resolution and the planning implications of inter-annual variability. *Applied Energy* 197.
- GenX documentation, Time Domain Reduction; tsam documentation (extreme-period methods); ReEDS documentation, representative periods (all: verify current versions).
