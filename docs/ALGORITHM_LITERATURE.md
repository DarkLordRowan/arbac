# Literature and provenance of accelerator implementations

This index is **generated from explicit per-class `LITERATURE` metadata**.
Every registered accelerator is linked to a published source describing the
underlying **family, model or construction**. A reference does **not** by
itself establish that all implementation details, default parameters and
exception-handling policies are identical to the publication.

Provenance codes: `literature_family` = published family; `local_variant` =
local algorithm/evaluation policy built on that family; `local_extension` =
locally generalized mathematical model; `implementation_variant` = alternative
evaluator of one transformation; `alias` = other name of the same method;
`legacy_name` = historical ID with corrected attribution; `attribution_pending`
= exact historical identity must be established; `model_assisted` = needs extra
information not available to an ordinary black-box accelerator.

**Special warning:** `levin_sidi_s` equals a Weniger-style factorial
quotient in the tested parameter setting. The link to Sidi ch. 19 is a
**candidate for formal comparison**, not a verified formula attribution.
Do not cite Sidi S as a proven independent algorithm merely on the basis
of the registered class name.

Дополнительная независимая программная проверка: [LEVIN_SIDI_S_VERIFICATION.md](LEVIN_SIDI_S_VERIFICATION.md).

## Registered accelerators

