# SUMMARY — `algebra_system_solving`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 8
- Files created: not recorded

### Scope
Systems of polynomial/rational equations (1–5 equations, 1–4 variables): linear unique /
dependent / inconsistent / underdetermined, rational coefficients, parametric equations,
divisions and conditions, nonlinear and resultant-based systems, degenerate/product systems,
higher-degree polynomials, transcendental equations, and mixed multi-variable systems.
Both CLI `solve` and MCP `algebra.solve` were exercised; returned solutions were
independently substituted with sympy 1.14 (`fractions`-exact where applicable) and solution
counts compared against sympy ground truth.

### Counts
- Distinct systems/queries generated and run: **185** (catalog `systems.py`) plus **10** hard
  probes plus **10** targeted probes for the findings = **205** system instances, each run
  twice through MCP for determinism (≈410 solve calls), plus CLI golden double-runs.
- Categories (count): nonlinear2 25, univariate_poly 20, linear2_unique 10, linear_dependent 10,
  linear_inconsistent 10, linear_underdetermined 10, degenerate_product 10, rational_division 10,
  transcendental 10, mixed_multi 10, adversarial_extra 31, linear3_unique 8, rational_coeff 8,
  parametric 8, linear4_unique 5.
- Systems with an independent sympy ground-truth solution set: **87**; of those **36** count
  mismatches were triaged (most were sympy-truth artifacts; the actionable ones are F1/F2 below).
- Files written (in this folder only):
  - CLI goldens: `01_linear_systems`, `02_nonlinear_systems`, `03_rational_conditions`,
    `04_parametric`, `05_bug_missing_solutions`, `06_bug_identity_highdegree` (`.ucas` + `.out`).
  - MCP goldens: `mcp_solve_systems`, `mcp_solve_bugs` (`.jsonl` + `.out`).
  - `FINDINGS.md`, `SUMMARY.md`, and `.work/` (harness, reports, probes — scratch only).
- All 8 goldens were run twice and `diff`ed: **100% deterministic**, exit code 0.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| LIMIT | 2 | — |

### Issues by severity
- `WRONG` HIGH: **2** — F1 resultant back-substitution drops solutions (false "no real
  solution"); F2 high-degree polynomials falsely report "no real solution".
- `WRONG` MEDIUM: **1** — F3 identity equations report "no real solution" despite
  `every_value: true`.
- `LIMIT` LOW: **2** — F4 narrow accepted system shapes; F5 trig identity returns finite sample.
- `CRASH`: 0. `HANG`: 0. `DETERMINISM`: 0.


## Takeaway
Correct solutions that ucas returns do substitute to residual 0, but `solve` is **unsound on completeness**: resultant back-substitution silently loses branches where the eliminated variable's divisor vanishes, high-degree root isolation gives up with a false "no real solution", and identities are reported as having no solution.

### Original takeaway (verbatim)
Correct solutions that ucas returns do substitute to residual 0, but `solve` is **unsound on
completeness**: resultant back-substitution silently loses branches where the eliminated
variable's divisor vanishes, high-degree root isolation gives up with a false "no real
solution", and identities are reported as having no solution. Substitution certificates
cannot detect missing solutions, so an independent completeness check is required.
