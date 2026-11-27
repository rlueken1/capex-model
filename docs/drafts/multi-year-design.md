# DRAFT: multi-year capacity expansion design (new gates after Gate 6)

Status: **DRAFT (formulation lead, 2026-11-26). Not approved and not part of `docs/formulation.md`.** Owner decision
2026-11-27: multi-year optimization gets its own gate(s) directly after Gate 6 (GenX cross-check). This file proposes
the math, data, tests and gate split. Once approved, the spec step of the first multi-year gate copies §1 into
formulation.md as new §7.0 under the next version string, with one DECISIONS entry.
Gate numbers below use the **proposed renumbering**: new Gates 7 and 8, so old 7–20 become 9–22 (owner decision O2).

## 1. Design

### 1.1 Sets and year weights
- Model years $\mathcal Y=\{y_1<\dots<y_N\}$ (config `my.years`, e.g. 2025, 2030, 2035, 2040). Model year $y_k$ stands for
  the calendar years $\tau\in S_k=\{y_k,\dots,y_k+\Delta_k-1\}$, with span $\Delta_k=y_{k+1}-y_k$. The last span $\Delta_N$ is set in config
  (`my.tail_years`, default $=\Delta_{N-1}$). The horizon ends at $T^{end}=y_N+\Delta_N-1$.
