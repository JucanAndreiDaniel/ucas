# SUMMARY — `series_acceleration`

## Counts
- Distinct expressions/queries tried: 247
- Goldens written: 8
- Files created: 18

### Counts
- Distinct expressions / queries tried: **≈ 247** (228 MCP `transforms`/`calculus`
  calls across 7 probe batches + 19 CLI invocations). Categories: absolutely and
  conditionally convergent series, divergent and borderline p-series, telescoping,
  geometric / arithmetico-geometric, Dirichlet/oscillatory, power-series radius and
  interval endpoints, Euler–Maclaurin asymptotics, generating functions (ordinary and
  exponential), infinite products, and closed forms (ζ(2), ζ(4), η, Γ/Wallis,
  `sinh(pi)/pi`, Catalan/Fibonacci).
- Cross-checks: mpmath 1.3.0 at 30–40 dps for every claimed closed form / product
  value / Dirichlet limit cited in FINDINGS.md.
- Files created: **18** in `tests/stress/areas/math/series_acceleration/` only
  - CLI goldens: `01_closed_forms`, `02_converge_dirichlet`, `03_radius_logbug`,
    `04_asymptotic_ugly`, `05_sum_prod_edges`, `06_cli_sum_limits` (each `.ucas` + `.out`)
  - MCP goldens: `mcp_product_accel`, `mcp_misc_wrong` (each `.jsonl` + `.out`)
  - `FINDINGS.md`, `SUMMARY.md`
- All goldens exit 0 and are byte-identical across repeated runs (no hangs, crashes,
  or nondeterminism in this area).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 6 | F1 Dirichlet series declared divergent; F2 radius finite-n ≈0.99999 for 1/log n; F3 exponential products → 0; F4 prod n^2/(n^2-1) self-contr |
| NLP | 2 | F6 H(n) silently misread; F9 i!/factorial(i) not parsed in CLI sum |
| LIMIT | 4 | F7 unsimplified Euler–Maclaurin garbage; F8 symbolic fallback for large CLI sums; F9 factorial parsing; F4 numeric 0 on division by zero |

### Issues by severity
| Severity | Count | Topics |
|---|---|---|
| `WRONG`  | 6 | F1 Dirichlet series declared divergent; F2 `radius` finite-n ≈0.99999 for `1/log n`; F3 exponential products → 0; F4 `prod n^2/(n^2-1)` self-contradiction; F5 binomial overflow + missed divergence; F6 `H(n)` misread → 1 instead of 2 |
| `NLP`    | 2 | F6 `H(n)` silently misread; F9 `i!`/`factorial(i)` not parsed in CLI `sum` |
| `LIMIT`  | 4 | F7 unsimplified Euler–Maclaurin garbage; F8 symbolic fallback for large CLI sums; F9 factorial parsing; F4 numeric 0 on division by zero |
| `CRASH`  | 0 | — |
| `HANG`   | 0 | — |
| `DETERMINISM` | 0 | — |

(Some findings carry two severity tags; unique finding count is 9.)


## Takeaway
The closed-form/telescoping/Geometric core is solid, but the convergence engine misses Dirichlet cancellation, the radius and product acceleration paths replace limits with finite-n fits (yielding wrong R ≈ 0.99999 and product values of 0), and several NLP/parse paths silently return wrong answers.

### Original takeaway (verbatim)
The closed-form/telescoping/Geometric core is solid, but the convergence engine
misses Dirichlet cancellation, the radius and product acceleration paths replace
limits with finite-n fits (yielding wrong R ≈ 0.99999 and product values of 0), and
several NLP/parse paths silently return wrong answers.
