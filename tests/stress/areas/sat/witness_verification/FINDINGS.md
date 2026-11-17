# Stress findings — `witness_verification`

_Original heading: Findings — witness_verification_

# Findings — witness_verification

Scope: independent verification of ucas witnesses (equiv/differ counterexamples,
wrap, domain, crit, range, error, fit) on u4/u8/i8/i16 by a Python bit-accurate
interpreter (`expr_eval.py`) plus full-domain brute force (`verify_witnesses.py`).

**Witness result:** 222 cases per seed × 2 seeds (444 case-runs) were checked.
Every displayed witness and every global claim (equal, differ count, wrap count,
undefined count, local extrema, reachable values, worst point) matched our
independent brute-force computation. No fabricated/wrong witness, false `equal`,
or missing extremum was found in the CLI witness machinery.

The issues below are adjacent problems found while building/validating the
verifier.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | MCP `session/define` without a JSON-RPC `id` silently does not register the definition |
| LIMIT | 1 | MCP `equiv` with expression strings fails to parse |

## Findings

### LIMIT-1 — MCP `equiv` with expression strings fails to parse
**Severity:** LIMIT
_Original classification: `LIMIT (NLP/MCP routing`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (copy-pasteable; an `analyze`/`equiv` call with expression strings):

```sh
cd $ROOT/tests/stress/areas/sat/witness_verification
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"equiv","args":{"f":"(x*y)^5","g":"(y*x)^5"}}}}' \
 | $ROOT/ucas --mcp
```

**Observed:** (last line):

```json
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"error (parse_error): expected an expression\n\n<json>:1:22: error: expected an expression\n    equiv (x*y)^5 (y*x)^5\n                         ^\n"}],"structuredContent":{"id":1,"ok":false,"cmd":"equiv","ucas":"equiv (x*y)^5 (y*x)^5","error":{"code":"parse_error","message":"expected an expression","pos":{"line":1,"col":22}}},"isError":true}}
```

**Why it matters:** it's a bug / expected:** the MCP tool turns this example JSONL call into
the ucas statement `equiv (x*y)^5 (y*x)^5`, which the ucas CLI grammar rejects
(`equiv F G` wants function names, or typed applications such as `isqrt(x: u4)`,
not two bare expression strings). Either the example should work, or the tool
should return a clear "define the functions first" diagnostic rather than a
low-level parse error. Working form:
define f and g with `session`/`define` (with `id`s), then call `equiv` with
`{"f":"f","g":"g"}` — see `mcp_witnesses.jsonl`/`.out`.

### WRONG-1 — MCP `session/define` without a JSON-RPC `id` silently does not register the definition
**Severity:** WRONG
_Original classification: `WRONG (state handling`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/witness_verification
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"session","arguments":{"op":"define","args":{"name":"f","params":[{"name":"x","type":"u8"}],"body":"x*x"}}}}' \
 '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"session","arguments":{"op":"define","args":{"name":"g","params":[{"name":"x","type":"u8"}],"body":"x*x+1"}}}}' \
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"session","arguments":{"op":"funcs","args":{}}}}' \
 '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"equiv","args":{"f":"f","g":"g"}}}}' \
 | $ROOT/ucas --mcp
```

**Observed:** (last two lines):

```json
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"text\": \"\"}"}],"structuredContent":{"id":3,"ok":true,"cmd":"funcs","structured":false,"result":{"text":""}}}}
{"jsonrpc":"2.0","id":4,"result":{"content":[{"type":"text","text":"error (parse_error): expected an expression\n\n<json>:1:10: error: expected an expression\n    equiv f g\n             ^\n"}],"structuredContent":{"id":4,"ok":false,"cmd":"equiv","ucas":"equiv f g","error":{"code":"parse_error","pos":{"line":1,"col":10}}},"isError":true}}
```

**Why it matters:** it's a bug / expected:** the two `define` calls are well-formed and are
accepted without error, but `funcs` reports an empty state and `equiv f g` then
fails as if `f`/`g` were undefined. Adding an `id` field to each `define` makes
the *same* definitions register correctly and `equiv f g` returns
`f and g differ at 256 points, e.g. x=0: 0 vs 1`. Notification-style calls
(no `id`) should still mutate session state, or should be rejected loudly;
silently dropping the state change is unsound for any session-based client.

### WRONG-2 — constant-folded values are not reduced to the declared machine type when combined with a boolean/comparison operand
**Severity:** WRONG
_Original classification: `WRONG (out-of-type range`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/witness_verification
printf 'f(x: u4) = ((13 * 14) xor (4 * 15)) + (x == 4)\ntable f\nrange f\n' \
  | $ROOT/ucas
```

**Observed:**

```
  x=0  ->  138
  x=1  ->  138
  ...
  x=4  ->  139
range of f -> int:
  138..139
  fits in u8
  over all 16 points of the domain
```

**Why it matters:** it's a bug / expected:** `f` is declared `u4`, so every value must lie in
0..15. The constant subtree `(13*14) xor (4*15)` folds to the unbounded value
138 (= 0b10001010); when combined with a *comparison* operand `(x == 4)` ucas
keeps 138/139 instead of reducing them into u4 (10/11). Compare with the same
constant added to a plain variable, `f(x: u4) = x + ((13*14) xor (4*15))`, where
ucas correctly emits `note: literal 138 does not fit u4; it becomes 10` and
reports `range 0..15`. This inconsistency makes `table`/`range` return values
outside the function's declared type and can mislead any witness checker that
takes `table` as ground truth.

## Checks that passed

### Notes on verifier accuracy
`expr_eval.py` was validated against ucas `table` on 10,336 machine-value
comparisons (0 mismatches) over u4/u8/i8/i16 after modelling ucas's constant
folding. A few ucas constant-folding quirks (e.g. `~(x xor x)` in u8, or a
ternary whose arms are large constant subtrees) are handled explicitly in the
verifier and are reported as such in `verify_report.txt`; they are not counted
as witness failures.
