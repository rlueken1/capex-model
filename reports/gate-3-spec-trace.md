# Gate 3 code-vs-spec trace: formulation §7.4a (DC power flow) and dual/sign conventions

Item G3-6 (formulation lead, 2026-11-27). Spec: `docs/formulation.md` F-0.3 (§3, §4, §7.4a, §8 incl. §8.10a), DECISIONS 44–50,
`docs/gates/gate-3.md`, `reports/gate-3-evidence.md`. Code at `gate-3` head (code = `2563d52`). Read-only review of `src/capex/` and
`tests/`. Checks I ran: `pytest tests/test_pjm5bus.py` (103 passed); `python -m capex run cases/pjm5bus` (angle, ref A) and a PTDF-form,
ref-D variant (both health `pass`); loader probes on edited copies of `pjm5`/T4; `loop.interval` on a hand-made rank-deficient Φ.
Scratch outputs are in the session scratchpad.

**Bottom line.** The LP, the μ sign, the LMP decomposition and every §7.4a.6 check match the spec. The audit route is independent of
the builder's network code. 0 blockers. 8 should-fix: 4 are settled in this item by spec amendment 2 (DECISIONS 51), and 4 need
code or tests (fix items in §3). 5 are carried to a later gate. 2 G3-5 observations are confirmed as spec-conform (no fix).

