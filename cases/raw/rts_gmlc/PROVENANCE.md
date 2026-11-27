# RTS-GMLC raw data — provenance (prep item P1, DRAFT for Gate 4)

- **source_id:** `rts_gmlc` (registry: `docs/data-sources.md`, `data/common/sources.csv`)
- **Upstream:** https://github.com/GridMod/RTS-GMLC (branch `master`)
- **Pinned commit:** `3ece0d3725c844056132393ee252b3083dd4eab4` (committed 2025-10-22T20:33:26-06:00)
- **Retrieved:** 2026-11-26 (shallow `git clone --depth 1` from this cloud workspace)
- **Vintage:** RTS-GMLC as of the pinned commit; time series are calendar year 2020 (hourly DA, 5-min RT)
- **method:** `observed` · **basis:** "published test-system value" · **confidence:** high (for the system as published)
- **Files unmodified.** Paths below mirror the upstream repo layout exactly.

## What is vendored here (43 files, ~9 MB) and why
Full repo at the pinned commit is 209 files / 218 MB (mostly tool-specific formats and 5-min RT series), too large to
commit. Vendored = what Gates 4–5 need:

| Upstream path | Use |
|---|---|
| `RTS_Data/SourceData/*.csv` (bus, branch, dc_branch, gen, storage, reserves, simulation_objects, timeseries_pointers) + `README.md` | Network, units (heat-rate curves, PMin, ramps, fuel, VOM, starts), storage, reserves, series pointers |
| `RTS_Data/SourceData/HR_data/*` (csv, R, README; PNGs skipped) | Heat-rate fit provenance (`Final_Fits.csv`, `gen_oldHRs.csv`) |
| `RTS_Data/timeseries_data_files/*/DAY_AHEAD_*.csv` + `README.md` | Hourly 2020 regional load, PV, RTPV, wind, hydro, CSP inflow, reserve requirements |
| `RTS_Data/FormattedData/PLEXOS/PLEXOS_Solution/DAY_AHEAD Solution Files/{allTX,noTX}/PLEXOS_DA_solution_*.csv` + `README.md` | **Published reference results** (PLEXOS DA: price, generation, commitment, flow, cost) for the Gate 4 fixed-fleet dispatch comparison |
| `README.md`, `RTS-GMLC_updates.md`, `RTS_Data/README.md` | Upstream documentation |

Not vendored: `REAL_TIME_*` 5-min series, other `FormattedData/*` tool formats (MATPOWER, PSS/E, PSO, openTEPES …),
`RTS-GMLC.pdf`, images, Load `origin/` files. Two git submodules (PIDG, MAGMA) were not fetched (tooling only).

## Integrity
`MANIFEST.csv` lists **every** file at the pinned commit: path, bytes, sha256, git mode, `vendored` yes/no. All 43
vendored files were re-hashed after copy and match. To recover a non-vendored file:
`git clone https://github.com/GridMod/RTS-GMLC && git -C RTS-GMLC checkout 3ece0d3725c844056132393ee252b3083dd4eab4`,
then check its sha256 against `MANIFEST.csv`.

## Licence — needs verification
No `LICENSE` file exists in the repo at the pinned commit, and the README states no licence terms. The earlier registry
note ("BSD-style at last check") could not be confirmed. RTS-GMLC is a DOE-lab-consortium public test system widely
redistributed (e.g. PowerModels, PowerSystems.jl, PyPSA examples), but **redistribution terms are unverified**.
Until confirmed: treat as `license_class=verify`, keep it to internal test use, and cite
Barrows et al., "The IEEE Reliability Test System: A Proposed 2019 Update," *IEEE Trans. Power Systems* 35(1), 2020
(verify citation details). Owner question raised in PLAN.md "Needs owner".

## Notes for P5 (conversion to data-schema.md)
- `gen.csv` has 157 units, `storage.csv` 22 rows, `bus.csv` 73 buses in 3 areas; `timeseries_pointers.csv` maps
  each series to its object (DA and RT).
- Costs and fuel prices are as published (dollar year not stated upstream → P5 must record `dollar_year` with
  `method=assumed` and say so in `basis`).
- Reference results exist for two cases: `allTX` (with transmission limits) and `noTX` (copper-plate).
