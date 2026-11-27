# Assumptions book: T2b

- run_id: e6d7dd9a2298437f9f75dc58e3c9fae5
- fingerprint: 51d3dc0f65bb8db069ad7e0a35928a7cd3f432508f8e6965dfeba858d5ffe1a6
- case: T2b
- base dollar year: 2024
Toy case: all inputs assumed; numbers are illustrative, not PJM estimates.

## Provenance mix

    table  method confidence  rows
load_meta assumed        low     1
resources assumed        low     3
  finance assumed        low     1
 deflator assumed        low     1

## Dollar-year conversions to base 2024$

 dollar_year  factor
        2024     1.0

## Annualization table (formulation 5.2)

resource_id component  dollar_year_in  deflator_factor  fom   I   r   n  kappa  pff  crf  ann   cfix         basis
        bat         P            2024              1.0  0.0 NaN NaN NaN    NaN  NaN  NaN  NaN    0.0 cfix_override
        bat         E            2024              1.0  0.0 NaN NaN NaN    NaN  NaN  NaN  NaN 3000.0 cfix_override

## Counts

                      item      value
                     zones   1.000000
                   periods   1.000000
                     links   0.000000
     resources_thermal_vre   2.000000
         resources_storage   1.000000
                candidates   1.000000
            cfix_overrides   2.000000
availability_values_zeroed   0.000000
         weight_sum_blocks 121.666667
