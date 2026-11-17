# Stress findings — `sat_wrap_domain`

_Original heading: FINDINGS — `sat_wrap_domain`_

# FINDINGS — `sat_wrap_domain`

All commands below were run with `$ROOT/ucas` (already built), bounded by
`timeout`, from this directory unless a path is shown.  Every golden `.out` in this folder was
generated twice and `diff`ed: all 15 goldens are byte-for-byte deterministic.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | constant `INT64_MIN / -1` raises SIGFPE at fold time |
| WRONG | 4 | `wrap` end-to-end never reports a mismatch for `i64` |
| NLP | 1 | English "wrap" phrasing not accepted |
| DETERMINISM | 1 | in-process MCP server has a global definition table and can die |

## Findings

### CRASH-1 — constant `INT64_MIN / -1` raises SIGFPE at fold time
**Severity:** CRASH
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (CLI):
```sh
printf 'f(x: i64) = -9223372036854775808 / -1\nshow f\n' | timeout 10 $ROOT/ucas
```
Also kept as `repro_crash_int64min.ucas` (run it with `timeout 10 $ROOT/ucas repro_crash_int64min.ucas`).

**Observed:** (exit 136 = 128+8, SIGFPE; stdout is empty):
```
/usr/bin/bash: line 1: ... Floating point exception   | timeout 10 ./ucas ...
timeout: the monitored command dumped core
stdout=[]
```
It crashes during constant folding of the definition itself: `show`, `wrap`, `domain`,
`range`, `table` and a bare definition all crash.  `-128 / -1`, `-32768 / -1` and
`-2147483648 / -1` are fine (they are `int` values inside int64), and the *variable* form
`f(x: i64 in {-9223372036854775808}) = x / -1` is handled correctly (`wrap`/`domain`/`range`
report the UB and the wrapped value).  Only the constant INT64_MIN literal Div triggers the
host `IDIV` overflow.

MCP reproducer: `repro_crash_int64min.jsonl`
```sh
timeout 15 $ROOT/ucas --mcp < repro_crash_int64min.jsonl > /tmp/x.out 2>&1
# exit 136; output stops after the `initialize` + `notifications/initialized` lines
# (truncated JSON-RPC stream, no reply to id 1 or 2)
```
**Expected:** a note that `INT_MIN / -1` wraps (as the variable form gets), not a process kill.

### WRONG-1 — `wrap` end-to-end never reports a mismatch for `i64`
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'f(x: i64) = -x\nwrap f\n' | $ROOT/ucas
```
**Observed:**
```
wrap analysis of f:
  -x   (i64)
      nuw fails: unsigned wrap at 65535 points, e.g. x=-9223372036854775808
      nsw fails: signed wrap at 1 points, e.g. x=-9223372036854775808  <- UB in C; a compiler assumes it cannot happen
  end to end: differs from the mathematical result at 0 points, e.g.
  sampled 65536 points (domain has 2^64 or more points); not exhaustive
```
`nsw fails at 1 point` but `end to end: differs at 0 points` with an empty `e.g.`.  The same
happens for every i64 wrapping expression (`x + INT64_MAX`, `x*3`, `x+x`, `x - INT64_MIN`)
and for a singleton domain:
```
f(x: i64 in {-9223372036854775808}) = -x
wrap f   ->   nsw fails at 1 points, e.g. x=-9223372036854775808
              end to end: differs from the mathematical result at 0 points, e.g.
```
The i8/i16/i32 twins report the correct count (1 point for negation).  u64 `wrap` also
reports mismatches correctly.  Root cause is evidently that the "ideal" twin of `i64` is
`int`, which is itself checked at the int64 range, so the mathematical result wraps the same
way as the machine result.  MCP `structuredContent` repeats the bogus value
(`"end_to_end":{"exact":false,"mismatch_points":0}` despite `signed_wrap_points:1`).
Kept as golden `03_i64_wrap_wrong.ucas`/`.out` and in `mcp_wrap_domain_range.jsonl` (id 7).

### WRONG-2 — `range` "proved bound" for i64 negation claims an unreachable maximum 2^63
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'g(x: i64) = -x\nrange g\n' | $ROOT/ucas
```
**Observed:**
```
range of g -> i64:
  -9223372036854775808..9223372036854775807
  fits in i64
  sampled 65536 points (domain has 2^64 or more points); not exhaustive
  sound bound (intervals): -9223372036854775808..9223372036854775807
  proved bound (monotonicity, exact algebra): -9.2233720368547758e+18..9.2233720368547758e+18
  the sample reaches both ends: the range is exactly -9.2233720368547758e+18..9.2233720368547758e+18 (proved)
    max: g is nonincreasing in x, so take x = -9223372036854775808:
      --9223372036854775808
      in 9.2233720368547758e+18..9.2233720368547758e+18 by intervals
```
The top line says the range is `[-2^63, 2^63-1]`, but the "proved" claim is
`[-2^63, 2^63]`: the upper endpoint is 2^63, which is not representable in i64 and is not
reachable (`-INT64_MIN` wraps to `-2^63`).  The monotonicity proof ignores the wrap at the
single endpoint exponent.  i8/i16/i32 do not emit this line (they are exhaustive or use only
the sound interval bound).  Kept in `03_i64_wrap_wrong.out` and MCP golden id 9.

