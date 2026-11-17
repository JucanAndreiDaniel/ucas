# SUMMARY — `polynomial_gcd_resultant`

## Counts
- Distinct expressions/queries tried: ≈600
- Goldens written: 15
- Files created: 32

### Coverage

- **≈600 distinct expressions/queries tried.**
  - 378 machine-generated, sympy-oracle-checked queries: 40 random pairs over Z
    (gcd, lcm, Sylvester-determinant resultant, quotient, remainder), 20 shared-factor
    pairs, 20 rational-coefficient pairs, 10 structured pairs, 7 symbolic discriminants,
    27 factor/expand round-trips, 10 multivariate gcds, 4 zero/constant cases.
  - ~120 hand-probed edge cases: zero/constant/negative-leading polynomials, repeated and
    irreducible factors, cyclotomic `x^n-1` for many n, rational coefficients, symbolic
    coefficients (including reserved-name collisions), divisibility certificates,
    resultant-based `solve` systems, and high degrees (64, 65, 100, 120, 150, 200, 500,
    1000, 1000000).
  - ~120 statements in the 15 durable golden files, each run twice and byte-diffed.
- **Files created: 32** in `tests/stress/areas/math/polynomial_gcd_resultant/` only:
  - 13 CLI goldens `01_..13_*.ucas` + matching `.out`
  - 2 MCP goldens `mcp_algebra_core.jsonl`, `mcp_algebra_edges.jsonl` + matching `.out`
  - `FINDINGS.md`, `SUMMARY.md`
- All runs used `timeout 15` and the absolute binary path. No rebuilds, no source edits,
  no other folders touched.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | F1 (degree>64 gcd returns 1 with false certificate), F2 (false "irreducible" claim, deg 41–64), F3 (degree>64 atoms produce nonsense resulta |
| LIMIT | 2 | F5 (MCP structured lcm result contains non-parseable where CSE), F6 (reserved constant e collides with a symbolic coefficient) |

### Issues by severity

| Severity | Count | IDs |
|----------|-------|-----|
| WRONG    | 4     | F1 (degree>64 gcd returns 1 with false certificate), F2 (false "irreducible" claim, deg 41–64), F3 (degree>64 atoms produce nonsense resultants/discriminants/remainders), F4 (exact results printed as truncated decimals) |
| LIMIT    | 2     | F5 (MCP structured `lcm` result contains non-parseable `where` CSE), F6 (reserved constant `e` collides with a symbolic coefficient) |
| CRASH    | 0     | — |
| HANG     | 0     | — |
| NLP      | 0     | — |
| DETERMINISM | 0  | every would-be golden produced byte-identical output across two runs |

Sympy verified all gcd/lcm/resultant/quotient/remainder values in the normal (degree ≤ 64,
integer-coefficient) regime — no wrong answer was found there. The 6 "not done" outputs
from 64-bit coefficient overflow are the documented graceful limit, not defects.


## Takeaway
Exact algebra is reliable for small/medium integer polynomials, but degree > 64 silently switches to opaque-atom handling (wrong gcds, bogus resultants/discriminants) and degrees 41–64 add a false irreducibility claim; rational-coefficient results also lose exactness in printing despite "check: exact".

### Original takeaway (verbatim)

Exact algebra is reliable for small/medium integer polynomials, but degree > 64 silently
switches to opaque-atom handling (wrong gcds, bogus resultants/discriminants) and degrees
41–64 add a false irreducibility claim; rational-coefficient results also lose exactness
in printing despite "check: exact".
