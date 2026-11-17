# SUMMARY — `gates_find_cost`

## Counts
- Distinct expressions/queries tried: 227
- Goldens written: 13
- Files created: 13

### Counts

- **Distinct statements / queries tried:** 227 isolated CLI statements
  (auto-fuzzed across `gates`, `find`, `cost`, `mca`, `model`, `use`, plus
  malformed variants) + 63 `find` function/queries + 117 `mca` function×µarch
  pairs + 13 MCP calls (analyze cost/gates/find, x86 mca/models, flat mode)
  + ad-hoc probes. Roughly **430+ distinct statements/queries** exercised.
- **Golden files written:** 13
  - CLI (10): `01_gates_bits` … `10_degenerate` (`.ucas` + `.out`)
  - MCP (3): `mcp_cost_gates_find`, `mcp_errors`, `mcp_flat`
    (`.jsonl` + `.out`; `mcp_flat.flags` contains `--flat`)
  - Crash reproducer (no `.out`, as required): `crash_deep_expr.ucas`
- **Every golden run twice and `diff`ed:** identical (no nondeterminism).
- **Issues by severity:**
  - CRASH: 1 (deep-expression parser stack overflow; kills CLI and MCP server)
  - HANG: 0
  - WRONG: 0 (no false minimality, wrong cost ordering or unsound cost found)
  - NLP: 2 (documented `cost n` in basis gates unparseable; negative `find`
    op count parsed as function application)
  - LIMIT: 2 (6-input cap on `gates`; MCP error-code inconsistency for unknown µarch)
  - DETERMINISM: 0

### Reproducer quick reference

| Severity | One-line reproducer |
|---|---|
| CRASH | `cd tests/stress/areas/sat/gates_find_cost && timeout 15 $ROOT/ucas crash_deep_expr.ucas` → exit 139 |
| NLP | `printf 'basis b { and(x,y) = x&y cost 3 }\n' > /tmp/b.ucas && $ROOT/ucas /tmp/b.ucas` → `'cost' is not defined` |
| NLP | `find f -1` (with `f(x: u8 in 0..15) = x*x`) → reports on constant `1` |
| LIMIT | `gates` with 7 input bits → clean "up to 6 input bits" error |
| LIMIT | MCP `mca ... model nosuch` → `error.code=failed` vs `parse_error` for `cost` |

See `FINDINGS.md` for exact commands and outputs.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| NLP | 2 | — |
| LIMIT | 2 | — |

## Takeaway
The synthesis and cost machinery is remarkably robust — fuzzing 430+ statements found no false minimality claims, wrong costs, hangs or nondeterminism — but a deeply nested expression segfaults the parser (and takes the MCP server down with it), and the documented `cost n` annotation on basis gates does not parse.

### Original takeaway (verbatim)

The synthesis and cost machinery is remarkably robust — fuzzing 430+ statements
found no false minimality claims, wrong costs, hangs or nondeterminism — but a
deeply nested expression segfaults the parser (and takes the MCP server down
with it), and the documented `cost n` annotation on basis gates does not parse.
