# DECISIONS (settled — append, don't rewrite)

2026-11-19 (owner + Claude, kickoff chat)
1. Own formulation, not built on PyPSA/GenX. Python. Literature informs, code is ours.
2. Solver: HiGHS default, solver-agnostic design (Gurobi optional later).
3. Time structure: weighted representative 3-day periods chosen by clustering on load,
   wind, solar, net load; always include peak and renewable-scarcity periods; weights =
   days represented. Inter-period storage linking for long-duration/seasonal storage.
   No 8760 capacity expansion. Backcasts use the same periods with fleet fixed; a one-off
   full-year fixed-fleet dispatch check validates the period selection.
4. Capacity market: PJM RPM modeled with a piecewise VRR demand curve and ELCC accreditation.
   Energy prices: shortage pricing (ORDC-style) and calibrated offer adders, all documented.
5. Benchmarking is the primary thread. Metrics: zone/month LMPs, on/off-peak spreads, RPM
   clearing prices, generation mix vs EIA-923, capacity factors, storage revenues vs IMM.
   Calibrate on some years, hold out others; no merge may worsen hold-out score.
6. First use case: storage value. UI: local web app, single user (owner) initially.
7. Team: 5 core roles (formulation lead, builder, verifier, data lead, PM incl. token
   economy) + 4 gate reviewers (markets PJM/NYISO, consulting, UI, client panel).
8. Budget: ~50% of owner's weekly Pro usage. Sessions run overnight ET. Sonnet default,
   Opus for spec and gate reviews. One deliverable per session.
9. Owner signs off every gate. No deadlines.

2026-11-19 (plan revision, owner approved)
10. 17 gates (0–16) replace the original 8; see PLAN.md. A crude PJM-wide 2023 backcast
    (Scoreboard v0, Gate 4) comes before added sophistication; from Gate 5 on, every feature
    must improve or hold the hold-out scoreboard.
11. Gate rigor framework: docs/gates/README.md. Criteria fixed before each gate starts.
12. Every solve reports the marginal price-setter per zone/hour from duals and dispatch;
    marginal fuel shares are benchmarked against IMM statistics.
13. Complexity value review: each feature has an ablation switch and a ledger row
    (accuracy gain vs compute cost); keep, default-off, or drop by judgment, owner decides.
14. CI and data downloads run in GitHub Actions.

2026-11-19 (owner)
15. NYISO gate removed. PJM only for now; other RTOs/grids added later, one at a time.
16. Data provenance is mandatory for every input value (docs/data-sources.md). Missing
    PJM unit characteristics are estimated from public data and literature with a
    documented hierarchy and back-testing; every run emits an assumptions book.

2026-11-19 (owner, expert review)
17. Test ladder before PJM: analytic toys → PJM 5-bus → RTS-GMLC (3 regions, ~150 gens,
    full year, published reference results) → GenX example cross-check → one PJM zone →
    PJM single node → PJM zonal. 21 gates (0–20), see PLAN.md.
18. Backcast accuracy drivers are first-class: daily hub-level gas prices (and fuel price as
    a clustering feature), forced extreme-event periods, outages, imports/exports,
    nuclear/hydro/pumped storage, DR.
19. Policy module (state RPS/CES, RGGI by state, federal credits under current law) and
    realism limits (annual build caps by tech/zone, going-forward-cost retirements,
    announced retirements/RMR fixed).
20. Engineering discipline: all costs carry a dollar year and are kept in real terms; one
    annualization function; numerical conditioning check in health checks; run fingerprint
    (inputs + code + solver settings hash) for exact reproducibility.
21. Benchmarking: day-ahead LMPs first; "good enough" targets set from literature before
    seeing results; forward runs compared with PJM West Hub futures.

2026-11-20 (owner, answering W1 questions)
22. Annualization: NREL ATB-style CRF including tax/depreciation (project finance factor)
    is the default; simple real-WACC CRF kept as an option. One `annualize` function.
23. Non-unique prices at capacity: score capex-mode prices on block/monthly averages until
    reserves/ORDC arrive at Gate 7; keep gate order.
24. Base dollar year 2024$, BEA GDP deflator. PJM backcast scarcity pricing uses PJM's
    reserve shortage pricing (ORDC) curve; VOLL only as unserved-energy backstop.

2026-11-22 (formulation lead, W3 — spec patch; owner confirms at Gate 0 review)
25. Formulation F-0.2 fixes Gate 0 review findings 1–5: fuel price $\phi_{f,p,t}$ (daily values within each
    3-day block); DECISIONS 22–24 written into §5.2/§9 (ATB-style PFF default with formula, simple CRF option);
    `VOLL` price-setter class covers total blackout (`BLACKOUT` sub-tag, `use_ub` rent); `bal` residual in
    unscaled MW (1e-6 for Gate 1 toys, §6.2 thresholds otherwise); $Z^0$ in reported total and decomposition
    but not in LP or duality check; $FOM^P/FOM^E$ defined; $w_p \ge 1$ with no upper bound; one remainder-day
    rule (§1.2); simplex (dual) forced, crossover mandatory with IPM, `basis_valid` checked. DC power flow
    option sketched as §7.4a (`tx.model`), pending owner decision on Gate 0 review item 3.
    Builder finding (W3): HiGHS `presolve=off` added to the default solver options (§4) so known-answer duals are
    reproducible; recorded in the run fingerprint.

