# Stress findings — `parser_json_fuzz`

_Original heading: FINDINGS — `parser_json_fuzz`_

# FINDINGS — `parser_json_fuzz`

Frontends exercised: CLI `.ucas`, `--json` (JSONL, `--files none`), `--mcp` (JSON-RPC JSONL).
All reproducers use the absolute binary `$ROOT/ucas` and are bounded by `timeout`.
Crash/hang cases are documented here only — they are **not** kept as golden `.out` tests.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 5 | 1 — deep parenthesis nesting segfaults the CLI parser |
| HANG | 1 | 1 — quadratic blowup on a long identifier |
| LIMIT | 5 | 1 — lexical error anywhere in a `.ucas` file aborts the entire file |

## Findings

### CRASH-1 — 1 — deep parenthesis nesting segfaults the CLI parser
**Severity:** CRASH
_Original classification: `CRASH-1`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd /tmp/opencode
python3 -c "open('deep.ucas','w').write('show '+'('*2000+'x'+')'*2000+'\n')"
timeout 15 $ROOT/ucas deep.ucas > deep.out 2>&1; echo $?
```

**Observed:** : exit code **139** (SIGSEGV). `deep.out` contains only the echoed first line
(`> show ` followed by 2000 `(` …) before the process dies; no diagnostic is printed.
Threshold measured on this host: 1520 parens → exit 0; 1540 parens → SIGSEGV.
The same crash occurs for 2000 unmatched leading `(` (`show ` + `(`*20000, exit 139).

**Why it matters:** it is a bug**: malformed-but-finite input should produce a `parse_error` (or a depth
limit like the JSON frontend's `bad_json` "nested too deeply"), not a stack overflow. The
partial output is stable, but the crash makes it unsuitable as a golden.

### CRASH-2 — 2 — deep unary-minus chain segfaults the CLI parser
**Severity:** CRASH
_Original classification: `CRASH-2`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd /tmp/opencode
python3 -c "open('unary.ucas','w').write('show ' + '-'*2000 + 'x\n')"
timeout 15 $ROOT/ucas unary.ucas > unary.out 2>&1; echo $?
```

**Observed:** : exit code **139** (SIGSEGV), with only partial echoed output. Threshold on
this host: 1500 minuses → exit 0; 1550 minuses → SIGSEGV.

**Why it matters:** it is a bug**: unbounded recursion in the unary-expression parser; should be a
graceful parse error or depth limit.

### CRASH-3 — 3 — deep nested function calls segfault the CLI parser
**Severity:** CRASH
_Original classification: `CRASH-3`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd /tmp/opencode
python3 -c "open('fns.ucas','w').write('show ' + 'sqrt('*3000 + 'x' + ')'*3000 + '\n')"
timeout 15 $ROOT/ucas fns.ucas > fns.out 2>&1; echo $?
```

**Observed:** : exit code **139** (SIGSEGV), partial echoed output only.

**Why it matters:** it is a bug**: same unbounded-recursion class as CRASH-1/2.

### CRASH-4 — 4 — a single malformed request kills the entire `--json` server (no `timeout_s`)
**Severity:** CRASH
_Original classification: `CRASH-4`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_json_fuzz
python3 - <<'PY' > /tmp/opencode/jkill.jsonl
import json
print(json.dumps({"id":1,"cmd":"ucas","args":{"source":"show "+("("*3000)+"x"+(")"*3000)}}))
print(json.dumps({"id":2,"cmd":"bigint","args":{"expr":"2^10"}}))
PY
timeout 30 $ROOT/ucas --json --files none < /tmp/opencode/jkill.jsonl; echo $?
```

**Observed:** : exit code **139** (SIGSEGV) and `timeout: the monitored command dumped core`.
Request 2 is never answered — the whole JSONL stream is lost.

With `timeout_s` present the failure is contained and the documented code is returned:
```json
{"id": 1, "ok": false, "cmd": "ucas", "error": {"code": "internal", "message": "the evaluation crashed (signal 11); the state is unchanged"}}
{"id": 2, "ok": true, "cmd": "bigint", ...}
```

**Why it matters:** it is a bug**: one malformed request should not take down the server and discard
queued requests; a per-request fault boundary should not depend on the client opting in
with `timeout_s`.

### CRASH-5 — 5 — a single malformed request kills the entire `--mcp` server
**Severity:** CRASH
_Original classification: `CRASH-5`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_json_fuzz
python3 - <<'PY' > /tmp/opencode/mkill.jsonl
import json
print('{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}')
print('{"jsonrpc":"2.0","method":"notifications/initialized"}')
print(json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":"show "+("("*3000)+"x"+(")"*3000)}}}))
print('{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"show","args":{"f":"x+1"}}}}')
PY
timeout 30 $ROOT/ucas --mcp < /tmp/opencode/mkill.jsonl; echo $?
```

**Observed:** : the `initialize` answer is emitted, then exit code **139** (SIGSEGV) with
`timeout: the monitored command dumped core`; the request after the deep one is never
answered.

**Why it matters:** it is a bug**: same per-request fault-isolation gap as CRASH-4, on the MCP wire.

### HANG-1 — 1 — quadratic blowup on a long identifier
**Severity:** HANG
_Original classification: `HANG-1`._
**Reproducer:**
```sh
cd /tmp/opencode
python3 -c "open('longid.ucas','w').write('show ' + 'a'*100000 + '\n')"
time timeout 15 $ROOT/ucas longid.ucas > longid.out 2>&1; echo $?
```

**Observed:** : exit code **124** (timeout) at 100 000 characters (>12 s). Measured scaling:
10 000 chars ≈ 0.26 s, 20 000 ≈ 0.86 s, 50 000 ≈ 5.3 s, 100 000 > 12 s — quadratic.
At 200 000 chars it also times out, having already echoed the input line.

**Why it matters:** it is a bug / expected**: a single identifier token should be linear in length; a
client can wedge the process with a ~100 KB token.
**Expected:** fast reject or linear scan.

### LIMIT-1 — 1 — lexical error anywhere in a `.ucas` file aborts the entire file
**Severity:** LIMIT
_Original classification: `LIMIT-1`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd /tmp/opencode
printf 'bigint 2^10\nshow @@@\nbigint 3^10\n' > tok.ucas
timeout 10 $ROOT/ucas tok.ucas
```

**Observed:** :
```
tok.ucas:2:6: error: unexpected character '@'
    show @@@
         ^
```
Neither statement 1 nor 3 executes — there is no `> bigint ...` echo and no output from
them. (In contrast, *parse* errors such as `show (x` are recovered per statement and
the surrounding statements do run.)

**Why it matters:** it matters**: a single stray byte anywhere discards all work in the file. Kept as a
documented behavior (goldens `02_unterminated`, `04_bad_unicode`, `05_parse_edges`,
`07_lex_comment`, `08_lex_backslash`, `09_lex_escape`, `11_unmatched_bracket` each
isolate one such error).

### LIMIT-2 — 2 — duplicate parameter names silently accepted
**Severity:** LIMIT
_Original classification: `LIMIT-2`._
**Reproducer:**
```sh
printf '%s\n' '{"id":1,"cmd":"define","args":{"name":"g","params":[{"name":"x","type":"u8"},{"name":"x","type":"i8"}],"body":"x"}}' \
 | timeout 10 $ROOT/ucas --json --files none
```

**Observed:** : `"ok": true`, `ucas: "g(x: u8, x: i8) = x"`, both params echoed, no note or
error. CLI `f(x: u8, x: i8) = x` also passes silently (golden `01_bad_types.out`).

**Why it matters:** it is a bug / expected**: a duplicate parameter is almost certainly a typo; JSON
mode is documented to reject malformed arguments with `bad_request`.
**Expected:** reject.

### LIMIT-3 — 3 — reserved words accepted as parameter/function names
**Severity:** LIMIT
_Original classification: `LIMIT-3`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_json_fuzz
timeout 10 $ROOT/ucas 14_reserved_names.ucas | head
```

**Observed:** : `f(in: u8) = in`, `f(if: u8) = if`, `f(for: u8) = for`, `f(real: u8) = real`,
`f(bool: u8) = bool` all define silently. `f(sum: u8) = sum` is *accepted as a definition*
but its body fails with `error: 'sum' is not defined` — inconsistent. JSON `define` with
`name: "in"`, `"if"`, `"real"` likewise returns `ok:true` (golden `json_args.out`).

**Why it matters:** it matters**: reserved words (`sum`, `in`, `if`, `where`, type names, command names)
should be rejected at definition time, not half-accepted.

### LIMIT-4 — 4 — out-of-range parameter ranges silently accepted
**Severity:** LIMIT
_Original classification: `LIMIT-4`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_json_fuzz
timeout 10 $ROOT/ucas 13_bad_ranges.ucas
```

**Observed:** : `f(x: u8 in -1..255) = x`, `f(x: u8 in 0..256) = x` and
`f(x: i8 in -128..128) = x` all define with no note or error (only genuinely inverted
ranges like `5..1` get `domain_error`). JSON `define` with `range: [0, 256]` on a `u8`
returns `ok:true` (golden `json_numbers.out`).

**Why it matters:** it is a bug / expected**: a range partly outside the declared machine type's domain
is malformed; expected a `domain_error` or a note.

### LIMIT-5 — 5 — invalid `timeout_s` values silently accepted
**Severity:** LIMIT
_Original classification: `LIMIT-5`._
**Expected:** _not recorded_
**Reproducer:**
```sh
printf '%s\n' \
 '{"id":1,"cmd":"show","args":{"f":"x","timeout_s":-5}}' \
 '{"id":2,"cmd":"show","args":{"f":"x","timeout_s":"abc"}}' \
 '{"id":3,"cmd":"show","args":{"f":"x","timeout_s":1e9}}' \
 | timeout 15 $ROOT/ucas --json --files none
```

**Observed:** : all three return `"ok": true` with normal `show` results; no `bad_request`.
(Other options are validated: `assume:123`, `defaults:"yes"`, `answers:123`,
`files:"bogus"` all give `bad_request` — see golden `json_numbers.out`.)

**Why it matters:** it is a bug / expected**: a non-positive or non-numeric timeout is meaningless;
expected `bad_request`, or at least a note.

## Checks that passed

### Positive observations (no bug)
- All error codes observed across both JSON frontends are in the documented set
  (`bad_json`, `bad_request`, `unknown_command`, `parse_error`, `domain_error`, `failed`,
  `internal`, plus MCP protocol codes -32700/-32600/-32601/-32602). No undocumented code,
  and no `ok:true` on syntactically malformed JSON.
- The JSON parser gracefully rejects: truncated JSON, bad literals, single quotes, trailing
  commas, trailing garbage, `NaN`/`Infinity`, duplicate keys, bad `\u` escapes, unpaired
  surrogates, `\u0000`, and nesting deeper than ~62 levels (`bad_json: nested too deeply`).
- Unknown commands → `unknown_command`; unknown args / wrong types / missing required args
  → `bad_request`; `english` with an empty `text` → `bad_request`, with a non-string `text`
  → `bad_request`, and with an unreadable character (`@@@@`) → `parse_error`.
- All 20 kept golden `.out` files were regenerated and `diff`-ed twice: byte-identical
  (no nondeterministic witness, timing, or cost numbers).
