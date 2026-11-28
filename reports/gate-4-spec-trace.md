# Gate 4 code-vs-spec trace: F-0.4 (S1–S4), dual/sign conventions, block contract A1–A10

Item G4-7 (formulation lead, 2026-11-28). Spec: `docs/formulation.md` F-0.4 (§2.4, §3 audit profile, §6.1, §7.4a.1–.12),
DECISIONS 51–59, `docs/gates/gate-4.md`, `docs/drafts/architecture-spec.md` §A, `reports/gate-4-evidence.md` (incl. §14).
Code at `gate-4` head `dc7cf6e` (no `src/capex/` change in this item). Checks I ran (scratchpad, not committed):
R4-NX and R4-N window runs (`make_window_case` + `run_case`); the same with a monkeypatched `_members` (the F4-1 rule);
R4-NS with that patch; `cases/pjm5bus` angle and PTDF form on `main` (`f3acf4d`, F-0.3 code) vs `gate-4`, outputs diffed;
`pytest` on pjm5/G4/G3-fix files with the patch; the full suite once at the end (§6).

**Bottom line.** The LP (S1), the μ sign, the DC-link duals, the rent identity per component, the S2 storage rows, the
audit profile (S3) and the unscaling rule (S4) all match the spec. 1 blocker (F4-1): the R4-NX `loop_alpha` fail comes
from a spec error that the code implements faithfully. The spec is fixed here by F-0.4 amendment 1 (DECISIONS 60), and
a 10-line code change follows. The 8 G4-3 SPEC-GAPs are all ruled (§3), 7 of them by spec text alone. 3 should-fix items
are test or evidence completeness (F4-2, F4-4) and run-book provenance (F4-3). Nothing in the code contributes to C1/G1 (§5).

