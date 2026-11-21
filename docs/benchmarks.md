# Benchmarks and scoreboard

Status: **proposed — owner approves at Gate 0 review.** Owner decisions this file implements: DECISIONS 5, 12, 18, 21, 23, 24.
Rule (DECISIONS 21): every target below is fixed **before** any backcast result exists. Changing a target later needs a DECISIONS entry with a reason that is not "the result missed it".
Targets marked **[P]** = *proposed, owner to confirm* (no literature threshold found). Citations marked **(verify)** were written from memory and must be checked before they are quoted to a client.

## 1. Evidence base for targets (honest summary)
- No published numeric acceptance threshold for hourly-LMP backcast error of PJM production-cost or capacity-expansion models is known to the author. Practitioner convention (vendor and consultancy PCM validation: PLEXOS, Aurora, GridView, ProMod) is to compare annual energy by fuel, monthly average LMPs, and price-duration curves against history, and to accept monthly-average errors of order 10–20% and poor hourly correlation. Treat this as convention, not citation. **(verify)**
- Related sources to read before Gate 12 sets baselines:
  - Monitoring Analytics, *State of the Market Report for PJM* (annual): LMP, marginal-fuel, congestion, DA/RT convergence and net-revenue tables. Primary reference for M5 and M8. Table names and years change; the data lead pins them per year.
  - Bloom et al. (NREL, 2016), Eastern Renewable Generation Integration Study: PLEXOS on the Eastern Interconnection with historical comparison. **(verify)**
  - Barrows et al. (2020), "The IEEE Reliability Test System: A Proposed 2019 Update," IEEE Trans. Power Syst. (RTS-GMLC). **(verify)**
  - Li, F., Bo, R. (2010), "Small test systems for power system economic studies," IEEE PES GM (PJM 5-bus). **(verify)**
  - Sioshansi, Denholm, Jenkin, Weiss (2009), "Estimating the value of electricity storage in PJM," *Energy Economics* 31(2); Byrne & Silva-Monroy (2012), Sandia SAND2012-3863, storage arbitrage revenue bounds. **(verify)**
  - Bessembinder & Lemmon (2002), *J. Finance* 57(3); Longstaff & Wang (2004), *J. Finance* 59(4): forward premia in PJM-type power markets.
  - Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* (time-series cross-validation, rolling origin).
- Targets are therefore two-tier: **good** and **acceptable**. Below *acceptable* a metric is a `fail`; between is `warn`.

## 2. What is compared with what
Actuals are real $2024 (BEA deflator, DECISIONS 24); model outputs are real $2024. Nominal only in §7.
On-peak = PJM definition (HE08–HE23 EPT, Mon–Fri excluding NERC holidays), off-peak = all other hours. Location = PJM pricing zone or hub (West, Dominion, etc.) per case; load-weighted zone LMP for zones. Actual DA/RT LMPs from `pjm` (Data Miner 2); IMM, EIA from `imm`, `eia923`.
Model-side price series: capex mode gives price only on rep periods, so (a) **block/monthly-average** metrics are computed by weighting periods by $w_p$ and mapping each rep period to the months it represents (DECISIONS 23); (b) **hourly metrics** (M1.3–M1.5 hourly parts) are computed only from the **full-year fixed-fleet dispatch** (backcast mode, DECISIONS 3), never from rep-period capex runs. Until Gate 7 (ORDC), hourly prices at capacity are non-unique (formulation §3.7, §9 Q2): hourly metrics at capacity-bound hours use the midpoint of the allowed price interval and are labelled `degenerate-midpoint`; the target applies only to block/monthly metrics before Gate 7.

## 3. Metrics in priority order
Definitions: bias = model − actual (MBE); MAE and RMSE on the stated aggregation; "rel" = divided by the actual mean of the same aggregation; r = Pearson correlation.

