# Stress area index

All areas follow the one design in `README.md`.
Each count lists the paired goldens. Each pair has an input and a `.out` file.

## _TEMPLATE (0)


## float (6)

- `below_tolerance_float` — 22 goldens
- `float_exhaustive` — 25 goldens
- `fp_edge` — 10 goldens
- `magic_constants` — 20 goldens
- `nan_subnormal_modes` — 9 goldens
- `worst_case_rounding` — 28 goldens

## frontend (25)

- `binary_source_unicode` — 14 goldens
- `cli_args_fuzz` — 0 goldens
- `command_inventory` — 30 goldens
- `concurrent_clients` — 2 goldens
- `discord_bot` — 12 goldens
- `env_locale_tty` — 6 goldens
- `mcp_api_fuzz` — 10 goldens
- `mcp_codemode_schemas` — 11 goldens
- `mcp_op_inventory` — 49 goldens
- `mcp_protocol_negotiation` — 22 goldens
- `mcp_resources_prompts` — 9 goldens
- `output_input_boundary` — 4 goldens
- `parser_error_recovery` — 178 goldens
- `parser_json_fuzz` — 20 goldens
- `readme_examples` — 21 goldens
- `repo_tooling` — 2 goldens
- `schema_conformance` — 22 goldens
- `self_reference_state` — 19 goldens
- `session_reset_systematic` — 22 goldens
- `state_long_session` — 11 goldens
- `stdin_interactive` — 13 goldens
- `syntax_weird` — 12 goldens
- `timeout_isolation` — 4 goldens
- `timeout_s_systematic` — 3 goldens
- `tool_abuse_files` — 7 goldens

## gpu (5)

- `cost_cross_model` — 12 goldens
- `plot_gif_resources` — 11 goldens
- `spirv_glsl_simplify` — 6 goldens
- `tex_domain_modules` — 9 goldens
- `x86_intrinsics_mca` — 22 goldens

## math (30)

- `algebra_ring_ff` — 14 goldens
- `algebra_system_solving` — 8 goldens
- `approx_fit_search` — 20 goldens
- `bigint_extremes` — 15 goldens
- `cas_tricky_corpus` — 12 goldens
- `complex_branch_cuts` — 14 goldens
- `crit_classification` — 14 goldens
- `cyclic_basis_solve` — 129 goldens
- `det_linear_algebra` — 6 goldens
- `elliptic_rank_generators` — 13 goldens
- `external_oracle_diff` — 10 goldens
- `hypercomplex_algebras` — 12 goldens
- `integer_division_semantics` — 9 goldens
- `integer_factorization` — 19 goldens
- `math_function_domain` — 24 goldens
- `multivariate_limits` — 17 goldens
- `number_theory_core` — 12 goldens
- `numeric_arg_overflow` — 14 goldens
- `ode_boundary_problems` — 24 goldens
- `output_prettyprint` — 16 goldens
- `polynomial_gcd_resultant` — 15 goldens
- `precision_controls` — 12 goldens
- `second_cas_oracle` — 7 goldens
- `series_acceleration` — 8 goldens
- `simplify_idempotence` — 7 goldens
- `sparse_large_matrices` — 7 goldens
- `table_interpolation` — 11 goldens
- `transforms_ode_series` — 12 goldens
- `trig_identity_sweep` — 12 goldens
- `type_coercion` — 13 goldens

## nlp (13)

- `english_redos` — 12 goldens
- `nlp_ambiguity` — 9 goldens
- `nlp_arith` — 10 goldens
- `nlp_british_dialect` — 5 goldens
- `nlp_calculus` — 8 goldens
- `nlp_checklist` — 12 goldens
- `nlp_intent_boundaries` — 11 goldens
- `nlp_multilingual` — 3 goldens
- `nlp_numbers` — 13 goldens
- `nlp_robustness` — 7 goldens
- `nlp_roundtrip` — 7 goldens
- `nlp_session_state` — 13 goldens
- `thesis_nlp_noise_bias` — 7 goldens

## sat (26)

- `afl_coverage_fuzz` — 3 goldens
- `aig_growth_patterns` — 12 goldens
- `boolean_sat_u1` — 51 goldens
- `dd_diff_isolation` — 9 goldens
- `equiv_domain_systematic` — 9 goldens
- `exponential_defs` — 13 goldens
- `gates_basis_edges` — 17 goldens
- `gates_find_cost` — 13 goldens
- `grammar_corpus_mutate` — 4 goldens
- `grammar_fuzz_reduce` — 4 goldens
- `llm_mutators_findings` — 12 goldens
- `metamorphic_identities` — 23 goldens
- `proof_kernel_axioms` — 7 goldens
- `prove_symbolic` — 16 goldens
- `range_sampled_soundness` — 7 goldens
- `sat_crypto_circuits` — 19 goldens
- `sat_hard_mult` — 15 goldens
- `sat_ranges_where` — 8 goldens
- `sat_wide_bitops` — 14 goldens
- `sat_wrap_domain` — 15 goldens
- `symbolic_diff_exact` — 6 goldens
- `thesis_fusion_enum` — 16 goldens
- `thesis_mr_mining` — 331 goldens
- `type_mutation_diff` — 10 goldens
- `undefined_propagation` — 19 goldens
- `witness_verification` — 9 goldens

## systems (22)

- `build_variants` — 0 goldens
- `c_vectorize_loops` — 18 goldens
- `cfront_bench_timing` — 22 goldens
- `cfront_float_semantics` — 19 goldens
- `cfront_fuzz` — 30 goldens
- `cfront_preprocessor` — 23 goldens
- `cfront_ub_contracts` — 14 goldens
- `coverage_gap_analysis` — 0 goldens
- `fault_injection` — 2 goldens
- `make_test_baseline` — 0 goldens
- `resource_limits` — 17 goldens
- `resource_limits_extended` — 4 goldens
- `rng_stochastic` — 9 goldens
- `sanitizer_builds` — 0 goldens
- `seed_env_control` — 7 goldens
- `signal_interrupts` — 0 goldens
- `snippets_db` — 20 goldens
- `soak_nondeterminism` — 0 goldens
- `source_hotspots` — 24 goldens
- `static_analysis` — 5 goldens
- `suite_mutation_testing` — 0 goldens
- `translation_validation` — 6 goldens
