# Stress findings — `type_coercion`

_Original heading: FINDINGS — `type_coercion`_

# FINDINGS — `type_coercion`

Area: implicit type inference and cross-type coercion (`uN`, `iN`, `int`, `real`,
`f16/f32/f64`, `bool`, `complex`, `quat`, `cd(N)`, tables, `match`, ranges,
`asuint`/`asint`/`asfloat`).

All goldens in this folder are deterministic (each generated twice and `diff`ed).
No crash, hang, or nondeterministic case was found: 49 adversarial single-expression
probes were each run under `timeout 8` with exit code 0, and every would-be golden
was run twice with identical output. Issues below are wrong/inconsistent answers.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 5 | `equiv` proves a signed↔unsigned reinterpretation equal |
| LIMIT | 2 | inline definitions passed to `range`/`wrap` are misparsed |

## Findings

### WRONG-1 — `equiv` proves a signed↔unsigned reinterpretation equal
**Severity:** WRONG
**Expected:** _not recorded_
A `u8` identity and an `i8` reinterpretation of the same bits are declared equal,
although their values and ranges differ (`a(200) = 200`, `b(200) = i8(200) = -56`;
`range a` = 0..255, `range b` = -128..127).

**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/math/type_coercion && $ROOT/ucas 06_equiv_reinterpret.ucas
```
Exact observed output (from `06_equiv_reinterpret.out`):
```
> range a
range of a -> u8:
  0..255   (256 distinct values)
  fits in u8
  over all 256 points of the domain
> range b
range of b -> i8:
  -128..127   (256 distinct values)
  fits in i8
  over all 256 points of the domain
> equiv a b
a and b are equal on the domain of a (exhaustive)
> equiv b a
b and a are equal on the domain of b (exhaustive)
```
Also confirmed over MCP (`mcp_type_coercion.out`, ids 5–7):
`"result": {"kind": "equiv", "equal": true, "exhaustive": true, "mismatch_points": 0}`
while `range a`/`range b` report `0..255` / `-128..127`.

**Why it matters:** `equiv` is documented to check value equality on the domain. Comparing
before coercion, `a` and `b` differ on 128 of 256 inputs. It appears to coerce both
results to F's (unsigned) result type before comparing, so bit patterns are compared
instead of mathematical values. The same effect makes
`equiv fneg constm1` report "differ at 255 points, e.g. x=-128: 128 vs 255" — the
`-1` constant is silently shown as `255` (u8). Wrong "equal" proofs are unsound.

### WRONG-2 — `range` monotonicity "proved bound" is wrong for wide signed types (i56–i63)
**Severity:** WRONG
**Expected:** _not recorded_
For an identity on `i56`, `i59`, `i60`, `i61`, `i62`, `i63`, the *proved* upper bound
is reported equal to the lower bound and the max is attributed to the lower endpoint.
`i32` and `i64` are correct, so this is a width-dependent bug (≥56 bits).

**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/math/type_coercion && $ROOT/ucas 05_range_signed_boundary.ucas
cd $ROOT/tests/stress/areas/math/type_coercion && $ROOT/ucas --mcp < mcp_range_boundary.jsonl
```
Exact observed output (`05_range_signed_boundary.out`):
```
range of i63id -> i63:
  -4611686018427387904..4611686018427387903
  fits in i63
  sampled 65536 points (domain has 9223372036854775808 points); not exhaustive
  sound bound (intervals): -4611686018427387904..4611686018427387903
  proved bound (monotonicity, exact algebra): -4.6116860184273879e+18..-4.6116860184273879e+18
  the sample reaches the lower end: the minimum is exactly -4.6116860184273879e+18 (proved)
    max: i63id is nondecreasing in x, so take x = -4611686018427387904:
      -4611686018427387904
    min: i63id is nondecreasing in x, so take x = -4611686018427387904:
      -4611686018427387904
    (a bound the sample does not reach may still be loose)
```
MCP `structuredContent` (`mcp_range_boundary.out`, id 2) makes it explicit:
`"result": {..., "max": {"value": 4.611686018427388e+18, "exact": "4611686018427387903"}, ...,
"proved_bound": {"min": -4.611686018427388e+18, "max": -4.611686018427388e+18,
"max_steps": "i63id is nondecreasing in x, so take x = -4611686018427387904:\n      -4611686018427387904"}}`.

**Why it matters:** the true max is `4611686018427387903` (`2^62-1`). The "proved bound"
claims the max is `-4.611686018427388e+18`, and the `max_steps` proof evaluates the
function at the *minimum* endpoint. The final printed range is still right only
because the sample happens to reach the ends; the proof object is wrong and would
produce an unsound (too-small) range when the extremum is not sampled.

### WRONG-3 — `re`/`im`/`abs`/`arg`/`conj`/`real` of a complex value infer as `complex`
**Severity:** WRONG
**Expected:** _not recorded_
The real part, imaginary part, modulus and argument of a complex number are real
values, but `show` types each of them as `complex`, and `equiv` then refuses real
identities over them. The dedicated `re` *command* gives the real value, showing the
type inference is what is wrong.

**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/math/type_coercion && $ROOT/ucas 03_complex_infer.ucas
```
Exact observed output (`03_complex_infer.out`):
```
> show re(z: complex)
_(z: complex) = re(z)
  -> complex
