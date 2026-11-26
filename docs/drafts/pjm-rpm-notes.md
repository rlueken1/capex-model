# PJM RPM mechanics: notes for Gate 14 (capacity market module)

**DRAFT — prep item P8, for Gate 14; not owner-approved.** Date: 2026-11-26. Author: markets reviewer.

Citation convention: `[S#]` points to the Sources list at the end (title + URL). A number with no `[S#]` and no
"(verify)" is a defect; anything marked "(verify)" is unconfirmed or secondary and must be pinned to a primary PJM
table before it is used as a benchmark. "Computed" means arithmetic done here from cited inputs. Public sources only
(DECISIONS 26). PJM only. Base dollar year 2024$.

Status of the world as of this date: BRAs for 2024/25 through 2028/29 are done. The 2029/30 BRA is scheduled for
December 2026 and has NOT been held yet [S12][S9]; its parameters are posted [S9]. Results are therefore not
benchmarks yet.

---

## 1. RPM overview

### 1.1 Products and auctions
- RPM is PJM's forward capacity market: load-serving entities buy capacity (UCAP, unforced capacity) for a delivery
  year (DY) running June 1 to May 31. The Base Residual Auction (BRA) clears one price per modeled LDA from a
  Variable Resource Requirement (VRR) demand curve and offered supply [S1][S2].
- Incremental Auctions (IAs) adjust positions after the BRA. In the current calendar PJM lists a 3rd IA for 2027/28
  (Feb 2027), a 2nd IA for 2028/29 (Jul 2027) and a 3rd IA for 2028/29 (Feb 2028) [S12] (secondary calendar, verify).
  Under the pre-2023 schedule, IAs were 20, 10 and 3 months before the DY (verify). The model does not need IAs
  (see 6.8).
- Capacity Performance (CP) is the only product: all capacity is year-round with non-performance charges (verify
  rate formula in PJM Manual 18 / OATT Att. DD).

### 1.2 Compressed schedule and return to normal
| DY | BRA held / results | Months before DY (approx.) | Source |
|---|---|---|---|
| 2024/25 | Dec 2022 (verify) | ~18 (computed from the assumed date) | not confirmed in this pass; results report [S3] (verify) |
| 2025/26 | results July 30, 2024 | ~11 (computed; the report itself says ~10) | [S4] |
| 2026/27 | results July 22, 2025 (press release date) | ~11 (computed) | [S5][S6] |
| 2027/28 | results Dec 17, 2025 (press release date) | ~18 (computed) | [S7][S8] |
| 2028/29 | window opened June 30, 2026; results July 14, 2026 | ~23 | [S13][S1a][S10] |
| 2029/30 | Dec 9-15, 2026 window; results Dec 22, 2026 (scheduled) | ~30 (computed) | [S12] (verify) |
| 2030/31 | May 2027 (scheduled) | ~37 (3-year forward) | [S12] (verify) |

