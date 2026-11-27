# Data schema — capex-model inputs and outputs

Version: **S-0.1** (Gate 0, W2). Matches `docs/formulation.md` F-0.1 (symbols, units §1.1, dollar-year §5,
audit §8, extensions §7). Provenance rule and estimation hierarchy: `docs/data-sources.md`.
Gate column = first gate that needs the table (G1 full detail; G3+ sketched: columns may be added, never
renamed or re-unit'd without bumping S-x.y and the loader).
G3-1 (DECISIONS 48, formulation F-0.3): `links.csv` network fields, `tx.*` switches, `dcpf` outputs and validation added.
All additive (no rename, no unit change), so the schema string stays `S-0.1`.
G3-6-fix1 (DECISIONS 51, formulation F-0.3 amendment 2): `switches`/`tolerances` key rules, `formulation_version`
(case vs code), `price_setter` list cells and `island_id` aligned with the formulation. Rules/wording only; `S-0.1` stays.
G4-1 (DECISIONS 56–57, formulation F-0.4): `links.link_type`, switch `tx.dc_links`, top-level `audit_profile`, the
F-0.4 version rule, `run.json` `excluded_links`, check `price_setter.loop_interval`, heat-rate derivation note. All
additive (absent column/key = previous behaviour), so the schema string stays `S-0.1`.

## 0. Global conventions
- **Formats.** CSV (UTF-8, header row, `.` decimal, ISO-8601 dates, empty = null) for G1–G4 and any table
  < 1e5 rows; Parquet with identical column names/types for large tables. Loader accepts either.
- **Layout.** `cases/<case_id>/case.yaml` + `cases/<case_id>/*.csv|parquet`. Shared reference data
  (deflator, source registry) in `data/common/`. Run outputs in `outputs/<run_id>/` (parquet + `run.json`).
- **Units = I/O units of formulation §1.1** (MW, MWh, $/MWh, $/MW-yr, ...). Column names carry units as a
  suffix (`_mw`, `_mwh`, `_usd_mwh`, `_usd_mw_yr`, `_mmbtu_mwh`, `_usd_mmbtu`, `_frac`, `_h`). No GW/M$ in files;
  scaling is internal (§6).
- **Time.** $\Delta t = 1$ h. Period `p` = representative 3-day block, `t` = 1..72 (hour 1 = first hour of the
  block, local prevailing time for backcasts; DST days resolved by the Gate-5 builder, not here).
- **Keys** are unique per table; ids are `[a-z0-9_]+`, case-sensitive, <= 48 chars.
- **Dollar year.** Every cost column is real $ of `dollar_year` (int, per row; one year per row, split rows if a
  row mixes years). Converted once, at load, by `capex.econ.to_base_dollars` to base 2024$ (DECISIONS 24):
  $C^{(B)} = C^{(y)}\,\mathrm{DEF}(B)/\mathrm{DEF}(y)$ with BEA GDP implicit price deflator (NIPA 1.1.9, annual).
  Deflator table: `data/common/deflator.csv` (§1.1). Original values and factors are kept in the assumptions book;
  the model never sees nominal numbers. Sub-annual series use the annual value of their calendar year.
- **Provenance** (every value-bearing table; field set P below).

### Provenance design: per-row default + per-cell override
**Fields P:** `source_id` (registry id), `vintage` (data year/release, text), `retrieved` (date),
`method` (`observed|derived|estimated|assumed`), `basis` (formula, regression/fit id, or citation),
`confidence` (`high|medium|low`), and `est_level` (1–4, the hierarchy level of `data-sources.md`; required when
`method` is `derived` or `estimated`, optional otherwise).

- **Entity tables** (resources, links, policy, ...): **P columns on every row** = default for all value cells of the row.
  Cells that differ (e.g. observed capacity but estimated heat rate) are listed in `provenance_cells.csv`
  (`table,row_key,column,source_id,vintage,retrieved,method,basis,confidence,est_level`), which overrides the row default.
  Rationale: one row per unit stays readable and diffable; per-cell provenance everywhere (wide `*_src` columns or tidy
  long-format values) triples width or breaks joins, yet the estimation hierarchy genuinely needs cell resolution for
  PJM fleet data (G11+). The loader writes `resolved_provenance.parquet`, one row per (table,row_key,column),
  which the assumptions book and the "share observed/estimated/assumed" statistics read.
- **Time-series tables** (load, profiles, fuel, outages): too large for per-row P. Provenance is **per series** in a
  companion `<table>_meta.csv` keyed by the series key (zone / resource / hub), with P (+ `dollar_year` if a cost).
- **Rejected:** a value-bearing table or series without P, `method=assumed` with `confidence=high`,
  `estimated`/`derived` without `basis`.

## 1. Case and scenario

### 1.1 `case.yaml` (manifest) — G1
| Key | Type | Meaning / feeds |
|---|---|---|
| `case_id`, `description` | str | label |
| `schema_version` | str | `S-0.1`; loader refuses mismatch |
| `formulation_version` | str | `F-0.2`, `F-0.3` or `F-0.4` (loader accepts all three; `tx.model: dcpf` requires `F-0.3` or `F-0.4`; the F-0.4 inputs `links.link_type`, `tx.dc_links` and `audit_profile` require `F-0.4`, else `DataError` naming the input; formulation §7.4a.9). This declared value is what `run.json` `formulation_version` reports; the fingerprint carries the **code's** version `capex.FORMULATION_VERSION` (`F-0.3` from Gate 3), not this field (formulation §8.10, F-0.3 amendment 2) |
| `base_dollar_year` | int | $B$ (2024) |
| `model_year` | int | $y$; fixes $D_y$ (365/366) |
| `dt_h` | float | must be 1.0 (asserted, §1.1) |
| `zones` / tables | list / map | `tables:` maps each logical table to a file with `sha256` (feeds fingerprint). Exception: the shared source registry `sources` (`data/common/sources.csv`) is listed **without** `sha256` (DECISIONS 40); its content still enters the run fingerprint as a canonical input table (formulation §8.10) |
| `switches` | map | all ablation keys: `ts.mode`, `ts.n_periods`, `ts.features.*`, `ts.forced.*`, `storage.inter_period`, `reserves.enabled`, `reserves.ordc`, `tx.model` (`transport` default \| `dcpf`), `tx.dcpf_form` (`angle` default \| `ptdf`), `tx.ref_bus` (zone id or list, ≤ 1 per island; formulation §7.4a.1), `tx.dc_links` (`controllable` default \| `exclude`; only with `tx.model: dcpf`, formulation §7.4a.12), `tx.losses/hurdle/expansion/interfaces`, `uc.*`, `policy.*`, `build.limits`, `retire.economic`, `calib.adders`, `deflate.monthly`, `scaling` (bool, default true = formulation §6.1 scaling on); absent = default-off. **Keys (F-0.3 amendment 2, formulation §7.4a.1):** a key the code does not implement is a load error (`DataError` naming the key) whatever its value, including the keys reserved above for later gates (`tx.losses`, `reserves.enabled`, …), which become valid in their own gate. Implemented at Gate 3: `tx.model`, `tx.dcpf_form`, `tx.ref_bus`, `scaling`; added at Gate 4: `tx.dc_links` (a `DataError` unless `tx.model: dcpf`). `tx.ref_bus` must be a string or a non-empty list of strings (else `DataError`; `[]` is an error, omit the key for the default; F-0.3 amendment 3) |
| `audit_profile` | str | F-0.4 (formulation §3 "Audit profile"): `exact` (default when absent) \| `standard`; any other value is a `DataError`. Sets the thresholds of `balance`, `storage.soc_recompute`, `kvl.recompute`, `ptdf.recompute`: `exact` pass ≤ 1e-6 MW/MWh; `standard` warn > 1e-3, fail > 1e-1. Test systems omit it; RTS-GMLC and PJM cases set `standard`. Enters the fingerprint config only when present |
| `voll_usd_mwh` | float | VOLL ($Z^{use}$, §2.3); G7+: backstop only (DECISIONS 24) |
| `finance_default` | str | `finance_class` used when a resource gives none |
| `solver` | map | name, options (algorithm, tolerances, crossover=true); all in fingerprint |
| `seed` | int | clustering seed (G5) |
| `tolerances` | map | `tol_q_mw`, `tol_pi_usd_mwh`, etc. (§4); under `dcpf` also `kvl_residual_mw`, `lmp_decomposition_usd_mwh`, `line_dual_usd_mwh`, `loop_alpha` (1e-6 each), `congestion_rent_rel` (1e-7) (formulation §7.4a.6). A key that is not a field of the run's tolerance set (Gate 1 keys; plus the §7.4a.6 keys only under `dcpf`) is a load error (`DataError`), never a Python `TypeError` (F-0.3 amendment 2). Under `audit_profile: standard` the keys `bal_residual_mw` and `kvl_residual_mw` are not in the tolerance set (`DataError`; F-0.4) |

### 1.2 `scenarios.csv` — G4 (single-scenario cases omit it)
| Column | Type | Meaning |
|---|---|---|
| `scenario_id` (key) | str | |
| `parent_id` | str | inherits parent overrides |
| `table`, `row_key`, `column`, `value` | str | cell override applied after load (replaces value; provenance auto-set `method=assumed`, `basis=scenario:<id>`) |
| `switch_key`, `switch_value` | str | switch override |
Scenario id enters the fingerprint; outputs live in `outputs/<run_id>/` with the `scenario_id` in `run.json`.

### 1.3 `data/common/deflator.csv` — G1
| Column | Type | Meaning |
|---|---|---|
| `year` (key) | int | calendar year |
| `gdp_deflator_index` | float | BEA annual GDP implicit price deflator (index, published base) → DEF(y) |
| `is_projection` | bool | true for years beyond latest BEA actual (filled from AEO macro series; flag, `method=assumed`) |
| `source_id` `vintage` `retrieved` `method` `basis` `confidence` | P | `bea_gdpdef` (actuals), `aeo` (projections) |
Required for every `dollar_year` and the base year; missing year = load error. Optional `deflator_monthly.csv`
(`year,month,index`) only with `deflate.monthly`.

## 2. Time structure

### 2.1 `periods.csv` — G1 (toy: 1 period; real: G5)
| Column | Type | Unit | Key | Feeds |
|---|---|---|---|---|
| `period_id` | str | | key | $p$ |
| `weight_blocks` | float | blocks | | $w_p$ (§1.2); identity $\sum_p w_p = D_y/3$ (tol 1e-9), $w_p\ge1$ |
| `rep_kind` | enum | | | `single` (toy), `medoid`, `forced`, `full_block` |
| `days_represented` | float | d | | $=3 w_p$ (cross-check) |
| `source_start_date` | date | | | G5+: real first day of the medoid block (backcast: ties profiles to history) |
| `forced_reason` | str | | | G5: `peak_load|peak_net_load|min_renewable|max_fuel_price|event:<name>` |
| `cluster_size_blocks` | int | | | G5: audit |
No P columns (derived by code, not data); `periods_meta.json` records clustering config/seed.

### 2.2 `block_map.csv` — G5 (chronology for inter-period SOC, reconstruction)
`block_j` (int key, 1..J), `block_start_date`, `period_id` ($\mathrm{rep}(j)$, §7.2), `weight_fraction` (1 or remainder
fraction, §1.2/§7.1). Feeds `st_link`; also the full-year dispatch check.

### 2.3 Demand `load.csv` — G1
| Column | Type | Unit | Feeds |
|---|---|---|---|
| `zone`, `period_id`, `t` | key (3-part) | | $D_{z,p,t}$ index |
| `demand_mw` | float >= 0 | MW | $D_{z,p,t}$ (net of BTM as supplied; `load_meta` says whether BTM removed) |
Series meta `load_meta.csv`: `zone`, P, `net_of_btm` (bool), `year`. Backcast load = PJM metered/forecast zonal load (G11).

## 3. Network and resources

### 3.1 `zones.csv` — G1
`zone_id` (key), `name`, `rto` (`PJM`...), `state_shares_ref` (G10: points to `zone_state_share`), `reserve_area` (G7), P.
Feeds $\mathcal Z$. (Not value-bearing for G1 toy; P optional there, required from G3.)

### 3.2 `links.csv` — G1 (G3 adds network fields, G8 adds losses/expansion)
| Column | Type | Unit | Gate | Feeds |
|---|---|---|---|---|
| `link_id` (key) | str | | 1 | $l$ |
| `zone_from`, `zone_to` | str | | 1 | $o(l)$, $e(l)$ (must differ) |
| `ntc_fwd_mw`, `ntc_rev_mw` | float >= 0, `inf` or blank | MW | 1 | $F^+_l$, $F^-_l$ (`transport`); under `dcpf` the line rating $F_l$ (both equal). Blank = `inf` = unlimited (G3, both models) |
| `reactance_pu` | float > 0 | pu on `base_mva` | 3 | series reactance $x_l$; $b_l=\texttt{base\_mva}/x_l$ MW/rad (formulation §7.4a.2). Required under `dcpf`; ignored (type-checked only) under `transport` |
| `base_mva` | float > 0 | MVA | 3 | per-unit base of `reactance_pu` (100 for `pjm5`); required under `dcpf` (AC rows) |
| `link_type` | enum `ac`\|`dc`, blank = `ac` | | 4 | F-0.4 (formulation §7.4a.12). Column optional; absent or blank = `ac`, so existing cases are unchanged. `dc` = controllable DC link: under `dcpf` a `flow` column with no `kvl` row, not part of any island; under `transport` validated, then treated as an ordinary link. A `dc` row must have blank `reactance_pu` and `base_mva`, and may have `ntc_fwd_mw` ≠ `ntc_rev_mw` |
| `loss_frac` | float [0,1) | – | 8 | $\lambda_l$ |
| `hurdle_usd_mwh` | float >= 0 | $/MWh | 8 | $h_l$ |
| `capex_usd_mw`, `fom_usd_mw_yr`, `life_yr`, `finance_class`, `x_max_mw` | | | 8 | expansion $y_l$, ANN |
| `dollar_year` + P | | | 1 | |
Provenance: the row's P fields cover `reactance_pu`/`base_mva` (e.g. `pjm5`: `source_id=pjm5`, `method=observed`, basis
`case5.m branch x, rateA`); zonal equivalents (G10) are `derived` with `basis` = the reduction method. Parallel lines are
separate rows with distinct `link_id` (same or opposite orientation allowed); `link_id` must be unique (key).
Optional `interfaces.csv` + `interface_links.csv` (G8): `iface_id, limit_mw_fwd, limit_mw_rev`; `iface_id, link_id, beta`.

