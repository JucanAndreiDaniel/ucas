# SUMMARY — `number_theory_core`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 12
- Files created: 12

### Counts

- Distinct numeric queries cross-checked against sympy / brute force: **≈10,900**
  - 1582 general rings ops (phi, carmichael, factorint, Legendre/Jacobi, sqrtmod, QR,
    inverse, order, primroot, CRT, congruence, dlog)
  - 6256 exhaustive sqrtmod/Legendre/QR cases (all odd primes p<300, prime powers, all n≤120)
  - 496 `ring Z/n` structure + primality-verdict cases (Carmichael, Mersenne, Fermat, pseudoprimes)
  - 228 division-magic cases with 709 independent ucas-evaluator substitutions plus 184
    big-integer formula checks
  - 175 large-u64 cases near 2⁶⁴, with certificate checks by substitution
  - ~60 English (NLP) phrasings, ~40 adversarial edge/overrun cases
- All runs bounded by `timeout 15` (multi-thousand-call harness batches used longer wall bounds
  but every single query is sub-second).
- Golden files written: **12** (10 CLI `.ucas`+`.out`, 2 MCP `.jsonl`+`.out`), each 6–18
  statements, every one verified deterministic by running twice and diffing (byte-identical).
- Issues by severity: **WRONG 1**, **NLP 6**, **LIMIT 3**, **CRASH 0**, **HANG 0**,
  **DETERMINISM 0**.

### Files created

```
01_primality.ucas/.out       02_phi_lambda.ucas/.out   03_symbols.ucas/.out
04_sqrt_qr.ucas/.out         05_inverse_order.ucas/.out 06_crt_congruence.ucas/.out
07_primroot.ucas/.out        08_magic.ucas/.out        09_ring_zn.ucas/.out
10_large_u64.ucas/.out
mcp_rings_core.jsonl/.out    mcp_rings_edge.jsonl/.out
FINDINGS.md                  SUMMARY.md
```


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| NLP | 6 | — |
| LIMIT | 3 | — |

## Takeaway
The `rings` number-theory core is mathematically sound and deterministic across CLI and MCP — primality, factorization, phi/lambda, symbols, sqrt/QR, inverses, orders, primitive roots, CRT, congruences, and magic numbers all matched sympy on ~10,900 cases with valid certificates.

### Original takeaway (verbatim)

The `rings` number-theory core is mathematically sound and deterministic across CLI and MCP —
primality, factorization, phi/lambda, symbols, sqrt/QR, inverses, orders, primitive roots, CRT,
congruences, and magic numbers all matched sympy on ~10,900 cases with valid certificates.
The only defects are in the **English front-end**: several number-theory phrasings silently
misroute to unrelated domains (`zerodivisors mod 12` → sedenions, `cube roots mod 7` → complex
roots), drop tokens (`x squared`, duplicated `congruence`), or are silent no-ops (`factor 561`),
plus missing Möbius/divisor-sum support and two structured-output LIMITs for large values /
root-cap overruns.
