# Formulation spec — capex-model

Version: **F-0.2** (Gate 0 patch, W3, 2026-11-22; F-0.1 was W1). Status: draft for owner review.
F-0.2 changes (DECISIONS 25): daily fuel price $\phi_{f,p,t}$; DECISIONS 22–24 applied (ATB-style PFF default,
block-average price scoring, 2024\$ / ORDC backcast scarcity); `VOLL` class covers total blackout; tolerances,
$Z^0$, $FOM^P/FOM^E$, weight range, remainder-day rule and basic-solution requirement made consistent;
DC power-flow option sketched for Gate 3 (§7.4a).
F-0.2 amendment 1 (W4b-fix1, 2026-11-25, DECISIONS 31): SOC-row recomputation health check (§3 check 8, §8.6);
storage price-setter `setter_cost`/`residual` defined per class (§4 Outputs); dual-degenerate storage duals at
zero storage capacity (§3 check 7, T2c in §10). The LP itself is unchanged, so the version string stays `F-0.2`.
F-0.2 amendment 2 (W5-spec1, 2026-11-26, DECISIONS 32): wording only — §6.2 states that infeasibilities are
measured on the scaled LP and splits the "RHS ratio / any finite bound" row into a ratio metric and a magnitude
metric (the code's reading, ratified); §5.2 `ANN ≥ I/n` check limited to PFF ≥ 1. LP and thresholds unchanged.
F-0.2 amendment 3 (W6-spec1, 2026-11-26, DECISIONS 35): reporting only — §4 `CAPACITY_RENT` hours are attributed to
the `INVESTMENT_MARGIN` unit(s), else to the highest-MC unit in the rent set, with the full rent set in `rent_ids`;
§8.5 rents of $x=0$ candidates flagged `non-unique (bound)`; §8.11 assumptions-book run header and toy banner;
§10 T2a typo ($v = 60\cdot0.9$). LP, duals, price checks and thresholds unchanged.
Scope of authority: code in `src/capex/` implements this file. Any deviation changes this
file in the same commit and is logged in `DECISIONS.md`. Constraint/variable labels in
`code font` are the identifiers used in code, audit output and tests.

Contents
1. Conventions
2. Gate 1 toy model (full spec)
3. Dual interpretations and verifier checks
4. Price-setter algorithm
5. Dollar-year, real terms, single annualization function
6. Scaling plan and numerical conditioning check
7. Gate 5–10 extensions (sketch)
8. Audit hooks
9. Known accuracy risks / open questions
10. Known-answer toy cases (T1–T4)

---

## 1. Conventions

### 1.1 Units (I/O boundary)
| Quantity | Unit at I/O | Internal (scaled, §6) |
|---|---|---|
| power, capacity, flow | MW | GW |
| energy, storage capacity | MWh | GWh |
| variable cost, price | $/MWh (base-year real $) | M$/GWh |
| fixed cost (annualized) | $/MW-yr, $/MWh-yr | M$/GW-yr, M$/GWh-yr |
| overnight capex | $/MW, $/MWh | (never enters LP directly) |
| objective | $ /yr (base-year real) | M$/yr |

All inputs and outputs are in I/O units; scaling happens only in the model builder and is
undone by the audit layer. Time step $\Delta t = 1$ h everywhere (power × 1 h = energy), so
$\Delta t$ is omitted from equations; code must still assert it.

### 1.2 Time indexing and weights
- Model year $y$ with $D_y \in \{365, 366\}$ days, $H_y = 24 D_y$ h.
- Representative periods $p \in \mathcal P$, each a 3-day block; hours $t \in \mathcal T = \{1,\dots,72\}$.
- Cyclic predecessor within a period: $t^- = t-1$ for $t>1$, $1^- = 72$.
- Period weight $w_p$ = number of 3-day blocks of the year that period $p$ represents
  $= (\text{days represented by } p)/3$. Every modeled hour $(p,t)$ stands for $w_p$ real hours.
- **Weight identity (validated on load, tol $10^{-9}$):** $\sum_{p} 72\, w_p = H_y$, i.e. $\sum_p w_p = D_y/3$.
- **Weight floor:** $w_p \ge 1$ (a period represents at least itself). This is what keeps
  $w_p \cdot \text{VOLL}$ from interacting with tiny weights (§6). Violations are a load error.
- Remainder days ($D_y \bmod 3 \in \{1,2\}$) form one truncated final block of $1$ or $2$ days. It is
  assigned to the period whose first $24(D_y \bmod 3)$ hours are nearest in feature space, and that
  period's weight grows by $1/3$ or $2/3$ (single rule; §7.1 uses it unchanged).
- Weight range: $w_p \ge 1$, no upper bound. Typical PJM runs ($8$–$40$ periods) have $w_p \in [1, 40]$;
  the single-period toys of §10 have $w = 121.\overline6$. Scaling (§6) is checked for $w_p \le 122$.
- Annual sum of an hourly quantity $q$: $\sum_p w_p \sum_t q_{p,t}$ (units: MW·h = MWh).

### 1.3 Sign conventions
- Injections into a zone are positive. Storage: charge $c \ge 0$ withdraws, discharge $d\ge0$ injects.
- Flow $f_l$ is signed: positive in the direction $o(l) \to e(l)$ (origin → end).
- Objective is **minimized** total annual system cost.
- **Canonical dual convention:** for every row $i$, $y_i := \partial Z^*/\partial b_i$ (sensitivity of
  the optimal objective to the row's right-hand side). For minimization, an equality has
  free $y$, a binding $\le$ row has $y \le 0$, a binding $\ge$ row has $y\ge0$. HiGHS
  (`highspy`, `getSolution().row_dual`) returns exactly this for minimization;
  column duals are reduced costs $s_j = c_j - \sum_i a_{ij} y_i$ ($s_j \ge0$ at lower bound,
  $\le 0$ at upper bound). Every solver adapter must return duals in this convention;
  the adapter test (verifier) checks it on a 2-variable LP with one binding row of each type.
- Economic duals (prices, rents) reported by audit are defined in §3 with explicit sign flips
  so that every reported price/rent is $\ge 0$ in normal operation.

### 1.4 Notation
| Symbol | Meaning | Unit |
|---|---|---|
| $z \in \mathcal Z$ | zones | – |
| $l \in \mathcal L$ | transport links, origin $o(l)$, end $e(l)$ | – |
| $r \in \mathcal R = \mathcal R^{TH}\cup\mathcal R^{VRE}\cup\mathcal R^{ST}$ | resources (thermal, variable renewable, storage); zone $z(r)$ | – |
| $\mathcal R_z$ | resources in zone $z$ | – |
| $K^0_r$ | existing capacity (storage: $P^0_r$ power, $E^0_r$ energy) | MW, MWh |
| $X^{max}_r$ | max new build ($+\infty$ allowed; storage: $X^{P,max}, X^{E,max}$) | MW, MWh |
| $A_{r,p,t}\in[0,1]$ | availability (thermal: $1-$derate/outage; VRE: capacity factor) | – |
| $MC_{r,p,t}$ | marginal cost $= HR_r\,\phi_{f(r),p,t} + VOM_r$ (+ adders, §7) | $/MWh |
| $HR_r$, $\phi_{f,p,t}$ | heat rate; fuel price, hourly-indexed; real data are daily, so $\phi$ is constant on hours $1$–$24$, $25$–$48$, $49$–$72$ of a block (the three gas days of the medoid) | MMBtu/MWh, $/MMBtu |
| $VOM_r$ | variable O&M (storage: per MWh discharged) | $/MWh |
| $C^{fix}_r$ | annualized fixed cost of new capacity $=\text{ANN}(I_r,\ldots)+FOM_r$ (§5) | $/MW-yr |
| $C^{P}_r, C^{E}_r$ | storage annualized fixed cost, power / energy part | $/MW-yr, $/MWh-yr |
| $FOM_r$ | fixed O&M | $/MW-yr |
| $FOM^P_r, FOM^E_r$ | storage fixed O&M, power / energy part | $/MW-yr, $/MWh-yr |
| $\eta^c_r,\eta^d_r$ | charge / discharge efficiency (RTE $=\eta^c\eta^d$) | – |
| $\sigma_r$ | self-discharge per hour | 1/h |
| $\underline\delta_r,\overline\delta_r$ | min / max duration of new storage $E/P$ | h |
| $D_{z,p,t}$ | demand (net of behind-the-meter, as supplied) | MW |
| $\text{VOLL}$ | value of lost load | $/MWh |
| $F^+_l, F^-_l$ | NTC in positive / negative direction ($\ge 0$) | MW |

---

## 2. Gate 1 toy model (full spec)

Single model year, one or few zones, lossless NTC transport, thermal + VRE + storage,
existing and new capacity, unserved energy, curtailment, intra-period cyclic SOC. No
reserves, UC, policy, retirements, capacity market.

**Data rule.** A resource is either *existing* ($K^0_r>0$, $X^{max}_r=0$) or *candidate*
($K^0_r = 0$, $X^{max}_r>0$). The math allows both on one resource, but Gate 1 data keeps
them separate so zero-profit tests are clean.

### 2.1 Decision variables
| Label | Symbol | Index | Bounds | Unit |
|---|---|---|---|---|
| `x` | $x_r$ | $r \in \mathcal R^{TH}\cup\mathcal R^{VRE}$ | $0 \le x_r \le X^{max}_r$ | MW |
| `xP` | $x^P_r$ | $r\in\mathcal R^{ST}$ | $0 \le x^P_r \le X^{P,max}_r$ | MW |
| `xE` | $x^E_r$ | $r\in\mathcal R^{ST}$ | $0 \le x^E_r \le X^{E,max}_r$ | MWh |
| `g` | $g_{r,p,t}$ | $r \in \mathcal R^{TH}\cup\mathcal R^{VRE}$ | $\ge 0$ | MW |
| `ch` | $c_{r,p,t}$ | $r\in\mathcal R^{ST}$ | $\ge 0$ | MW |
| `dis` | $d_{r,p,t}$ | $r\in\mathcal R^{ST}$ | $\ge 0$ | MW |
| `soc` | $e_{r,p,t}$ | $r\in\mathcal R^{ST}$ (end-of-hour) | $\ge 0$ | MWh |
| `flow` | $f_{l,p,t}$ | $l\in\mathcal L$ | $-F^-_l \le f \le F^+_l$ | MW |
| `use` | $u_{z,p,t}$ | $z\in\mathcal Z$ | $0 \le u \le D_{z,p,t}$ | MW |

Bound labels (for column duals): `x_ub`, `xP_ub`, `xE_ub`, `flow_ub`, `flow_lb`, `use_ub`.
Curtailment is not a variable: $\text{curt}_{r,p,t} = A_{r,p,t}(K^0_r+x_r) - g_{r,p,t}$ for $r\in\mathcal R^{VRE}$ (reported).

### 2.2 Constraints
Capacity expressions: $K_r = K^0_r + x_r$; $P_r = P^0_r + x^P_r$; $E_r = E^0_r + x^E_r$.

**`bal[z,p,t]`** — energy balance (equality; RHS = demand)
$$\sum_{r\in\mathcal R_z\setminus\mathcal R^{ST}} g_{r,p,t} + \sum_{r\in\mathcal R_z\cap\mathcal R^{ST}} (d_{r,p,t}-c_{r,p,t}) + \sum_{l:e(l)=z} f_{l,p,t} - \sum_{l:o(l)=z} f_{l,p,t} + u_{z,p,t} = D_{z,p,t}$$

**`gen_max[r,p,t]`**, $r\in\mathcal R^{TH}\cup\mathcal R^{VRE}$:
$\; g_{r,p,t} - A_{r,p,t}\,x_r \le A_{r,p,t}K^0_r$

**`st_pwr[r,p,t]`** (single inverter; LP relaxation of "not both at full power"):
$\; c_{r,p,t} + d_{r,p,t} - x^P_r \le P^0_r$

**`st_soc[r,p,t]`** (cyclic within period via $t^-$):
$\; e_{r,p,t} - (1-\sigma_r)\,e_{r,p,t^-} - \eta^c_r c_{r,p,t} + d_{r,p,t}/\eta^d_r = 0$

**`st_emax[r,p,t]`**: $\; e_{r,p,t} - x^E_r \le E^0_r$

**`st_dur_lo[r]`**, **`st_dur_hi[r]`** (candidate storage only; omitted if bound absent):
$\; x^E_r - \underline\delta_r x^P_r \ge 0,\qquad x^E_r - \overline\delta_r x^P_r \le 0$

Gate 1 writes `gen_max`, `st_pwr`, `st_emax` as rows even for existing-only resources
(toy size is irrelevant). A later optimization may turn them into column bounds when
$X^{max}=0$, but audit must still report their duals under the same label.

Note: with all $MC\ge0$ and VRE curtailable, prices are $\ge 0$, so simultaneous
charge/discharge is never strictly profitable; it can appear at $\pi=0$ (degenerate).
Audit reports hours with $\min(c,d) > tol_q$ (`simul_chdis`); not an error in Gate 1.

### 2.3 Objective (annual, base-year real $)
$$\min Z = \underbrace{\sum_{r\in\mathcal R^{TH}\cup\mathcal R^{VRE}} C^{fix}_r x_r + \sum_{r\in\mathcal R^{ST}}(C^P_r x^P_r + C^E_r x^E_r)}_{Z^{inv}}
+ \underbrace{\sum_p w_p \sum_t\Big[\sum_{r} MC_{r,p,t}\,g_{r,p,t} + \sum_{r\in\mathcal R^{ST}} VOM_r d_{r,p,t}\Big]}_{Z^{var}}
+ \underbrace{\sum_p w_p\sum_t\sum_z \text{VOLL}\,u_{z,p,t}}_{Z^{use}} + Z^0$$
$Z^0 = \sum_r FOM_r K^0_r + \sum_{r\in\mathcal R^{ST}} (FOM^P_r P^0_r + FOM^E_r E^0_r)$ is a constant
(existing FOM, no retirement in Gate 1); it is added to the reported total and to the objective
decomposition (§8.4), but is **not** in the LP and **not** in the strong-duality check (§3 check 2).
Sunk capex of existing units is excluded.

---

## 3. Dual interpretations and verifier checks

Let $S = 10^3$ be the dual unscaling factor (§6: $k_P/k_C$). Raw duals $\tilde y$ come from
the scaled LP; $y = S\,\tilde y$ is in $/(unit of row RHS) per year.

| Row / bound | Raw sign (min) | Economic quantity | Conversion | Unit |
|---|---|---|---|---|
| `bal[z,p,t]` | free, normally $\ge0$ | energy price (LMP) $\pi_{z,p,t}$ | $\pi = y/w_p$ | $/MWh |
| `gen_max[r,p,t]` | $\le 0$ | capacity scarcity rent per available MW in that hour | $\rho_{r,p,t} = -y/w_p$ | $/MWh |
| (annual) | | capacity rent $R_r=\sum_p w_p\sum_t A_{r,p,t}\rho_{r,p,t}$ | | $/MW-yr |
| `st_pwr[r,p,t]` | $\le 0$ | storage power rent | $\rho^P = -y/w_p$; $R^P_r = \sum w_p\rho^P$ | $/MWh; $/MW-yr |
| `st_emax[r,p,t]` | $\le 0$ | storage energy rent | $\rho^E = -y/w_p$; $R^E_r=\sum w_p \rho^E$ | $/MWh; $/MWh-yr |
| `st_soc[r,p,t]` | free, normally $\le0$ | marginal value of stored energy ("water value") | $v_{r,p,t} = -y/w_p$ | $/MWh stored |
| `st_dur_lo` / `st_dur_hi` | $\ge0$ / $\le0$ | rent transfer between power and energy builds | $y$ | $/MWh-yr |
| `flow_ub`/`flow_lb` (col) | $s\le0$ / $s\ge0$ | congestion rent $\pi_{e(l)}-\pi_{o(l)}$ | $\mu_{l,p,t} = -s/w_p$ | $/MWh |
| `x_ub` (col) | $s\le0$ | value of relaxing build limit $R_r - C^{fix}_r$ | $-s$ | $/MW-yr |
| `use_ub` (col) | $s \le 0$ | blackout rent $\pi - \text{VOLL}$ (only if $u=D$) | $-s/w_p$ | $/MWh |

Stationarity relations used by tests and by §4 (from $s_j = c_j - \sum_i a_{ij}y_i$):
- $g$: $w_p MC - y^{bal} - y^{gen}=s_g$ → if $g>0$ and not at cap: $\pi = MC$; if at cap: $\pi = MC + \rho$.
- $d$: $w_p VOM - y^{bal} - y^{soc}/\eta^d - y^{pwr} = s_d$ → interior $d$, slack `st_pwr`: $\pi = VOM + v/\eta^d$.
- $c$: $y^{bal} + \eta^c y^{soc} - y^{pwr} = s_c$ → interior $c$: $\pi = \eta^c v$.
- $e$: $-y^{soc}_t + (1-\sigma) y^{soc}_{t^+} - y^{emax}_t = s_e$ → $0<e<E$: $v_t = (1-\sigma)v_{t^+}$.
- $f$ (lossless): $-y^{bal}_{e(l)} + y^{bal}_{o(l)} = s_f$ → interior flow: $\pi_{o}=\pi_{e}$.
- $x$: $C^{fix} - \sum_{p,t} A\,(-y^{gen}) = s_x$ → $s_x = C^{fix}_r - R_r$.

**Verifier checks (Gate 1 health checks; tolerances in `docs/gates/gate-1.md`):**
1. `bal` residual $|\text{LHS}-D|$, measured in **unscaled MW**, every $(z,p,t)$: Gate 1 toy and random cases
   require $\le 10^{-6}$ MW; all other runs use the §6.2 warn/fail thresholds ($10^{-3}$ / $10^{-1}$ MW).
2. Strong duality on the LP objective (i.e. excluding the constant $Z^0$): $|Z^{primal}-Z^{dual}|/|Z| \le 10^{-7}$, where
   $Z^{dual}=\sum_i b_i y_i + \sum_j (\text{bound}_j \cdot s_j)$ over active bounds.
3. Complementary slackness on every row and bound: $|y_i \cdot \text{slack}_i| \le tol$.
4. Dual sign feasibility per the table (raw signs).
5. **Zero-profit** for each candidate with $0 < x_r < X^{max}_r$: $|R_r - C^{fix}_r| \le 10^{-6} C^{fix}_r$;
   at $x_r = 0$: $R_r \le C^{fix}_r$; at $x_r = X^{max}_r$: $R_r \ge C^{fix}_r$.
   Storage: reduced costs recomputed from duals, $s_{xP} = C^P - R^P + \underline\delta y^{lo} + \overline\delta y^{hi}$ and
   $s_{xE} = C^E - R^E - y^{lo} - y^{hi}$, must equal the solver's column duals; with fixed duration
   $\delta$ the combined test is $(C^P+\delta C^E) - (R^P+\delta R^E)$ $=0$ / $\ge0$ / $\le0$ for interior / at 0 / at max.
6. **Revenue identity** (any resource, from complementary slackness):
   $\sum_p w_p \sum_t (\pi - MC)\,g = R_r K_r$; storage:
   $\sum_p w_p\sum_t[\pi(d-c) - VOM\,d] = R^P_r P_r + R^E_r E_r$ (+ $\sigma$ terms are zero by construction).
   Hence for interior candidates, market revenue minus variable cost = annualized fixed cost.
7. Hourly duals may be **non-unique** (dual degeneracy) in blocks of hours with identical
   data or at capacity (see T1). Tests on prices compare weighted averages over such blocks,
   or check the price lies in the interval allowed by the price-setter class (§4), never a
   single hourly value unless the case is constructed to make it unique.
   **Storage duals at zero storage capacity** ($P_r = E_r = 0$, e.g. T2c) are dual-degenerate: $c=d=e=0$ in every
   hour, so $v$, $\rho^P$, $\rho^E$ are pinned only by dual feasibility (§10 T2c gives the interval). For such a
   storage, tests compare primal values, $\pi$ and generator $\rho$ only, and check its rents against the interval
   (at $x=0$: rent $\le$ cost, never "$<$"); $v$, $\rho^P$, $\rho^E$ are reported, not compared across scalings or
   solver settings. On random instances, storage duals are excluded from the scaling comparison for the same reason.
8. **SOC-row recomputation** (`storage.soc_recompute`, every solve with storage). From the **case data** — the
   loaded $\eta^c_r$, $\eta^d_r$, $\sigma_r$, never the coefficients of the assembled matrix — and the unscaled
   primal, recompute for every $(r,p,t)$, with the same cyclic $t^-$ as `st_soc` (§7.2 form when linked):
   $\;r^{soc}_{r,p,t} = e_{r,p,t} - (1-\sigma_r)e_{r,p,t^-} - \eta^c_r c_{r,p,t} + d_{r,p,t}/\eta^d_r$ (MWh).
   Pass: $\max|r^{soc}| \le 10^{-6}$ MWh on Gate 1 toy and random cases; otherwise the §6.2 `bal` thresholds
   applied in MWh (warn $10^{-3}$, fail $10^{-1}$). Reason: checks 1–7 prove the solved LP is self-consistent, not
   that it encodes the case; a wrong `st_soc` coefficient (e.g. $\eta^c$ and $\eta^d$ swapped, audit mutation M4)
   leaves duality, CS and rent identities intact. Same principle as check 1, which recomputes `bal` from $D$.

---

## 4. Price-setter algorithm

Run on every solve, per $(z,p,t)$, using unscaled primal and economic duals. Requires a
**basic (vertex) solution**. Solver config therefore forces it: HiGHS `solver=simplex`,
`simplex_strategy=1` (dual), `presolve=off` by default (presolve changes which degenerate dual vertex is
returned; with it on, T3a's Peaker reduced cost reads 0 instead of 40,500); if IPM is chosen, `run_crossover=on` is mandatory. The
adapter reports `basis_valid`; audit rejects a solution without a valid basis (IPM without
crossover makes every unit look marginal). Solver choice and options enter the fingerprint (§8.10).

Tolerances: $tol_q = \max(10^{-3}\text{ MW}, 10^{-6} K_r)$; $tol_\pi = \max(0.01\ \$/\text{MWh}, 10^{-5}|\pi|)$.
"Interior" means strictly inside bounds by more than $tol_q$.

**Step 0 — price islands.** Build graph on zones; connect $o(l), e(l)$ if
$|\pi_{o(l)}-\pi_{e(l)}| \le tol_\pi$. Connected components are islands $\mathcal I$. Check: every
link with $|\Delta\pi| > tol_\pi$ is at the bound in the low→high price direction and
$|\mu_l - \Delta\pi| \le tol_\pi$; else flag `LINK_INCONSISTENT`.

**Step 1 — candidates in the island** (all zones $z' \in \mathcal I(z)$), in this order; every
match is recorded, the first class matched is the *primary* class:

| Class | Condition | Price check |
|---|---|---|
| `VOLL` | $u_{z',p,t} > tol_q$ and $u < D - tol_q$ | $\lvert\pi-\text{VOLL}\rvert\le tol_\pi$ |
| `VOLL` / sub-tag `BLACKOUT` | $u_{z',p,t} \ge D - tol_q$, $D>tol_q$ (`use_ub` binding; total blackout) | $\pi \ge \text{VOLL} - tol_\pi$ and $\lvert \pi - \text{VOLL} - \mu^{use}\rvert \le tol_\pi$, $\mu^{use}=-s_{use}/w_p$ |
| `MARGINAL_UNIT` | $r$ with $tol_q < g < A K - tol_q$ | $\lvert\pi - MC_r\rvert \le tol_\pi$ |
| `STORAGE_DIS` | $d$ interior, `st_pwr` slack | $\lvert\pi - VOM - v/\eta^d\rvert \le tol_\pi$ |
| `STORAGE_CH` | $c$ interior, `st_pwr` slack | $\lvert\pi - \eta^c v\rvert\le tol_\pi$ |
| `TIE_AT_BOUND` | $r$ at a bound with $\lvert MC_r-\pi\rvert\le tol_\pi$ | (same) |
| `CAPACITY_RENT` | none of the above; every resource in the island with $MC<\pi - tol_\pi$ is at cap; at least one resource at cap with $\rho>tol_\pi$ | $\max MC_{\text{at cap}} - tol_\pi \le \pi \le \min(\text{VOLL}, \min MC_{\text{with room}}) + tol_\pi$ |

`CAPACITY_RENT` attribution (amendment 3). Let the **rent set** $S$ be the at-cap resources in
the island with $\rho>tol_\pi$; it is reported in full in column `rent_ids` (sorted ids; empty
for every other class). The **setters** (`setter_ids`, and the hour's attribution in the
summary) are a subset of $S$:
1. if some $r\in S$ has an interior build ($0<x_r<X^{max}_r$, i.e. `build_status` = `interior`),
   the setters are all such $r$; sub-tag `INVESTMENT_MARGIN` (the price recovers their capex,
   cf. T1, T3b);
2. else the setter is the $r\in S$ with the largest $MC_r$ (all $r\in S$ with
   $MC_r \ge \max_S MC - tol_\pi$ on a tie); sub-tag `DEGENERATE` (price is not unique: any
   value in the check interval is optimal; reported with the interval).
Reason: on a real fleet almost every unit is at cap in a scarcity hour, so attributing the hour
to all of $S$ would count nuclear and coal as price-setters in the marginal-fuel shares. The
class's condition and price check are unchanged. Units attributed outside zone $z$ get
the flag `IMPORT` plus the list of binding links on the island boundary (`CONGESTED`).

**Step 2 — unexplained.** If no class matches, or the matched class fails its price check,
the zone-hour is `UNEXPLAINED`. Health check: count of `UNEXPLAINED` must be 0.

**Outputs** per $(z,p,t)$: primary class, setter resource id(s), tech/fuel, setter zone,
$\pi$, setter cost, residual $\pi - \text{cost}$, island id, binding links. **Setter cost** is the
cost term of the class's price check, so `residual` is within $tol_\pi$ of 0 for every explained hour except
`BLACKOUT` and `CAPACITY_RENT`: `MARGINAL_UNIT`/`TIE_AT_BOUND` $MC_r$; `STORAGE_DIS` $VOM_r + v_{r,p,t}/\eta^d_r$
(not $VOM_r$ alone); `STORAGE_CH` $\eta^c_r v_{r,p,t}$; `VOLL` VOLL; `BLACKOUT` VOLL (residual $=\mu^{use}\ge0$);
`CAPACITY_RENT` the interval's lower end $\max MC_{\text{at cap}}$ (residual = scarcity rent), with the interval
reported in `price_lo`/`price_hi` (this does not change with the setter subset). Several setters (other
classes): mean of their costs. Further column `rent_ids` (the `CAPACITY_RENT` rent set $S$, else empty). Aggregate: share of
weighted hours ($\sum w_p$) by marginal fuel/tech per zone — the IMM comparison metric.
Ties between several marginal units split the hour equally among them; a `CAPACITY_RENT` hour is split
equally among its setters only (not among all of `rent_ids`).

Later classes (inserted before `CAPACITY_RENT`, by gate): `RESERVE_ORDC` (G7: price includes
reserve shadow price via headroom coupling), `LOSS_HURDLE` (G8: island test becomes
$\pi_e = \pi_o(1+\lambda_l)+h_l$), `UC_COMMIT` / `RAMP` (G9: unit with interior commitment, or
binding ramp row whose dual explains $\pi - MC$), `POLICY` (G10: $MC$ includes REC/CO$_2$ terms).

---

## 5. Dollar-year, real terms, single annualization function

### 5.1 Real-terms rules
- Every cost input carries `dollar_year` (and the provenance fields of `docs/data-sources.md`).
  A cost without a dollar year is a load error.
- Model base dollar year $B$ (config, e.g. 2024). Conversion:
  $C^{(B)} = C^{(y)} \cdot \text{DEF}(B)/\text{DEF}(y)$, deflator series **BEA GDP implicit price
  deflator, annual (NIPA Table 1.1.9)**, `source_id = bea_gdpdef`, vintage recorded. Sub-annual
  series (daily gas, hourly LMPs used as benchmarks) are deflated with the annual value of
  their calendar year (monthly interpolation optional, switch `deflate.monthly`).
- All model costs, prices and outputs are real $B$. Nominal values exist only at the
  ingestion boundary and in reports that explicitly label them nominal (e.g. futures comparison).
- Discount/financing rates are **real**. If a nominal rate $i$ is supplied with inflation $\pi^e$:
  $r = (1+i)/(1+\pi^e) - 1$ (Fisher). Conversion happens once, in the same module as §5.2.
- One deflation function `capex.econ.to_base_dollars(value, dollar_year)` and one
  annualization function (below). No other code path deflates or annualizes; the verifier
  adds a static check that no `(1 + r) **`-style annuity math appears outside `capex/econ.py`.

### 5.2 `capex.econ.annualize`
Inputs: overnight cost $I$ (base $ per MW or per MWh), real WACC $r$, economic life $n$ (yr),
optional construction spend profile $(\phi_1,\dots,\phi_L)$, $\sum\phi_k=1$, $\phi_k$ = share spent in
year $k$ before COD ($k=L$ is the last year), optional multiplicative project-finance factor
$\text{PFF}$ (DECISIONS 22: ATB-style is the default, below).

$$\text{CRF}(r,n) = \begin{cases} \dfrac{r(1+r)^n}{(1+r)^n-1} & r \ne 0\\[4pt] 1/n & r=0 \end{cases}
\qquad
\text{IDC factor } \kappa = \sum_{k=1}^{L}\phi_k(1+r)^{L-k+0.5}\ \ (\kappa=1 \text{ if no profile})$$
$$\text{ANN}(I) = I\cdot \kappa\cdot \text{PFF}\cdot \text{CRF}(r,n)\qquad[\$/\text{MW-yr}]$$
Mid-year spending convention.

**Project finance factor (DECISIONS 22).** `finance.mode ∈ {atb_pff (default), simple_crf}` per finance class
(`finance.csv`). `simple_crf`: $\text{PFF}=1$. `atb_pff` (NREL ATB method): 
$$\text{PFF} = \frac{1 - T\cdot \text{PVD}}{1-T},\qquad \text{PVD} = \sum_{k=1}^{M} \frac{m_k}{(1+i)^{k}},$$
$T$ = combined federal+state tax rate, $m_k$ = MACRS depreciation shares for class life $M$ ($\sum m_k = 1$;
half-year convention tables, $M+1$ entries), $i$ = nominal WACC $= f_d\, i_d (1-T) + (1-f_d)\, i_e$; the real WACC for the CRF is
$r = (1+i)/(1+\pi^e)-1$ (Fisher, §5.1). If a class supplies `pff` directly, that value is used and recorded
as `method=assumed`. Both modes are tested; toys use `cfix_override` so neither affects T1–T4. Edge cases: $|r| < 10^{-9}$ uses the $r=0$ branch; require
$n \ge 1$, $r > -1$, $\phi_k\ge0$; raise otherwise. Output is checked: $\text{ANN}\ge I/n$ when $r\ge0$ **and** $\text{PFF}\ge1$ (then $\kappa\ge1$ and
$\text{CRF}\ge1/n$, so the bound holds). The `atb_pff` formula gives $\text{PFF}\ge1$ whenever $\text{PVD}\le1$, i.e. for any
nominal WACC $i\ge0$; only a directly supplied `pff` < 1 (`method=assumed`) can fall below it, and then the check is
skipped, not failed (DECISIONS 32).

Use: $C^{fix}_r = \text{ANN}(I_r) + FOM_r$ (FOM added *after* annualization, never annualized);
storage $C^P_r = \text{ANN}(I^P_r)+FOM^P_r$, $C^E_r = \text{ANN}(I^E_r)+FOM^E_r$; transmission
expansion (G8) and sustaining capex for going-forward costs (G10) use the same function.
The assumptions book prints $I, r, n, \kappa, \text{PFF}, \text{CRF}, C^{fix}$ per resource.

---

## 6. Scaling plan and numerical conditioning check

### 6.1 Scaling
Power scale $k_P = 10^{-3}$ (MW→GW), cost scale $k_C = 10^{-6}$ ($→M$). Scaled variables
$\tilde x = k_P x$; scaled objective $\tilde Z = k_C Z$; scaled cost coefficients $\tilde c = c\,k_C/k_P = 10^{-3}c$
(so $/MWh → M$/GWh and $/MW-yr → M$/GW-yr share the factor). Raw duals unscale with
$S = k_P/k_C = 10^3$ (§3). Optional extra objective factor $s_{obj}$ (default 1) is divided out too.

Typical scaled magnitudes (PJM-size, $w_p\in[1,40]$; toys $w\le122$, same bounds hold within $\times4$):
| Item | Range |
|---|---|
| matrix: balance/flow/storage coefficients, $\eta$, $1/\eta$, $A$ | $10^{-3}$ … $1.2$ |
| matrix: DC power flow $B_l$ or PTDF (§7.4a, Gate 3+) | $10^{-3}$ … $10^{2}$ (per-unit on 100 MVA) |
| matrix: duration coefficients $\overline\delta$ (≤ 1000 h for seasonal) | up to $10^3$ |
| objective: $w_p MC$ | $10^{-4}$ … $10$ |
| objective: $w_p\text{VOLL}$ (VOLL ≤ 10 000 $/MWh) | ≤ $4\times10^2$ |
| objective: $C^{fix}$ | $10^{1}$ … $10^{3}$ |
| RHS: demand, existing capacity (GW) | $10^{-3}$ … $2\times10^2$ |

Rules: (a) weights live in the objective only, never in rows; $w_p\ge1$ (§1.2).
(b) Availability/CF values $< 10^{-3}$ are set to 0 at build and counted in the assumptions
book. (c) No big-M: unlimited bounds are $+\infty$, never $10^9$. (d) VOLL enters only the
objective (and later the price-setter check), never a row. (e) Zero-cost VRE is not perturbed
(perturbations corrupt price-setter attribution).

### 6.2 Conditioning check (`capex.audit.conditioning`, every solve)
Reports on the scaled LP: rows, cols, nnz; min/max $|a_{ij}|$ over nonzeros and ratio;
min/max nonzero $|c_j|$, $|b_i|$, finite $|\text{bounds}|$ and ratios; count of coefficients below
$10^{-6}$; after solve: max primal and dual infeasibility (scaled: the units the solver's tolerances act on),
max `bal` residual (unscaled MW), solver status, iteration count, whether crossover ran.
| Metric | Warn | Fail |
|---|---|---|
| matrix ratio $\max|a|/\min|a|$ | $>10^6$ | $>10^9$ |
| objective ratio | $>10^8$ | $>10^{11}$ |
| RHS ratio $\max|b|/\min|b|$ (nonzero finite row bounds) | $>10^6$ | $>10^9$ |
| largest finite variable bound $\max|l_j|,|u_j|$ (absolute, scaled units) | $>10^5$ | $>10^7$ |
| max primal or dual infeasibility (scaled) | $>10^{-7}$ | $>10^{-5}$ |
| max `bal` residual (unscaled MW; Gate 1 toys require $\le10^{-6}$, §3) | $>10^{-3}$ | $>10^{-1}$ |
A **fail** marks the run invalid in the fingerprint; a warn is listed in the health report.
Definitions (DECISIONS 32). Ratios and minima use nonzero finite magnitudes only; $\pm\infty$ bounds are skipped. The bound
metric is a magnitude, not a ratio: it flags big-M-style bounds (rule (c)); the smallest nonzero bound is reported only.
Primal infeasibility = max violation of scaled row and column bounds; dual infeasibility = max of the scaled stationarity
residual $|c - A^\top y - s|$ and any dual-sign violation. Scaled is used because the solver's feasibility tolerances
($10^{-7}$) act there; the unscaled physical check is the `bal` residual row. Note: a $10^{9}$ MW bound is $10^{6}$ scaled
and only warns; rule (c) still forbids it, and the builder must not rely on this check to catch it.

---

## 7. Gate 5–10 extensions (sketch)

Each item: equations at sketch level, ablation switch (config key), accuracy risk (⚠).

### 7.1 Representative periods (Gate 5) — switch `ts.mode ∈ {full_blocks, clustered}`, `ts.n_periods`
- Candidate pool: all consecutive 3-day blocks $j=1..J$ of the year ($J=\lfloor D_y/3\rfloor$); the truncated
  remainder block follows the single rule of §1.2.
- Feature vector per block: hourly zonal load, wind CF, solar CF, net load
  ($D - \sum A^{VRE}K^{VRE}$ at current fleet), the three daily fuel prices (hub gas) — each z-scored,
  feature-group weights in config (`ts.features.*`, each switchable, incl. `ts.features.fuel_price`).
- Clustering: k-medoids (medoids are real blocks: preserves chronology and cross-correlation);
  hierarchical/k-means with medoid representation as alternative (Kotzur et al. 2018a; Hoffmann
  et al. 2020 review). $w_p = |\text{cluster } p|$ (+ remainder fraction).
- **Forced periods** (`ts.forced.peak_load`, `.peak_net_load`, `.min_renewable`, `.max_fuel_price`,
  `.events=[dates]`, e.g. Winter Storm Elliott 2022-12-23..25): removed from the pool before
  clustering, enter with $w_p = 1$ (they represent themselves); weight identity preserved.
- Validation: annual energy, peak, VRE CF, duration curves of load/net load vs full year; the
  one-off full-year fixed-fleet dispatch check (DECISIONS 3).
- ⚠ Medoids under-represent tails inside clusters; 3-day cyclic wrap creates artificial
  end-of-period effects for SOC/UC; fuel-price clustering competes with weather features at fixed $k$.

### 7.2 Inter-period SOC (Gate 5) — switch `storage.inter_period` (per resource flag `long_duration`)
Kotzur et al. (2018b) superposition: chronological sequence $\text{rep}(j)\in\mathcal P$ for actual blocks $j$.
For linked storage, `st_soc` keeps its form but $e^{intra}_{r,p,t}$ is free with $e^{intra}_{r,p,0}=0$ (no cyclic wrap), and
$$E_{r,j+1} = (1-\sigma)^{72}E_{r,j} + e^{intra}_{r,\text{rep}(j),72}\quad(\texttt{st\_link}),\qquad E_{r,J+1}=E_{r,1}$$
$$0 \le E_{r,j} + \underline e_{r,\text{rep}(j)},\quad E_{r,j}+\overline e_{r,\text{rep}(j)}\le E_r\quad(\texttt{st\_link\_lo/hi})$$
with $\underline e_{r,p}\le e^{intra}_{r,p,t}\le\overline e_{r,p}$ (exact for $\sigma=0$; conservative-approximate for $\sigma>0$).
Adds $J\approx122$ variables per resource. Short-duration storage stays intra-cyclic.
Dual of `st_link` = inter-period water value; price-setter `STORAGE_*` uses $v$ from the linked system.
⚠ Pumped hydro in PJM has weekly patterns that 3-day medoids may miss.

### 7.3 Reserves and ORDC shortage pricing (Gate 7) — switches `reserves.enabled`, `reserves.ordc`
Products $k$ (e.g. synchronized, primary/10-min, 30-min), nested $\mathcal K_k$ (higher quality counts toward lower).
Variables $q_{r,k,p,t}\ge0$, shortfall $\delta_{k,s,p,t}\in[0,\Delta_{k,s}]$ on ORDC steps $s$ with penalty $P_{k,s}$.
- `res_head[r,p,t]`: $g + \sum_k q_{r,k} \le A K$ (storage: $d - c + \sum_k q \le P$, and SOC sufficiency $\sum_k q\,\tau_k/\eta^d \le e$).
- `res_ramp[r,k,p,t]`: $q_{r,k} \le RR_r\,\tau_k\,K_r$ (ramp rate × deployment time).
- `res_req[k,a,p,t]` (reserve area $a$): $\sum_{k'\succeq k}\sum_{r\in a} q_{r,k'} + \sum_s \delta_{k,s} \ge \sum_s \Delta_{k,s}$; cost $w_p\sum_s P_{k,s}\delta_{k,s}$.
Dual of `res_req` / $w_p$ = reserve clearing price; energy price picks up reserve opportunity cost
through `res_head`. Price-setter class `RESERVE_ORDC`. PJM ORDC parameters by data lead (post-2022 design).
⚠ Shortage hours are few but dominate scarcity revenue for storage; resolves `CAPACITY_RENT/DEGENERATE` pricing.

### 7.4 Zonal transmission + expansion (Gate 8) — switches `tx.losses`, `tx.hurdle`, `tx.expansion`, `tx.interfaces`
Split $f = f^+ - f^-$, $f^\pm \ge 0$. Losses: receiving end gets $(1-\lambda_l)f^\pm$. Hurdle cost $w_p h_l (f^++f^-)$.
Expansion $y_l\ge0$, cost $\text{ANN}(I_l)+FOM_l$: `flow_ub`: $f^+ \le F^+_l + y_l$, $f^- \le F^-_l + y_l$ (rows when expandable).
Interfaces: `iface[i,p,t]`: $\sum_l \beta_{i,l}(f^+_l-f^-_l)\le \bar F_i$ (PJM transfer interfaces).
⚠ Transport ignores loop flow; intra-zonal congestion (large in PJM) is invisible at zonal resolution.

### 7.4a DC power flow option (Gate 3 PJM 5-bus; owner decision pending, Gate 0 review item 3) — switch `tx.model ∈ {transport, dcpf}`
Nodes $n$ (buses; in zonal runs a zone is a node), lines $l$ with susceptance $B_l$ (per unit, 100 MVA base) and
rating $F_l$. Angle form (default for small systems): free $\theta_{n,p,t}$, `ref_angle`: $\theta_{n_0,p,t}=0$ per island;
`kvl[l,p,t]`: $f_{l,p,t} - B_l(\theta_{o(l)} - \theta_{e(l)}) = 0$; `flow_ub/flow_lb` as in §2 (bounds on $f$).
PTDF form (large systems): $f_{l} = \sum_n \text{PTDF}_{l,n}\,\text{inj}_n$ with `kvl` rows replaced; same duals.
LMP decomposition: $\pi_n = \lambda_{ref} - \sum_l \text{PTDF}_{l,n}\,\mu_l$ (energy + congestion; lossless).
Price-setter: Step 0 islands no longer suffice (loop flow makes $\Delta\pi$ non-zero on unconstrained lines). With
`dcpf` the class `MARGINAL_UNIT` may hold at **several** nodes at once; a node with no local marginal unit is
`CONGESTION_LOOP`: price check $|\pi_n - \sum_{m\in\text{marg}} \alpha_{n,m} MC_m| \le tol_\pi$ where the weights $\alpha$
solve the PTDF system restricted to marginal units and binding lines. Spec completed at Gate 3.
⚠ Zonal PJM runs keep `transport` unless Gate 8 shows `dcpf` improves the scoreboard (ledger row).

### 7.5 Clustered linear UC (Gate 9) — switches `uc.enabled`, `uc.min_updown`, `uc.ramps`
Palmintier & Webster (2014, 2016): per cluster $r$ of identical units of size $\bar P_r$, commitment
$n_{r,p,t}\in[0, K_r/\bar P_r]$ continuous, starts $s$, shutdowns $s'$:
- `uc_state`: $n_t - n_{t^-} = s_t - s'_t$; `uc_gmin/gmax`: $P^{min}_r n_t \le g_t \le A\bar P_r n_t$; `uc_cap`: $n_t \le K_r/\bar P_r$
- `uc_minup`: $\sum_{\tau=t-UT+1}^{t} s_\tau \le n_t$; `uc_mindn`: $\sum_{\tau=t-DT+1}^{t} s'_\tau \le K_r/\bar P_r - n_t$
- `uc_rampup/dn`: $g_t - g_{t^-} \le RU(n_t - s_t) + \max(P^{min},RU)s_t - P^{min}s'_t$ (and symmetric)
- cost $w_p(SC\,s_t + NL\,n_t)$. Price-setter `UC_COMMIT`: interior $n$ → $\pi = MC + NL/\bar P$ (block marginal); `RAMP` when ramp row binds.
⚠ LP relaxation understates cycling cost and min-gen inflexibility (off-peak/negative prices too high/rare);
PJM's fast-start pricing makes LP-relaxation prices a reasonable but not exact analogue.

### 7.6 Policy (Gate 10) — switches `policy.rps`, `policy.ces`, `policy.rggi`, `policy.federal_credits`
- `rps[s]` (state $s$, tier): $\sum_{r\in\text{Elig}_s}\sum_p w_p\sum_t \theta_{r,s}g_{r,p,t} + a_s \ge \kappa_s \sum_p w_p\sum_t\sum_z \beta_{s,z}D_{z,p,t}$,
  ACP slack $a_s\ge0$ at cost $P^{ACP}_s$; dual = REC price ($/MWh). $\theta$ = delivery/eligibility share, $\beta$ = state load share of zone.
- RGGI: backcast mode uses observed allowance prices as adders $MC \mathrel{+}= ER_r\,P^{CO2}_{s(r),y}$ for units in participating
  states in that year (membership by year, e.g. VA exit); forward mode optionally a cap row `co2_cap[s]` with dual = allowance price.
- Federal credits under current law: PTC as negative $MC$ term ($\Rightarrow$ negative prices possible; price-setter must allow $\pi<0$);
  ITC reduces $I$ before `annualize`. Eligibility/phase-out by tech and in-service year encoded by data lead (post-2025 law changes).
⚠ Leakage between RGGI and non-RGGI PJM states is modeled only through zonal resolution.

### 7.7 Build limits and retirements (Gate 10) — switches `build.limits`, `retire.economic`
- `build_lim[g,z]`: $\sum_{r\in \text{tech } g, z} x_r \le B_{g,z,y}$ (queue/interconnection reality; dual = value of one more MW of headroom).
- Economic retirement: $K_r = K^0_r - \text{ret}_r + x_r$, $0\le \text{ret}_r\le K^0_r - K^{keep}_r$; objective adds $GFC_r(K^0_r-\text{ret}_r)$,
  $GFC$ = going-forward cost (FOM + sustaining capex via `annualize`); retire iff rent $< GFC$.
- Announced retirements: $K^0_r=0$ from the retirement date; RMR units: $\text{ret}_r$ upper bound 0.
⚠ Single-year steady-state economics plus missing capacity revenue retire too much: `retire.economic` must stay
off until RPM (Gate 14) exists; backcasts always fix retirements.

### 7.8 Pointer (Gate 12/14)
Offer adders $MC^{offer} = MC + \alpha_{tech,season}$ (calibrated, documented, switch `calib.adders`). RPM: piecewise VRR
demand curve as stepped benefit segments with ELCC-accredited supply $\sum_r \text{ELCC}_r K_r$; dual = capacity price ($/MW-day after conversion).

---

## 8. Audit hooks (`capex.audit` must expose)
1. **Balance residuals** per `bal[z,p,t]`, max/abs-sum.
2. **All duals** raw and economic (§3) with labels, plus column reduced costs.
3. **Binding-constraint report**: per label family, count/share of binding rows (slack $\le tol$) weighted by $w_p$; list of binding bounds (`x_ub`, `flow_*`, `use_ub`).
4. **Objective decomposition**: $Z^{inv}$ by resource, $Z^{var}$ by resource and fuel, $Z^{use}$ by zone, $Z^0$; must sum to $Z$ within $10^{-9}$ relative.
5. **Revenue/rent table** per resource: energy revenue, variable cost, rents $R$, $C^{fix}$, profit; zero-profit flags (§3 check 5–6).
   Column units in data-schema §5 (`rents`). Column `rent_note` = `non-unique (bound)` for every candidate with
   `build_status` = `at_zero` (amendment 3): its column is at the lower bound, so $R$, $R^P$, $R^E$ and `excess_rent`
   are one vertex of a dual interval (cf. T2c, T3a) and must not be read as the cost cut needed to build; empty otherwise.
6. **Storage**: SOC trajectories, cyclic closure residual, **SOC-row recomputation residual** from case data
   (§3 check 8, health check `storage.soc_recompute`), `simul_chdis` hours, water values.
7. **Price-setter report** (§4) and `UNEXPLAINED` count; marginal fuel shares per zone.
8. **Curtailment** and **unserved energy** by zone/period, weighted annual totals.
9. **Conditioning report** (§6.2).
10. **Run fingerprint**: SHA-256 over (canonical input tables: sorted, fixed float repr; config incl. all switches; formulation version string `F-x.y`; git commit + dirty-diff hash; solver name, version, all options; Python and package versions; clustering seed); stored with run id, timestamps, solve time, model size. Same fingerprint ⇒ bit-identical outputs expected.
11. **Assumptions book** (from data layer): provenance mix by parameter, dollar-year conversions, annualization table.
   Starts with the run header of data-sources.md "Assumptions book format" item 1 (run_id and fingerprint equal to
   `run.json`, case, base dollar year); for a case with no input cell whose `method` is observed, derived or estimated,
   the header adds the banner line "Toy case: all inputs assumed; numbers are illustrative, not PJM estimates."
   (amendment 3).

---

## 9. Known accuracy risks / open questions (owner)
- **Q1 Financing — resolved (DECISIONS 22):** ATB-style PFF default, simple CRF optional (§5.2).
- **Q2 Degenerate prices — resolved (DECISIONS 23):** capex-mode prices scored on block/monthly averages until G7.
- **Q3 Base dollar year — resolved (DECISIONS 24):** 2024\$, BEA GDP implicit price deflator.
- **Q4 Scarcity pricing — resolved (DECISIONS 24):** PJM backcasts use PJM's reserve shortage (ORDC) curve (G7);
  VOLL is only the unserved-energy backstop (Gate 1 toys keep a single VOLL).
- **Q5 Leap years and remainder days.** Single fractional-block rule (§1.2) adopted in F-0.2; revisit only if G5
  validation shows a bias.
- **Q6 Storage inverter.** `st_pwr` uses $c+d\le P$ (single inverter). OK for batteries; pumped hydro may need separate pump/turbine ratings.
- Risk: lossless transport and no intra-zonal congestion bias east/west spreads low until G8.
- Risk: no min-gen/UC until G9 → off-peak prices too high, nuclear/coal cycling absent.

---

## 10. Known-answer toy cases
All cases: one zone, one period, $D_y = 365$, $w = 365/3 = 121.\overline{6}$ (each modeled hour = $121.\overline 6$ h;
12 h ⇒ 1460 h/yr), $A=1$, $\sigma=0$, $Z^0 = 0$, no links unless stated. Numbers verified with HiGHS (dual simplex).

### T1 — screening curve, two new thermals + VOLL
Demand: $t=1..36$: 80 MW; $t=37..60$: 120 MW; $t=61..72$: 150 MW (annual durations: 150 MW for 1460 h,
≥120 MW for 4380 h, ≥80 MW for 8760 h). Candidates: Base $C^{fix}=150\,000$ $/MW-yr, $MC=20$; Peaker $C^{fix}=60\,000$, $MC=80$; VOLL $=10\,000$.
Screening: Base/Peaker breakeven at $(150-60)\cdot10^3/(80-20)=1500$ h; Peaker/USE at $60\,000/9\,920 = 6.05$ h.
**Answer:** $x_{Base}=120$, $x_{Peak}=30$ MW, $u=0$. $Z = 18.0+1.8+17.52+3.504 = 40.824$ M$.
Prices (block averages; hourly values within a block are **not unique**):
- off-peak block: $\pi=20$ (`MARGINAL_UNIT` Base);
- peak block: Peaker zero-profit $1460(\bar\pi_{pk}-80)=60\,000\Rightarrow\bar\pi_{pk}=121.096$ (`CAPACITY_RENT/INVESTMENT_MARGIN`);
- mid block: Base zero-profit $1460(\bar\pi_{pk}-20)+2920(\bar\pi_{mid}-20)=150\,000\Rightarrow \bar\pi_{mid}=20+2400/2920=20.822$.
Checks: $\sum w D\pi = Z$ (strong duality); hourly $\pi\in[20,80]$ in mid hours and $\ge 80$ in peak hours.

### T2 — storage arbitrage, two prices
Existing: G1 100 MW $MC=20$; G2 200 MW $MC=60$. Demand $t=1..36$: 50 MW, $t=37..72$: 150 MW.
Storage $\eta^c=\eta^d=0.9$, $VOM=0$, duration 4 h.
- **T2a** existing storage $P^0=10$ MW, $E^0=40$ MWh. Prices 20 / 60 (G1 / G2 marginal). Per period: charge
  $40/0.9 = 44.4\overline4$ MWh, discharge $36$ MWh (hourly schedule not unique). Water value $v = 20/0.9 = 22.2\overline2$ during
  charging, $v = 60\cdot0.9 = 54$ during discharging ($\pi = v/\eta^d$); $R^E = w(54-22.2\overline2) = 3\,866.30$ $/MWh-yr, $R^P = 0$.
  Net revenue $= w(60\cdot36-20\cdot44.4\overline4) = 154\,651.85$ $/yr $= R^E E^0$. $Z = 26\,125\,348.15$ $ (vs 26 280 000 without storage).
- **T2b** candidate storage, $C^P=0$, $C^E=3\,000$, $\underline\delta=\overline\delta=4$, $X^{P,max}=10$, $X^{E,max}=40$: builds 10 MW/40 MWh
  (at bound); combined excess rent $(R^P+4R^E)-(C^P+4C^E) = 4(3\,866.30-3\,000)=3\,465.19$ $/MW-yr $\ge 0$; $Z=26\,280\,000-154\,651.85+120\,000 = 26\,245\,348.15$.
- **T2c** same with $C^E=5\,000$: builds 0; $Z = 26\,280\,000$; prices 20 / 60 (unique, G1 / G2 marginal).
  Storage duals are **dual-degenerate** (§3 check 7): with $P=E=0$, dual feasibility of $c,d,e$ at 0 gives
  $\eta^d(\pi_t-\rho^P_t)\le v_t\le(\pi_t+\rho^P_t)/\eta^c$ and $v_{t^+}-v_t\le\rho^E_t$ (cyclic), so with
  $\rho^P=0$ $v\in[18,22.\overline2]$ in low hours, $[54,66.\overline6]$ in high hours, and $\sum_t\rho^E_t\ge 54-22.\overline2$ per
  period. Hence combined rent $R^P+4R^E\in[4\cdot3\,866.30,\;4\cdot5\,000] = [15\,465.19,\;20\,000]$ $/MW-yr: the lower
  end is the T2a arbitrage value (using $\rho^P>0$ costs more than it saves), the upper end is reduced cost
  $\ge 0$ at $x=0$. Any point is optimal; HiGHS returns 4 380 (scaled) or 5 000 (unscaled) for $R^E$. Tests assert
  the interval (rent $\le$ cost, not $<$), not a point.

### T3 — VOLL-bound
Existing G 100 MW $MC=30$; demand 80 MW except $t=48$: 120 MW; VOLL $=1\,000$; candidate Peaker $MC=100$.
- **T3a** $C^{fix}=150\,000$: breakeven vs USE $150\,000/900=166.7$ h $> 121.\overline6$ h ⇒ $x=0$, $u_{48}=20$ MW,
  $\pi_{48}=1000$ (`VOLL`), other hours $\pi=30$. G rent $=w(1000-30)=118\,016.67$ $/MW-yr; Peaker reduced cost
  $150\,000 - w\cdot900 = 40\,500$. $Z = 23\,530\,333.33$.
- **T3b** $C^{fix}=100\,000$ ($111.1$ h $<121.\overline6$ h): $x=20$, $u=0$, $\pi_{48} = 100 + 100\,000/w = 921.92$
  (`CAPACITY_RENT/INVESTMENT_MARGIN`, unique: single hour). $Z = 23\,340\,333.33$.

### T4 — two zones, binding link
Zone A: G_A existing 1000 MW $MC=20$, $D_A=50$; zone B: G_B 1000 MW $MC=50$, $D_B=100$ (all hours);
link A→B $F^+=F^-=50$. **Answer:** $f=50$ (at `flow_ub`), $g_A=100$, $g_B=50$; $\pi_A=20$, $\pi_B=50$, $\mu=30$ $/MWh;
two islands, B's setter `MARGINAL_UNIT` G_B, A's G_A; congestion rent $= w\cdot72\cdot50\cdot30 = 13\,140\,000$ $/yr;
$Z = 39\,420\,000$.

### References
- Kotzur, L., Markewitz, P., Robinius, M., Stolten, D. (2018a). Impact of different time series aggregation methods on optimal energy system design. *Renewable Energy* 117.
- Kotzur, L., Markewitz, P., Robinius, M., Stolten, D. (2018b). Time series aggregation for energy system design: modeling seasonal storage. *Applied Energy* 213.
- Hoffmann, M., Kotzur, L., Stolten, D., Robinius, M. (2020). A review on time series aggregation methods for energy system models. *Energies* 13(3).
- Palmintier, B., Webster, M. (2014). Heterogeneous unit clustering for efficient operational flexibility modeling. *IEEE Trans. Power Syst.* 29(3).
- Palmintier, B., Webster, M. (2016). Impact of operational flexibility on electricity generation planning with renewable and carbon targets. *IEEE Trans. Sustain. Energy* 7(2).
- NREL Annual Technology Baseline (financing/CRF methodology); BEA NIPA Table 1.1.9 (GDP implicit price deflator).
