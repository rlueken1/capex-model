# cases/rts_gmlc — RTS-GMLC as a fixed-fleet case (prep item P5)

Converted from the vendored raw data `cases/raw/rts_gmlc/` (upstream commit `3ece0d3`, fetched 2026-11-26, see
`PROVENANCE.md` there) into schema S-0.1 / formulation F-0.2. Regenerate everything, byte-identical, with
`python scripts/convert_rts_gmlc.py` (stdlib + pandas/numpy/pyyaml; no network). Purpose: Gate 4 full-year fixed-fleet
dispatch check against the PLEXOS DA reference (`allTX` / `noTX`). **Licence:** upstream states no licence terms
(PROVENANCE.md); internal test system only, never a client deliverable (DECISIONS 34).

## Structural choices
- **Time.** 2020 is a leap year, 8784 h = 122 x 72. The full year is 122 periods `p001..p122`, each a real consecutive
  72-h block (`rep_kind=full_block`, `weight_blocks=1`, `days_represented=3`, `source_start_date` set), so the weight
  identity sum w = 366/3 holds and no single 8784-h period is needed (loader fixes T=72). Hour index h (0-based) maps to
  period `h//72+1`, `t=h%72+1`. Upstream series are 8784 consecutive local hours with no DST gap.
- **Fixed fleet.** All resources `status=existing`, `k0_mw=PMax`, `xmax=0`; no candidates, so no capex, finance or
  annualization (a placeholder `finance` class `rts_unused` exists only because the loader requires the table).
- **Zones** `r1,r2,r3` = RTS Areas 1-3 (bus.csv `Area`); generators are assigned through their bus.
- **Case-local `sources.csv`.** `data/common/sources.csv` lacks an `rts_gmlc` row. Editing it would change the sha256 that
  the T1-T4 manifests pin, so this case points its `sources` table at a local copy (common rows + `rts_gmlc`).
  `data/common/sources.csv` and all T* cases are untouched. Follow-up at Gate 4 (DECISIONS 38, 40): append the
  `rts_gmlc` row to the common file and point this case at it; no T* re-hash is needed since DECISIONS 40 (registry not pinned).
- **Availability is `availability.csv.gz`.** 81 VRE series x 8784 h = 711,504 rows (20 MB as text); gzip (2.6 MB) is read
  natively by the loader's `pd.read_csv`. Not Parquet (loader reads CSV only).
- **Sidecar files the loader ignores (not in manifest, not hashed):** `provenance_cells.csv` (387 per-cell overrides, the
  schema section 0 design), `assumptions.csv` (assumption/gap register).

## Mapping raw -> schema
| Schema table.column | Raw source | Method |
|---|---|---|
| `zones` | `bus.csv` Area (3) | observed |
| `load.demand_mw` | `timeseries_data_files/Load/DAY_AHEAD_regional_Load.csv` (MW, 8784 h x 3 areas) | observed (DA forecast); the series is already regional, so no bus aggregation is needed. Its max equals the Area bus.csv `MW Load` sum (2850), a unit check; `net_of_btm=False` (RTPV is supply) |
| `links.ntc_*_mw` | `branch.csv` inter-area branches, `Cont Rating`, summed per area pair, symmetric | derived (est_level 1), medium |
| `links` DC | `dc_branch.csv` DC1 (bus 113 Area 1 -> 316 Area 3), `MW Load` 100 MW used as symmetric rating | assumed, low |
| `resources.k0_mw`, `zone`, `vom_usd_mwh` | `gen.csv` `PMax MW`, Bus ID -> Area, `VOM` (all 0) | observed (zone derived) |
| `resources.heat_rate_mmbtu_mwh` | `gen.csv` `HR_avg_0`, `HR_incr_1..3`, `Output_pct_0..3` | derived, est_level 1, high (below) |
| `fuel_prices`, `fuel_map` | `gen.csv` `Fuel Price $/MMBTU`; 4 hubs `rts_oil/coal/gas/nuclear`, constant all year | observed |
| `availability` (VRE) | PV, RTPV, WIND, HYDRO series (MW) / PMax; CSP `Natural_Inflow` (MW) / PMax, capped at 1 | derived, est_level 1 |
| storage `e0_mwh` | `storage.csv` head-reservoir `Max Volume GWh` x 1000 = 150 MWh (tail identical) | derived |
| storage `eta_c/eta_d` | `gen.csv` round-trip 85% -> sqrt(0.85) each | estimated, level 4, medium |
| `x_*` columns | `gen.csv` bus, PMin, FOR, scheduled maint weeks, ramp, min up/down, plus no-load and alt heat rates | observed/derived, kept for Gates 4/9 |

**Heat rate and marginal cost.** `gen.csv` gives the fuel curve as `HR_avg_0` (BTU/kWh at `Output_pct_0` x PMax) and
incremental rates `HR_incr_k` between points. Fuel input F0 = HR_avg_0 x P0, F_k = F_(k-1) + HR_incr_k x (P_k - P_(k-1)).
`heat_rate_mmbtu_mwh` = secant slope (F_N - F_0)/(P_N - P_0) in MMBtu/MWh (BTU/kWh / 1000): the marginal fuel burn, since the
model's `MC = HR x phi + VOM` has no no-load term. Nuclear has a flat curve (all `HR_incr` 0), so it uses the full-load average
(10.0). Alternatives are kept in `x_hr_full_load_avg_mmbtu_mwh` and `x_noload_mmbtu_h` (the intercept, to be used if Gate 9
adds no-load cost). Resulting MC ($/MWh): nuclear 8.0, coal 16.4-25.1, gas CC 24.1-29.5, gas CT 25.9-39.5, oil CT 88.8-101.0,
oil ST 100.0-127.7. This is a modelling choice to confirm (DECISIONS candidate), not a data fact.

