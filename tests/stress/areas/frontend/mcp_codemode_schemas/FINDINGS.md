# Stress findings — `mcp_codemode_schemas`

_Original heading: FINDINGS — `mcp_codemode_schemas`_

# FINDINGS — `mcp_codemode_schemas`

Scope: tool-catalog completeness and schema correctness of the MCP server
(`$ROOT/ucas --mcp`, plus `--flat`), cross-checked against the
README (`README.md` § "MCP server"), the skill (`.claude/skills/ucas/SKILL.md`),
the authoritative `session` → `schema` op, and the JSON frontend (`--json`).

All goldens in this folder were run at least twice and were byte-identical; the
`--mcp` MCP namespace was not used for goldens (the wire server is the ground
truth), so nothing here depends on a transient Code Mode catalog.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 3 | 1 — Grouped tools declare `additionalProperties:false` but silently drop unknown top-level… |

## Findings

### LIMIT-1 — 1 — Grouped tools declare `additionalProperties:false` but silently drop unknown top-level arguments
**Severity:** LIMIT
_Original classification: `LIMIT (schema-enforcement mismatch, not a crash`._
**Expected:** _not recorded_
All 27 tool `inputSchema`s set `additionalProperties: false`. For the 9
**standalone** tools an unknown top-level argument is rejected by the frontend
with `bad_request "TOOL has no argument KEY"`. For the 18 **grouped** tools the
wrapper reads only `op` and `args` and silently ignores any other top-level key,
so the declared schema is not enforced and a mistyped key can go unnoticed.
(An unknown key *inside* `args` is correctly rejected by the frontend for both
kinds — the boundary is inconsistent.)

**Reproducer:**
Reproducer (golden `mcp_tools_extra.jsonl`; ids 2 and 19 shown):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_codemode_schemas
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"calculus","arguments":{"op":"diff","args":{"f":"x^2","var":"x"},"__extra_top_key":123}}}' \
 '{"jsonrpc":"2.0","id":19,"method":"tools/call","params":{"name":"ucas","arguments":{"source":"x=1","__extra_top_key":123}}}' \
 | timeout 15 $ROOT/ucas --mcp
```
**Observed:**
```json
{"jsonrpc": "2.0", "id": 2, "result": {"content": [ ... ], "structuredContent": {"id": 2, "ok": true, "cmd": "diff", ... }, "isError": false}}
{"jsonrpc": "2.0", "id": 19, "result": {"content": [ ... ], "structuredContent": {"id": 19, "ok": false, "cmd": "ucas", "error": {"code": "bad_request", "message": "ucas has no argument \"__extra_top_key\""}}, "isError": true}}
```
**Why it matters:** it is a bug / expected: with `additionalProperties:false` the grouped-tool
call carrying `__extra_top_key` should be rejected (or at minimum the same
`bad_request ... has no argument "__extra_top_key"` returned), as it is for the
standalone `ucas` tool. Silently accepting it hides client bugs.

### LIMIT-2 — 2 — Skill advertises a non-existent `x86` op `models`; real op is `x86_models`
**Severity:** LIMIT
_Original classification: `LIMIT (documentation/schema vocabulary mismatch`._
`.claude/skills/ucas/SKILL.md` line 28 documents the `x86` group as
`x86 (mca, models, intrinsics)`. The actual `x86` op enum is
`x86_models x86_model mca intrinsic intrinsics x86check` — there is no `models`
op. A client following the skill gets a bare tool-level error.

**Reproducer:**
Reproducer (golden `mcp_vocab_docs.jsonl`, ids 3 and 4):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_codemode_schemas
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"x86","arguments":{"op":"models","args":{}}}}' \
 '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"x86","arguments":{"op":"x86_models","args":{}}}}' \
 | timeout 15 $ROOT/ucas --mcp
```
**Observed:**
```json
{"jsonrpc": "2.0", "id": 3, "error": {"code": -32602, "message": "x86 needs \"op\", one of: x86_models x86_model mca intrinsic intrinsics x86check"}}
{"jsonrpc": "2.0", "id": 4, "result": { ..., "structuredContent": {"id": 4, "ok": true, "cmd": "x86_models", ...}, "isError": false}}
```
**Why it matters:** it is a bug / expected: the skill is the agent-facing quick reference; an
op it lists must be callable.
**Expected:** either name the op `x86_models`, or add
a `models` alias.

### LIMIT-3 — 3 — README's MCP tool/op table is stale (missing tools; `texalu`/`texenc` mis-grouped)
**Severity:** LIMIT
_Original classification: `LIMIT (documentation/schema vocabulary mismatch`._
**Why it matters:** _not recorded_
`README.md` § "MCP server" table lists 15 grouped tools + `ucas`/`english`/
`spirv_simplify`. The server advertises 27 tools. The README omits the grouped
tools `x86`, `elliptic_ff`, `proofs` and the standalone tools `texalu`, `texenc`,
`lperm`, `tcdot`, `winograd`, `ozaki`. It also lists `texalu` and `texenc` as
`analyze` ops, but in the live catalog they are standalone tools:
`analyze` with `op:"texalu"` or `op:"texenc"` is `-32602`, while the standalone
`texalu`/`texenc` tools are callable.

**Reproducer:**
Reproducer (golden `mcp_vocab_docs.jsonl`, ids 1, 2, 7, 8):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_codemode_schemas
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"texalu","args":{}}}}' \
 '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"texalu","arguments":{}}}' \
 | timeout 15 $ROOT/ucas --mcp
