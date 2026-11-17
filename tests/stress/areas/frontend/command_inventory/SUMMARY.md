# SUMMARY — `command_inventory`

## Counts
- Distinct expressions/queries tried: 223
- Goldens written: 30
- Files created: 32

### Counts

- **223 distinct CLI command invocations / statements** tried, across 30 golden
  files (`NN_*.ucas` + `NN_*.out`), each run twice under `timeout 15`; all were
  byte-identical and exited 0.  Target was 150+, met.
- **30 `.ucas` inputs + 30 `.out` goldens**, plus `FINDINGS.md` and this file
  (32 files).  Every goldens file is deterministic (two-run `cmp` passed).
- **Inventory size**: 150+ top-level command spellings (commands, aliases,
  definition forms and mode/option words) classified below.
- Issues: **WRONG 1**, **LIMIT 1**, CRASH 0, HANG 0, DETERMINISM 0
  (see `FINDINGS.md`).

### How the inventory was built

`README.md` "Commands" table, the `help()` text in `src/parse.c`, the dispatch
in `src/parse.c:statement()`, the `*_command()` entry points in
`src/{alg,xform,props,forms,viz,ring,stoch,...}.c`, and the authoritative
`ucas_cmds[]` list in `src/hyper.c:1576`.  Coverage was checked by grepping
every `tests/stress/*/*.ucas` and `tests/*.ucas` for each command token; the
"covered by" column names the matching stress areas (areas are abbreviated,
e.g. `cas_tricky_corpus` → `cas_tricky`).  `GAP` means no stress area exercised
the command; those rows now point at a golden in this folder.

### Coverage table: command → covering stress area / GAP → example input

### A. Look, session and meta

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `show` | many (output_prettyprint, parser_error_recovery, …) | — |
| `table` | table_interpolation, boolean_sat_u1, … | — |
| `parse` | parser_error_recovery, syntax_weird, … | — |
| `funcs` | state_long_session, session_reset_systematic | — |
| `models` | cost_cross_model, gates_find_cost, x86_intrinsics_mca | — |
| `help` | **GAP** (only incidental `help` text in `tests/forms.ucas`) | 27: `help` |
| `more` | approx_fit_search, gates_find_cost | — |
| `use` | cost_cross_model, x86_intrinsics_mca, session_reset | — |
| `basis` (definition) | cyclic_basis_solve, gates_basis_edges | covered here 27: `basis myand { andg(x, y) = x & y; org(x, y) = x \| y }` |
| `model` (definition) | cost_cross_model, gates_find_cost | covered here 27: `model mym : gt1030 { imul: 5 }` |
| `state` | **not a CLI command** (JSON/MCP tool) | mcp_api_fuzz / session areas |
| `reset` | **not a CLI command** (JSON/MCP tool) | session_reset_systematic |
| `assume` | spvsimplify option (`spvassume_words`); NLP/JSON tool | covered here 14: `spvsimplify … assume x 0 31` |
| `forget` | **not a CLI command** (NLP "forget everything") | nlp areas |
| `schema` | **not a CLI command** (JSON/MCP tool) | schema_conformance |

### B. Look/comparison and proof machinery

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `range` | range_sampled_soundness, sat_ranges_where, … | — |
| `domain` | equiv_domain_systematic, sat_wrap_domain, … | — |
| `wrap` | sat_wrap_domain, undefined_propagation, … | — |
| `crit` | crit_classification | — |
| `diff` | symbolic_diff_exact, second_cas_oracle, … | — |
| `equiv` | equiv_domain_systematic, sat_*, fpsat areas, … | — |
| `fit` | approx_fit_search, below_tolerance_float | — |
| `error` | approx_fit_search, precision_controls, … | — |
| `gates` (`gates npn`) | gates_basis_edges, gates_find_cost, boolean_sat_u1 | — |
| `find` | gates_find_cost, approx_fit_search, … | — |
| `find … saturate` | **GAP** (option never stressed) | 23: `find f 1 saturate` |
| `cost` | cost_cross_model, gates_find_cost, … | — |
| `stoke` | rng_stochastic, gates_find_cost | — |
| `pit` | rng_stochastic, seed_env_control | — |
| `phash` | rng_stochastic, sat_crypto_circuits | — |
| `rule` (declaration) | **GAP** | 15: `rule dbl(a: u32) = a << 1 => a + a` |
| `rules infer` | source_hotspots, thesis_nlp_noise_bias | — |
| `snippets grow` | snippets_db, gates_find_cost | — |
| `theorem`, `prove` | prove_symbolic, proof_kernel_axioms | — |

