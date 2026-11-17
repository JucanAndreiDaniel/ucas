# SUMMARY — `transforms_ode_series`

## Counts
- Distinct expressions/queries tried: 430
- Goldens written: 8
- Files created: 28

### Original preamble

Area covered: `calculus`, `transforms` and `solids` MCP tools plus the CLI statements for
Laplace/Z/Fourier transforms & inverses (with ROC), recurrences and ODEs, transfer functions,
Fourier series, DFT/DTFT, generating functions, infinite sums/products, convergence and radius,
Taylor/power series, Euler–Maclaurin asymptotics, limits, derivatives, Jacobian/Hessian/Wronskian,
implicit derivatives, definite/contour integrals (`around`), and solids/arc length.

### Counts

- **Distinct expressions / queries tried:** ~430
  - Golden cases: 112 CLI statements + 68 MCP calls = 180
  - Additional adversarial exploration (divergent series, borderline convergence, singularity-laden
    ODEs, false closed forms, malformed args, ROC/endpoint probes, heavy orders): ~250
- **Files written: 28**
  - 8 CLI goldens (`01_...`..`08_...`, `.ucas` + `.out`)
  - 3 MCP goldens (`mcp_transforms`, `mcp_calculus`, `mcp_ode_series`, `.jsonl` + `.out`)
  - 1 flat-mode MCP golden (`mcp_flat.jsonl` + `.out` + `.flags` = `--flat`)
  - `gen_mcp.py` (JSONL generator for the MCP goldens)
  - `FINDINGS.md`, `SUMMARY.md`
- Every golden was run twice and diffed byte-for-byte; all 12 are deterministic. The `--mcp` runs
  exit 0 with no `isError` / `ok:false` responses in the kept files.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 1 | high-order symbolic diff expression swell (diff exp(x^2)log(1+x) x 11..12 >30 s) |
| WRONG | 4 | powerseries+var multiplies by variable; laplace_solve/zsolve drop ;-separated ICs; fourier(x^n)=0; converge/infinite_sum call Dirichlet seri |
| NLP | 1 | dtft documented f arg causes a parse error |
| LIMIT | 1 | trivial constant arc-length antiderivative not found |

### Issues by severity

| Severity | Count | Short titles |
|----------|-------|--------------|
| CRASH    | 0     | — |
| HANG     | 1     | high-order symbolic `diff` expression swell (`diff exp(x^2)*log(1+x) x 11..12` >30 s) |
| WRONG    | 4     | `powerseries`+`var` multiplies by variable; `laplace_solve`/`zsolve` drop `;`-separated ICs; `fourier(x^n)=0`; `converge`/`infinite_sum` call Dirichlet series divergent |
| NLP      | 1     | `dtft` documented `f` arg causes a parse error |
| LIMIT    | 1     | trivial constant arc-length antiderivative not found |
| DETERMINISM | 0  | — |

Total issues: **7**.


## Takeaway
The transforms/calculus backends are numerically sound on mainstream inputs (all self-checks agree), but the frontend quietly produces wrong answers for several perfectly reasonable inputs — a `var` argument, a semicolon in ODE/recurrence conditions, polynomial Fourier transforms, and oscillatory series — and high-order `diff` has an unbounded expression-swell hang.

### Original takeaway (verbatim)

The transforms/calculus backends are numerically sound on mainstream inputs (all self-checks agree),
but the frontend quietly produces wrong answers for several perfectly reasonable inputs — a `var`
argument, a semicolon in ODE/recurrence conditions, polynomial Fourier transforms, and oscillatory
series — and high-order `diff` has an unbounded expression-swell hang.