### 3.3 `resources.csv` — G1 (existing + candidate; one row per resource or cluster)
| Column | Type | Unit | Applies | Feeds |
|---|---|---|---|---|
| `resource_id` (key) | str | | all | $r$ |
| `zone` | str | | all | $z(r)$ |
| `type` | enum `TH|VRE|ST` | | all | $\mathcal R^{TH},\mathcal R^{VRE},\mathcal R^{ST}$ |
| `tech` | str | | all | reporting; price-setter tech |
| `fuel` | str, nullable | | required: TH without `mc_override`; optional: VRE, ST | `fuel_map` -> hub (TH); price-setter fuel (null reported as `none`). The column may be absent if no row requires it (DECISIONS 31) |
| `status` | `existing|candidate` | | all | G1 data rule: existing ($K^0>0,X^{max}=0$) xor candidate ($K^0=0,X^{max}>0$) |
| `k0_mw` | float >= 0 | MW | TH,VRE | $K^0_r$ ; ST: $P^0_r$ |
| `e0_mwh` | float >= 0 | MWh | ST | $E^0_r$ |
| `xmax_mw` | float >= 0 or `inf` | MW | TH,VRE; ST | $X^{max}_r$; ST: $X^{P,max}_r$ |
| `xmax_mwh` | float >= 0 or `inf` | MWh | ST | $X^{E,max}_r$ |
| `heat_rate_mmbtu_mwh` | float > 0 | | TH w/ fuel | $HR_r$ (incremental). From a piecewise fuel curve: secant $(F_N-F_0)/(P_N-P_0)$, or full-load average $F_N/P_N$ if the curve is flat, no no-load term; cell provenance `derived`, est_level 1 (formulation §2.4, DECISIONS 57). Intercept kept in `x_noload_mmbtu_h` for the UC gate |
| `vom_usd_mwh` | float >= 0 | $/MWh | TH,ST | $VOM_r$ (ST: per MWh discharged) |
| `mc_override_usd_mwh` | float | $/MWh | TH,VRE | optional; if set replaces $HR\phi+VOM$ (toys T1–T4 use it: $MC=20$ etc.). VRE without it: $MC=0$ (zero fuel cost, no VOM; never perturbed, formulation §6.1e), whether or not `fuel` is given |
| `fom_usd_mw_yr` | float >= 0 | $/MW-yr | all | $FOM_r$ ($FOM^P_r$ for ST) |
| `fom_usd_mwh_yr` | float >= 0 | $/MWh-yr | ST | $FOM^E_r$ |
| `capex_usd_mw` | float >= 0 | $/MW | candidate | $I_r$ ($I^P_r$ for ST) |
| `capex_usd_mwh` | float >= 0 | $/MWh | cand. ST | $I^E_r$ |
| `cfix_override_usd_mw_yr`, `cfix_e_override_usd_mwh_yr` | float | | candidate | bypass annualize with given $C^{fix}$ / $C^E$ (toys: T1 $C^{fix}=150000$); flagged in assumptions book |
| `life_yr`, `finance_class` | int, str | | candidate | $n$, key into `finance.csv` |
| `construction_profile_id` | str | | candidate | optional key into `construction_profiles.csv` ($\phi_k$) |
| `eta_c_frac`, `eta_d_frac` | float (0,1] | | ST | $\eta^c,\eta^d$ |
| `selfdis_frac_h` | float [0,1) | 1/h | ST | $\sigma_r$ |
| `dur_min_h`, `dur_max_h` | float >= 0 (null = none) | h | cand. ST | $\underline\delta,\overline\delta$ |
| `long_duration` | bool | | ST | G5 inter-period flag |
| `dollar_year` | int | | rows with cost | §0 |
| P | | | all | per-row default; cell overrides in `provenance_cells.csv` |
Later columns (null in G1): `pmin_frac`, `unit_size_mw`, `ramp_up_mw_h`, `ramp_dn_mw_h`, `min_up_h`, `min_dn_h`,
`start_cost_usd_mw`, `no_load_usd_h`, `reserve_ramp_frac_min` (G7/G9), `er_tco2_mwh` / `co2_lb_mmbtu` (G10),
`elcc_class` (G14), `in_service_date`, `retire_date`, `rmr` (bool), `keep_mw` ($K^{keep}$), `gfc_usd_mw_yr` (G10),
`eia_plant_id`, `eia_gen_id`, `ori_unit_ids` (G11: link to EIA/CEMS/PJM ids).
**Existing fleet at scale (G11+)** is built by the pipeline from EIA-860/NEEDS into this same table; the raw
unit-level table is `fleet_units.parquet` (one row per generator, P per cell via the cell-override table) and
`resources.csv` is its clustered image (G18); `cluster_map.csv` (`unit_id, resource_id, share`) keeps the trace.