- PJM states it returns to its normal BRA schedule starting with the 2030/31 BRA [S12] (secondary, verify against
  PJM's RPM auction schedule page) and describes working toward three-year-forward planning without a firm date in its
  July 2026 release [S10].
- The delay originated with FERC-approved schedule changes (dockets ER23-1609, ER25-118) [S12].

### 1.3 FRR alternative
- A load-serving entity may self-supply under the Fixed Resource Requirement (FRR) instead of RPM. FRR UCAP is
  removed from the RTO/LDA reliability requirement before the BRA [S9].
- FRR commitments (RTO): 2025/26: 10,886 MW [S6a]; 2026/27: 11,933 MW UCAP [S5a]; 2027/28: 11,299 MW UCAP [S3a];
  2028/29: 10,863.8 MW UCAP [S1a]. Dominion moved from FRR to RPM for 2025/26 [S4].

### 1.4 Locational Deliverability Areas (LDAs)
- PJM models an LDA separately if its Capacity Emergency Transfer Limit (CETL) is below 1.15 x its Capacity Emergency
  Transfer Objective (CETO) (or by other triggers) [S9]. 2029/30 models 17 LDAs: WEST (newly added), MAAC, EMAAC,
  SWMAAC, PS, PS-NORTH, PEPCO, DPL-SOUTH, ATSI, ATSI-CLEVELAND, COMED, BGE, PPL, DAYTON, DEOK, DOM, JCPL [S9].
  2025/26 had 15 LDAs (no WEST, no JCPL as a separate curve) [S4].
- Nesting: PS-NORTH within PS within EMAAC within MAAC within RTO; BGE and PEPCO within SWMAAC within MAAC; DPL-SOUTH
  within EMAAC (PJM LDA topology, verify against Manual 18 / planning parameters). ATSI-CLEVELAND within ATSI; ATSI,
  COMED, DAYTON, DEOK, DOM, PPL are zonal LDAs directly under RTO (MAAC for PPL) (verify).
- "Constrained" means the LDA clears above the RTO price (locational price adder > 0). History:
  - 2024/25: five constrained LDAs (BGE $73.00, MAAC/SWMAAC $49.49, EMAAC $54.95 vs RTO $28.92) [S4].
  - 2025/26: two constrained: BGE $466.35 and DOM $444.26 vs RTO $269.92 [S4].
  - 2026/27, 2027/28, 2028/29: none constrained; every LDA at the cap (adder $0.00) [S5a][S3a][S1a].
- CETL / CETO, 2027/28 (UCAP MW; CETL shown; CETO not published in the text read, verify): MAAC 3,013.0, EMAAC
  8,025.0, SWMAAC 7,319.0, PS 9,307.0, PS North 4,623.0, DPL South 1,974.0, PEPCO 6,776.0, ATSI 9,919.0, ATSI-Cleveland
  4,938.0, COMED 3,965.0, BGE 5,975.0, PL 6,181.0, Dayton 4,665.0, DEOK 4,938.0, DOM 6,441.0, JCPL 4,331.0 [S11].
  The report says the delayed Chanceford-Doubs upgrade materially reduced MAAC, SWMAAC and DOM CETLs [S3a][S1a].
- 2029/30: DOM and COMED have CETL/CETO ratio below 1; COMED CETL down 68% vs 2028/29, SWMAAC up 37% [S9].
- Recommendation for the model: represent as constrained only the LDAs that were constrained in a backcast year
  (BGE, DOM in 2025/26; the five in 2024/25) and, forward, those with ratio < 1.15 (COMED, DOM, MAAC, per [S9][S11]
  (verify per DY)). Everything else folds into RTO. See 6.5.

---

## 2. VRR curve and cost parameters

### 2.1 Shape (curve in force for 2028/29 onward, FERC order of Jan 21, 2026, ER26-455)
All quantities are % of the Reliability Requirement (RR); price in $/MW-day UCAP [S14].

| Point | Quantity | Price (new, 2028/29+) | Price (old, through 2027/28) |
|---|---|---|---|
| 1 (a) | 99.0% of RR | max(1.15 x Gross CONE - 0.75 x E&AS offset, 0.20 x Gross CONE), divided by reference-resource UCAP factor | max(Gross CONE, 1.75 x Net CONE) |
| 2 (b) | 101.5% of RR | 50% of Point-1 price | 0.75 x Net CONE |
| 3 (c) | 106.0% of RR | $0 | $0 at 104.5% of RR |

- Segments between points are linear; below point 1 the price is held at point 1's price (flat at the cap) [S14]
  (flat-left-of-point-1 is standard PJM design, verify in OATT Att. DD sec 5.10).
- The 0.20 x Gross CONE term is the safeguard against a near-zero curve if the E&AS offset is very high; the 0.75
  multiplier hedges E&AS overestimation [S14].
- Worked check, RTO CT, 2028/29: Gross CONE $613/MW-day, net E&AS $361/MW-day [S15] gives
  1.15 x 613 - 0.75 x 361 = $434.2 (computed); divided by the 79% reference UCAP factor = ~$550/MW-day UCAP
  (computed); this matches the $550 cap reported in the FERC order [S14]. Without the collar the uncapped
  2028/29 clearing was simulated at $554.72 RTO and $776.69 ComEd [S1a].
- Curve is built per LDA (own RR, own Net CONE) and per UCAP; the RTO curve is also used for 2024/25-era IRM-based
  curves in ICAP terms before ELCC (see 2.4).

### 2.2 Price collar (cap and floor) from the PJM-Pennsylvania settlement
| DY | Cap ($/MW-day UCAP) | Floor ($/MW-day UCAP) | Cap / floor ($/MW-day ICAP) | Source |
|---|---|---|---|---|
| 2026/27 | 329.17 | 177.24 | 256.75 / 138.25 | [S5a] |
| 2027/28 | 333.44 | 179.55 | 256.75 / 138.25 | [S3a][S11] |
| 2028/29 | 325.00 | 175.00 | 256.75 / 138.25 | [S1a] |
| 2029/30 | 337.83 | 181.91 | n/a in text read (verify) | [S9] |

- The ICAP cap and floor are constant; the UCAP values move with the reference-resource accredited UCAP factor
  (2026/27: 0.78 implied; 2027/28: 77.0% [S11]; 2028/29: 79% [S9]; 2029/30: 76% [S9]) [S9][S11]. Check: 256.75/0.77 =
  $333.4 (computed) matches [S11].
- Origin: settlement between the Pennsylvania Governor and PJM, approved by FERC for the 2026/27 and 2027/28 BRAs
  (approval Apr 2025; docket ER25-1357 as cited in [S9]; date verify) [S16]. Extension to 2028/29 and 2029/30 accepted
  by FERC Apr 28, 2026, ER26-1556 [S17]. PJM calls 2028/29 the third consecutive collared auction, collar covering
  four auctions in total [S10].
- The FERC order of Jan 21, 2026 states the collar itself is temporary and separate from the new curve [S14]. The
  user-quoted "~$325 cap / ~$175 floor" is confirmed as the 2028/29 number [S1a][S17]; the 2026/27 and 2027/28 values
  were higher in $/MW-day UCAP (above).
- Is the collar extended beyond 2029/30? Not confirmed (verify). Press says no material change expected for 2029/30
  [S18].

### 2.3 Reference resource, Gross CONE, E&AS offset, Net CONE
- Reference resource: combustion turbine (dual fuel, GE 7HA.03 class); FERC accepted keeping the CT over CC and over
  4-hour battery in the Periodic Review [S14][S15]. Net CONE amortized over 20 years for CONE Areas 1-4; Area 5 (ComEd)
  has an Illinois CEJA asset-life adjustment [S14].
- Question premise "CT vs CC change": the evidence found is that the CT stayed the reference resource (updated
  specifications), and CC was not selected [S14]. Whether an earlier CC reference existed is NOT supported by what
  was read; owner/data lead to confirm (verify).
- 2028/29 Gross CONE ($/MW-yr; ICAP basis assumed, verify): Area 1 $218,000; Area 2 $222,000; Area 3 $215,000;
  Area 4 $216,000; Area 5 $248,000 [S14]. Project development period 44 months (previously 20); 7-year straight-line
  depreciation instead of 100% year-one bonus depreciation [S14].
- 2028/29 RTO CT Gross CONE $613/MW-day and net E&AS offset $361/MW-day; VOM $2.65/MWh (IMM argued $5.30/MWh)
  [S15]. E&AS offset for multi-zonal LDAs and RTO uses the 67th percentile of zonal values [S14]. E&AS is a forward
  method using LMP data for 2023-2025 [S9].
- 2027/28 values (old parameters) by area, $/MW-day UCAP Net CONE [S11], with Gross CONE and E&AS offset in
  ICAP $/MW-yr:

| Area | Gross CONE | E&AS offset | Net CONE |
|---|---|---|---|
| RTO | 149,309 | 80,962 | 242.52 |
| MAAC | 147,295 | 58,990 | 301.50 |
| EMAAC | 142,216 | 41,088 | 358.84 |
| SWMAAC | 147,601 | 85,945 | 218.78 |
| PS / PS North | 142,216 | 27,958 | 405.43 |
| DPL South | 142,216 | 68,207 | 262.61 |
| PEPCO | 147,601 | 65,224 | 292.30 |
| ATSI / ATSI-Cleveland | 152,979 | 88,624 | 228.35 |
| COMED | 158,731 | 51,900 | 379.08 |
| BGE | 147,601 | 106,667 | 145.25 |
| PL | 145,017 | 56,131 | 315.40 |
| Dayton | 152,979 | 98,356 | 193.82 |
| DEOK | 152,979 | 91,138 | 219.44 |
| DOM | 152,979 | 102,776 | 178.14 |
| JCPL | 142,216 | 29,620 | 399.53 |

- 2028/29 and 2029/30 Net CONE by area: not stated numerically in the text read; they sit in Table 3 / the planning
  parameters workbook for each DY (verify) [S9]. 2029/30 Net CONE rose 7.0% (PL) to 16.6% (COMED) in RTO and seven
  LDAs, and fell sharply in SWMAAC, PEPCO, BGE, DOM on higher E&AS offsets [S9].
- Net CONE changes between 2024/25 and 2025/26 ranged from +4.1% (PE) to -80.6% (BGE) [S4]. Net CONE is a volatile
  input, which is why M7.2 is "report" only.

### 2.4 Requirement parameters (RTO)
| DY | IRM | FPR | Pool-wide accredited UCAP factor | Forecast peak (MW) | Reliability requirement (MW UCAP) | Source |
|---|---|---|---|---|---|---|
| 2026/27 | 19.1% | 0.9170 | 0.7699 | n/a (verify) | 146,105 | [S19][S5a] |
| 2027/28 | 20.0% | 0.9260 | 0.7717 (BRA doc), 0.772 (params doc) | 164,579 (params) vs 164,186 (as quoted in [S20]) (verify) | 152,400 | [S11][S8a][S20] |
| 2028/29 | 20.0% | 0.9401 | 0.7834 | 165,567 [S20]; 165,954 as quoted in [S9] (verify) | 156,013 | [S20][S1a] |
| 2029/30 | not in text read (verify) | not in text read (verify) | n/a (verify) | 171,916 | 158,712 (before FRR adjustment) | [S9] |

- FPR = (1 + IRM) x pool-wide accredited UCAP factor [S9]. Reliability requirement (UCAP) = forecast peak x FPR
  (computed check, 2027/28: 164,579 x 0.926 = 152,400, consistent with [S11]).
- Forecast peak figures differ across PJM documents for the same DY (e.g. 2027/28 164,579 vs 164,186; 2028/29
  165,567 vs 165,954). Data lead must pin the figure to the planning parameters workbook for that BRA, not to a later
  presentation (verify).
- Reserve margin: PJM's reserve margin is ICAP-based, (installed ICAP - peak)/peak, versus the IRM target. IRM history
  from the reports: 14.7% (2024/25, [S4]), 17.8% (2025/26, [S4]), 19.1% (2026/27, [S5a]), 20.0% (2027/28, 2028/29)
  [S3a][S1a]. The jump reflects the ELCC transition and winter-risk weighting (verify attribution).
- LDA reliability requirements exist for each modeled LDA (2027/28 table in 1.4 and [S11]).

---

## 3. ELCC accreditation

### 3.1 Concept
- PJM accredits resources by marginal ELCC class ratings, a % of ICAP. The class rating is computed from an LOLE
  simulation of the whole portfolio (hours-of-risk weighted) [S20][S21]. Accredited UCAP of a class member =
  ICAP x class rating (computed; PJM states the class rating "multiplied by ICAP" - verify exact wording in Manual 21A
  / OATT Schedule 9.2 [S21]).
- Thermal units: PJM applies a unit-specific adjustment to the class rating based on the unit's own performance in
  hours of risk relative to the class (so effective UCAP = ICAP x class ELCC x performance adjustment, bounded)
  (verify mechanism and cap in Manual 21A). Do not model it at first: use class ratings only (see 6.4).
- Storage: accredited by duration class (4/6/8/10 h) as a % of ICAP (nameplate discharge MW). No dispatch is
  needed in the capacity module; the energy-market model may use the same MW. A hybrid solar+storage and combination
  resources get resource-specific analyses [S21] (no class rating for combination, Complex Hybrid, hydro with
  non-pumped storage, Other Unlimited, and Gas CC Dual Fuel in 2028/29 [S21]).
- Ratings for later DYs are preliminary and are re-run each year with updated load forecasts; ratings are fixed for the
  BRA of that DY [S20][S21]. The 2028/29 changes came from a load forecast with less winter risk (about 2.5 pp of LOLH)
  and weather/performance data through May 2025; the ELCC methodology itself did not change in that update [S20].

### 3.2 Class ratings by BRA delivery year (% of ICAP)
| Class | 2026/27 [S19] | 2027/28 [S8a] | 2028/29 [S21] |
|---|---|---|---|
| Onshore wind | 41 | 41 | 34 |
| Offshore wind | 69 | 67 | 60 |
| Fixed-tilt solar | 8 | 7 | 7 |
| Tracking solar | 11 | 8 | 10 |
| Landfill gas (intermittent) | 50 | 48 | 50 |
| Hydro (intermittent) | 38 | 39 | 35 |
| Storage 4-h | 50 | 58 | 59 |
| Storage 6-h | 58 | 67 | 68 |
| Storage 8-h | 62 | 70 | 71 |
| Storage 10-h | 72 | 78 | 78 |
| Demand resource | 69 | 92 | 91 |
| Nuclear | 95 | 95 | 96 |
| Coal | 83 | 83 | 85 |
| Gas CC | 74 | 74 | 78 |
| Gas CT | 60 | 61 | 67 |
| Gas CT dual fuel | 78 | 77 | 79 |
| Diesel utility | 91 | 92 | 93 |
| Steam | 73 | 72 | 75 |
| Waste-to-energy steam | not listed | 83 | 84 |
| Oil-fired CT | not listed | 80 | 83 |

- 2026/27 column is from PJM's March 2025 IRM/FPR/ELCC presentation (the BRA ratings file itself could not be
  retrieved in this pass) [S19]; confirm it equals the final 2026/27 BRA ratings (verify). A 3rd-IA 2026/27 rating set
  also exists and may differ [S22] (verify).