### WRONG-3 — `wrap` end-to-end error for `u64 -> f32/f64` conversion is nonsense
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'f(x: u64) = f64(x)\nwrap f\n' | $ROOT/ucas
```
**Observed:**
```
wrap analysis of f:
  f64(x)   (f64)
      nnan holds (no NaN from non-NaN inputs)
      ninf holds
  end to end vs the real-number result: max abs error 1.84e+19, max rel error 1.84e+19, max 8.94415e+18 ulp
      worst relative error at x=18446744073709551615
```
`f64(2^64-1)` rounds to 2^64 with relative error ~5e-20, not 1.84e19.  The last value matches
the *int* twin wrapping `2^64-1` to `-1`, then comparing `2^64` to `-1`.  `u64 -> f32` shows
the same `1.84e+19` max rel error.  `i64 -> f64` and `i32 -> f32` are correct (~2^-24/2^-53).
Kept in golden `10_int_to_float.out`.

### WRONG-4 — `equiv` accepts an undefined function name and answers "equal"
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (the second name is not defined at the time of the call):
```sh
printf 'rt1(x: f32) = asfloat(asuint(x))\nequiv rt1 idf\nidf(x: f32) = x\n' | $ROOT/ucas
```
**Observed:**
```
rt1 and idf are equal on the domain of rt1 (sampled, not proved; no SAT proof: its counterexample did not reproduce)
```
MCP `structuredContent` for the same call: `"equal": true, "mismatch_points": 0,
"method": "sampled", "sat": {"result":"unsupported","why":"its counterexample did not reproduce"}`.
A bare unknown name becomes a free variable (`show nosuch` -> `_(nosuch: real) = nosuch`);
comparing a defined f32 function against an out-of-domain real variable reports "undefined vs
undefined" as *equal*.
**Expected:** reject the unknown function name (or report a mismatch).
Also reproduces with `f(x: f32) = x; equiv f nosuch`.

### NLP-1 — English "wrap" phrasing not accepted
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'wrap x plus one for a signed byte x\n' | $ROOT/ucas
```
**Observed:**
```
  sorry: of what?
```
"what is the range of x squared for a signed byte x?", "domain of 1/x for x an unsigned byte",
"show the wrapping of x times 2 for a signed 8 bit x" and "what is the range of f for an i64 x
where f is minus x" all route correctly (the last one also exposes finding 3).  The bare
"wrap <english expr> for a <type> x" form is not recognised.

### DETERMINISM-1 — in-process MCP server has a global definition table and can die
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (harness-level caveat, not a tool golden`._
**Reproducer:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Observed:** during this run through Code Mode `tools.ucas.*`: defining `f(x: f32) = x + 1` in one
call and then calling `wrap f` in a later call returned `x^2 + 1 (u8)`, i.e. a definition made
by another concurrent session; later the server reported
`MCP tool "ucas" on server "ucas" failed: Connection closed: MCP server process exited`.
This is the shared in-process MCP server, not the per-file CLI server.  All MCP goldens in this
folder therefore use isolated `ucas --mcp < FILE.jsonl` processes (`mcp_wrap_domain_range.*`,
`mcp_flags_flat.*`), which were verified deterministic by running twice and diffing.

## Checks that passed

### Non-findings (verified correct)
- i8 wrap `nsw`/`nuw` counts, witnesses, and multi-interval `exact for` bands were cross-checked
  against an independent Python bit-level simulator for ~15 expression shapes (add, sub,
  constant-multiply, square, negate, `x*x+x*x`, disjoint-product `(x-123)*(x-100)`,
  `(x*2)/2`, piecewise absolute value, cube).  All matched.
- `domain` correctly reports shift-amount UB (`0 <= n < width`), division-by-zero, and the
  `INT_MIN / -1` UB for the variable form.
- `real` vs `f32/f16/f64` `sqrt`/`1/0`/`log` domain and nnan/ninf wrap reports are consistent.
- Float bit-cast round-trips and `ftz`/`nanbits` equiv proofs are stable and correct when both
  operands are properly defined.
