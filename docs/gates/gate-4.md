# Gate 4 — RTS-GMLC fixed-fleet dispatch vs the PLEXOS reference; first performance-ledger rows: exit criteria

Status: **DRAFT (prep item P12, formulation lead, 2026-11-27) — NOT APPROVED. Owner approves or amends this at the start
of Gate 4.** Once approved, the criteria are frozen (docs/gates/README.md). Branch `gate-4` is created from `gate-3`.
Inputs: DECISIONS 3, 29, 45–47, 52(3), 54(7, 10); reports/gate-3-review.md §4 (a)–(c); reports/gate-3-spec-trace.md
(F3-3, F3-9, F3-12, F3-13); docs/drafts/architecture-spec.md §A (feature-block contract A1–A10); `cases/rts_gmlc/`;
`cases/raw/rts_gmlc/`. Gate numbers follow DECISIONS 43: reserves = Gate 9, linearized UC = Gate 11.
Default network model stays `transport` (DECISIONS 29/47). `dcpf` is used here on a nodal variant only, as an option.

## 1. Scope
In: the fixed-fleet LP (formulation F-0.3 + §3 amendments S1–S4 → **F-0.4**) on RTS-GMLC against the PLEXOS DA
reference; the HVDC block `tx.dc_links` (S1); storage under `dcpf` (S2: closes F3-9, F3-13); the non-toy audit profile
(S3: F3-3); θ/`ref_angle` unscaling (S4: F3-12); case variants and reference tables (§2); `reports/performance-ledger.md`
(README "Performance budget"); complexity-ledger rows for `tx.dc_links` and for `tx.model` on RTS.
Also in: carried data items K4–K6 (§7).
Out: UC (Gate 11), reserves/ORDC (Gate 9), losses, rep periods and inter-period SOC (Gate 5), expansion, PJM data,
a scoreboard (it starts at Gate 5, README §3). LMPs are **reported, not judged** (§5).

## 2. Reference facts (checked in this draft against the vendored files) and runs
- **The reference is 336 h, not a full year.** `FormattedData/PLEXOS/PLEXOS_Solution/DAY_AHEAD Solution Files/{allTX,noTX}/`
  holds `generation`, `commitment`, `cost` (156 units), `price` (73 buses) and `flow` (120 AC branches + `113_316_1`).
  The window is 2020-07-05 00:00 to 07-18 23:00. `MANIFEST.csv` lists no other PLEXOS, Prescient or SIIP *results*
  at the pinned commit. The upstream HTML reports (`RTS_*_7.12/7.15.html`, not vendored) look like the same windows
  (verify). The window starts exactly at block **p063**. The comparison uses p063–p066 plus the first 48 h of p067.
- **The reference has no storage or CSP.** `313_STORAGE_1` and `212_CSP_1` have no columns in the outputs, and total
  generation equals our window load exactly (1,793,948 MWh), so no storage losses and no unserved energy are visible.
  Whether PLEXOS modelled these two units at all needs checking (verify).
- **HVDC.** In `allTX`, `113_316_1` lies in [−100, +100] MW: 303 h at +100, 20 h at −100, mean 85.4 MW from Area 1 to
  Area 3. It is dispatched and sits at its limit in 96% of hours. In `noTX` it runs from −155 to −62, so noTX also
  lifts this limit. Its `MW Load` value of 100 therefore acts as a ±100 MW rating.
- **Congestion is rare.** In `allTX`, 13 of 336 h have a bus price spread above 0.01 $/MWh (max 43.34). CB-1 sits at
  500 MW in 10 h. Prices range from −6.87 to 111.59 $/MWh, mean 21.79. 15% of bus-hours are at or below 0.01 $/MWh and
  7 are negative, which comes from fixed hydro and RTPV schedules. `noTX` has one price in every hour.
- **Cost basis.** The `cost` file sums to $27.01 M (allTX). Pricing PLEXOS generation at our linear MC gives $25.70 M.
  The 4.9% gap is no-load, start and heat-rate-curve cost that our LP does not have. What the cost file contains is
  unverified (verify).