| ID | Code | Bibliography / locator | Attribution |
|---|---|---|---|
| `aitken_backtracking` | `history_transforms.py` | [Sidi, Practical Extrapolation Methods, Cambridge University Press (2003)](https://doi.org/10.1017/CBO9780511546815); ch. 15 (Delta-squared processes) | `local_variant` |
| `aitken_delta2` | `aitken.py` | [Sidi, Practical Extrapolation Methods, Cambridge University Press (2003)](https://doi.org/10.1017/CBO9780511546815); ch. 15 (Delta-squared processes) | `literature_family` |
| `anderson` | `history_transforms.py` | [Walker & Ni, Anderson Acceleration for Fixed-Point Iterations, SIAM J. Numer. Anal. 49 (2011)](https://doi.org/10.1137/10078356X); fixed-point acceleration background; scalar observed-pair variant here | `local_variant` |
| `brezinski_e` | `brezinski_e_general.py` | [Fdil, Some results on convergence acceleration for the E-algorithm, Applicationes Mathematicae 24(4) (1997)](https://matwbn.icm.edu.pl/ksiazki/zm/zm24/zm2443.pdf); section 1 recurrence | `model_assisted` |
| `brezinski_theta` | `rho_theta.py` | [Sidi, Practical Extrapolation Methods (2003)](https://doi.org/10.1017/CBO9780511546815); ch. 20.2 | `literature_family` |
| `chang_wynn` | `final_catalogue.py` | [Chang, He, Hu, Sun & Weniger, Construction of New Generalizations of Wynn's Epsilon and Rho Algorithm (2019)](https://arxiv.org/abs/1903.10198); Eq. (3.20) | `literature_family` |
| `cvz_2a` | `cvz_2000.py` | [Cohen, Rodriguez Villegas & Zagier, Convergence Acceleration of Alternating Series, Experimental Mathematics 9 (2000), 3-12](https://doi.org/10.1080/10586458.2000.10504632); Algorithm 2A | `literature_family` |
| `cvz_2b` | `cvz_2000.py` | [Cohen, Rodriguez Villegas & Zagier, Convergence Acceleration of Alternating Series, Experimental Mathematics 9 (2000), 3-12](https://doi.org/10.1080/10586458.2000.10504632); Algorithm 2B | `literature_family` |
| `cvz_chebyshev` | `cvz_2000.py` | [Cohen, Rodriguez Villegas & Zagier, Convergence Acceleration of Alternating Series, Experimental Mathematics 9 (2000), 3-12](https://doi.org/10.1080/10586458.2000.10504632); Algorithm 1 | `literature_family` |
| `drummond` | `direct.py` | [Weniger, Nonlinear Sequence Transformations (1989/2003)](https://arxiv.org/abs/math/0306302); section 9.5 (Drummond transformation) | `literature_family` |
| `euler_alternating` | `euler_alternating.py` | [Sidi, Practical Extrapolation Methods (2003)](https://doi.org/10.1017/CBO9780511546815); section 15.2 (Euler alternating-series transformation) | `literature_family` |
| `ford_sidi` | `history_transforms.py` | [Ford & Sidi, An algorithm for a generalization of the Richardson extrapolation process, SIAM J. Numer. Anal. 24 (1987), 1212-1232](https://doi.org/10.1137/0724080); W^(m) recursion and generalized Richardson-type elimination | `local_variant` |
| `ford_sidi_dm_wm` | `ford_sidi_wm_1987.py` | [Ford & Sidi, An algorithm for a generalization of the Richardson extrapolation process, SIAM J. Numer. Anal. 24 (1987), 1212-1232](https://doi.org/10.1137/0724080); appendix B | `literature_family` |
| `ford_sidi_wm` | `ford_sidi_wm_1987.py` | [Ford & Sidi, An algorithm for a generalization of the Richardson extrapolation process, SIAM J. Numer. Anal. 24 (1987), 1212-1232](https://doi.org/10.1137/0724080); section 4 and appendix B | `literature_family` |
| `homeier_f` | `homeier.py` | [Homeier, Scalar Levin-Type Sequence Transformations (2000)](https://arxiv.org/abs/math/0005209); Eq. (98) | `literature_family` |
| `homeier_h` | `homeier.py` | [Homeier, Scalar Levin-Type Sequence Transformations (2000)](https://arxiv.org/abs/math/0005209); Eq. (107) | `literature_family` |
| `homeier_j` | `final_catalogue.py` | [Homeier, Scalar Levin-Type Sequence Transformations (2000)](https://arxiv.org/abs/math/0005209); Eqs. (33), (94) | `literature_family` |
| `homeier_pj` | `homeier.py` | [Homeier, Scalar Levin-Type Sequence Transformations (2000)](https://arxiv.org/abs/math/0005209); Eqs. (148), (155) | `literature_family` |
| `iterated_aitken` | `additional_transforms.py` | [Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)](https://arxiv.org/abs/math/0306302); section 5.1 | `literature_family` |
| `levin` | `direct.py` | [Levin, Development of non-linear transformations for improving convergence of sequences, Int. J. Comput. Math. 3 (1973)](https://doi.org/10.1080/00207167308803075); Levin family; remainder estimates | `literature_family` |
| `levin_power_remainder` | `levin_power_remainder.py` | [Levin, Development of non-linear transformations for improving convergence of sequences, Int. J. Comput. Math. 3 (1973)](https://doi.org/10.1080/00207167308803075); Levin family; remainder estimates | `local_extension` |
| `levin_sidi_m` | `additional_transforms.py` | [Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)](https://arxiv.org/abs/math/0306302); sections 9.2 and 9.4 | `legacy_name` |
| `levin_sidi_s` | `levin_sidi_s.py` | [Sidi, Practical Extrapolation Methods (2003)](https://doi.org/10.1017/CBO9780511546815); sections 6.3.3 and 19.3 (Sidi S; naming comparison still unresolved) | `attribution_pending` |
| `lubkin_w` | `iterated_transforms.py` | [Weniger, Nonlinear Sequence Transformations (1989/2003)](https://arxiv.org/abs/math/0306302); section 10.3 (Lubkin W / theta_2 context) | `literature_family` |
| `osada_generalized_rho` | `osada_rho.py` | [Osada, A convergence acceleration method for some logarithmically convergent sequences, SIAM J. Numer. Anal. 27 (1990), 178-189](https://doi.org/10.1137/0727012); Eq. (3.1) | `literature_family` |
| `osada_rho_safe` | `osada_extended.py` | [Osada, A convergence acceleration method for some logarithmically convergent sequences, SIAM J. Numer. Anal. 27 (1990), 178-189](https://doi.org/10.1137/0727012); Eq. (3.1) | `local_variant` |
| `osada_rho_theta_estimated` | `osada_extended.py` | [Osada, A convergence acceleration method for some logarithmically convergent sequences, SIAM J. Numer. Anal. 27 (1990), 178-189](https://doi.org/10.1137/0727012); Eq. (5.1) + Eq. (3.1) | `local_variant` |
| `overholt` | `iterated_transforms.py` | [Sidi, Practical Extrapolation Methods (2003)](https://doi.org/10.1017/CBO9780511546815); ch. 22 (Overholt transformation) | `literature_family` |
| `richardson` | `direct.py` | [Sidi, Practical Extrapolation Methods (2003)](https://doi.org/10.1017/CBO9780511546815); ch. 1 (Richardson extrapolation) | `local_variant` |
| `shanks` | `direct.py` | [Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)](https://arxiv.org/abs/math/0306302); section 5 (Shanks / epsilon) | `literature_family` |
| `sidi_d_m` | `sidi_d_m.py` | [Sidi, Practical Extrapolation Methods: Theory and Applications (2003)](https://doi.org/10.1017/CBO9780511546815); section 6.2 | `literature_family` |
| `sidi_d_m_e_recursive` | `sidi_d_m_e_recursive.py` | [Sidi, Practical Extrapolation Methods: Theory and Applications (2003)](https://doi.org/10.1017/CBO9780511546815); section 6.2 | `implementation_variant` |
| `sidi_dm_strided` | `sidi_dm_strided.py` | [Sidi, Practical Extrapolation Methods: Theory and Applications (2003)](https://doi.org/10.1017/CBO9780511546815); section 6.2 | `local_variant` |
| `weniger` | `direct.py` | [Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)](https://arxiv.org/abs/math/0306302); section 8.2 | `literature_family` |
| `weniger_fractional_factorial` | `weniger_fractional_factorial.py` | [Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)](https://arxiv.org/abs/math/0306302); inverse-power and inverse-factorial Levin-type constructions | `local_extension` |
| `weniger_m` | `weniger_m_alias.py` | [Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)](https://arxiv.org/abs/math/0306302); sections 9.2 and 9.4 | `alias` |
| `wynn_epsilon` | `wynn_epsilon.py` | [Wynn, On a device for computing the e_m(S_n) transformation, MTAC 10 (1956), 91-96](https://doi.org/10.2307/2002183); epsilon recursion; see also DLMF 3.9(iv) | `literature_family` |
| `wynn_epsilon_adaptive` | `final_catalogue.py` | [Wynn, On a device for computing the e_m(S_n) transformation, MTAC 10 (1956), 91-96](https://doi.org/10.2307/2002183); epsilon recursion; see also DLMF 3.9(iv) | `local_variant` |
| `wynn_epsilon_fixed` | `additional_transforms.py` | [Wynn, On a device for computing the e_m(S_n) transformation, MTAC 10 (1956), 91-96](https://doi.org/10.2307/2002183); epsilon recursion; see also DLMF 3.9(iv) | `local_variant` |
| `wynn_rho` | `rho_theta.py` | [Weniger, Nonlinear Sequence Transformations (1989/2003)](https://arxiv.org/abs/math/0306302); section 6.2 (Wynn rho recurrence) | `literature_family` |

## Implementation-specific notes

- **`aitken_backtracking`**: Local backtracking to locate a nonsingular triple; not a named historical algorithm.
- **`aitken_delta2`**: Aitken Delta^2 expression; exact triple window.
- **`anderson`**: Scalar observed-pair extrapolation, not a full fixed-point function Anderson solver.
- **`brezinski_e`**: Requires explicit auxiliary/error basis; compare separately from black-box methods.
- **`brezinski_theta`**: Theta recurrence; current lower-order fallback is implementation policy.
- **`chang_wynn`**: Chang et al. generalization; different input budget from ordinary Wynn epsilon.
- **`cvz_2a`**: CVZ alternating-series transformation.
- **`cvz_2b`**: CVZ alternating-series transformation.
- **`cvz_chebyshev`**: CVZ accelerated alternating-series transformation.
- **`drummond`**: Difference-quotient scheme with configurable remainder choice.
- **`euler_alternating`**: Alternating-series Euler transformation; restricted regularity assumptions.
- **`ford_sidi`**: Generalized elimination using a Levin error basis; verify exact column-basis mapping per example.
- **`ford_sidi_dm_wm`**: Ford-Sidi d example via W^(m) recursion.
- **`ford_sidi_wm`**: Ford-Sidi W^(m) recurrence, generalized basis.
- **`homeier_f`**: F construction per the cited Homeier formulas.
- **`homeier_h`**: H construction per the cited Homeier formulas.
- **`homeier_j`**: Generalized J difference construction.
- **`homeier_pj`**: pJ variant; special p=2 numerical pathway.
- **`iterated_aitken`**: Repeated Delta^2 transform; not identical to Shanks of the same order.
- **`levin`**: Current implementation has configurable remainder estimates and beta.
- **`levin_power_remainder`**: Independent power-model collocation with variable exponent; do not attribute generalized formula to Levin.
- **`levin_sidi_m`**: Historical C++ identifier; factorial Weniger M formula, not an independent Sidi algorithm.
- **`levin_sidi_s`**: EXPLICIT WARNING: implementation is factorial Weniger S-type quotient; same formula as weniger at equal parameters. Verify exact Sidi ch.19 formula before claiming this identifier identifies Sidi S; see also https://arxiv.org/abs/math/0306302.
- **`lubkin_w`**: W transform; equivalent theta_2 rational expression in this implementation.
- **`osada_generalized_rho`**: Generalized rho, including parameter specialization to classical rho.
- **`osada_rho_safe`**: Published generalized rho recurrence plus local last-valid-row recovery.
- **`osada_rho_theta_estimated`**: Two-stage exponent estimate is NOT literal published automatic algorithm (6.1).
- **`overholt`**: Overholt transformation; check window indexing against original.
- **`richardson`**: Specialized Romberg-style error grid with ratio 1/4; not generic Richardson.
- **`shanks`**: Hankel determinant Shanks transformation; independently see DLMF 3.9(iv).
- **`sidi_d_m`**: Direct d^(m) defining linear system, not optimized W^(m).
- **`sidi_d_m_e_recursive`**: Alternative E-recursive elimination for the same d^(m) system; not a new method.
- **`sidi_dm_strided`**: Nonuniform R_l sampling extension of the defining d^(m) system.
- **`weniger`**: Factorial Levin-type transform; distinct parameter/remainder choices do not imply distinct methods.
- **`weniger_fractional_factorial`**: Fractional step in inverse-factorial basis is local generalization, not published Weniger formula.
- **`weniger_m`**: Published-name alias for legacy levin_sidi_m; not an independent algorithm.
- **`wynn_epsilon`**: Wynn epsilon recursive table; local singularity fallback policy is separate.
- **`wynn_epsilon_adaptive`**: Adaptive selection of available even columns is local stability policy.
- **`wynn_epsilon_fixed`**: Fixed even-column/window evaluator; not an additional mathematical transformation.
- **`wynn_rho`**: Wynn rho recursion with configurable interpolation node grid.
