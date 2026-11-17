# SUMMARY — `integer_factorization`

## Counts
- Distinct expressions/queries tried: 378
- Goldens written: 14
- Files created: not recorded

### Coverage
- **Distinct queries tried: 378** (371 generated cases in the sweep harness + 7 focused probes
  for pseudoprimes, 2^40 semiprimes, argument types, huge expressions and explicit `timeout_s`).
- Categories: small primes; large/Mersenne primes; semiprimes (factors up to 2^40); prime powers;
  Carmichael numbers (33); highly composite numbers (46); Fibonacci/Lucas numbers; factorials and
  binomials; perfect powers; numbers near 2^63/2^64; negatives, zero and one; malformed/wrong
  factor arguments; huge composites and perfect squares of 61/64-bit primes.
- Interfaces exercised: CLI `bigint factor`, CLI `factorint`, MCP `abstract_algebra.bigint_factor`,
  MCP `abstract_algebra.bigint`, MCP `rings.factorint`, plus wrong MCP argument types.
- Independent verification: each completed result's factors were multiplied in Python and every
  factor was re-tested for primality with `sympy.isprime`; 334 MCP results and 115 CLI headlines
  verified this way. All completed results were correct — no wrong product, composite factor,
  missing factor, or false passing check among them.

### Files created (all under `tests/stress/areas/math/integer_factorization/`)
- **14 CLI goldens** (`01_small_primes` … `14_pseudoprimes`), each `.ucas` + `.out` — 125 statements.
- **5 MCP goldens** (`mcp_bigint_factor`, `mcp_factorint`, `mcp_bigint_expr`, `mcp_errors`,
  `mcp_argtypes`), each `.jsonl` + `.out` — 67 calls.
- `FINDINGS.md`, `SUMMARY.md`.
- Total: 40 files. Every golden was run twice and `diff`-clean (deterministic); all runs used
  `timeout 15`.

### Compliance
All files were created only in `tests/stress/areas/math/integer_factorization/`. No source, Makefile, existing
test, or `opencode.json` was modified; no `make` or `git` command was run; every run was bounded by
`timeout 15` (one explicit 30 s characterization in FINDINGS.md).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | after its internal ~25 s budget MCP returns ok:true with a composite in factors[].prime, only flagged by a not_complete string and the headl |
| LIMIT | 1 | negative sign omitted from structured factors (product of factors ≠ negative value) |

### Issues by severity
| Severity | Count | Short description |
|---|---|---|
| `HANG` | 1 (4 inputs) | factorization of large prime squares / `2^256-1` / `2^400+1` never returns within 15 s (CLI and MCP) |
| `WRONG` | 1 | after its internal ~25 s budget MCP returns `ok:true` with a composite in `factors[].prime`, only flagged by a `not_complete` string and the headline |
| `LIMIT` | 1 | negative sign omitted from structured `factors` (product of factors ≠ negative `value`) |
| `CRASH` / `DETERMINISM` / `NLP` | 0 | none observed |

All issues are documented in `FINDINGS.md` with copy-pasteable reproducers and exact observed output.
The hanging / incomplete cases were deliberately **not** added as golden `.out` files.


## Takeaway
Factorization is correct and deterministic for every input that completes, but Pollard-Brent rho hangs on large prime squares / large-smooth composites and, when the MCP side finally gives up, it reports success while leaving a composite in the `prime` field of the structured result.

### Original takeaway (verbatim)
Factorization is correct and deterministic for every input that completes, but Pollard-Brent rho
hangs on large prime squares / large-smooth composites and, when the MCP side finally gives up, it
reports success while leaving a composite in the `prime` field of the structured result.