### C. Cost-model / architecture commands

| command | covered by | GAP → example input |
|---|---|---|
| `banks` | **GAP** | 01: `banks lane & 31` |
| `intatomic` | **GAP** | 02: `intatomic g count 100` |
| `rop` | **GAP** | 03: `rop acc` |
| `dword` | build_variants only | — |
| `foldproof` | build_variants only | — |
| `mma`, `hmma` | main test + mma_validate.needs; >15 s (FINDINGS §2) | — |
| `lperm` | **GAP** | 16: `lperm lane xor 3 model rdna2` |
| `tcdot` | numeric_arg_overflow | — |
| `winograd` | **GAP** | 17: `winograd d4` |
| `ozaki` | **GAP** | 18: `ozaki g tol 1e-3` |
| `texalu` | tex_domain_modules; main corpus | — |
| `texenc` | table_interpolation; main corpus | — |

### D. Calculus / loops / ODE / PDE

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `integrate`, `antiderivative` | transforms_ode_series, nlp_calculus, … | 30: `integrate sin(x) from 0 to pi` |
| `integrate … qmc` | JSON-only option (jsonmode.c), not CLI | — |
| `sum`, `prod` | series_acceleration, transforms_ode_series | — |
| `closed` | series_acceleration, transforms_ode_series | — |
| `scheme` | **GAP** | 21: `scheme p more` |
| `continuous` | **GAP** | 22: `continuous h` |
| `diff`/`grad`/`hessian`/`laplacian`/`jacobian` | transforms_ode_series, nlp_calculus | — |
| `grad` alias `gradient` | transforms_ode_series (canonical only) | 28: `gradient x^2 + y^2` |
| `ddir` | **GAP** | 05: `ddir x^2*y along 3, 4 at 1, 1 raw` |
| `wronskian` | transforms_ode_series | — |
| `limit`/`lim` | multivariate_limits, complex_branch_cuts, … | — |
| `taylor` (alias `maclaurin`) | transforms_ode_series (canonical only) | 28: `maclaurin sin(x)` |
| `implicit` | transforms_ode_series | — |
| `pde` | **GAP** | 06: `pde heat { u_t = 0.1 u_xx; u(x,0)=sin(pi x); x in 0..1; t in 0..0.5 }` |
| `dsolve` | ode_boundary_problems, transforms_ode_series | — |
| `partial` | nlp_calculus, table_interpolation | — |

### E. Complex / trig / hypercomplex

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `complex`, `polar`, `conj`, `re`, `im`, `modulus`, `arg` | complex_branch_cuts, cas_tricky | — |
| `rect` (alias of `complex`) | **GAP** (alias form) | 20: `rect (2+3i)(4-5i)` |
| `nthroots`, `unity` | complex_branch_cuts, cas_tricky | — |
| `trig` | trig_identity_sweep | — |
| `holomorphic`, `residue`, `poles` | complex_branch_cuts, cas_tricky | — |
| `associator` | **GAP** | 24: `associator e1, e2, e4` |
| `commutator` | **GAP** | 24: `commutator i, j` |
| `axisangle` | **GAP** | 24: `axisangle (0, 0, 1), 90 degrees` |
| `rotmatrix` | **GAP** | 24: `rotmatrix 1 + i + j + k` |
| `frommatrix` | **GAP** | 24: `frommatrix 0, -1, 0, 1, 0, 0, 0, 0, 1` |
| `slerp` | **GAP** | 24: `slerp 1, k, 1/2` |
| `rotate` | hypercomplex_algebras | — |
| `zerodivisors` | **GAP** | 26: `zerodivisors sedenion` |
| `table quaternion\|octonion\|sedenion` | hypercomplex_algebras | — |
| `algebra NAME` | hypercomplex_algebras | — |

### F. Symbolic algebra / solving

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `expand`, `factor`, `simplify`, `together`, `cancel`, `collect`, `apart` | algebra_ring_ff, cas_tricky, simplify_idempotence, … | — |
| `gcd`, `lcm`, `resultant`, `discriminant`, `quo`, `rem`, `divide` | polynomial_gcd_resultant, algebra_ring_ff | — |
| `solve` | algebra_system_solving, polynomial_gcd_resultant, … | — |
| `substitute` (`subst`) | **GAP** | 07: `substitute x = 2, y = 3 in x^2 + y` |
| `sub` | **not an alias** (bare variable) | 29: `sub` |

