# SUMMARY — `simplify_idempotence`

## Counts
- Distinct expressions/queries tried: 376
- Goldens written: 7
- Files created: 16

### Counts
- **Distinct expressions / queries tried:** ~376
  - Main corpus: **217** (58 polynomial, 32 rational, 23 trig, 23 log/exp,
    22 abs/min/max, 15 piecewise, 24 complex, 20 machine-type)
  - Targeted probes: ~159 (52 rational-sum/difference idempotence variants,
    36 machine-type bitwise/type probes, 22 + 14 cancellation-condition probes,
    15 sign-chain probes, 20 misc syntax/complex probes)
- **Files written (deliverables): 16**
  - CLI golden pairs: `01_rat_nonidem`, `02_nonidem_variants`,
    `03_expand_factor_nonidem`, `04_canonical_controls`, `05_cancel_conditions`,
    `06_machine_types` → 6 `.ucas` + 6 `.out`
  - MCP golden pair: `mcp_algebra_nonidem.jsonl` + `.out`
  - `FINDINGS.md`, `SUMMARY.md`
  - (Helper scripts and raw logs live under `_scratch/`, not part of the catalog.)
- **Checks run:** simplify/expand/factor idempotence (1–6 passes),
  canonicity `simplify(expand(e)) == simplify(factor(e))`, cancellation conditions,
  rewrite-order independence, determinism (every golden run twice).
- **All runs bounded with `timeout`; no source files edited, no rebuild, no git.**


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| LIMIT | 2 | — |

### Issues by severity
- **CRASH:** 0
- **HANG:** 0
- **WRONG:** 1 — `simplify`/`expand`/`factor` are not idempotent on rational
  differences with a negative leading numerator (`1/x - 1/y` → `-(x-y)/(x*y)`
  → `(y-x)/(y*x)`); 24/52 variants affected; reproduces via CLI and `algebra` MCP.
- **NLP:** 0
- **LIMIT:** 2 — (a) complex powers of `I` not reduced, breaking canonicity
  (`I**2 + 1` stays `I^2 + 1` instead of `0`); (b) `simplify` rejects bitwise
  `<< >> ~ &` on integer types with a contradictory "declare as int or uN" error.
- **DETERMINISM:** 0


## Takeaway
The algebra normalizer's biggest weakness here is idempotence: any rational whose combined numerator carries a leading minus sign needs two simplification passes to reach a fixed point (and the claim "same normal form" is made on the unstable first pass), while polynomial/trig/log canonicity and cancellation conditions are otherwise clean.

### Original takeaway (verbatim)
The algebra normalizer's biggest weakness here is idempotence: any rational
whose combined numerator carries a leading minus sign needs two simplification
passes to reach a fixed point (and the claim "same normal form" is made on the
unstable first pass), while polynomial/trig/log canonicity and cancellation
conditions are otherwise clean.
