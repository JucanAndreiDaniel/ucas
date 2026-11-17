# SUMMARY — `mcp_op_inventory`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 49
- Files created: not recorded

### Counts
- MCP operations enumerated: **248** (239 grouped `op` values across 18 tool schemas +
  9 standalone tools = 27 tools; `session schema` reports exactly 248 `commands`).
- Stress files scanned for coverage: **11,928**.
- Ops with genuine pre-existing coverage: **203**.
- Ops with NO genuine coverage (empty-args only): **45** (GAP).
- Calls generated for the 45 GAP ops: **258** (5+ valid + 1 malformed each), all under
  `timeout 15` and run twice for determinism.
- Golden `.out` files kept: **49** (45 combined op files, of which `mma`+`adamfit` were
  replaced: 6 single-call `mma` goldens + 6 single-call `adamfit` reproducers without goldens).
  Breakdown: 43 single-file op goldens + 6 mma single-call goldens = **49 goldens**;
  6 adamfit single-call reproducers with **no golden** (nondeterministic timing).
- JSONL test files: **55** (45 originals − 2 split (`34_mma`,`35_adamfit`) + 12 split files).

### Reproducer commands (quick)
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_op_inventory
# deterministic golden example (abstract algebra)
timeout 15 $ROOT/ucas --mcp < 01_abexact.jsonl > /tmp/o.out 2>/tmp/o.err && diff /tmp/o.out 01_abexact.out
# nondeterminism (adamfit) — diff two runs
timeout 15 $ROOT/ucas --mcp < 35a_valid0.jsonl > /tmp/a.out 2>/dev/null
timeout 15 $ROOT/ucas --mcp < 35a_valid0.jsonl > /tmp/b.out 2>/dev/null
diff /tmp/a.out /tmp/b.out
# slow mma single call
timeout 15 $ROOT/ucas --mcp < 34a_valid0.jsonl > /tmp/m.out 2>/dev/null
```


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 3 | mma (slow, ~9 s/call), ec_pairing (kind needs P/Q/n), GAP coverage (45 ops) |
| DETERMINISM | 1 | adamfit (wall-clock timing in response text; no golden kept) |

### Issues by severity
| Severity | Count | Ops |
|---|---|---|
| CRASH | 0 | — |
| HANG | 0 | — (cumulative batch timeouts on `mma` only; per-call <15 s) |
| WRONG | 0 | — |
| DETERMINISM | 1 | `adamfit` (wall-clock timing in response text; no golden kept) |
| LIMIT | 3 | `mma` (slow, ~9 s/call), `ec_pairing` (kind needs P/Q/n), GAP coverage (45 ops) |


## Takeaway
All 248 MCP operations were inventoried and 45 previously untested ones now have >=5 valid calls + 1 malformed call each (258 calls, 49 deterministic goldens); the only defect surfaced is `adamfit` leaking wall-clock time into its response, with no crashes, hangs, or wrong envelopes found in the untouched ops.

### Original takeaway (verbatim)
All 248 MCP operations were inventoried and 45 previously untested ones now have >=5 valid
calls + 1 malformed call each (258 calls, 49 deterministic goldens); the only defect surfaced
is `adamfit` leaking wall-clock time into its response, with no crashes, hangs, or wrong
envelopes found in the untouched ops.
