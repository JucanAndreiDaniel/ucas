# Stress findings — `spirv_glsl_simplify`

_Original heading: Findings — `spirv_glsl_simplify` stress area_

# Findings — `spirv_glsl_simplify` stress area

All commands use the already-built `$ROOT/ucas` (no rebuild).
`spirv-cross` is **not installed** on this host; that is recorded as LIMIT-1, not a bug.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | 1 — 64-bit comparison operands are inferred as 32-bit (wrong proof domain) |
| NLP | 1 | 1 — a GLSL compile failure is reported as a SPIR-V parse error |
| LIMIT | 3 | 1 — spirv-cross not installed (GLSL view skipped) |
| DETERMINISM | 2 | 1 — malformed GLSL error text contains a random temp filename |

## Findings

### WRONG-1 — 1 — 64-bit comparison operands are inferred as 32-bit (wrong proof domain)
**Severity:** WRONG
**Reproducer:**
```sh
printf '%s' '{"id":1,"cmd":"spirv_simplify","args":{"code":"%c = OpULessThan %bool %lx %ulong_8\\n%k = OpSelect %ulong %c %lx %ulong_8\\nOpStore %out %k","lang":"spv","nofile":true,"budget":2}}' | $ROOT/ucas --json --files none
```

**Observed:** (excerpt of `text`):
```
  input %lx: uint
  output %out: ulong (stored to; its values are listed after the run)
```

**Why it matters:** `%ulong_8` is a 64-bit constant and `%k`/`%out` are `ulong`, so the
free input `%lx` must be a 64-bit value. Arithmetic ops get this right
(`%r = OpIAdd %ulong %lx %ulong_8` reports `input %lx: ulong`), but **every comparison
opcode** gets it wrong. Surveyed: `OpULessThan`, `OpUGreaterThan`, `OpULEqual` →
`uint`; `OpSLessThan`, `OpIEqual`, `OpINotEqual` → `int`. SAT proofs and any assumption
on `%lx` are therefore carried out on a 32-bit domain that is not the one the
instruction uses, so a rewrite can be "proved" for values the real shader cannot take.

**Expected:** `input %lx: ulong`, with the proof over 64 bits.

### WRONG-2 — 2 — large `ranges` bounds overflow to INT64_MIN, producing unsound rewrites
**Severity:** WRONG
**Reproducer:**
Reproducer A (corrupted bound is echoed back):
```sh
printf '%s' '{"id":1,"cmd":"spirv_simplify","args":{"code":"%a = OpIAdd %uint %x %uint_1\\nOpStore %out %a","lang":"spv","nofile":true,"budget":1,"ranges":{"x":[0,9223372036854775807]}}}' | $ROOT/ucas --json --files none
```

**Observed:**
```json
"ucas": "spvsimplify budget 1 nofile assume x 0 -9223372036854775808",
"assumptions": [{"name": "x", "lo": 0, "hi": -9223372036854775808}]
```

Any upper (or lower) bound at or near `2^63` wraps to `-9223372036854775808`.
Characterisation: values up to ~`9e18` pass through, `9223372036854774808` is
rounded to `9223372036854774784`, and `9223372036854775807` (`INT64_MAX`) becomes
`INT64_MIN`. This is consistent with parsing the JSON integer as a `double` and
casting to `int64` (`INT64_MAX` rounds to `2^63`, which overflows).

**Reproducer:**
Reproducer B (the corrupted assumption drives an unsound rewrite):
```sh
printf '%s' '{"id":1,"cmd":"spirv_simplify","args":{"code":"%c = OpULessThan %bool %lx %ulong_8\\n%k = OpSelect %ulong %c %lx %ulong_8\\nOpStore %out %k","lang":"spv","nofile":true,"budget":3,"ranges":{"lx":[9223372036854775808,9223372036854775810]}}}' | $ROOT/ucas --json --files none
```

**Observed:** (rewrites + assumption):
```
  assuming lx in [-9223372036854775808, -9223372036854775808] (every load of it)
  rewrites:
    %c = OpULessThan %bool %lx %ulong_8  ->  true   (always this value)
    %k = OpSelect %ulong %c %lx %ulong_8 ->  0      (always this value)
```

**Why it matters:** the real range is `lx in [2^63, 2^63+2]`. Every one of those
values is `>= 8`, so `lx < 8` is **false** and the select's result is the constant **8**.
The tool instead rewrites the output to **0** (and even reports the compare as `true`
while reporting the select as `0`, which is internally inconsistent). This is a
concrete unsound rewrite caused by the overflowed range. (WRONG-1 compounds it by
typing `%lx` as 32-bit.)

**Expected:** reject an out-of-range bound, or parse it exactly (bigint), and never
emit a rewrite that is false on the requested range.

