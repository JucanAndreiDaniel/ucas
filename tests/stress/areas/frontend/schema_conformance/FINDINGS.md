# Stress findings — `schema_conformance`

_Original heading: schema_conformance — findings_

# schema_conformance — findings

Scope: reply-*shape* correctness of the ucas JSON Lines (`--json --files none`)
and MCP stdio (`--mcp`, plus `--flat`) frontends.  A reusable checker lives in
`schema_check.py`; all goldens in this folder are fed through it with
`python3 schema_check.py --all`.

**Headline: across 386 golden replies (and ~730 during exploration) spanning all
27 tool families and every documented envelope field, no schema violation was
found.**  Specifically, every reply had correct field types, no undocumented
fields, `ok`/`error` and `structured`/`result` consistent, `isError` set exactly
when `error` was present (MCP), `structuredContent.id` echoed for string /
float / negative / >2^53 ids, `proof.kind` ∈ {symbolic, exhaustive, sat,
numeric, search}, `error.code` ∈ the documented 12-code set, and `notes[].kind`
∈ {rule, info, assumed, default}.  All goldens were byte-identical when run
twice (no nondeterministic field ordering).

Below are the only deviations observed; both are cross-layer/protocol limits,
not envelope bugs.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 2 | 1 — MCP rejects JSON-RPC ids that JSON mode echoes |

## Findings

### LIMIT-1 — 1 — MCP rejects JSON-RPC ids that JSON mode echoes
**Severity:** LIMIT
**Why it matters:** _not recorded_
JSON mode echoes **any** `id` verbatim, including `null`, floats, booleans,
arrays and objects.  The MCP frontend rejects `null`, `true`, arrays and objects
at the JSON-RPC layer with `-32600 invalid request` (the reply's `id` is forced
to `null`), so those ids never reach an envelope / `structuredContent`.
String, float, negative and very large integer ids do reach it and are echoed
correctly in both `result.id` (JSON-RPC) and `structuredContent.id`.

**Reproducer:**
Reproducer (MCP, `null` id):
```sh
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":null,"method":"tools/call","params":{"name":"abstract_algebra","arguments":{"op":"bigint","args":{"expr":"2^4"}}}}' \
 | timeout 15 $ROOT/ucas --mcp
```
**Observed:** (last line):
```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "invalid request"}}
```
The same `null` id in JSON mode *is* accepted and echoed:
```sh
printf '%s\n' '{"id":null,"cmd":"bigint","args":{"expr":"2^4"}}' \
 | timeout 15 $ROOT/ucas --json --files none
# {"id": null, "ok": true, "cmd": "bigint", ... }
```
**Expected:** /why: JSON-RPC 2.0 permits a null id; a stricter MCP gate is defensible,
but the asymmetry means a client cannot rely on `id` round-tripping uniformly
across the two frontends.  Documented here rather than as a golden because it is
intentional protocol gating, not a malformed reply.

The same rejection happens for `id: true`, `id: [1,2]`, `id: {"a":1}` (all
invalid JSON-RPC id types).  See `json_ids.jsonl` / `mcp_ids.jsonl` goldens.

### LIMIT-2 — 2 — Invalid op is rejected before an envelope exists (cross-layer shape differs)
**Severity:** LIMIT
**Expected:** _not recorded_
For an `op`-based tool, an op outside the tool's enum produces different reply
shapes in the two frontends.  MCP validates `op` against the tool's JSON-Schema
enum and returns a bare JSON-RPC error with **no** `structuredContent` /
`isError`; JSON mode returns a normal envelope with `error.code =
"unknown_command"`.

**Reproducer:**
**Observed:**
```sh
# MCP
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"algebra","arguments":{"op":"nope","args":{}}}}' \
 | timeout 15 $ROOT/ucas --mcp
# {"jsonrpc":"2.0","id":5,"error":{"code":-32602,"message":"algebra needs \"op\", one of: expand factor ..."}}

# JSON
printf '%s\n' '{"id":5,"cmd":"nope","args":{}}' \
 | timeout 15 $ROOT/ucas --json --files none
# {"id":5,"ok":false,"cmd":"nope","error":{"code":"unknown_command","message":"unknown command \"nope\" ..."}}
```
**Why it matters:** the "JSON envelope == MCP `structuredContent`" invariant that
holds for every valid command (verified across 164 paired requests in
`_scratch/gen.py`'s `xlayer` corpus) does **not** hold for invalid ops, because
the MCP side has no envelope at all.  This is schema validation happening at the
transport layer, not a wrong-typed field.

## Checks that passed

### Non-issues investigated (kept as goldens, not bugs)
* `structured:false` with a `result` present — e.g. `parse`, `funcs`, `models`,
  `help`, `ucas`.  The schema doc states "unstructured commands give `{text}`",
  and that is exactly what these return (`result == {"text": ...}`).  Conformant.
* MCP `content[]` containing an `image` block (`type/data/mimeType`) for `plot` /
  `plot3d` — a standard MCP content type, not a malformed text block.  Conformant.
* File-producing commands diff between `--files none` (JSON goldens) and MCP
  default file writes (base64 image attached, `files[]` populated).  This is the
  documented `files` option, not nondeterminism.
* `ok:false` together with a partial `result` (e.g. ambiguous / `not_understood`
  English replies) — allowed; only `ok:true` + `error` would be a violation, and
  none was observed.

No `CRASH`, `HANG`, `WRONG`, `NLP` or `DETERMINISM` issue was found in this area.
