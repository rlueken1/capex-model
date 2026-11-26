# EIA-860 / EIA-923 field mapping and estimation hierarchy (P10)

**STATUS: DRAFT for owner review.** Gate 11 (PJM single-zone slice) and Gate 16 (full pipeline) use.
Author: data lead, 2026-11-26. Written without network access: EIA file layouts, column names and literature
numbers are from memory. **Every item marked `(verify)` must be checked against the real files (first
GitHub Actions run, or the owner) before a loader is written.** Nothing here is code or a settled decision.
Governing docs: `docs/data-sources.md` (provenance rule, hierarchy), `docs/data-schema.md` S-0.1 (targets),
DECISIONS 16 (provenance mandatory), 26 (buy nothing, simplest model first), 15 (PJM only), 5-bus/rep-period
structure in DECISIONS 3.

---------------------------------------------------------------------------------------------------

## 1. Scope and sources

| source_id | File / sheet | Role in the model |
|---|---|---|
| `eia860` | Annual EIA-860 zip. Schedule files (names as in recent releases, verify): `1_Utility`, `2___Plant`, `3_1_Generator` (tabs: Operable, Proposed, Retired and Canceled), `3_2_Wind`, `3_3_Solar`, `3_4_Energy_Storage`, `3_5_Multifuel`, `6_1_EnviroAssoc`, `6_2_EnviroEquip` (verify) | Fleet backbone: id, plant, zone inputs, tech, capacity, dates, storage |
| `eia860` (monthly) | EIA-860M (monthly status workbook: operating, planned, retired, canceled/postponed tabs; verify) | Status changes since the annual vintage: new COD, retirements, delays. Used for forward runs and the build-limit baseline; not for characteristics |
| `eia923` | Annual final zip `f923_<year>`. Pages: Page 1 Generation and Fuel Data; Page 3 Boiler Fuel Data; Page 4 Generator Data; Page 5 Fuel Receipts and Costs (verify page numbering) | Net generation, fuel use (heat rates), delivered fuel cost, monthly benchmarks |
| `pudl` | Catalyst Cooperative PUDL tables (`out_eia__yearly_generators`, `core_eia923__monthly_generation_fuel`, `core_eia860__scd_generators`, EIA-EPA crosswalk; table names verify) | Preferred cleaned alternative: harmonised ids, fixed units/codes, pre-built plant-part allocation of 923 fuel to generators, CEMS-to-EIA crosswalk. Cite release DOI. Pin the release as `vintage` |

Access and storage follow `data-sources.md` "Data acquisition plan": raw files are downloaded only in GitHub
Actions (manifests `data/manifests/eia860.csv`, `eia923.csv`, both `enabled=false` until Gate 11/16, URL pattern
and sha256 unverified). Raw EIA files are public domain, but raw data is never committed (DECISIONS 28).

**Vintage handling.**
- Primary: **final annual** release (860 final ~Sep-Oct of year+1; 923 final ~Sep-Nov of year+1; verify).
  `vintage` = the data year (e.g. `2023`), plus release flag `final|early` in `basis`.
- Early release (860 and 923 "Early Release", ~Feb-Mar; verify) only for a backcast year with no final data; every
  cell touched is `confidence` capped at `medium` and flagged `early_release` in `basis`.
- Never mix: capacity/status from 860 year Y with 923 generation for year Y. A multi-year heat-rate fit uses
  explicit Y-1, Y, Y+1 only when stated in `basis`.
- 860M overlays carry their own `vintage` (`2023-11` style) and `source_id=eia860` with `basis` "860M status overlay".

