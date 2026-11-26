# PJM 5-bus raw data (prep item P3)

- **source_id:** `pjm5` (registry: `docs/data-sources.md`)
- **Primary file:** `case5.m`, MATPOWER `data/case5.m` (https://github.com/MATPOWER/matpower). Header: "modified 5 bus, 5 gen case based on PJM 5-bus system", based on F. Li and R. Bo, "Small Test Systems for Power System Economic Studies," Proc. 2010 IEEE PES General Meeting; "Created by Rui Bo in 2006, modified in 2010, 2014. Distributed with permission."
- **Retrieved:** 2026-11-26 from `raw.githubusercontent.com/.../master/data/case5.m`. `git ls-remote` HEAD at retrieval was `b6c85b0323d20fb801cab3377c803a285d730847`; this is the repo HEAD, **not** the last commit touching the file (GitHub API was not reachable). The file's sha256 below is the real pin; the SHA is the nearest recoverable repo state.
- **Vintage:** MATPOWER master as of 2026-11-26 (file header: modified 2014); Li & Bo 2010.
- **method:** `observed` (published test-system value) · **basis:** "published test-system value" · **confidence:** high for the system as published. Dollar year unspecified in the source (unitless $), see gate-3.md §2.
- **Files are unmodified.** sha256/bytes/URLs in `MANIFEST.csv`.

## Files
| File | What |
|---|---|
| `case5.m` | MATPOWER case5, unmodified (primary) |
| `LICENSE_MATPOWER` | MATPOWER LICENSE, unmodified |
| `powermodels_case5.m` | PowerModels.jl test copy, cross-check only (a *different* test case, see below); not a model input |
| `case5_buses.csv`, `case5_gens.csv`, `case5_branches.csv` | Plain parse of `case5.m` (parser: scratchpad `parse5.py`, run `python -I`). Generator names (Alta, Park City, Solitude, Sundance, Brighton) and bus letters A-E are **not in the file**; they come from Li & Bo and are mapped by row order (see caveat) |
| `case5_dcopf_check.csv` | Independent scipy/HiGHS DC-OPF on the parsed data (angle form, ref bus 1): cost, dispatch, LMPs, flows |

## Licence
MATPOWER LICENSE: code is 3-clause BSD, **but "The MATPOWER case files distributed with MATPOWER are not covered by the BSD license. In most cases, the data has either been included with permission or has been converted from data available from a public source."** `case5.m` says "Distributed with permission." So the case file's redistribution terms are **not** BSD; permission from the author is stated but its scope is not documented. 5 buses of published test data are widely redistributed (PowerModels, pandapower etc.), but treat as `license_class=verify`: internal test use; cite Li & Bo 2010 and MATPOWER. Owner may wish to decide whether to keep the raw file in a client-facing repo.

## Verification of gate-3.md section 2 against `case5.m`
| Item | gate-3.md | case5.m | Match |
|---|---|---|---|
| Loads (MW) | B 300, C 300, D 400, A/E 0 | bus2 300, bus3 300, bus4 400, bus1/5 0 | yes |
| Alta | A, 40 MW, $14 | gen1 bus1, Pmax 40, c1 14 | yes |
| Park City | A, 170 MW, $15 | gen2 bus1, Pmax 170, c1 15 | yes |
| Solitude | C, 520 MW, $30 | gen3 bus3, Pmax 520, c1 30 | yes |
| Sundance | D, 200 MW, $40 | gen4 bus4, Pmax 200, c1 40 | yes |
| Brighton | E, 600 MW, $10 | gen5 bus5, Pmax 600, c1 10 | yes |
| Pmin, startup, no-load | none | Pmin 0; startup/shutdown 0; c0 0 | yes |
| x (pu, 100 MVA) | A-B .0281, A-D .0304, A-E .0064, B-C .0108, C-D .0297, D-E .0297 | identical | yes |
| Limits | A-B 400, D-E 240, others unlimited | rateA 400 and 240; 0 = unlimited elsewhere | yes |
| Published dispatch | Solitude 323.49, Brighton 466.51 | `Pg` column 323.49 / 466.51 | yes |
| LMPs 16.98/26.38/30.00/39.94/10.00 | stated | my DC-OPF on the parsed data: 16.9774/26.3845/30.0000/39.9427/10.0000; cost 17,479.897; D-E binding at 240 (E to D), A-B flow 249.7 (not binding) | yes (to 0.01) |

**No discrepancies in gate-3.md's inputs.** Notes (not discrepancies):
1. The mapping of names and letters is by row order: case5.m gives only bus numbers 1-5 and generator rows; the names come from Li & Bo, which could not be fetched (IEEE paywall). Mapping is consistent with the gate-3 table and with costs. Owner download (needs owner): Li & Bo 2010 paper only if the names/letters or their published LMP table must be quoted directly; the reference LMPs are here reproduced independently from `case5.m`, so not required for the gate.
2. case5.m header says "5 gen", and includes `r`, `b`, Q data and bounds (angmin/angmax +/-360) not used by the DC case. rateA = 0 means unlimited in MATPOWER.
3. case5.m `Pg` column is the OPF solution baked into the file, so it doubles as the published dispatch check.
4. gate-3.md's "D-E shadow price ~62.32" is a derived value, not in the file, and was not re-derived here (the check file reports LMPs and flows only).

## PowerModels copy (cross-check): differs, do not use as the source
`powermodels_case5.m` is a modified test fixture (header: "used in tests of non-contiguous bus ids, transformer orientation swapping, ..."): bus 5 renumbered 10, two shifted-transformer branches (3-4 and 4-3, ratio 1.05, angle +/-1), 7 branches, rateA 426 on lines that are unlimited in MATPOWER, angle limits +/-30 deg, extra dummy gencost rows, quadratic cost terms, solved voltages/Q values. Costs, Pmax and loads match MATPOWER; the network differs. Using it would change the congestion pattern. Primary source is MATPOWER.

## Needs owner
- Confirm acceptable licence handling of `case5.m` (data not BSD; "distributed with permission").
- Optional: Li & Bo 2010 paper (IEEE, paywalled) to confirm names/letters and their printed LMP table.
