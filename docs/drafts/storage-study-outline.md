# DRAFT for owner — P9, not approved: Gate 15 storage value study outline

Status: **DRAFT (prep item P9, 2026-11-26).** Not part of any gate criteria. Owner approves or amends at the Gate 14 -> 15
boundary. Nothing here changes `docs/formulation.md`. Dollar-year convention: real $2024 (DECISIONS 24) unless stated.
Citation rule: every number has a source tag `[Ax]` (section 9) or is marked **(verify)**. "(computed)" = arithmetic on cited
inputs shown in the text. Unsourced priors are labelled "prior" and must be replaced by model/backcast results before any
client sees them.

## 1. Purpose, audience, prerequisites

**Purpose.** Answer, for PJM only, "what does a standalone battery earn from energy arbitrage, reserves and capacity, and does
that cover its annualized cost, by duration, zone and scenario?" using public data only (DECISIONS 26/28) and a model whose
hub price spreads have been backcast (benchmarks M1.5, M3, M4, M8.1).

**Audience (the three client types in client-questions.md Q1-Q6):**
- Utility / planner: how much storage is economic, effect on capacity needs and prices (Q2, Q4, Q11).
- IPP / developer: revenue stack by duration and zone, sensitivity to gas, ELCC, collar (Q1, Q3, Q4, Q6).
- Investor / lender's engineer: downside cases, scarcity dependence, perfect-foresight haircut, confidence rating (Q1, Q5, Q12).

**Gates that must pass first (hard dependencies):**
| Gate | Why the study needs it |
|---|---|
| G5 rep periods + inter-period SOC | storage dispatch, long-duration SOC across periods; ablation of inter-period linking is part of the evidence [gate5 draft] |
| G7 reserves + ORDC | reserve revenue stream and a unique scarcity price (benchmarks section 5: hourly metrics only enforceable after G7) |
| G8 zonal transmission | location question Q6; zone vs hub basis (indicative only; nodal out of scope) |
| G10 policy + build realism | build limits (queue), RGGI/RPS, credits; storage ITC treatment under current law (verify) |
| G11-G13 PJM data slice, scoreboard v0, single node | PJM prices, fleet, backcast baselines; M1.x and M8.1 computed |
| G14 capacity market | VRR dual, ELCC classes, collar switch `rpm.collar` [pjm-rpm-notes 6.9] |
| G16 data pipeline (soft) | ATB, AEO, EIA-860 inputs versioned; if not done, the study uses the G11 slice inputs and says so |
| G17 hold-out (soft) | an uncalibrated-on-2024 check is what makes "client-grade" defensible; without it label results "indicative" |

Hard rule: no client-grade claim unless M8.1 and M1.5 are at least `acceptable` on the hold-out year (benchmarks section 3).

## 2. Client questions the study answers

| # | Question the study answers | client-questions.md |
|---|---|---|
| S1 | What does a 100 MW / 4 h battery in zone X earn per kW-yr from energy, reserves, capacity? | Q1 |
| S2 | Does that revenue cover annualized cost (levelized $/kW-yr), and what build cost is breakeven? | Q1, Q8 (pattern) |
| S3 | Which duration (2/4/6/8 h) has the best net value per kW and per kWh? | Q2 |
| S4 | How much storage is economic by 2030/2035 before spreads erode (saturation curve)? | Q2 |
| S5 | How sensitive is revenue to gas price, load growth/data centers, build-out of solar/wind, retirements? | Q3, Q11 |
| S6 | How much comes from capacity (ELCC x clearing price), and what if the collar ends or ELCC falls? | Q4 |
| S7 | How much revenue depends on scarcity hours, and what if shortage pricing is not repeated (no Elliott-type event)? | Q5, Q12 |
| S8 | Does location matter: zone vs West Hub basis, congested interfaces? | Q6 |
| S9 | How do storage additions feed back on price spreads, capacity prices and the marginal fuel at charge/discharge hours? | Q2, Q3, Q4 |
| S10 | What do I put in a pro forma as a P50 and a downside, after a perfect-foresight haircut? | Q1, Q5 |
| S11 | How reliable is the answer: provenance mix, backcast error through the storage lens, price-setter report? | Q14 |
| S12 | How does storage compare with a new CT or CC as capacity/energy supplier (net revenue vs cost)? | Q8, Q7 (adjacent) |