| Run | Case | Config | Window | Role |
|---|---|---|---|---|
| R4-Z | `rts_gmlc_px` (3 zones, PLEXOS-aligned fleet: no CSP, no storage) | `transport` | p063–p067 | judged vs allTX (§5) |
| R4-C | `rts_gmlc_px_cp` (one zone, copper plate) | `transport` | p063–p067 | judged vs noTX (cleanest UC/reserve gap) |
| R4-N | `rts_gmlc_nodal_px` (73 buses, 120 AC lines + DC1) | `dcpf`, angle, `tx.dc_links` absent (= controllable) | p063–p067 | judged vs allTX; reported nodal |
| R4-NP / R4-NX | same | PTDF form / `tx.dc_links: exclude` | p063–p067 | equivalence (§4) / ablation (§8) |
| R4-NS | `rts_gmlc_nodal` (full fleet, storage at bus 313) | `dcpf` | p063–p067 | storage under dcpf on a real case (health checks only) |
| R4-F | `rts_gmlc` and `rts_gmlc_px` full fleet / aligned | `transport` | 122 blocks | full-year health checks, block identity, performance |
| R4-NF | `rts_gmlc_nodal` | `dcpf` | 122 blocks | performance ledger only; separate Actions job, not in CI |

All runs are fixed fleet ($X^{max}=0$), have no inter-block SOC (cyclic per 72 h, Gate 5 adds linking), and use
`audit_profile: standard` (S3).

## 3. Spec changes this gate requires (W-spec, item G4-1; one DECISIONS entry; version F-0.3 → F-0.4)
**S1 — HVDC as a controllable link inside `dcpf` (chosen).** This replaces "no HVDC/transport links mixed with lines" in §7.4a.
- *Data:* `links.csv` gets a `link_type` ∈ {`ac`, `dc`} column; blank or absent means `ac`, so every existing case is
  unchanged. A `dc` row must have blank `reactance_pu`/`base_mva` (`DataError` otherwise). Asymmetric `ntc_fwd`/`ntc_rev`
  ratings are allowed. A rating of 0 is an error.
- *Sets:* $\mathcal L=\mathcal L^{AC}\cup\mathcal L^{DC}$. Islands are the components of $(\mathcal N,\mathcal L^{AC})$
  only. A DC link may join two islands.
- *LP:* no new columns. A DC link $k$ is a `flow` column with bounds $-F^-_k\le f_k\le F^+_k$.
  - Angle form: `bal` is unchanged (the transport injection pair) and $k$ gets **no `kvl` row**.
  - PTDF form: $f_k$ enters as $+f_k$ at $e(k)$ and $-f_k$ at $o(k)$. That means `bal_sys[i]` gains
    $\sum_{k:e(k)\in i}f_k-\sum_{k:o(k)\in i}f_k$, and `ptdf_flow[l]` gains $-(H_{l,e(k)}-H_{l,o(k)})f_k$ (coupling hook H1).
  - Lossless: DC1 `R Line` is ignored (state it in the assumptions book).
- *Duals:* $\mu_k=-s_f/w$, read as for transport, gives $\mu_k=\pi_{e(k)}-\pi_{o(k)}$ with $\mu_kf_k\ge0$. It is nonzero
  only at a limit. The decomposition $\pi_n=\lambda_{i(n)}-\sum_{l\in\mathcal L^{AC}}H_{l,n}\mu_l$ is unchanged, because
  $\mu_k$ does not enter it.
- *Congestion rent* is computed per **rent component** (islands joined by any DC link), each hour:
  $\sum_n\pi_n(-\text{inj}^{res}_n)=\sum_{l\in AC}\mu_lf_l+\sum_{k\in DC}\mu_kf_k$. Here $\text{inj}^{res}$ excludes DC
  flows. With no DC link this is exactly amendment 2.