- 2027/28 values are from PJM's July 2025 MC presentation [S8a] and the 2027/28 BRA report [S3a] corroborates only
  the DR move 69% to 92%. 2028/29 values are from PJM's 28/29 BRA ELCC class ratings file [S21].
- Several classes moved a lot: storage 4-h 50 to 59, DR 69 to 91, onshore wind 41 to 34, gas CT 60 to 67 [S19][S21].
  This is a modeling input risk: the benchmark prices embed these yearly ratings.
- ELCC ratings beyond 2028/29 exist as preliminary forecasts (e.g. through 2035) [S23] (verify before use).
- Effect on price: PJM states higher accredited UCAP factors increased offered and cleared UCAP in 2028/29 [S1a].

---

## 4. Recent BRA results (M7.1 benchmark numbers)

### 4.1 RTO headline
| DY | RTO price ($/MW-day) | Cleared UCAP, RPM (MW) | FRR (MW UCAP) | Total procured (MW UCAP) | Reliability req. (MW UCAP) | Reserve margin (RPM / total) vs IRM | Source |
|---|---|---|---|---|---|---|---|
| 2024/25 | 28.92 | 147,478.9 (incl. EE; 140,415.8 excl. EE) | n/a (verify) | n/a (verify) | n/a | 21.7% / 20.4% vs 14.7% | [S4] |
| 2025/26 | 269.92 | 135,684.0 (134,672.2 excl. EE) | 10,886 | 146,570 | n/a (not stated) | 18.6% / 18.5% vs 17.8% | [S4][S6a] |
| 2026/27 | 329.17 (cap) | 134,205.3 per Table 3; 134,310.8 per exec. summary | 11,933 | 146,243.8 | 146,105 | 18.9% RPM vs 19.1% IRM; total 139 MW above req. | [S5a][S5] |
| 2027/28 | 333.44 (cap) | 134,478.1 | 11,299 | 145,777.1 | 152,400 | 14.4% RPM / 14.9% total vs 20.0% | [S3a] |
| 2028/29 | 325.00 (cap) | 138,317.8 | 10,863.8 | 149,181.6 | 156,013 | 14.4% RPM / 14.7% total vs 20.0% | [S1a] |

