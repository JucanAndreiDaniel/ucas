# Stress findings — `mcp_api_fuzz`

_Original heading: Findings — `mcp_api_fuzz`_

# Findings — `mcp_api_fuzz`

All commands below use the built binary `$ROOT/ucas` and are
copy-pasteable.  Golden files live in this directory.  Every golden was run at
least twice and the outputs diffed before it was kept (all 10 goldens are now
deterministic — one initially flaked and was fixed as described in finding 8);
nondeterministic and timeout cases are documented here instead.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | quadratic blowup on a large `ucas` source |
| WRONG | 2 | escaped NUL in a string is rejected as `-32700 parse error` and loses the request id |
| LIMIT | 3 | `id: null` is rejected as an invalid request |
| DETERMINISM | 2 | `c_optimize` with `timed: true` embeds wall-clock seconds |

## Findings

### HANG-1 — quadratic blowup on a large `ucas` source
**Severity:** HANG
infinite loop).

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_api_fuzz
python3 -c 'import json
print(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}))
print(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}))
print(json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":"x"*100000}}}))' > /tmp/ucas_big.jsonl
time timeout 30 $ROOT/ucas --mcp < /tmp/ucas_big.jsonl > /tmp/ucas_big.out
```

**Observed:** (wall clock):
```
 25 KB -> 1.65 s     30 KB -> 2.38 s     40 KB -> 4.50 s
 50 KB -> 5.87 s    100 KB -> 25.6 s (timeout 6 s kills the 50 KB case)
```
No output for the tool call until it completes; under the suite's 15 s bound a
100 KB source is indistinguishable from a hang.  Exit code is 0 when allowed to
finish; the cost grows ~O(n^2).  **Not kept as a golden.**

**Why it matters:** it is a bug / expected:** a fuzz-style client can send a large source; a
100 KB request tying up the single-threaded MCP server for ~26 s is a DoS-level
limit.
**Expected:** linear handling or a bounded parse.

### WRONG-1 — escaped NUL in a string is rejected as `-32700 parse error` and loses the request id
**Severity:** WRONG
_Original classification: `WRONG (protocol error code + lost correlation id`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `mcp_control_chars.jsonl`):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_api_fuzz
timeout 15 $ROOT/ucas --mcp < mcp_control_chars.jsonl
```

**Observed:** output (verbatim, ids 7 and 8 were the two tool calls):
```json
{"jsonrpc": "2.0", "id": 0, "result": { ...initialize result... }}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
{"jsonrpc": "2.0", "id": 9, "result": {}}
```
Line 3 of the input is a valid JSON-RPC message whose `params.name` is
`"ana\u0000lyze"`; line 4 has an argument value `"x\u0000+1"`.  Both are legal
JSON escapes.  A control test with `\u0001`, `\u0041`, `\u007a` in the same
position is accepted and answered as `-32602 unknown tool "..."`, so NUL is the
specific trigger (C strings are NUL-terminated, the decoded byte truncates the
value and corrupts the message).

**Why it matters:** it is a bug / expected:** the JSON is well-formed, so `-32700 parse error`
is the wrong code; and the reply's `id` is `null` instead of the request's `id`
(7 / 8), so a client cannot correlate the error.  Expected at minimum
`-32602 unknown tool "ana\u0000lyze"` with `id: 7` echoed.

### DETERMINISM-1 — `c_optimize` with `timed: true` embeds wall-clock seconds
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (do not make a golden`._
**Expected:** _not recorded_
**Reproducer:**
```sh
python3 -c 'import json
print(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}))
print(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}))
print(json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_optimize","args":{"code":"int f(int x){return x*3+1;}","nofile":true,"timed":true}}}}))' > /tmp/timed.jsonl
$ROOT/ucas --mcp < /tmp/timed.jsonl > /tmp/t1.out
$ROOT/ucas --mcp < /tmp/timed.jsonl > /tmp/t2.out
diff /tmp/t1.out /tmp/t2.out
```

**Observed:** the `content[0].text` and `structuredContent.text` contain
`"... for x86-64-v3 in 0.8 s"` on one run and `... in 0.7 s` on another.
`diff` reports the timing difference.

**Why it matters:** it is a bug / expected:** two identical requests produce different
output, so such a call cannot be used as a golden.  Documented, not kept as a
`.out`.  (All 10 goldens that *were* kept were checked twice and are stable;
seed-dependent `stoke`, `pit`, `phash`, `mma`, `adamfit`, `ecdsa_sign` and
`integrate` with an explicit seed were also checked and are deterministic.)

### WRONG-2 — `session/assume` silently accepts a wrong-typed `name` and drops the assumption
**Severity:** WRONG
_Original classification: `WRONG (malformed argument accepted, bogus success`._
**Reproducer:**
Reproducer (golden `mcp_wrongargs.jsonl`, id 20):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_api_fuzz
python3 -c 'import json
print(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}))
print(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}))
print(json.dumps({"jsonrpc":"2.0","id":20,"method":"tools/call","params":{"name":"session","arguments":{"op":"assume","name":[],"value":1}}}))' \
 | $ROOT/ucas --mcp
```

**Observed:** output (verbatim):
```json
{"jsonrpc": "2.0", "id": 20, "result": {"content": [{"type": "text", "text": "{\"kind\": \"assume\", \"assumptions\": {}}"}], "structuredContent": {"id": 20, "ok": true, "cmd": "assume", "structured": true, "result": {"kind": "assume", "assumptions": {}}, "notes": [], "conditions": [], "checks": [], "files": [], "text": ""}, "isError": false}}
```
`name` is an array and `value` is a bare number, yet the call reports
`ok: true`, `assumptions: {}`, `isError: false` — the malformed assumption is
silently discarded.  Every other op tested with a wrong-typed required arg
returned `bad_request`.

**Why it matters:** it is a bug / expected:** accepting a malformed argument and reporting
success lets a client believe an assumption was installed when it was not.
**Expected:** `bad_request` (as `define` with `name: []` already returns).

### LIMIT-1 — `id: null` is rejected as an invalid request
**Severity:** LIMIT
_Original classification: `LIMIT (JSON-RPC 2.0 deviation`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `mcp_protocol.jsonl`, input line 8):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_api_fuzz
printf '%s\n' '{"jsonrpc":"2.0","id":null,"method":"ping","params":{}}' \
 | $ROOT/ucas --mcp | grep '"code"'
```
(When run standalone the server may require the initialize handshake first;
in the golden the handshake precedes it.)

**Observed:** output (verbatim):
```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "invalid request"}}
```

**Why it matters:** it is a bug / expected:** JSON-RPC 2.0 says `id` "MUST contain a String,
Number, or NULL value if included" (only SHOULD NOT be Null); a message with
`id: null` is a request, not a notification, and `ping` should answer
`{"jsonrpc":"2.0","id":null,"result":{}}`.  Note the server already echoes
`id: null` for parse errors, so it is not treating null as "no id" everywhere.

### LIMIT-2 — empty `source` gets the misleading error `source: a string`
**Severity:** LIMIT
_Original classification: `LIMIT (wrong/misleading validation message; inconsistency`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `mcp_grouped_args.jsonl`, id 81):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_api_fuzz
python3 -c 'import json
print(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}))
print(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}))
print(json.dumps({"jsonrpc":"2.0","id":81,"method":"tools/call","params":{"name":"ucas","arguments":{"source":""}}}))' \
 | $ROOT/ucas --mcp | tail -1
```

**Observed:** output (verbatim):
```json
{"jsonrpc": "2.0", "id": 81, "result": {"content": [{"type": "text", "text": "error (bad_request): source: a string"}], "structuredContent": {"id": 81, "ok": false, "cmd": "ucas", "error": {"code": "bad_request", "message": "source: a string"}}, "isError": true}}
```
The sibling tool `english` with `text: ""` correctly answers
`error (bad_request): text is empty` (id 76 of the same golden).  An empty
string *is* a string, so `source: a string` does not explain the rejection.

**Why it matters:** it is a bug / expected:** use the same `source is empty` message, or
accept empty source.  Error code and `isError` are otherwise correct.

### LIMIT-3 — a notification carrying an `id` answers `-32601 method not found`
**Severity:** LIMIT
_Original classification: `LIMIT (confusing protocol error`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `mcp_protocol2.jsonl`, id 8):
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_api_fuzz
python3 -c 'import json
print(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}))
print(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}))
print(json.dumps({"jsonrpc":"2.0","id":8,"method":"notifications/initialized"}))' \
 | $ROOT/ucas --mcp | tail -1