No client question exists today for "storage value under ancillary-service market saturation" or "hybrid solar+storage"; both are
out of scope for this study (proposal: add S-level note only, decision 4).

## 3. Study design

### 3.1 Scope: zones, years, durations
- **Zones/hubs.** Base: PJM-wide copper plate with West Hub as price proxy (G13 state) for the headline; then 3-5 zones
  from G8/G18 state (candidates: Dominion, ComEd, PSEG/EastNJ, a West-side zone) - choose by IMM congestion and queue
  data **(verify)**. Nodal prices out of scope; say so on page 1 of every deliverable (Q6).
- **Years.** Backcast/validation year 2023 (development) and 2024 (sealed, benchmarks section 4); forward study years 2030 and
  2035 (real $2024), with 2027 as near-term bracket tied to cleared BRA delivery years (2026/27-2028/29 all cleared at the cap
  [pjm-rpm-notes 4]).
- **Durations.** 2, 4, 6, 8 h at fixed 100 MW discharge. Model storage as MW (`xP`) and MWh (`xE`) independent variables, so
  duration is an output in the expansion runs and a fixed input in the per-unit revenue runs. ELCC classes exist only for
  4/6/8/10 h [A2: S21]; 2 h has no published class, so its capacity credit is a stated assumption (default: 4-h class
  rating scaled by duration ratio, flagged `method=assumed`) **(verify against Manual 21A)**.
- **Round-trip efficiency, degradation, availability:** section 6 values; availability as forced-outage factor in the
  capacity (ELCC) step only, not in energy dispatch, to avoid double counting.

### 3.2 Scenarios and sensitivities
Base case plus one-at-a-time sweeps (tornado) and three combined cases. Each scenario is one scenario-manager entry with a
fingerprint (G1).

| Axis | Low | Base | High | Provenance note |
|---|---|---|---|---|
| Gas price (daily hub series, DECISIONS 29) | 2024 strip | AEO reference (verify vintage) | 2022-like | EIA AEO [A7] (verify); 2022 is a backcast year |
| Load growth / data centers | PJM forecast less step | PJM load forecast (vintage recorded) | forecast + extra GW | PJM load forecast (verify vintage) [pjm-rpm-notes 6.10] |
| ELCC by duration | class ratings fall 10 pp (portfolio effect) | published 2028/29 ratings | 2027/28 ratings | classes in section 5.2 [A2]; beyond 2028/29 preliminary only (verify) |
| Capacity price | collar on (cap ~$325 UCAP 2028/29) | collar on to DY 2029/30 then off (verify) | uncollared ($554.72 RTO 2028/29 sim) | [A2: S1a] |
| Build cost | ATB moderate | ATB moderate | ATB advanced / conservative | ATB [A1]; absolute $/kWh (verify) |
| Renewables/retirements | policy-light | G10 policy + announced retirements | accelerated retirements | G10 inputs |
| Scarcity | no forced extreme periods | forced Elliott-type period in 1 of N years | forced every year | G12 forced periods; Q5 |

Combined cases: "Developer base", "Collar ends + weak ELCC" (downside), "Data-center surge + high gas" (upside).

### 3.3 Revenue stacking: what is co-optimized and what is ex post
| Stream | Treatment | Reason |
|---|---|---|
| Energy arbitrage (DA price) | **co-optimized** in capex LP over weighted rep periods with inter-period SOC | core LP; storage is a resource with SOC dynamics |
| Reserves (reg/sync/non-sync via ORDC) | **co-optimized** from G7: reserve MW consume power/energy headroom constraints | capacity headroom is shared with energy; ex post addition would double count the same MW |
| Capacity (RPM) | **co-optimized only through accredited MW** (ELCC x MW into the VRR supply row, G14); revenue = dual price x ELCC x MW, an annual flow | capacity price is a system dual, not an hourly flow |
| Ancillary products outside ORDC (regulation performance, black start) | **not modeled**; stated as excluded | no public price series in scope; avoid claiming |
| RT premium / DA-RT spread | **not modeled** (single price); reported as context (M3.2) and as an explicit downside | model targets DA |

