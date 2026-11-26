# Data sources and assumptions

Version S-0.1 (Gate 0, W2). Tables that carry these fields: `docs/data-schema.md`. Mirrored machine-readable as
`data/common/sources.csv` (one row per `source_id` below).

## Provenance rule (applies to every input value)
Every parameter in every input table carries:
- `source_id` → a row in the source registry below
- `vintage` (data year / release) and `retrieved` date
- `method`: `observed` | `derived` | `estimated` | `assumed`
- `basis`: how it was derived/estimated (formula, regression id, or citation)
- `confidence`: high / medium / low
- `est_level` (1–4, hierarchy level below): required when `method` is `derived` or `estimated`

Nothing enters the model without these fields (per row, with per-cell overrides; per series for time series: see
`data-schema.md` §0). Every run writes an **assumptions book** (`outputs/<run>/assumptions.md`) listing, by
parameter, the share of capacity that is observed vs estimated vs assumed, with citations: the client-facing audit trail.

## Estimation hierarchy for missing unit characteristics
When a PJM unit lacks a characteristic (heat rate, min gen, ramp, start cost, outage rate,
VOM, FOM), use the first level available and record which (`est_level`):
1. **Unit-specific observed** — e.g. heat rate from EPA CEMS heat input / gross load, or
   EIA-923 fuel consumption / net generation.
2. **Plant-level observed**, allocated to units.
3. **Statistical estimate from public data** — regression or peer-group median by
   technology, prime mover, vintage, size class, and region (fit on units that have
   observed data; fit stored with id and fit statistics).
4. **Literature / public defaults** with citation — e.g. NREL ATB, EIA AEO assumptions,
   EPA NEEDS / IPM documentation, NERC GADS summary statistics, published academic values.
Estimates are back-tested where possible (hold out units with observed values and report
error), and the levels used feed the `confidence` field (suggested map: L1 high, L2 medium-high, L3 medium, L4 low;
overridden downward when the back-test error is large). Test-system data (RTS-GMLC, 5-bus, GenX) is `observed`
for the system as published (`basis` = "published test-system value"), never mixed into PJM statistics.

## Source registry
Access codes: **A** = automated GitHub Actions download (cached as an artifact); **P** = via PUDL; **M** = manual
download by the owner, committed or uploaded as an artifact; **L** = licensed/commercial. Gate = first gate that needs it.
URLs/licences marked "verify" were not checked from this workspace (no network) and must be confirmed by the first
Actions run or the owner before reliance. Terms below are my reading of the public terms, not legal advice.