- 2028/29: 6,831.3 MW UCAP short of the requirement; 2027/28: 6,516.6 MW short [S1a][S3a]. Total cost to load
  $16.4 billion (2028/29) [S10]; $14.7 billion (2025/26) vs $2.2 billion (2024/25) [S4].
- 2028/29 uncollared simulation: RTO $554.72/MW-day, COMED $776.69/MW-day, total reserve margin 14.8% [S1a]. This is
  the only published no-collar counterfactual read in this pass; one for 2027/28 and 2026/27 may exist
  (verify).

### 4.2 LDA prices
| DY | Notable LDA prices ($/MW-day) | Constrained LDAs | Source |
|---|---|---|---|
| 2024/25 | RTO 28.92; MAAC/SWMAAC 49.49; EMAAC 54.95; BGE 73.00 | five | [S4] |
| 2025/26 | RTO/MAAC/EMAAC/SWMAAC 269.92; DOM 444.26 (adder 174.34); BGE 466.35 (adder 196.43) | BGE, DOM | [S4] |
| 2026/27 | all LDAs 329.17 | none | [S5a] |
| 2027/28 | all 17 listed LDAs 333.44 | none | [S3a] |
| 2028/29 | all LDAs 325.00 (RTO, MAAC, EMAAC, SWMAAC, DOM, COMED, BGE, PPL, PEPCO, ATSI, ATSI-Cleveland, DAY, DEOK, DPL-South, PSEG, PS-North, JCPL) | none | [S1a] |
| 2029/30 | not yet held (scheduled results Dec 22, 2026) | n/a | [S12] (verify) |

