# SUMMARY — `bigint_extremes`

## Counts
- Distinct expressions/queries tried: 190
- Goldens written: 15
- Files created: not recorded

### Counts

- Distinct expressions/queries tried: **≈190** (164 verified bigint/golden
  statements + MCP bigint/factor calls + exploratory probes and bug
  reproducers). Categories: boundary values (2^61, 2^63, 2^64 and neighbours),
  factorials (0!…1000!), huge powers (2^n, 10^n, 3^n up to 10^5 digits),
  `bigint`/`bigint_factor`, primality on primes/semiprimes/Carmichael numbers,
  gcd/lcm of big values, binomials, modular exponentiation with exponents up
  to 10^5, Fibonacci at indices 10…1000 (exact via binomial identity),
  10³–10⁶-digit integers, and negative div/mod semantics.
- Golden CLI files: **12** (`01_boundaries` … `12_digit_extremes`) — 164
  statements, all verified against a Python oracle and run twice for
  determinism. Largest golden 135 KB (10^50000).
- Golden MCP files: **3** (`mcp_bigint`, `mcp_factor`, `mcp_intshow`) — 40
  tool calls, all `ok:true`, byte-identical across two runs.
- Bug reproducer files (no golden `.out`):
  `bug_int_overflow.ucas`, `bug_int_symbolic.ucas`, `bug_hang_factor.ucas`.
- Issues by severity: **WRONG 3, HANG 2, LIMIT 4, NLP 1, DETERMINISM 0**.
- Nondeterminism found: none (all goldens and factorization/primality probes
  were byte-identical across runs).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 2 | — |
| WRONG | 3 | — |
| NLP | 1 | — |
| LIMIT | 4 | — |

## Takeaway
`bigint`/`bigint_factor` are solid and deterministic through ~10^5 digits, but the general `int` type silently breaks at the signed-64-bit boundary (loops/sums error out; function results go symbolic), 10⁶-digit printing and large-semiprime factoring hang, and the English frontend misroutes “continued fraction”.

### Original takeaway (verbatim)

`bigint`/`bigint_factor` are solid and deterministic through ~10^5 digits,
but the general `int` type silently breaks at the signed-64-bit boundary
(loops/sums error out; function results go symbolic), 10⁶-digit printing and
large-semiprime factoring hang, and the English frontend misroutes
“continued fraction”.
