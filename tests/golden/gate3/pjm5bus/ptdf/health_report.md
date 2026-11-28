# Health report: pjm5bus
Overall: **pass**

| check | status | value | tolerance | detail |
|---|---|---|---|---|
| solver.optimal | pass | 0 | 0 | Optimal |
| balance | pass | 5.11591e-13 | 1e-06 | max |LHS-D| MW |
| strong_duality | pass | 0 | 1e-07 | primal 153123897.066338 dual 153123897.066338 $ (excl. Z0) |
| comp_slack | pass | 0 | 1e-08 |  |
| dual_sign | pass | 0 | 1e-09 |  |
| zero_profit | pass | 0 | 0 | all candidates ok |
| revenue_identity | pass | 3.64636e-16 | 1e-06 |  |
| storage_reduced_costs | pass | 0 | 1e-06 | recomputed vs solver reduced costs of xP, xE (scaled units) |
| decomposition | pass | 1.94629e-16 | 1e-09 | Z total 153123897.066338 incl. Z0 0.000000 |
| storage.closure | pass | 0 | 1e-06 | cyclic energy closure, MWh |
| storage.soc_recompute | pass | 0 | 1e-06 | st_soc residual recomputed from case eta_c, eta_d, sigma, MWh |
| storage.simul_chdis | pass | 0 | nan | hours with simultaneous charge and discharge (not an error) |
| basis_valid | pass | 0 | 0 | basic solution required (section 4) |
| price_setter.unexplained | pass | 0 | 0 | UNEXPLAINED zone-hours |
| price_setter.link_inconsistent | pass | 0 | 0 | n/a under dcpf (see lmp.decomposition, dcpf.line_duals) |
| price_setter.shares_sum_to_one | pass | 0 | 1e-09 |  |
| price_setter.loop_alpha | pass | 2.4869e-14 | 1e-06 | max(|sum alpha - 1|, |pi - sum alpha c|) over CONGESTION_LOOP |
| conditioning.matrix_ratio | pass | 29.0879 | 1e+06 | warn>1e+06 fail>1e+09 |
| conditioning.objective_ratio | pass | 1000 | 1e+08 | warn>1e+08 fail>1e+11 |
| conditioning.rhs_ratio | pass | 25 | 1e+06 | warn>1e+06 fail>1e+09 |
| conditioning.bound_max | pass | 0.4 | 100000 | warn>100000 fail>1e+07 |
| conditioning.primal_infeasibility | pass | 0 | 1e-07 | warn>1e-07 fail>1e-05 |
| conditioning.dual_infeasibility | pass | 1.11022e-15 | 1e-07 | warn>1e-07 fail>1e-05 |
| conditioning.bal_residual_mw | pass | 5.11591e-13 | 0.001 | warn>0.001 fail>0.1 |
| kvl.recompute | pass | 8.52651e-14 | 1e-06 | max |f - b(theta_o - theta_e)| MW, case b, theta from output angles |
| ptdf.recompute | pass | 8.52651e-14 | 1e-06 | max |f - f_rc| MW, f_rc from B_red theta = inj (case b, solved inj) |
| lmp.decomposition | pass | 7.10543e-15 | 1e-06 | max |pi - (lambda - sum_l H mu)| $/MWh, H from case data |
| congestion_rent | pass | 7.29673e-16 | 1e-07 | max |sum pi (-inj) - sum mu f| / max(1, |sum mu f|) |
| dcpf.line_duals | pass | 0 | 1e-06 | mu != 0 only at a rating, mu sgn f >= 0 |
| dcpf.islands | pass | 0 | 0 | 1 islands: i1 ref A |
