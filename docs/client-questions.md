# Client questions the model must be able to answer

Status: **proposed — owner approves at Gate 0 review.**
Purpose: keeps feature work tied to what a PJM client pays for, and feeds the complexity value review (docs/gates/README.md: "Δ answers to the client questions it is meant to affect").
Each entry: **Asks** (who), **Outputs** (audit/report items that answer it; section refs are to docs/formulation.md), **Gate** (first gate where an answer exists; "indicative" = toy/test-system answer with stated limits, "client-grade" = backed by PJM backcast), **Confidence** (benchmark metrics in docs/benchmarks.md that give the reader reason to trust it).
Gate numbers follow PLAN.md. Answers before Gate 12 carry no PJM accuracy claim.

## Storage value (first use case)

**Q1. What would a 100 MW / 4 h battery in zone X earn per kW-year from energy arbitrage, reserves and capacity, and does that cover its annualized cost?**
- Asks: storage developer, investor, lender's engineer.
- Outputs: revenue/rent table (§8.5), storage rents $R^P,R^E$ and zero-profit flags (§3 checks 5–6), storage SOC and water values (§8.6), annualized cost table (§5.2). Split by stream: energy (G5), reserves (G7), capacity (G14).
- Gate: arbitrage indicative G5; all three streams client-grade G15.
- Confidence: M8.1 (price-shape error through the storage lens), M1.5/M4 (daily spreads), M7.1 (capacity price), M8.2.

**Q2. How much storage, at what duration (2/4/6/8 h), is economic in PJM by 2030/2035 before arbitrage spreads erode?**
- Asks: storage developer, utility planner, investor.
- Outputs: capacity expansion result `xP`, `xE` by zone and duration; marginal storage rent vs cost (T2b-style excess rent); spread compression curve from scenario sweep; build-limit duals (§7.7).
- Gate: indicative G5; client-grade G15 (single-year) and G18 (multi-year).
- Confidence: M1.5, M3.1, M8.1; ablation of inter-period SOC (G5 ledger) for long durations.

**Q3. How sensitive is storage revenue to gas prices, solar and wind build-out, and coal/gas retirements?**
- Asks: investor, storage developer, IPP.
- Outputs: scenario manager results; price-setter shares (§4) showing which fuel sets charge vs discharge hours; spread statistics by scenario.
- Gate: G5 (indicative); G10 policy/build realism; G15 client-grade.
- Confidence: M1.5, M5 (marginal fuel mix at the right hours), M1.1 on hold-out years with very different gas prices (2022 vs 2024).

**Q4. What does storage earn from the capacity market, given ELCC accreditation, and what happens to RPM prices as storage and other resources are added?**
- Asks: storage developer, IPP, utility.
- Outputs: capacity price (VRR dual), ELCC-accredited MW by resource, capacity rent in revenue table.
- Gate: G14 (needs RPM and ELCC); client-grade G15.
- Confidence: M7.1, M7.2; known risk: ELCC values are PJM-published inputs, not model-derived.

**Q5. How much of storage value comes from scarcity events, and what if shortage pricing is not repeated?**
- Asks: investor, lender, storage developer.
- Outputs: revenue contribution by hour class (ORDC hours, forced extreme-event periods such as Winter Storm Elliott), reserve prices (§7.3), revenue with and without forced periods.
- Gate: G7 (ORDC), G12 (extreme periods); client-grade G15.
- Confidence: M1.4 tails (p95, p99, hours above $100), M1.5, M8.1.

**Q6. Does location matter: zone versus hub, and congestion on the interfaces?**
- Asks: storage developer, IPP, transmission-owning utility.
- Outputs: zonal prices, congestion rents $\mu$ (§3), price-islands and binding links in the price-setter report; basis to West Hub.
- Gate: G8 indicative; G18 client-grade (zonal). Nodal prices are out of scope; say so in every deliverable.
- Confidence: M1.6, M1.1 by zone, comparison of modeled congestion rent with IMM congestion totals (verify table).

## Generation, planning and risk

**Q7. Will my existing unit (coal/gas/nuclear) cover its going-forward costs, and when does it retire?**
- Asks: IPP, investor, utility.
- Outputs: unit/cluster rent vs going-forward cost (§7.7), capacity factor, marginal fuel share.
- Gate: G10 (retirement logic) but only trustworthy after G14 (capacity revenue); `retire.economic` stays off until then (§7.7 ⚠).
- Confidence: M6.1, M6.2, M7.1.

**Q8. What is the entry economics of a new CC, CT, solar, wind, or hybrid plant (net revenue vs annualized cost, capture price, curtailment)?**
- Asks: developer, investor, lender.
- Outputs: rent vs $C^{fix}$ (§3 check 5), capture price (generation-weighted price), curtailment by zone (§8.8), PTC/ITC treatment (§7.6).
- Gate: G10 (policy), G14 (capacity revenue); client-grade G15 pattern reused.
- Confidence: M6.2 (CF), M1.1 (shape), M1.2 (bias), M7.2.

**Q9. How do my forward price views for PJM West Hub (next 1–5 years) compare with the market's futures?**
- Asks: investor, IPP trading/origination, utility hedging.
- Outputs: forward-mode West Hub on/off-peak block prices by month, gap table vs futures, scenario fan.
- Gate: G17.
- Confidence: benchmarks §7 (futures vs realized baseline), M1.1/M1.2 on hold-out.

**Q10. What would a least-cost portfolio look like under state RPS/CES and RGGI rules, and how do prices and emissions change?**
- Asks: utility planner (IRP), state-policy consultants, developer.
- Outputs: capacity/energy mix, REC and CO2 duals (§7.6), emissions, price changes.
- Gate: G10 indicative; G18 client-grade.
- Confidence: M6.1 (mix), M1.1 with RGGI adders in backcast years, M5.

**Q11. How do data-center and electrification load growth change energy prices, capacity prices and build needs?**
- Asks: utility, IPP, investor, regulator staff.
- Outputs: load scenarios, capacity/price deltas, binding build limits (queue realism, §7.7).
- Gate: G18 (multi-year zonal).
- Confidence: M7.1 (capacity), M1.1, M6.1; build-limit data quality flagged in assumptions book.

**Q12. How bad is a Winter Storm Elliott-type event for prices, fuel supply, and my asset, and how often does it matter?**
- Asks: IPP, utility risk, storage developer, lender.
- Outputs: forced-period results, scarcity pricing, unserved energy, event-period revenue by resource.
- Gate: G12 (forced periods on one zone), G7 first for pricing mechanics; client-grade G13.
- Confidence: M1.4 tails, M2 on the event days, M1.5; limitation: gas-supply outages need explicit outage inputs, not price signals.

**Q13. If interconnection queue delays limit new build, what happens to prices and reliability?**
- Asks: utility planner, developer, regulator staff.
- Outputs: `build_lim` duals (value of one more MW of headroom), unserved energy, price deltas.
- Gate: G10.
- Confidence: M6.1 and M7.1 under limits matching actual 2022–24 additions (hold-out check of build realism).

**Q14. How reliable is this answer: which inputs are observed, which estimated, and what drives the price in each hour?**
- Asks: every client, and the client-panel reviewer.
- Outputs: assumptions book (provenance mix by parameter, §8.11), price-setter report and share by marginal fuel (§4), health report, run fingerprint, scoreboard.
- Gate: G1 for the audit layer; G11–G16 for the PJM data content.
- Confidence: M5; scoreboard history across versions (G20).
