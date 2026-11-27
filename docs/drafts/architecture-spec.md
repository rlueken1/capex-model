# DRAFT — Architecture spec: feature-block contract, `ra.prm`, weighted rep-period price duration curve

Status: **DRAFT (prep item P11, 2026-11-27) — not approved, not part of `docs/formulation.md`.** Owner approves or
amends at a gate boundary; the formulation lead then copies §A into formulation §0 (new), §B into §7 (Gate 7 sketch →
full spec at the Gate 7 W-spec step) and §C into formulation §7.1.7 / benchmarks.md §2, under the next version string
with one DECISIONS entry each (proposed texts in §D).
Implements DECISIONS 44(c)(e) as amended by 45: **no operations mode**; capacity expansion and prices both come from
weighted representative 3-day periods (DECISIONS 3); the full-year fixed-fleet dispatch is a one-off check of period
selection only. Notation, units, signs and dual conventions: formulation F-0.3 §1, §3 (on `gate-3`). Scaling: §6.
**Gate numbers are the NEW numbers of DECISIONS 43** (Gate 7 multi-year core + PRM, 9 reserves/ORDC, 10 zonal
transmission, 11 UC, 12 policy + build/retire, 14 scoreboard v0, 16 capacity market). Formulation §7 headings and
benchmarks.md still use OLD numbers (ORDC "G7" = new 9; scoreboard "G12" = new 14; RPM "G14" = new 16); §D lists the
renumbering edit.

---

## A. Feature-block contract (proposed formulation §0)

Every modelling feature after Gate 1 is **one block**. A block is accepted into a gate only if it supplies all ten
items below; the gate review checks the list item by item. The Gate 1 core (`x, xP, xE, g, ch, dis, soc, flow, use`;
`bal, gen_max, st_*`) is block 0 and is always on. `tx.model = dcpf` (Gate 3) is the reference implementation of the
contract (it already has items A1–A9; A10 is its §7.4a.9 transport identity).