**Filter to PJM.** Plant file `Balancing Authority Code == 'PJM'` (verify exact column title) gives the PJM BA footprint.
Known pitfalls: (a) the BA code is a plant attribute as of the survey year; plants can change BA (e.g. into/out of
PJM); (b) some plants are blank or `NA`; (c) behind-the-meter and distribution-connected small units exist under PJM
(keep, but flag; the model's demand is net of BTM only if `load_meta.net_of_btm` says so); (d) Dominion's DOM zone and
all PJM zones share BA code `PJM`; the BA field does not give a zone. **Zone assignment is a gap** (section 6).

---------------------------------------------------------------------------------------------------

## 2. Field-by-field mapping

Target tables: `fleet_units.parquet` (unit level, one row per generator; schema 3.3 final paragraph) which is clustered
to `resources.csv` at G18. Column names are the schema columns; `-` means no target column today (see gaps, section 6).
Provenance for every cell is as in section 5. "Method" is the default; the estimation fallbacks of section 4 apply
wherever the EIA cell is blank, zero or fails sanity bands.

### 2.1 860 Plant and Generator (operable) fields

| EIA file / sheet | EIA column (exact where known) | Schema target | Units / transform | Method |
|---|---|---|---|---|
| 3_1 Gen | `Plant Code` | `eia_plant_id` (int) | as is | observed |
| 3_1 Gen | `Generator ID` | `eia_gen_id` (str); `resource_id` = `eia_<plant>_<gen>` lower-cased, `[^a-z0-9]`->`_`, collisions suffixed `_2`; <= 48 chars | sanitise; keep original in `eia_gen_id` | derived (id rule in `basis`) |
| 3_1 Gen | `Utility ID`, `Utility Name`; 1_Utility | `x_utility_id` (extra col, prefix `x_` allowed) | as is | observed |
| 3_1 Gen | `Plant Name`, `State`, `County` | `x_plant_name`, `x_state`, `x_county` | as is. State feeds `zone_state_share` (G10) and the zone fallback | observed |
| 2 Plant | `Balancing Authority Code` | filter only (`x_ba_code`) | `== PJM` | observed |
| 2 Plant | `Transmission or Distribution System Owner`, `... ID` (verify) | `zone` (via zone map, see 6) | lookup table `data/common/pjm_zone_map.csv` (to be created) | assumed (map) / derived |
| 2 Plant | `Latitude`, `Longitude` | `x_lat`, `x_lon` | optional, for zone fallback and weather matching | observed |
| 3_1 Gen | `Prime Mover` | `x_prime_mover`; with energy source -> `tech` (table 2.2) | code lookup | derived |
| 3_1 Gen | `Technology` (descriptive text, e.g. "Natural Gas Fired Combined Cycle") | cross-check of `tech`; mismatches logged | text | observed |
| 3_1 Gen | `Energy Source 1` ... `Energy Source 6` | `fuel` (primary = ES1; multi-fuel handled below) | code lookup (table 2.3) | derived |
| 3_5 Multifuel / 3_1 Gen | `Multiple Fuels?`, `Cofire Fuels?`, `Switch Between Natural Gas and Oil?` (verify) | `x_dual_fuel` (bool) | Y/N -> bool; informs future fuel-switch feature, not used in G11 | observed |
| 3_1 Gen | `Nameplate Capacity (MW)` | `x_nameplate_mw` | as is | observed |
| 3_1 Gen | `Summer Capacity (MW)`, `Winter Capacity (MW)` | `k0_mw` = summer (see rule below); winter in `x_winter_mw` | MW | observed |
| 3_1 Gen | `Minimum Load (MW)` | `pmin_frac` = min load / `k0_mw` | frac; bounds [0, 1]; 0 or blank = missing (hierarchy 4.2) | observed (if > 0), else estimated |
| 3_1 Gen | `Status` (OP, SB, OS, OA, TS, ... ; verify full code list) | `status` existing if OP/SB; others per table 2.4 | code lookup | derived |
| 3_1 Gen | `Operating Month`, `Operating Year` | `in_service_date` (first of month) | ISO-8601 | observed |
| 3_1 Gen | `Planned Retirement Month`, `Planned Retirement Year` | `retire_date`, `retirements.announced=true` | ISO-8601; announced is not guaranteed (can slip) | observed, confidence medium |
| 3_1 Retired tab | `Retirement Month`, `Retirement Year` | historical `retire_date` (fleet reconstruction for backcast year) | | observed |
| 3_1 Proposed tab | `Effective Month/Year`, `Current Month/Year` , `Status` (P, L, T, U, V, TS ... verify) | `queue.csv` baseline, `build_limits` (G10); not `fleet_units` | | observed |
| 3_1 Gen | `Time from Cold Shutdown to Full Load` (verify name; coded duration classes) | `x_cold_start_class`; feeds `min_up_h/min_dn_h` and startup-cost class (4.5) | code -> hours class (verify codes) | observed |
| 3_1 Gen | `Turbines`, `Turbines/Hydraulic Turbines/Inverters` (verify) | `x_n_turbines` (combined cycle block structure: CT count) | int | observed |
| 3_1 Gen | `Topping or Bottoming?`, `Sector`, `Carbon Capture Technology?` (verify) | `x_chp` flag (Sector = CHP codes; verify), `x_ccs` | bool | observed |
| 3_1 Gen | `Unit Code` (verify), `Associated With Combined Heat and Power System?` (verify) | `x_unit_code`; groups generators into plant-prime-mover units (combined-cycle blocks) | str | observed |
| 3_1 Gen | `Nameplate Power Factor` | not used (MW basis) | | |
| 6_1 EnviroAssoc | boiler-generator association (`Boiler ID`, `Generator ID`) and `Steam Plant Type`, `Boiler Status` (verify) | `x_boiler_ids` (for 923 Page 3 -> generator fuel allocation, section 3) | many-to-many; `pct` split unknown (verify) | observed |

**Capacity basis rule (recommendation).** The model's `k0_mw` is **summer net capacity** (`Summer Capacity (MW)`),
with **winter** kept. Reasons: (i) PJM peak is summer and the capacity-market (G14) accredits against summer peak;
(ii) summer capacity is the net, de-rated-for-heat figure and is closest to what 923 net generation can deliver
in the hours that matter for LMP formation; (iii) nameplate is a gross, often generator-rating figure and
overstates thermal output by 2-10 % (verify typical gap) on CT and CC units. Winter > summer for gas
turbines by up to ~10-15 % (verify); a seasonal derate is a G12 option via `availability.csv` (`availability_frac =
winter/summer`), not a first-gate feature. If summer is blank or 0, fall back to nameplate x peer-median
summer/nameplate ratio for the same prime mover and size class (hierarchy level 3, fit id recorded).
Wind and solar use nameplate (their capacity factor series is on nameplate; `Summer Capacity` is a
peak-contribution figure, not what the profile scales to). Storage uses the charge/discharge rate fields below.

### 2.2 Prime mover (`Prime Mover`) to model class

`type` in the schema is `TH | VRE | ST`. `tech` is free text; a controlled vocabulary is proposed here (recommend
adopting in the schema, section 6). `x_chp` plants keep their class but are flagged.

| PM code | EIA meaning | `type` | `tech` class | Notes |
|---|---|---|---|---|
| ST | Steam turbine (non-CC) | TH | `coal_st`, `gas_st`, `oil_st`, `nuc_st`, `bio_st`, `waste_st` (by fuel) | nuclear is `ST` + `NUC`; geothermal/solar thermal ST not in PJM scale |
| CA | Combined-cycle steam part | TH | `ngcc` (with CT) | CC block = CT + CA; capacity-weighted aggregate in 4.1 |
| CT | Combined-cycle combustion turbine part | TH | `ngcc` | do not treat as simple-cycle CT |
| CS | Combined-cycle single shaft | TH | `ngcc` | block in one generator |
| GT | Combustion (gas) turbine, simple cycle | TH | `ngct` (`oilct` if oil) | |
| IC | Internal combustion engine | TH | `ice_gas`, `ice_oil`, `landfill_gas` (LFG is `fuel` `LFG`) | small; landfill gas flagged renewable for G10 |
| FC | Fuel cell | TH | `fuel_cell` | tiny; keep |
| OT, OP, ... | Other / pumped-hydro others | review | manual | list unmapped codes in the assumptions book |
| HY | Hydro, conventional | VRE (run-of-river) or TH-limited | `hydro` | treated as VRE profile if no energy-limit feature; verify decision |
| PS | Hydro pumped storage | ST | `phs` | energy and power via 3_4 or approximated (2.5) |
| WT | Wind turbine, onshore | VRE | `wind_on` | |
| WS | Wind turbine, offshore | VRE | `wind_off` | |
| PV | Solar photovoltaic | VRE | `solar_pv` | utility vs distributed by `Sector`/size; DPV is a load adjustment, not a resource, under the BTM rule |
| BA | Battery energy storage | ST | `bat` | |
| FW | Flywheel | ST | `flywheel` | tiny |
| CE | Compressed air storage | ST | `caes` | none in PJM today (verify) |
| BT | Binary cycle (geothermal) | VRE/TH | n/a PJM | |
| NB | Nuclear (via `NB` in some PUDL harmonisation; EIA uses `ST` + `NUC`) | TH | `nuc_st` | do not rely on NB in raw EIA; verify |

### 2.3 Energy source code to model `fuel`

| EIA code | Fuel | Model `fuel` | Notes |
|---|---|---|---|
| NG | Natural gas | `gas` | maps to hub via `fuel_map` (G5, DECISIONS 29) |
| BIT, SUB, LIG, RC (refined coal), ANT, WC (waste coal) | Coal | `coal` | `RC` is synfuel-treated coal; verify the 923 treatment |
| DFO, RFO, KER, JF, WO | Distillate / residual / kerosene / jet / waste oil | `oil` (`oil_dfo`, `oil_rfo` if prices differ) | |
| NUC | Nuclear | `uranium` (fixed fuel cost) | MC from ATB/NEEDS (4.5) |
| WAT | Water | none (`type` VRE or ST) | |
| WND, SUN | Wind, solar | none (VRE; MC=0 per schema 3.3) | |
| MWH | Electricity used for storage | none (ST) | |
| LFG, OBG, OBS, OBL, WDS, BLQ, AB, MSW, SLW, GEO, OG, PG, SGC, SGP, BFG, PUR, TDF, WH, OTH | Gas/biomass/waste/other | `biomass`, `waste`, `other_gas`, or `other` (review) | list unmapped; each flagged for owner check |

Multi-fuel: primary fuel = `Energy Source 1`. Secondary fuels (ES2..ES6) kept in `x_fuel_secondary` for later gates;
no switching in G11 (simplest model first).

### 2.4 `Status` to model status (verify full code list)

| Code | Meaning (EIA) | Model use |
|---|---|---|
| OP | Operating | `existing` |
| SB | Standby/backup, available | `existing`, flag `x_standby`; capacity kept but low-capacity-factor prior |
| OS | Out of service, not expected to return in the year | exclude (`x_oos`); keep for retirement analysis |
| OA | Out of service but expected to return | `existing` with `x_oa` flag; included, confidence medium |
| TS, V, U, T, L, P, ... | Proposed stages (under construction ... planned) | `queue.csv`, not fleet (G10) |
| RE / retired tab | Retired | not in fleet for years after `retire_date` |

### 2.5 Storage and duration (3_4 Energy Storage; 3_1 for pumped hydro)

| EIA column (verify all) | Schema target | Transform | Method |
|---|---|---|---|
| `Nameplate Energy Capacity (MWh)` | `e0_mwh` | as is | observed |
| `Maximum Charge Rate (MW)` | `x_charge_mw` | as is | observed |
| `Maximum Discharge Rate (MW)` | `k0_mw` (ST: power `P^0`) | as is; if different from charge rate, discharge used (schema has one power) | observed |
| `Storage Technology 1..` (verify codes: LIB, PB, ZN, FLW, ...) | `tech`/`x_storage_tech` | lookup | derived |
| derived | duration `x_dur_h` = `e0_mwh / k0_mw` | h; flag < 0.25 h or > 24 h as suspect | derived (est_level n/a; `basis` formula) |
| `Direct Support`, `Charge Source` flags (verify) | `x_*` | informational | observed |
| none | `eta_c_frac`, `eta_d_frac`, `selfdis_frac_h` | EIA does not report round-trip efficiency | **assumed**: ATB battery RTE (verify value) split `sqrt(RTE)` per leg; `confidence=low`, `est_level=4` |
| Pumped hydro (3_1 `PS`): no energy field | `e0_mwh` | estimate hours from published fleet averages (PJM/DOE hydropower: ~8-12 h typical; verify) | estimated, `est_level=4`, `confidence=low` |

### 2.6 Wind, solar, multifuel supplementary sheets

3_2 Wind (`Predominant Turbine Manufacturer`, `Turbine Hub Height`, `Number of Turbines`) and 3_3 Solar
(`Single-Axis Tracking?`, `DC Net Capacity (MW)`, `Fixed Tilt?` ...; verify): used only to pick a representative
`availability` profile class (tracking vs fixed; AC vs DC ratio) at G11; capacity stays nameplate (AC).

---------------------------------------------------------------------------------------------------

## 3. Heat-rate derivation from EIA-923

**Level 1/2 quantity.** Annual (or multi-month) plant-prime-mover-fuel heat rate:

    HR_{plant,PM,fuel} = sum_m EFC_{m} / sum_m NG_{m}     [MMBtu/MWh]

- 923 Page 1 columns (verify exact): `Plant Id`, `Reported Prime Mover`, `Reported Fuel Type Code`,
  `Elec Fuel Consumption MMBtu` (annual `Elec_MMBtu` + monthly `Elec_MMBtu January`...), `Net Generation (Megawatthours)`
  (annual) and monthly net generation columns, `Total Fuel Consumption MMBtu`. Schema-neutral name used here:
  `elec_fuel_consumption_mmbtu`, `net_generation_mwh`.
- Use **electric** fuel (`Elec Fuel Consumption`), not total fuel, for CHP plants. Total includes the
  thermal output; do not use it.
- Output column `heat_rate_mmbtu_mwh` is a **single average heat rate**. The model has no heat-rate curve at G1-G9
  (the UC extension, G9, adds `no_load_usd_h` and a marginal heat rate). Level-1 curve detail from CEMS is retained
  in `x_hr_a`, `x_hr_b` (no-load MMBtu/h and incremental MMBtu/MWh) for G9, with the fit in the assumptions book.
- Heat-rate basis: 923 net generation and fuel give **net** heat rate on a LHV/HHV basis? EIA fuel MMBtu is HHV
  (gross heating value; verify). ATB/EIA new-build rates are HHV too (verify); keep all HHV and say so in `basis`.

**Allocation to generators** (a plant-prime-mover row maps to many generators):
1. If 923 Page 4 (generator-level net generation) and Page 3 (boiler fuel) cover the unit, use them with the 860 boiler-
   generator association: **level 1** (unit-specific). Coverage is partial: only plants/units above a size/technology
   threshold report at this level (verify), mainly steam units and combined cycles of larger plants.
2. Else plant-prime-mover aggregate applied to every generator of that PM at the plant, weighted by **summer capacity**
   when generators differ in type (e.g. two CC blocks): **level 2**. All generators of the plant-PM-fuel share the same HR.
3. For plants with several fuels per PM (dual-fuel, coal + gas cofire), split fuel columns by `Reported Fuel Type Code`
   and compute `HR_f`; the unit HR = fuel-energy-weighted average, and the fuel dimension kept in `x_hr_by_fuel`.

**Pitfalls and treatments.**

| Pitfall | Treatment |
|---|---|
| CHP / cogeneration: electric fuel not separated from thermal in some plants; `Useful thermal output` (923 Page 1 col, verify) exists | Use `Elec Fuel Consumption`; if missing, subtract thermal output / assumed boiler efficiency 0.8 (assumed, `est_level=4`, `confidence=low`); flag `x_chp`; HR kept only if inside bands |
| Combined cycle: CT and CA units both reported, fuel reported at plant-PM level against `CT`, steam `CA` has zero or no fuel | Aggregate to plant block: sum fuel on `CT`/`CS` rows, sum generation of all CC rows (`CT+CA+CS`), compute block HR, then assign the same HR to each CC generator row; the model treats a CC block as one resource where the clustering allows |
| Negative or zero net generation (station service exceeds output; idle units; steam in startup) | If annual net gen <= 0 or < 5 % capacity-hours (CF < 0.02): discard (level 1 invalid), fall to next level; never divide by tiny denominators |
| Partial-year operation (new COD, retired mid-year) | Use only months with generation > 0; if < 3 such months, treat as invalid |
| Nuclear | HR reported in 923 is thermal (reactor heat, ~10.4 MMBtu/MWh, verify); fuel cost per MWh comes from NEEDS / ATB (nuclear fuel cost ~ $/MWh range, verify); keep HR for emissions accounting only; MC = fuel cost `assumed` |
| Low capacity factor peakers: heat-rate inflated by starts and part load | Reported annual HR is higher than full-load HR; keep it flagged `x_hr_basis=annual_average` and adjust when starts are known (CEMS, level 1 path) |
| Wind/solar/hydro | no HR |
| Fuel not fully attributed (e.g. refined coal, landfill gas blanks) | exclude from level-1/2; use level 3 |
| Reporting errors (misplaced decimals, MWh vs thousand MWh) | sanity bands below; cross-check with CEMS if available |

**Sanity bands for `heat_rate_mmbtu_mwh` (HHV).** Out-of-band values are rejected and the cell moved to the next level;
bands are assumed, to be tuned on the back-test (values here are `(verify)` against ATB/NEEDS/EIA-AEO tables).

| tech class | lower | upper |
|---|---|---|
| `ngcc` | 5.8 | 9.5 (verify) |
| `ngct` / `gas_st` | 8.0 (GT) / 8.5 (ST) | 16.0 / 16.0 (verify) |
| `coal_st` | 8.8 | 13.5 (verify) |
| `oil_*` | 8.5 | 17.0 (verify) |
| `ice_*` | 8.0 | 13.0 (verify) |
| `nuc_st` | 10.0 | 11.5 (verify; thermal basis) |

---------------------------------------------------------------------------------------------------

## 4. Estimation hierarchy for missing unit characteristics

All levels follow `data-sources.md` (observed -> plant-level -> statistical estimate -> cited default). The
confidence map is the default: **L1 high, L2 medium-high (stored `medium`; schema enum has no `medium-high`), L3 medium, L4 low**;
lowered one step when the back-test (4.7) error exceeds its tolerance. Free sources only (DECISIONS 26).

### 4.1 Heat rate (`heat_rate_mmbtu_mwh`)

| Level | Source | Method | Confidence |
|---|---|---|---|
| 1 | EPA CEMS (`cems`): hourly heat input (MMBtu) and gross load (MW) per unit; EIA-EPA crosswalk (`pudl`, or EPA power-sector crosswalk; verify) for ids; 923 Page 3/4 unit-level fuel and gen | CEMS: regress heat input on load (linear: `HI = a + b*MW`) over hours with load > 0; average HR = sum HI / sum gross MWh; convert gross to net with plant-level station-service ratio from 923 (net/gross). Prefer 923 unit-level `fuel / net` when available | high |
| 2 | 923 plant-prime-mover fuel / net generation (section 3) allocated to generators | capacity-weighted allocation; CC block aggregated | medium (stored; "medium-high") |
| 3 | Peer-group median/regression on observed L1+L2 PJM units (fit stored with id, fit stats) | `log HR ~ tech + fuel + size_class + vintage_decade + CF_class`; if n < 5 in a cell, merge adjacent cells and widen to PJM + neighbouring RTOs from CEMS; RMSE reported | medium |
| 4 | NEEDS (`needs`) unit heat rate (itself an estimate); ATB class defaults; AEO assumptions | take NEEDS if present; else ATB/AEO technology default. Both carry `(verify)` of vintage | low |

### 4.2 Minimum generation (`pmin_frac`)

| Level | Source | Method | Confidence |
|---|---|---|---|
| 1 | 860 `Minimum Load (MW)` > 0 (a reported unit value) | `pmin_frac = Minimum Load / summer capacity` | medium (self-reported, not tested; see note) |
| 1b | CEMS observed operation | for online hours (load > 0), 2nd-5th percentile of hourly load relative to unit max; taken as demonstrated min-stable; Observed minimum includes ramping hours, so use a low-percentile and exclude start/stop hours | medium-high |
| 3 | Peer-group (tech x size x vintage) median of level 1/1b values | as 4.1 L3 | medium |
| 4 | Literature: NREL/WECC cycling studies (Kumar et al. 2012, "Power Plant Cycling Costs", NREL/SR-5500-55433, Intertek APTECH; Lew et al. 2013 "Western Wind and Solar Integration Study Phase 2", NREL/TP-5500-55588; verify citations) and EPA/IPM defaults. Typical values (verify, not for use before checking): coal ~ 25-50 %, gas ST ~ 25-40 %, ngcc ~ 40-50 %, ngct ~ 40-50 %, nuclear ~ 90-100 % (baseload, no cycling), ICE ~ 30-50 % | table in `data/common/assumptions_defaults.csv` with citation row per value | low |

Note: 860 `Minimum Load (MW)` is self-reported and often equals a round number or the nameplate for non-dispatchable units; apply bounds [0.05, 1.0] (verify) and treat 0 as missing. Needed from G9 only (UC); at G1-G8 the column stays null (simplest first).

### 4.3 Ramp rate (`ramp_up_mw_h`, `ramp_dn_mw_h`)

EIA has no ramp field. All levels are estimates (no observed level 1 except CEMS).

| Level | Source | Method | Confidence |
|---|---|---|---|
| 1 | CEMS hourly gross load, per unit | hourly change `dP`; ramp = 95th-99th percentile of positive (negative) `dP` over operating hours with no start/stop; expressed in MW/h and as fraction of capacity; check against ramp assumptions in the literature class | medium (hourly data hides 5/10-min ramps) |
| 3 | Peer-group percentile of L1 values by tech x size | as 4.1 L3 | medium |
| 4 | Literature default (verify): Lew et al. 2013 / Kumar et al. 2012 class ramp assumptions; EPA IPM / NEEDS-adjacent ramp; typical %/min (verify): coal ~1-3, ngcc ~2-5, ngct ~8-12, gas ST ~2-4, nuclear ~0-1 | convert %/min x 60 x capacity to MW/h, cap at capacity per hour (`dt = 1 h`) | low |

At `dt = 1 h` most thermal ramp rates are non-binding (e.g. 2 %/min = 120 %/h of capacity); the hourly ramp matters
mostly for nuclear, large coal and constrained units. This is the argument for **deferring** ramp estimation to G9.

### 4.4 Forced and planned outage rates (`outages.csv`: `forced_outage_frac`, `planned_outage_frac`, `derate_frac`; G12)

| Level | Source | Method | Confidence |
|---|---|---|---|
| 1 | Unit-specific outage history: not available publicly (PJM eDART / NERC GADS unit data confidential). **Proxy**: CEMS operating-hour gaps combined with 923 CF cannot separate forced from planned | do not claim level 1 for outage rates | n/a |
| 2 | PJM published fleet statistics: Data Miner 2 planned/forced outage feeds (aggregate MW by day and reason; verify), PJM Reserve Requirement Study class EFORd/ELCC tables (verify) | aggregate to class; allocate to units by class | medium |
| 3 | Peer-group from public aggregates and CEMS-derived availability (share of hours with load > 0 as a feature to rank units; cannot split forced from planned) | Use only as a regression feature, not as a stand-alone published level | low |
| 4 | NERC GADS public summary (`nerc_gads`): class averages of EFOR/ forced outage rate (verify typical values: ngcc ~ 4-7 %, coal ~ 7-12 %, nuclear ~ 1-3 %, ngct ~ 6-12 %, verify) and planned outage factor by class (typical planned ~ 5-10 % of hours coal/ngcc, nuclear ~ 5-8 % annualised, verify) | monthly shape: planned outages concentrated in shoulder months (spring/fall); shape from PJM planned-outage aggregates (verify) | low (class average) |
| 4b | PJM EFORd class values in reserve requirement study / capacity market parameters (verify) | accreditation-linked; aligns with G14 | medium |

Outages are a **G12** feature (DECISIONS 29: simplest first); here we only fix the data path and provenance.

### 4.5 Startup cost, no-load, VOM, FOM (G9/G11)

Startup cost (`start_cost_usd_mw`; and `x_start_mmbtu_mw` if the schema gains fuel-based starts): no EIA field;
only `Time from Cold Shutdown to Full Load` (verify) as a class hint.

| Level | Source | Method | Confidence |
|---|---|---|---|
| 1 | CEMS: detect starts (load 0 -> > 0), start-up fuel = heat input during the start ramp above steady-state heat rate | per unit; needs thousands of starts for stable estimate | medium |
| 3 | Peer-group median of L1 by tech/size | | medium |
| 4 | Kumar et al. 2012 (NREL/SR-5500-55433; verify) cold/warm/hot start cost tables by technology and size (reported as $/MW-start; magnitudes, dollar year and units must be read from the report, no numbers asserted here) (verify) | convert to model $ via `dollar_year`; deflate with `bea_gdpdef`; split into fuel (MMBtu) vs non-fuel parts to avoid double-counting gas price | low |

VOM and FOM (`vom_usd_mwh`, `fom_usd_mw_yr`): level 4 only for existing fleet: NEEDS/ATB/EIA AEO
"Assumptions to the AEO: Electricity Market Module cost and performance table" (verify) by class; each with its own
`dollar_year`. No unit-level source exists. Back-test is not possible (no observed cost); `confidence=low`.

### 4.6 Fill order and dispatch rule

For a cell `c` (unit u, column x): take the first level whose value exists AND passes band checks of its section.
If levels disagree strongly (L1 and L3 differ by more than the L3 RMSE x 2), flag `x_conflict` and keep the
lower-level value only when the higher level's input data is verifiably complete (e.g. >= 8 months generation).
Never leave blank; never silently default (CLAUDE.md). Every fill writes a `provenance_cells.csv` row.

### 4.7 Back-test plan (mandatory for L3; recommended for L2)

1. Population: PJM units with observed level-1 values for the characteristic (heat rate: CEMS or 923 unit-level;
   min gen: CEMS percentile and 860 min load; ramp: CEMS percentile).
2. K-fold (K = 5), stratified by tech x size class; hold out fold units, fit L3 on remainder, predict held-out cells.
   Fixed seed recorded in `basis`.
3. Compare **each level against the observed values**: L2 (plant-level allocation) vs L1 on units with both; L3 vs L1;
   L4 default vs L1. Report per tech class: n, bias, MAE, RMSE, MAPE, 80 % interval coverage.
4. Report **capacity-weighted** error as well as unit-count error, and the effect on system dispatch cost: re-run a fixed-fleet
   dispatch (allowed one-off full-year check in CLAUDE.md) with HR perturbed to the estimates, and report change in
   annual variable cost and in marginal-unit identity (price-setter report).
5. Tolerances (proposed, owner can change): heat rate MAPE <= 5 % (L2), <= 8 % (L3), <= 15 % (L4); min-gen MAE <= 8
   percentage points of capacity (L3); ramp: log-error reported only (no tolerance, hourly ramp rarely binds).
   A level exceeding tolerance drops one confidence step, and the failure goes to the assumptions book section 6.
6. Output: `reports/estimation-backtest-<vintage>.md` and rows in the assumptions book (section 6 "Estimates and fits"):
   fit id, formula, n, errors, units affected, share of capacity.
7. Outage rates and startup costs have no observed unit-level truth in public data; their back-test is **indirect**:
   fleet-level checks (PJM published class forced outage rate; backcast monthly generation vs 923; capacity factor by
   tech vs 923). State this limit in the book.

---------------------------------------------------------------------------------------------------

## 5. Provenance recording

Per `data-schema.md` section 0: P fields = `source_id, vintage, retrieved, method, basis, confidence, est_level`.
`fleet_units.parquet` carries a per-row default (the 860 row) and `provenance_cells.csv` overrides cells.

| Cell origin | `source_id` | `vintage` | `method` | `basis` (content) | `confidence` | `est_level` |
|---|---|---|---|---|---|---|
| 860 field copied (k0, dates, tech, storage MWh) | `eia860` | data year + `final|early` | observed | `"860 <file>/<sheet>/<column>"` | high (capacity, dates), medium (min load, planned retirement) | blank (optional for observed) |
| Heat rate from 923 unit-level | `eia923` | year | derived | `"HR=sum(EFC)/sum(NG), 923 p3/p4, months=<n>, allocation=unit"` | high | 1 |
| Heat rate from CEMS | `cems` | year | derived | `"sum(heat input)/sum(gross MWh) x net/gross ratio <r>, crosswalk=<id>"` | high | 1 |
| Heat rate plant-PM alloc | `eia923` | year | derived | `"HR=EFC/NG p1, PM=<>, alloc=cap-weighted, n_gens=<k>"` | medium | 2 |
| Peer-group / regression | the data sources used (`eia923`, `cems`) | year range | estimated | `"fit:<fit_id>; formula; n; RMSE; seed"` | medium (lowered if back-test fails) | 3 |
| Literature / NEEDS / ATB default | `needs`, `atb`, `nerc_gads`, or `lit_<author_year>` (new registry rows) | publication year | estimated (or assumed if a modeller's pick) | `"Kumar 2012 Table x p y, class=<>"` (verify) | low | 4 |
| Zone from lookup | `pjm_zone_map` (new registry row) | map year | assumed | `"TO owner id <n> -> zone <z>"` | medium | n/a |
| Dollar values from literature | as above | | | `dollar_year` column set to the publication's year, converted at load | | |

Rules: `assumed` is never `high` (schema rule 7); `estimated` and `derived` need `basis` and `est_level`;
every new `source_id` (e.g. `kumar2012_cycling`, `lew2013_wwsis2`, `pjm_zone_map`) is added to
`docs/data-sources.md` and `data/common/sources.csv` in the same commit that uses it.

**Assumptions book contributions** (from `resolved_provenance.parquet`, no hand editing):
- Section 2 Provenance mix: share of capacity (MW) and cells by `method` and `est_level` for each of: capacity, heat rate,
  min gen, ramp, outage, start cost, VOM/FOM; the headline "x % of PJM MW has an observed heat rate".
- Section 3 sources: `eia860`, `eia923`, `pudl` (release DOI), `cems`, `needs`, `atb`, `nerc_gads`; vintage, retrieved,
  licence class (all public domain/CC-BY (verify)).
- Section 4 dollar years: costs from NEEDS/ATB/Kumar with `dollar_year` and factors.
- Section 6: every fit id with formula, n, error, units; the back-test tables of 4.7.
- Section 8: low-confidence cells touching > 1 % of capacity.
- New "Data quality events" subsection: unmapped PM/fuel codes, out-of-band values rejected, CHP units, early-release
  rows, unit-id collisions, zone-map defaults, with counts and MW.

---------------------------------------------------------------------------------------------------

## 6. Gaps and "Needs owner"

**Downloads (cloud workspace cannot reach EIA/EPA/PUDL hosts; record in PLAN.md "Needs owner").**
1. Run `data-eia860` and `data-eia923` workflows (manifests exist, `enabled=false`) once with `pin_mode=record`; confirm
   URLs and sha256 (`eia8602023.zip`, `f923_2023.zip`; verify file names).
2. Confirm actual sheet and column names against the downloaded files and clear every `(verify)` here.
3. PUDL release: choose a release, record DOI; confirm table names and CC-BY terms.
4. EPA CAMPD/CEMS hourly for PJM states, backcast year (large; **P** via PUDL preferred). CAMPD needs an API key
   (free) as a repo secret `CAMPD_API_KEY` (verify name) only if PUDL is not used.
5. NEEDS workbook (URL changes by IPM version; owner download or the workflow with a pinned URL).
6. NERC GADS summary tables, Kumar et al. 2012 and Lew et al. 2013 PDFs: manual (**M**) transcription with page refs.
7. PJM Data Miner outage aggregates and PJM zone data: manual or key-based (existing `pjm_dm2` row).

**Zone mapping (open gap).** 860 gives BA code `PJM` but no zone. Options, in order: (1) `Transmission or Distribution
System Owner (ID)` -> PJM transmission-owner zone table (TO-zone map from PJM manuals / Data Miner; hand-built CSV,
`method=assumed`); (2) NEEDS IPM region / zone attribute for NEEDS-matched units (verify); (3) state + county/lat-lon
nearest TO territory. Multi-zone TOs (e.g. Dominion vs. DEOK/Dayton boundaries, AEP across several states) and units
in zones like OVEC/EKPC without a clean TO id need manual resolution; target list is the units that fail (1). Until built,
G11 single-zone slice can be defined by TO owner(s) chosen by owner, avoiding the map.

**Other gaps.**
- 860 does not report outage rates, ramp rates, startup costs, VOM/FOM, efficiencies: all level 3/4.
- 923 unit-level coverage is partial; most small gas CT/IC units are plant-level only (L2) or L3.
- PJM-specific fuel: unit fuel costs are not in 923 for non-regulated plants (Page 5 cost is redacted or aggregated for
  some plants; verify); used only as a check on `gas_basis_fallback`.
- Retirement and new-build status in 860M are announcements, not facts.
- CEMS covers only fossil >= 25 MW; nuclear, hydro, wind, solar, small units have no level 1 hourly path.

### Schema gaps found in `data-schema.md` S-0.1 (for the next schema bump)
1. No controlled `tech` / `fuel` vocabulary (only free str); the prime-mover and fuel maps above need a registry table.
2. No `zone_map` / TO-owner mapping table or `ba_code` field; `zones.csv` has no link to 860 plant/utility ids.
3. No unit-level fit/estimate registry table (assumptions book section 6 requires fit id, formula, n, error, units; no input schema for it).
4. `resources` has one `heat_rate_mmbtu_mwh`; no heat-rate curve fields (`hr_noload_mmbtu_h`, `hr_incr_mmbtu_mwh`) for G9; `start_cost_usd_mw` is $-only (no fuel MMBtu).
5. No `capacity_basis` field (summer vs nameplate vs winter) and no `winter_mw` / `nameplate_mw` columns; proposed: `x_` columns now.
6. Confidence enum has no `medium-high`; the data-sources map mentions "L2 medium-high": decide (store `medium`, or add the level).
7. No `chp`, `standby`, `prime_mover`, `fuel_secondary`, `cold_start_class` columns; proposed as `x_` extensions.
8. `outages.csv` (G12) keys by `resource_id`; EIA ids are changing in time (generator renames): no `unit_id` history/`id_valid_from` rule.
9. Storage: `eta_*` and `selfdis_frac_h` have no EIA source; pumped hydro `e0_mwh` needs an `estimated` flow: fine under P but the 860 `Storage` sheet's charge vs discharge rate difference is not represented (one power column).

### Owner decision list (recommendation each)
1. Use summer net capacity as `k0_mw` (nameplate for wind/solar), winter kept as `x_winter_mw`. **Recommend: yes.**
2. Prefer PUDL as the cleaned 860/923/CEMS source, with raw EIA files as fallback. **Recommend: yes** (fewer id bugs; verify licence/release first).
3. Add the controlled `tech`/`fuel` vocabularies of 2.2/2.3 to the schema at the S-0.2 bump. **Recommend: yes.**
4. Build `data/common/pjm_zone_map.csv` by hand (TO owner -> zone), `method=assumed`, for the G11 slice. **Recommend: yes**, and choose the G11 zone(s) first.
5. Accept 860 `Minimum Load (MW)` as observed `pmin_frac` only after the CEMS cross-check (else treat as `estimated`). **Recommend: yes.**
6. Defer ramp, min gen, startup, outage estimation to G9/G12 (data path fixed here, no estimation before the gate). **Recommend: yes** (simplest first, DECISIONS 26).
7. Add `medium-high` to the confidence enum, or store L2 as `medium`. **Recommend: store `medium`** (no schema change).
8. Adopt the back-test tolerances in 4.7 (heat rate MAPE 5/8/15 % by level). **Recommend: yes** as starting values; revise after the first back-test.
9. Approve manual transcription of NERC GADS and Kumar/Lew cycling tables (page refs, no redistribution). **Recommend: yes.**
10. Run the one-off `pin_mode=record` workflows for `eia860`/`eia923` (and a PUDL pull) to clear the `(verify)` list. **Recommend: yes**, before any loader is written.