**Link rating choice back-test.** PLEXOS `allTX` DA flow on CB-1 reaches exactly 500 MW (the Cont Rating; LTE is 600), so
`Cont Rating` is what the reference used. Ratings: r1-r2 1175 (AB1 175 + AB2 500 + AB3 500), r1-r3 500 (CA-1), r2-r3 500 (CB-1),
DC r1-r3 100. Reactances are not carried (no DC power flow before Gate 3's scope; `allTX` flows will differ from a transport model).

## Totals (MW) vs upstream `gen.csv` (no published table was available offline; the compared totals are gen.csv sums)
| Fuel / tech | n | loaded k0_mw | gen.csv PMax sum |
|---|---|---|---|
| coal | 16 | 2317.0 | 2317.0 |
| gas CC / CT | 10 / 27 | 3550.0 / 1485.0 | 3550.0 / 1485.0 |
| oil CT / ST | 12 / 7 | 240.0 / 84.0 | 240.0 / 84.0 |
| nuclear | 1 | 400.0 | 400.0 |
| hydro | 20 | 1000.0 | 1000.0 |
| PV / RTPV / wind / CSP | 25 / 31 / 4 / 1 | 1554.5 / 1161.4 / 2507.9 / 200.0 | same |
| storage (pumped, 150 MWh) | 1 | 50.0 | 50.0 |
| **total** | **154 gen + 1 ST = 155** | **14,549.8** | **14,549.8** (157 rows; 3 sync condensers 0 MW excluded) |
Load: 37.66 TWh in 2020; coincident peak 8191.8 MW (sum of area peaks 8550 MW).

## Provenance coverage
Every value-bearing table (`resources`, `links`, `load_meta`, `finance`, `availability_meta`, `fuel_prices_meta`, `zones`)
carries all P fields on every row (0 blanks); `source_id=rts_gmlc`, vintage `rts_gmlc@3ece0d3`, retrieved 2026-11-26.
Row default for resources is observed/high; `provenance_cells.csv` overrides 387 cells: `heat_rate` 73 derived (L1), `zone` 155
derived (L1), `dollar_year` 155 assumed/low, storage `e0` derived, `eta_c/eta_d` estimated (L4), `selfdis` assumed/low.
Method mix by capacity for resources.k0_mw: 100% observed. By row: links 3 derived + 1 assumed; availability 81/81 derived; load,
zones, fuel prices observed. The estimation hierarchy was needed only for storage efficiency (level 4: symmetric split of the
published round trip). No estimates were back-tested beyond the link-rating check above; none involve unit statistics, so there
is nothing to hold out.

## Gaps and assumptions (machine-readable: `assumptions.csv`)
- **A1 dollar year.** Upstream states none. Set to 2024 (base year, factor 1), `assumed/low`. `data/common/deflator.csv` has only a
  placeholder 2024 row, so any other year would fail the loader. Affects only fuel prices; VOM = 0.
- **A6 / G5 outages.** TH availability is the default 1.0. Forced-outage rates and maintenance weeks are kept as `x_` columns; how the
  PLEXOS reference treated outages is unverified. Compare the committed MW in the reference before attributing dispatch differences.
- **A7 hydro, A8 RTPV.** Both are fixed upstream schedules (PMin = PMax = series); here they are curtailable VRE (no must-take flag).
  Hydro reservoirs and `Inflow Limit` are not modeled. Availability values below 1e-3 (1060) will be zeroed by the loader.
- **G2 costs.** FOM and capex are not in RTS-GMLC and are left null (not needed for dispatch; constant in Z0). Filling them
  (NREL ATB, est_level 4) needs an Actions download.
- **G3 CSP.** Modeled as VRE with availability min(inflow/200, 1); inflow above 200 MW (clipped) and 1.2 GWh thermal storage are lost.
- **G4 UC data** (Pmin, ramps, min up/down, start heat/cost): `x_` columns only (Pmin, ramp, min up/down) or not carried (starts).
- **Storage initial SOC** (0.075 GWh) cannot be expressed; period closure is cyclic per 72 h block. Inter-block SOC chaining is not available
  until `storage.inter_period` and `block_map` (Gate 5).
- **G5 reserves** (Spin/Reg/Flex requirements) not modeled before Gate 7; PLEXOS DA prices include reserve effects.
- **Reference weeks:** PLEXOS solution files cover only 336 h (2020-07-05 to 07-18); the full-year check can compare only that window.

## Loader smoke check
`capex.data.load_case("cases/rts_gmlc")` validates: 3 zones, 122 periods (sum w = 122), demand (3,122,72), 154 gen + 1 storage, 4 links,
sha256 of all tables match. No solve was run.