```

**Observed:** output (verbatim):
```json
{"jsonrpc": "2.0", "id": 8, "error": {"code": -32601, "message": "method not found: notifications/initialized"}}
```

**Why it matters:** it is a bug / expected:** an `id` turns the message into a request, but
`notifications/initialized` is only registered as a notification.  A clearer
answer would be `-32600 invalid request` ("notifications cannot have an id"),
as JSON-RPC clients sometimes include one by mistake.

### DETERMINISM-2 — a tiny `timeout_s` races with validation (`failed` vs `timeout`, occasionally two replies)
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (plus a hint of WRONG: duplicate responses`._
**Expected:** _not recorded_
**Reproducer:**
```sh
python3 -c 'import json
print(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}))
print(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}))
print(json.dumps({"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"stoke","args":{"f":"x+1","steps":100000,"timeout_s":0.001}}}}))' > /tmp/race.jsonl
for k in 1 2 3 4 5; do $ROOT/ucas --mcp < /tmp/race.jsonl | tail -1; done
```

**Observed:** the single request with `id: 7` answers either of two different
errors, apparently at random (16/20 runs `failed`, 4/20 `timeout`):
```json
{"jsonrpc":"2.0","id":7,"result":{"content":[{"type":"text","text":"error (failed): stoke: an integer function on machine types (uN, iN)\n..."}],"structuredContent":{"id":7,"ok":false,"cmd":"stoke","error":{"code":"failed","message":"stoke: an integer function on machine types (uN, iN)",...}},"isError":true}}
{"jsonrpc":"2.0","id":7,"result":{"content":[{"type":"text","text":"error (timeout): timed out after 0.001 s; the state is unchanged"}],"structuredContent":{"id":7,"ok":false,"cmd":"stoke","error":{"code":"timeout","message":"timed out after 0.001 s; the state is unchanged"}},"isError":true}}
```
In one observed run the server emitted **both** replies to the same `id: 7`
(`{"...ids": [0,1,...,7,7,8,...]}` — 13 output lines for 12 expected), so a
client can receive a duplicate response.