## 1. Trace table (Gate 4 additions)
| Spec clause | Code | Result | Note |
|---|---|---|---|
| §7.4a.9 F-0.4 version gate on `link_type`, `tx.dc_links`, `audit_profile` | data.py:182-189, 213-219, 562-569 | MATCH | each names the input |
| §7.4a.12 A1 `tx.dc_links` ∈ {controllable, exclude}, absent = controllable, sub-switch of dcpf | data.py:57-58, 213-217 | MATCH | under `transport` a load error |
| §7.4a.12 A2 `link_type` blank/absent = ac; dc row blank x/base; rating 0 = error | data.py:543-560 | MATCH | rules hold in both network models |
| §7.4a.12 `exclude` drops dc rows after validation; ids in `run.json` | data.py:572-578, 620; run.py:73 | MATCH | `provenance_cells` is never loaded, so there is nothing to drop (see F4-3) |
| §7.4a.12 under `transport` a dc row is a plain link | data.py:592 (`is_dc = dc & dcpf`) | MATCH | |
| §7.4a.2/.12 islands from AC lines only; rent components over all links | audit/network.py:87-93 | MATCH | builder: model.py:95-96 |
| §7.4a.12 A4 angle: `bal` pair, no `kvl` row for DC | model.py:155-159, 174-186, 191-202 | MATCH | |
| §7.4a.12 A4 PTDF: `bal_sys` ±f_k, `ptdf_flow` −(H_e−H_o) f_k (H1) | model.py:205-234 | MATCH | DC inside one island: ±1 on the same `bal_sys` entry, explicit zero removed (model.py:170) |
| §7.4a.12 A6 μ_k = −s_f/w = π_e − π_o, μf ≥ 0 | audit/duals.py (μ as §7.4a.5) | MATCH | H1a/H1c pass vs the independent route |
| §7.4a.5 decomposition excludes μ_k | audit/network.py:92 (b = 0 for DC ⇒ H row 0), 217-218 | MATCH | |
| §7.4a.6 `kvl.recompute` skips DC; `ptdf.recompute` adds DC flows | audit/network.py:148-150, 123-129, 214 | MATCH | |
| §7.4a.6 `congestion_rent` per rent component, inj excludes DC | audit/network.py:163-172 | MATCH | |
| §7.4a.6 `dcpf.line_duals` incl. DC, asymmetric ratings | audit/network.py:153-160 | MATCH | |
| §7.4a.6 `link_inconsistent` on DC links only (detail text) | audit/pricesetter.py:77-88; loopsetter.py:252-254; report.py:94-99 | MATCH | F-0.3 bytes kept with no DC link |
| §7.4a.12 A8 price components (islands + free DC, tol_q line rule) | loopsetter.py:36-55 | MATCH | |
| §7.4a.12 congested iff an AC line of C^π is priced | loopsetter.py:58-63, 239-242 | MATCH | |
| §7.4a.12 Φ̂ = marginal-bus rows + free-DC rows (RHS 0); one λ per island | loopsetter.py:125-133; loop.py:27-31 | MATCH | |
| §7.4a.12 `binding_links` = K + DC at limit, priced, end in C^π | loopsetter.py:222-227, 251 | MATCH | |
| §7.4a.7 𝓜_i: local-class setters that pass their price check, no BLACKOUT | loopsetter.py:66-76 | MATCH spec / **SPEC ERROR** | `TIE_AT_BOUND` at tol_π enters Φz = c (F4-1, amended) |
| §7.4a.7 case (a)/(b)/(c) by SVD rank, 1e-9 σ_max | loop.py:34-45 | MATCH | |
| §7.4a.7 interval rows: resources at a bound, unserved, blackout ≥ VOLL | loopsetter.py:79-92 | MATCH | exact rows (gap 1, amended) |
| §7.4a.7 S2 storage rows (idle two-sided, dis/ch at limit, ±tol_π, not in 𝓜_i, P > tol_q) | loopsetter.py:95-117 | MATCH | v from `eco.v` (solved `st_soc` duals) |
| §7.4a.7 solved-point pre-check at tol_π | loop.py:61-66, 85-86; loopsetter.py:140 | MATCH | λ = π at each island's reference bus |
| §7.4a.7 status map OPTIMAL / UNBOUNDED(_OR_INFEASIBLE) → ±∞ / else NaN | loop.py:69-76 | MATCH (string-keyed) | in audit code, not in the adapter (F4-5) |
| §7.4a.7 failed side → empty cell, never NaN | pricesetter.py:300-304 | MATCH | |
| §7.4a.7 failed side → "keeps class CONGESTION_LOOP + flag UNEXPLAINED" | pricesetter.py:221-223, 291 | DEVIATION → amended | code writes `primary_class` UNEXPLAINED (§4 Step 2), which is right (F4-6) |
| §7.4a.6 `loop_interval` value and detail | loopsetter.py:212-219, 255-256; report.py:104-105 | MATCH / count unit amended | a point violation counts 2 per bus (F4-7) |
| §7.4a.6 `loop_alpha` | loopsetter.py:201-209; report.py:102-103 | MATCH | fails on R4-NX (F4-1) |
| §3 S3 `audit_profile` exact/standard; MW keys a DataError under standard | data.py:182-189, 221-232; report.py:64-73, 152-163, 113-116 | MATCH | detail `audit_profile=standard warn>0.001 fail>0.1` |
| §3 S3 fingerprint: profile only when present | data.py:651 (`config = manifest`); fingerprint.py:76 | MATCH | |
| §6.1 S4 x = x̃/k_j, s = s̃ k_j/(k_C s_obj), y = ỹ k_i/(k_C s_obj); θ, `ref_angle` k = 1 | audit/solved.py:24-56; model.py:99-113 | MATCH | U1 passes |
| §6.1 `duals_raw` label `theta` rows only where nonzero | audit/duals.py:59-81 | MATCH | DECISIONS 58; pjm5 `duals_raw.csv` byte-identical to main |
| §1.2 window weight rule (DECISIONS 58) | data.py (weight check) | MATCH | not re-traced beyond B1 |
| §2.4 heat rate secant / full-load average if F_N ≤ F_0; no no-load | scripts/convert_rts_gmlc.py:57-73, 337-346 | MATCH (data layer) | test is `Fuel == Nuclear or secant ≤ 0` (F4-9) |
| §7.4a.10 M13–M16 hooks | tests/test_gate4_mutations.py | MATCH after naming | hooks named in amendment 1 (gap 8) |