- *Price-setter (§7.4a.7):* prices are computed per **price component** (islands joined by DC links strictly inside
  their limits). Unknowns are one $\lambda_i$ per island and $\mu_{\mathcal K}$ (binding AC lines), with
  $\phi_n=[e^\top_{i(n)},-H^\top_{\mathcal K,n}]$. The rows are $\phi_b$ for marginal buses ($=c_b$), plus
  $\phi_{e(k)}-\phi_{o(k)}=0$ for each free DC link. Cases (a)/(b)/(c) compare the row count, $|\mathcal B|+|\mathcal D^{free}|$,
  with the column count, #islands $+|\mathcal K|$. A DC link at a limit is listed in `binding_links`.
- *Checks:* `price_setter.link_inconsistent` is evaluated on the DC links under `dcpf` (it is no longer n/a).
  `ptdf.recompute` adds DC flows to the case-data injections. `kvl.recompute` skips DC links.
- *Switch:* `tx.dc_links` ∈ {`controllable`, `exclude`} is a sub-switch of `tx.model=dcpf` (load error under
  `transport`, A1). Absent means `controllable`, which deviates from A1's "off is default". The reasons: the block is
  data-activated, it is inert on every earlier case (none has `dc` rows, so A10 holds trivially), and dropping data the
  user supplied silently would break the strict-key rule (DECISIONS 51(a)). `exclude` is the ablation. Under
  `transport`, `link_type` is validated but ignored, so a DC link stays a plain link and transport outputs stay identical.
- *Why not the alternatives:*
  - **Exclusion** would remove a tie that sits at ±100 MW in 96% of reference hours (≈28.7 GWh Area 1→3 in the window).
    That is material next to only 13 congested hours, and R4-NX quantifies it.
  - A **fixed 100 MW injection** contradicts the reference, which reverses the flow in 20 h.
  - The **controllable link** matches the reference and is standard practice: MATPOWER `toggle_dcline` uses paired
    injections (Zimmerman et al. 2011, verify), and PyPSA separates `Link` from `Line` (Brown et al. 2018). It adds no
    columns and has fewer rows than an AC line. It is also needed later for PJM controllable ties (merchant HVDC/VFT
    into NYISO, verify) and for zonal interfaces mixed with lines.

**S2 — storage under `dcpf` (closes F3-9).** The case-(c) interval LP gets one inequality per storage unit at a bound
at bus $m$. It uses the §4 setter costs at the **solved** water value $v_{r,p,t}$: $c^d=VOM+v/\eta^d$ and $c^c=\eta^cv$.
- idle: $c^c\le\pi_m\le c^d$
- discharging at the `st_pwr` limit: $\pi_m\ge c^d$
- charging at the `st_pwr` limit: $\pi_m\le c^c$

The interval is therefore *conditional on v*, which is noted in `detail`. The solved point always satisfies it, so it can
never produce a false fail. It is narrower than the full dual range, and it is no longer "only wider".
Storage units that pass their class check join $\mathcal M_i$, as in F-0.3.
**F3-13 (closed):** the adapter maps solver status to an enum.
- `OPTIMAL` gives a value.
- `UNBOUNDED` and `UNBOUNDED_OR_INFEASIBLE` give ±∞. The LP is feasible by construction, because the solved $(\lambda,\mu)$ is a point of it. That point's feasibility is checked first.
- Anything else fails the new check `price_setter.loop_interval`: value = count of failed solves plus count of
  $\pi\notin[\text{lo}-tol_\pi,\text{hi}+tol_\pi]$; pass = 0. It never becomes NaN or a silent UNEXPLAINED.

**S3 — non-toy warn/fail split (closes F3-3).** Add a top-level `case.yaml` key `audit_profile` ∈ {`exact`, `standard`}.
Absent means `exact`, so T1–T4 and `pjm5` keep their hash, fingerprint and outputs. It covers `balance`,
`storage.soc_recompute`, `kvl.recompute` and `ptdf.recompute`.
- `exact`: pass ≤ 1e-6 MW or MWh.
- `standard`: warn > 1e-3, fail > 1e-1, the §6.2 `bal` thresholds. 1e-1 MW is 1e-5 of the 8.2 GW RTS peak.