| ID | Metric (aggregation) | Good | Acceptable | Enabled / enforced |
|---|---|---|---|---|
| **M1 DA LMP (primary)** | | | | |
| M1.1 | Monthly mean DA LMP, on-peak and off-peak, per zone/hub: MAE rel | ≤10% | ≤20% **[P]** | G12 baseline, G13 enforced |
| M1.2 | Annual mean DA LMP bias, on-peak and off-peak: abs(bias) rel | ≤5% | ≤10% **[P]** | G12 / G13 |
| M1.3 | Hourly DA LMP shape (full-year fixed fleet): r of hourly series; RMSE rel reported, no target | ≥0.60 | ≥0.40 **[P]** | G12 |
| M1.4 | Price-duration curve: Wasserstein-1 distance / actual mean; plus signed error at p5, p25, p50, p75, p95, p99 and share of hours above $100 and at or below $0 (reported) | ≤0.15 | ≤0.25 **[P]** | G12 (hourly); monthly-block version G13 |
| M1.5 | Daily max–min DA spread (storage-relevant): monthly mean of daily (max−min), rel bias; and r of the 12 monthly values | rel bias ≤20%, r ≥0.80 | ≤35%, r ≥0.60 **[P]** | G12 (needs hourly) |
| M1.6 | Zone-to-hub basis: monthly mean (zone − West Hub), MAE in $/MWh | ≤$2 | ≤$4 **[P]** | G13 (copper plate: reported only); enforced G18 |
| **M2 RT LMP** | Same as M1.1, M1.2, M1.5. Single-price model is compared to RT as a second reference; DA is the target. | ≤12% / ≤6% / ≤25% | ≤22% / ≤12% / ≤40% **[P]** | G12, informational until G7 |
| **M3 Spreads** | | | | |
| M3.1 | Monthly on-peak minus off-peak mean spread, rel error | ≤20% | ≤35% **[P]** | G12 |
| M3.2 | DA–RT premium (actual only) reported next to model error so that error is read against it; IMM DA/RT convergence tables **(verify)** | report | report | G12 |
| **M4 Daily spread distribution** | p10/p50/p90 of daily DA max–min; share of days with spread ≥ $30 | ≤25% rel | ≤40% rel **[P]** | G12 |
| **M5 Marginal fuel shares** | Share of weighted hours by marginal fuel/tech from the price-setter report (formulation §4) vs IMM marginal-resource-by-fuel statistics (IMM tables are RT-based and by load-weighted or hours basis: pin the exact table per year **(verify)**). Fuel groups: gas, coal, nuclear/hydro/other, wind/solar, storage/DR, other. Metric: max abs share error over groups, and total variation distance | ≤5 pp, TV ≤10 pp | ≤10 pp, TV ≤20 pp **[P]** | G12 |
| **M6 Generation and CF** | | | | |
| M6.1 | Annual generation by fuel vs EIA-923 (PJM balancing-authority plants, EIA-860 BA field **(verify)**): abs error in share of total, and rel error in TWh for fuels >5% of generation | ≤2 pp, ≤5% | ≤4 pp, ≤10% **[P]** | G12 |
| M6.2 | Capacity factor by tech/fuel vs EIA-923/860: abs pp error (gas CC, gas CT/ST, coal, nuclear, hydro, wind, solar) | ≤5 pp (nuclear ≤2) | ≤8 pp (nuclear ≤4) **[P]** | G12 |
| M6.3 | Net imports and curtailment vs PJM reported (informational) | report | report | G12 |
| **M7 RPM (capacity)** | | | | |
| M7.1 | Model capacity price vs RPM Base Residual Auction clearing price, RTO and constrained LDAs, per delivery year ($/MW-day); cleared UCAP and reserve margin vs auction results | ≤$25 or ≤20% | ≤$50 or ≤35% **[P]** | G14 |
| M7.2 | Net CONE / reference-resource economics consistency with PJM published values | report | report | G14 |
| **M8 Storage revenue** | | | | |
| M8.1 | Perfect-foresight DA arbitrage revenue of a 100 MW, 4 h, RTE 85% unit, computed by the **same LP on actual prices** vs on **model prices**, $/kW-yr; same hub/zone and year | ≤20% rel | ≤35% **[P]** | G12 (arbitrage), full at G15 |
| M8.2 | Model storage net revenue (energy + reserves + capacity) vs IMM net-revenue and published-literature ranges (Sioshansi 2009; Byrne & Silva-Monroy 2012 **(verify)**) | inside literature/IMM range | within 25% of range edge **[P]** | G15, directional only |
M8.1 is the cleanest storage test: it needs no storage in the actual fleet and isolates price-shape error, which is what drives storage value. Perfect-foresight revenue overstates real storage revenue; the metric compares like with like (same algorithm both sides) and the client report states this.