| # | Item | Rule |
|---|---|---|
| A1 | **Switch** | One config key `<family>.<name>` in `case.yaml → switches`, added to the loader allowlist (`capex.data.SWITCH_KEYS`) in the same commit. Its **off value is the default** unless a DECISIONS entry says otherwise (e.g. `tx.model` default `transport` = its off value). Unknown keys and values stay load errors (F-0.3 amendment 2). Sub-switches (`uc.ramps`) are valid only when the parent is on; otherwise a load error. |
| A2 | **Inputs** | Each input table/column the block reads is listed in data-schema.md with provenance columns (`source_id, vintage, method, basis, confidence`). Required **only when on**; when on, a missing value is a load error (never a silent default; estimation hierarchy of data-sources.md applies upstream). When off, the block's tables are **not read and not hashed**; their presence is noted only in `run.json` (non-canonical), so an off block cannot change any canonical output. |
| A3 | **Variables** | Column families with label, index dims, bounds, unit (I/O and scaled), as in formulation §2.1. Columns are **appended after all earlier blocks' columns** in the fixed block registry order (gate order), so switching a block off leaves every earlier block's offsets unchanged. |
| A4 | **Rows** | Row families with label, dims, sense, RHS, unit; appended after earlier rows, same rule. Each row family declares its **weight divisor** $W$: hourly rows $W = w_p$ (× $\omega_y$ from Gate 7), annual rows $W = 1$ (× $\omega_y$). A block may touch earlier blocks only through three declared **coupling hooks**: (H1) an injection term in `bal`/`bal_sys` (or a reserve requirement row from Gate 9), (H2) a term in a capacity expression $K_r, P_r, E_r$ (e.g. retirement), (H3) an objective term. Any other cross-block coefficient is a spec violation. |
| A5 | **Objective** | Each cost term with its weight ($w_p$, $\omega_y$) and its line in the objective decomposition (§8.4); decomposition still sums to $Z$ within $10^{-9}$ rel. |
| A6 | **Duals** | One row per row/bound family in the §3 table: raw sign (minimization), economic quantity, conversion ($y\cdot S/W$), unit, and the stationarity relation it changes (e.g. $s_x$ for PRM, §B4). Strong duality and complementary slackness (§3 checks 2–4) cover the block's rows automatically; the block lists any new RHS terms. |
| A7 | **Health checks** | At least one **recompute-from-case-data** check (the §3 check 8 principle: recompute the block's rows from the loaded case data and the unscaled primal, never from matrix coefficients), with `check_id`, family, warn/fail thresholds, and toy/random tolerance. Plus any identity the block's duals must satisfy (e.g. zero profit with capacity revenue). |
| A8 | **Price-setter** | Either a new hourly class (name, condition, price check, setter cost, residual, position in the §4 class order) or an explicit statement "**no hourly class; hourly classes unchanged**" with the reason; plus, for annual rows, an annual setter report (§B5 is the pattern). `UNEXPLAINED` must stay 0. |
| A9 | **Audit, outputs, mutation** | Output tables (data-schema §5 entry, key columns, sort order), audit hook entry (§8), and at least one **mutation hook** `M<n>` (a deliberate code defect that A7 or A10 must catch; verifier writes the test, as M1–M10). |
| A10 | **Ablation identity test** | With the switch **off**, on every case of the previous gate's golden set (T1–T4 and `pjm5` now; plus RTS-GMLC from Gate 4): canonical outputs are identical to the stored golden outputs under the §8.10a rule, with fingerprint, `formulation_version` and git fields masked (the §7.4a.9 procedure, generalised). Golden set is refreshed only at a gate boundary, from the approved branch. Optional **inert test**: block on, parameters chosen so it cannot bind (e.g. requirement 0) → objective equal within $10^{-9}$ rel and weighted block-average prices equal within $tol_\pi$; vertex-level identity is not required (degenerate LPs may return another vertex). |

Bookkeeping that is not part of the LP but is part of acceptance: one `reports/complexity-ledger.md` row (Δ error,
Δ size, Δ time, Δ client answers; keep / default-off / drop) and one `reports/performance-ledger.md` row (rows, cols,
nnz, solve time, peak memory vs previous gate; >2× growth needs a reason). The fingerprint already covers switches
(§8.10: config incl. all switches), so no new fingerprint field is needed.

Code shape (non-normative, for the builder): one module per block exposing `enabled(case)`, `layout(cols, rows)`,
`matrix_parts`, `costs`, `bounds`, `hooks` (H1–H3 terms), `duals`, `health`, `price_setter`, `outputs`; `build_lp`
loops over the registry in gate order. The Gate 3 network code is refactored into this shape only if the refactor
keeps A10 green (no behaviour change); it is not required.

---

## B. Planning reserve margin `ra.prm` (Gate 7; proposed formulation §7.9)

### B1 Switch, scope, simplest first
- Switch `ra.prm ∈ {off (default), on}`. Off ⇒ Gate 6 LP exactly (A10).
- Gate 7 scope: **one PRM area per model year, the whole system** (all zones). Nested areas (PJM LDAs with CETL import
  limits) are Gate 16 work with the VRR curve, which replaces this hard row (`ra.mode ∈ {prm, vrr}` then). No
  capacity-import credit, no FRR carve-out, no unit-specific performance adjustment, no endogenous (declining) ELCC.
- Hard requirement, no shortfall slack (a slack with a penalty is a demand curve, i.e. Gate 16). Feasibility is
  checked **before** the solve (B6, `prm.precheck`), so an infeasible case fails with the deficit in MW, not a solver status.

### B2 Sets and parameters (per model year $y$; one year until multi-year is on)
| Symbol | Meaning | Unit | Source / rule |
|---|---|---|---|
| $c(r)$ | ELCC class of resource $r$ (`resources.csv` column `elcc_class`) | – | required for every resource when on |
| $\varepsilon_{c,y}\in[0,1]$ | class ELCC rating, share of ICAP (`elcc.csv`: `class, year, elcc` + provenance) | – | PJM class ratings (pjm-rpm-notes §3.2) for PJM; assumed values flagged for test systems |
| $\hat D_y$ | forecast coincident peak load of the area (`ra_requirement.csv`) | MW | PJM 50/50 forecast peak for PJM. Test systems: max hourly system load of the **full-year input data** (not of the rep periods), `method = derived` |
| $m_y$ | installed reserve margin, IRM | – | PJM IRM per delivery year (pjm-rpm-notes §2.4); test systems `assumed` |
| $\mathrm{Req}_y = \hat D_y(1+m_y)\,\bar\varepsilon_y$ | requirement in accredited (UCAP) MW; $\bar\varepsilon_y$ = pool-wide accredited UCAP factor, so $\mathrm{Req}_y = \hat D_y\cdot\mathrm{FPR}_y$ for PJM | MW UCAP | Default $\bar\varepsilon_y = 1$ (requirement stated in ICAP-equivalent, i.e. "ELCC × capacity ≥ peak × (1+IRM)" as DECISIONS 44(c) words it). PJM runs set $\bar\varepsilon_y$ so that Req matches the published reliability requirement (pjm-rpm-notes §2.4: 164,579 × 0.926 = 152,400 MW for 2027/28) — owner question O1 |

ICAP basis: thermal = $K_r$ (summer net capability, as loaded); VRE = nameplate $K_r$; storage = discharge power
$P_r$. The ELCC rating already contains outage and weather risk; it is independent of the hourly availability
$A_{r,p,t}$ used in dispatch (no double counting: $A$ is energy-side only).

**Storage duration class.** PJM rates storage by duration class (4/6/8/10 h). Existing storage: class from
$E^0_r/P^0_r$ **rounded down** to the nearest class (never over-accredits; pjm-rpm-notes §6.4 said "nearest" —
owner question O2). Candidate storage under `ra.prm = on` must have **fixed duration** ($\underline\delta_r=\overline\delta_r$),
one candidate row per duration class; a candidate with a free $E/P$ ratio is a load error when `ra.prm` is on.
Reason: accreditation that depends on $E/P$ is a min/step function and would need either binaries or a
multi-segment construction for one Gate 7 row; fixed-duration candidates keep the row linear and exact.

### B3 Row
Accredited capacity expression (uses the capacity expressions of §2.2, so H2 terms such as retirement enter automatically):
$$\mathrm{UCAP}_y = \sum_{r\in\mathcal R^{TH}\cup\mathcal R^{VRE}} \varepsilon_{c(r),y}\,K_{r,y} + \sum_{r\in\mathcal R^{ST}} \varepsilon_{c(r),y}\,P_{r,y}$$
**`prm[y]`** ($\ge$; RHS in MW UCAP):
$$\sum_{r\notin\mathcal R^{ST}} \varepsilon_{c(r),y}\,x_{r} + \sum_{r\in\mathcal R^{ST}} \varepsilon_{c(r),y}\,x^P_{r} \;\ge\; \mathrm{Req}_y - \sum_{r\notin\mathcal R^{ST}}\varepsilon_{c(r),y}K^0_r - \sum_{r\in\mathcal R^{ST}}\varepsilon_{c(r),y}P^0_r$$
(multi-year: $x$ summed over vintages alive in $y$, $K^0$ as surviving in $y$, per docs/drafts/multi-year-design.md §1.3).
One row per year; weight divisor $W = 1$ ($\omega_y$ under multi-year). Scaled like every MW row ($k_P$); its dual
unscales with $S$ like the others; coefficients $\varepsilon\in[0,1]$ add no new magnitude to the §6.2 ranges.
No new variables. Size cost: $N_y$ rows and at most $|\mathcal R^{cand}|\cdot N_y$ nonzeros — negligible.

### B4 Dual, stationarity, zero profit
| Row | Raw sign | Economic quantity | Conversion | Unit |
|---|---|---|---|---|
| `prm[y]` | $\ge 0$ | capacity shadow price per accredited MW, $\kappa_y$ | $\kappa_y = S\,\tilde y/\omega_y$ ($\omega_y=1$ single-year) | $/MW-yr (UCAP) |
Also reported as $\kappa_y/D_y$ $/MW-day UCAP (the RPM unit; the delivery-year vs calendar-year mismatch is
pjm-rpm-notes §6.7 and stays a Gate 16 topic).
Stationarity changes (all others unchanged):
- $x_r$: $s_x = C^{fix}_r - R_r - \varepsilon_{c(r)}\kappa$.
- $x^P_r$: $s_{xP} = C^P_r - R^P_r - \varepsilon_{c(r)}\kappa + \underline\delta_r y^{lo} + \overline\delta_r y^{hi}$; $s_{xE}$ unchanged.
Zero-profit check (§3 check 5) becomes, for interior candidates, $|R_r + \varepsilon_{c(r)}\kappa - C^{fix}_r|\le 10^{-6}C^{fix}_r$
(storage, fixed duration $\delta$: $(C^P+\delta C^E) = R^P+\delta R^E+\varepsilon\kappa$); at $x=0$: $\le$; at $X^{max}$: $\ge$.
Revenue identity (§3 check 6) is unchanged for energy; the rent table (§8.5) gains columns `ucap_mw`
($\varepsilon K$ or $\varepsilon P$), `cap_rev` ($\varepsilon\kappa K$, $/yr), and `profit` includes `cap_rev`.
Existing resources earn `cap_rev` too (reported; it enters going-forward economics once `retire.economic` is on, Gate 12).
Strong duality: the row adds $\mathrm{RHS}\cdot y$ to $Z^{dual}$ (RHS includes the existing-fleet credit above).
Economic reading: $\kappa$ is the **net CONE of the marginal accredited MW**: $\kappa = (C^{fix}_r - R_r)/\varepsilon_{c(r)}$
for any interior candidate. Energy prices in scarcity hours fall by the "missing money" now paid through $\kappa$
(T5 below: annual mean price 31.42 → 25.00 $/MWh).

### B5 Price-setter
**No hourly class; hourly classes unchanged.** The row has no hourly index, so no hourly stationarity changes; every
§4 condition and price check stays as is. Only the *reading* of sub-tag `INVESTMENT_MARGIN` changes: with `prm`
binding, the hourly prices of a `CAPACITY_RENT` hour recover capex **net of** $\varepsilon\kappa$. This is stated in
the price-setter report header when `ra.prm` is on.
**Annual capacity price-setter** (`capacity_price.csv`, one row per area-year), classes in this order:
| Class | Condition | Price check / reported value |
|---|---|---|
| `PRM_SLACK` | $\mathrm{UCAP}_y - \mathrm{Req}_y > tol_q$ | $\kappa\le tol_\kappa$ |
| `PRM_MARGINAL_BUILD` | binding; some candidate with $0<x<X^{max}$ (interior by $tol_q$) and $\varepsilon>0$ | $\lvert\kappa - (C^{fix}_r - R_r)/\varepsilon_{c(r)}\rvert\le tol_\kappa$ for each such $r$; setters = all of them. Sub-tag `DEGENERATE` when every setter with $R_r>0$ earns it only in hours of class `CAPACITY_RENT`/`DEGENERATE` and no setter has $R_r=0$ with no at-cap hour: then the energy/capacity split of its rent is not unique ($R_r+\varepsilon\kappa=C^{fix}_r$ holds on a whole interval), and $[\kappa^{lo},\kappa^{hi}]$ as in the next row is reported |
| `PRM_MARGINAL_RETIRE` (Gate 12) | binding; an existing unit with interior retirement | $\lvert\kappa-(GFC_r-R_r)/\varepsilon\rvert\le tol_\kappa$ |
| `PRM_DEGENERATE` | binding, none of the above (requirement met exactly by existing + at-bound builds) | $\kappa\in[\kappa^{lo},\kappa^{hi}]$: $\kappa^{lo}=\max(0,\max_{x_r>0}(C^{fix}_r-R_r)/\varepsilon)$ over at-$X^{max}$ builds, $\kappa^{hi}=\min_{x_r=0,\varepsilon>0}(C^{fix}_r-R_r)/\varepsilon$; any value is optimal; interval reported |
| `UNEXPLAINED` | no class or failed check | health check: count must be 0 |
$tol_\kappa=\max(1\ \$/\text{MW-yr},10^{-6}\kappa)$. Columns: `area, year, kappa_mw_yr, kappa_mw_day, class, setter_ids,
kappa_lo, kappa_hi, req_mw, ucap_mw, slack_mw` plus `ucap_by_class` in `capacity_mix.csv` (`area, year, class, icap_mw, ucap_mw`).
Note $R_r$ (energy rents) is itself an interval when hourly duals are degenerate, so the `PRM_DEGENERATE` interval
is reported as computed at the returned vertex (as `price_lo/hi` for `CAPACITY_RENT`).

### B6 Health checks, outputs, mutation hook, identity
- `prm.precheck` (load time, case data only): $\sum_r\varepsilon(K^0+X^{max})\ge\mathrm{Req}$ (unbounded candidates pass);
  fail = `DataError` naming the deficit in MW.
- `prm.recompute`: from **case data** ($\varepsilon$ via `elcc_class` × `elcc.csv`, $\hat D$, $m$, $\bar\varepsilon$, $K^0$, $P^0$)
  and the unscaled primal, recompute $\mathrm{UCAP}_y-\mathrm{Req}_y$; must be $\ge -tol$ (toy $10^{-6}$ MW, else §6.2
  `bal` thresholds); and $\kappa\cdot(\mathrm{UCAP}-\mathrm{Req})\le$ CS tolerance.
- `prm.zero_profit`: B4 identity per candidate (folds into §3 check 5).
- `capacity_price.unexplained` = 0.
- Mutation hook **M11**: storage accredited on $E$ instead of $P$ (or $\varepsilon$ looked up by the wrong year) —
  `prm.recompute` must fail; **M12**: RHS omits the existing-fleet credit — `prm.recompute` and zero profit must fail.
- A10: `ra.prm` off ⇒ golden identity. Inert test: $m_y$ such that $\mathrm{Req}\le$ existing UCAP → `PRM_SLACK`,
  objective equal to off run within $10^{-9}$ rel.

### B7 Known-answer toy T5 (for the verifier; closed form)
One zone, one period, $w=121.\overline 6$ ($H=8760$), flat load $D=100$ MW, VOLL 10,000 $/MWh, no existing fleet.
Candidates: Base $C^{fix}=100{,}050$ $/MW-yr, $MC=20$, $\varepsilon=0.9$; Peaker $C^{fix}=50{,}000$, $MC=60$, $\varepsilon=0.8$.
- **T5-off** (`ra.prm` off): $x_{base}=100$, $x_{peak}=0$; mean price $=20+100{,}050/8760=31.42$ $/MWh (hourly degenerate).
- **T5a** (on, $\hat D=100$, $m=0.15$, $\bar\varepsilon=1$, Req = 115): $x_{base}=100$, $x_{peak}=(115-90)/0.8=31.25$ MW (idle, $g=0$);
  $\kappa=50{,}000/0.8=62{,}500$ $/MW-yr (171.23 $/MW-day), class `PRM_MARGINAL_BUILD` (setters `peaker`, `base`);
  $R_{base}=100{,}050-0.9\cdot62{,}500=43{,}800$ ⇒ weighted mean price exactly $25.00$ $/MWh; objective
  $100{,}050\cdot100+50{,}000\cdot31.25+8760\cdot100\cdot20=29{,}087{,}500$ $/yr.
- **T5b** (on, $\varepsilon_{base}=1$, $m=0$, Req = 100): requirement met exactly by the energy-optimal build, peaker
  not built; class `PRM_MARGINAL_BUILD` (setter `base`) with sub-tag `DEGENERATE`, $\kappa\in[0, 62{,}500]$
  ($\kappa^{hi}$ from the unbuilt peaker), and for any returned vertex $R_{base}=100{,}050-\kappa$
  (mean price $=20+(100{,}050-\kappa)/8760$); objective $= $ T5-off objective. In T5a the idle peaker ($R=0$, no
  at-cap hour) pins $\kappa$, so no sub-tag there.
- **T5c** precheck: Peaker $X^{max}=10$, Base $X^{max}=100$, Req 115 → $0.9\cdot100+0.8\cdot10=98<115$ ⇒ `DataError` deficit 17 MW.

---

## C. Weighted rep-period price duration curve and the price benchmarks (proposed formulation §7.1.7 addition, benchmarks.md §2 replacement)

DECISIONS 45: the primary price check is the **weighted rep-period price duration curve (PDC)**, plus monthly means and
daily spreads **from the same periods**, mapped to the real-world PDC (benchmarks M1.4, M1.1, M1.5). The full-year
fixed-fleet dispatch is only a check of period selection (C6).

### C1 The model price sample
For a location $z$ (a zone; "system" = load-weighted over zones, weights $D_{z,p,t}$) and model year $y$, the model
sample is the multiset $\{(\pi_{z,p,t},\,w_p): p\in\mathcal P, t=1..72\}$, $\pi$ from §3 ($\pi = y/w_p$; forced periods $w_p=1$).
Total weight $\sum_p 72\,w_p = H_y$ (weight identity, §1.2), so **each modeled hour counts $w_p$ real hours** and the
sample has exactly the mass of the real year. Weighted empirical CDF:
$\hat F(x)=\frac1{H_y}\sum_p w_p\,|\{t:\pi_{z,p,t}\le x\}|$; quantile $\hat Q(u)=\inf\{x:\hat F(x)\ge u\}$ (left-continuous inverse,
no interpolation). Actual: the $H_y$ hourly DA LMPs of the same location and calendar year, real $2024 (benchmarks §2), $F$, $Q$ alike.
Equivalence used by C3–C4: the chronological reconstruction $\hat\pi_{z,j,t}=\pi_{z,\mathrm{rep}(j),t}$ over real blocks
$j$ (gate5 draft §7.1.7, `block_map.csv`), with the remainder block contributing its first $h_r$ hours, has the same
distribution as the weighted sample (the remainder's weight fraction $\omega_{\bar J}=h_r/72$ is in $w_p$). The PDC uses the
weighted sample (no calendar); monthly and daily metrics use the reconstruction (they need calendar dates).

### C2 M1.4 — PDC distance and quantiles
- $W_1 = \int_0^1|\hat Q(u)-Q(u)|\,du$, computed **exactly** by merging the two step functions on the union of their
  breakpoints (no binning); metric `M1.4.w1_rel` $=W_1/\overline{\pi^{act}}$ (actual mean). Targets unchanged (good ≤0.15,
  acceptable ≤0.25 [P]).
- Signed quantile errors $\hat Q(u)-Q(u)$ at $u\in\{0.05,0.25,0.50,0.75,0.95,0.99\}$; weighted share of hours with
  $\pi>100$ and with $\pi\le0$ (model $\frac1{H_y}\sum w_p\,|\cdot|$ vs actual count$/H_y$).
- Blocks: `all`; `onpeak`/`offpeak` PDCs use the reconstruction's calendar (C3 rule) and are reported, not enforced.
- **Degenerate hours.** Where the price-setter class gives an interval (`CAPACITY_RENT` / `DEGENERATE`: $[$`price_lo`,
  `price_hi`$]$, `price_hi` capped at VOLL; `BLACKOUT`: VOLL), the PDC uses the midpoint and sets
  `degenerate_midpoint = true` on every metric row that includes such an hour; a lower and an upper envelope PDC
  (all degenerate hours at `price_lo` / at `price_hi`) are reported with their $W_1$. Until Gate 9 (ORDC) the
  **upper tail is not judged** (DECISIONS 45): enforcement uses the trimmed distance $W_1^{[0,0.95]}=\int_0^{0.95}|\hat Q-Q|\,du$
  over the same normalisation, and $p95$, $p99$ and the share $>\$100$ are `baseline`; from Gate 9 on the full $W_1$
  is enforced [P] (owner question O4).

### C3 M1.1 — monthly on-/off-peak means from the same periods
Each reconstructed hour $(j,t)$ carries the **calendar of the real block $j$** (`block_start_date` + $t-1$ hours,
case time basis per data-schema), not the representative's own dates. Month $m$, block $b\in\{$on, off$\}$ (PJM
definition, benchmarks §2): $\bar\pi^{model}_{m,b} = \text{mean of }\hat\pi_{z,j,t}$ over reconstructed hours in $(m,b)$;
the remainder block counts its $h_r$ hours once. This equals the $w$-weighted period average only when every block
of a cluster falls in one month — it does not in general, which is why the reconstruction, not $w_p$, is used here.
Metric and targets unchanged (MAE rel over the 12×2 values).
⚠ **Weekday/weekend mismatch:** a weekend-shaped medoid can represent weekday blocks; its prices then land in
on-peak hours of the real calendar. Report the share of reconstructed on-peak hours whose representative hour was
itself off-peak (`onpeak_mismatch_share`); if it is large, Gate 5 adds a day-type feature or day-type-pure clusters
(owner question O5 — a Gate 5 matter, recorded here so P12/Gate 5 criteria can carry it).

### C4 M1.5 / M4 — daily spreads from the same periods
Representative day $k\in\{1,2,3\}$ of period $p$ (hours $24(k-1)+1..24k$) has spread
$\Delta_{z,p,k}=\max-\min$ of $\pi_{z,p,t}$ over its 24 hours. It stands for
$n_{p,k}=|\{j\text{ full}:\mathrm{rep}(j)=p\}| + \mathbf 1[\mathrm{rep}(\bar J)=p \wedge k\le r_y]$ real days ($r_y=D_y\bmod 3$),
so $\sum_k n_{p,k}=3w_p$ and $\sum_{p,k}n_{p,k}=D_y$ — exact, including the remainder block (whose days are the
**first** $r_y$ days of its representative, not $w_p$ spread evenly over three days). Daily-spread distribution (M4):
the sample $\{(\Delta_{p,k}, n_{p,k})\}$. Monthly mean of daily spreads (M1.5): each real day of block $j$ gets
$\Delta_{\mathrm{rep}(j),k}$ and its own calendar month; bias rel and $r$ over the 12 monthly values as in benchmarks §3.
Spreads mix degenerate hours: rows carry `degenerate_midpoint` as in C2; the spread computed from envelopes is reported.

### C5 M1.3 (hourly correlation) — reported only
The reconstruction's chronology is synthetic (a block's prices come from another block's weather and fuel days),
so the hourly Pearson $r$ against the actual series measures period selection, not price formation. Under
DECISIONS 45 M1.3 becomes `info` (computed from the reconstruction, no target); benchmarks.md §3 row edited
accordingly (§D). M3.1 (monthly on-off spread) follows C3; M5 marginal-fuel shares are already $w_p$-weighted (§4).

### C6 Period-selection check (the one-off full-year fixed-fleet dispatch)
Same case, same fleet (the rep-period run's built capacities fixed, $X^{max}=0$), `ts.mode = full_blocks`: the
"full-year" PDC $F^{fy}$. Report $W_1(\hat F, F^{fy})/\overline{\pi^{fy}}$ (aggregation error alone) next to
$W_1(\hat F, F)$ and $W_1(F^{fy}, F)$ (model error alone). It is a Gate 5 test-ladder row (benchmarks §6,
"rep-period run vs full-year dispatch of the same fleet"); proposed tolerance ≤0.05 [P] trimmed as C2, for
P12/Gate 5 criteria to adopt or change. This run is a check of period selection only — no client output is taken from it.

### C7 Outputs
`pdc.csv` (`location, year, curve` ∈ {model, model_lo, model_hi, actual, fullyear}, `u, price`, at the 1000 quantiles
$u=0.0005,0.0015,\dots,0.9995$ for plotting; metrics are computed exactly, not from this grid);
`daily_spread.csv` (`location, period, day_k, n_days, spread`); scoreboard rows as benchmarks §8 with `block`,
`degenerate_midpoint` and a new `curve_basis` ∈ {`weighted_rep`, `fullyear`}. One function (`capex.scoreboard`) computes all.

### C8 Multi-year
Per model year $y$ with its own periods and weights; the PDC of $y$ is compared to actuals only when $y$ is a
backcast calendar year. Forward years report the PDC without a reference.

---

## D. Proposed edits and DECISIONS entries (made at the W-spec step, not now)
- **E1** formulation: new §0 = §A; §7.9 = §B (Gate 7); §7.1.7 gains C1–C4 (pointer to benchmarks for metrics);
  §7.7 retirement note "must stay off until RPM" → "allowed with `ra.prm` on" (DECISIONS 44(c)); §7.8 pointer: VRR
  replaces `prm` (`ra.mode`). §7 headings renumbered to DECISIONS 43 numbers (ORDC 9, transmission 10, UC 11, policy/build 12, pointer 14/16).
- **E2** benchmarks.md §2 "Model-side price series": replace "(b) hourly metrics … only from the full-year fixed-fleet
  dispatch" with C1–C5 (weighted rep-period sample and reconstruction; full-year dispatch = C6 check only); §3 M1.3 →
  `info`; M1.4/M1.5 "Enabled" columns renumbered (old G12 → 14, G7 → 9) and the C2 trimmed rule; §5 "until Gate 7"
  → "until Gate 9"; §6 Gate 5 row adds C6.
- **E3** data-schema: `resources.csv.elcc_class`, `elcc.csv`, `ra_requirement.csv` (both with provenance columns),
  outputs `capacity_price.csv`, `capacity_mix.csv`, `pdc.csv`, `daily_spread.csv`; `rents` + `ucap_mw`, `cap_rev`.
- **E4** docs/gates/README.md: "Feature-block contract" section pointing to formulation §0 (A1–A10 checklist in every gate review).
- Proposed DECISIONS text: "(n) Formulation §0 feature-block contract A1–A10 adopted; every gate review checks it per
  new block. (n+1) `ra.prm` (Gate 7): one system area, hard row, ELCC class × ICAP (storage on $P$, fixed-duration
  candidates), $\kappa$ = capacity shadow price, no hourly price-setter class; annual setter report. (n+2) Price
  benchmarks M1.1/M1.4/M1.5 from the weighted rep-period sample and its reconstruction (C1–C4); M1.3 info; upper
  tail judged from Gate 9; full-year dispatch = period-selection check C6."

## E. Accuracy risks / open owner questions (yes/no; recommendation in brackets)
- **O1** For PJM runs, state the PRM requirement as PJM does (forecast peak × FPR, i.e. $\bar\varepsilon$ = pool-wide
  UCAP factor), so $\kappa$ is comparable with BRA prices? [yes — with $\bar\varepsilon=1$ the row requires ~25% more
  UCAP than PJM does and $\kappa$ would be biased high]
- **O2** Existing storage duration rounded **down** to the ELCC class (not to the nearest)? [yes — never over-accredits]
- **O3** Candidate storage must have fixed duration when `ra.prm` is on (one candidate per duration class)? [yes — keeps the row linear and exact]
- **O4** PDC upper tail (p95+, share >$100) `baseline` until Gate 9, trimmed $W_1^{[0,0.95]}$ enforced before that? [yes]
- **O5** Record weekday/weekend mismatch (C3) as a Gate 5 criterion input for P12/gate-5? [yes]
- **O6** Block contract A10 golden set refreshed only at gate boundaries from the approved branch? [yes]
- ⚠ Exogenous class ELCC ignores the portfolio effect (falling marginal ELCC as storage/solar grow) — builds of a
  class can overshoot; ledger reports class UCAP shares; endogenous ELCC stays out until a client question needs it.
- ⚠ A hard PRM with no demand curve makes $\kappa$ jump between 0 and net CONE; RPM-like prices need Gate 16's VRR.
- ⚠ Rep-period PDC tails are bounded by forced periods (gate5 draft §7.1.3); a too-small $k$ flattens the PDC
  shoulders — C6 isolates this from formation error.

## References
- Kotzur, Markewitz, Robinius, Stolten (2018), "Impact of different time series aggregation methods on optimal
  energy system design," *Renewable Energy* 117 — duration-curve fit of aggregated time series.
- Hoffmann, Kotzur, Stolten, Robinius (2020), "A review on time series aggregation methods for energy system
  models," *Energies* 13(3) — weighted representative periods, duration-curve validation.
- Jenkins & Sepulveda (2017), GenX formulation (MIT CEEPR WP 2017-017) — capacity reserve margin constraint
  `CapRes` with derating factors and its dual as a capacity price (verify section numbering).
- Ho et al. (2021), *Regional Energy Deployment System (ReEDS) Model Documentation*, NREL/TP-6A20-78195 — planning
  reserve margin with capacity credit (verify).
- PJM ELCC class ratings, IRM/FPR: docs/drafts/pjm-rpm-notes.md §2.4, §3 (sources and verify flags there).