## 1. Trace table
| Spec clause | Code | Result | Note |
|---|---|---|---|
| §7.4a.1 `tx.model` values, load error | data.py:173-182 | MATCH | `tx.model: foo` gives DataError |
| §7.4a.1 `tx.dcpf_form` default angle | data.py:144-145, 176-180 | MATCH | value checked even under transport (stricter, harmless) |
| §7.4a.1 `tx.ref_bus` id/list, ≤1 per island, default first zone | network.py:39-52; data.py:510-514 | MATCH / DEVIATION | `tx.ref_bus: 3` raises TypeError, not DataError (F3-2) |
| §7.4a.1 unknown switch keys | data.py:156-182 | SPEC-GAP → amended | `tx.losses: true` and `tx.dcpf_formm` load silently (F3-2) |
| §7.4a.1 no default written to config | data.py:556 | MATCH | `switches=manifest.get(...)` |
| §7.4a.2 incidence, b = base/x (MW/rad) | network.py:25-27, 59-61 | MATCH | |
| §7.4a.2 rating F = fwd = rev, blank = ∞, 0 is an error | data.py:497-509 | MATCH | |
| §7.4a.2 islands, ids `i1..` by smallest row, isolated node | network.py:30-52 | MATCH | own island; empty reduced block skipped |
| §7.4a.2 PTDF, H=0 across islands and at n0, 1e-10 noise | network.py:55-70 | MATCH | |
| §7.4a.2 scaling: θ unscaled, kvl coeff k_P b | model.py:94-99, 183-187 | MATCH | coeff 15.6 max for pjm5 |
| §7.4a.2 duals of new rows/cols unscaled | audit/solved.py:20-44 | DEVIATION (latent) | θ reduced cost and `ref_angle` slack use the k_P factors (F3-12) |
| §7.4a.3 `theta` free, `kvl` row, `ref_angle` always a row | model.py:140-145, 177-188, 272-273, 293-295 | MATCH | size +|N| cols, +|L|+|I| rows, +3|L|+|I| nnz (evidence §8) |
| §7.4a.4 no `bal`/θ; `bal_sys`, `ptdf_flow` rows and RHS; flow bounds kept | model.py:127-128, 191-205, 277-283 | MATCH | no ranged rows |
| §7.4a.5 μ = −s_f/w, signed, μf ≥ 0 | audit/duals.py:41 | MATCH | de: f = −240, μ = −62.322 |
| §7.4a.5 `kvl` dual = π_o − π_e + μ | (raw duals) | MATCH | de: y/w = −32.38 = 29.94 − 62.32 |
| §7.4a.5 `ref_angle` dual = 0 | (raw duals) | MATCH | −0.0 in every hour |
| §7.4a.5 PTDF LMP from H^LP (coefficients of `use[n]`) | audit/duals.py:29-34 | MATCH | same expression gives `bal` under transport, so golden is unchanged |
| §7.4a.5 decomposition λ = π(n0), −Σ H^case μ; ref dependence | audit/network.py:189-194 | MATCH | ref D: λ = 39.94, A congestion = −22.97 |
| §7.4a.5 congestion-rent identity per island-hour | audit/network.py:141-144 | DEVIATION | summed over all islands per hour (F3-10) |
| §7.4a.6 `kvl.recompute` (θ from `angles`) | audit/network.py:128-129, 186-193 | MATCH | PTDF form uses recomputed θ, so it equals `ptdf.recompute` (as spec) |
| §7.4a.6 `ptdf.recompute` (linalg.solve, no PTDF) | audit/network.py:113-125 | MATCH | |
| §7.4a.6 `lmp.decomposition`, `dcpf.line_duals` | audit/network.py:132-138, 194 | MATCH | `binding_slack` 1e-6 |
| §7.4a.6 `dcpf.islands` (angle row form, θ ≤1e-9; PTDF lo=hi=ΣD) | audit/network.py:147-177 | MATCH | detail reads "1 islands: i1 ref A" (grammar nit) |
| §7.4a.6 `price_setter.loop_alpha` | audit/loopsetter.py:196-204 | MATCH | 2.8e-14 on P5a |
| §7.4a.6 tolerance keys only under dcpf | config.py:97-104; data.py:555 | MATCH | unknown key → TypeError (F3-2) |
| §7.4a.6 non-toy warn/fail for the MW checks | audit/report.py:96-99 | MISSING → amended | same gap for `balance` (F3-3) |
| §7.4a.6 Gate 1 checks under dcpf; `link_inconsistent` n/a | audit/duals.py:45-53; report.py:83-84 | MATCH | detail text exactly as spec |
| §7.4a.7 congested test, uncongested island rule | audit/loopsetter.py:96-103, 214-220 | MATCH / SPEC-GAP | line tol_π/tol_q not defined in the spec → amended to the code (F3-14) |
| §7.4a.7 class order in congested island-hours | audit/loopsetter.py:219-220 | MATCH | local(6) → LOOP → CAPACITY_RENT {n} → UNEXPLAINED |
| §7.4a.7 marginal set 𝓜_i | audit/loopsetter.py:106-115 | SPEC error → amended | the spec wrongly counted BLACKOUT as marginal; code needs the price check (F3-8, F3-14) |
| §7.4a.7 K_i, B, c_b mean, φ, Φ, SVD rank 1e-9, pinv | audit/loop.py:25-41; loopsetter.py:131-147 | MATCH | |
| §7.4a.7 cases (a)/(b)/(c), DEGENERATE | audit/loop.py:30-36; pricesetter.py:225-229 | MATCH | (b)/(c) covered by builder smoke tests only (F3-11) |
| §7.4a.7 case-(c) interval LP, bounds, ±∞ | audit/loop.py:44-65; loopsetter.py:118-128 | DEVIATION / MISSING | no storage rows; only the "Unbounded" status maps to ±∞ (F3-9, F3-13) |
| §7.4a.7 outputs: setter_ids, setter_zone, binding_links "sorted" | loopsetter.py:148; pricesetter.py:245, 254 | DEVIATION → amended | code: grouped by bus; links in csv order (F3-7) |
| §7.4a.7 flags CONGESTED/IMPORT/DEGENERATE, price_lo/hi, summary split | pricesetter.py:225-262 | MATCH | |
| §7.4a.7 P5a α example | price_setter_loop.csv | MATCH | D (1.497137, −0.497137) reproduced |
| §7.4a.8 `zone_hourly` extension, `flows`, `angles`, `islands`, `price_setter_loop` | audit/network.py:201-224; run.py:55-60, 95-99; loopsetter.py:183-193 | MATCH | `theta_source` lp/recomputed |
| §4 Outputs `island_id` format | loopsetter.py:226; pricesetter.py:256 | SPEC-GAP → amended | transport 0-based per hour; dcpf 1-based k of `ik` (F3-7) |
| §7.4a.9 transport identity; loader F-0.2/F-0.3; dcpf needs F-0.3 | data.py:165-182; tests/golden | MATCH | 21 identity tests pass |
| §8.10 fingerprint `formulation_version` | __init__.py:3; audit/fingerprint.py:77 | DEVIATION | F-0.2 for every run (F3-1) |
| §7.4a.10 builder API, audit never imports `capex.network` | network.py:25, 45, 55; tests/test_pjm5bus.py:730 | MATCH | static test passes |
| §7.4a.10 M7–M10 | tests/test_pjm5bus.py | MATCH | all caught (evidence §5) |
| §8.12 congestion rent per hour and per year | – | SPEC-GAP → amended | §7.4a.8 has no such table; read from `flows` (F3-15) |