### G. Properties

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `monotonic` (`monotone`) | nlp_arith (canonical only) | 28: `monotone x^3` |
| `period` (`periodic`) | nlp_roundtrip (weak) | 08: `period sin(x) + cos(3x)` |
| `identify` (`classify`) | nlp_roundtrip, prove_symbolic | — |
| `parity`, `symmetry` | sat_crypto_circuits, llm_mutators | — |
| `bounded` | **GAP** | 09: `bounded 1/x in 1..2` |
| `injective`, `surjective`, `bijective` | nlp_arith | — |
| `continuity`, `discontinuities` | cas_tricky, multivariate_limits | — |
| `convexity` (`convex`, `concave`) | **GAP** | 10: `convexity x^3` |
| `asymptotes` | cas_tricky, trig_identity_sweep | — |
| `zeros` (`roots`) | cas_tricky, approx_fit_search | 28: `roots x^2 - 1` |

### H. Rings, number theory, matrices

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `ring` | number_theory_core, algebra_ring_ff | — |
| `inverse` (`invmod`, `modinv`) | number_theory_core (canonical only) | 28: `invmod 3 mod 11` |
| `order` (`multorder`) | number_theory_core (canonical only) | 28: `multorder 3 mod 11` |
| `phi` (`totient`) | number_theory_core (canonical only) | 28: `totient 12` |
| `carmichael` | number_theory_core | — |
| `factorint` | integer_factorization, number_theory_core | — |
| `crt`, `congruence` | number_theory_core | — |
| `legendre`, `jacobi`, `sqrtmod`, `qr` | number_theory_core | — |
| `primroot` | number_theory_core | — |
| `dlog` | **GAP** | 11: `dlog 3 base 2 mod 11` |
| `magic` | magic_constants, integer_division_semantics | — |
| `gf2matrix` | **GAP** | 12: `gf2matrix x ^ (x << 3) u8` |
| `irreducible` | algebra_ring_ff (sparse) | 26: `irreducible x^8+x^4+x^3+x+1 over GF(2)` |
| `primitive` | algebra_ring_ff (sparse) | 26: `primitive x^8+x^4+x^3+x+1 over GF(2)` |
| `det`, `rank` | det_linear_algebra, sparse_large_matrices | — |
| `nullspace` | **GAP** | 13: `nullspace [[1,1,0],[0,1,1],[1,0,1]] mod 2` |
| `matinv`, `matsolve` | **GAP** | 26: `matinv [[1,2],[3,4]] mod 5` |
| `snf`, `abgroup`, `homology`, `cohomology`, `cayley`, `space` | absalg/homalg: snf/abgroup in algebra_ring_ff; rest **GAP** | 19: `homology RP^4` |

### I. Transforms / series / sums

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `laplace`, `ilaplace`, `ztrans`, `iztrans`, `zsolve`, `tf` | transforms_ode_series | — |
| `fourier`, `ifourier`, `dft`/`fft`, `idft`/`ifft`, `dtft` | transforms_ode_series (dft/idft only) | 25: `dtft 0.5^n`, `dft [1, 2, 3, 4]` |
| `fseries`, `genfunc`/`ogf`, `egf`, `coeffs`, `asymptotic` | **GAP** | 25: `fseries exp(x)`, `coeffs sin(x)` |
| `converge`, `radius` | series_acceleration, transforms_ode_series | — |
| `powerseries` | llm_mutators_findings, ode_boundary_problems | — |

### J. Visualization / plotting / geometry

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `plot`, `plot3d` | plot_gif_resources, fault_injection | — |
| `animate` | plot_gif_resources, fault_injection | — |
| `neighbourhood` (`neighborhood`) | **GAP** | 04: `neighbourhood x^3 - 3x nofile` |
| `area`, `revolve`, `volume`, `surfacearea`, `arclength`, `centroid` | plot_gif_resources, transforms_ode_series | — |
| `approx`, `approx more` | approx_fit_search, rng_stochastic | — |
| `adamfit` | fault_injection (crash area) | — |
| `gif` | **not a command** — output format of plot/animate/scan | plot_gif_resources |

### K. SPIR-V / C frontends / miscellaneous

