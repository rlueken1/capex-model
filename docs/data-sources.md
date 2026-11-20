# Data sources and assumptions (draft — data lead expands in W2 and Gate 3/11)

## Provenance rule (applies to every input value)
Every parameter in every input table carries:
- `source_id` → a row in the source registry below
- `vintage` (data year / release) and `retrieved` date
- `method`: `observed` | `derived` | `estimated` | `assumed`
- `basis`: how it was derived/estimated (formula, regression id, or citation)
- `confidence`: high / medium / low

Nothing enters the model without these fields. Every run writes an **assumptions book**
(`outputs/<run>/assumptions.md`) listing, by parameter, the share of capacity that is
observed vs estimated vs assumed, with citations — this is the client-facing audit trail.

## Estimation hierarchy for missing unit characteristics
When a PJM unit lacks a characteristic (heat rate, min gen, ramp, start cost, outage rate,
VOM, FOM), use the first level available and record which:
1. **Unit-specific observed** — e.g. heat rate from EPA CEMS heat input / gross load, or
   EIA-923 fuel consumption / net generation.
2. **Plant-level observed**, allocated to units.
3. **Statistical estimate from public data** — regression or peer-group median by
   technology, prime mover, vintage, size class, and region (fit on units that have
   observed data; fit stored with id and fit statistics).
4. **Literature / public defaults** with citation — e.g. NREL ATB, EIA AEO assumptions,
   EPA NEEDS / IPM documentation, NERC GADS summary statistics, published academic values.
Estimates are back-tested where possible (hold out units with observed values and report
error), and the levels used feed the `confidence` field.

## Source registry (to be completed)
| source_id | Source | Use | Access |
|-----------|--------|-----|--------|
| eia860 | EIA Form 860 | fleet, capacity, tech, vintage, retirements | Actions download |
| eia923 | EIA Form 923 | generation, fuel use, derived heat rates | Actions download |
| pudl | Catalyst PUDL | cleaned EIA/FERC/CEMS joins | Actions download |
| cems | EPA CEMS | hourly heat input/output, unit heat rates, starts | via PUDL |
| needs | EPA NEEDS (IPM) | unit characteristics, defaults | Actions download |
| atb | NREL ATB | new-build costs and performance | Actions download |
| aeo | EIA AEO | fuel price projections, assumptions | Actions download |
| pjm | PJM Data Miner 2 | load, LMPs, reserves, RPM results | Actions download |
| imm | Monitoring Analytics (PJM IMM) | State of the Market benchmarks, marginal fuel | manual/Actions |
| gas | Henry Hub + regional basis | fuel prices | TBD (license check) |