### 3.4 `finance.csv` — G1 (feeds `capex.econ.annualize`; DECISIONS 22)
| Column | Type | Unit | Feeds |
|---|---|---|---|
| `finance_class` (key) | str | | |
| `mode` | `simple_crf|atb_pff` | | switch between real-WACC CRF and ATB-style PFF |
| `wacc_real_frac` | float | – | $r$ (real; if nominal supplied: `wacc_nominal_frac`+`inflation_frac` and loader applies Fisher, §5.1) |
| `pff` | float > 0 | – | PFF (default 1); for `atb_pff` derived per tech from ATB CRF/simple-CRF or from the inputs below |
| `debt_frac`, `debt_rate_nominal`, `equity_rate_nominal`, `tax_rate`, `macrs_class_yr` | float/int | | optional ATB-style inputs to derive PFF |
| P | | | |
`construction_profiles.csv`: `profile_id, k (1..L), share_phi` ($\sum_k\phi_k=1$). Both feed the annualization table of
the assumptions book ($I, r, n, \kappa, \mathrm{PFF}, \mathrm{CRF}, C^{fix}$ per resource).

### 3.5 `availability.csv` — G1 (long, sparse: omitted rows = default)
| Column | Type | Unit | Feeds |
|---|---|---|---|
| `resource_id`, `period_id`, `t` | key | | |
| `availability_frac` | float [0,1] | – | $A_{r,p,t}$ (VRE: capacity factor; TH: 1 − derate/outage). Default 1 for TH, **required for every (VRE,p,t)** |
Meta `availability_meta.csv` keyed by `resource_id` (VRE) or by `profile_id`: P + `profile_year`, `weather_year`.
Values < 1e-3 are zeroed at build and counted (§6.1b). G12 adds `outages.csv` (§9) from which TH $A$ is built.