### 4.3 Cleared UCAP by LDA, 2027/28 and 2028/29 (MW) [S3a][S1a]
| LDA | 2027/28 | 2028/29 |
|---|---|---|
| RTO | 134,478.1 | 138,317.8 |
| MAAC | 51,665.7 | 53,457.6 |
| EMAAC | 23,863.2 | 24,789.4 |
| SWMAAC | 6,482.6 | 6,717.0 |
| COMED | 19,549.4 | 20,919.3 |
| DOM | 19,896.1 | 21,246.4 |
| BGE | 2,216.8 | 2,289.3 |
| PPL | 8,568.2 | 8,856.9 |
| PEPCO | 2,148.9 | 2,255.5 |

2027/28 also: ATSI 7,603.6; ATSI-Cleveland 1,651.6; DAY 928.9; DEOK 2,414.5; DPL-South 959.6; PSEG 4,157.0;
PS-North 2,379.7; JCPL 2,496.6 [S3a].

### 4.4 Supply mix and demand response (context)
- 2028/29 cleared mix: 46% gas, 20% nuclear, 18% coal, 5% DR, 4% hydro, 2% wind, 2% oil, 1% solar; new generation and
  uprates 525 MW UCAP; gas +5,639 MW, coal -2,941 MW, solar +651 MW vs the prior auction [S10]. DR cleared 7,365 MW
  UCAP [S18].

### 4.5 Benchmark-comparison hazards for M7.1 (read before building the scoreboard)
1. **Collar contamination.** In 2026/27, 2027/28 and 2028/29 every LDA cleared at the cap [S5a][S3a][S1a]. The model
   price can only be compared as "at or near cap" there; a match to a number says nothing about the model's economics.
   The informative backcast years are 2024/25 and 2025/26 (price formed by the uncapped curve). For the collared
   years compare against the uncollared simulation ($554.72 RTO / $776.69 ComEd for 2028/29 [S1a]) and report the
   cleared-quantity shortfall (6.5-6.8 GW below the requirement [S1a][S3a]).
2. **Cleared UCAP has two published figures** for 2026/27 (134,205.3 table vs 134,310.8 summary [S5a]) and for 2027/28
   the 2028/29 press release quotes 134,585 MW while the BRA report says 134,478.1 [S10][S3a]. Pin to the BRA report
   Table 3/results table and record the table and page in the benchmark file (verify).
3. **Reserve margin definition** is ICAP-based in PJM reports; the model's UCAP-based accounting must convert using the
   pool-wide accredited UCAP factor, or the M7.1 reserve-margin comparison is apples to oranges.
4. **Units:** the 2024/25 and 2025/26 figures include energy efficiency (EE) in cleared UCAP; subtract EE for a clean
   comparison with the two numbers published [S4].
5. **Scale of tolerance.** M7.1 tolerance is "<= $25 or <= 20%" [benchmarks.md M7.1]; a $25 absolute test is
   meaningful only for 2024/25 ($28.92). For the capped years a 20% tolerance on $325-$334 is $65-67 (computed).

---

## 5. Prices and units (reference for the data layer)
- PJM publishes capacity prices in $/MW-day UCAP. Annualization: $/MW-yr = $/MW-day x days in the delivery year
  (computed). DY 2027/28 includes Feb 29, 2028, so 366 days; other recent DYs have 365 (computed; verify calendar).
  Simple convention: x365 for model use, document the leap-year difference (<0.3%, computed).
- Example: $325.00/MW-day x 365 = $118,625/MW-yr (computed) nominal (2028/29 $). Convert to 2024$ using the repo
  deflator per docs/data-sources.md (GDP deflator, BEA actual / AEO projection); do not hard-code a factor here.
- Auction prices are nominal dollars of the delivery year, set 3 years or fewer earlier; deflate by DY, not by auction
  date, for consistency with the model year (decision for the data lead).
- Net CONE and the cap/floor are annually re-indexed for inflation and the reference-resource UCAP factor [S9][S14];
  the cap formula in ICAP terms ($256.75/MW-ICAP-day) has been constant 2026/27-2028/29 [S5a][S3a][S1a].

---

## 6. Modeling implications for the LP (formulation sec 7.8 sketch)