Dual and sign conventions: unchanged from F-0.3 and verified again. `bal` dual/w = π, `flow` bound duals give signed μ with
μf ≥ 0 (DC links included), `kvl` and `ref_angle` follow the §7.4a.5 table, and `strong_duality`, `comp_slack` and `dual_sign`
pass on every run in this item (largest R4-NX values: 6.8e-16, 1.0e-17, 1.7e-15).

## 2. Findings
**F4-1 blocker (spec error; amended, code fix pending).** R4-NX `price_setter.loop_alpha` fails at 2.4e-3 against 1e-6.
- Spec: §7.4a.7 (F-0.3 amendment 2) put every class setter that "passes its class price check" into 𝓜_i with c_m = class
  cost, `TIE_AT_BOUND` included. That check uses the §4 band tol_π = max(0.01, 1e-5|π|).
- Code: loopsetter.py:66-76 implements it as written.
- Evidence (reproduced, `tx.dc_links: exclude`, p063 t66–67, island congested on `ac_a11`): 𝓜 = {107_cc_1 (MARGINAL_UNIT,
  26.842549), 118_cc_1 (MARGINAL_UNIT, 27.597968), 321_cc_1 (TIE_AT_BOUND at **0 MW**, mc 27.529292 vs π_b321 = 27.525732)}.
  That is three rows for two unknowns (λ, μ_a11), case (b), and the system is inconsistent by 3.6e-3. The min-norm weights
  give Σαc − π = 2.4e-3 at b108 (70 bus-hours per hour exceed 1e-6). 321_cc_1 is off because it is 3.6 mills uneconomic: its
  reduced cost is nonzero, so it is not marginal. Of 4,098 TIE_AT_BOUND bus-hours in the run, 4,096 are exact (≤ 1e-9).
  These 2 are the only ones that are not. R4-N passes only because its vertex has no such member.
- Gate impact: gate-4.md §6 says "all checks, all runs in §2: no fail", and R4-NX is a §2 run.
- Fix (spec, done): amendment 1(a). A `TIE_AT_BOUND` unit joins 𝓜_i only if |π_m − c_m| ≤ ε_tie = 1e-7 $/MWh. Otherwise it
  keeps its bus-local label and is only a bound row in case (c).
- Scratch proof with `_members` patched to this rule: R4-NX passes 31/31 (loop_alpha 9.6e-12). R4-N (2.0e-11) and R4-NS
  (2.3e-12) are unchanged and pass. pjm5, G4 and G3-fix tests: 217 pass, 1 xfail.
- Owner of fix: builder (code) and verifier (tests).

**F4-2 should-fix (verifier).** No `pjm5` Gate-3 golden exists, so "pjm5 P5a–P5f golden identity" (gate-4.md §6 row 5) has
no stored reference.
- Spec: §7.4a.9 and §7.4a.13 row 6.
- Code and tests: `tests/golden/` has only `gate2/`.
- Evidence: I ran `cases/pjm5bus` in angle and PTDF form with `main` `f3acf4d` (F-0.3 code) and with `gate-4`. Under the §7.4a.9
  rule every canonical output is byte-identical: the only differences are the `run_id`/`fingerprint` lines of `assumptions.md`,
  the one new `price_setter.loop_interval` row in `health.csv`/`health_report.md`, and `run.json` (non-canonical). So A10
  holds today, but nothing stops a regression.
- Fix: store the golden and add the test.

**F4-3 should-fix, pre-existing (carry: code at Gate 5 start).** The run's assumptions book has no cell-level provenance.
- Spec: data-schema.md:39-45 says the loader resolves `provenance_cells.csv` into `resolved_provenance`. data-sources.md:99-115
  defines the book format (provenance mix by parameter family, overrides list).
