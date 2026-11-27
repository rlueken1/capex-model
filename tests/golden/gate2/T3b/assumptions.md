# Assumptions book: T3b

- run_id: d18940f2b27a44329f075a82c846b9b4
- fingerprint: c7b3493a0a306f3081bd92c75ff1035aba88b8b9d77b3fc1aa4a4da53816668d
- case: T3b
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
     peaker       cap            2024              1.0  0.0 NaN NaN NaN    NaN  NaN  NaN  NaN 100000.0 cfix_override

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