2026-11-24 (owner, Gate 0 review — reports/gate-0-review.md items 1–16)
26. Owner accepts all recommendations in the 16-item list, with two overrides: (a) **buy nothing** — no data
    licences or paid services; (b) **simplest model first** — add complexity only in a later gate, and only
    after the simpler model solves properly (passes its gate). Gate 0 approved (item 1; F-0.2 confirmed, item 13).
27. Item 4 (gas licence): **no purchase**. Regional gas = EIA Henry Hub daily + public monthly basis
    (`gas_basis_fallback`, est_level 3). Accept the lower fuel-price confidence in backcasts.
28. Item 11 (futures): **no purchase**. Gate 17 compares with West Hub futures only if settles are freely
    available (public/delayed tables); otherwise that comparison is dropped and the gap logged. Never commit raw data.
29. Items 2, 3 under the simplicity rule: daily fuel price φ(f,p,t) is built at Gate 5 (rep periods), not before;
    Gate 1–4 toys/test systems keep one fuel price per case. DC power flow (§7.4a `tx.model`) is built at Gate 3
    only, as an option; transport/copper-plate stays the default.
30. Items 5–10, 14–16 accepted as recommended. Item 12: no extra Gate 0 reviewers (reviewers read Gate 1 in W6).
    Item 14: T1 mid/peak hours may be CAPACITY_RENT or TIE_AT_BOUND; block averages stay exact.

2026-11-25 (formulation lead, W4b-fix1 — spec amendment from W4b verifier findings; owner confirms at Gate 1 review item 5)
31. F-0.2 amendment 1 (LP unchanged; version string stays F-0.2). (a) New health check `storage.soc_recompute`
    (formulation §3 check 8, §8.6; gate-1.md §3): recompute the `st_soc` residual from case-data η^c, η^d, σ, ≤1e-6 MWh
    on toys. Reason: duality/CS/rent checks only prove the solved LP is self-consistent; mutation M4 (η swap) passed all
    of them. (b) Confirmed: STORAGE_DIS setter cost = VOM + v/η^d, STORAGE_CH = η^c v; `setter_cost`/`residual` now
    defined per class (§4 Outputs) — the code's π−VOM residual is a code bug. (c) `fuel` optional for VRE (and ST);
    VRE without `mc_override` has MC = 0 (data-schema §3.3, §6 rule 5). (d) T2c: storage duals at zero capacity are
    dual-degenerate; proven interval R^P+4R^E ∈ [15,465.19, 20,000] (§10); T2c tests assert the interval (rent ≤ cost,
    not <) and compare primal, π, generator ρ across scalings, not v/ρ^P/ρ^E. A degeneracy fact, not a tolerance edit.

2026-11-26 (formulation lead, W5-spec1 — spec wording from W5 findings F2, F6; owner confirms at Gate 1 review)
32. F-0.2 amendment 2 (wording only; LP, thresholds and code unchanged; version string stays F-0.2). (a) §6.2: primal
    and dual infeasibility are measured on the **scaled** LP (the solver's tolerances act there; `bal` gives the
    unscaled MW check). The text said "unscaled", the table "(scaled)"; the table and the code were right. (b) §6.2 row
    "RHS ratio / any finite bound" split into two metrics: RHS ratio max|b|/min|b| over nonzero finite row bounds
    (warn 1e6, fail 1e9) and largest finite variable bound, absolute in scaled units (warn 1e5, fail 1e7). This is the
    reading in `conditioning.py` (`rhs_ratio`, `bound_max`); its SPEC-AMBIGUITY note can be dropped at the next code
    touch. (c) §5.2: the ANN ≥ I/n output check applies only when r ≥ 0 and PFF ≥ 1 (ATB-style PFF ≥ 1 for any nominal
    WACC ≥ 0); a directly supplied pff < 1 skips it, as `econ.py:annualize` does.

2026-11-26 (owner, Gate 1 review — "yes to all" on reports/gate-1-review.md decisions 1–9, plus P1 licence question)
33. Gate 1 review answered yes to all 9 items: (1) T1–T4 within tolerance; (2) all health checks pass, UNEXPLAINED = 0;
    (3) fingerprint deterministic (environment-bound by design); (4) all audit mutations caught; (5) spec changes
    F-0.2 amendments 1–2 / DECISIONS 30–32 accepted; (6) local log in place of CI accepted (moot, CI green);
    (7) merge `gate-1` into `main` and mark Gate 1 DONE **after** item 8's fixes land and CI is green — this is the
    owner's advance approval for that merge, executed by item W7; (8) close M1, M2, C1, C2 first via W6-spec1, W6-fix1,
    W6-fix1-test; (9) carry later-gate findings (W5 F3–F5, F7, F8; markets M3–M5, M7; consulting C3–C8) into the draft
    criteria of the gates named (P2 and later gate drafts).