Every other threshold is unchanged in both profiles. The profile is written in `detail`, and it enters the fingerprint
only when present. RTS cases set `standard`.

**S4 — F3-12 (closed).** θ reduced costs and `ref_angle` row activity and slack are unscaled by the §6.1 column/row
rule ($k_\theta=1$; θ reduced cost × $1/(k_C s_{obj})$). No output changes today, because both are 0 at every optimum.

**S5 — docs.**
- benchmarks.md §6 row G4: "full-year" becomes "336-h PLEXOS window", and "zonal price MAE ≤10%" becomes "reported".
  Under DECISIONS 21 the reason is a formulation gap known before any result (UC and reserves in the reference;
  non-unique LP prices at capacity before Gate 9), not a missed target.
- data-schema: `link_type`, `audit_profile`.
- DECISIONS entry for the heat-rate choice (secant incremental, no no-load term; P5 note).

## 4. Known-answer tests (verifier, from the spec; independent route = `scipy.optimize.linprog(highs)` from case CSVs, never `capex` builders)
Tolerances are those of gate-3.md §3: objective rel 1e-7, dispatch 1e-4 MW, LMP 1e-4 $/MWh vs the independent route.
| Id | Case | Must reproduce |
|---|---|---|
| H1a | `pjm5` + DC link B→E, ±50 MW, binding | dispatch, LMPs, $f_k$ at its limit, $\mu_k=\pi_E-\pi_B$; decomposition; rent identity incl. $\mu_kf_k$ |
| H1b | H1a with a ±500 MW DC rating (free) | $\pi_B=\pi_E$; the free-DC row enters α; UNEXPLAINED = 0 |
| H1c | two AC islands joined only by one DC link (fixture) | two λ; binding: prices differ by $\mu_k$; free: one price; rent per component |
| H1d | H1a with `tx.dc_links: exclude` | canonical outputs equal P5a golden (§8.10a rule) |
| H1e | H1a, angle vs PTDF form; and `link_type` dc vs ac under `transport` | equal primal and LMPs (rel 1e-9 / abs 1e-6); transport outputs identical |
| S2a | `pjm5` + storage (bus D, 50 MW / 200 MWh) under a two-level 72-h load | SOC, STORAGE_DIS/CH classes, storage in $\mathcal M_i$ with correct α; `storage.soc_recompute` |
| S2b | fixture forcing case (c) with storage at a bound | interval contains π; ⊆ the interval without storage rows; equals the verifier's own interval LP (abs 1e-6) |
| S2c | interval LP returning `UNBOUNDED_OR_INFEASIBLE` (stub adapter) | ±∞, no NaN; `price_setter.loop_interval` = 0 |
| A1 | synthetic residuals 5e-4 / 5e-2 / 0.5 MW | exact: fail/fail/fail; standard: pass/warn/fail; no key = exact |
| U1 | injected scaled solution vector | θ reduced cost and `ref_angle` slack unscaled per S4 |
| B1 | R4-F (aligned) restricted to p063–p067 vs R4-Z | per-block objective rel 1e-8 (blocks are independent at Gate 4) |
| N1 | R4-N vs R4-NP | objective rel 1e-7, LMP abs 1e-4 (where duals are unique) |

Mutation tests (numbers M13–M16; M11/M12 are reserved by the architecture draft for `ra.prm`). Each must make at least
one check or test fail:
- (M13) one S2 inequality sign flipped → `price_setter.loop_interval`.
- (M14) a DC link given a `kvl` row (x = 0.01) → `link_inconsistent` on DC.
- (M15) DC flow dropped from `ptdf_flow` → `ptdf.recompute`.
- (M16) "infeasible or unbounded" mapped to NaN → `loop_interval`, never a silent UNEXPLAINED.

