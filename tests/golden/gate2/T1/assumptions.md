# Assumptions book: T1

- run_id: 2b2dc0e48cad475ab2ab461a2f17f109
- fingerprint: 99271be394eb1ff9bfa71857887de63227de7b471e89d689f29d4c8742982a30
- case: T1
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
       base       cap            2024              1.0  0.0 NaN NaN NaN    NaN  NaN  NaN  NaN 150000.0 cfix_override
     peaker       cap            2024              1.0  0.0 NaN NaN NaN    NaN  NaN  NaN  NaN  60000.0 cfix_override

## Counts

                      item      value
                     zones   1.000000
                   periods   1.000000
                     links   0.000000
     resources_thermal_vre   2.000000
         resources_storage   0.000000
                candidates   2.000000
            cfix_overrides   2.000000
availability_values_zeroed   0.000000
         weight_sum_blocks 121.666667