34. RTS-GMLC licence (P1): no LICENSE file upstream; owner approves use as an internal test system (subset vendored in
    `cases/raw/rts_gmlc/`, cited) and never in client deliverables until terms are confirmed.

2026-11-26 (formulation lead, W6-spec1 — spec from W6 findings M1, M2, M6, C1, C2; owner pre-approved by DECISIONS 33 item 8)
35. F-0.2 amendment 3 (reporting only; LP, duals, price checks and thresholds unchanged; version stays F-0.2). (a) M1, new rule:
    a `CAPACITY_RENT` hour's setters are the rent-set units (at cap, ρ > tol_π) with an interior build (`INVESTMENT_MARGIN`),
    else the rent-set unit(s) with the highest MC (`DEGENERATE`); only setters share the hour in the summary; the full rent
    set goes in new column `rent_ids`; `setter_cost` stays the interval lower end max MC at cap (formulation §4). Reason: on a
    real fleet nearly every unit is at cap in scarcity hours, so equal splitting would credit nuclear/coal as price-setters.
    (b) M2: `rents.rent_note` = `non-unique (bound)` for candidates with build_status `at_zero` (§8 item 5). (c) C1:
    data-schema §5 `rents` names the unit of every column ($/yr totals vs $/MW-yr, $/MWh-yr per unit). (d) C2: assumptions
    book starts with run_id/fingerprint (= run.json), case, base $ year, and a "Toy case: all inputs assumed…" banner when
    no input cell is observed/derived/estimated (§8 item 11; data-sources.md). (e) M6: §10 T2a typo, v = 60·0.9 = 54.

2026-11-26 (formulation lead, W6-spec2 — conflict found by W6-fix1; within DECISIONS 33 item 8 scope)
36. F-0.2 amendment 4 (reporting only; LP, fingerprint inputs and thresholds unchanged; version stays F-0.2). Canonical
    outputs, the object of gate-1.md §3 byte-identity, = every file in `outputs/<run_id>/` except `run.json`, with
    `assumptions.md` compared after removing its single `- run_id: ` line (which must exist once and equal `run.json`).
    Per-run values (run_id, timestamps, solve time) may appear only there; all other files are pure functions of the
    fingerprint inputs. data-schema §5 "every output table has `run_id`" replaced: tables carry no `run_id` column (the
    code already omits it); stacking readers take it from `run.json`. Reason: DECISIONS 35(d) put the random run_id in
    the assumptions book, which made byte-identity impossible as worded. Rejected: a deterministic run_id (two runs
    would share an id) and dropping run_id from the book (undoes C2). Verifier updates its test in W6-fix1-test.