**Avoiding double counting (checklist the verifier tests):**
1. Reserve MW and energy MW from the same unit cannot exceed discharge/charge limits in any hour (constraint, not ex post).
2. Capacity ELCC is a function of duration class and does not scale with the energy/reserve dispatch; revenue is not reduced for
   cycling, so cap duty-cycle claims (a 4 h class cannot also be sold as 8 h).
3. Zero-profit check: in the expansion run, total revenue (energy + reserves + capacity) of the marginal MW equals annualized
   cost; the revenue table must reconcile to the objective decomposition (audit layer, formulation sec 8.5).
4. Ex post revenue tables sum streams that come from the same solved dispatch only; no "stack of maxima" from separate runs.
5. PTC/ITC and RGGI effects are reported as a separate line, never netted silently.

### 3.4 Perfect-foresight bias: haircut and disclosure
The LP knows all prices in each period (perfect foresight within the rep period and across SOC links). It overstates actual
revenue. Handling:
- Disclose on every revenue table: "perfect-foresight DA arbitrage upper bound".
- Quantify with the backcast: M8.1 compares the same LP on actual vs model prices (same algorithm, like with like).
- Provide an **ex post realized-style bound**: run storage dispatch on lagged or day-ahead-forecast prices (e.g. same-hour-last-week
  forecast) on 2023/2024 actual prices to estimate foresight loss. Sioshansi et al. and Byrne & Silva-Monroy report arbitrage
  bounds and foresight effects [A5] (verify); report the ratio as an empirical haircut with range, not a single point.
- Also disclose: rep periods smooth extremes, so spreads on the extreme tail are conservative while foresight is optimistic. The two
  errors are not assumed to cancel; the full-year fixed-fleet dispatch (allowed one-off per CLAUDE.md) measures the rep-period error.
- Headline: P50 = perfect-foresight x (1 - empirical haircut), with the unhaircut value shown alongside. The haircut value is
  an output of the backcast, so it is not stated here (prior only: "meaningful, order 10-30%" is unsourced; verify).

## 4. Outputs: tables and charts

### 4.1 Tables
- T1 Revenue stack by duration, zone, year: energy, reserves, capacity, total, $/kW-yr and $/kWh-yr. (S1, S3)
- T2 Annualized cost (levelized $/kW-yr): capex x CRF + FOM + augmentation/replacement, with dollar year, WACC, life stated
  (formulation single annualization function). (S2)
- T3 Net revenue = T1 - T2, plus breakeven build cost ($/kWh) per duration. (S2, S3)
- T4 Scenario matrix: net revenue for each scenario x duration; tornado data. (S5-S7)
- T5 Saturation table: storage GW installed vs marginal net revenue. (S4, S9)
- T6 Provenance table: share of inputs by method (observed/derived/estimated/assumed) from the assumptions book. (S11)
- T7 Backcast table: M1.5, M3.1, M4, M8.1 by hub-year with status. (S11, section 7)