### 6.1 Current sketch (formulation.md 7.8)
Piecewise VRR demand curve as stepped benefit segments; ELCC-accredited supply sum_r ELCC_r K_r; dual = capacity price
($/MW-day after conversion). The notes below support that sketch and propose boundaries; no change to the formulation
is made here.

### 6.2 VRR as a concave piecewise-linear benefit
- The VRR is a decreasing price curve, so the buyer's benefit (area under it) is concave. Represent with segments
  s = 1..S with breakpoints at 99.0%, 101.5%, 106.0% of RR (new curve [S14]); variable q_s in [0, width_s] with benefit
  slope = price on that segment. LP maximizes total benefit minus cost, so no integer variables are needed and the
  concavity is automatic.
- Left of 99% RR the price is flat at the cap p1 [S14] (verify), so add a segment from 0 to 0.99 RR at p1 (or a
  penalty/shortfall slack with price = p1 so the LP stays feasible when supply < requirement).
- Because the linear segments between points are straight lines, a stepped approximation (S = 6-10 steps per
  segment) is a minor error; or use exact slopes within one segment by a convex-combination (SOS-free for concave
  benefit). Choose steps for simplicity first.
- The dual of the accredited-supply row is the capacity price in $/MW-day UCAP; convert to $/MW-yr for the objective.
  Objective capacity benefit must use the same annualization (x365).

### 6.3 Exogenous inputs (do not endogenize in Gate 14)
- ELCC class ratings by DY (section 3.2): exogenous, per PJM [S19][S8a][S21]. Q4 already flags this as a PJM-published
  input, not model-derived [client-questions Q4].
- Reliability requirement and IRM/FPR (section 2.4): exogenous per DY; for forward years use the PJM forecast with
  an owner-set sensitivity.
- Net CONE, Gross CONE, E&AS offset, cap/floor: exogenous from PJM planning parameters [S9][S11]. The model must NOT
  recompute Net CONE from its own E&AS (circular); report the model's implied Net CONE only for M7.2.
- FRR load and cleared FRR UCAP: exogenous reduction of the requirement (6.6).

### 6.4 Accreditation inside the LP
- Accredited UCAP of resource r in DY y: ELCC_class(r),y x K_r (ICAP). Existing capacity K0_r and new x_r both
  accredit; retirement variable ret_r subtracts.
- Marginal ELCC means class ratings fall as a class is added (storage, solar, wind) - the portfolio effect PJM
  recomputes each year. In the LP, use the exogenous rating (a fixed per-class factor). If Q4's "what happens to RPM
  prices as storage is added" matters, add a second-order switch: piecewise-decreasing ELCC for the new-build class
  as a function of class MW (calibrated from PJM's published ratings across DYs, which show a 4-h storage rating
  rising from 50 to 59% as other resources changed [S19][S21]; direction depends on portfolio - do not extrapolate)
  (verify). Keep OFF in the first implementation.
- Thermal unit-specific adjustment: skip first; if needed, treat as a single class-level EFORd haircut taken from
  the data layer (estimation hierarchy in docs/data-sources.md).
- Storage: UCAP = ELCC_dur x discharge MW; duration classes 4/6/8/10-h [S21]. Round to the class nearest the unit
  duration and record in the assumptions book.

### 6.5 LDA nesting as extra constraints
- Keep RTO as the base row. Add per-LDA rows only for LDAs that are constrained in the backcast year or have
  CETL/CETO < 1.15 forward (section 1.4): LDA_a: sum over r in a of ELCC_r K_r + CETL_a >= RR_a - FRR_a - slack (price
  of slack is the LDA price adder; the LDA's own VRR curve applies).
- The LDA price = RTO price + adder, where the adder is the dual of the LDA row beyond the RTO row (equivalent to a
  nested formulation). The nesting hierarchy in 1.4 must be used (a MAAC row implies EMAAC and SWMAAC subsets feed it)
  (verify).
- Data needed per DY per LDA: reliability requirement, CETL, accredited supply by zone mapping (data lead). Example
  numbers for 2027/28 are in 1.4 and 2.3 [S11].
- Our zonal energy model resolution and the RPM LDA map differ (PS-NORTH, DPL-SOUTH, JCPL sub-zonal). Collapse to the
  model's zones with a documented mapping; mark as an approximation.

### 6.6 FRR load removal
- Subtract FRR accredited UCAP obligation from the RTO (and LDA) requirement before building the curve [S9]. Treat as a
  per-DY exogenous constant from the BRA report (10.9-11.9 GW in 2025/26-2028/29 [S6a][S5a][S3a][S1a]).
- FRR entities' capacity is NOT in RPM supply; leave it out of the supply side (data lead to split plant-level
  ownership; if not available, keep all UCAP in supply and do not remove FRR - state clearly (verify)).

### 6.7 Annual versus delivery-year mismatch
- The model's period is a calendar/representative year with weighted 3-day periods; PJM DY runs June to May. Assign
  a model year y to the DY that starts in June of y (convention, owner confirm) and use the DY's parameters and
  prices; capacity revenue (price x ELCC x K) is an annual flow, so no sub-annual allocation is needed in the LP.
- Seasonal accreditation is NOT a feature of the current ELCC classes (class ratings are annual); hours-of-risk
  weighting is in the rating, not in dispatch [S20][S21]. The DY 2027/28 leap-day effect is ignored (section 5).