**Why it matters:** it is a bug / expected:** the command's domain check and the 1 ms
wall-clock timer are in a race; identical requests must not produce different
error codes, and one request must never produce two responses.  This is why the
`timeout_s: 0.001` argument was removed from `mcp_state.jsonl` (with it, the
golden failed a re-run `diff`); the golden now uses the same call without
`timeout_s`, which deterministically returns `failed`.

## Checks that passed

### Checked, no issue found
* **isError / structuredContent invariant:** across all 289 tool calls in the
  goldens, the 192 that produced a JSON-RPC `result` all have a boolean
  `isError` and a `structuredContent`; the 94 answered with protocol-level
  `-32602` errors (and 3 id-less notification-style tool calls that are not
  answered) do so by design.  Every application error has `isError: true` plus a
  `structuredContent.error.code` from the README set (`bad_json`,
  `bad_request`, `unknown_command`, `parse_error`, `domain_error`,
  `unsupported`, `failed`, `ambiguous`, `needs_input`, `not_understood`,
  `timeout`, `internal`).  Ambiguous errors carry `error.key`, `error.readings`
  and the `args.assume.KEY` hint (see `mcp_ambiguous.jsonl`).
  Protocol-level errors (bad tool name/op/argument shape) correctly use
  JSON-RPC errors (`-32600`/`-32601`/`-32602`/`-32700`) with no
  `structuredContent` — this matches the README, so it is not a bug.
* **State leaking:** definitions persist within a JSONL session; a failed call
  and an `ambiguous` error do not create partial definitions; explicit
  `args.assume` and `args.defaults` do **not** leak into later calls;
  `session/reset` clears definitions.  See `mcp_state.jsonl`.
* **Grouped vs flat:** grouped tools validate `op` through JSON-RPC `-32602`;
  flat mode exposes 248 op-tools and correctly returns `-32602 unknown tool`
  for grouped names (`analyze`, `calculus`, `properties`, `c`,
  `abstract_algebra`) and `bad_request ... has no argument "op"` for flat
  op-names that collide with grouped tool names (`algebra`, `complex`).
  See `mcp_flat_valid.jsonl` and `mcp_flat_malformed.jsonl`.
* Unknown methods, bad ids, missing params, batch arrays (including `[]` and
  non-object elements), and bare non-JSON values were all exercised in
  `mcp_protocol.jsonl` / `mcp_protocol2.jsonl`; response ids and codes are
  stable and documented.
