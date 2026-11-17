# SUMMARY — `timeout_isolation`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 4
- Files created: not recorded

### Coverage

- **156 deliberately long searches** in `json_long_150.jsonl` (CLI `--json`):
  `gates` 32, `find` 30, `approx` 25, `fit` 25, `prove` 20, `equiv` 12,
  `range` 12. Every one returned `error.code == "timeout"`.
  `gates` uses `nodes 4194304` / `8388608` (at and above the 2^22 synthesis
  cap); `equiv` uses nested 64-bit multiplies (hard SAT); `range` uses an
  expensive nested `exp`/`sin` real function.
- Plus **~40 edge/probe queries**: `timeout_s` = 0, -1, -0.5, 1e9, 1e300,
  1e400, 4294967.3, 9007199254740992, string, null, true; `reset`/`define`
  with `timeout_s`; hard `equiv`/`range`; repeated timeouts; crash-shaped
  arguments (`nodes 1e18`, `degree 1e6`, empty `g`, negative `nodes`).
- MCP equivalents in `mcp_timeout.jsonl` (15 tool calls, 8 timeouts) and
  `mcp_timeout_edges.jsonl` (14 calls, 8 timeouts).

### Files created

| file | purpose |
|------|---------|
| `json_long_150.jsonl` / `.out` | golden: 156 long searches, all `code: timeout`, with state checks |
| `json_timeout_edges.jsonl` / `.out` | golden: 0/negative/huge/`null`/`true`/string-timeout, repeated timeouts, reset |
| `mcp_timeout.jsonl` / `.out` | golden: every target op times out over MCP, `isError:true`, `code:timeout`, state intact |
| `mcp_timeout_edges.jsonl` / `.out` | golden: MCP repeated timeouts, huge timeout success, reset with timeout |
| `FINDINGS.md` | issues found |
| `SUMMARY.md` | this file |

All four `.out` files were generated with the exact `run.sh` commands
(`--json --files none < f.jsonl` for `json_*`, `--mcp < f.jsonl` otherwise)
and reproduced byte-identically on a second run.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | string timeout_s accepted but silently disables the limit |
| LIMIT | 2 | non-positive/non-finite timeout_s do not limit; latent int overflow in poll wait |

### Issues by severity

| severity | count | summary |
|----------|-------|---------|
| CRASH | 0 | no crash or `code: internal` observed |
| HANG past requested timeout | 0 | all 156 searches were killed on time |
| WRONG | 1 | string `timeout_s` accepted but silently disables the limit |
| LIMIT | 2 | non-positive/non-finite `timeout_s` do not limit; latent int overflow in poll wait |
| DETERMINISM | 0 | all four goldens reproduced exactly |


## Takeaway
The fork-based `timeout_s` isolation is sound for numeric positive limits: the `code: timeout` error is correct, session state is unchanged, repeated timeouts are safe, and no child process leaks.

### Original takeaway (verbatim)

The fork-based `timeout_s` isolation is sound for numeric positive limits:
the `code: timeout` error is correct, session state is unchanged, repeated
timeouts are safe, and no child process leaks. The gap is validation: accepted
string, zero, negative and infinite `timeout_s` values disable the limit
silently.
