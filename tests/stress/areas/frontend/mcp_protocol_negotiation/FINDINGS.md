# Stress findings — `mcp_protocol_negotiation`

_Original heading: Findings — `mcp_protocol_negotiation`_

# Findings — `mcp_protocol_negotiation`

Area: MCP handshake (`initialize` / `notifications/initialized`) and JSON-RPC 2.0 framing
on `ucas --mcp`.  All commands use the built binary `$ROOT/ucas` and are
copy-pasteable.  Goldens in this directory were each run **twice** under `timeout 15` and
byte-diffed; all 22 are deterministic.  No crash, hang, malformed reply or unsound answer
was found.  The issues below are protocol-conformance **LIMIT**s.

Protocol facts used (from the official MCP schemas/changelogs):
- the server advertises exactly three supported `protocolVersion`s: `2024-11-05`,
  `2025-03-26`, `2025-06-18`; anything else is downgraded to `2025-06-18`;
- JSON-RPC **batching was added in 2025-03-26 and removed in 2025-06-18**;
- **structured tool output** (`outputSchema` / `structuredContent`) and the `title` field
  on `Tool` / `Implementation` were **added in 2025-06-18**;
- 2025-06-18 changed the lifecycle operation from SHOULD to **MUST**.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 4 | MCP lifecycle is not enforced at all |

## Findings

### LIMIT-1 — MCP lifecycle is not enforced at all
**Severity:** LIMIT
_Original classification: `LIMIT (spec deviation; the 2025-06-18 lifecycle is a MUST`._
**Expected:** _not recorded_
`tools/call`, `ping`, `tools/list`, … are answered with **no `initialize` and no
`notifications/initialized` at all**.  A duplicate `initialize` mid-stream is also accepted
and answered, and re-initialising does not reset session state (state *is* predictable —
it simply persists).  The implementation treats `initialize` as an ordinary request whose
reply is computed on demand; it never records a "handshake complete" state.