| command (aliases) | covered by | GAP → example input |
|---|---|---|
| `spvsimplify` | **GAP** (main corpus uses `simplify` + block) | 14: `spvsimplify nofile nofunctions` |
| `spvsimplify … sink` | **GAP** | 14: `spvsimplify nofile nofunctions sink rgba8` |
| `spvsimplify … advice` | **GAP** | 14: `spvsimplify nofile nofunctions advice` |
| `simplify` (+ SPIR-V/GLSL block, `SAT simplify`, `optimize this`, `peephole with smt`) | spirv_glsl_simplify | — |
| `c optimize`, `c lower`, `c targets` (the `c` line commands) | cfront_* areas | — |
| `cf` | C-frontend module, not a standalone CLI command | cfront_* areas |
| `ec` (`ellcurve`, `elliptic`, `diophantine`, `weierstrass`, `congruent`, `mordell`, `cubesum`) | elliptic_rank_generators | — |
| `ntheory` | **not a command** — module name (phi, crt, dlog, …) | number_theory_core covers its commands |
| `eval`, `evaluate` | not CLI commands (NLP starters / bare variables) | 29: `eval 2+2` → `2eval + 2` |
| `vals` | not a command (bare variable) | 29: `vals` |
| `reportall` | not a command (bare variable) | 29: `reportall` |
| `tabulate` | English verb → `table it` | 29: `tabulate sin(x)` |
| `dot`, `emit`, `viz`, `gif` | not commands (bare variables / builtin / module) | 29: `dot`, `emit`, `viz` |

### Golden-file index (GAP commands newly covered)

| file | command(s) | file | command(s) |
|---|---|---|---|
| `01_banks` | banks | `16_lperm` | lperm |
| `02_intatomic` | intatomic | `17_winograd` | winograd |
| `03_rop` | rop | `18_ozaki` | ozaki |
| `04_neighbourhood` | neighbourhood/neighborhood | `19_homology` | homology, cohomology, space, cayley |
| `05_ddir` | ddir | `20_rect` | rect + complex parts |
| `06_pde` | pde, dsolve | `21_scheme` | scheme |
| `07_substitute` | substitute, subst | `22_continuous` | continuous |
| `08_period` | period, periodic | `23_saturate` | find … saturate |
| `09_bounded` | bounded | `24_hyper_ops` | associator, commutator, axisangle, rotmatrix, frommatrix, slerp |
| `10_convexity` | convexity, convex, concave | `25_xform_obscure` | fseries, dtft, genfunc, ogf, egf, coeffs, asymptotic, dft |
| `11_dlog` | dlog | `26_ring_obscure` | matinv, matsolve, irreducible, primitive, zerodivisors |
| `12_gf2matrix` | gf2matrix | `27_session_commands` | help, funcs, use, basis, model |
| `13_nullspace` | nullspace | `28_aliases` | monotone, roots, convex/concave, maclaurin, gradient, totient, multorder, invmod, modinv |
| `14_spvsimplify` | spvsimplify + sink/advice/assume | `29_noncommands` | eval, vals, sub, tabulate, reportall, ntheory, gif, dot, emit, viz |
| `15_rule` | rule | `30_integrate_options` | integrate (definite), antiderivative |


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| LIMIT | 1 | — |

## Takeaway
Most commands already have a stress area, but roughly 30 genuine CLI commands had none (`banks`, `intatomic`, `rop`, `neighbourhood`, `ddir`, `pde`, `substitute`, `period`, `bounded`, `convexity`, `dlog`, `gf2matrix`, `nullspace`, `spvsimplify`, `rule`, `lperm`, `winograd`, `ozaki`, `homology`, `rect`, `scheme`, `continuous`, `saturate`, `spvsimplify`'s `sink`/`advice`, several aliases and hypercomplex ops) — they are now covered by 30 goldens; one misleading `banks` diagnostic and one long-running `mma` search were found.

### Original takeaway (verbatim)

Most commands already have a stress area, but roughly 30 genuine CLI commands
had none (`banks`, `intatomic`, `rop`, `neighbourhood`, `ddir`, `pde`,
`substitute`, `period`, `bounded`, `convexity`, `dlog`, `gf2matrix`,
`nullspace`, `spvsimplify`, `rule`, `lperm`, `winograd`, `ozaki`, `homology`,
`rect`, `scheme`, `continuous`, `saturate`, `spvsimplify`'s `sink`/`advice`,
several aliases and hypercomplex ops) — they are now covered by 30 goldens;
one misleading `banks` diagnostic and one long-running `mma` search were found.