## 5. RTS-GMLC comparison criteria (verifier computes them from run outputs + reference tables; builder does not)
Notation: $C^{PX}_{our}=\sum g^{PX}MC^{our}$ (PLEXOS dispatch priced at our cost data). $Z^{our}$ is our variable cost
in the same window.
| Id | Metric | Runs | Rule | Justification |
|---|---|---|---|---|
| F0 | reference feasibility | R4-Z, R4-C | PLEXOS dispatch, with tie flows summed per area pair and DC1 as the DC link, violates no constraint of our LP by > 1 MW (rounding) | establishes that both models describe the same system. A violation is a data-alignment error to fix, not a tolerance to loosen |
| C0 | lower bound | R4-Z, R4-C | $Z^{our}\le C^{PX}_{our}(1+10^{-6})$ | follows from F0: the PLEXOS dispatch is feasible in our LP, so our optimum cannot cost more. A breach is a bug |
| C1 | like-for-like cost gap $(C^{PX}_{our}-Z^{our})/C^{PX}_{our}$ | R4-Z, R4-C, R4-N | ≤ 5% **[P]** | benchmarks.md §6 G4 row. The gap measures what UC (Pmin, min up/down) and reserves force on PLEXOS. LP-relaxation gaps of a few % are usual (Palmintier & Webster 2014, verify). R4-N has no C0, because PLEXOS flows may not satisfy our lossless KVL exactly (verify PLEXOS DC-OPF settings) |
| C2 | total cost vs PLEXOS `cost` file | all | reported; must close exactly: (PLEXOS cost − $C^{PX}_{our}$) [cost-basis gap: no-load, start, HR curve] + ($C^{PX}_{our}-Z^{our}$) [dispatch gap] = PLEXOS cost − $Z^{our}$ | basis gap measured here as 4.9% (allTX). Judging it would grade cost data that the LP cannot have before Gate 11 |
| G1 | generation share by tech (coal, gas CC, gas CT, oil, nuclear, hydro, wind, PV, RTPV) | R4-Z, R4-C, R4-N | abs ≤ 3 pp each **[P]**; nuclear ≤ 0.5 pp | benchmarks.md §6. Nuclear (MC 8, lowest) runs flat in both models (reference 7.48%) |
| G2 | VRE+hydro curtailment, unserved energy | all | unserved = 0 MWh (reference serves all load); curtailment reported | the reference schedules hydro and RTPV as fixed. Ours may curtail them at π = 0 |
| L1 | area and bus LMP: mean, PDC quantiles (p5…p99), hours ≤ 0.01 and < 0, bus spread hours | all | **reported, not judged**, labelled `expected gap: UC/reserves/fixed hydro+RTPV` | the reference has UC and 7 reserve products (reserves.csv). LP prices at capacity-bound hours are non-unique before Gate 9 (benchmarks §5). Our MC ≥ 0 cannot reproduce its 7 negative bus-hours |
| L2 | binding sets: hours CB-1/`ac_r2_r3` at limit (ref 10), DC1 at ±limit (ref 323), congested hours (ref 13) | R4-Z, R4-N | reported | expected-binding report. A gross mismatch (e.g. DC1 never at a limit) is investigated in evidence |
| P1 | marginal fuel shares, ours vs PLEXOS-inferred (committed unit strictly inside [Pmin, Pmax] with MC within 0.5 $/MWh of the bus price) | R4-Z, R4-C | reported | README price-setter benchmark. No IMM comparison on a test system |
| U0 | UC-gap attribution: PLEXOS energy at Pmin from committed units with MC > bus price ("UC must-run"), by tech | R4-C | reported | explains the G1 and C1 residuals line by line |