### 6.8 What to omit in the first version
- Incremental auctions, bilateral trades, CP non-performance penalties (the energy model is deterministic, so
  expected penalty is a revenue haircut and part of offer-price calibration in the Gate 12 adders; verify), must-offer
  rules and exceptions (treat existing resources as offered at their going-forward cost; in the LP: offer price =
  going-forward cost plus calibration adder), and Minimum Offer Price Rule: FERC's 2021 action removed the expanded
  MOPR for most resources (verify the order and the remaining Unit-Specific/state-subsidy constraints). No MOPR
  needed unless a client study is about state-subsidized entry.
- Reliability Backstop procurement (planned from Sept 2026; FERC partially approved) is outside RPM; flag for
  forward scenarios only [S10][S18] (verify status).

### 6.9 Recommendation: simplest-first for Gate 14
1. One RTO-level row with the 2028/29-style curve (3 points, flat cap left of point 1), exogenous requirement, FRR,
   class ELCC factors, collar on/off switch (`rpm.collar`). Dual = capacity price.
2. Backcast against 2024/25 and 2025/26 (uncollared), then report-only against the 2026/27-2028/29 collared years with
   the uncollared simulation for 2028/29 [S1a]. Do not claim a pass on capped years.
3. Add constrained LDA rows (BGE, DOM for 2025/26; COMED/DOM/MAAC forward) in a second step with their own ablation
   switch. Ablate with the single-row RTO model.
4. Per-class ELCC erosion (marginal ELCC vs MW) as a later switch, only if a client question (Q4) requires it.
5. Net CONE consistency (M7.2): report model-implied cost of new entry vs PJM Net CONE; do not tune to it.
Each feature gets an ablation switch and a line in reports/complexity-ledger.md per gate rigor rules.

### 6.10 Other caveats
- With the collar, the dual of the supply row is not the market price in capped years (cap binding): the model should
  report both the "uncollared" dual and the capped price.
- The model's no-retirement stance (backcasts fix retirements) and missing capacity revenue: formulation.md sec 7.7
  already restricts economic retirement until RPM exists. Gate 14 should enable `retire.economic` only after the
  RPM module passes 2024/25 and 2025/26 backcasts.
- Data-center load growth drives the forecast (about +2 GW forecast demand for 2028/29 [S18]); the load forecast
  vintage is an input to RR; record vintage and method in the assumptions book per provenance rules.

---

## 7. Sources
- [S1] PJM, "2028/2029 Base Residual Auction Results Report" (July 14, 2026):
  https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2028-2029/2028-2029-bra-results-report.pdf
  ([S1a] = same document; table numbers as read: Table 1, 2, 3 pp. 4-8, Appendix p. 17)
- [S2] PJM, RPM information page: https://www.pjm.com/markets-and-operations/rpm (listed in docs/data-sources.md row
  pjm_rpm; not fetched in this pass)
- [S3] PJM, 2024/2025 RPM BRA results (as summarized in [S4]); [S3a] PJM, "2027/2028 BRA Report":
  https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2027-2028/2027-2028-bra-report.pdf
- [S4] PJM, "2025/2026 Base Residual Auction Report" (July 30, 2024), contains 2024/25 comparisons:
  https://pjm.com/-/media/markets-ops/rpm/rpm-auction-info/2025-2026/2025-2026-base-residual-auction-report.ashx
- [S5] PJM press release, 2026/27 BRA (July 22, 2025):
  https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/2025-releases/20250722-pjm-auction-procures-134311-mw-of-generation-resources-supply-responds-to-price-signal.pdf
  ; [S5a] PJM, "2026/2027 BRA Report": https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2026-2027/2026-2027-bra-report.pdf
- [S6] PJM Inside Lines, 2026/27 results: https://insidelines.pjm.com/pjm-auction-procures-134311-mw-of-generation-resources-supply-responds-to-price-signal/
  ; [S6a] PJM Inside Lines, 2025/26 results (FRR 10,886 MW, reserve margin 18.5%):
  https://insidelines.pjm.com/pjm-capacity-auction-procures-sufficient-resources-to-meet-rto-reliability-requirement/
- [S7] PJM press release, 2027/28 BRA (Dec 17, 2025):
  https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/2025-releases/20251217-pjm-auction-procures-134479-mw-of-generation-resources.pdf
- [S8] PJM Inside Lines, 2027/28 results: https://insidelines.pjm.com/pjm-auction-procures-134479-mw-of-generation-resources/
  ; [S8a] PJM MC presentation, "2027/2028 BRA FPR and IRM" (July 23, 2025), ELCC ratings:
  https://www.pjm.com/-/media/DotCom/committees-groups/committees/mc/2025/20250723/20250723-item-02---2027-2028-bra-fpr-and-irm---presentation.pdf
- [S9] PJM, "2029/2030 Planning Period Parameters for Base Residual Auction" (posted Aug 31, 2026):
  https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2029-2030/2029-2030-planning-period-parameters-for-base-residual-auction-report.pdf
- [S10] PJM Inside Lines, 2028/29 results (July 14, 2026):
  https://insidelines.pjm.com/pjm-capacity-auction-procures-138318-mw-of-generation-resources-as-work-continues-to-address-growing-electricity-demand/