- Code: no module reads `provenance_cells.csv`, and `audit/assumptions.py` prints a mix by table.
- Evidence: in the R4-N book, `resources observed high 153` hides the derived heat-rate cells (A5) and the assumed
  `base_mva` (A11). The book also lacks the aligned-fleet and heat-rate lines that gate-4.md §9 asks to excerpt (only
  "tx.dc_links: controllable (dc_113_316; lossless, source resistance ignored)" is there). Gate 4 excerpts therefore come
  from `cases/rts_gmlc_nodal_px/assumptions.csv`: A5 (secant HR, nuclear full-load average, no no-load), A12 (CSP and
  storage removed, PLEXOS has no columns for them), A15 (DC1 lossless controllable, R ignored), A4 (±100 MW back-test).
- Fixing it changes `assumptions.md`, which is canonical, so the T1–T4/pjm5 goldens would break. Do it at a gate boundary,
  with a golden refresh.

**F4-4 should-fix (verifier).** The performance ledger cannot show the README rule "T1–T4/pjm5 size identical to Gate 3,
time ≤ 2×".
- Spec: gate-4.md §8 ("first rows: T1–T4, pjm5 (Gate 3 reference = gate-3-evidence §8)").
- Evidence: `reports/performance-ledger.md` has no T1–T4 rows and no pjm5 transport or PTDF rows. The `pjm5-dcpf` row has
  "previous gate s" empty, although gate-3-evidence §8 gives 11.5 ms (angle), 3.2 ms (transport) and 4.4 ms (PTDF). The size
  matches (1,224 × 1,517, nnz 3,672), and 10.3 ms / 11.5 ms gives a ratio of 0.90.
- Fix: add the missing rows with previous_s. T1–T4 have no Gate-3 timing, so show size identity against the golden LP
  shapes and record previous_s as "n/a (not measured at Gate 3)".

**F4-5 carry (builder, later gate).** The interval status map keys on HiGHS display strings, and the scipy adapter raises.
- loop.py:72-74 compares `modelStatusToString` text ("Primal infeasible or unbounded"). §7.4a.7 says the adapter maps status
  to an enum.
- `ScipyHighsSolver.solve` raises `SolverError` on any non-optimal status (solver.py:105-106). With `solver: scipy`, an
  unbounded interval side therefore raises instead of giving ±∞.
- On HiGHS the failure is loud: an unknown string → NaN → counted. So this is not a Gate 4 defect.
- Fix: a `Solution.status` enum set by each adapter, and a scipy adapter that returns its status.

**F4-6 narrative (closed by amendment 1c).** A failed side writes `primary_class` = UNEXPLAINED. That follows §4 Step 2;
the F-0.4 wording "keeps class CONGESTION_LOOP" was the error. `price_setter.unexplained` and `loop_interval` both fail.

**F4-7 narrative (closed by amendment 1c).** A violated solved point counts 2 per bus of the component-hour, where the spec
said "one failed solve". Only pass vs fail is judged, so the count unit is now defined to match the code.

**F4-8 narrative (for the A-contract adoption, P11).** `tx.dc_links` deviates from draft A2/A3 by design. DC rows live in
`links.csv`, so they are read and hashed under `exclude`. DC columns sit inside the `flow` block, so `exclude` shifts later
column offsets. Canonical outputs are keyed by ids, so nothing observable changes. Record these as accepted deviations
when §A is adopted.

**F4-9 narrative (data lead).** The converter picks the full-load average heat rate when `Fuel == Nuclear or secant ≤ 0`,
while §2.4 uses F_N ≤ F_0. The two are equivalent on RTS, where all nuclear `HR_incr` = 0. Harmonise the next time the
converter changes.

**F4-10 carry (owner, G4-8).** S2b stays a strict xfail. Nothing in the code blocks case (c). It is unreachable for a
structural reason (§7.4a.13 row 3): in a basic optimum, prices are pinned by basic columns, and with a fixed fleet those
columns are all in 𝓜_i. A constructive fixture exists: a congested pjm5 with one candidate at an interior build that sits
at its cap with rent > 0, plus storage at a bound in that hour. A hook-level test is the cheaper alternative.

