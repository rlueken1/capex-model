# pjm5bus — PJM 5-bus test system (Gate 3)

Fixed-fleet DC power flow known-answer case: F. Li and R. Bo (2010) via MATPOWER `case5.m`, tables built from the parsed
`cases/raw/pjm5bus/case5_{buses,gens,branches}.csv` (sha256 of `case5.m` pinned in `cases/raw/pjm5bus/MANIFEST.csv` and
`data/manifests/pjm5.csv`). Default switch in `case.yaml`: `tx.model: dcpf` (angle form, reference bus A); `tx.dcpf_form`
and `tx.ref_bus` are absent so their defaults apply (formulation 7.4a.1).

- Zones A-E = MATPOWER buses 1-5; resources `alta, park_city, solitude, sundance, brighton` = gen rows 1-5 (Li & Bo names);
  links `ab, ad, ae, bc, cd, de` = branch rows 1-6 (from -> to as in `case5.m`).
- `ntc_fwd_mw = ntc_rev_mw = rateA`; MATPOWER rateA = 0 (unlimited) is a blank cell. `reactance_pu` = branch x, `base_mva` = 100.
- One period `p1`, 72 identical hours, `model_year 2025` (weight 365/3), no candidates (`xmax_mw = 0`).
- Provenance: every row `source_id = pjm5`, method `observed`, confidence `high`; the exceptions (dollar year 2024 assumed,
  blank = unlimited rating) are listed per cell in `provenance_cells.csv`. Data-terms caveat: `cases/raw/pjm5bus/README.md`.
- Own `sources.csv`: appending `pjm5` to the shared `data/common/sources.csv` would change the `sources` fingerprint
  component of T1-T4 (formulation 7.4a.9 identity).