## 6. Health checks (all Gate 1 and Gate 3 checks keep their thresholds; profile `standard` per S3 on RTS cases)
| Check | Pass rule |
|---|---|
| All checks, all runs in §2 | no `fail`; every `warn` listed and explained in evidence. Strong duality, comp. slackness and dual sign use their unchanged thresholds on non-toy cases (verify they hold at RTS size). A miss leads to a spec-or-code decision, never a tolerance edit |
| Marginal price-setter report | UNEXPLAINED = 0 every zone-hour (R4-Z, R4-C, R4-F) and bus-hour (R4-N*, R4-NS). Per run: share of hours by class and by fuel; DEGENERATE share and interval widths. R4-NS must show STORAGE_DIS/CH rows that pass their price check |
| dcpf checks on R4-N*, R4-NS | `kvl.recompute`, `ptdf.recompute`, `lmp.decomposition`, `congestion_rent` (per rent component), `dcpf.line_duals`, `link_inconsistent` (DC), `dcpf.islands` (1 island at RTS; verified connected, 73 buses), `price_setter.loop_alpha`, `price_setter.loop_interval` all pass |
| Conditioning (§6.2) | no `fail`. Nodal $b_l$ spans 474–11,111 MW/rad (x 0.009–0.211 pu, checked) and scaling must handle it |
| Default unchanged | T1–T4 and `pjm5` P5a–P5f golden identity (§8.10a) with S1–S4 in. Fingerprints change once for F-0.4 (as DECISIONS 52(2)) |

## 7. Carried items
| ID | Item | Pass rule |
|---|---|---|
| F3-3 / F3-9 / F3-12 / F3-13 | closed by S3 / S2 / S4 / S2 | A1, S2a–c, U1, M13, M16 pass |
| K4 | `rts_gmlc` row appended to `data/common/sources.csv`; case-local copy retired (DECISIONS 38/41) | loader uses the common file. T* need no re-hash (DECISIONS 41) |
| K5 | provenance fix: assumption A4 says "flow file has no DC1 column", which is wrong. `113_316_1` exists and back-tests ±100 | `dc_r1_r3` becomes method `derived`, back-test noted like A3 |
| K6 | reference tables `ref_plexos_da_{alltx,notx}` (tidy CSV from the vendored files, sha256 equals MANIFEST.csv, `source_id=rts_gmlc`, method observed) | verifier test checks the hashes and window alignment (first hour = p063 t1) |

## 8. Complexity value review and performance ledger
- **Complexity ledger** (reported; judgment rules apply from Gate 5):
  - `tx.dc_links` row: R4-N vs R4-NX. Δ C1, Δ G1, Δ L2 vs PLEXOS; Δ rows/cols/nnz/time.
  - `tx.model=dcpf` update, now on a non-toy case: R4-N vs R4-Z. Δ C1, G1, L1/L2 vs allTX, Δ size and time.
  - S2–S4 are audit or spec fixes with no LP change, so they get no row.
- **Performance ledger** `reports/performance-ledger.md`. One row per case × run:
  - Columns: rows, cols, nnz, solve time (median of 3; T1–T4/pjm5 median of 7), peak RSS, solver method and crossover,
    HiGHS version, runner type, git commit, previous-gate value and ratio.
  - First rows: T1–T4, `pjm5` (Gate 3 reference = gate-3-evidence §8), R4-Z, R4-C, R4-N, R4-NP, R4-NS, R4-F, R4-NF.
  - Rules: T1–T4/pjm5 size identical to Gate 3 and time ≤ 2× (README). Window runs ≤ 60 s solve each **[P]**, so CI
    stays ≤ 10 min (DECISIONS 47). R4-F zonal full year ≤ 5 min and ≤ 4 GB **[P]** (size estimate ≈ 1.4 M cols/rows;
    verify on runner). R4-NF (≈ 3.7 M cols) is reported only.
  - Fallback if R4-F misses: per-block solves are exact at Gate 4 (no inter-block coupling), but that ends at Gate 5,
    so a miss is a ledger finding, not a fix to adopt silently.

## 9. Evidence file `reports/gate-4-evidence.md`
As in gate-3.md §5, plus:
- §2 facts re-verified;
- F0/C0–C2/G1/G2 tables per run with margins, and the C2 decomposition;
- L1/L2/P1/U0 tables labelled `reported`;
- H1a–e, S2a–c, A1, U1, B1, N1 expected vs obtained;
- M13–M16 caught;
- price-setter class/fuel shares;
- the A1–A10 block checklist for `tx.dc_links`;
- ledger rows;
- CI run links;
- assumptions-book excerpts for the RTS cases (lossless DC1, aligned fleet, heat-rate choice).