## 3. Rulings on the 8 G4-3 SPEC-GAPs (text in formulation §7.4a.13; DECISIONS 60(e))
| # | Gap | Ruling | Spec change | Test change |
|---|---|---|---|---|
| 1 | only S2 rows relaxed | verifier reading is the spec: bound rows exact, S2 rows ± tol_π | §7.4a.7 sentence | none |
| 2 | U1 θ label | label `theta`, nonzero rows only (already §6.1 / DECISIONS 58) | row in §7.4a.13 | none |
| 3 | S2b unreachable | structural, not vertex luck; constructive fixture or hook-level test; owner picks | §7.4a.13 row 3 | owner G4-8 |
| 4 | H1b no binding AC | H1b = ±500 MW one-price case plus a free DC inside the congested island | §7.4a.13 | none (test already does both) |
| 5 | H1c free variant | rating ≥ 510 MW, `ab` unlimited is the reading | §7.4a.13 | none |
| 6 | H1d no Gate-3 golden | golden from `main` at the Gate-3 merge, `tests/golden/gate3/pjm5bus/` | §7.4a.13 | F4-2 |
| 7 | A1 injection | adapter-output shift (M10 hook), scaling off | §7.4a.13 | none |
| 8 | M13/M16 hook names | `loopsetter._storage_bounds`, `loop.side_value` (or `loop.interval` wrap) | §7.4a.10 | none |

## 4. Block contract A1–A10 (draft §A as checklist; DECISIONS 56 did not adopt it)
| # | `tx.dc_links` (S1) | `audit_profile` (S3) | S2 storage interval rows | S4 scaling |
|---|---|---|---|---|
| A1 switch | PASS with an owner deviation: in `SWITCH_KEYS` (data.py:57); default `controllable` (DECISIONS 55(3)); sub-switch error under transport (data.py:216) | PASS as a top-level key, not a switch (audit-only, no LP block); absent = `exact` | n/a (audit-only, always on under dcpf) | n/a |
| A2 inputs | PASS: `link_type` in data-schema §3.2 rule 11; provenance on rows; exclude reads and hashes dc rows (F4-8) | PASS: data-schema l.64 | n/a (reads solved v) | n/a |
| A3 variables | PASS: none new; DC columns are in `flow`, offsets shift under exclude (F4-8) | n/a | n/a | PASS: θ k = 1 (model.py:99-104) |
| A4 rows | PASS: no rows; H1 only (`bal`/`bal_sys`, `ptdf_flow`) | n/a | PASS: interval-LP rows only (loopsetter.py:95-117) | PASS: `ref_angle` k = 1 (model.py:107-113) |
| A5 objective | PASS: zero cost, lossless | n/a | n/a | PASS: decomposition check 1.4e-16 (R4-NX) |
| A6 duals | PASS: μ_k = π_e − π_o (H1a, H1c) | n/a | PASS: rows from §3 stationarity at solved v | PASS: U1; pjm5 `duals_raw` identical |
| A7 health | PASS: `ptdf.recompute`, `kvl.recompute`, rent per component, `line_duals`, `link_inconsistent` (DC) | PASS: thresholds of 4 checks (A1 test) | PASS: `loop_interval` | PASS: strong duality, CS, sign |
| A8 price-setter | PASS: no new class; price components; free-DC rows. Caveat F4-1 (generic loop code, also without DC) | "no class; unchanged" | PASS: rows tighten case (c) only; UNEXPLAINED 0 on all runs | n/a |
| A9 outputs, mutation | PASS: no new table (`flows`); M14, M15 caught | n/a (A1 known answer, no mutation id) | PASS: M13, M16 caught (forced route) | n/a (U1) |
| A10 identity | PASS: H1d (exclude = no-DC fixture); pjm5 angle + PTDF identical to `main` F-0.3 (F4-2 to pin it); T1–T4 gate2 golden pass | PASS: key absent = F-0.3 bytes (same pjm5 diff) | PASS: pjm5 identical except the one new row | PASS: same diff |
| ledgers | complexity row present (R4-N vs R4-NX, Δ +360 cols, +720 nnz, Z +0.011%); performance row R4-NX 27.1 s | – | – | – |