### 4.2 Charts (6-10)
| # | Chart | X | Y | Units | Question |
|---|---|---|---|---|---|
| C1 | Revenue stack by duration (stacked bars: energy, reserves, capacity) | duration 2/4/6/8 h | revenue, $/kW-yr | real $2024 | S1, S3 |
| C2 | Net revenue vs annualized cost (bars with cost line; error bars = haircut range) | duration x scenario | $/kW-yr | levelized, dollar-year stated | S2 |
| C3 | Breakeven build cost | duration | $/kWh (and $/kW) | real $2024 | S2; compare with ATB band |
| C4 | Value vs penetration (saturation curve for energy and total) | installed storage GW (by duration) | marginal net revenue, $/kW-yr | real $2024 | S4, S9 |
| C5 | Tornado: net revenue change for 4 h unit | sensitivity bar | delta $/kW-yr | real $2024 | S5 |
| C6 | Capacity stream vs ELCC and collar | clearing price $/MW-day | capacity revenue $/kW-yr, lines per ELCC | UCAP price; ELCC % | S6 |
| C7 | Hours-at-margin / price-setter summary at charge and discharge hours | marginal fuel (gas, coal, nuclear/hydro, wind/solar, storage, scarcity) | share of charge hours and of discharge hours, % | weighted hours | S9, S11 (M5 view) |
| C8 | Revenue by hour class (scarcity vs normal hours) | scenario with/without forced extreme period | revenue share, % | - | S7 |
| C9 | Daily price spread distribution, model vs actual hub | daily spread $/MWh (p10/p50/p90) | frequency or quantile | $/MWh real 2024 | section 7 |
| C10 | Zone vs hub basis | zone | net revenue difference vs West Hub, $/kW-yr | real $2024 | S8 |

All charts: legend with scenario ID and fingerprint; axis label shows dollar-year; shaded band where a haircut applies.

## 5. Sanity ranges (to be replaced with results; every figure cited or marked)
These are for the "would a client believe this?" test. Out-of-range model output triggers investigation, not tuning.

### 5.1 Energy arbitrage ($/kW-yr)
- Published PJM storage arbitrage values: Sioshansi et al. 2009 (PJM, 2002-2007 prices, 1 MW unit) and Byrne & Silva-Monroy 2012
  [A5] are the standard references; numbers not retrieved in this pass: **(verify)**. Their era (pre-shale-gas spread
  structure, different fuel mix) limits transfer.
- Recent PJM battery revenue benchmarks exist from commercial analysts (Modo Energy monthly PJM BESS benchmark, 2025-2026 [A4])
  and IMM State of the Market reports [A3]. Values in the search snippets were not readable in this pass: **(verify)**. Modo is
  a paid-leaning source; use only as a public cross-check where freely readable, never as an input (DECISIONS 26/28).
- Prior (unsourced, to be replaced): perfect-foresight 4 h DA arbitrage at West Hub in 2023-2024 is roughly tens of $/kW-yr
  rather than hundreds. Computation target: M8.1 on actual 2023/2024 DA hub prices.
- Internal consistency test: arbitrage revenue per kW-yr <= (mean of top-4 daily spread-hours) x 365 x RTE factor; check with
  the actual daily spread distribution (M4). (computed bound)

### 5.2 Capacity revenue (ELCC x BRA price)
ELCC (% of ICAP) from pjm-rpm-notes 3.2 [A2: S19, S8a, S21]; prices from section 4 there [A2: S5a, S3a, S1a].
| Delivery year | RTO price $/MW-day UCAP | 4 h ELCC | 4 h capacity revenue, $/kW-yr (computed) |
|---|---|---|---|
| 2026/27 | 329.17 (cap) | 50% | 60.1 |
| 2027/28 | 333.44 (cap) | 58% | 70.6 |
| 2028/29 | 325.00 (cap) | 59% | 70.0 |
| 2028/29 uncollared simulation | 554.72 | 59% | 119.5 |
Computation: ELCC x price x 365 / 1000. Duration spread at the 2028/29 cap: 6 h (68%) 80.7; 8 h (71%) 84.2; 10 h (78%) 92.4 (computed).
Caveats: ELCC applies to ICAP (nameplate discharge MW); price is per UCAP MW. Collar contamination: three consecutive
cleared years at the cap say nothing about model economics [A2 sec 6]. Beyond 2028/29 both ELCC and price are forecasts
**(verify)**; the study must show collar-on and collar-off.
Marginal ELCC decline with penetration (class rating falls as storage is added) is a second-order switch in the capacity module
[A2 sec 6.4]; the saturation chart (C4) should show it separately from energy saturation.

### 5.3 Reserve revenue
- Regulation: PJM battery regulation revenues fell with market saturation 2023-2025 per commercial analyses [A4] and FERC EQR
  data **(verify)**. No usable number retrieved; do not state a range.
