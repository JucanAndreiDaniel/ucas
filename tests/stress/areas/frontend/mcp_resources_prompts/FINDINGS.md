# Stress findings — `mcp_resources_prompts`

_Original heading: Findings — `mcp_resources_prompts`_

# Findings — `mcp_resources_prompts`

Scope: the MCP surface **other than tools** — `resources/*`, `prompts/*`,
`completion/complete`, `logging/setLevel`, `notifications/*`, `ping`, and
`tools/list` cursors.  All commands use the built binary
`$ROOT/ucas` and are copy-pasteable.  Goldens live in this
directory.  **All 9 goldens were run twice and diffed: byte-identical, exit 0
under `timeout 15`.**  No crashes or hangs were found on this surface.

The server advertises `capabilities: {"tools":{"listChanged":false},
"resources":{}, "prompts":{}}`.  The advertised methods all work:

| capability | working methods |
|---|---|
| `resources` | `resources/list`, `resources/templates/list`, `resources/read` |
| `prompts` | `prompts/list`, `prompts/get` |
| `tools` | `tools/list`, `tools/call` |

Catalog discovered at runtime: resources `ucas://state` (application/json),
`ucas://help` (text/plain), `ucas://schema` (application/schema+json);
`resourceTemplates: []`; prompts `prove_identity(identity)`,
`cheaper_implementation(f)`, `explore_function(f)`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | legal `\u0000` escape anywhere in a string field yields `-32700 parse error` and loses the… |
| LIMIT | 1 | duplicate JSON object keys are rejected as `-32700 parse error` with `id: null` |

## Findings

### WRONG-1 — legal `\u0000` escape anywhere in a string field yields `-32700 parse error` and loses the request id
**Severity:** WRONG
_Original classification: `WRONG (wrong error code for well-formed JSON + lost correlation id`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `mcp_parse_errors.jsonl`):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_resources_prompts
timeout 15 $ROOT/ucas --mcp < mcp_parse_errors.jsonl
```

**Observed:** output (verbatim, lines 2–7 of the output; ids 1–4 are four different
surfaces, ids 5–6 are the duplicate-key case from finding 2):**
```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
```

**Minimal single-surface reproducer:**
```sh
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":42,"method":"resources/read","params":{"uri":"ucas://state\u0000x"}}' \
'{"jsonrpc":"2.0","id":43,"method":"ping","params":{}}' \
| timeout 15 $ROOT/ucas --mcp
```

**Observed:** the `id: 42` line is answered by
`{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}`
instead of a resource read; `id: 43` then answers `{"result": {}}`, so the
session survives.  The same happens for `\u0000` in a `prompts/get` **name**, in
a `prompts/get` **argument value**, and in a list-method **cursor** (golden
ids 2, 3, 4).  `\u0001`, `\u0041`, `\u007a`, `%00` and a literal trailing space
do **not** trigger it — NUL is the specific byte.

**Why it matters:** it is a bug / expected:** `\u0000` is a legal JSON string escape, so the
message is well-formed JSON-RPC; `-32700 parse error` is the wrong code, and the
reply must echo `id: 42`.  Expected at minimum `-32002 resource not found` (or
`-32602`) with `id: 42`.  This is the same root cause already reported for tool
names/arguments in `mcp_api_fuzz/FINDINGS.md` finding 2, here confirmed across
the resources/prompts/list-cursor surface; the decoded NUL corrupts the
C-string parsing and the generic parse-error path drops the correlation id.

### LIMIT-1 — duplicate JSON object keys are rejected as `-32700 parse error` with `id: null`
**Severity:** LIMIT
_Original classification: `LIMIT (strict parser + lost correlation id`._
**Reproducer:**
Reproducer (golden `mcp_parse_errors.jsonl`, ids 5–6):
```sh
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":9,"method":"ping","params":{},"params":{}}' \
'{"jsonrpc":"2.0","id":10,"method":"resources/read","params":{"uri":"ucas://nope","uri":"ucas://state"}}' \
'{"jsonrpc":"2.0","id":11,"method":"ping","params":{}}' \
| timeout 15 $ROOT/ucas --mcp
```

**Observed:** output (verbatim):
```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": 11, "result": {}}
```

Duplicates at **any** object level are rejected — top-level `id`, `method`,
`params`, or nested inside `params`.  A duplicate `id` loses *both* ids.

**Why it matters:** it is a bug / expected:** RFC 8259 says object names SHOULD be unique but
does not forbid duplicates; most JSON parsers accept them with last-key-wins.
Rejecting well-formed JSON with `-32700` and `id: null` prevents a client from
correlating the error.
**Expected:** accept (last wins) or return a correlated
`-32600 invalid request`.

## Checks that passed

### Checked — no issue found
* **Capability ↔ implementation match.** `completion/complete`,
  `logging/setLevel`, `resources/subscribe`, `resources/unsubscribe` all return
  `-32601 method not found` (golden `mcp_unsupported.jsonl`).  This is
  **consistent** with the advertise capabilities — `logging` and `completions`
  are not advertised and `resources.subscribe` is not enabled — so there is no
  capability/behavior mismatch here.  `resources/list`, `resources/read`,
  `resources/templates/list`, `prompts/list`, `prompts/get` and `tools/list` all
  work exactly as advertised.
* **Resource URIs are exact and case sensitive, with no traversal.** 33 URI
  variants were tried (case changes, trailing slash/space, `?query`, `#frag`,
  `ucas:/state`, `ucas:state`, `file:///etc/passwd`, `http://…`, empty, percent
  escapes).  All unknown URIs return the correct MCP error
  `-32002 {"message":"resource not found"}`; only the three advertised URIs
  succeed.  `resources/read` results have the correct `contents` shape
  (`uri`, `mimeType`, `text`).
* **`prompts/get` shape and validation.** All three prompts return
  `{"description", "messages":[{role:"user", content:{type:"text",text:…}}]}`.
  Unknown/wrong-typed names and missing/wrong-typed arguments return the correct
  `-32602` (`unknown prompt` / `missing the prompt's argument`); extra arguments
  are ignored; an empty-string argument value is accepted.  The prompt text
  interpolates the argument verbatim (expected for a prompt template).
* **Cursors are uniformly ignored, never crash.** For `tools/list`,
  `resources/list`, `resources/templates/list`, `prompts/list`, 19 cursor values
  (empty, numeric strings, huge number, whitespace, 0/1/-1/float/bool/array/
  object) all return the full list with no `nextCursor`.  Non-object `params`
  (`[]`, `"str"`) correctly yields `-32602 params must be an object`.
* **State resource is not stale.** `ucas://state` reflects `session/define`
  (function appears) and `session/reset` (function disappears) correctly —
  golden `mcp_state_resource.jsonl`.
* **Schema resource is large but deterministic.** `resources/read
  ucas://schema` returns 459,099 bytes of stable JSON Schema (golden
  `mcp_resource_schema.jsonl`, two runs byte-identical).
* **Notifications are silent and harmless.** 12 notification methods, malformed
  params, and a 500-notification burst never produce a reply, never desync the
  connection, and the server answers `ping` afterward.  A notification carrying
  an `id` is treated as a request and gets `-32601 method not found: …`
  (consistent with `mcp_api_fuzz` finding 7).
* **id echo and liveness.** String, float, 9223372036854775807, negative and
  empty-string ids are all echoed exactly; every `ping` returns `{}`; the server
  remains alive after every probe (final `ping`, `tools/call`, `resources/read`,
  `prompts/get` all succeed).
* **No crash / hang / nondeterminism** on this surface: all 9 goldens exit 0
  under `timeout 15` and are byte-identical across runs.