- [S11] PJM, "2027/2028 RPM BRA Planning Parameters":
  https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2027-2028/2027-2028-planning-period-parameters-for-base-residual-auction-pdf.pdf
- [S12] ESAI Power, PJM capacity auction calendar (secondary; confirm on PJM site):
  https://www.esaipower.com/capacity-market-auction-calendar/pjm-capacity-auction-calendar/
- [S13] PJM answer in FERC ER26-455 (BRA start June 30, 2026): https://www.pjm.com/-/media/DotCom/documents/ferc/filings/2025/20260102-er26-455-000.pdf
- [S14] FERC order, PJM Periodic Review (ER26-455-000, 194 FERC P 61049, Jan 21, 2026):
  https://www.pjm.com/pjmfiles/directory/etariff/FercOrders/8578/20260121-er26-455-000 (194 FERC P 61049).pdf
- [S15] = [S13] (PJM answer; CT Gross CONE $613/MW-day, net E&AS $361/MW-day, VOM $2.65/MWh).
- [S16] FERC approval of Pennsylvania-PJM settlement (collar for 2026/27-2027/28): Utility Dive,
  https://www.utilitydive.com/news/ferc-pjm-interconnection-capacity-auction-price-cap-collar/745979/ and PJM Inside Lines
  https://insidelines.pjm.com/ferc-approves-capacity-auction-price-collar-to-next-two-capacity-auctions/ (snippet-level;
  not fetched; verify approval date)
- [S17] Troutman Pepper, "FERC Accepts PJM Capacity Market Price Collar Extension" (May 13, 2026; FERC order Apr 28,
  2026, ER26-1556): https://www.troutmanenergyreport.com/2026/05/ferc-accepts-pjm-capacity-market-price-collar-extension/
- [S18] Utility Dive, 2028/29 BRA coverage: https://www.utilitydive.com/news/pjm-capacity-auction-price-cap-reserve-shortfall/825282/
- [S19] PJM MC presentation, "IRM, FPR and ELCC for 26/27 BRA" (Mar 19, 2025):
  https://www.pjm.com/-/media/DotCom/committees-groups/committees/mc/2025/20250319/20250319-item-03---irm-fpr-and-elcc-for-26-27-bra---presentation.pdf
- [S20] PJM MRC presentation, "2028/2029 BRA FPR and IRM" (Feb 13, 2026):
  https://www.pjm.com/-/media/DotCom/committees-groups/committees/mrc/2026/20260213-special/item-01---2028-2029-bra-fpr--irm---presentation.pdf
- [S21] PJM, "2028/29 BRA ELCC Class Ratings":
  https://www.pjm.com/-/media/DotCom/planning/res-adeq/elcc/28-29-bra-elcc-class-ratings.pdf
- [S22] PJM, "2026/27 3IA ELCC Class Ratings":
  https://www.pjm.com/-/media/DotCom/planning/res-adeq/elcc/2026-27-3ia-elcc-class-ratings.pdf (not fetched)
- [S23] PJM, preliminary ELCC class ratings, 2027-2035:
  https://www.pjm.com/-/media/DotCom/planning/res-adeq/elcc/discussion-of-preliminary-elcc-class-ratings-for-period-2027-2035.pdf
  (not fetched)
- Not used but needed: PJM IMM, State of the Market reports (capacity market section) for independent confirmation,
  https://www.monitoringanalytics.com/reports/ (not fetched this pass).

## 8. Verify list
1. 2024/25 BRA: date, cleared UCAP, FRR, reliability requirement, per-LDA prices (only partially via [S4]); fetch the
   2024/25 BRA report directly. Date believed Dec 2022 (not confirmed).
2. 2026/27 ELCC ratings: confirm final BRA ratings file (fetch was blocked); the table uses the Mar 2025 presentation.
3. Which cleared-UCAP figure to pin for 2026/27 (134,205.3 vs 134,310.8) and 2027/28 (134,478.1 vs 134,585).
4. Forecast peak per DY (competing figures in 2.4).
5. FERC approval date and docket for the original Pennsylvania settlement collar (ER25-1357 as cited by [S9]).
6. Whether the collar extends past 2029/30; whether a post-2029/30 BRA schedule (2030/31 in May 2027) is final.
7. Premise "CT vs CC reference resource change": evidence read says CT retained; confirm history of reference resource.
8. 2028/29 and 2029/30 Net CONE by area, IRM/FPR for 2029/30, CETL/CETO table for 2028/29 and 2029/30, and CETO values.
9. Gross CONE basis (ICAP vs UCAP, $/MW-yr) in the FERC order table.
10. VRR flat-left-of-point-1 and exact segment interpolation (OATT Att. DD sec 5.10).
11. LDA nesting topology and which LDAs are zonal.
12. Unit-specific thermal adjustment mechanism in ELCC accreditation (Manual 21A / OATT Schedule 9.2); exact accredited UCAP formula.
13. CP non-performance charge rate; IA timing under the old schedule; expanded MOPR removal order (FERC 2021).
14. 2029/30 BRA results (due Dec 22, 2026 per [S12]); update M7.1 table once published.
15. IMM State of the Market confirmation of all clearing prices, and IMM positions on the E&AS offset and VOM.
16. Deflator choice for annualized $/MW-yr to 2024$ (repo data-sources entry), not computed here.