- Spinning/non-synchronous reserve: PJM reserve prices typically low outside scarcity **(verify with IMM)**. Model reserve revenue
  (G7) is ORDC-based and mostly scarcity-driven; compare with IMM reserve market tables [A3] for the backcast year.
- Gate: reserve revenue > capacity or arbitrage revenue in the base case is a red flag unless forced scarcity periods drive it.

### 5.4 Cost and technical parameters
| Parameter | Value | Source |
|---|---|---|
| Capex (4 h, utility-scale) | absolute 2023-2030 $/kWh not retrieved in this pass; ATB moderate scenario gives 37% reduction 2022-2035 for 60 MW, 4 h; base year 2022$ | [A1] absolute $/kWh **(verify)** |
| Fixed O&M | 2.5% of capital cost per year, includes augmentation; no variable O&M | [A1] |
| Round-trip efficiency | 85% | [A1] |
| Lifetime / analysis life | 15 years | [A1] |
| Degradation | ATB gives no explicit rate (depends on usage; augmentation folded into FOM) | [A1]; manufacturer/LBNL rates **(verify)** |
| WACC for annualization | study value from formulation annualization function; project finance 7-10% real is a prior **(verify)** | assumed |
| ITC for standalone storage | available under current law at 30% base, with conditions **(verify)** | G10 |
Illustrative annualization (formula only, placeholder capex to show scale): annual cost $/kW-yr = capex $/kW x (CRF + FOM%);
CRF(8%, 15 yr) = 0.1168 (computed); at 2.5% FOM the factor is 0.1418 (computed), i.e. each $100/kW of capex costs about
$14/kW-yr. Capex $/kW = $/kWh x hours. Report both $/kW-yr and $/kWh-yr because duration changes the comparison.

## 6. Method details that change numbers (fix before running)
- Dollar year: real $2024 throughout; ATB values converted from 2022$ with the BEA deflator (DECISIONS 24); stated on each chart.
- One annualization function (formulation sec 5.2): same WACC and life for all durations; state augmentation/replacement.
- Rep periods: weights $w_p$, forced peak/scarcity periods, inter-period SOC [gate5 draft]. Duration 6-8 h results depend on
  inter-period linking; show the ablation (linking off) in the evidence (G5 ledger).
- Charge/discharge price-setting: report who sets the price at charge hours (e.g. nuclear/coal -> low) vs discharge hours (gas
  -> high); this drives sensitivity to gas and retirements.
- Storage self-effect on prices: the expansion run (xP, xE endogenous) captures it; the per-unit revenue run is a price-taker
  on a fixed fleet; label which is which in every table.
- Load/fleet vintages and PJM load forecast vintage recorded in the assumptions book (pjm-rpm-notes 6.10).

## 7. Benchmarks and validation the study must show
1. **Hub DA spread backcast (benchmarks M1.5, M3.1, M4):** modeled vs actual West Hub daily max-min spread, monthly mean and
   p10/p50/p90 for 2023 (development) and 2024 (sealed). Target good: rel bias <= 20%, r >= 0.80; acceptable <= 35%, r >= 0.60.
2. **M8.1:** same LP on actual vs model prices, 100 MW / 4 h / RTE 85%, $/kW-yr. Target good <= 20% rel, acceptable <= 35%
   (benchmarks section 3). Report for each duration, not only 4 h (extension; add to benchmarks only via DECISIONS).
3. **Price-duration curve (M1.4) and tails:** share of hours >$100 and <= $0, p95/p99 - storage revenue is tail-sensitive.
4. **Price-setter report vs IMM marginal fuel shares (M5).**
5. **Capacity module:** M7.1 on 2024/25 and 2025/26 (uncapped years) and the uncollared simulation 2028/29 [A2: S1a].
6. **Public study comparison (directional, M8.2):**
   - PJM/IMM net revenue tables in State of the Market (2024, 2025 editions) [A3] **(verify whether a battery row exists)**;
   - Sioshansi et al. 2009, Byrne & Silva-Monroy 2012 [A5] **(verify)**;
   - NREL Storage Futures Study and LBNL/ NREL storage value work [A6] **(verify titles and PJM numbers)**;
   - Commercial benchmarks (Modo) only as a cross-check [A4] **(verify)**.
   Result must be inside the published/IMM range or within 25% of its edge (M8.2 acceptable); if outside, explain by year,
   fuel price and foresight, not tune.