```
**Observed:**
```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "analyze needs \"op\", one of: show table parse range domain wrap crit equiv ..."}}
{"jsonrpc": "2.0", "id": 7, "result": { ..., "structuredContent": {"id": 7, "ok": false, "cmd": "texalu", "error": {"code": "bad_request", "message": "texalu needs \"f\" ..."}}, "isError": true}}
```
**Expected:** README's table and op lists should match the live `tools/list` (the
`session schema` resource is the authoritative source and does match).

## Checks that passed

### Headline (non-issues, verified)
- **`tools/list` returns 27 grouped/standalone tools** (134 KB), no `nextCursor`.
  `tools/list` ignores bogus `cursor` (string or int) and unknown params; a
  non-object `params` is `-32602 "params must be an object"`.
  Golden: `mcp_catalog.jsonl` / `.out`.
- **Catalog is internally complete.** The 18 grouped tools advertise 239 unique
  `op` enum values; the 9 standalone tools (`ucas`, `english`, `texalu`,
  `texenc`, `spirv_simplify`, `lperm`, `tcdot`, `winograd`, `ozaki`) supply the
  other 9 commands: 239 + 9 = 248, exactly the 248 commands in `session schema`.
  Every enum op is documented in its tool description, every description token
  is in the enum, all 27 `outputSchema`s are byte-identical, and each standalone
  tool's `inputSchema.required` matches its frontend required params.
- **Nothing advertised is uncallable.** All 239 group ops were called with empty
  args (`mcp_all_ops.jsonl`, 239 calls) and again with type-appropriate required
  args; in both sweeps every one returned a normal JSON-RPC reply (0 bare
  `-32602 "needs op"` errors, 0 missing replies, exit 0 under `timeout 90`).
- **`structuredContent` equals the JSON frontend response** exactly (all fields,
  all 11 cross-layer pairs tried: analyze/calculus/algebra/rings/
  abstract_algebra/session/proofs/tcdot/english/ucas/x86). `isError` == not `ok`,
  `structuredContent.id` echoes the request id, `error.code` is in the 12-code
  enum, `proof.kind` and `notes[].kind` are in their enums — checked across all
  ~400 replies in this folder. No envelope violation, crash, hang, or
  nondeterminism was found.
- **`--flat` mode** lists exactly the same 248 commands as one tool each, with
  no `outputSchema` (as documented); tool name == op, arguments are the op's
  args directly (not wrapped as `{op,args}`). Golden: `mcp_flat_catalog.*`,
  `mcp_flat_calls.*`. No hyphenated tool name exists; any tool name containing
  `-` is `-32602 unknown tool`. Protocol 2024-11-05 / 2025-03-26 omit
  `outputSchema`, 2025-06-18 includes it — correct.