### 3.6 `fuel_prices.csv` — G1 (toy may use `mc_override`; real: daily hub gas)
| Column | Type | Unit | Feeds |
|---|---|---|---|
| `fuel_hub`, `period_id`, `t` | key | | |
| `price_usd_mmbtu` | float >= 0 | $/MMBtu | $\phi_{f,p}$ — **hourly-resolved** to carry the 3 daily prices of a block (see Spec issues) |
Meta `fuel_prices_meta.csv` keyed by `fuel_hub`: P + `dollar_year` + `price_basis` (`nominal_as_reported`; deflated at load),
`license_class` (see data-sources). `fuel_map.csv`: `fuel`, `zone` (opt.), `fuel_hub` (e.g. gas in Dominion zone -> `dom_south`+basis rule).
Raw daily history (G11): `fuel_prices_daily.parquet` (`fuel_hub, date, price_usd_mmbtu, dollar_year`), medoid blocks sample from it via `periods.source_start_date`.
Adders (delivery, basis, CO$_2$ via G10) are separate columns/tables, never folded silently into price.

## 4. Storage-specific, reserves, policy, limits (sketch)

| Table | Gate | Key | Columns (sketch) | Feeds |
|---|---|---|---|---|
| `reserve_products.csv` | 7 | `product_id` | `deploy_time_min`, `nests_into` (higher quality counts to lower), P | $k,\tau_k,\mathcal K_k$ |
| `reserve_requirements.csv` | 7 | `product_id,reserve_area,period_id,t` | `requirement_mw`, P | $\sum_s\Delta_{k,s}$ |
| `ordc_curve.csv` | 7 | `product_id,reserve_area,step_s` | `width_mw` ($\Delta_{k,s}$), `penalty_usd_mwh` ($P_{k,s}$), `dollar_year`, `effective_from`, P | PJM ORDC (post-2022) |
| `losses_hurdles` in links | 8 | | see 3.2 | |
| `uc_params` in resources | 9 | | see 3.3 | $\bar P, P^{min}, RU, UT, DT, SC, NL$ |
| `policy_rps.csv` | 10 | `state,tier,year` | `target_frac` ($\kappa_s$), `acp_usd_mwh` ($P^{ACP}_s$), `dollar_year`, `eligible_techs`, P | `rps[s]` |
| `policy_elig.csv` | 10 | `state,resource_id` | `theta_frac` ($\theta_{r,s}$) | |
| `zone_state_share.csv` | 10 | `state,zone` | `beta_frac` ($\beta_{s,z}$) | |
| `rggi.csv` | 10 | `state,year` | `member` (bool), `allowance_usd_short_ton`, `dollar_year`, P | $P^{CO2}_{s,y}$; membership by year (VA exit) |
| `emission_factors.csv` | 10 | `fuel` | `co2_short_ton_mmbtu`, P | $ER_r = HR\cdot EF$ |
| `federal_credits.csv` | 10 | `tech,in_service_year` | `ptc_usd_mwh`, `itc_frac`, `phaseout_frac`, `dollar_year`, `law_ref`, P | PTC as −MC; ITC reduces $I$ |
| `build_limits.csv` | 10 | `tech,zone,year` | `max_mw_per_year` ($B_{g,z,y}$), basis = queue/interconnection data, P | `build_lim` |
| `retirements.csv` | 10 | `resource_id` | `retire_date`, `announced` , `rmr`, `keep_mw`, `gfc_usd_mw_yr`, `dollar_year`, P | announced/RMR fixed, GFC |
| `elcc.csv` | 14 | `class,year` | `elcc_frac` , P | ELCC-accredited supply |
| `vrr_curve.csv` | 14 | `lda,delivery_year,point` | `price_usd_mw_day`, `quantity_mw`, `cone_usd_mw_day`, `net_cone`, `dollar_year`, P | VRR demand curve |
| `rpm_results.csv` | 14,17 | `lda,delivery_year` | `clearing_price_usd_mw_day`, `cleared_mw` (benchmark only) | scoreboard |
| `queue.csv` | 10,16 | `project_id` | `zone,tech,mw,status,cod,source` | basis for `build_limits` |
| `outages.csv` | 12 | `resource_id,period_id,t` or `resource_id,month` | `forced_outage_frac`, `planned_outage_frac`, `derate_frac`, P (meta) | $A_{r,p,t}$ |
| `imports.csv` | 12 | `zone,period_id,t` | `net_import_mw` (fixed ext. interchange in backcast), P(meta) | fixed injection into `bal` |
| `dr_programs.csv` | 12 | `program_id` | `zone,mw,max_hours,call_cost_usd_mwh,dollar_year`, P | DR as thermal-like resource |
| `benchmarks_*.parquet` | 4,12,14 | | observed DA/RT LMP (zone,date,hour), IMM marginal fuel shares, EIA-923 monthly gen, RPM prices, IMM storage revenue; P(meta) | scoreboard (`docs/benchmarks.md`); never enter the LP |