## 4. Calibration, hold-out, regression rule
- **Years (PLAN Gate 17):** 2022, 2023, 2024. Proposed split **[P]**: calibrate on 2022+2023, hold out 2024 (rolling origin, forward in time; Hyndman & Athanasopoulos). Secondary leave-one-year-out folds (hold out 2022, then 2023) are reported to expose instability; 2022 is a gas-price-shock year with Winter Storm Elliott and is the hardest.
- **Development vs sealed hold-out [P]:** Gates 11–16 need a year to develop on. Use **2023 as the development year** and keep **2024 sealed** (no metric computed or looked at) until Gate 13 baseline freeze, then used only by the regression rule. Reason: repeated use of one hold-out year for accept/reject decisions is data snooping and shrinks its value (owner question in the Gate 0 review).
- **What calibration may touch:** only the named parameters (offer adders by tech/season, outage rates, import/export profile scalars, hydro/pumped-storage energy budgets, clustering k). Every calibrated value goes in the assumptions book with `method=estimated`, fit years and fit statistics. Hold-out data never enters any fit, including the choice of k.
- **Regression rule (DECISIONS 5, enforced from Gate 5 on test systems and Gate 12 on PJM):** a merge to the gate branch must not worsen the hold-out scoreboard: for each M1.1, M1.2, M1.5, M5, M6.1 value (aggregate over locations), `new ≤ old + ε`, with ε = max(1% rel of old, the 90th-percentile run-to-run variation from re-running with 5 clustering seeds). Any worsening beyond ε needs a written waiver in `reports/complexity-ledger.md` that the owner accepts at the gate. Fingerprint-identical re-runs must reproduce values exactly (ε=0).
- **Gate 5–10 features** are judged on the RTS-GMLC full-year reference (test-ladder §6) until Gate 12; from Gate 12 on they must also hold or improve the PJM scoreboard (ablation switch on/off).

## 5. Scoring on block averages until Gate 7 (DECISIONS 23)
Before reserves/ORDC exist, capex-mode LMPs at capacity are non-unique (§9 Q2). Therefore: M1.1–M1.2, M3.1, M5 are scored on weighted **block and monthly averages** (on-peak/off-peak by month); M1.3–M1.5 hourly parts are reported as baselines with `status=baseline` and become enforceable at Gate 7 (shortage pricing) when a unique price exists in scarcity hours.

## 6. Test-ladder targets
Tolerances are for the model against the named reference; "explained" means each residual is traced to a documented formulation difference.

| Rung (gate) | Compared | Tolerance |
|---|---|---|
| Analytic toys T1–T4 (G1) | objective, capacities, block-average prices, rents, congestion rent vs closed forms in formulation §10 | objective and capacities rel 1e-6; block prices rel 1e-5; hourly price only inside the interval allowed by price-setter class |
| PJM 5-bus (G3) | nodal LMP and congestion component per bus, flows, dispatch vs published case results (Li & Bo 2010) | LMP abs 0.01 $/MWh (published values are rounded); dispatch abs 0.1 MW; price-setter class correct at every bus-hour. Spec gap: needs DC flow/PTDF, see report |
| RTS-GMLC dispatch (G4) | full-year fixed-fleet dispatch vs the published reference production-cost results (exact files: verify in the RTS-GMLC repo) : total variable cost, generation by tech, zonal mean price | cost ≤5%, tech share ≤3 pp, zonal price MAE ≤10% **[P]** (no UC yet; tighten to 2%/2 pp/5% after G9) |
| RTS-GMLC rep periods + storage (G5) | rep-period run vs the full-year fixed-fleet dispatch of the same fleet: annual variable cost, net-load duration curve, storage cycles/revenue, capacity mix if expansion enabled | cost ≤2%; net-load duration W1/mean ≤3%; peak net load error ≤1%; storage revenue ≤10% **[P]**; capacity per tech ≤10% |
| Reserves, transmission, UC (G7–G9) | same RTS reference after each feature; reserve price vs reference where published | must not exceed G5 errors; new feature judged by ledger |
| GenX cross-check (G6) | same inputs run in GenX (e.g. 3-zone example): objective, capacity by tech, annual mean zonal price, dispatch by tech | formulation-matched options: objective rel 1e-3, capacity per tech ≤1% of peak load, annual zonal price rel 1e-2; every difference larger than that explained line by line. Unexplained >0.5% objective = fail |
| One PJM zone (G11–G12) | M1–M6 for one zone, 2023 development year | G12: baselines recorded, no pass/fail; hard checks: balance, weights, provenance coverage ≥ stated in data schema |
| PJM single node (G13) | M1.1, M1.2, M3.1, M5, M6 for PJM-wide copper plate (West Hub as price proxy) | `acceptable` tier required; sealed 2024 first scored here |
| PJM zonal (G14–G18) | all of §3 incl. M7, M8, M1.6 and futures (§7) | `good` tier on hold-out for M1.1, M1.2, M6.1; others `acceptable` |

