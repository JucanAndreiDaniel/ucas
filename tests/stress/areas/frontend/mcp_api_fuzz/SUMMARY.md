# SUMMARY — `mcp_api_fuzz`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 10
- Files created: not recorded

### Coverage counts

* **Distinct queries / messages tried:** 352 JSON-RPC messages across 10 golden
  files, of which **289 are `tools/call` tool calls** (the remainder are
  `initialize`, `notifications/initialized`, `tools/list`, `ping`, resources /
  prompts, malformed and batch messages).  Additional ad-hoc probes (large
  source, NUL escapes, timed `c_optimize`, deep JSON nesting) are documented in
  FINDINGS.md.
* **Tools exercised:** all 27 registered tools in grouped mode
  (`analyze`, `calculus`, `algebra`, `properties`, `complex`, `hypercomplex`,
  `rings`, `transforms`, `solids`, `plot`, `c`, `x86`, `session`, `proofs`,
  `abstract_algebra`, `elliptic`, `elliptic_ff`, `homological`, `ucas`,
  `english`, `spirv_simplify`, `texalu`, `texenc`, `lperm`, `tcdot`, `winograd`,
  `ozaki`), plus 248 op-tools in `--flat` mode.
* **Fuzz dimensions:** every tool with missing / empty / wrong-typed `op` and
  `args`; unknown tools, unknown ops, unknown methods; wrong-typed required and
  optional arguments; ambiguous inputs and their `args.assume` keys
  (`caret`, `solve_for`, `free_vars`); malformed JSON-RPC (bad ids, missing
  params, batch arrays, notifications, wrong `jsonrpc` version, bare JSON
  scalars); grouped mode and `--flat` mode; state persistence / reset /
  non-leaking `assume`+`defaults`; determinism.

### Files created (in this folder only)

| File | Purpose |
|------|---------|
| `mcp_grouped_args.jsonl` / `.out` | 87 calls: every grouped/direct tool with missing/empty/wrong-typed args |
| `mcp_protocol.jsonl` / `.out` | 41 messages: malformed JSON-RPC (unknown methods, bad ids, batches, notifications, parse errors) |
| `mcp_protocol2.jsonl` / `.out` | 19 messages: protocol edges (wrong-typed names/params, duplicate ids, notifications with id, resources/prompts) |
| `mcp_ambiguous.jsonl` / `.out` | 13 calls: ambiguous errors with readings + `args.assume` keys and their resolutions |
| `mcp_state.jsonl` / `.out` | 11 calls: state persistence, non-leaking assume/defaults, reset |
| `mcp_wrongargs.jsonl` / `.out` | 34 calls: wrong-typed args across focus tools |
| `mcp_fuzz.jsonl` / `.out` | 92 calls: broad random invariant fuzz across all tools |
| `mcp_control_chars.jsonl` / `.out` | 5 messages: NUL escape reproducer (finding 2) |
| `mcp_flat_valid.flags`, `mcp_flat_valid.jsonl` / `.out` | 12 valid flat-mode calls |
| `mcp_flat_malformed.flags`, `mcp_flat_malformed.jsonl` / `.out` | 24 flat-mode malformed/unknown calls |
| `FINDINGS.md` | issues with reproducers and verbatim outputs |
| `SUMMARY.md` | this file |

The two `--flat` goldens have a `.flags` file containing `--flat`, matching the
repo's `tests/mcp/NAME.flags` convention.  All 10 `.out` files were generated
with `timeout 30 $ROOT/ucas --mcp [--flat] < NAME.jsonl` from
this directory and verified by a second identical run + `diff` (deterministic).
Findings 1, 3 and 8 are deliberately **not** goldens.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 1 | quadratic slowdown on 100 KB ucas source (~26 s) |
| WRONG | 2 | NUL escape → -32700 + lost id; session/assume silently drops a malformed assumption |
| LIMIT | 3 | id:null rejected; empty source gets source: a string; notification with id → method-not-found |
| DETERMINISM | 2 | c_optimize with timed:true embeds wall-clock seconds; tiny timeout_s races with validation (failed vs timeout, sometimes a duplicate reply) |

### Issues by severity

| Severity | Count | Titles |
|----------|-------|--------|
| CRASH | 0 | — |
| HANG | 1 | quadratic slowdown on 100 KB `ucas` source (~26 s) |
| WRONG | 2 | NUL escape → `-32700` + lost id; `session/assume` silently drops a malformed assumption |
| NLP | 0 | — |
| LIMIT | 3 | `id:null` rejected; empty `source` gets `source: a string`; notification with `id` → method-not-found |
| DETERMINISM | 2 | `c_optimize` with `timed:true` embeds wall-clock seconds; tiny `timeout_s` races with validation (`failed` vs `timeout`, sometimes a duplicate reply) |


## Takeaway
The MCP layer is robust under heavy malformed-input fuzzing — every tool call kept `isError` and `structuredContent` consistent and ambiguity responses were complete — but it mis-handles NUL escapes (wrong code, dropped id), silently accepts a malformed `session/assume`, has two protocol/validation rough edges, a quadratic large-source slowdown, and two timing races (`timed:true` text and a tiny `timeout_s` that can change the error code or duplicate a reply).

### Original takeaway (verbatim)

The MCP layer is robust under heavy malformed-input fuzzing — every tool call
kept `isError` and `structuredContent` consistent and ambiguity responses were
complete — but it mis-handles NUL escapes (wrong code, dropped id), silently
accepts a malformed `session/assume`, has two protocol/validation rough edges,
a quadratic large-source slowdown, and two timing races (`timed:true` text and
a tiny `timeout_s` that can change the error code or duplicate a reply).

### Folder confinement

All files above were created only in
`$ROOT/tests/stress/areas/frontend/mcp_api_fuzz/`.  No source file, Makefile,
existing test, `opencode.json`, or another subagent's folder was touched; no
`make`, `git`, or commit was run; all exploratory scratch files were written to
`/tmp/opencode`.
