# How a gate is passed

Each gate N has `docs/gates/gate-N.md` with exit criteria and numeric tolerances,
approved by the owner at the end of gate N-1's review. Criteria do not move during the work.

A gate passes only with an evidence file `reports/gate-N-evidence.md` linking to:

1. **CI test runs** (GitHub Actions, every push) — objective pass/fail with tolerances.
2. **Model-health checks** (run on every solve, reported by `capex.audit`):
   - energy balance residual ≈ 0 every zone/hour
   - duals equal expected prices (energy, reserves, capacity); complementary slackness
   - storage SOC consistent across hours and across linked periods
   - objective decomposition sums to total
   - expected constraints binding (binding-constraint report)
   - **marginal price-setter report** (see below)
3. **Scoreboard** (from Gate 5): hold-out backcast error improves or holds vs previous gate.
4. **Complexity value review** (from Gate 5, see below).
5. **Independent review**: verifier + the relevant reviewer role(s) write pass/fail against
   the gate checklist in `reports/gate-N-review.md`, ending in an explicit yes/no
   **decision list** for the owner.
6. **Owner sign-off.** Only the owner marks a gate DONE and merges to `main`.

## Marginal price-setter report (every solve)
For each zone and timestep, identify what sets the price, from duals and dispatch:
- a unit/cluster dispatched strictly between min and max whose marginal cost (incl.
  adders) equals the zonal energy dual → that unit is marginal;
- otherwise classify the price-setter as: storage opportunity cost, imported marginal
  unit + congestion (transmission limit binding), reserve/shortage pricing (ORDC),
  ramp/UC constraint, or unserved energy (VOLL).
Checks: every zone-hour has an identified price-setter (no "unexplained"); the price
equals the setter's cost within tolerance. Output: share of hours by marginal fuel/tech
per zone — benchmarked against the PJM Market Monitor's (IMM) marginal-resource-by-fuel
statistics as a scoreboard metric.

## Complexity value review (every feature, from Gate 5)
Every feature has an on/off switch so it can be ablated. For each feature report:
- Δ hold-out backcast error (scoreboard metrics)
- Δ solve time, Δ problem size (rows/cols/nonzeros), Δ memory
- Δ answers to the client questions it is meant to affect

Judgment (formulation lead + consulting reviewer; owner decides):
- **Keep** if it measurably improves accuracy for its cost, **or** a client question
  needs it even without backcast gain (e.g. VRR curve for capacity prices) — say which.
- **Keep but default off** if it helps only some questions.
- **Simplify or drop** if it adds compute with no measurable value.
Results go in `reports/complexity-ledger.md`, one row per feature, kept current.
