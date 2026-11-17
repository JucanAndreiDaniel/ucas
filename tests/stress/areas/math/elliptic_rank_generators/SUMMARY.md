# SUMMARY — `elliptic_rank_generators`

## Counts
- Distinct expressions/queries tried: 62,800
- Goldens written: 13
- Files created: not recorded

### Files created

- CLI goldens: `01_q_summary` … `10_q_mordell` (10 × `.ucas` + 10 × `.out` = 20 files)
- MCP goldens: `mcp_elliptic_q`, `mcp_elliptic_ff`, `mcp_errors` (3 × `.jsonl` + 3 × `.out` = 6 files)
- `FINDINGS.md`, `SUMMARY.md` (2 files)
- **Total: 28 files**, all inside `tests/stress/areas/math/elliptic_rank_generators/`.
- Every golden was run twice under `timeout` and diffed: all deterministic; all exit 0.
  No crash, hang, or nondeterminism was kept as a golden.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | F1 (Tate internal not divisible by 64/256/729/1024 on valid curves), F2 (negative scalar misparsed as modulus) |
| LIMIT | 3 | F3 (Schoof unsupported on P-521), F4 (default generator search misses large generator), F5 (cosmetic negated P: display) |

### Coverage (distinct queries issued)

| Area | Queries |
|------|---------|
| Independent Python group-law cross-check over Q (add/mul/on) | 215 |
| Independent Python group-law cross-check over F_p (ec_points/ec_info/ec_add/ec_mul, 17 small curves) | 374 |
| a_p (Q) vs #E(F_p) (FF) cross-check, 12 curves × primes | 424 |
| Canonical height scaling h(nP)=n^2 h(P) | 36 |
| BSD / functional-equation consistency scan (Q curves) | 200 |
| Mordell curves y^2=x^3+k, k=-30..30 | 60 |
| j=1728 family y^2=x^3-a*x, a=1..400 | 600 |
| j=0 family y^2=x^3+k, k=1..1500 | 1500 |
| Random general Weierstrass curves (small / large coefficients) | 500 |
| Random short curves (|A|,|B| <= 20000) | 600 |
| Exhaustive short curves (A,B in [-120,120]) | 58,074 |
| Named curves, edge cases, parsing/associativity probes (P-521, P-256, secp256k1, ec_vectors, singular curves, ...) | ~40 |
| Golden corpus statements (CLI 10 files + MCP 3 files) | ~135 |

**Total distinct queries: ~62,800** (well above the 150+ target).
All independent cross-checks (group law over Q and F_p, a_p vs #E, height scaling, BSD
integrality) **passed** — the implementation is mathematically sound in those areas.

### Issues by severity

| Severity | Count | IDs |
|----------|-------|-----|
| CRASH | 0 | — |
| HANG | 0 | — (very large point search is slow but honours `timeout_s`) |
| WRONG | 2 | F1 (Tate internal `not divisible by 64/256/729/1024` on valid curves), F2 (negative scalar misparsed as modulus) |
| NLP | 0 | (F2's root cause is a parse error, counted under WRONG) |
| LIMIT | 3 | F3 (Schoof unsupported on P-521), F4 (default generator search misses large generator), F5 (cosmetic negated `P:` display) |
| DETERMINISM | 0 | — |


## Takeaway
The Q and finite-field arithmetic is solid (589 independent group-law checks, 212 trace cross-checks, 36 height relations all pass), but Tate's algorithm at p=2/p=3 throws `internal: X is not divisible by Y` on about 1% of perfectly nonsingular curves, and an unparenthesised negative `ec_mul` scalar on an equation-specified F_p curve is silently reparsed as part of the modulus.

### Original takeaway (verbatim)

The Q and finite-field arithmetic is solid (589 independent group-law checks, 212 trace
cross-checks, 36 height relations all pass), but Tate's algorithm at p=2/p=3 throws
`internal: X is not divisible by Y` on about 1% of perfectly nonsingular curves, and an
unparenthesised negative `ec_mul` scalar on an equation-specified F_p curve is silently
reparsed as part of the modulus.