**Independence of the audit route.** `capex.audit.network` shares no builder network code. It rebuilds islands, the reference rule,
b, PTDF and angles itself (scipy, `numpy.linalg.solve` against the builder's `inv`). Code it does share:
(i) the loader's `Case` arrays (`x_pu`, `base_mva`, `f_plus`). These are case data, and the P5a independent scipy route reads
the CSVs directly, so a loader parsing error would still show. (ii) `Solved` unscaling through `model.column_scale`. A wrong θ
scale would show in `kvl.recompute`. (iii) `nodal_price` and `dcpf.islands` read the LP matrix. The spec requires this.
None of the three is a finding.

## 2. Findings
**F3-1 should-fix (Gate 3).** The fingerprint `formulation_version` is still F-0.2.
- Spec: §8.10; data-schema l.53 ("the code's version goes into the fingerprint"); §7.4a.9, which already masks this field in the
  golden test.
- Code: `src/capex/__init__.py:3` and `audit/fingerprint.py:77`. `run.py:68` writes the case's version to `run.json`.
- Evidence: the pjm5 dcpf run has `run.json` F-0.3 but fingerprint component F-0.2, and the code comment cites §7.4a.9 for the
  opposite of what it says. `tests/test_health_fingerprint.py:217` asserts F-0.2.
- Fix: set the constant to `F-0.3`, and have the verifier update `:217` in the same item. The spec is already clarified
  (amendment 2e). Every fingerprint changes once.

**F3-2 should-fix.** Switch keys and tolerance keys are not validated.
- Spec: §7.4a.1 (gap; amended in 2a).
- Code: `data.py:156-182`, `data.py:555-556`, `network.py:41-42`.
- Evidence: `tx.losses: true` loads and runs with the key ignored. `tx.dcpf_formm: ptdf` runs the angle form (G3-5).
  `tolerances: {kvl_resid_mw: 1}` raises TypeError. `tx.ref_bus: 3` raises "TypeError: 'int' object is not iterable".
- Fix (builder): allowlist `tx.model`, `tx.dcpf_form`, `tx.ref_bus`, `scaling`; anything else is a DataError, and so are bad
  tolerance keys or a bad `tx.ref_bus` type.

**F3-3 carry to Gate 4 (spec amended).** The non-toy 1e-3/1e-1 MW split is not built.
- Spec: §7.4a.6 ("as for `balance`").
- Code: `report.py:96-99`. `balance` at `report.py:135` has no split either; only `conditioning.bal_residual_mw` carries §6.2.
- Evidence: nothing in the code marks a case as toy or non-toy.
- Every Gate 3 case is a test system, and gate-3.md §4 requires 1e-6, so nothing fails today. Amendment 2b defers the split to
  Gate 4 (the first non-toy case), where one rule will cover all four MW checks.

**F3-4 carry (schema bump; owner review item 6).** `pjm5` `sources.csv` and `periods.csv` have thin provenance.
- Code: `data.py:50`. The schema defines `sources` as (`source_id`, `description`) and gives `periods` no provenance columns, so
  this is the same for every case and is not a pjm5 deviation.
- Vintage and licence are recorded in `docs/data-sources.md` and `cases/raw/pjm5bus/README.md`. Period weights are derived from
  `model_year` (§1.2).
- Belongs with the DECISIONS 49 schema reconciliation.

**F3-5 no defect (G3-7 narrative).** Blank `ntc_*` means unlimited under both models.
- Spec: data-schema l.120 says so explicitly.
- Effect: the P5f transport run has only ab (400 MW) and de (240 MW) limits, so most of the network is a copper plate. This
  belongs in the P5f text ("transport has no loop flow and no ratings on four lines"), not in a fix.

**F3-6 no defect (G3-7 narrative).** The bus-D weights α = (1.497137, −0.497137) are correct.
- Spec: §7.4a.7, which says the weights are not convex.
- Evidence: they reproduce π_D = 39.943, sum to 1, and match the spec example.
- Meaning: 1 MW more load at D is served by +1.497 MW from solitude (C) and −0.497 MW from brighton (E), which keeps de at
  240 MW. This is for the markets reviewer.

**F3-7 should-fix (spec amended in 2d; verifier test needed).** Formats of the list cells.
- Spec: §7.4a.7 said `setter_ids` and `binding_links` are "sorted", and §4 never defined `island_id`. G3-2 and G3-5 had left
  this open.
- Code: `loopsetter.py:148` and `pricesetter.py:254` write `setter_ids` grouped by bus ("solitude,brighton"; sorted would be
  "brighton,solitude"). `pricesetter.py:245` writes `binding_links` in `links.csv` order. `island_id` is 0-based under
  transport and 1-based (`loopsetter.py:226`) under dcpf.
- Resolution: amendment 2d ratifies the code. Transport byte identity forbids changing the transport order, and the dcpf order
  matches `price_setter_loop`.

**F3-8 should-fix (spec error, amended in 2c; builder plus test).** BLACKOUT is counted as a marginal member of 𝓜_i.
- Spec: §7.4a.7.
- Code: `loopsetter.py:106-115` uses `local[:6]`, which includes `VOLL_BLACKOUT` with c = VOLL. At a blackout bus
  π = VOLL + μ^use, so Φz = c is wrong, and every loop bus of that island would become UNEXPLAINED.
- Gate 3 cases cannot reach this path (VOLL never binds in pjm5; P5e peaks at 1100 MW against 1530 MW of capacity).
- Fix: skip `VOLL_BLACKOUT` in `_members`, and add a bound π_m ≥ VOLL in `_bounds` (`loopsetter.py:118-128`).

**F3-9 carry (the first dcpf case with storage; depends on owner review item 7).** The case-(c) interval has no storage rows.
- Spec: §7.4a.7 says "every resource at a bound", but gives no inequality for storage, which involves the water value v.
- Code: `loopsetter.py:118-128`.
- Effect: the interval can only be too wide, never wrongly tight. Amendment 2c states this limit for Gate 3.

**F3-10 should-fix (spec amended in 2b; builder plus test).** `congestion_rent` adds up all islands per hour.
- Spec: §7.4a.5 states the identity per island-hour; the §7.4a.6 table said max over (p,t).
- Code: `audit/network.py:141-144`.
- Effect: with two or more islands, residuals of opposite sign cancel.
- Fix: compute the residual per island-hour and take the max. On single-island pjm5 the value does not change.

**F3-11 should-fix (verifier).** Only builder smoke tests cover CONGESTION_LOOP cases (b) and (c).
- Spec: §7.4a.7 (b)/(c), the `DEGENERATE` sub-tag, `price_lo`/`price_hi`, and no `price_setter_loop` rows in (c).
- Code: covered only by `tests/builder/test_builder_g3_3_smoke.py:60-74`.
- This breaks "builder ≠ verifier" (CLAUDE.md) for a feature of this gate.
- Fix (verifier): tests built from the spec formulas, not from the code.

**F3-12 carry (nit, latent).** θ reduced costs and `ref_angle` row slack and activity are unscaled with the k_P factors.
- Code: `solved.py:27-44`. θ needs 1/(k_C s_obj), and `ref_angle` is a radian row.
- Effect: both are exactly 0 at every optimum (θ is free and basic; the ref dual is 0), so no output is affected. It would
  matter if θ ever got bounds (angle limits are out of scope).

**F3-13 carry with F3-9 (nit).** The interval LP maps only HiGHS status "Unbounded" to ±∞.
- Code: `loop.py:63`.
- Effect: a status such as "Primal infeasible or unbounded" would give NaN and then UNEXPLAINED. This is a visible false fail,
  not a silent one. Case (c) cannot occur in Gate 3. The hand-made probe returned "Unbounded" correctly.

**F3-14 should-fix, resolved here (spec amendment 2c).** Line tolerances and the 𝓜_i price check were undefined.
- Spec: §7.4a.7 did not define a line's tol_π or tol_q.
- Code: `loopsetter.py:99` uses the max of the end buses' tol_π; `loopsetter.py:102` uses `tol_q_abs_mw`; `loopsetter.py:113`
  requires the class price check for 𝓜_i membership.
- Resolution: amendment 2c ratifies the code. No code change.

**F3-15 should-fix, resolved here (spec amendment 2f).** §8.12 asks for congestion rent per hour and per year, but no output
table exists. The amendment defines both as read from `flows` (μ·f, w_p). No code change.

## 3. Proposed fix items (PLAN.md lines, before G3-7)
- [ ] G3-6-fix1 Formulation lead [Sonnet] (mechanical doc alignment): align `docs/data-schema.md` with formulation F-0.3 amendment 2 (DECISIONS 51): `switches` row (key not implemented = load error; list `scaling`), `tolerances` row (unknown key = load error), `run.json` `formulation_version` = case's declared version (fingerprint = code's), `price_setter` list-cell order and `island_id` per formulation §4 "List cells". Docs only.
- [ ] G3-6-fix2 Builder [Sonnet] (+ verifier subagent for one test line, as G3-3-fix2): `reports/gate-3-spec-trace.md` F3-1/F3-2/F3-8/F3-10 — (1) `capex.FORMULATION_VERSION = "F-0.3"` (verifier edits `tests/test_health_fingerprint.py:217` to F-0.3 in the same item; §7.4a.9 golden identity must stay green); (2) loader: `switches` allowlist `tx.model, tx.dcpf_form, tx.ref_bus, scaling`, any other key, an unknown `tolerances` key or a non-string `tx.ref_bus` → `DataError`; (3) `audit/loopsetter.py`: `VOLL_BLACKOUT` not in 𝓜_i, blackout bound π ≥ VOLL in case (c); (4) `congestion_rent` per island-hour (§7.4a.6). T1–T4 golden and pjm5 outputs unchanged apart from fingerprints.
- [ ] G3-6-fix3 Verifier [Sonnet]: tests from formulation F-0.3 amendment 2 (not from the code): loader rejects `tx.dcpf_formm`, `tx.losses: true`, `reserves.enabled: false`, an unknown tolerance key, `tx.ref_bus: 3` with `DataError`; fingerprint `formulation_version` = F-0.3 and `run.json` = case version; `price_setter` list cells (P5a A: `setter_ids` `solitude,brighton`, `setter_zone` `C,E`, `island_id` 1; T4 transport `island_id` 0); `congestion_rent` evaluated per island on the islands fixture; `CONGESTION_LOOP` cases (b) and (c) from the §7.4a.7 formulas (min-norm α sums to 1 and reproduces π; interval incl. ±∞; `DEGENERATE`, `price_lo/hi`, no `price_setter_loop` rows in (c)); a total-blackout bus is never in 𝓜_i.

Carried (record in the Gate 3 review, no item now): F3-3, F3-9, F3-13 → Gate 4 spec work; F3-4 → schema bump (DECISIONS 49);
F3-12 → whenever θ gets bounds.

## 4. Owner yes/no questions (for the G3-7 decision list)
1. Should switch keys be strict, so that a key for a later gate is rejected even when set to its default-off value (for example
   `reserves.enabled: false`)? Recommendation: yes. A no means default-off values of keys listed in data-schema are accepted.
2. Is it acceptable that every run fingerprint, T1–T4 included, changes once because `formulation_version` goes from F-0.2 to F-0.3
   (as §7.4a.9 already provides)?
3. Should F3-3 (non-toy MW warn/fail), F3-9 and F3-13 (loop interval with storage) and F3-12 be carried to Gate 4? If dcpf is not
   kept for Gate 4 (review item 7), F3-9 and F3-13 wait until dcpf returns.

Spec edits made in this item: `docs/formulation.md` (header, §4 List cells, §7.4a.1, §7.4a.6, §7.4a.7, §8.10, §8.12) and
`DECISIONS.md` entry 51. No edits to `src/capex/` or `tests/`.
