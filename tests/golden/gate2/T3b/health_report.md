# Health report: T3b
Overall: **pass**

| check | status | value | tolerance | detail |
|---|---|---|---|---|
| solver.optimal | pass | 0 | 0 | Optimal |
| balance | pass | 1.42109e-14 | 1e-06 | max |LHS-D| MW |
| strong_duality | pass | 1.52213e-16 | 1e-07 | primal 23340333.333333 dual 23340333.333333 $ (excl. Z0) |
| comp_slack | pass | 0 | 1e-08 |  |
| dual_sign | pass | 0 | 1e-09 |  |
| zero_profit | pass | 0 | 0 | all candidates ok |
| revenue_identity | pass | 0 | 1e-06 |  |
| storage_reduced_costs | pass | 0 | 1e-06 | recomputed vs solver reduced costs of xP, xE (scaled units) |
| decomposition | pass | 0 | 1e-09 | Z total 23340333.333333 incl. Z0 0.000000 |
| storage.closure | pass | 0 | 1e-06 | cyclic energy closure, MWh |
| storage.soc_recompute | pass | 0 | 1e-06 | st_soc residual recomputed from case eta_c, eta_d, sigma, MWh |
| storage.simul_chdis | pass | 0 | nan | hours with simultaneous charge and discharge (not an error) |
| basis_valid | pass | 0 | 0 | basic solution required (section 4) |
| price_setter.unexplained | pass | 0 | 0 | UNEXPLAINED zone-hours |
| price_setter.link_inconsistent | pass | 0 | 0 | link-hours with inconsistent price gap / bound / congestion rent |
| price_setter.shares_sum_to_one | pass | 0 | 1e-09 |  |
| conditioning.matrix_ratio | pass | 1 | 1e+06 | warn>1e+06 fail>1e+09 |
| conditioning.objective_ratio | pass | 33.3333 | 1e+08 | warn>1e+08 fail>1e+11 |
| conditioning.rhs_ratio | pass | 1.5 | 1e+06 | warn>1e+06 fail>1e+09 |
| conditioning.bound_max | pass | 0.12 | 100000 | warn>100000 fail>1e+07 |
| conditioning.primal_infeasibility | pass | 0 | 1e-07 | warn>1e-07 fail>1e-05 |
| conditioning.dual_infeasibility | pass | 5.32907e-15 | 1e-07 | warn>1e-07 fail>1e-05 |
| conditioning.bal_residual_mw | pass | 1.42109e-14 | 0.001 | warn>0.001 fail>0.1 |
