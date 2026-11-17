# Stress findings — `cfront_float_semantics`

_Original heading: cfront_float_semantics — findings_

# cfront_float_semantics — findings

Area: C float/double semantics and aliasing in the C99 frontend (`c lower`, `c
optimize`, MCP tool `c`), plus the float `wrap`/`equiv` analysers the frontend's
fast-math flags lean on.

Binary: `$ROOT/ucas` (built; not rebuilt). All reproducers run
from `$ROOT/tests/stress/areas/systems/cfront_float_semantics` unless stated.
Severity legend: `CRASH` | `HANG` | `WRONG` | `NLP` | `LIMIT` | `DETERMINISM`.

Summary of the sweep: ~410 generated float functions were run through both `c
lower` and `c optimize` under `timeout 15` (24 batches) with **no crash and no
hang**; a second stress set (120-deep expression, 120 functions in one block,
`budget 0`, `timed trace`, hard f64 `equiv`) also all exited 0. Every lowering
reviewed by hand against C semantics (promotions, 2^24/2^53 conversions, literal
rounding, signed zero, inf/NaN, UB conditions) was correct, and every applied
`c optimize` rewrite was one of the five sound ones in `src/cf_opt.c:1330-1411`
(div-by-exact-power-of-two, double-rounding removal, etc.). All 19 golden files
were run twice and were byte-identical. The issues below are two wrong/sampled
claims and several toolchain limits.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | 1 — `wrap` claims `nnan holds` for `x/x` although `x=0` (in-domain) yields `0/0 = NaN` |
| LIMIT | 4 | 1 — `c optimize ... check` cannot make float parameters or results: every float function i… |

## Findings

### WRONG-1 — 1 — `wrap` claims `nnan holds` for `x/x` although `x=0` (in-domain) yields `0/0 = NaN`
**Severity:** WRONG
**Expected:** _not recorded_
what a fast-math rewrite would trust)

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_float_semantics
timeout 30 $ROOT/ucas 18_nnan_sample.ucas
```

**Observed:** output (exact, from `18_nnan_sample.out`):

```
> w(x: f32) = x / x
> wrap w
wrap analysis of w:
  x/x   (f32)
      nnan holds (no NaN from non-NaN inputs)
      ninf holds
  end to end vs the real-number result: max abs error 0, max rel error 0, max 0 ulp (correctly rounded)
  sampled 65536 points (domain has 4278190079 points); not exhaustive
> wk(x: f32) = (x - x)/(x - x)
> wrap wk
...
  (x - x)/(x - x)   (f32)
      nnan fails: NaN at 65536 points, e.g. x=-3.40282347e+38
```

**Why it matters:** the domain of an `f32` parameter is the finite values
(README, "Proofs on floats": *"the finite values in its range, -0 read as +0"*),
so `x = 0` is an input. `0.0f/0.0f` is NaN — proved by the second half of the
same output, where `(x-x)/(x-x)` is `0/0` for every finite `x` and `wrap`
correctly reports `nnan fails: NaN at 65536 points`. Hence `x/x` *does* produce
NaN from a non-NaN, in-domain input, and `nnan holds` is false. The cause is
`src/analyze.c:1269-1295`: `nnan` is decided only from `NSAMPLE = 65536` random
points (`run_next`), and a single-point case like `x = 0` is never sampled
(probability ~65536/4.28e9). The line states the claim as fact with no
"sampled" caveat (the caveat appears later, on the end-to-end line). A consumer
using `nnan` to justify `x == x` / no-NaN fast-math rewrites could be misled.
(Note: this is the `wrap` analyser, not `c optimize`; cfront itself does **not**
apply any no-NaN rewrite — see `07_fastmath_sensitive.out`.)

### WRONG-2 — 2 — C frontend drops the `defined where (no C UB)` condition for a *constant* out-of-range float→int conversion
**Severity:** WRONG
function's body is wholly UB, but a real inconsistency with the variable case)

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_float_semantics
timeout 30 $ROOT/ucas 04_const_ub.ucas
# and the MCP form, where the missing field is explicit:
timeout 30 $ROOT/ucas --mcp < 15_const_ub_mcp.jsonl
```

**Observed:** output (exact, from `15_const_ub_mcp.out`, id 1 `structuredContent`):

```json
"functions": [
  {"function": "a", "value": "i32(1e+30)"},
  {"function": "d", "value": "i32(x)",
   "where": "f64(x) > -2147483649 && f64(x) < 2147483648"}
]
```

and from `04_const_ub.out`:

```
  a_const_huge() = i32(1e+30)
  c_negone() = u32(-1)
  d_var(a: f32) = i32(a)
    defined where (no C UB): f64(a) > -2147483649 && f64(a) < 2147483648
  j_big() = u32(4294967296)
```

**Why it matters:** C99 6.3.1.4 makes `(int)1e30`, `(unsigned)(-1.0)` and
`(unsigned)4294967296.0` undefined (integral part out of range); `float→int`
with a runtime operand correctly gets a UB condition (`d_var`, and the MCP
`where` field for `d`). When the operand folds to a constant, `add_cond`
(`src/cf_lower.c:235-243`) builds `!g || ok` with `ok` constant-false, giving a
constant-false `L.where` that is omitted from both the text and the JSON
`where` field. The same happens for constant signed overflow
(`int f(void){return 2147483647+1;}` prints no condition, while the variable
form does). A consumer of the MCP `functions[].where` field sees `a` as a total
function when it is UB everywhere.
**Expected:** an explicit empty-domain /
constant-false condition, as for the variable case.