## 5. Outputs (`outputs/<run_id>/`) — all in I/O units, base 2024$, real; weights applied only where stated
Every output table belongs to one run through its directory `outputs/<run_id>/`; tables do not repeat `run_id` as a
column, so that canonical outputs are byte-identical across runs (formulation §8.10, amendment 4); a reader that stacks
runs adds `run_id` from `run.json`. Raw duals use the canonical convention (§1.3); economic quantities per §3.

| File | Gate | Key | Columns | Notes (audit §8) |
|---|---|---|---|---|
| `run.json` | 1 | – | (F-0.4) `excluded_links` (ids of `dc` rows dropped by `tx.dc_links: exclude`; empty list otherwise; non-canonical), `run_id`, `fingerprint` (SHA-256), `case_id`, `scenario_id`, `formulation_version` (the case's declared `case.yaml` value; the fingerprint hashes the code's `capex.FORMULATION_VERSION` instead, F-0.3 amendment 2), `schema_version`, `git_commit`, `dirty_diff_hash`, `solver`, `solver_version`, `solver_options`, python/package versions, `seed`, timestamps, `solve_time_s`, `rows`, `cols`, `nnz`, `status`, `valid` (false if any conditioning fail), `crossover_ran` | §8.10; same fingerprint => identical outputs |
| `dispatch.parquet` | 1 | `resource_id,period_id,t` | `g_mw`, `curtail_mw`, `charge_mw`, `discharge_mw`, `soc_mwh` (unserved energy is in `zone_hourly`) | primal; $w_p$ in `weights` join |
| `zone_hourly.parquet` | 1 | `zone,period_id,t` | `demand_mw`, `unserved_mw`, `lmp_usd_mwh` ($\pi=y/w_p$), `bal_residual_mw`, `weight_hours` | prices & balance check |
| `flows.parquet` | 1 | `link_id,period_id,t` | `flow_mw`, `congestion_rent_usd_mwh` ($\mu$), `at_bound` | under `dcpf`: same columns; $\mu=-s_f/w$, signed, $\mu f\ge0$ (formulation §7.4a.5) |
| `zone_hourly` (dcpf columns) | 3 | as `zone_hourly` | `lmp_energy_usd_mwh` ($\lambda$ at the island reference bus), `lmp_congestion_usd_mwh` ($-\sum_l H_{l,n}\mu_l$), `lmp_loss_usd_mwh` (0), `island_id`, `ref_zone` | only under `dcpf`; components depend on the reference bus, the total does not |
| `angles` | 3 | `zone,period,t` (as `zone_hourly`) | `theta_rad`, `island_id`, `is_ref`, `theta_source` (`lp`\|`recomputed`) | only under `dcpf` (§7.4a.8) |
| `islands` | 3 | `zone` | `island_id`, `ref_zone` | only under `dcpf` |
| `price_setter_loop` | 3 | `zone,period_id,t,resource_id` | `alpha` (–, may be < 0 or > 1, sums to 1 per bus-hour), `cost_usd_mwh`, `setter_zone`, `case` (`unique`\|`weights_nonunique`) | only under `dcpf`; `CONGESTION_LOOP` weights (§7.4a.7) |
| `capacity.parquet` | 1 | `resource_id` | `existing_mw`, `new_mw`, `existing_mwh`, `new_mwh`, `at_xmax`, `x_reduced_cost_usd_mw_yr` | $x,x^P,x^E$ |
| `duals_raw.parquet` | 1 | `label,index` | `dual` (canonical), `slack`, `basis_status`, `weight` | all row families + `x_ub`, `flow_*`, `use_ub` bounds |
| `rents.parquet` | 1 | `resource_id` | `kind` (generator tech kind, or `ST` for storage); **\$/yr:** `energy_revenue`, `variable_cost`, `fixed_cost` (total fixed cost of built + existing capacity), `profit`, `revenue_identity_residual`; **\$/MW-yr (per unit of capacity):** `rent_cap_usd_mw_yr` ($R$, generators), `rent_pwr` ($R^P$), `cfix` (generators $C^{fix}$; storage $C^P+\delta C^E$ with $\delta$ the fixed duration, $\delta=0$ if duration is free), `excess_rent` (rent − `cfix`, candidates only); **\$/MWh-yr:** `rent_en` ($R^E$); **flags:** `build_status` (`at_zero`/`interior`/`at_max`/`existing`), `zero_profit_ok`, `rent_note` (`non-unique (bound)` for candidates at `at_zero`, else empty) | §8.5, checks §3.5–3.6. Per-unit and total columns differ by the capacity: e.g. T2b `bat` `cfix` 12,000 \$/MW-yr vs `fixed_cost` 120,000 \$/yr (C1) |
| `price_setter.parquet` | 1 | `zone,period_id,t` | `primary_class`, `all_classes`, `setter_ids`, `setter_tech`, `setter_fuel`, `setter_zone`, `price`, `setter_cost`, `residual`, `island_id`, `binding_links`, `flags` (`IMPORT`,`CONGESTED`,`INVESTMENT_MARGIN`,`DEGENERATE`,`UNEXPLAINED`), `price_lo`, `price_hi`, `rent_ids` (`CAPACITY_RENT` rent set; `setter_ids` holds only the attributed subset). **List cells** (formulation §4 "List cells", F-0.3 amendment 2): items joined by `,` with no spaces; `setter_ids` in the class pool's row order (generators or storage in `resources.csv` order, unserved energy as `unserved:<zone>` in `zones.csv` order; `CONGESTION_LOOP`: by bus in `zones.csv` order, by id within a bus = `price_setter_loop` row order) — not sorted; `setter_tech`, `setter_fuel`, `setter_zone`, `rent_ids` distinct values sorted lexicographically; `binding_links` in `links.csv` row order; `all_classes` in evaluation order, total blackout `VOLL:BLACKOUT`; `flags` in the order `UNEXPLAINED`, then `DEGENERATE` or `INVESTMENT_MARGIN`, `BLACKOUT`, `IMPORT`, `CONGESTED`, `LINK_INCONSISTENT`. `island_id` integer: under `transport` the 0-based price-island label of the hour (connected component, per hour); under `dcpf` the $k$ of electrical island `i`$k$ (formulation §7.4a.2) | §4 |
| `price_setter_summary.parquet` | 1 | `zone,tech,fuel,class` | `share_weighted_hours`, `weighted_hours` | IMM comparison metric |
| `objective.parquet` | 1 | `component,id` | `component` (`Z_inv`,`Z_var`,`Z_use`,`Z0`), `id` (resource/zone/fuel), `value_usd_yr`; plus `total` row | sums to $Z$ within 1e-9 rel. |
| `annualization.parquet` | 1 | `resource_id` | `I`, `dollar_year_in`, `deflator_factor`, `r`, `n`, `kappa`, `pff`, `crf`, `ann`, `fom`, `cfix` | §5.2 print |
| `binding.parquet` | 1 | `family` | `n_rows`, `n_binding`, `weighted_share_binding`, plus bound list | §8.3 |
| `storage.parquet` | 1 | `resource_id,period_id,t` | `soc_mwh`, `water_value_usd_mwh` ($v$), `simul_chdis` flag; per-period `cyclic_closure_residual` | §8.6 |
| `curtail_unserved.parquet` | 1 | `zone|resource,...` | weighted annual MWh by zone/period | §8.8 |
| `health.parquet` | 1 | `check_id` | `family` (`balance`,`strong_duality`,`comp_slack`,`dual_sign`,`zero_profit`,`revenue_identity`,`price_setter`,`conditioning`,`storage`,`decomposition`, `network` (G3, dcpf only)); F-0.4 adds check `price_setter.loop_interval` (dcpf only, value = count, pass 0), `status` (`pass|warn|fail`), `value`, `tolerance`, `detail` | gate evidence |
| `conditioning.json` | 1 | – | §6.2 metrics (matrix/obj/RHS ranges, ratios, tiny-coefficient count, max infeasibilities, residual) | |
| `assumptions.md` + `assumptions_cells.parquet` | 1 (full G16) | – | see `docs/data-sources.md` "Assumptions book" | |
| `reserve_prices.parquet` | 7 | `product,area,p,t` | `price_usd_mwh`, `shortfall_mw` | |
| `scoreboard.parquet` | 4+ | `metric,scope` | `value`, `benchmark`, `error`, `target`, `holdout` | `docs/benchmarks.md` |