7. **Foresight-haircut table:** perfect-foresight vs lagged-forecast dispatch on actual 2023/2024 prices.
8. **Sign/zero-profit checks:** revenue table reconciles to objective decomposition; marginal unit earns exactly annualized cost
   in the expansion run (formulation sec 3 checks 5-6).

## 8. Disclaimers to print with the deliverable
- Model-based estimate, not a forecast or investment advice; DA-only price model, RT/DA premium excluded.
- Perfect-foresight upper bound with a stated haircut; actual operations will earn less.
- Zonal prices only; no nodal congestion or interconnection costs; basis to West Hub is zone-average.
- Capacity revenue uses PJM-published ELCC ratings and BRA/collar assumptions, which are rule- and policy-dependent and may
  change; results shown with and without the collar.
- Ancillary revenue limited to ORDC-style reserves; regulation performance payments excluded.
- Input provenance: share observed/derived/estimated/assumed is shown; items marked (verify) are not client-ready.
- Public data only; no licensed data.

## 9. Sources
- [A1] NREL, Annual Technology Baseline 2024, "Utility-Scale Battery Storage": https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage
  (fetched 2026-11-26: FOM 2.5% of capex incl. augmentation, RTE 85%, life 15 yr, 37% reduction 2022-2035 moderate, 2022$).
- [A2] Repo `docs/drafts/pjm-rpm-notes.md` (PJM BRA reports and ELCC class files; tags S1a, S3a, S5a, S8a, S19, S21 inside it).
- [A3] Monitoring Analytics, State of the Market Report for PJM: 2024 (https://www.pjm.com/-/media/DotCom/committees-groups/committees/mc/2025/20250425-special-som/2024-annual-state-of-the-market-report-for-pjm.pdf)
  and 2025 (https://www.pjm.com/-/media/DotCom/committees-groups/committees/mc/2026/20260424-special/2025-annual-state-of-the-market-report-for-pjm.pdf);
  located by search, contents not read in this pass.
- [A4] Modo Energy, PJM battery revenue benchmarks 2025-2026 (e.g. https://modoenergy.com/research/pjm-battery-revenues-benchmark-november-2025);
  located by search, not read; commercial source.
- [A5] Sioshansi, Denholm, Jenkin, Weiss (2009), Energy Economics 31(2); Byrne & Silva-Monroy (2012), SAND2012-3863
  (as cited in docs/benchmarks.md section 1; not re-checked).
- [A6] NREL Storage Futures Study (2021) and related NREL/LBNL storage value work (not retrieved).
- [A7] EIA Annual Energy Outlook gas price projections (vintage to pin; not retrieved).
- [A8] Repo `docs/benchmarks.md` (M1.5, M3, M4, M5, M7, M8 definitions) and `docs/client-questions.md` (Q1-Q14).

## 10. Owner decisions (yes/no, with recommendation)
1. Approve the headline as P50 = perfect-foresight x empirical haircut, with the unhaircut value always shown beside it? Rec: **yes**.
2. Require G7 (ORDC) and G14 (capacity) passed, and M8.1/M1.5 at least `acceptable` on the sealed 2024 hold-out, before any
   client-grade label; otherwise ship as "indicative"? Rec: **yes**.
3. Show capacity revenue with collar on and collar off in every table (not collar-off as the headline)? Rec: **yes**.
4. Keep hybrid solar+storage and regulation-performance payments out of scope for this first study? Rec: **yes**.
5. Extend M8.1 from 4 h only to 2/4/6/8 h (requires a DECISIONS entry before any result exists)? Rec: **yes**.
6. Treat 2 h storage ELCC as an assumed value (scaled from the 4 h class) until the PJM class table is checked? Rec: **yes**.