### LIMIT-1 — 1 — `c optimize ... check` cannot make float parameters or results: every float function is "not tested"
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer / observed output (`19_check_float.ucas` + `.out`):

**Observed:**
```
> c optimize nofile check budget 3
...
  check: fadd not tested (a parameter or result the harness cannot make)
  check: fdiv not tested (a parameter or result the harness cannot make)
  check: dmad not tested (a parameter or result the harness cannot make)
  check: the original does not compile:
cc: error: unrecognized command-line option '-fsanitize-minimal-runtime'
```

With a `cc`→clang shim (`mkdir -p /tmp/shim; printf '#!/bin/sh\nexec /usr/bin/clang "$@"\n'
> /tmp/shim/cc; chmod +x /tmp/shim/cc; PATH=/tmp/shim:$PATH ...`) the compile
error goes away and the last line becomes
`check: compiled both with cc -O2 -march=x86-64-v3; 0 calls of 0 functions agree (edge and random inputs)`
— i.e. still **zero** float functions tested.

**Why it matters:** the end-to-end differential checker (the obvious way to
validate a rewrite) silently skips *all* float-valued functions, so even a
working compiler gives "0 calls of 0 functions agree". Float rewrites therefore
rely solely on the derivation in `gen_float` (`src/cf_opt.c`) and on `equiv`'s
finite-only domain (LIMIT-2), with no C-vs-output random check. The default
host `cc` being GCC with clang-only sanitizer flags passed is the same problem
already recorded in the sibling area `cfront_fuzz` LIMIT-1.

### LIMIT-2 — 2 — float **parameters** of ucas (hence cfront proofs) exclude infinity and NaN, and read `-0` as `+0`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
rewrite)

**Evidence / reproducer:**

**Observed:**
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/cfront_float_semantics
timeout 30 $ROOT/ucas 16_wrap_float.ucas | head -12
```

README "Proofs on floats" (lines 299-302): *"Two values are equal as `equiv`
compares them: both NaN, or `==` (so -0 and +0 are one value...). A parameter's
domain is the evaluator's: the finite values in its range, -0 read as +0; a
`u32` read by `asfloat` covers every bit pattern."* The domain count printed by
`wrap` for two `f32` params is 18302910352054026241 ≈ (2^32 − 2^24)^2, i.e.
finite values only. Consequently `equiv z1 e2 nanbits` reports `a+0.0f == a`
(`17_nanbits.out`) although in C `-0.0f + 0.0f = +0.0f`; cfront correctly does
**not** exploit that equality (no rewrite for `f_add_zero`), but the proof
engine's notion of equality is weaker than bit/C equality for signed zero.

### LIMIT-3 — 3 — pointer/union type punning, `volatile`, aggregates and math.h calls are not lowered
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Reproducers / observed output:**

* `09_punning.out`: every pointer cast (`*(int*)&f`), union punning (`U u; u.f=f;
  return u.i;`) and `memcpy` bit copy gives
  `not lowered: ... the address of a parameter is taken` or
  `not lowered: ... a local of a non-integer type or whose address is taken (u)`.
* `10_volatile_restrict.out`: `volatile int*` params / globals give
  `not lowered: ... a volatile variable`; `restrict` arrays lower only to loop
  IR, not a function value.
* `05_fma_contract.out`: `fma`/`fmaf`/`sqrtf` calls give
  `not lowered: line N: a call of fma (not defined in this file)` even with
  `#include <math.h>`; `a*b+c` stays two operations (`#pragma STDC FP_CONTRACT
  OFF` is emitted in `c optimize` output). So there is no fused-multiply-add
  rewrite, which is the conservative/correct choice for strict C semantics.

**Why it matters:** these constructs are therefore outside the frontend's
proof model; no unsound rewrite is applied to them because none is attempted.

### LIMIT-4 — 4 — MCP `c` tool has no `c_check`, and `c_lower`/`c_optimize` reject the `nofile` argument
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer / observed output (`14_mcp_float.jsonl` was written without
`nofile`; adding it gives):**

**Observed:**
```json
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"error (bad_request): c_lower has no argument \"nofile\""}],
 "structuredContent":{"id":1,"ok":false,"cmd":"c_lower","error":{"code":"bad_request","message":"c_lower has no argument \"nofile\""}},"isError":true}}
```

The CLI `nofile` option has no MCP equivalent; float `c_lower`/`c_optimize` over
MCP work correctly otherwise (see `14_mcp_float.out`).

## Checks that passed

### Positive results (no finding)
Every lowering in `01_promotion.out`, `02_literals.out`, `03_conv_boundary.out`,
`06_special.out`, and `13_compound.out` matched hand-written C/IEEE-754
semantics, including: float-vs-double promotion and usual conversions, 2^24 and
2^53 rounding, subnormal/min/max literals, inf/NaN constants, signed zero,
compound assignment, `?:` conversions, and all float→int UB bounds. `08_opt_divpow2.out`
shows the only applied rewrite (`x/2^k → x*2^-k`) is correctly *not* applied
when the reciprocal would underflow or the divisor is infinite/subnormal. Fuzz
(and explicit stress) found no crash, hang, or wrong applied rewrite.