2026-11-26 (owner)
37. Gate 1 approved; owner instructed the merge of `gate-1` into `main` (done 2026-11-26; CLAUDE.md conflict resolved
    with gate-1's version; 460 tests pass on main). `gate-2` created from `main`, prep branch P1–P10 merged into it.
38. Owner answered yes to every open recommendation: P3 (MATPOWER case5.m used as an internal test system, vendored and
    cited, not in client deliverables); P5 (append an `rts_gmlc` row to data/common/sources.csv and re-hash T1–T4
    manifests in one commit at Gate 4; heat-rate choice gets its DECISIONS entry at Gate 4); P8 (M7.1 pass/fail years are
    2024/25 and 2025/26; collar-capped years reported against PJM's uncollared simulation + MW shortfall); P9 (all 6
    storage-study outline items, applied at Gate 15); P10 (all 10 EIA-mapping items); Gate 2 criteria
    (docs/gates/gate-2.md) approved as drafted. Gate 3 and Gate 5 drafts stay DRAFT until their own boundary.

2026-11-26 (owner)
39. Owner answered yes to G2-3's question: `.github/workflows/data-download.yml` copied alone onto `main` (f123ad1) so GitHub
    can dispatch it (dispatch needs the file on the default branch). Dispatch-only, `contents: read`; a run with
    `--ref gate-2` uses gate-2's workflow and scripts. No other gate-2 work is on `main`; Gate 2 is not merged or done.

2026-11-26 (formulation lead, G2-6 — P1-b, delegated by approved gate-2.md §4)
40. P1-b: **exclude** the shared source registry `data/common/sources.csv` from per-file sha256 pinning in case manifests.
    T1–T4 `case.yaml` list `sources` without `sha256`; every other table (incl. shared `deflator.csv`) stays pinned.
    data-schema §5 and §6 rule 1 amended. Reason: the registry changes no number in the LP; it only gates provenance
    (`source_id` must exist, data-schema §6 rule 7) and, later, licence checks. Pinning it made every registry append
    (many coming at Gates 4, 16, 18) break every case until re-hashed — noise, not signal. Reproducibility is kept: the
    run fingerprint already hashes the registry as a canonical input table (formulation §8.10), so a registry edit still
    changes the fingerprint of every run that loads it. Rules: the registry is append-only for `source_id` (never delete
    or rename an id a case cites); rows may gain columns/fields. Rejected: keep pinning (re-hash churn across all cases per
    registry row); a case-local registry copy per case (drifts; the rts_gmlc copy is retired at Gate 4). Effect on
    DECISIONS 38 (P5): at Gate 4 append the `rts_gmlc` row and point rts_gmlc at the common file; no T* re-hash needed.
    Not an LP or formulation change (version stays F-0.2). T1–T4 fingerprints change once (manifest config component).
    Local: 547 pass / 30 skip / 0 fail; check_markers exit 0.

2026-11-26 (owner, live reply to G2-7's question)
41. Owner answered yes to G2-7's question (V2-1): once G2-7a fixes `.github/workflows/data-download.yml` on `gate-2`, the
    run doing G2-7a copies that one file alone onto `main` (as DECISIONS 39), so G2-7b can dispatch it. Only that
    file; no merge; Gate 2 stays not merged and not done.
42. Owner answered yes to all 9 Gate 2 review items (reports/gate-2-review.md, 2026-11-27): C1–C9 pass; D1–D8 pass with
    D4/D5/D7 as carried limitations; F3–F5, P1-a/b closed; pinned versions (requirements-ci.txt, ubuntu-24.04) are the
    supported environment; DECISIONS 38–41 and data-schema §5/§6.1 accepted; owner enables branch protection on `main`
    requiring `ci`; merge `gate-2` → `main` and mark Gate 2 DONE (owner later said to merge before the branch deletion; branch neutralized instead);
    markets items (a) log provenance/hashes and (b) case5.m hash test go into Gate 3 criteria, (c)–(f) are later-gate notes
    (Gate 4/11/16); bump Actions majors (Node 20 deprecation) in Gate 3.

2026-11-27 (owner, live session)
43. Gate restructure: multi-year optimization is a critical feature and gets its own gates, inserted right after Gate 6
    (GenX cross-check). The owner let the formulation lead set the split: **two gates** — 7 Multi-year expansion core
    (perfect foresight: model years, discounted year weights, vintages, lifetimes, horizon-end annuity truncation; toys +
    RTS-GMLC) and 8 Foresight modes + per-year periods + GenX multi-stage cross-check. Design draft:
    docs/drafts/multi-year-design.md (its O3–O12 stay open for the owner, due by the Gate 6 → 7 boundary). All gates
    renumbered, sequential. **Old → new map** (every gate number in entries 1–42, docs/drafts/* and reports/* before this
    date uses OLD numbers): 0–6 unchanged; 7→9 reserves/ORDC; 8→10 zonal transmission; 9→11 UC; 10→12 policy + build/
    retirement; 11→13 PJM one-zone slice; 12→14 scoreboard v0; 13→15 PJM single node; 14→16 capacity market;
    15→17 storage value study; 16→18 full data pipeline; 17→19 calibration + hold-out; 18→20 PJM zonal (multi-year
    now from Gates 7–8, applied at PJM scale); 19→21 local web UI; 20→22 continuous accuracy.
44. Design review (owner asked 2026-11-27 for a crisp, lightweight, best-practice design; docs/design-review-2026-11-27.md).
    Kept: one LP, block builder, 3-day rep periods, Kotzur SOC, clustered linear UC, ORDC, audit layer, test ladder.
    Changed, no new gates: (a) **one formulation, two modes** — plan (rep periods, multi-year, LP, investment duals) and
    operations (one year, full chronology, fixed fleet, rolling windows, optional UC); client hourly prices, spreads and
    storage revenue come from operations mode; Gate 4 builds operations mode (extends DECISIONS 3's "one-off" dispatch
    check into a mode; no 8760 *expansion* still holds); Gate 5 adds plan-vs-operations revenue reconciliation.
    (b) UC (Gate 11) is built in operations mode first; plan-mode UC optional, ledger sets the default.
    (c) ELCC-accredited planning reserve margin `ra.prm` enters at Gate 7; economic retirement (Gate 12) allowed with it
    on; Gate 16's VRR curve replaces the hard PRM row. (d) Performance budget from Gate 4: every gate reports size and
    runtime in `reports/performance-ledger.md`; Gate 7 adds a synthetic PJM-scale stress case; targets [P] pending owner.
    (e) Every feature is one block with a switch, labelled rows, audit hooks, a price-setter class and an off-identity test.
    Spec drafting: prep items P11 (architecture spec) and P12 (gate-4.md draft).
45. Owner reply to 44 (2026-11-27): **no operations mode.** Capacity expansion and prices both come from weighted
    representative 3-day periods (DECISIONS 3 unchanged). Primary price check: the weighted rep-period price duration
    curve (each modeled hour counts w_p real hours), plus monthly means and daily spreads from the same periods, mapped
    to the real-world PDC (benchmarks.md M1.4, M1.1, M1.5). Full-year fixed-fleet dispatch stays the one-off check of
    period selection only. Reverts 44(a) and 44(b): Gate 4 keeps its original scope; Gate 5 adds the PDC comparison
    instead of revenue reconciliation; UC (Gate 11) is in the expansion LP, switch default off unless the ledger shows it
    changes builds or PDC fit. 44(c) PRM at Gate 7, (d) performance budget, (e) block contract stand. Note: before
    Gate 9 (ORDC) prices at capacity-bound hours are non-unique, so the PDC upper tail is judged from Gate 9 on.
46. Owner (2026-11-27): full (integer/MIP) unit commitment is not used — the model stays an LP. The basis is
    **linearized clustered UC** (Palmintier & Webster; continuous commitment, formulation §7.5), built at Gate 11 with
    `uc.enabled` **default off**. The ledger reports its effect on builds and the PDC fit; switching it on by default is
    considered no earlier than Gate 19 (calibration + hold-out) and needs an owner decision.
47. Owner (2026-11-27): **Gate 3 criteria approved** (docs/gates/gate-3.md) with dispatch tolerance 0.01 MW and the P5e load
    scan kept; carried items K1–K3 added (DECISIONS 42). The default network model is and stays **`tx.model = transport`
    (pipe-and-bubble zonal transport)** everywhere, incl. PJM zonal; `dcpf` is an option only (reaffirms DECISIONS 29).
    **Runtime targets confirmed:** PJM single node, 1 year (~20 periods) ≤ 2 min; PJM zonal (~20 zones, 50+ clusters),
    4 model years ≤ 30 min — with or without linearized UC (no separate UC target: linearized UC is part of the zonal
    LP); CI ≤ 10 min. Branch `gate-3` created from `gate-2`.

2026-11-27 (formulation lead, G3-1 — W-spec, gate-3.md §6)
48. Formulation **F-0.3**: §7.4a DC power flow option completed (spec only; `transport` stays the default, DECISIONS 29/47).
    Switches `tx.model` (`transport`|`dcpf`), `tx.dcpf_form` (`angle` default|`ptdf`), `tx.ref_bus` (default: first zone of
    each island in `zones.csv` order). Angle form: free `theta` (rad, unscaled; `kvl` coefficient $k_P b_l$, $b_l$ =
    `base_mva`/`reactance_pu` MW/rad), rows `kvl` and one `ref_angle` **row** per island-hour (dual is 0 by construction).
    PTDF form: per-island PTDF from the reduced B matrix; rows `bal_sys` + `ptdf_flow` with `flow` columns **kept**, so flow
    limits stay column bounds (no ranged rows; F5 not exercised) and $\mu$ is read identically in both forms and in
    `transport`: $\mu=-s_f/w$, signed, $\mu f\ge0$. LMP decomposition $\pi_n=\lambda_{ref}-\sum_l H_{l,n}\mu_l$ (+ loss 0);
    components are reference-bus dependent, totals, $\mu$ and $\alpha$ are not. Congestion-rent identity per hour.
    Checks (dcpf only): `kvl.recompute`, `ptdf.recompute` (case-data route, no shared builder code), `lmp.decomposition`,
    `congestion_rent`, `dcpf.line_duals`, `dcpf.islands`, `price_setter.loop_alpha`. Price-setter: congested islands use
    bus-local classes, then `CONGESTION_LOOP` with $\alpha_n^\top=\phi_n\Phi^+$ over marginal buses and binding lines
    ($\sum\alpha=1$, not convex); `DEGENERATE` when weights are non-unique (min-norm) or not computable (interval from a
    tiny restricted dual LP). Outputs: `zone_hourly` LMP components, `angles`, `islands`, `price_setter_loop`; `flows`
    unchanged. Identity under `transport`: canonical outputs of T1–T4 byte-identical to golden Gate-2 outputs
    (`tests/golden/gate2/`) with fingerprint/version/git fields masked; loader accepts case `F-0.2` and `F-0.3`.
    data-schema `links.csv` validation (dcpf: x>0, base>0, symmetric rating, rating 0 an error, blank = unlimited).
    Mutation hooks M7–M10 named (§7.4a.10). gate-3.md §2 surplus corrected 14,957.28 → 14,957.29 (arithmetic only;
    gate-3.md is where the number is stated; criteria and tolerances unchanged). Rejected: `ref_angle` as a column bound
    (M9 would be invisible); PTDF limits as ranged rows (extra adapter risk, μ read from a different place); convex
    (non-negative) loop weights (wrong: P5a bus D has α = 1.497/−0.497).
49. Owner (2026-11-27, live reply to the G3-1 questions): (a) **yes** — the Gate-2 output key columns (`zone,period,t`,
    `link,period,t`, `resource,period,t`, `g_mw`) stay as they are through Gate 3 (transport byte-identity) and are
    reconciled with data-schema (`period_id`, `link_id`, `resource_id`) in a later schema bump; (b) **yes** — the
    `pjm5` test case keeps uppercase zone ids `A`–`E` (T4 precedent); real PJM data keeps lowercase ids.

2026-11-27 (formulation lead, G3-3-fix2 — spec ruling on cross-machine float noise)
50. Formulation F-0.3 **amendment 1** (comparison rule only; LP, outputs, fingerprint inputs and thresholds unchanged,
    version string stays `F-0.3`): new §8.10a. When two runs' canonical outputs are compared (§7.4a.9 golden identity,
    Gate-2 C7 two-job compare, later golden tests), the `value` field of `health.csv` and the value cell of the
    `health_report.md` check table are equal at $|a-b|\le10^{-12}$ absolute or relative; every other byte of every
    canonical output stays identical (row set/order, status, tolerance, detail; all decision outputs). Cause (CI run 148,
    job 140393434312): only `strong_duality` differed, 1.7e-16 vs 0.0 on T1/T2b/T2c/T3a/T4, between the golden machine
    and the CI runner. This workspace reproduces golden byte-identically on Py 3.13.18 and on Py 3.12.16 with the CI pins,
    so the difference is the machine, not Python: BLAS/SIMD reduction order is CPU-dependent and not a fingerprint input. Explains run 142's "seed"
    difference in `compare` (two runners). Rejected: (a) rounding health values in outputs — changes outputs, forces a
    golden regeneration (SOURCE.txt forbids it to make a test pass) and a src change; (b) regenerating golden in CI from
    the Gate-2 merge commit — doubles CI solves, weakens the fixed reference; (c) tolerance on all files — would hide
    real drift in decision outputs. Possible later hardening (not required): exactly rounded sums (`math.fsum`) for
    health diagnostics, which would make the values CPU-independent; it changes golden health values, so it needs its own
    item and owner yes. This narrows how Gate-2 C7 "byte-identical" is read (two health values only) → owner yes/no in
    the Gate-3 review.

2026-11-27 (formulation lead, G3-6 code-vs-spec trace, reports/gate-3-spec-trace.md)
51. Formulation F-0.3 **amendment 2** (rules/wording only; LP, duals, thresholds unchanged, version string stays `F-0.3`).
    (a) §7.4a.1: a `switches` key the code does not implement is a `DataError` whatever its value (incl. reserved
    later-gate keys); implemented at Gate 3: `tx.model`, `tx.dcpf_form`, `tx.ref_bus`, `scaling`; unknown `tolerances`
    keys and a non-string `tx.ref_bus` are `DataError`, not `TypeError` (G3-5 found `tx.dcpf_formm: ptdf` silently ran
    angle; this trace found `tx.losses: true` silently ignored). (b) §7.4a.6 `congestion_rent` per island-hour (was
    summed over islands per hour; residuals of two islands could cancel). Non-toy MW warn/fail split stays unbuilt for
    all four MW checks and is specified in Gate 4 (every Gate 3 case is a test system at 1e-6). (c) §7.4a.7: line
    $tol_\pi$ = max of the end buses' $tol_\pi$, line $tol_q$ = `tol_q_abs_mw` (the code's reading); $\mathcal M_i$ members
    must pass their class price check (code); `BLACKOUT` is **not** a marginal member (π = VOLL + μ^use is not a known
    cost; the F-0.3 text was wrong) and becomes a case-(c) bound π ≥ VOLL; storage bounds in case (c) deferred (interval
    only wider). (d) §4 "List cells": the Gate-2 code's join/order rules ratified (transport byte identity freezes them;
    "sorted" in §7.4a.7 for `setter_ids`/`binding_links` was not what the code writes); `island_id` integer, 0-based
    price island under `transport`, k of `ik` under `dcpf`. (e) §8.10: the fingerprint carries the **code's** version
    (`capex.FORMULATION_VERSION`, F-0.3 from Gate 3; §7.4a.9 already masks it in the golden test); `run.json` keeps the
    case's declared version. (f) §8.12: congestion rent per hour/year is read from `flows` (no table). Rejected: changing
    `setter_ids` to sorted order (breaks transport golden); keeping the fingerprint at F-0.2 (hides the formulation
    change; §7.4a.9 was written to let it differ). Code fixes: G3-6-fix2/fix3 in PLAN.md.
52. Owner (2026-11-27, live reply to the G3-6 questions, `reports/gate-3-spec-trace.md` §4): **yes to all four.**
    (1) Switch keys strict: a key the code does not implement is a `DataError` even at its default-off value (e.g.
    `reserves.enabled: false`), per DECISIONS 51(a). (2) Every run fingerprint, T1–T4 included, changes once as the code's
    `formulation_version` goes F-0.2 → F-0.3 (DECISIONS 51(e)); outputs stay byte-identical. (3) F3-3, F3-9, F3-12,
    F3-13 carried to Gate 4 (F3-9/F3-13 wait for the first `dcpf` case with storage if dcpf is not kept for Gate 4).
    (4) DECISIONS 50 / §8.10a accepted: Gate-2 C7 "byte-identical" reads with health `value` compared at 1e-12
    abs-or-rel, all other bytes exact. G3-7 records these as answered in the Gate 3 decision list.

2026-11-27 (formulation lead, G3-6-fix4 — spec ruling on an empty `tx.ref_bus` list)
53. Formulation F-0.3 **amendment 3** (load rule only; LP, outputs, fingerprint inputs unchanged, version string stays
    `F-0.3`): §7.4a.1 + data-schema rule 11 — `tx.ref_bus: []` is a `DataError` ("names no zone; omit the key for the
    default"); an entry that is not a zone id (incl. `""`) already was. The default reference rule (first zone of each
    island in `zones.csv` order) is asked for only by omitting the key; a non-empty list may still leave islands unnamed
    (they take the default). Reasons: (a) one spelling per meaning — absent and `[]` would be two `case.config` values,
    so two fingerprints (§7.4a.9 "absent stays absent") for the same LP; (b) consistent with the strict-key rule
    (DECISIONS 51(a)/52(1)): an empty list is more likely a script's empty selection than a request for the default.
    Rejected: `[]` = default (silent, and the fingerprint split). Effect: the strict xfail
    `test_loader_empty_ref_bus_list_is_rejected` in `tests/test_g3_fix3.py` is right as written (no verifier change);
    G3-6-fix5 builder makes the loader raise, verifier removes the xfail marker. Found by G3-6-fix3.

2026-11-27 (owner, live reply "Approve proceed" to reports/gate-3-review.md)
54. Owner answered **yes to all 10 Gate 3 review items**: (1) P5a–P5f within tolerance, LMPs matched at 0.01 (published row
    reproduced independently; Li & Bo table not read); (2) health checks, UNEXPLAINED = 0, CONGESTION_LOOP α correct; (3) M7–M10
    caught; (4) `transport` default and Gate 1 results unchanged; (5) §7.4a / F-0.3 amendments 1–3 accepted; (6) `pjm5` provenance
    accepted, licence `verify` = internal test use only, never shipped to clients; (7) `dcpf` kept as an option for Gate 4
    RTS-GMLC, `transport` stays default; (8) merge `gate-3` → `main`, Gate 3 DONE; (9) delete branch `g2-7b-broken-hash`;
    (10) markets notes (a)–(c) go into the Gate 4 criteria draft (P12), (d)–(f) are later-gate notes (PJM zonal gates).

2026-11-27 (owner, live reply "Approve all" to the P12 draft `docs/gates/gate-4.md`)
55. Owner **approved the Gate 4 criteria** (`docs/gates/gate-4.md`, drafted on `prep` as P12, copied to `gate-4` unchanged
    except its status line) and answered **yes to O1–O7**: (1) the 336-h PLEXOS DA window (p063–p067) is the Gate 4
    reference, full year for health/performance only; (2) a 73-bus nodal variant is the `dcpf` case; (3) S1 HVDC 113–316 as a
    controllable link, key absent = `controllable` (an A1 deviation), `exclude` = ablation; (4) LMPs reported, not judged,
    replacing benchmarks §6 "zonal price MAE ≤10%" for G4; (5) judge on the PLEXOS-aligned fleet (CSP, storage removed), storage
    checked by R4-NS and fixtures; (6) S2 storage interval conditional on the solved water value; (7) [P] tolerances C1 5%,
    G1 3 pp, budgets window ≤60 s, full year ≤5 min / 4 GB, R4-NF outside CI. Branch `gate-4` created from `gate-3`; the
    P11 architecture draft travels with it as an input (its own O1–O6 stay open). Spec changes S1–S5 land in G4-1 (F-0.4).

2026-11-27 (formulation lead, G4-1 W-spec, gate-4.md §3 S1–S5)
56. Formulation **F-0.4** (code `capex.FORMULATION_VERSION` F-0.3 → F-0.4; every fingerprint changes once, canonical outputs
    of T1–T4 and `pjm5` unchanged except one new `dcpf` health row, removed before the golden compare, §7.4a.9). Loader
    accepts F-0.2/F-0.3/F-0.4; the F-0.4 inputs (`links.link_type`, `tx.dc_links`, `audit_profile`) require `F-0.4`.
    (S1, §7.4a.12) Controllable DC link: `link_type` ∈ {`ac`, `dc`} (blank = `ac`); a `dc` row is a zero-cost `flow`
    column with bounds $-F^-\le f\le F^+$ (asymmetric allowed, 0 in either direction = `DataError`), injection pair in `bal`
    / `bal_sys` / `ptdf_flow` (hook H1), no `kvl` row; islands from AC lines only; $\mu_k=\pi_e-\pi_o$; rent identity per
    rent component (islands + all DC links); price-setter per price component (islands + DC links strictly inside limits)
    with free-DC rows in $\hat\Phi$; `link_inconsistent` evaluated on DC links. Switch `tx.dc_links` absent = `controllable`
    (owner's A1 deviation, DECISIONS 55(3)), `exclude` drops `dc` rows after validation (ids in `run.json`
    `excluded_links`); a `DataError` outside `dcpf`. Replaces §7.4a "no HVDC/transport links mixed with lines".
    (S2, §7.4a.7; closes F3-9/F3-13) Storage not in $\mathcal M_i$ adds idle / discharge-at-limit / charge-at-limit rows to
    the case-(c) interval LP at the solved $v$, relaxed by $tol_\pi$; solver status mapped to an enum (UNBOUNDED and
    UNBOUNDED_OR_INFEASIBLE → ±∞ after a feasibility pre-check of the solved point; anything else, or NaN, = failed solve);
    new check `price_setter.loop_interval` (count, pass 0). (S3, §3; closes F3-3) top-level `audit_profile` ∈ {`exact`
    (default), `standard`} for `balance`, `storage.soc_recompute`, `kvl.recompute`, `ptdf.recompute`; under `standard`
    the keys `bal_residual_mw`/`kvl_residual_mw` are `DataError`. (S4, §6.1; closes F3-12) general column/row unscaling
    rule; θ reduced cost and `ref_angle` use $k=1$. (S5) benchmarks §6 G4 row: 336-h window, LMPs reported.
    Details decided here (gate-4.md left them open): F-0.4 version gate on the new inputs (same pattern as dcpf ⇒ F-0.3);
    DC rating 0 in either direction is an error (no one-way links yet, avoids a link stuck at a bound at f = 0);
    `tx.dc_links` under `transport` is an error while `tx.dcpf_form`/`tx.ref_bus` stay "ignored" (F-0.3 behaviour kept,
    changing it would move fingerprints; harmonise if A1 is adopted); S2 rows relaxed by $tol_\pi$ so the solved point
    always passes; storage with $P\le tol_q$ and simultaneous charge/discharge add no row (interval only wider there);
    new health row kept even when vacuous (value 0) rather than emitted only when case (c) occurs.
    Rejected: S1 exclusion as default (drops a tie at its limit 96% of reference hours), a fixed 100 MW injection
    (reference reverses in 20 h), a DC link as an AC line with tiny reactance (wrong physics, conditioning); S2 full-dual
    interval with $v$ free (needs the whole storage dual system in the tiny LP; owner chose conditional, 55(6)); S3 a
    test-system flag inferred from provenance (`is_toy`) — implicit, and `pjm5` is observed data yet a test system.

2026-11-27 (formulation lead, G4-1 heat-rate choice; DECISIONS 38 P5 note)
57. Heat rate from a piecewise fuel curve (formulation §2.4): $HR_r$ = secant incremental rate $(F_N-F_0)/(P_N-P_0)$ over
    the operating range, or the full-load average $F_N/P_N$ when the curve is flat ($F_N\le F_0$, RTS nuclear); **no
    no-load term** before the UC gate (Gate 11); intercept kept as `x_noload_mmbtu_h`. Ratifies the RTS-GMLC converter
    (`cases/rts_gmlc/README.md`, cell provenance derived L1). Reasons: (a) the LP has one linear cost per unit and no
    commitment, so the price it can form is an incremental cost; the secant is the MW-width-weighted mean of the
    `HR_incr` segments, i.e. the best single incremental rate over the range; (b) zero new columns or rows; (c) the
    missing no-load cost is a separate, measured line (gate-4.md C2 basis gap, 4.9% in the window), not mixed into
    dispatch error. Rejected: full-load average heat rate (folds no-load fuel into MC, overstates marginal cost and
    prices, distorts merit order between units with different no-load shares); piecewise segments as separate columns
    (3× thermal columns; without Pmin/commitment the lowest segment is dispatchable from 0 MW, so the extra accuracy is
    spurious until UC); `HR_incr` of the last segment (overstates the price at partial load). Accuracy cost flagged in
    §2.4/§9: flatter intra-unit price steps; cost understated by no-load fuel.

2026-11-27 (builder, G4-4)
58. Window runs load (formulation §1.2 weight identity): when every period is `rep_kind = full_block` with $w_p=1$, the load
    check is $\sum_p w_p\le D_y/3$ instead of equality. Reason: the Gate 4 judged runs (R4-Z/C/N/NS, gate-4.md §2) and the
    B1 test restrict `rts_gmlc*` to p063–p067, which sums to 5 blocks, not 122; F-0.4 text required the identity with no
    exception, so those cases could not load. Every other case keeps the equality. Also (S4 implementation reading):
    `duals_raw` lists θ reduced-cost rows only where nonzero, so the pjm5 `duals_raw.csv` stays byte-identical; the
    `price_setter` cells `price_lo`/`price_hi` are `None` (empty in CSV) instead of NaN where no interval applies.