> show im(z: complex)
_(z: complex) = im(z)
  -> complex
> show abs(z: complex)
_(z: complex) = abs(z)
  -> complex
> show real(z: complex)
_(z: complex) = z
  -> complex
```
and from a direct command (probe):
```
re 3 + 4i
Re(3 + 4i) = 3
  check: equal numerically (3, complex arithmetic)
```
Additionally, `equiv zsq abs2` with `zsq(z:complex)=re(z)^2+im(z)^2` and
`abs2(z:complex)=abs(z)^2` is rejected:
`error: equiv works on real functions; this one is complex (use re, im, modulus or arg ...)`.

**Why it matters:** the inferred `-> complex` notes are wrong for real-valued functions,
and the wrong type propagates through arithmetic (`re(z)^2 + im(z)^2` is typed complex),
blocking proofs of real identities on complex inputs. `real(z: complex)` is even
simplified to `z` and stays `complex`, so the "real" conversion is a no-op on complex.

### WRONG-4 — `domain` and `wrap` contradict each other on `int` overflow at 2^63
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/math/type_coercion && $ROOT/ucas 07_domain_wrap_int.ucas
```
Exact observed output (`07_domain_wrap_int.out`):
```
domain of ovf:
  x: int, 0..10
  no conditions: total on its parameter types
  defined at 1 of 11 points
  defined for: 0
  undefined e.g. at x=1; x=2; x=3; x=4
  over all 11 points of the domain
wrap analysis of ovf:
  no wrapping or rounding operations
  end to end: equals the mathematical (unbounded) result everywhere
  over all 11 points of the domain
range of ovf -> int:
  9223372036854775807..9223372036854775807
  fits in u63
  undefined at 10 points
  over all 11 points of the domain
```
**Why it matters:** `domain` and `range` correctly find that `int` is checked against the
int64 range (only x=0 is defined), yet `domain` simultaneously prints "no conditions:
total on its parameter types" and `wrap` prints "no wrapping ... equals the mathematical
(unbounded) result everywhere". The three analyses disagree about whether overflow at
`2^63-1 + 1` is defined.

### WRONG-5 — mixed signed/unsigned arithmetic silently reinterprets and narrows
**Severity:** WRONG
**Expected:** _not recorded_
The note only says "computed as u8/u32/u64"; it does not warn that the signed operand
is reinterpreted as unsigned and the result wraps. Examples (`01_mixed_infer.out`,
`07_domain_wrap_int.out`):
**Observed:**
**Reproducer:**
```sh
> show u8(1) + i8(-2)
  note: mixing u8 and i8: computed as u8
_() = 255
  -> u8
> show i64(-1) < u64(1)
  note: mixing i64 and u64: computed as u64
_() = 0
  -> bool
wrap analysis of mix8:
  u8(x)   (u8)
      truncates at 32768 points, e.g. x=-128, y=0
  u8(x) + y   (u8)
      nuw fails: unsigned wrap at 32640 points, e.g. x=-1, y=1
      nsw fails: signed wrap at 16384 points, e.g. x=127, y=1
  end to end: differs from the mathematical result at 16384 points, e.g. x=-128, y=0
```
**Why it matters:** `u8(1) + i8(-2)` is mathematically `-1` but is reported as `255`
with only a neutral "computed as u8" note; `i64(-1) < u64(1)` is `false` when the
mathematical comparison is `true`. The reinterpretation is detectable only through
`wrap`, not from the note attached to the expression, so the coercion is silent.

### LIMIT-1 — inline definitions passed to `range`/`wrap` are misparsed
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/math/type_coercion
printf 'wrap u8ovf(x: u8 in 250..255) = x + 10\n' > /tmp/tc_inline.ucas
$ROOT/ucas /tmp/tc_inline.ucas
```
Exact observed output:
```
> wrap u8ovf(x: u8 in 250..255) = x + 10
  note: u8ovf(...) read as multiplication: u8ovf is not a function
  note: '=' inside an expression read as '=='
wrap analysis of u8ovf*real(x >= 250 && x <= 255) == real(x + 10):
  x + 10   (u8)
      nuw fails: unsigned wrap at 1010 points, e.g. u8ovf=-10, x=246
  end to end: differs from the mathematical result at 107 points, e.g. u8ovf=-10, x=246
```
**Why it matters:** it is a limitation: `range F`/`wrap F` accept a name or an *anonymous expression
with inline annotations* (`range isqrt(x: u4)`), but not an inline definition with
`= body`. The parser silently invents a free variable `u8ovf` and a bogus equality,
producing a plausible-looking but meaningless analysis instead of a parse error.
Define the function first (as goldens 05–08 do) to get the correct result.

### LIMIT-2 — free `z`/`w` default differs between CLI and MCP
**Severity:** LIMIT
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
In the CLI, `show re(z)` silently defaults `z` to complex with a note; over MCP the
same expression returns `error (ambiguous)` and requires `args.assume.z="complex"`
(or `defaults:true`). This is by design for the API, but the inconsistency means a
typed/untyped expression that works on the CLI fails over MCP unless `assume` is set.
**Reproducer:**
Repro: compare `03_complex_infer.out` with MCP ids 4/2 of `mcp_type_coercion.out`.

## Checks that passed

_No separate passed checks were recorded in the original document._