### DETERMINISM-1 — 1 — malformed GLSL error text contains a random temp filename
**Severity:** DETERMINISM
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf '%s' '{"id":1,"cmd":"spirv_simplify","args":{"code":"#version 450\\nvoid main( { syntax error here","lang":"glsl","nofile":true,"budget":2}}' | $ROOT/ucas --json --files none
printf '%s' '{"id":1,"cmd":"spirv_simplify","args":{"code":"#version 450\\nvoid main( { syntax error here","lang":"glsl","nofile":true,"budget":2}}' | $ROOT/ucas --json --files none
```

**Observed:** two runs differ only in the glslang temp path:
```
ERROR: /tmp/ucas-glsl-FcjCxU.glsl:2: '' : syntax error, unexpected LEFT_BRACE ...
```
vs.
```
ERROR: /tmp/ucas-glsl-tSWmdR.glsl:2: '' : syntax error, unexpected LEFT_BRACE ...
```
The `error` object itself is stable; only `text` moves. Running such a case twice under
`timeout` and `diff` fails. I therefore kept no golden `.out` for malformed-GLSL cases.

**Expected:** a stable diagnostic (fixed placeholder path, or omit the temp path).

### DETERMINISM-2 — 2 — wall-clock timing embedded in human-readable output
**Severity:** DETERMINISM
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer:** any case whose derivation takes measurable time; e.g.
`approx:true, ulp:100000, search:"anneal", seed:1` on `OpExtInst %glsl Pow`, or a
200-statement GLSL shader. Run the same request twice and `diff` the outputs.

**Observed:** (only difference between two runs):
```
-  derived in 3.5 s
+  derived in 3.4 s
```
and
```
-  proved in 1.9 s; the operands' definitions were expanded up to 16 levels ...
+  proved in 1.8 s; the operands' definitions were expanded up to 16 levels ...
```
The structured `result` (rewrites, `ulp_bound`, nofile checksum) is byte-identical;
only the `text` field varies. This makes CLI `.out` goldens for slow cases flaky.
All goldens in this folder were chosen from fast cases and were verified deterministic
by running each twice and diffing.

**Expected:** omit the fractional timing from text, or keep it only in a
machine-readable field.

### NLP-1 — 1 — a GLSL compile failure is reported as a SPIR-V parse error
**Severity:** NLP
**Reproducer:**
```sh
printf '%s' '{"id":1,"cmd":"spirv_simplify","args":{"code":"#version 450\\nlayout(local_size_x=64) in;\\nuint f(uint n){return n<=1u?1u:n*f(n-1u);}\\nvoid main(){uint i=gl_GlobalInvocationID.x;}","lang":"glsl","functions":true,"nofile":true,"budget":2}}' | $ROOT/ucas --json --files none
```

**Observed:** the real reason (glslang `Linking compute stage: Recursion detected`)
is demoted to a note, while the top-level error is
```json
{"code": "failed", "message": "SPIR-V: not an instruction: \"#version 450\"", ...}
```

**Why it matters:** with `lang: "glsl"` (and a `#version` line) the tool should keep
the GLSL compile error as the primary error instead of re-parsing the GLSL source as
SPIR-V assembly and reporting a misleading second error.

**Expected:** `{"code":"failed","message":"... recursion detected ..."}` or similar.

### LIMIT-1 — 1 — spirv-cross not installed (GLSL view skipped)
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Observed:** on every simplification of a GLSL/SPIR-V input:
**Reproducer:**
```sh
  GLSL view: spirv-cross not found (install it, pkg install spirv-cross, or put it on PATH): skipped
```
`glslangValidator`, `spirv-opt`, `spirv-dis` and `spirv-as` are present; only
`spirv-cross` is missing. No `glsl_view` diff can be produced in this environment.
Not a tool bug — no fix sought here.

### LIMIT-2 — 2 — transient Code Mode MCP server disconnect (not reproducible)
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
During one batch of Code-Mode `tools.ucas.spirv_simplify` calls the MCP server process
exited (`Connection closed: MCP server process exited`), and the `ucas` tool namespace
was briefly unavailable. Replaying the same requests through `ucas --mcp` (fresh
JSONL session, all six range-overflow values) returned normally with exit 0, and
`--json` runs of the same inputs were all exit 0. I could not reproduce a crash in the
binary itself, so I am not claiming a CRASH; recording it as a transient/observability
limit only.

### LIMIT-3 — Minor: accepted-invalid inputs (LIMIT / low severity)
**Severity:** LIMIT
_Original classification: `LIMIT / low severity`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
These are handled without crashing but are silently accepted rather than rejected:

- `ranges: {"n":[31,1]}` (lo > hi) — accepted, empty assumption, no error.
- `float_ranges: {"x":[10,0]}` (lo > hi) — accepted, assumption silently dropped.
- `ulp: -1` — accepted; mode silently falls back to `vulkan_precision`.
- `code: ""` — `bad_request "code: a string"` (an empty string is treated as absent).
- Non-JSON NUL byte (`\u0000`) in `code` — `bad_json` from the JSON reader (protocol-level, expected).

Properly rejected (good): `ranges` with strings/3-element/empty arrays, `float_ranges`
with `"nan"`/`"inf"`/empty, `seed:-1`, `sink:"bogus"`, `model:"no_such_model"`
(parse_error that lists valid models), inline assembly in C, malformed SPIR-V text.

## Checks that passed

_No separate passed checks were recorded in the original document._