## 7. Forward runs vs PJM West Hub futures (Gate 17)
- **Instrument:** monthly PJM Western Hub on-peak (and off-peak where listed) futures, which settle against the **real-time** hub LMP, and calendar strips, from ICE (and CME where listed). Settlements are **licensed data**; the data lead checks terms before any use or redistribution (`source_id` to be added; verify availability of historical settles). No futures data is committed to the repo if the licence forbids it.
- **Method:** pick quote dates (e.g. last trading day of each quarter); run the model forward for the delivery year using fuel forwards of the same date (NYMEX Henry Hub futures plus hub basis) and load/fleet as known at that date; convert real-2024$ output to nominal using the inflation path declared in the run config; compare monthly on-peak/off-peak West Hub block averages and the calendar strip.
- **Metrics:** signed gap and abs gap rel to the future, for 1-year-ahead strips and months 1–24 [P: report only, target abs gap ≤15% on 12-month strips as sanity check]. **Baseline for context:** the gap between the same futures and the **realized** price in the delivery year. The model is not expected to beat the futures; if model-vs-realized error is below futures-vs-realized error that is a finding, not a requirement.
- **Caveats:** (1) risk premium: futures are not unbiased forecasts (Bessembinder & Lemmon 2002; Longstaff & Wang 2004) so a persistent gap is not by itself model error; (2) futures settle on RT, the model targets DA; (3) thin liquidity beyond ~2 years and in off-peak contracts; (4) futures embed weather and outage expectations, our runs use normal-weather representative periods; (5) nominal vs real conversion adds its own error; (6) licensing.

## 8. Scoreboard output
Per run, `reports/scoreboard/<run_id>.csv` (long format, one row per metric value) and appended to `reports/scoreboard/history.csv`; `reports/scoreboard/latest.md` is a rendered summary table with deltas vs the previous gate.

Columns: `run_id`, `fingerprint`, `formulation_version`, `git_commit`, `gate`, `case` (e.g. `rts_gmlc`, `pjm_zone_dom`), `year`, `split` (`dev`/`calib`/`holdout`/`test`), `ts_mode` (`full_blocks`/`clustered`), `features_on` (sorted switch list), `location` (zone/hub id), `metric_id` (M1.1 …), `block` (`onpeak`/`offpeak`/`all`/`hourly`), `period` (`2023-07`/`annual`), `value`, `unit`, `n_obs`, `target_good`, `target_acceptable`, `status` (`good`/`acceptable`/`fail`/`baseline`/`info`), `prev_run_id`, `prev_value`, `delta`, `ref_source_id`, `ref_vintage`, `degenerate_midpoint` (bool), `notes`.
Rules: rows are never overwritten; `status=baseline` rows have empty targets until the enforcing gate; the scoreboard is computed by one function (`capex.scoreboard`), reads only audit outputs and `ref_*` tables, and is fingerprint-tagged so a score is reproducible.