## 5. C1/G1 and S2b: does the code contribute?
- **C1/G1: no code contribution found.**
  - The G4-3 independent scipy LP, built from the case CSVs with no capex code, predicted C1 7.1%. capex gives 7.10% and 7.14%.
  - F0 and C0 pass, so the PLEXOS dispatch is feasible in our LP, and our optimum is no more expensive.
  - B1 passes, and R4-Z and R4-C reach the same optimum.
  - F4-1 is audit-only and changes no dispatch.
  - The residual is the LP relaxation of UC and reserves (U0: 38.8% of PLEXOS gas-CC energy is at Pmin above price).
  - The one modelling choice that also moves the coal/CC split is DECISIONS 57: secant heat rate, no no-load term. It is a
    spec choice, not a bug. If the owner wants it sized at G4-8, a cheap check is to rerun R4-C with
    `x_hr_full_load_avg_mmbtu_mwh` in place of the secant (kept in `resources.csv` for this purpose).
- **S2b:** nothing in the code (F4-10).

## 6. Test run
`pytest -q -x --no-header -p no:cacheprovider` stops at the first known red: 216 passed, 1 failed
(`test_c1_like_for_like_cost_gap_within_5pct[R4-Z]`). The same command without `-x` gives **800 passed, 6 failed,
5 skipped, 1 xfailed** in 122 s. The 6 failures are exactly the known C1/G1 ids, `[R4-Z, R4-C, R4-N]` × {C1, G1}. The xfail
is S2b. R4-NX is not part of the suite: no test runs it, so F4-1 needs one (fix item 1b).

## 7. Fix items (for PLAN.md)
1. **G4-7-fix1 builder [Sonnet]** (F4-1): in `capex/audit/loopsetter.py::_members`, drop `TIE_AT_BOUND` setters with
   |π(bus) − mc| > `loop.TIE_EPS` = 1e-7 (formulation §7.4a.7 amendment 1); no other change. Re-run R4-N, R4-NX and R4-NS
   health; the pjm5 golden identity must stay.
   **G4-7-fix1b verifier [Sonnet]**: a test from the spec, a pjm5 dcpf fixture with one unit at a bound whose mc is set
   0.005 above its congested-hour bus price (inside tol_π, not a tie). Expect: `loop_alpha` pass and the unit not in
   `setter_ids` of CONGESTION_LOOP rows. Also an R4-NX health test (window, `CAPEX_GATE4_FULL`-gated like N1).
2. **G4-7-fix2 verifier [Sonnet]** (F4-2): generate `tests/golden/gate3/pjm5bus/{angle,ptdf}/` + `SOURCE.txt` from `main`
   `f3acf4d`; test the §7.4a.9 rule (mask the two header lines, drop the `price_setter.loop_interval` row).
3. **G4-7-fix3 verifier [Sonnet]** (F4-4): add ledger rows T1–T4 and pjm5 transport/angle/PTDF with previous-gate values from
   gate-3-evidence §8 (T1–T4: size identity, previous "n/a").
4. **Gate 5 W-spec item, formulation lead [Opus] + builder [Sonnet]** (F4-3): load `provenance_cells.csv`, build the
   data-sources.md book sections 2 and 7. This changes the canonical `assumptions.md`, so the golden refresh goes at the
   Gate 5 start.
5. **Later, builder [Sonnet]** (F4-5): solver-status enum in `Solution`; scipy adapter returns its status instead of raising.
6. **G4-8 owner decision** (F4-10): close S2b by the constructive candidate fixture or the hook-level test, or accept the
   strict xfail.
