# Gate 3 — PJM 5-bus (DC power flow option): exit criteria

Status: **APPROVED by owner 2026-11-27 (DECISIONS 47)** — dispatch tolerance 0.01 MW, P5e load scan kept, §4a carried items added.
Gate numbers use the renumbering of DECISIONS 43. Default network model stays `transport` (pipe-and-bubble); `dcpf` is an option only.
Criteria are frozen once approved (docs/gates/README.md). Branch `gate-3`, created from `gate-2`.
Spec: formulation §7.4a (`tx.model ∈ {transport, dcpf}`), which this gate must first **complete** (see §6, item W-spec).
DECISIONS 29: DC power flow is built here only as an **option**; `transport` stays the default everywhere.

## 1. Scope
In: `tx.model = dcpf` in angle form (required) and PTDF form (required, equal results); `CONGESTION_LOOP` price-setter
class and the LMP decomposition (energy + congestion, lossless); `links.csv` network fields `reactance_pu`, `base_mva`
(data-schema §3.2, reserved since G0); the `pjm5` case (`cases/pjm5bus/`, built from `cases/raw/pjm5bus/`, prep item P3)
with provenance; a fixed-fleet (no-build) run mode for test systems if not already supported.
Out: losses, hurdles, interfaces, expansion (Gate 10), reserves (Gate 9), UC (Gate 11), any PJM market data.

## 2. Reference case `pjm5` (source: Li & Bo 2010; MATPOWER `case5`)
Values below were written from memory and **reproduced in this draft by an independent scipy `linprog(highs)` DC-OPF**
(2026-11-26); P3 must confirm every input against the pinned source file and Li & Bo Table/Fig. before approval (verify).
- Buses A–E (MATPOWER 1–5). Loads (MW): B 300, C 300, D 400 (A, E 0); total 1000.
- Generators (MW max, $/MWh linear cost, no min gen): Alta A 40 @14; Park City A 170 @15; Solitude C 520 @30;
  Sundance D 200 @40; Brighton E 600 @10.
- Lines (x pu on 100 MVA; rating MW, blank = unlimited): A–B 0.0281 / 400; A–D 0.0304; A–E 0.0064; B–C 0.0108;
  C–D 0.0297; D–E 0.0297 / 240.
- Model mapping: one 3-day period, 72 identical hours, $w = D_y/3$ (load validation), existing units only
  ($X^{max}=0$), VOLL as the general case default (must not bind), dollar year 2024 (case is unitless-$ in the
  source; method `assumed`, noted in the assumptions book).

**Expected per-hour solution** (published, rounded; reproduced by the independent solve):
| Quantity | A | B | C | D | E |
|---|---|---|---|---|---|
| LMP ($/MWh) | 16.98 | 26.38 | 30.00 | 39.94 | 10.00 |
| Dispatch (MW) | Alta 40, Park City 170 | – | Solitude 323.49 | Sundance 0 | Brighton 466.51 |

Binding: only D–E at its 240 MW limit (flow E→D). Hourly cost 17,479.90 $/h. Merchandising (congestion) surplus
$\sum_n \pi_n(D_n-G_n)$ = 14,957.28 $/h, so the D–E shadow price is ≈ 62.32 $/MWh (derived here; verify).
Marginal units: Solitude (C) and Brighton (E); A, B, D have no local marginal unit (loop-flow prices).