## 6. Validation rules (loader rejects; `capex.data.validate`)
Errors abort the run before the LP is built; warnings go to `health.parquet`. IDs below refer to tables above.
1. **Schema:** `schema_version` and `formulation_version` match; every required file/column present; no unknown columns
   (unless prefixed `x_`); types parse; no NaN/null in non-nullable columns; keys unique; file `sha256` equals manifest wherever the manifest gives one (every table except the `sources` registry, DECISIONS 40).
2. **Units/ranges:** column suffix units only; `demand_mw >= 0`; `availability_frac in [0,1]`; `eta in (0,1]`;
   `selfdis in [0,1)`; capacities, NTC, costs, heat rates >= 0 (HR > 0 where fuel used); `loss_frac in [0,1)`;
   `dur_min <= dur_max`; `xmax` may be `inf` but never a large sentinel (>= 1e6 MW is an error; no big-M, §6.1c); `dt_h == 1`.
   NTC/rating: blank or `inf` = unlimited; a finite value >= 1e6 MW is an error (sentinel).
3. **Time:** periods cover `t = 1..72` exactly for every (zone,p) in `load`, every (VRE,p) in `availability`, every
   (hub,p) in `fuel_prices` used by a resource; weights satisfy $\sum_p 72 w_p = H_y$ (1e-9) and $w_p \ge 1$ (§1.2);
   `days_represented = 3 w_p`; `block_map` covers 1..J and references existing periods (G5).
