# SUMMARY — `nlp_calculus`

## Counts
- Distinct expressions/queries tried: 227
- Goldens written: 8
- Files created: not recorded

### Coverage

- **Distinct English queries tried: 227** (unique lines; ~245 requests counting
  MCP `english` / `calculus` / `transforms` calls). Categories: derivatives
  (explicit, higher, partial, mixed, gradient, Hessian, Laplacian, Jacobian,
  Wronskian, directional, implicit), limits (two-sided, one-sided, infinity,
  0/0, L'Hôpital, squeeze/oscillation), integrals (definite/indefinite,
  numeric, area under/between), Taylor/Maclaurin/Chebyshev/minimax/power
  series and asymptotics, finite/infinite sums and products, ODEs (`dsolve`,
  Laplace), recurrences (`closed`, `zsolve`, `genfunc`, `egf`), Laplace/Z/
  Fourier/DFT/DTFT transforms and transfer functions, and solids/arc length
  (area, revolve, volume, surfacearea, arclength, centroid).
- All runs bounded by `timeout 15` (goldens `timeout 30`). Every query exited
  0 in 0.01–0.7 s. **No crashes, no hangs.**

### Files written (all under `tests/stress/areas/nlp/nlp_calculus/`)

CLI goldens (`NAME.ucas` + `NAME.out`, 6 pairs):
- `01_derivatives` (10 statements)
- `02_limits` (8)
- `03_integrals` (9)
- `04_series_sums` (10, includes a deterministic Chebyshev/minimax fit)
- `05_ode_recurrence` (9)
- `06_transforms` (10)

MCP goldens (`NAME.jsonl` + `NAME.out`, 2 pairs):
- `mcp_english_calculus` (7 calls: `english` + `calculus` diff/integrate/limit)
- `mcp_transforms` (7 calls: `transforms` laplace/ilaplace/ztrans/fourier/
  infinite_sum/genfunc + `english`)

Docs: `FINDINGS.md`, `SUMMARY.md`. **Total 18 files.**

All 8 golden outputs were regenerated a second time and `diff`-identical
(`DETERMINISM: clean`). No golden contains `sorry:`, a parse error, or an
`isError:true` MCP response.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | "the integral of x from pi to 0" → +4.9348 (should be −4.9348); "the limit of ln x as x approaches 0 from the right" → false DISAGREES; "the |
| NLP | 5 | y' = -2y + 1, y(0)=3, solve from 0 to 2 in 2 steps → silent no output; "sin x squared" → sin(x^2); ~19 ordinary phrasings unrecognized; y''/ |
| LIMIT | 2 | order > 12 rejected by diff/taylor; no Laplace rule for log t/t^n/t^p sin t |

### Issues by severity

| Severity | Count | Short reproducer |
|---|---|---|
| WRONG | 3 | "the integral of x from pi to 0" → +4.9348 (should be −4.9348); "the limit of ln x as x approaches 0 from the right" → false `DISAGREES`; "the closed form of fibonacci" → "it has no loops" |
| NLP | 5 | `y' = -2y + 1, y(0)=3, solve from 0 to 2 in 2 steps` → silent no output; "sin x squared" → `sin(x^2)`; ~19 ordinary phrasings unrecognized; `y''`/`dy/dt` ODE phrasings fail; recurrence closed-form phrasings leak raw parse errors |
| LIMIT | 2 | order > 12 rejected by diff/taylor; no Laplace rule for `log t`/`t^n`/`t^p sin t` |
| CRASH | 0 | — |
| HANG | 0 | — |
| DETERMINISM | 0 | all goldens diff-identical |

See `FINDINGS.md` for exact commands and pasted outputs.


## Takeaway
The calculus/transform engines are correct and deterministic, but the **English front-end is the weak link**: it silently flips reversed integral bounds (wrong sign), silently drops a verbatim ODE "solve" request, misparses "sin x squared", takes "closed form of fibonacci" to a nonsense answer, and rejects many ordinary calculus phrasings instead of routing them.

### Original takeaway (verbatim)

The calculus/transform engines are correct and deterministic, but the **English
front-end is the weak link**: it silently flips reversed integral bounds
(wrong sign), silently drops a verbatim ODE "solve" request, misparses
"sin x squared", takes "closed form of fibonacci" to a nonsense answer, and
rejects many ordinary calculus phrasings instead of routing them.
