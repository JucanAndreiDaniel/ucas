# SUMMARY — `mcp_protocol_negotiation`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 22
- Files created: not recorded

### Scope.
MCP handshake and JSON-RPC 2.0 framing on `ucas --mcp`: protocol-version
negotiation, `initialize` params, lifecycle ordering, notifications-with-ids, id-less
requests, batches, unknown methods, invalid JSON, trailing data and huge/unusual ids.

### Counts

| metric | count |
|---|---|
| distinct cases (JSON-RPC message lines across all `.jsonl` inputs) | **256** |
| exploratory cases (extra ad-hoc mutations, bulk runs, not kept as goldens) | ~2800 |
| MCP golden pairs (`.jsonl` + `.out`) | **22** |
| other files (`FINDINGS.md`, `SUMMARY.md`) | 2 |
| goldens verified byte-identical on two runs under `timeout 15` | 22 / 22 |
| issues by severity | `CRASH` 0 · `HANG` 0 · `WRONG` 0 · `NLP` 0 · `LIMIT` 4 · `DETERMINISM` 0 |

Distinct-case coverage includes 29 `protocolVersion` values (the 3 supported ones, newer /
older / bogus versions, empty and whitespace variants, unicode, and 11 non-string types),
11 `capabilities` / `clientInfo` shapes, 4 bad `params` envelopes, 7 `jsonrpc`-field
variants, 6 lifecycle orderings, 4 notification-with-id methods, 3 id-less request types,
6 batch arrays, 8 unknown/wrong-typed methods, 12 malformed-JSON lines, 5 duplicate-key
lines, 15 huge/unusual ids and 6 invalid id types.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 4 | — |

### Issues found

All four are protocol-conformance limits, not crashes or unsound CAS answers:

1. **LIMIT** — no MCP lifecycle enforcement: tools/call & ping work with no
   `initialize` / `notifications/initialized`; duplicate `initialize` is accepted and
   state persists. (`mcp_no_handshake`, `mcp_notif_only`, `mcp_duplicate_init`)
2. **LIMIT** — `2025-03-26` is advertised but its JSON-RPC batching is not implemented;
   batches get `-32600` under every negotiated version. (`mcp_batch_by_version`)
3. **LIMIT** — 2025-06-18-only `title` fields are emitted under `2024-11-05` /
   `2025-03-26`, although `structuredContent` / `outputSchema` are correctly gated.
   (`mcp_version_shaping`)
4. **LIMIT** — a notification method carrying an `id` answers `-32601 method not found`
   instead of a clearer `-32600`. (`mcp_notif_with_id`)


## Takeaway
The handshake is robust and deterministic — negotiation, error codes, id echoing and state are predictable, with no hangs or crashes across 256 framed cases and ~2800 exploratory mutations — but it is largely **cosmetic**: the server echoes a negotiated version and gates structured output correctly, yet does not enforce the lifecycle or implement every feature of the older versions it advertises.

### Original takeaway (verbatim)

The handshake is robust and deterministic — negotiation, error codes, id echoing and state
are predictable, with no hangs or crashes across 256 framed cases and ~2800 exploratory
mutations — but it is largely **cosmetic**: the server echoes a negotiated version and
gates structured output correctly, yet does not enforce the lifecycle or implement every
feature of the older versions it advertises.

### Confinement:
all files created live only in
`$ROOT/tests/stress/areas/frontend/mcp_protocol_negotiation/`.
