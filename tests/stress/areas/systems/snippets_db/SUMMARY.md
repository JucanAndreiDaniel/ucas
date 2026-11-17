# SUMMARY — `snippets_db`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 20
- Files created: not recorded

### Coverage

- **Distinct CLI statements / queries in the durable goldens: 168**
  across 19 `.ucas` files (`01_`–`19_`), covering:
  - `find ... snippets` against the built-in database for 1/2/3 inputs and
    8/16/32-bit widths (matched, unmatched, complex, constant, shifts);
  - find with no name, with a named custom `.snip`, and with a file that does
    not exist;
  - 53 hand-built malformed/edge-case/controlled `.snip` fixtures (`fx_*.snip`): empty,
    header-only, bad version/points/inputs/width, missing/garbage header,
    levels with 0/1/negative/huge/70 entries, wrong word counts, unknown and
    misnamed operations, forward/self references, tab/CRLF/NUL/blank/overlong
    lines, huge and out-of-range constants, duplicate hashes, free variables,
    non-monotonic levels and a binary op with a missing operand;
  - named and unnamed `snippets grow` (fresh, resume, shape mismatch, bad
    hash, unknown leaf, levels mismatch), argument-range validation, and
    session-DB lifetime probes.
- **MCP queries: 6** tool calls in `mcp_snippets.jsonl` (session define, raw
  find with snippets, unnamed grow, rejected named grow, 1-input find, state).
- Additional exploratory probes (~200 one-off CLI/MCP invocations) were used
  to locate the issues below; the durable catalog keeps only deterministic,
  isolated reproducers.

### Files written in this folder

- 19 `NN_*.ucas` + 19 `NN_*.out` deterministic CLI goldens.
- 1 `mcp_snippets.jsonl` + 1 `mcp_snippets.out` MCP golden.
- 53 `fx_*.snip` fixtures (read-only inputs for the goldens).
- 3 `gx_*.snip` files produced by `15_grow_named.ucas` (regenerated on each run).
- `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | WRONG-1 session DB pollution; WRONG-2 duplicate-hash shadowing; WRONG-3 false cost claim from malformed levels; WRONG-4 silent missing-opera |
| LIMIT | 3 | LIMIT-1 single session DB; LIMIT-2 Unicode/path names rejected; LIMIT-3 unchecked constant overflow |

### Issues by severity

| Severity | Count | IDs |
|----------|-------|-----|
| CRASH    | 0     | —   |
| HANG     | 0     | —   (one apparent hang was `a ^ b` = power on 2-input u8, not snippets) |
| WRONG    | 4     | WRONG-1 session DB pollution; WRONG-2 duplicate-hash shadowing; WRONG-3 false cost claim from malformed levels; WRONG-4 silent missing-operand misparse |
| NLP      | 0     | —   |
| LIMIT    | 3     | LIMIT-1 single session DB; LIMIT-2 Unicode/path names rejected; LIMIT-3 unchecked constant overflow |
| DETERMINISM | 0  | —   every golden diffed clean across two runs |


## Takeaway
The `.snip` loader is robust against almost every malformed file (clean diagnostics, no crashes, no writes outside the folder), but its single global session-DB state, first-hash-only lookup, and unchecked `levels`/arity parsing let hand-crafted files produce wrong "reads an input", "differs elsewhere", and wrong-cost answers.

### Original takeaway (verbatim)

The `.snip` loader is robust against almost every malformed file (clean
diagnostics, no crashes, no writes outside the folder), but its single global
session-DB state, first-hash-only lookup, and unchecked `levels`/arity parsing
let hand-crafted files produce wrong "reads an input", "differs elsewhere",
and wrong-cost answers.

### Folder confinement

All files listed above live only in `tests/stress/areas/systems/snippets_db/`. The built-in
database was read from `$ROOT/snippets` (absolute path compiled
into the binary) read-only; no fixture was copied there and no source, Makefile,
test or `opencode.json` was touched. All runs were bounded with `timeout`.
