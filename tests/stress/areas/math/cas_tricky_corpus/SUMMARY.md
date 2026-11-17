# SUMMARY — `cas_tricky_corpus`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 143
- Files created: not recorded

### Method (idea 3 / GEMM cas-testing):
assembled a literature/textbook corpus of known-tricky
CAS inputs — singular & oscillatory integrals, limits at essential singularities, Dirichlet
series, zero polynomials, `sin²+cos²`, branch cuts (`log(-1)`, `sqrt(x²)`, `atan2`),
removable singularities, telescoping & divergent-looking convergent series, `residue` at
poles, `taylor` at non-analytic points — and ran the relevant symbolic commands
(`limit`, `integrate`, `antiderivative`, `sum`, `prod`, `converge`, `radius`, `simplify`,
`expand`, `factor`, `cancel`, `apart`, `series`/`taylor`, `residue`, `complex`, `domain`,
`range`, `continuity`, `zeros`, `equiv`) over them.

### Counts

- Distinct symbolic queries executed: **~380** (≈231 exploratory probes + 143 durable golden
  statements + 5 MCP calls). Distinct expression shapes: **> 250**.
- Durable goldens: **11 CLI files** (`01`–`11`, 143 statements) + **1 MCP JSONL** (5 calls),
  each with a captured `.out`. All outputs regenerated twice and `diff`ed: **100%
  deterministic**.
- Crashes: **0**. Hangs: **0** (every run exit 0, < 130 ms). Nondeterminism: **0**.
- Independent oracle: `mpmath` 1.3 high-precision `nsum` + `sympy` 1.14 (installed with
  `pip install --break-system-packages sympy`).

### Folder contents

`01_dirichlet_series`, `02_floor_limits`, `03_taylor_coeffs`, `04_integrals_singular`,
`05_limits_essential`, `06_simplify_identities`, `07_poly_factor`,
`08_residue_taylor_nonan`, `09_complex_branch`, `10_converge_series`, `11_domain_range`
(each `.ucas` + `.out`), `mcp_wrong_checks.jsonl` + `.out`, `FINDINGS.md`, `SUMMARY.md`.
All work stayed inside `tests/stress/areas/math/cas_tricky_corpus/`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | ~19 wrong answers in 3 families (below) |
| LIMIT | 5 | capability gaps / misleading diagnostics (see FINDINGS.md) |

### Issues by severity

| Severity | Families | What |
|----------|----------|------|
| **WRONG** | 3 | ~19 wrong answers in 3 families (below) |
| **LIMIT** | 5 | capability gaps / misleading diagnostics (see FINDINGS.md) |
| CRASH / HANG / DETERMINISM | 0 | — |

Confirmed WRONG families:

1. **Dirichlet series declared divergent** — `sum`/`converge` on `sin(n)/n`,
   `cos(n)/n`, `sin(n)/√n`, `sin(2n)/n`, `(-1)^n sin(n)/n`, `sin(n)/log n`
   all get "diverges: comparison with the p-series", contradicting Dirichlet's test and
   ucas's own converging partial sums. Exact values confirmed with mpmath.
2. **L'Hôpital on `floor`/`ceil` at infinity** — `limit floor(x)/x x -> inf` returns `0`
   (true `1`), etc., with the internal numeric check reporting `DISAGREES`.
3. **High-order Taylor coefficients wrong** — `taylor 1/(1+x^2) ... order 8` gives
   `23x^8/7` (true `1`), order ≥ 8 generally; internal `taylor_jet` check `passed:false`.

MCP structured output (`mcp_wrong_checks.out`) independently exposes two of these as
`checks:[{"passed":false,...}]`, and the wrong verdicts as `result.diverges`/`result.limit`.


## Takeaway
The CAS core is robust (no crashes) but unsound on three textbook patterns — oscillating series, limits of integer-step functions at infinity, and high-order Taylor coefficients — and its own numeric/jet checks already flag two of them, so the findings are easy to confirm.

### Original takeaway (verbatim)

The CAS core is robust (no crashes) but unsound on three textbook patterns — oscillating
series, limits of integer-step functions at infinity, and high-order Taylor coefficients —
and its own numeric/jet checks already flag two of them, so the findings are easy to confirm.