| source_id | Name | Publisher | Use in model | Gate | Format / access | License / terms note | Cadence |
|---|---|---|---|---|---|---|---|
| `rts_gmlc` | RTS-GMLC test system (3 regions, ~150 gens, hourly load/RE) | GridMod / NREL, `github.com/GridMod/RTS-GMLC` | Test ladder: unit data, hourly profiles, published production-cost reference results | 4 | **A** git clone at a pinned commit; **fetched 2026-11-26** (P1): commit `3ece0d3`, 43-file subset (SourceData, DA hourly series, PLEXOS DA reference solutions) vendored in `cases/raw/rts_gmlc/` with full-repo `MANIFEST.csv` (sha256) and `PROVENANCE.md` | **No LICENSE file in repo at pinned commit** and no terms in README; redistribution unverified — internal test use only until owner confirms (`license_class=verify`) | Static (pinned commit) |
| `pjm5` | PJM 5-bus test system (Li & Bo 2010, "Small test systems for power system economic studies", IEEE PES GM; MATPOWER `case5`) | Li & Bo; MATPOWER (`github.com/MATPOWER/matpower`, `data/case5.m`) | Known LMP/congestion test (4 gens, 5 buses, line limits); small enough to hand-verify | 3 | **A** one file; **fetched 2026-11-26** (P3): `data/case5.m` sha256 `ed907208...fe279`, MATPOWER repo HEAD `b6c85b0` at retrieval, vendored in `cases/raw/pjm5bus/` with `MANIFEST.csv` and `README.md` | MATPOWER code is BSD-3, but its LICENSE excludes case files ("included with permission"): data terms unverified, `license_class=verify`, internal test use; cite Li & Bo 2010 and MATPOWER | Static |
| `genx_examples` | GenX example systems (e.g. three-zone, `example_systems/`) | GenX Project (MIT/Princeton), `github.com/GenXProject/GenX.jl` | Cross-check inputs and expected results for capacity expansion | 6 | **A** git clone at pinned release | Open-source, GPL-2.0 (verify): use as data inputs only; do not copy code (DECISIONS 1) | Per release |
| `eia860` | EIA Form 860 (generators, plants, planned/retired units) | U.S. EIA, `eia.gov/electricity/data/eia860/` | Fleet, capacity, tech, vintage, retirements, planned additions | 11 | **A** (or **P**) annual zip/xlsx | U.S. Government public domain; cite EIA | Annual (final ~Sep for prior year), monthly "early release" |
| `eia923` | EIA Form 923 (generation, fuel use, fuel cost) | U.S. EIA, `eia.gov/electricity/data/eia923/` | Monthly generation by fuel (benchmark), fuel use → derived heat rates, fuel cost for hub-basis checks | 11 | **A** (or **P**) | Public domain | Monthly (~2 mo lag); annual final |
| `eia930` | EIA Form 930 hourly grid monitor (demand, net interchange, gen by fuel) | U.S. EIA, `eia.gov/opendata/` (API key) | Hourly PJM demand and external interchange (imports/exports in backcasts) | 12 | **A** (API key as repo secret) | Public domain; API key free | Hourly, ~1 d lag |
| `pudl` | Catalyst Cooperative PUDL (cleaned EIA/FERC/EPA joins, CEMS, FERC-714) | Catalyst Cooperative, `catalyst.coop` | Preferred clean source for 860/923/CEMS/714 and the EIA-EPA crosswalk (plant/unit ids) | 11 | **A** parquet/SQLite from the PUDL data release (Zenodo / cloud bucket; verify current location) | Data CC-BY-4.0 (verify), code MIT; cite release DOI; pin release as `vintage` | Quarterly-ish releases |
| `cems` | EPA CAMPD / CEMS hourly emissions and operations (gross load, heat input, SO2/NOx/CO2) | U.S. EPA, `campd.epa.gov` | Unit-level observed heat rates, hourly operating profiles, starts/min-load proxies (est_level 1) | 11 | **P** (preferred; hourly CEMS is large) or **A** via CAMPD API (API key, verify) | Public domain | Quarterly/annual finalization |
| `needs` | EPA NEEDS database (IPM unit characteristics) + IPM documentation | U.S. EPA, `epa.gov/power-sector-modeling` | Unit characteristics defaults (heat rate, controls, retirement info, capacity); est_level 4 reference | 11 | **A** xlsx (page changes by IPM version; verify URL each update) | Public domain | Per IPM release (irregular, ~yearly) |
| `atb` | NREL Annual Technology Baseline | NREL, `atb.nrel.gov` (data via NREL OEDI / `data.openei.org`; verify) | New-build overnight capex, FOM, VOM, heat rate, CF, life, financing (CRF, PFF inputs), scenarios (Moderate/Advanced/Conservative) | 5 (toy), 11 | **A** data file per ATB year | CC BY 4.0 for ATB data (verify); cite year | Annual (~summer) |
| `aeo` | EIA Annual Energy Outlook (+ Assumptions to the AEO) | U.S. EIA, `eia.gov/outlooks/aeo/` | Projected fuel prices, macro (GDP deflator projection for years beyond BEA actuals), plant cost/performance assumptions | 10, 17 | **A** API / tables | Public domain | Annual |
| `pjm_dm2` | PJM Data Miner 2 (DA/RT LMP by zone and hub, metered load, load forecasts, reserve prices/requirements, ORDC, generation by fuel, outages, interchange) | PJM Interconnection, `dataminer2.pjm.com` | DA/RT LMP benchmarks (DA first), load, reserve products, ORDC inputs, marginal-fuel reference where available | 4 (5-bus: none), 11 | **A** via the Data Miner 2 API (subscription key from a free account, stored as repo secret; verify rate limits) | PJM terms of use apply (verify redistribution limits: keep raw pulls out of public repos; cite PJM) | Hourly/5-min feeds; archive history limited by feed (verify) |
| `pjm_rpm` | PJM RPM / Base Residual Auction results and planning parameters (VRR curve, Net CONE, reliability requirement, FRR/ELCC class UCAP) | PJM, `pjm.com/markets-and-operations/rpm` | Capacity price benchmarks (scoreboard), VRR curve inputs | 14 | **M** (PDF/xlsx reports; parse once) or **A** if stable URLs (verify) | PJM public reports; cite | Per auction (~annual, schedule changes: verify) |
| `pjm_elcc` | PJM ELCC class ratings / reports (2025/26 onward) | PJM planning, `pjm.com/planning/resource-adequacy-planning` (verify) | Accreditation by class and year for capacity-market module | 14 | **M** (PDF/xlsx) | PJM public reports; cite | Annual |
| `imm` | Monitoring Analytics, PJM State of the Market reports (marginal fuel by fuel, LMP decomposition, net revenue, ORDC/ shortage) | Monitoring Analytics (IMM), `monitoringanalytics.com/reports` (verify) | **Marginal fuel** shares (price-setter benchmark), net revenue of new entrants and storage benchmarks | 12 | **M** (PDF tables transcribed to CSV with page refs); **A** if stable | Copyright Monitoring Analytics: transcribe numbers with citation, no redistribution of report text (verify) | Quarterly + annual |
| `gas_hubs` | Daily regional gas price indices: Tetco M3, Transco Zone 6 non-NY, Dominion South (plus Texas Eastern/Columbia as needed) | ICE / S&P Global Platts / NGI (publishers of record) | **Daily hub-level fuel price** for MC and as clustering feature (DECISIONS 18) | 11 | **L** commercial licence typical (see risks) | **Licensed**: redistribution restricted; raw series likely cannot be stored in the repo or shared with clients | Daily |
| `gas_hh` | Henry Hub daily spot price | U.S. EIA natural gas spot prices (`eia.gov/dnav/ng/`; EIA attributes source to a data vendor, verify terms) and futures settle (CME) | Fallback / reference hub; regional price = HH + basis | 5, 11 | **A** (EIA API) | EIA data public; redistribution of upstream vendor series: verify | Daily |
| `gas_basis_fallback` | Estimated regional daily price = HH + basis from EIA monthly (EIA-923 delivered cost by state/plant, FERC Form 552 / EIA STEO regional), or PJM-published unit fuel costs (verify availability) | EIA / FERC | **Fallback** for hubs when no licence: monthly basis × HH daily shape; `method=estimated`, `est_level` 3 | 11 | **A** | Public | Monthly |
| `west_hub_fut` | PJM West Hub power futures (on-peak/off-peak monthly, ICE and CME) | ICE / CME Group | Forward-run comparison (DECISIONS 21) | 17 | **L** (settlement data licensed; verify delayed/public tables) | Licensed; use only transcribed monthly settles internally, no redistribution | Daily |
| `bea_gdpdef` | BEA GDP implicit price deflator, NIPA Table 1.1.9 (annual) | U.S. BEA, `bea.gov` (API key) | Convert all costs to base 2024$ | 1 | **A** (BEA API / FRED mirror `GDPDEF`, verify) | Public domain | Quarterly updates; annual revisions (record vintage) |
| `nerc_gads` | NERC GADS generating-unit availability summary statistics (EFOR, outage rates by type/size) | NERC, `nerc.com` (State of Reliability / GADS data summaries; verify) | Level-4 default forced/planned outage rates | 12 | **M** (PDF tables transcribed) | Summary statistics public; unit-level GADS data is confidential (not obtainable) | Annual |
| `rps_dsire` | State RPS/CES targets and tiers (DSIRE; LBNL "U.S. State RPS Status Update") | NC Clean Energy Technology Center (`programs.dsireusa.org`); LBNL (`emp.lbl.gov/projects/renewables-portfolio`) | Policy module: targets, eligibility, ACP prices, timelines for NJ, MD, IL, VA, DE, PA, OH etc. | 10 | **M** (statute-cross-checked table typed to CSV; verify against state statutes) | DSIRE: attribution/terms apply (verify); LBNL: public reports | Annual / as laws change |
| `rggi` | RGGI allowance auction/secondary prices and state membership/caps | RGGI Inc., `rggi.org` | CO2 adder by state/year; VA exit/re-entry membership | 10 | **A/M** auction results CSV/PDF (verify) | Public | Quarterly auctions |
| `queue_pjm` | PJM interconnection queue (active/withdrawn/in-service, by tech, zone, status) | PJM planning (`pjm.com`; verify) | Build limits, realism of candidate availability | 10 | **M**/**A** (xlsx export; verify) | PJM public data | Continuous |
| `queue_lbnl` | LBNL "Queued Up" interconnection queue data and completion rates | LBNL, `emp.lbl.gov/queues` | Historical completion/withdrawal rates → annual build caps by tech | 10 | **A** (xlsx) | Public report data, cite | Annual |
| `weather_re` | Wind/solar hourly profiles: NREL WIND Toolkit / NSRDB / Solar Power Data for Integration Studies, or Renewables.ninja; RTS-GMLC profiles for toys | NREL; Renewables.ninja (verify) | VRE capacity-factor series for zones/candidate sites (non-RTS cases) | 5, 11 | **A** via AWS/OEDI (verify access) | NREL data open (verify); Renewables.ninja CC BY-NC (verify; non-commercial limit matters for a consulting firm) | Static / annual |
| `ferc714` | FERC Form 714 hourly planning-area load (via PUDL) | FERC | Cross-check PJM zonal load | 11 | **P** | Public domain | Annual |

## Data acquisition plan
1. This cloud workspace cannot reach the sites above. **All downloads run in GitHub Actions** (`.github/workflows/data-*.yml`,
   skeleton at Gate 2), one workflow per source group, triggered manually (`workflow_dispatch`) and on a monthly schedule
   for incremental feeds. API keys (PJM, EIA, BEA, EPA) are repository secrets, never in files.
2. Each workflow writes **raw files** (unmodified, with HTTP date and sha256) as a versioned Actions artifact, plus a
   `manifest.json` (source_id, URL, retrieved date, vintage, sha256, byte size, licence class). Artifacts of licensed
   sources are marked `license_class=restricted` and never copied into the repo or client deliverables.
3. A second job turns raw → **canonical tables** per `data-schema.md` (Parquet) with provenance fields filled; artifact
   names `data-<source_id>-<vintage>`. Sessions download the artifact they need; the model never touches the network.
4. Sources marked **M** (PJM RPM/ELCC reports, IMM, NERC, RPS tables) are downloaded by the owner and uploaded to the
   repository `data/manual/<source_id>/` (non-restricted) or an Actions artifact (restricted); transcribed tables carry page refs in `basis`.
5. If a download is impossible, record it under "Needs owner" in PLAN.md and continue with the toy/test-system data.
6. Gate order: G1 needs none (hand-written cases + `bea_gdpdef`); G3 `pjm5`; G4 `rts_gmlc`; G6 `genx_examples`; G10 policy/queue;
   G11 the PJM single-zone slice (EIA/PUDL/CEMS/NEEDS/PJM/gas); G16 full pipeline, versioned.

## License risks
- **Daily hub gas (`gas_hubs`)**: ICE/Platts/NGI indices are commercial; redistribution and client-facing storage are likely
  prohibited, and even internal use needs a subscription. Risk: the largest backcast accuracy driver (DECISIONS 18) sits on
  the least available data. **Fallback**: EIA Henry Hub daily + regional monthly basis (`gas_basis_fallback`, est_level 3,
  confidence medium/low); **Owner decision (DECISIONS 27): no licence is bought; the fallback is the method.**
- **`west_hub_fut`**: licensed settlements; no purchase (DECISIONS 28) — use only freely available settles, else drop the Gate 17 futures comparison.
- **`pjm_dm2`**: usage terms limit redistribution; keep raw pulls in artifacts, publish only derived/aggregate metrics (verify).
- **`imm`**: copyrighted reports; transcribe numbers with citation, no re-publishing of text/charts.
- **`weather_re`**: Renewables.ninja is non-commercial (verify); prefer NREL data.
- **`genx_examples`** (GPL): use only as input data for a cross-check; no code reuse.
- **Client deliverables** must pass a licence check on every `source_id` they cite (`license_class` column in `sources.csv`).
- **Confidential data** (unit-level NERC GADS, PJM offer data with lag) is not assumed available; all such needs go through the hierarchy.

## Assumptions book format (`outputs/<run_id>/assumptions.md`; machine form `assumptions_cells.parquet`)
Generated from `resolved_provenance.parquet`, no hand editing. Sections:
1. **Run header**: run_id, fingerprint, case, base dollar year, formulation/schema versions, data vintages.
2. **Provenance mix**: per parameter family (capacity, heat rate, VOM, FOM, capex, outage, fuel price, load, profiles)
   share of capacity (MW) and of cells by `method` and `est_level`; table `family | observed | derived | estimated | assumed`.
3. **Source table**: each `source_id` used, vintage, retrieved, licence class.
4. **Dollar-year conversions**: per cost column the min/max input `dollar_year`, deflator factors, base year.
5. **Annualization table**: per candidate: $I, r, n, \kappa$, PFF, CRF, FOM, $C^{fix}$ (and override flags).
6. **Estimates and fits**: each regression/peer-group id, fit statistics, back-test error, units affected.
7. **Overrides and adjustments**: scenario overrides, CF values zeroed (<1e-3), `cfix_override`/`mc_override` used, weight/forced-period notes.
8. **Low-confidence list**: cells with `confidence=low` that touch > 1% of capacity, ranked.
