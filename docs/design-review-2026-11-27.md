# Design review — is the plan crisp, lightweight and best-practice? (2026-11-27)

Owner asked (live): will the plan give a crisp, lightweight optimization design, in line with industry and academic
practice, that solves capacity expansion, price formation and dispatch efficiently as the model grows into the basis of
a consulting practice? Reviewer: main session (Opus), reading PLAN.md, formulation.md F-0.2, gate-3/gate-5 drafts,
multi-year draft, benchmarks.md, src/capex layout. Outcome: DECISIONS 44, **amended by DECISIONS 45 (owner reply): gaps 1–2 withdrawn — no operations mode; prices and
the PDC check come from the weighted representative periods. Items below marked (withdrawn) do not apply.**

## What is already right (keep)
- One LP, own code, HiGHS, solver-agnostic; sparse block builder with labelled rows (`model.py` Block) — the GenX/PyPSA pattern.
- 3-day representative periods with weights, forced extremes, Kotzur inter-period SOC (Gate 5) — current academic practice.
- Clustered linear UC (Palmintier & Webster), ORDC, transport + DC-PF option, ATB-style annualization — standard choices.
- Audit layer (duals, price-setter, conditioning, fingerprint) and ablation/complexity ledger — stronger than most tools.
- Test ladder (toys → 5-bus → RTS-GMLC → GenX → PJM) and multi-year before the expensive features (Gates 7–8).

## Gaps (each fixed below without new gates)
1. (withdrawn, DECISIONS 45) **No first-class dispatch model.** Industry practice separates *plan* (capex, rep periods, LP) from *operate*
   (chronological fixed-fleet dispatch, full year, rolling horizon): PLEXOS LT→ST, Aurora LT→hourly, ReEDS→PLEXOS,
   GenX→PCM, RESOLVE→SERVM. The plan has dispatch only as "a one-off full-year check" (DECISIONS 3), yet benchmarks.md §2
   already needs hourly prices from it, and clients buy hourly prices, spreads and storage revenue. Capex-mode hourly duals
   are degenerate at capacity (§9 Q2) and exist only on rep periods. → Make **operations mode** a product.
2. (withdrawn, DECISIONS 45: UC stays in the expansion LP, default off unless the ledger says otherwise) **UC in the expansion LP multiplies size** (× years × periods) for little investment-decision value; its main effect is
   on hourly prices and cycling, i.e. on dispatch. → UC lives in operations mode; in plan mode it is an option, default off
   unless the ledger shows it changes builds.
3. **No resource-adequacy constraint until the VRR curve (old 14, now 16).** Every multi-year planning model (ReEDS PRM,
   GenX CapRes, RESOLVE, PLEXOS LT) has one; without it builds are driven by VOLL hours in a handful of periods, and
   §7.7 must keep economic retirement off. → Add a simple **ELCC-accredited planning reserve margin** (switch `ra.prm`)
   early; Gate 16 replaces the hard requirement with the VRR demand curve.
4. **Runtime is judged only at the end (Gate 20).** Multi-year now multiplies every later feature by N years; finding a
   scaling problem at PJM zonal is the expensive failure. → A **performance budget** in every gate from Gate 4 and a
   synthetic PJM-scale stress case at Gate 7.

## Trade-offs accepted (first three bullets withdrawn, DECISIONS 45)
- Two modes share one formulation and one builder (same blocks, same labels, same audit) — not two models. Plan mode
  = rep periods, multi-year, LP, investment duals; operations mode = one year, full chronology, fixed fleet, rolling
  windows (e.g. 7 days + 1-day look-ahead), optional UC. Consistency check: plan-mode block-average prices and unit
  revenues vs operations-mode results on the same fleet (revenue reconciliation, reported per gate from Gate 5).
- Prices for clients come from operations mode; plan-mode duals serve investment economics and the price-setter audit.
- PRM is a blunt adequacy proxy (no probabilistic LOLE); ELCC values are inputs (PJM class ELCC tables), not computed.
- Performance numbers below are **[P]** until the owner confirms.

## Changes made (PLAN.md table, DECISIONS 44, docs/gates/README.md)
| Gate | Change |
|---|---|
| 4 | RTS-GMLC dispatch → **operations mode**: full-year fixed-fleet chronological dispatch with rolling windows; source of hourly prices |
| 5 | add plan-vs-operations revenue reconciliation on RTS-GMLC |
| 7 | add ELCC-accredited PRM row (`ra.prm`, off = Gate 6 LP) and a synthetic PJM-scale stress case (size/time vs N years) |
| 11 | UC built in operations mode first; plan-mode UC optional, ledger decides default |
| 12 | economic retirement allowed with PRM on (no longer waits for RPM) |
| 16 | VRR curve replaces the PRM hard row |
| 17, 19, 20 | client hourly prices/revenues from operations mode; runtime targets checked |
| README | performance budget + `reports/performance-ledger.md` from Gate 4 |

## Performance targets (owner-confirmed 2026-11-27, DECISIONS 47; UC row dropped — linearized UC is part of the zonal model) (laptop-class, HiGHS, single thread unless noted)
- PJM single node, 1 year, ~20 periods: ≤ 2 min. PJM zonal (~20 zones, 50+ clusters), 4 model years: ≤ 30 min, with or without linearized UC.
- CI stays ≤ 10 min (Gate 2 C8). Every gate reports rows/cols/nnz/time vs the previous gate; >2× growth needs a ledger reason.