## 10. Proposed work items (PM writes them into PLAN.md on `gate-4`; builder ≠ verifier)
- **G4-1** Formulation lead [Opus]: W-spec S1–S5 into formulation.md (F-0.4), data-schema, benchmarks §6; DECISIONS
  entries (S1–S4 and the heat-rate choice).
- **G4-2** Data lead [Sonnet]: K4–K6. Converter variants: `rts_gmlc_px`, `rts_gmlc_px_cp`, `rts_gmlc_nodal`(`_px`)
  (73 buses, branch x/Cont Rating, DC1 `dc` ±100, load = area series × bus.csv `MW Load` share, which needs checking
  against PLEXOS participation (verify)). Sets `audit_profile: standard` and provenance on every new value.
- **G4-3** Verifier [Sonnet]: tests §4 (H1–N1, M13–M16) and the §5 comparison harness (F0/C0 route from case CSVs +
  reference tables), all from the spec, before the code exists (strict xfail).
- **G4-4** Builder [Sonnet]: S1–S4 in `src/capex/`, performance-ledger writer. No judging tests.
- **G4-5** Builder [Sonnet]: Actions job for R4-F/R4-NF (separate from CI, 30-min limit, artifact upload); CI runs window cases.
- **G4-6** Verifier [Sonnet]: runs everything, writes the evidence file and the ledger rows.
- **G4-7** Formulation lead [Opus]: code-vs-spec trace `reports/gate-4-spec-trace.md` (incl. the A1–A10 check).
- **G4-8** PM + markets reviewer [Opus]: `reports/gate-4-review.md` with the UC/reserve gap narrative (C1, G1, L1, U0)
  and the decision list.

## 11. Review and sign-off — decision list (format as gate-1.md §6)
Required items:
1. F0 and C0 hold, and C1/G1/G2 are within tolerance for R4-Z, R4-C, R4-N?
2. L1/L2/P1/U0 reported with gap labels, and no unexplained gross mismatch?
3. All health checks pass, with no `fail`, UNEXPLAINED = 0, and storage under dcpf correct (R4-NS, S2a–c)?
4. H1a–e, A1, U1, B1, N1 pass and M13–M16 are all caught?
5. Golden identity for T1–T4 and pjm5 holds, and F-0.4 (S1–S5) is accepted?
6. Performance-ledger rows present and within the [P] budgets, or the misses explained?
7. Complexity-ledger rows `tx.dc_links` and `tx.model` (RTS): keep `tx.dc_links` default `controllable`?
8. K4–K6 done and provenance complete?
9. Merge `gate-4` to `main` and mark Gate 4 DONE?

## 12. Owner questions (for approval of this draft; recommendation in brackets)
- O1. The full-year PLEXOS results are not in the repo. Accept the 336-h window (p063–p067) as the Gate 4 reference? A
  full year is used only for health and performance checks. [yes; the alternative is a data-lead search for other
  full-year RTS results, verify they exist]
- O2. Use a nodal variant (73 buses) as the `dcpf` case, because `dcpf` on the 3-zone equivalent has no meaningful
  reactances? [yes]
- O3. S1: model HVDC as a controllable link, with key absent = `controllable` (A1 deviation) and `exclude` as the
  ablation? [yes]
- O4. Make LMPs reported rather than judged, replacing benchmarks §6 "zonal price MAE ≤10%" for G4? [yes]
- O5. Judge on the PLEXOS-aligned fleet (CSP and storage removed, because the reference shows neither), with storage
  checked by R4-NS and the fixtures? [yes]
- O6. S2: use a storage interval conditional on the solved water value? [yes]
- O7. Confirm the [P] tolerances (C1 5%, G1 3 pp) and budgets (window ≤ 60 s, full year ≤ 5 min / 4 GB)? R4-NF stays
  outside CI. [yes]