**Reproducer:**
Reproducer (no handshake):
**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_protocol_negotiation
timeout 15 $ROOT/ucas --mcp < mcp_no_handshake.jsonl
```
Input line 1 is a bare `tools/call` (ids 1, 2, 3).  **Observed:**
```json
{"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "2^10 = 1024\n  bits: 11\n ..."}]}}
{"jsonrpc": "2.0", "id": 2, "result": {}}
{"jsonrpc": "2.0", "id": 3, "result": {}}
```
`mcp_notif_only.jsonl` (only `notifications/initialized`) and `mcp_duplicate_init.jsonl`
(three `initialize` calls, definitions survive them) show the same absence of gating.

**Why it matters:** it is a bug / expected:** per the MCP lifecycle a client **MUST** send `initialize`
and `notifications/initialized` before any other request; a strict server should reject
pre-handshake requests (e.g. `-32600` / "server not initialized").  Accepting them hides
client bugs and makes the negotiated version meaningless for the very first call.

### LIMIT-2 — `2025-03-26` is advertised but its batch support is not implemented
**Severity:** LIMIT
_Original classification: `LIMIT (feature of a negotiated, advertised version silently missing`._
**Expected:** _not recorded_
The server echoes `2025-03-26` when a client requests it, but rejects **every** JSON-RPC
batch array with the same `-32600 batches are not supported` it uses under `2025-06-18`
(where rejecting batches is correct, because 2025-06-18 removed them).  `2024-11-05` and
`2025-11-25` behave identically.  Version negotiation here only chooses the reply string
and the reply *shape*; it does not change transport features.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_protocol_negotiation
timeout 15 $ROOT/ucas --mcp < mcp_batch_by_version.jsonl
```
**Observed:** (12 reply lines; abridged):
```json
{"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": "2024-11-05", ...}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "batches are not supported"}}
{"jsonrpc": "2.0", "id": 100, "result": {}}
{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", ...}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "batches are not supported"}}
{"jsonrpc": "2.0", "id": 101, "result": {}}
...
```
**Why it matters:** it is a bug / expected:** 2025-03-26 explicitly *added* batching; a server that
advertises it must accept a batch (or must downgrade to a version that does not advertise
it).  As written, a compliant 2025-03-26 client immediately gets `-32600`.

### LIMIT-3 — 2025-06-18-only fields are emitted under older negotiated versions
**Severity:** LIMIT
_Original classification: `LIMIT (schema conformance; harmless extra fields`._
When the client negotiates `2024-11-05` or `2025-03-26`, the replies still contain fields
that those schemas do not define:
- `serverInfo.title` (added with `BaseMetadata` in 2025-06-18) in every `initialize` reply;
- `tools[].title` in every `tools/list` reply;
- the 2025-06-18 `outputSchema` is correctly *omitted* for old versions, and
  `structuredContent` is correctly *omitted* for old versions (so the shaping logic is
  partly version-aware — the `title` field was simply missed).

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_protocol_negotiation
timeout 15 $ROOT/ucas --mcp < mcp_version_shaping.jsonl
```
**Observed:** (abridged):
```json
{"jsonrpc":"2.0","id":0,"result":{"protocolVersion":"2024-11-05",
 "capabilities":{...},"serverInfo":{"name":"ucas","title":"ucas, a computer algebra system for programmers","version":"1"},...}}
{"jsonrpc":"2.0","id":10,"result":{"content":[...],"isError":false}}   <- no structuredContent (correct)
...
{"jsonrpc":"2.0","id":2,"result":{"protocolVersion":"2025-06-18","serverInfo":{"name":"ucas","title":...}}}
{"jsonrpc":"2.0","id":12,"result":{"content":[...],"structuredContent":{...},"isError":false}}
```
**Why it matters:** it is a bug / expected:** a strict client that validates replies against the
negotiated version's schema will reject the older-version replies because of the unknown
`title` field.
**Expected:** gate `title` on `protocolVersion == 2025-06-18`, as is already
done for `structuredContent` / `outputSchema`.

### LIMIT-4 — a notification method carrying an `id` answers `-32601 method not found`
**Severity:** LIMIT
_Original classification: `LIMIT (confusing protocol error; also recorded in mcp_api_fuzz finding 7`._
**Why it matters:** _not recorded_
In this area this was exercised for the handshake-specific notifications.  Adding an `id`
turns them into requests, but they are only registered as notifications, so the server
answers `-32601` instead of a clearer "notifications cannot have an id" (`-32600`).

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_protocol_negotiation
timeout 15 $ROOT/ucas --mcp < mcp_notif_with_id.jsonl
```
**Observed:**
```json
{"jsonrpc": "2.0", "id": 10, "error": {"code": -32601, "message": "method not found: notifications/initialized"}}
{"jsonrpc": "2.0", "id": 11, "error": {"code": -32601, "message": "method not found: notifications/cancelled"}}
{"jsonrpc": "2.0", "id": 12, "error": {"code": -32601, "message": "method not found: notifications/progress"}}
{"jsonrpc": "2.0", "id": 13, "error": {"code": -32601, "message": "method not found: notifications/message"}}
```
Ids are echoed correctly and the session stays usable (the trailing `ping` id 14 replies
`{}`).
**Expected:** `-32600 invalid request` with a message explaining that notifications
must not carry an id.

## Checks that passed

### Checked — no issue found
* **Negotiation itself:** `2024-11-05`, `2025-03-26`, `2025-06-18` are echoed verbatim;
  `2025-11-25`, `2026-01-01`, `1999-01-01`, `""`, `bogus`, `latest`, `"2025-6-18"`,
  whitespace-padded, unicode and every non-string type (123, 1.5, true, null, [], {}) all
  fall back deterministically to `2025-06-18`.  See `mcp_versions_supported`,
  `mcp_versions_fallback`, `mcp_versions_nonnumeric`.  Repeated / re-ordered `initialize`
  calls each echo their own negotiated version.
* **Params leniency:** missing `capabilities`, missing `clientInfo`, missing
  `protocolVersion`, `null` / array / string values for those fields, extra `_meta`,
  unknown capabilities and deep `clientInfo` objects are all accepted without a crash.
  A `params` that is present but not an object gives `-32602 params must be an object`
  while a missing `params` is accepted.  See `mcp_params_variants`, `mcp_params_bad`.
* **Errors well-formed / ids echoed:** every reply has `jsonrpc:"2.0"`, exactly one of
  `result` / `error`, integer `code` and string `message`.  `-32700 parse error` and
  `-32600` for invalid id types carry `id: null` (no trustworthy id to echo); every other
  error echoes string, float, negative and >2^53 ids verbatim.  See `mcp_error_shapes`,
  `mcp_huge_ids`, `mcp_invalid_ids`, `mcp_duplicate_keys`.
* **JSON-RPC framing:** duplicate JSON object keys, trailing data, unclosed strings, BOM,
  `NaN` / `Infinity`, single-quoted JSON and 500-deep arrays all produce a single
  `-32700 parse error` (id null) and the server keeps serving the next line.  Empty /
  whitespace-only lines are silently skipped.  Requests without ids produce no reply.
  See `mcp_invalid_json`, `mcp_duplicate_keys`, `mcp_requests_no_id`.
* **Session state predictable:** definitions persist across re-initialize and across a
  failed / invalid `initialize`; a parse or protocol error never mutates state.
  See `mcp_duplicate_init`.
* **Robustness / performance:** 800 mutated `initialize` messages, 1 MB `protocolVersion`,
  100 KB ids, 100 KB method names and 2000 consecutive `initialize` calls all completed
  in well under 1 s with exit code 0 and well-formed replies; no crash, signal, hang or
  truncated output was observed.  (These bulk runs were exploratory and are deliberately
  *not* kept as goldens to keep the suite small.)