4. **Referential integrity:** `zone`, `zone_from/to`, `resource_id`, `finance_class`, `fuel_hub`, `source_id`,
   `profile_id` all resolve; links join distinct zones; every zone has load.
5. **Gate-1 data rule:** resource `status=existing` => `k0>0` and `xmax=0`; `candidate` => `k0=0` and `xmax>0`. Types
   require their columns (ST: eta_c, eta_d, e0 / xmax_mwh; TH: HR and a `fuel` that maps to a hub, or `mc_override`;
   VRE: neither `fuel` nor `mc_override` required — missing both means $MC=0$).
   Candidates need (`capex`,`life_yr`,`finance_class`) **or** `cfix_override`.
6. **Dollar year:** every cost column row has `dollar_year`; it exists in `deflator.csv`; `base_dollar_year` exists; a
   cost with `dollar_year > base` is allowed only if the deflator row is a projection (flagged). Cost columns with
   no `dollar_year` => error. Negative cost columns allowed only for named credit columns (`ptc_*`).
7. **Provenance:** all P fields present on every row/series; `method` and `confidence` in enums; `source_id` in registry
   (`data/common/sources.csv`, mirrors `docs/data-sources.md`); `retrieved` <= today and `retrieved >= vintage` year start;
   `estimated|derived` needs `basis` + `est_level in 1..4`; `assumed` cannot be `high`; every cell override points at an
   existing (table,row_key,column); resolved provenance has no blanks.