## 3. Known-answer tests (verifier, from the spec; expected values computed in the test by an independent route)
Independent route = a DC-OPF written in the test from the case CSVs with `scipy.optimize.linprog(method="highs")`,
never calling `capex` model-building code. Tolerances: objective rel 1e-7; dispatch abs 1e-4 MW; LMP abs 1e-4 $/MWh
vs the independent route; and vs the **published rounded values** LMP abs 0.01 $/MWh, dispatch abs 0.01 MW
(owner approved 0.01 MW for this case, DECISIONS 47; benchmarks.md §6's 0.1 MW stays the general default).

| Case | Must reproduce | Expected price-setter report |
|---|---|---|
| P5a base (`dcpf`, angle form) | §2 table; only D–E binding; annual Z = 17,479.90 × 24 × $D_y$ (rel 1e-7 vs independent) | C: MARGINAL_UNIT Solitude; E: MARGINAL_UNIT Brighton; A, B, D: CONGESTION_LOOP with weights α over {Solitude, Brighton}, $\sum_m\alpha_{n,m}=1$, price check within $tol_\pi$; UNEXPLAINED = 0 |
| P5b PTDF form | identical primal and LMPs to P5a (rel 1e-9 / abs 1e-6) | identical to P5a |
| P5c reference-bus invariance | re-run P5a with each of the 5 buses as reference: LMPs and dispatch unchanged (abs 1e-6); energy component λ_ref changes, congestion components shift by the same constant | unchanged |
| P5d uncongested | P5a with the D–E limit removed: one price 30.00 at all buses; Brighton 600, Alta 40, Park City 170, Solitude 190 | all buses MARGINAL_UNIT Solitude (one island); no binding line |
| P5e load scan | 72 hours with load scaled by factors 0.50…1.10 (fixed list in the test); every hour vs the independent route | UNEXPLAINED = 0 every hour; class per bus-hour equals the class derived from the independent solution's marginal set and binding lines |
| P5f transport contrast | same case with `tx.model = transport` (NTC = rating): reported, not judged; evidence shows the flow and LMP differences | reported |

## 4. Health checks (all Gate 1 checks, gate-1.md §3, keep their thresholds) plus
| Check | Pass rule |
|---|---|
| KVL recomputation | recompute $f_l - B_l(\theta_o-\theta_e)$ from case reactances (not the LP matrix), every line-hour ≤ 1e-6 MW (same idea as `storage.soc_recompute`, DECISIONS 31) |
| PTDF recomputation | PTDF built from case data reproduces the solved flows from solved injections, ≤ 1e-6 MW |
| LMP decomposition | $\lvert\pi_n - (\lambda_{ref} - \sum_l \text{PTDF}_{l,n}\mu_l)\rvert \le 10^{-6}$ every bus-hour; congestion component 0 at every bus in P5d |
| Congestion rent identity | $\sum_n \pi_n(D_n - G_n) = \sum_l \mu_l f_l$ per hour, rel 1e-7 |
| Line duals | $\mu_l \ne 0$ only on lines at a rating (complementary slackness, §3 sign table extended to `flow_ub/flow_lb` under `dcpf`) |
| Islands | a case with two electrically separate parts (fixture) gets one reference angle per island; `ref_angle` count = island count |
| Conditioning (§6.2) | no `warn`/`fail` on P5a–P5e (B up to 1/0.0064 = 156 pu; scaling per §6.1 must handle it) |
| Ranged rows | if PTDF writes flow limits as ranged rows, the F5 fix (gate-2.md §4) is in and its adapter test passes |
| Default unchanged | with `tx.model = transport` (default) all Gate 1 tests and fingerprints of T1–T4 are unchanged except for the config field that records `tx.model` |

Audit-mutation tests (verifier): require at least one check to fail for each of (M7) one reactance scaled by 1.01 in
the LP only; (M8) a `kvl` row sign flip; (M9) wrong reference bus row dropped (angles free → must be detected, not
silently solved); (M10) one line's μ sign flipped in the adapter.

## 4a. Carried items (DECISIONS 42, Gate 2 review items 8–9)
| ID | Item | Pass rule |
|---|---|---|
| K1 | data-download job prints `provenance.json` and per-file sha256 to the job log | a `pjm5` dispatch log shows every field and hash |
| K2 | verifier test: `cases/raw/pjm5bus/case5.m` sha256 equals `data/manifests/pjm5.csv` | test passes; fails if the file changes |
| K3 | GitHub Actions bumped off Node 20 (`checkout`, `setup-python`, `upload/download-artifact` current majors) | CI and a `pjm5` dispatch green, no Node 20 warning |

## 5. Evidence file `reports/gate-3-evidence.md`
As gate-1.md §5, plus: P5a–P5f expected vs obtained with margins; the per-bus LMP decomposition table for P5a;
price-setter table with α weights; source-file hashes and P3 provenance for `pjm5`; the transport-vs-dcpf
contrast (P5f); runtime and problem size of `dcpf` vs `transport` (complexity ledger row `tx.model`, reported not gated
until Gate 5 rules apply).

## 6. Work order (proposed; PM confirms at Gate 3 scrum)
W-spec Formulation lead [Opus]: complete §7.4a — `kvl` row and `ref_angle` labels and signs, PTDF construction and
island handling, μ sign convention under `dcpf`, exact `CONGESTION_LOOP` definition (α from the PTDF system restricted
to marginal units and binding lines; degenerate cases when |marginal| ≠ |binding| + 1 → `DEGENERATE` sub-tag with the
interval), data-schema `links.csv` validation (reactance > 0 when `dcpf`). One DECISIONS entry; version → F-0.3.
→ Verifier tests (from the spec) → Builder → Verifier evidence → Formulation trace → Markets reviewer [Opus] (LMP and
congestion narrative vs Li & Bo; PJM practice: LMP = energy + congestion + loss, loss = 0 here) → PM decision list.

## 7. Review and sign-off — decision list (format as gate-1.md §6)
Required items: (1) P5a–P5f within tolerance and published LMPs matched at 0.01? (2) all health checks pass,
UNEXPLAINED = 0, CONGESTION_LOOP weights correct? (3) mutation tests M7–M10 all caught? (4) `transport` default and all
Gate 1 results unchanged? (5) §7.4a completion and F-0.3 accepted? (6) `pjm5` provenance complete (P3 source and
licence noted)? (7) keep `dcpf` as an option for Gate 4 RTS-GMLC (which has line data) — yes/no? (8) merge `gate-3`
to `main` and mark Gate 3 DONE?
Owner answers (2026-11-27, DECISIONS 47): dispatch tolerance 0.01 MW — yes; P5e load scan — keep.
