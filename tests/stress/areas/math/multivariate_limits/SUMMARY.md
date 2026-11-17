# SUMMARY — `multivariate_limits`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 11
- Files created: 11

### Original preamble

Area: limits and continuity in 2+ variables (finite points, infinity,
path-dependent limits, removable singularities, separate-vs-joint continuity,
piecewise/step functions, asymptotic behaviour).

### Counts

- **Distinct limit/continuity queries tried: ~913**
  - 612 systematic path-limit / slice-continuity cases (`gen_cases.py`):
    27 two-variable functions × 17 paths, plus infinity/finite-point paths,
    slice continuity, 20 classic limits, 13 continuity cases.
  - 97 adversarial indeterminate forms (`gen_tricky.py`), including 24
    multivariate rational asymptotics at infinity.
  - 164 randomized 0/0 and inf/inf limits cross-checked against sympy
    (`fuzz_limits.py`).
  - ~40 ad-hoc probes (deep nesting, floor/ceil, English frontend, MCP schemas,
    `where` clauses, divergence detector).
- **Verification**: claimed finite limits were checked along the exact path with
  mpmath at 50–60 decimal places; classic/adversarial limits cross-checked with
  sympy 1.14. Ground truth was computed independently of ucas.
- **Files created in this folder**: 11 CLI goldens (`.ucas`+`.out` = 22 files),
  6 MCP goldens (`.jsonl`+`.out` = 12 files), 1 `.flags` (`--flat`), 3 scratch
  driver scripts, 3 scratch result JSONs, `FINDINGS.md`, `SUMMARY.md`.
- **Determinism**: all 17 goldens generated twice and `diff`-ed — byte-identical.
  All runs bounded by `timeout`; no nonzero exit, no timeout, no truncated JSON.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | floor/ceil limits at infinity; exp(1/x) domain; off-grid spike continuity; false DISAGREES self-check |
| NLP | 1 | English multivariate limit/continuity requests rejected/misparsed |
| LIMIT | 3 | symbolic give-ups; no joint limit/continuity; tuple where conditions unparseable |

### Issues by severity

| Severity | Count | Summary |
|----------|-------|---------|
| CRASH    | 0 | none |
| HANG     | 0 | none |
| DETERMINISM | 0 | none (all goldens byte-identical across runs) |
| WRONG    | 4 | floor/ceil limits at infinity; `exp(1/x)` domain; off-grid spike continuity; false `DISAGREES` self-check |
| LIMIT    | 3 | symbolic give-ups; no joint limit/continuity; tuple `where` conditions unparseable |
| NLP      | 1 | English multivariate limit/continuity requests rejected/misparsed |

### Headline issues (one-line reproducers)

1. **WRONG** `limit floor(x)/x x->inf` -> 0 (true 1), with `DISAGREES` printed:
   `ucas 07_wrong_floor.ucas`
2. **WRONG** `continuity exp(1/x)` claims undefined on `(0, 0.001408881876)`
   (overflow artifact): `ucas 08_wrong_overflow_domain.ucas`
3. **WRONG** off-grid spike `(x==0.1234567?1:0)` declared continuous:
   `ucas 09_wrong_isolated_spike.ucas`
4. **WRONG** correct `log(x)->-inf` flagged `DISAGREES` by own numeric check:
   `ucas 11_selfcheck_disagrees.ucas`
5. **LIMIT** `cot(x)-1/x`, `exp(-1/x^2)/x`, `x^x` two-sided etc. give
   `not found symbolically`: `ucas 10_giveups.ucas`
6. **NLP** English "limit ... as (x,y) approaches (0,0)" -> not_understood:
   `ucas --mcp < mcp_english_multivariate.jsonl`
7. **LIMIT** joint multivariate limits rejected; slices reported independently:
   `ucas --mcp < mcp_multivariate_reject.jsonl`


## Takeaway
The limit engine returns correct values for ordinary path-dependent and removable-singularity cases, but L'Hôpital on `floor`/`ceil` produces flatly wrong limits at infinity (with `ok:true` and a failing self-check over MCP), while the continuity checker mistakes float overflow for a domain hole and misses isolated off-grid discontinuities; there is no joint-limit facility and the English frontend cannot express multivariate limit requests.

### Original takeaway (verbatim)

The limit engine returns correct values for ordinary path-dependent and
removable-singularity cases, but L'Hôpital on `floor`/`ceil` produces flatly
wrong limits at infinity (with `ok:true` and a failing self-check over MCP),
while the continuity checker mistakes float overflow for a domain hole and
misses isolated off-grid discontinuities; there is no joint-limit facility and
the English frontend cannot express multivariate limit requests.

### Confinement

All files were written only under `tests/stress/areas/math/multivariate_limits/`.
No source file, Makefile, existing test, `opencode.json`, git state, or other
subagent's folder was touched; no build was run.
