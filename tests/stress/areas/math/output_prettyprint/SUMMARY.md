# SUMMARY — `output_prettyprint`

## Counts
- Distinct expressions/queries tried: 187
- Goldens written: 15
- Files created: not recorded

### Counts

- Distinct expressions / queries tried: **187**
  - 170 CLI statements across 15 `.ucas` files
  - 17 MCP `analyze` calls (`show`/`parse`) in `mcp_prettyprint.jsonl`
  - plus ad-hoc Python-driven probes (long literals, deep towers, repeated
    parse, exhaustive f16 round-trip check, threshold bisection) that fed many
    additional inputs.
- Files written (all inside `tests/stress/areas/math/output_prettyprint/`):
  - 15 golden pairs: `01_bigints` … `15_bool_list` (`.ucas` + `.out`)
  - 1 MCP golden pair: `mcp_prettyprint.jsonl` + `mcp_prettyprint.out`
  - `FINDINGS.md`, `SUMMARY.md`
  - Total: 34 files.
- Issues by severity:
  - CRASH: 0
  - HANG: 0
  - WRONG: 4 (F1 f64 17→10 digit round-trip / max-finite→inf, F2 signed-zero
    sign loss, F3 negative-NaN/payload round-trip, F4 misleading "exact"
    rational printing)
  - NLP: 0
  - LIMIT: 2 (F5 `real` overflow + 77-digit literal cap, F6 complex/symbolic
    unevaluated printing and type loss)
  - DETERMINISM: 0


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | — |
| LIMIT | 2 | — |

## Takeaway
`show` emits round-trip-safe digits for IEEE values (f16/f32/f64) but the reader/display path (`parse`, `show` of a bare literal, MCP `show`/`parse`) collapses everything to a 10-digit `real`, so a f64 printed value does not round-trip: the largest finite f64 re-reads as `inf`.

### Original takeaway (verbatim)

`show` emits round-trip-safe digits for IEEE values (f16/f32/f64) but the
reader/display path (`parse`, `show` of a bare literal, MCP `show`/`parse`)
collapses everything to a 10-digit `real`, so a f64 printed value does not
round-trip: the largest finite f64 re-reads as `inf`. Signed zero and NaN
payloads also fail to round-trip, and `simplify`'s "exact" claim is printed
next to a truncated decimal that is not the rational it claims to equal.

All 16 golden tests were generated twice and were byte-identical; all runs
completed in well under the 15 s bound, with no crashes, hangs, or
nondeterminism.
