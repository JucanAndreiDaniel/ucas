# SUMMARY — `precision_controls`

## Counts
- Distinct expressions/queries tried: 170
- Goldens written: 11
- Files created: 26

### Counts

- Distinct expressions / queries tried: ~170 ad-hoc probes + 122 statements in CLI goldens + 12 MCP calls ≈ **304**.
- Files created: **26**
  - 11 CLI golden pairs: `01_types_int_real` … `11_types_mixed` (22 files, `.ucas` + `.out`)
  - 1 MCP golden pair: `mcp_precision.jsonl` + `mcp_precision.out` (2 files)
  - `FINDINGS.md`, `SUMMARY.md` (2 files)
- Issues by severity: **2 WRONG, 2 LIMIT, 0 CRASH, 0 HANG, 0 DETERMINISM** (deterministic cases only were kept as goldens).
- Determinism: every kept golden was run twice and `diff`ed; all matched. `approx` output was
  nondeterministic and was intentionally excluded from goldens.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 2 | — |

### Issues at a glance

1. **WRONG** — `expand 1/999999937*x` / `expand 2^60*x` / `expand 2/7` print rounded decimals
   while claiming `check: exact` / MCP `"same normal form over Q"`. Repro: `05_high_digit_constants.ucas`.
2. **WRONG** — `solve 0.3333333333333333*x = 1` returns `x = 3`, `residual 0`, `exact: true`
   although the written coefficient gives residual `1e-16`. Repro: `06_claims_exact.ucas`,
   `mcp_precision.jsonl` ids 9–10.
3. **LIMIT** — README's promised "printed rounded, with a note" note is missing for
   high-digit constants and coefficients > 2^53. Repro: `05_high_digit_constants.ucas`.
4. **LIMIT** — CLI silently accepts `ftz` on float-free functions and conflicting `ftz noftz`
   flags; MCP, by contrast, correctly requires both `ftz` and `nanbits`. Repro: `08_rounding_flags.ucas`.


## Takeaway
Precision claims are the weak point: ucas snaps long decimals to neat rationals and prints big rational coefficients as rounded decimals, then still labels the result `exact` / `residual 0`; sampled disclaimers, type-crossing differences, and MCP flag requirements were otherwise correct.

### Original takeaway (verbatim)

Precision claims are the weak point: ucas snaps long decimals to neat rationals and prints big
rational coefficients as rounded decimals, then still labels the result `exact` / `residual 0`;
sampled disclaimers, type-crossing differences, and MCP flag requirements were otherwise correct.