8. **Financial:** `wacc_real > -1`, `life >= 1`, `construction_profile` shares >= 0 sum to 1 (1e-9); ANN >= I/n for r >= 0 (§5.2).
9. **Economics sanity (warn):** VOLL < max MC or < max ORDC penalty; candidate `cfix` outside [0.2x, 5x] of tech median;
   total existing capacity < peak demand with no unserved allowance; any VRE capacity factor series with annual mean outside
   [0.02, 0.95]; weights with >30% in forced periods.
10. **Scenario:** overrides target existing cells and types stay valid (re-run 1–9 after applying).
11. **Network (G3, formulation §7.4a):** `tx.model` in {`transport`,`dcpf`}, `tx.dcpf_form` in {`angle`,`ptdf`}, every
    `tx.ref_bus` entry is a zone id and at most one per island, and a list is non-empty (`[]` = `DataError`, F-0.3 amendment 3); `switches` keys only from the implemented set and
    `tolerances` keys only from the run's tolerance set (§1.1 `case.yaml` rows; unknown key = `DataError`, F-0.3 amendment 2). Under `dcpf` (errors): every link has `reactance_pu > 0`
    and `base_mva > 0`; `ntc_fwd_mw == ntc_rev_mw` (both blank or equal; symmetric rating); a rating of 0 is an error
    (delete the row to open a line); `formulation_version: F-0.3` or `F-0.4`. **DC links (G4, F-0.4, formulation §7.4a.12;
    errors in both network models):** `link_type` not in {`ac`, `dc`, blank}; a `dc` row with a non-blank `reactance_pu` or
    `base_mva`; a `dc` row with `ntc_fwd_mw` or `ntc_rev_mw` = 0 (each must be > 0 or blank = unlimited); `tx.dc_links` not
    in {`controllable`, `exclude`}, or given without `tx.model: dcpf`; any F-0.4 input with `formulation_version` ≠ `F-0.4`.
    Under `dcpf` the AC-only rules above (reactance, `base_mva`, symmetric rating) apply to `ac` rows only, and islands are
    built from `ac` rows only. `audit_profile` not in {`exact`, `standard`} is a `DataError`. Under `dcpf` (warn): $b_l > 10^{6}$ MW/rad
    (`reactance_pu` tiny vs base) or $\max b/\min b > 10^{4}$ (conditioning, §6.2). Under `transport`: `reactance_pu`,
    `base_mva` may be blank; if present they must parse as floats; never used.
12. **Policy (G10):** state tiers' `target_frac in [0,1]`; `zone_state_share` sums to 1 per zone; RGGI membership year ranges
    non-overlapping. **Fuel (G1+):** no hub price gaps within modeled hours; no negative gas price unless `allow_negative_fuel`.

## 7. Spec issues this schema depends on (for formulation F-0.2; not edited here)
- **Fuel price index.** F-0.1 indexes $\phi_{f,p}$ by period only, but a 3-day block holds 3 daily gas prices. Schema uses
  $(f,p,t)$ so $MC_{r,p,t}$ is exact; needs formulation change (or a stated 3-day average with its accuracy cost).
- **DC power flow (G3).** Resolved in formulation F-0.3 §7.4a (DECISIONS 48).
- **Key-column names (open, pre-existing).** Gate-2 code writes `zone,period,t` / `link,period,t` / `resource,period,t`
  for `zone_hourly`, `flows`, `dispatch` (and `g_mw`), while this file says `period_id`, `link_id`, `resource_id`;
  `price_setter` uses `period_id`. Not renamed in G3 (would break the `transport` byte-identity rule); new dcpf tables
  follow the table they mirror. To be reconciled in one later schema bump.
- **Financing default.** DECISIONS 22 makes ATB-style PFF the default; F-0.1 §5.2 still says PFF=1 default and Q1–Q4 open.
