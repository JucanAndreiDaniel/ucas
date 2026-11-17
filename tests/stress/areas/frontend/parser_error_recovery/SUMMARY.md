# SUMMARY — `parser_error_recovery`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 178
- Files created: not recorded

### Counts

- **`.ucas` files:** 173 (each isolates one malformed-then-valid scenario, 3–6 statements)
- **Statements executed across `.ucas` files:** 539
- **Wire files:** 5 (`.jsonl`: 2 `--json`, 3 `--mcp`, of which 1 uses `--flat`), ~40 JSON-RPC/JSON calls
- **Distinct scenarios / queries tried:** ~213 (173 CLI + ~40 wire); ~580 total statements
- **Goldens (`.out`):** 178 (173 CLI + 5 wire)
- **Helper scripts kept for reproducibility:** `gen.py`, `run.py`, `gen_wire.py`
- **Determinism:** all 178 would-be goldens run twice and byte-compared; 0 nondeterministic
- **Adversarial sweeps:** 100 trailing-operator lines, 100 unclosed brackets, 1000 bad
  statements, NUL / invalid UTF-8 bytes, 10 KB unterminated string — all bounded, no crash/hang

### Reproduce everything

```sh
cd $ROOT/tests/stress/areas/frontend/parser_error_recovery
python3 gen.py && python3 run.py && python3 gen_wire.py
# then, from tests/stress/:
sh run.sh    # (checks every stress area; this folder contributes 178 goldens)
```


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 5 | swallowed lines / silent command-word capture; leaked free-variable names; byte-based columns; leading-operator command capture; ok:false +  |
| LIMIT | 1 | lexical errors (unterminated string, bad Unicode, NUL) abort the whole file |

### Issues by severity

| Severity | Count | Summary |
|---|---|---|
| CRASH | 0 | none found |
| HANG | 0 | none found |
| WRONG | 5 | swallowed lines / silent command-word capture; leaked free-variable names; byte-based columns; leading-operator command capture; `ok:false` + success payload on JSON wire |
| LIMIT | 1 | lexical errors (unterminated string, bad Unicode, NUL) abort the whole file |
| DETERMINISM | 0 | none found |


## Takeaway
The statement loop *does* resume after ordinary parse errors and the JSON/MCP sessions survive them, but recovery is lossy and misleading: dangling operators swallow following lines (turning `show`/`bigint` into variables), failed definitions leak their names as free variables, Unicode shifts error columns by bytes, and a failed JSON request can still carry successful results.

### Original takeaway (verbatim)

The statement loop *does* resume after ordinary parse errors and the JSON/MCP
sessions survive them, but recovery is lossy and misleading: dangling operators
swallow following lines (turning `show`/`bigint` into variables), failed
definitions leak their names as free variables, Unicode shifts error columns by
bytes, and a failed JSON request can still carry successful results.
