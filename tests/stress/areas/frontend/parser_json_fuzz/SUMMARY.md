# SUMMARY — `parser_json_fuzz`

## Counts
- Distinct expressions/queries tried: 232
- Goldens written: 20
- Files created: 20

### Scope
Parser and JSON-frontend robustness across the whole command set, exercised through all
three frontends:
- CLI: `timeout 30 $ROOT/ucas NAME.ucas`
- JSON: `timeout 30 $ROOT/ucas --json --files none < NAME.jsonl`
- MCP: `timeout 30 $ROOT/ucas --mcp < NAME.jsonl`

Malformed/edge categories covered: unterminated strings and comments, unmatched brackets,
bad unicode identifiers and escapes, huge integer literals (>2^64), deep nesting, wrong
argument types (`f` as number/null/list), unknown cmd/op, missing and extra arguments,
invalid types (`u0`, `u65`, `i0`, `i65`, `f128`, `boolx`), invalid ranges (`5..1`, and ranges
outside a type's domain), duplicate params, reserved words as names, duplicate JSON keys,
truncated JSON, and bad AST shapes.

### Counts
- **Distinct inputs tried: 232** (plus ~100 additional exploratory probes while narrowing
  crash thresholds and checking error codes).
  - CLI `.ucas` statements: **94** across 14 files.
  - `--json` JSONL requests: **92** across 4 files (`json_*.jsonl`).
  - `--mcp` JSON-RPC requests: **46** across 2 files (`mcp_*.jsonl`, including `initialize`
    and `notifications/initialized`).
- **Golden files written: 20** (20 `.ucas`/`.jsonl` inputs + 20 matching `.out` goldens).
- All 20 goldens regenerated and `diff`-ed twice: **byte-identical** (deterministic).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 5 | CRASH-1 deep parens, CRASH-2 deep unary -, CRASH-3 deep sqrt(, CRASH-4 --json server dies, CRASH-5 --mcp server dies |
| HANG | 1 | HANG-1 quadratic blowup on a 100k-char identifier |
| LIMIT | 5 | LIMIT-1 lexical error aborts whole file, LIMIT-2 duplicate params, LIMIT-3 reserved words, LIMIT-4 out-of-domain ranges, LIMIT-5 invalid tim |

### Issues by severity
| Severity | Count | IDs |
|----------|------:|-----|
| CRASH    | 5 | CRASH-1 deep parens, CRASH-2 deep unary `-`, CRASH-3 deep `sqrt(`, CRASH-4 `--json` server dies, CRASH-5 `--mcp` server dies |
| HANG     | 1 | HANG-1 quadratic blowup on a 100k-char identifier |
| WRONG    | 0 | — |
| NLP      | 0 | — |
| LIMIT    | 5 | LIMIT-1 lexical error aborts whole file, LIMIT-2 duplicate params, LIMIT-3 reserved words, LIMIT-4 out-of-domain ranges, LIMIT-5 invalid `timeout_s` |
| DETERMINISM | 0 | — |

No undocumented error codes and no `ok:true` on syntactically malformed JSON were found.


## Takeaway
The JSON/MCP JSON parsers are strict and deterministic, but the statement parser has an unbounded-recursion family of SIGSEGVs (~1500 nested tokens), a quadratic long-identifier hang, and neither JSON frontend isolates a crashing request unless the client supplies `timeout_s`.

### Original takeaway (verbatim)
The JSON/MCP JSON parsers are strict and deterministic, but the statement parser has an
unbounded-recursion family of SIGSEGVs (~1500 nested tokens), a quadratic long-identifier
hang, and neither JSON frontend isolates a crashing request unless the client supplies
`timeout_s`.

### Confirmation
All files created live only in `tests/stress/areas/frontend/parser_json_fuzz/` (plus throwaway probes in
`/tmp` and `/tmp/opencode`). No source, Makefile, existing test, or `opencode.json` was
modified; no `make`, `git`, or commit was run; every run was bounded by `timeout`.
