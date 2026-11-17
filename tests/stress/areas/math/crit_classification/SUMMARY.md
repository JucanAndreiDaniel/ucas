# SUMMARY — `crit_classification`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 14
- Files created: not recorded

### What was tried
- **~265 distinct expressions / queries**: 141 univariate functions in
  `exprs_all.txt` (polynomials with known derivative roots, trig/exponential
  combinations, plateaus, cusps/abs, non-differentiable points, no-critical-point
  functions, stationary inflections, high-frequency/oscillatory cases), plus
  ~120 additional adversarial probes (clustered roots, underflow, poles,
  piecewise `?:`, clustered/infinite critical points, 12 bivariate functions,
  and a 30-expression crash/hang sweep), plus ~15 MCP `properties` / `hessian`
  oracle queries.
- Independent oracle: `oracle.py` numerically differentiates each function by a
  dense [-10,10] scan + bisection and compares locations & min/max/inflection
  classifications against `analyze.crit`; MCP `properties.zeros`,
  `properties.monotonic`, `properties.convexity` and `calculus.hessian` are the
  internal cross-checks.
- Every candidate was run under `timeout` (10–30 s). Exit codes were recorded.

### Files created (all in this folder)
- CLI goldens (`.ucas` + `.out`): `01_polynomials`, `02_trig_exp`,
  `03_cusps_kinks`, `04_plateaus`, `05_no_critical`, `06_ranges_endpoints`,
  `07_missed_touching`, `08_underflow_rounding`, `09_parse_nondiff`,
  `10_highfreq_cap`, `11_multivariate` — 11 pairs, 5–24 statements each.
- MCP goldens (`.jsonl` + `.out`): `mcp_oracle_crosscheck`,
  `mcp_plateaus`, `mcp_cap` — 3 pairs (13 / 6 / 2 calls).
- Helpers/catalog: `oracle.py`, `exprs.txt`, `exprs_all.txt`.
- Reports: `FINDINGS.md`, `SUMMARY.md`.
- All 14 goldens were generated twice and `diff`ed: **all deterministic**;
  all exit code 0. No crash, hang, or nondeterministic case was found (so none
  were promoted to goldens, per `SPEC.md` rules).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | F1 (missed touching stationary inflections), F2 (underflow false inflections), F3 (plateau inconsistency), F4 (500-point structured truncati |
| NLP | 1 | F7 (unknown function name → bogus multiplication) |
| LIMIT | 4 | F5 (no endpoints), F6 (2D gradient only), F8 (cusps not classified), F9 (infinite critical points sampled) |

### Issues by severity
| Severity | Count | IDs |
|----------|-------|-----|
| WRONG   | 4 | F1 (missed touching stationary inflections), F2 (underflow false inflections), F3 (plateau inconsistency), F4 (500-point structured truncation) |
| LIMIT   | 4 | F5 (no endpoints), F6 (2D gradient only), F8 (cusps not classified), F9 (infinite critical points sampled) |
| NLP     | 1 | F7 (unknown function name → bogus multiplication) |
| CRASH / HANG / DETERMINISM | 0 | — |


## Takeaway
`crit` is reliable for isolated sign-changing roots of smooth functions, but is unsound/ incomplete for derivative roots that merely touch zero (F1), rounding-underflow plateaus (F2/F3), structured-result size (F4), closed-interval endpoints (F5), and multivariate classification (F6) — with an additional English frontend misparse for unknown function names (F7).

### Original takeaway (verbatim)
`crit` is reliable for isolated sign-changing roots of smooth functions, but is
unsound/ incomplete for derivative roots that merely touch zero (F1),
rounding-underflow plateaus (F2/F3), structured-result size (F4), closed-interval
endpoints (F5), and multivariate classification (F6) — with an additional English
frontend misparse for unknown function names (F7).
