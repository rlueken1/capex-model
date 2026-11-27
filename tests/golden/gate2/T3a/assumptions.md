# Assumptions book: T3a

- run_id: 249a09ced8794981afc5a164a64c2895
- fingerprint: cd3d32038ac4797c0c57ce26dd617f2ebc4a145ad67aba91de117fc3c1e4f52a
- case: T3a
- base dollar year: 2024
Toy case: all inputs assumed; numbers are illustrative, not PJM estimates.

## Provenance mix

    table  method confidence  rows
load_meta assumed        low     1
resources assumed        low     2
  finance assumed        low     1
 deflator assumed        low     1

## Dollar-year conversions to base 2024$

 dollar_year  factor
        2024     1.0

## Annualization table (formulation 5.2)

resource_id component  dollar_year_in  deflator_factor  fom   I   r   n  kappa  pff  crf  ann     cfix         basis
     peaker       cap            2024              1.0  0.0 NaN NaN NaN    NaN  NaN  NaN  NaN 150000.0 cfix_override

## Counts

                      item      value
                     zones   1.000000
                   periods   1.000000
                     links   0.000000
     resources_thermal_vre   2.000000
         resources_storage   0.000000
                candidates   1.000000
            cfix_overrides   1.000000
availability_values_zeroed   0.000000
         weight_sum_blocks 121.666667
