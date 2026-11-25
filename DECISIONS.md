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