- Vintages $v\in\mathcal Y$: a build in model year $v$ comes online at the start of $v$. No build happens between model years.
- Representative periods $p\in\mathcal P_y$, hours $t=1..72$, weights $w_{y,p}$, with the per-year weight identity
  $\sum_p w_{y,p}=D_y/3$ (§1.2 rule applied per year; $D_y$ = days of that year's weather year).
- `my.mode=single` (ablation, and the default until this gate passes): $N=1$, $\Delta_1=1$, $\rho$ ignored, so $\omega=1$.
  The LP is then **identical** to the Gate 6 LP. This is the identity test T7a.

### 1.2 Real discounting (one more function in `capex/econ.py`)
One real system discount rate $\rho$ (`my.discount_rate`, real, Fisher-converted once per §5.1). Costs are discounted to
$y_1$ with an end-of-year convention, so calendar year $\tau$ gets $\text{DF}(\tau)=(1+\rho)^{-(\tau-y_1)}$. The year multiplier is
$$\omega_k=\sum_{\tau\in S_k}\text{DF}(\tau)=\text{DF}(y_k)\,\frac{1-(1+\rho)^{-\Delta_k}}{1-(1+\rho)^{-1}}\quad(\rho=0:\ \omega_k=\Delta_k).$$
This is `capex.econ.pv_factor(rho, start, span)`. It sits in the same module as `annualize`, and the static
"no annuity math elsewhere" check (§5.1) also covers it. $\rho$ (the system's time preference) is kept separate from
each technology's financing WACC $r$ inside `annualize` (§5.2, DECISIONS 22). This follows GenX multi-stage and ReEDS.
When $\rho=r$ and PFF $=1$, the present value of the annuities equals the overnight cost (test T7e).

### 1.3 Variables, capacity by vintage, cumulative accounting
- $x_{r,v}\ge0$ is new capacity of resource $r$ in vintage $v$ (storage: $x^P_{r,v}, x^E_{r,v}$), with bound $X^{max}_{r,v}$.
- Survival: $s_{r,v,y}=1$ if $y<v+L_r$ ($L_r$ = technical life, in years), else 0. A unit is available for the **whole span**
  of model year $y$ if it is alive at the start of $y$ (start-of-span rule; ⚠ lumpy, see §1.11).
- Capacity in year $y$ (an expression, not a variable):
  $$K_{r,y}=K^0_{r,y}+\sum_{v\le y}s_{r,v,y}\,x_{r,v}\;\big[-\textstyle\sum_{v\le y}\text{ret}_{r,v}\ \text{from Gate 12, permanent}\big].$$
  $K^0_{r,y}$ is the exogenous schedule of existing capacity, with announced and age-based retirements already
  applied (table `existing_by_year`). The same form holds for $P_{r,y}$ and $E_{r,y}$.
- Every Gate 1–6 row gets the index $y$ and uses $K_{r,y}$: `bal[z,y,p,t]`, `gen_max`, `st_pwr`, `st_soc`, `st_emax`, the
  Gate 5 `st_link*` rows per year, and `st_dur_lo/hi[r,v]` per vintage.
- **Dispatch is per resource, not per vintage.** Vintages differ in cost only; HR, VOM and η are the same for every vintage.
  This keeps the operational LP at $N\times$ the single-year size. A vintage whose performance differs a lot becomes a
  separate resource (data rule).
- `build_cum[r,y]` (optional, for resource potential such as VRE sites): $\sum_v s_{r,v,y}x_{r,v}\le X^{cum}_{r}$. Its dual is
  the scarcity rent of the site.

### 1.4 Objective (present value, base-year real $)
$$\min Z=\sum_{r,v}\Big[\sum_{\tau=v}^{\min(v+n_r-1,\,T^{end})}\text{DF}(\tau)\,a_{r,v}+\sum_{k}\omega_k\,s_{r,v,y_k}FOM_{r,y_k}\Big]x_{r,v}
+\sum_k\omega_k\big(Z^{var}_{y_k}+Z^{use}_{y_k}\big)\;\big[+\textstyle\sum_k\omega_k Z^0_{y_k}\ \text{constant}\big]$$
- $a_{r,v}=\text{ANN}(I_{r,v})$ uses the **single annualization function** with the vintage's overnight cost $I_{r,v}$ (ATB
  trajectory). It is paid for the $n_r$ years of economic life, counted per calendar year, so it is exact even when the
  life ends in the middle of a span. $Z^{var}_y, Z^{use}_y$ are the Gate 1–6 annual expressions with year-$y$ data
  ($MC_{r,y,p,t}$ from the fuel path of that year).
- **End of horizon (`my.eoh=truncate`, default):** annuities after $T^{end}$ are not counted. When $\rho=r$, this equals
  charging the overnight cost minus a salvage value equal to the present value of the remaining annuities (Short et al. 2011, ReEDS;
  GenX multi-stage). `my.eoh=perpetuity` is an option: the last span runs to infinity, $\omega_N=\text{DF}(y_N)(1+\rho)/\rho$, as a
  steady-state tail. ⚠ Builds in the last 1–2 model years are always distorted. Report results only up to $y_{N-1}$, or add
  one model year beyond the study horizon (recommendation O3).

### 1.5 Economic life and end-of-life
$n_r$ (economic life, used in `annualize`) and $L_r$ (technical life, survival) are separate fields. The default is
$L_r=n_r$ (ATB). At end of life the capacity drops out of $K_{r,y}$. Replacement happens only through a new vintage
$x_{r,v'}$ (endogenous rebuild). Existing units retire by age: retirement year = online year (EIA-860) + $L_r$, unless an
announced date comes first.

### 1.6 Foresight: `my.foresight ∈ {perfect (default), myopic, rolling(k)}`
- `perfect`: one LP over all of $\mathcal Y$.
- `rolling(k)`: solve the window $\{y_j..y_{j+k-1}\}$, fix the vintages $x_{\cdot,y_j}$, move one step, repeat. Earlier vintages
  enter as fixed capacity. Their annuities are sunk: they go into the reported total and are left out of the LP.
  Inside a window, `truncate` applies at the window end. `myopic` is `rolling(1)`.
- Same LP builder, a loop over year subsets. A rolling run has one fingerprint per window plus one for the chain.

### 1.7 Representative periods per model year (interplay with Gate 5)
- Default `my.ts=shared`: one Gate 5 clustering on the weather/base year. The same medoid blocks and the same `block_map`
  are used for every $y$. Only the data change by year: load scaled per zone and year (energy and peak growth, §2),
  the year's fuel path, and the year's VRE fleet.
- `my.ts=per_year` (Gate 8 option): cluster again for each $y$, using that year's load and the net load at the year's
  **exogenous** fleet. Weights and forced periods come from the Gate 5 rules per year.
- ⚠ Fixed periods with growing VRE: the net-load peak moves (to winter evenings in PJM), so the forced periods chosen in
  the base year can miss scarcity in later years. This is the main accuracy risk; the Gate 8 ledger row measures it.

### 1.8 Storage across years: none
Each model year is year-cyclic on its own: Gate 5 `st_link` runs with $B_{r,y,J+1}=B_{r,y,1}$, and no state passes
between years. New health check `storage.no_interyear` confirms no row couples SOC across $y$.

### 1.9 Duals per year
Every operational dual is scaled by $\omega_y w_{y,p}$ in the objective, so
$$\pi_{z,y,p,t}=S\cdot y^{bal}_{z,y,p,t}/(\omega_y\,w_{y,p})\quad[\$/\text{MWh real }B,\ \text{undiscounted, in year }y].$$
The same rule applies to `gen_max` ($\mu$), the storage rows, and later `res_req`, `rps` (annual rows: divide by $\omega_y$ only)
and RPM. Annual rent $R_{r,y}=\sum_p w_{y,p}\sum_t A\,\mu$ is in $/MW-yr.
**Zero profit per vintage (PV over life inside the horizon).** If $x_{r,v}>0$:
$\sum_k\omega_k s_{r,v,y_k}(R_{r,y_k}-FOM_{r,y_k})=\sum_{\tau=v}^{\min(v+n_r-1,T^{end})}\text{DF}(\tau)a_{r,v}$.
If $x_{r,v}=0$, the left side is $\le$ the right side. This does **not** hold year by year: a vintage can earn below its
cost early and above it later. Per-year rents of a vintage that is alive in several years are pinned only when later
vintages also build. Otherwise they are non-unique across years, so per-year capacity rents are scored on averages
(extends DECISIONS 23).

### 1.10 Price-setter and health-check extensions
- The price-setter algorithm (§4) runs per $y$ on the unscaled per-year $\pi$, unchanged, with `UNEXPLAINED` counted per
  year. `CAPACITY_RENT` hours carry the vintage set whose PV zero-profit row they belong to.
- New checks: (a) weight identity per year; (b) $\omega$ recompute from `pv_factor` against a closed form, rel $10^{-12}$;
  (c) capacity accounting $K_{r,y}=K^0_{r,y}+\sum s\,x$ against an independent recompute from `builds.csv` (by vintage) and
  the case lives; (d) PV zero-profit per vintage, rel $10^{-6}$; (e) objective decomposition by year, both undiscounted and
  PV, summing to $Z$; (f) `storage.no_interyear`; (g) for rolling runs, chain consistency (fixed vintages equal the
  window solutions) and a regret report $Z^{myopic}-Z^{perfect}$ evaluated under perfect-foresight accounting.
- New outputs: `builds.csv` $(r,v,x)$, `capacity_by_year.csv`, `prices_by_year`, `pv_cost_by_year.csv`.

### 1.11 Scaling and conditioning
$\omega_k\in[\text{DF}(T^{end}),\Delta_k]$, about 0.1 to 10 for $\rho\le8\%$, horizons ≤ 40 years and $\Delta\le10$. This multiplies the
§6.1 objective ranges by at most 10: $\omega w\,\text{VOLL}\le4\times10^3$, still inside the warn limits. A perpetuity tail adds
up to $1/\rho\approx15$. Rule: $\omega$ goes into the objective only, never into rows (like $w$). Optional $s_{obj}=1/\sum_k\omega_k$, which
makes the objective an "average annual" figure; it is divided out in the audit. New conditioning metric `my.omega_ratio`
(warn $>10^2$). LP size grows linearly in $N$ (default $N\le5$). Within each year the rows stay block-diagonal, linked only
through the $x_{r,v}$ columns, so they are sparse.

**Accuracy flags.** (1) Backcasts run with a fixed fleet per year, so multi-year **does not move the backcast scoreboard**.
The gates are judged on known answers and the cross-check (O10). (2) Perfect foresight anticipates cost declines and load
growth, so it builds later and leaner than real developers. (3) $\rho$ largely decides build timing, so the result must be
reported with a sensitivity to $\rho$. (4) Performance is the same for every vintage, which ignores ATB heat-rate gains (small).
(5) Capacity availability follows the start-of-span rule.

## 2. Data needs (all free; every value with source_id, vintage, method, basis, confidence)
| Need | Source (`source_id`) | Method / note |
|---|---|---|
| Overnight capex, FOM, VOM by tech × year (Moderate, plus Advanced/Conservative as sensitivities) | NREL ATB (`atb`, existing) | observed (ATB projection), dollar year from ATB, deflated per §5.1 |
| Economic life $n$, WACC/PFF inputs by year | `atb` | observed. Technical life $L$: literature default (EIA/ReEDS docs), `method=assumed` with citation |
| Fuel price paths (Henry Hub, coal, oil, uranium), real | EIA AEO Reference case (`aeo`, existing) | observed projection. Regional basis held at the latest observed monthly basis (DECISIONS 27), `method=estimated` |
| PJM load growth by zone (energy, summer/winter peak, large loads) | PJM Load Forecast Report, annual, free PDF/xlsx (**new** `pjm_ltlf`) | observed forecast. Fallback: AEO EMM PJM-region demand growth |
| Existing-fleet online year, planned retirements | EIA-860 (`eia860`, existing) | observed. A missing online year uses the data-sources.md hierarchy (plant-level, then cohort median) |
| RTS-GMLC / toy growth and cost paths | none upstream | `method=assumed`: e.g. load +1.5 %/yr, ATB trajectories mapped by tech; the assumptions book shows the banner |
| GenX multi-stage example inputs | `genx_examples` (existing; verify that a multi-stage 3-zone example exists at the pinned release) | observed (test system) |
All projections go through the Gate 18 versioned pipeline later. For Gates 7–8, small CSVs live under `cases/` with provenance.

## 3. Known-answer tests (verifier; closed forms computed independently of `capex` model code)
One zone, flat demand, one period type, $w=121.\overline6$, VOLL 10,000 (non-binding), $H=8760$ unless stated, FOM 0.
| Id | Setup | Must reproduce |
|---|---|---|
| T7a identity | any Gate 1–6 case, `my.mode=single`; also $N=1$ with any $\rho$ and $\Delta=1$ | LP byte-identical to the single-year LP (fingerprint differs only in `my.*`); $Z$ bit-identical |
| T7b build timing | $D_y=100,120,140$ MW at $y=0,5,10$ ($\Delta=5$); existing gas 100 MW; candidate peaker $a$, MC $m$, $L=n\ge15$; $\rho=5\%$ | just-in-time: $x_{0}=0,x_{5}=20,x_{10}=20$; $Z$ closed form; $R_{y}$ per MW equals the PV-consistent annuity (unique here because vintage 10 pins year 10); PV zero-profit per vintage |
| T7c end-of-life rebuild | $D=100$ all years, $L=n=5$, $\Delta=5$, $N=3$ | $x_v=100$ in every vintage; $K_y=100$; capacity check (c) passes |
| T7d discount tie | need starts at $y_2$ only; $a_{v1}<a_{v2}$ (cost escalation); $\rho^*$ solves $\omega_1a_1=(\omega_2+\omega_3)(a_2-a_1)$ | at $\rho^*$: fixing either the early or the late build gives the same $Z$ (rel $10^{-9}$); at $\rho^*\pm0.5\%$: late / early build is the unique optimum |
| T7e PV equivalence | $\rho=r$, PFF $=\kappa=1$; life inside the horizon, then life past it | coefficient on $x_{r,v}$ $=I\,\text{DF}(v)$ exactly; with truncation $=I\,\text{DF}(v)-\text{PV(remaining annuities)}$ |
| T7f myopic vs perfect | $\rho=0$, $\Delta=1$, $N=2$, $D=100$ flat. G: $a=60$k/MW-yr, $L=n=2$, MC 30. T: $a=80$k, $L=n=1$, MC 30. N: only $v=2$, $a=50$k, MC 0 | perfect: T then N, $Z_{PF}$; myopic: G then N (G stranded in $y_2$); $Z_{my}-Z_{PF}=4.0$ M$ exactly; regret report equals it |
| T7g duals | T7b with $\rho=7\%$, scaled and unscaled solves | $\pi=S\,y/(\omega w)$ matches the per-year MC/rent closed form; health checks (a)–(f) pass |
| T7h no inter-year storage | Gate 5 T5a storage in a 2-year case, A blocks in $y_1$ and B blocks in $y_2$ | storage cannot move energy from $y_1$ to $y_2$: $Z$ = sum of the two single-year optima |

## 4. Gate split decision: **two gates**
| # | Gate | Core exit evidence |
|---|------|--------------------|
| 7 | Multi-year expansion core (perfect foresight) | model-year set + $\omega$ weights, real discounting (`pv_factor`), vintages, lives/end-of-life, truncated end-of-horizon; T7a–T7e, T7g, T7h exact; `my.mode=single` reproduces Gate 6 LP; RTS-GMLC 3+1 model years (shared periods) passes all health checks incl. PV zero-profit per vintage and per-year `UNEXPLAINED`=0; ledger row `my.mode` |
| 8 | Foresight modes + per-year periods + GenX multi-stage cross-check | `my.foresight` myopic/rolling (T7f exact, regret report); `my.ts=per_year` vs `shared` against a `full_blocks` multi-year RTS-GMLC reference (ledger decides default); GenX multi-stage 3-zone example: PV cost, capacity by stage/zone, per-stage prices compared, differences explained; ledger rows `my.foresight`, `my.ts`, `my.eoh` |

Why two. One gate would add three features (vintaged accounting, foresight modes, re-clustering) and a cross-check at
once, which breaks the simplest-first rule (DECISIONS 26). Vintages plus discounting with perfect foresight is the
smallest complete multi-year model, and its known answers fully define it. Myopic/rolling and per-year periods are
variants of a working core, so they share Gate 8. Three gates would spend a full owner review on the foresight loop,
which is about 100 lines and reuses the core LP. The GenX multi-stage cross-check belongs in **Gate 8**: GenX reports
both perfect-foresight and myopic stages, so both modes must exist first. Gate 7 runs on toys and RTS-GMLC (`rts_gmlc_x`
from Gate 5). Gate 8 runs on toys, RTS-GMLC and the GenX example. No PJM data is used in either.

## 5. Impacts on later gates (new numbers; old number in brackets)
- **9 [7] Reserves/ORDC**: requirements and ORDC steps by year; reserve price $=S\,y/(\omega_y w)$; ledger tests in a multi-year run.
- **10 [8] Transmission**: line expansion $y_{l,v}$ by vintage with lives and annuities via `annualize`/`pv_factor`; existing NTC by year.
- **11 [9] Clustered UC**: commitment bound uses $K_{r,y}$; cluster unit size fixed across vintages; per-year rows only.
- **12 [10] Policy/build/retire**: RPS/CES targets $\kappa_{s,y}$ and RGGI caps by year (banking would be the first legal inter-year
  link, behind a separate switch); PTC/ITC by **in-service vintage**, and a 10-year PTC needs vintage-resolved dispatch for
  credit cohorts (cohort = separate resource); build limits per year plus cumulative; economic retirement $\text{ret}_{r,v}$
  permanent and cumulative, compared on PV going-forward cost; announced retirements mapped to model years.
- **13–15 [11–13] PJM one zone / scoreboard / single node**: backcasts stay fixed-fleet per year (one LP per year, or
  `my.foresight` off). Forward runs use multi-year. The scoreboard is unchanged.
- **16 [14] Capacity market**: VRR curve and ELCC by delivery year (ELCC falls with penetration); RPM rents enter the PV zero-profit per vintage.
- **17 [15] Storage value study**: report storage value trajectories by year and vintage (a direct gain from these gates).
- **18 [16] Data pipeline**: versioned ATB/AEO/`pjm_ltlf` trajectories and EIA-860 online years.
- **19 [17] Calibration**: the hold-out stays per year. Optional multi-year backcast with observed builds fixed, as a realism check of build timing.
- **20 [18] PJM zonal**: drop "multi-year" from the name. It becomes "PJM zonal at N model years" with a runtime target for $N\times$ size.

## 6. Open owner decisions (yes/no; recommendation in brackets)
1. O1 Two multi-year gates (7 core with perfect foresight; 8 foresight modes + per-year periods + GenX multi-stage)? **[yes]**
2. O2 Renumber old Gates 7–20 as 9–22 (one DECISIONS line with the old→new map; a one-pass rename in formulation §7 and the drafts), instead of labels 6a/6b? **[yes]**
3. O3 Default model years: 5-year steps, plus one extra model year past the study horizon to absorb end effects; tail = `truncate`? **[yes]**
4. O4 One real system discount rate $\rho$ in the objective, separate from each technology's WACC in `annualize`; default $\rho$ = ATB real WACC of the reference class, with $\pm2$ pt sensitivity reported? **[yes]**
5. O5 End of horizon by truncated annuities (implicit salvage), with no explicit salvage term? **[yes]**
6. O6 Gate 7 uses the same representative periods for all years; per-year re-clustering is only a Gate 8 option that must earn its ledger row? **[yes]**
7. O7 No inter-year storage (each model year year-cyclic)? **[yes]**
8. O8 Cost varies by vintage, performance does not (separate resource where it differs a lot)? **[yes]**
9. O9 Perfect foresight is the default; myopic/rolling are for comparison and regret reporting? **[yes]**
10. O10 These gates are judged on known answers + health checks + GenX cross-check, not on backcast improvement (the scoreboard must only stay unchanged)? **[yes]**
11. O11 Add `pjm_ltlf` (PJM Load Forecast Report, free) to the source registry for PJM load growth? **[yes]**
12. O12 Technical life = economic life by default, with the start-of-span availability rule? **[yes]**

### References
Kotzur, Markewitz, Robinius, Stolten (2018), *Applied Energy* 213 (inter-period storage, used per year unchanged).
Short et al. (2011), *ReEDS model documentation*, NREL/TP-6A20-46534 (evaluation period, end effects).
Lara, Mallapragada, Papageorgiou, Venkatesh, Grossmann (2018), *EJOR* 271(3) (multi-period expansion, nested decomposition; GenX multi-stage basis).
Poncelet, Delarue, Six, D'haeseleer (2016), *Applied Energy* 162 (temporal vs techno-economic detail trade-offs).
Heuberger, Staffell, Shah, Mac Dowell (2017), *Comput. Chem. Eng.* 107 (myopic vs perfect foresight in expansion).
