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
