# SUMMARY — `magic_constants`

## Counts
- Distinct expressions/queries tried: 270
- Goldens written: 20
- Files created: 16

### Counts

* **Distinct expressions / queries tried: ~270**
  * CLI: 16 `.ucas` files, ~160 statements (fit sweeps, error sweeps, bit-hack
    equiv/range/show, magic divisors).
  * MCP: 4 `.jsonl` files, ~110 tool calls (analyze fit/error/equiv/range;
    rings magic).
  * External oracles: 2000 `magic` queries (`magic_all.ucas`), dense exact search
    over 2049 constants x 2^23 mantissas, full-domain integer checks.
* **Files written:** 16 `.ucas` + 16 `.out` (CLI goldens), 4 `.jsonl` + 4 `.out`
  (MCP goldens), `magic_all.ucas`, `magic_all.raw`, `FINDINGS.md`, `SUMMARY.md`,
  `gen_tests.py`, `run_all.py`, `verify_guess.py`, `search_K.py`,
  `verify_fit_error.py`, `verify_magic.py`.
* **Goldens checked for determinism: all 20** (each run twice, byte-identical,
  exit 0). No hangs, crashes or nondeterminism observed.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | fit returns non-optimal K; error max-rel claim is not a bound and disagrees with fit; error ignores G's where/range domain |
| LIMIT | 3 | bit hacks fail at negatives/ftz (verified); SAT counterexample not reproduced for asuint/asfloat identity; MCP arg strictness |

### Issues by severity

| Severity | Count | Summary |
|---|---|---|
| WRONG | 3 | fit returns non-optimal K; `error` max-rel claim is not a bound and disagrees with fit; `error` ignores G's `where`/range domain |
| LIMIT | 3 | bit hacks fail at negatives/ftz (verified); SAT counterexample not reproduced for asuint/asfloat identity; MCP arg strictness |
| CRASH / HANG / DETERMINISM | 0 | none found |


## Takeaway
`fit`/`error` on the inverse-sqrt magic constant optimise/report a small random sample rather than the domain (fit's K `0x5f376033` is beaten by `0x5f37642f`, `error` misses 99.95%-error subnormals and ignores `where`), while `rings`'s division magic numbers for divisors 1..1000 all verify exactly.

### Original takeaway (verbatim)

`fit`/`error` on the inverse-sqrt magic constant optimise/report a small random
sample rather than the domain (fit's K `0x5f376033` is beaten by `0x5f37642f`,
`error` misses 99.95%-error subnormals and ignores `where`), while `rings`'s
division magic numbers for divisors 1..1000 all verify exactly.
