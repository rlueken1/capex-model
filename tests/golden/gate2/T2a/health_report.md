# Health report: T2a
Overall: **pass**

| check | status | value | tolerance | detail |
|---|---|---|---|---|
| solver.optimal | pass | 0 | 0 | Optimal |
| balance | pass | 3.41061e-13 | 1e-06 | max |LHS-D| MW |
| strong_duality | pass | 2.71974e-16 | 1e-07 | primal 26125348.148148 dual 26125348.148148 $ (excl. Z0) |
| comp_slack | pass | 0 | 1e-08 |  |
| dual_sign | pass | 0 | 1e-09 |  |
| zero_profit | pass | 0 | 0 | all candidates ok |
| revenue_identity | pass | 2.07008e-15 | 1e-06 |  |
| storage_reduced_costs | pass | 0 | 1e-06 | recomputed vs solver reduced costs of xP, xE (scaled units) |
| decomposition | pass | 0 | 1e-09 | Z total 26125348.148148 incl. Z0 0.000000 |
| storage.closure | pass | 4.9738e-14 | 1e-06 | cyclic energy closure, MWh |
| storage.soc_recompute | pass | 1.59872e-14 | 1e-06 | st_soc residual recomputed from case eta_c, eta_d, sigma, MWh |
| storage.simul_chdis | pass | 0 | nan | hours with simultaneous charge and discharge (not an error) |
| basis_valid | pass | 0 | 0 | basic solution required (section 4) |
| price_setter.unexplained | pass | 0 | 0 | UNEXPLAINED zone-hours |
| price_setter.link_inconsistent | pass | 0 | 0 | link-hours with inconsistent price gap / bound / congestion rent |
| price_setter.shares_sum_to_one | pass | 0 | 1e-09 |  |
| conditioning.matrix_ratio | pass | 1.23457 | 1e+06 | warn>1e+06 fail>1e+09 |
| conditioning.objective_ratio | pass | 500 | 1e+08 | warn>1e+08 fail>1e+11 |
| conditioning.rhs_ratio | pass | 20 | 1e+06 | warn>1e+06 fail>1e+09 |
| conditioning.bound_max | pass | 0.15 | 100000 | warn>100000 fail>1e+07 |
| conditioning.primal_infeasibility | pass | 0 | 1e-07 | warn>1e-07 fail>1e-05 |
| conditioning.dual_infeasibility | pass | 4.44089e-16 | 1e-07 | warn>1e-07 fail>1e-05 |
| conditioning.bal_residual_mw | pass | 3.41061e-13 | 0.001 | warn>0.001 fail>0.1 |
