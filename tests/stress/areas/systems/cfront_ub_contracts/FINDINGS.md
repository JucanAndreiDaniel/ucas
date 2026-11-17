# Stress findings — `cfront_ub_contracts`

_Original heading: Findings — `cfront_ub_contracts`_

# Findings — `cfront_ub_contracts`

Area: C frontend UB domain conditions and `assume` / `wrapv` contracts.
Binary: `$ROOT/ucas` (already built). All runs bounded with `timeout`.
172 distinct C function snippets were tried via `c lower` / `c optimize` (CLI and MCP).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | `assume` lower bound of `INT64_MIN` (or below) SIGSEGVs `c optimize` |
| HANG | 1 | same `INT64_MIN` lower bound with an `int`-sized upper bound |
| WRONG | 3 | reversed `assume` bounds produce an empty domain yet still emit an incorrect rewrite |
| LIMIT | 2 | sequence-point (unsequenced read/write) UB is silently resolved to one order |

## Findings

### CRASH-1 — `assume` lower bound of `INT64_MIN` (or below) SIGSEGVs `c optimize`
**Severity:** CRASH
**Reproducer:**
Reproducer** (durable file `repro_crash_int64min.ucas`):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_ub_contracts
timeout 15 $ROOT/ucas repro_crash_int64min.ucas
```

Equivalent one-liner source:

````
c optimize nofile budget 3 assume x -9223372036854775808 0
```c
int f(int x){return x+1;}
```
````

**Observed:** output** (exit 139, SIGSEGV, core dumped):

```
> c optimize nofile budget 3 assume x -9223372036854775808 0
timeout: the monitored command dumped core
Segmentation fault
```

**Threshold probing** (same body, varying only the lower bound):

```
rc=0  for assume x -9223372036854775807 0     (INT64_MIN+1)
rc=139 for assume x -9223372036854775808 0    (INT64_MIN)
rc=139 for assume x -9223372036854775809 0
rc=139 for assume x -99999999999999999999 0
rc=0  for assume x -9000000000000000000 0
rc=0  for assume x 0 99999999999999999999     (huge positive bound is fine)
```

**Why it matters:** the CLI forbids nothing here; `-9223372036854775808` is a legal
64-bit value, and the neighbouring `-9223372036854775807` works. A segfault at exactly
`INT64_MIN` is the classic signature of an unguarded negation (`-lo`) or a
`range = hi - lo` that overflows when computing the assumed interval.
**Expected:**
accept the bound, clamp it to the parameter type, or emit a clean parse/domain error —
never crash. `c lower` with the same assume does **not** crash (it ignores the assume),
so the defect is in the `c optimize` domain/assume path.

### HANG-1 — same `INT64_MIN` lower bound with an `int`-sized upper bound
**Severity:** HANG
**Reproducer:**
Reproducer** (durable file `repro_hang_int64min.ucas`):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_ub_contracts
timeout 10 $ROOT/ucas repro_hang_int64min.ucas
```

````
c optimize nofile budget 3 assume x -9223372036854775808 2147483647
```c
int f(int x){return x+1;}
```
````

**Observed:** output:** only the echoed command line, no result, killed by `timeout`
after 10 s (also confirmed with a 35 s timeout: rc=124). `budget 3` does not bound it.

```
> c optimize nofile budget 3 assume x -9223372036854775808 2147483647
```
(then nothing until timeout)

**Why it matters:** the same malformed lower bound takes a different broken path than
finding 1 — with an ordinary `int` upper bound it appears to try to enumerate an
enormous (unclamped) interval. A `budget` of 3 CPU seconds is ignored.
**Expected:**
terminate promptly (clamp the assumed range to the parameter's `int` type, or reject).

### WRONG-1 — reversed `assume` bounds produce an empty domain yet still emit an incorrect rewrite
**Severity:** WRONG
**Reproducer:**
Reproducer** (golden `11_assume_empty.ucas` / `11_assume_empty.out`, deterministic):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_ub_contracts
timeout 15 $ROOT/ucas 11_assume_empty.ucas
```

**Observed:** output:

```
> c optimize nofile budget 5 assume x 100 0
<input>: error: the function is undefined on its whole domain
c optimize: 1 function, 1 rewrite proved (1 exhaustive, 0 by SAT) for x86-64-v3
  estimated cost of the rewritten values on x86-64-v3: 1.0 -> 0.0 cycles
  f (line 1): the value is x
    proof: exhaustive (exhaustive: 0 inputs); cost 1.0 -> 0.0
    over: x in [100, 0] (assumed)
    before: {return x+1;}
optimised C:
  /* optimised by ucas cfront for x86-64-v3 (x86-64-v3); every rewrite proved, see the report */
  #include <stdint.h>
  int f(int x){
  	return (int)(x);
  }
```

**Why it matters:** the tool itself prints `error: the function is undefined on its
whole domain`, then goes on to "prove" a rewrite over **0 inputs** and rewrites the
emitted C from `return x+1;` to `return x;`. A vacuous proof over an empty domain must
not license an unconditional rewrite: the rewritten function is wrong for every real
input (e.g. `f(5)` changes from 6 to 5).
**Expected:** reject `LO > HI`, or leave the
function body untouched when the domain is empty.

### WRONG-2 — division and remainder by zero are not reported as C UB domain conditions
**Severity:** WRONG
_Original classification: `WRONG / LIMIT`._
The README's C-frontend pipeline states that "division by zero, `INT_MIN / -1`, oversized
shifts ... as a domain condition (C UB)" are tracked. `c lower` disagrees for division
by zero.

**Reproducer:**
Reproducer** (golden `04_divzero.ucas` / `04_divzero.out`):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_ub_contracts
timeout 15 $ROOT/ucas 04_divzero.ucas
```

**Observed:** output** (excerpt):

```
  div0(x: i32) = x/0
  mod0(x: i32) = x % 0
  divvar(x: i32, y: i32) = x/y
    defined where (no C UB): !(x == -2147483648 && y == -1)
  modvar(x: i32, y: i32) = x % y
    defined where (no C UB): !(x == -2147483648 && y == -1)
  div0u(x: u32) = x/0
  mod0u(x: u32) = x % 0
  divexpr(x: i32) = x/0
  divassign(x: i32) = x/0
```

**Why it matters:** `x/0`, `x%0`, `x/(1-1)` and `x/=0` have **no** `defined where`
clause at all; `x/y` and `x%y` carry only the `INT_MIN / -1` condition and omit
`y != 0`. In C99 both are undefined for a zero divisor (6.5.5p5). The domain condition
is therefore incomplete: the tool claims the function is defined where it is not.
It also means `assume`-based narrowing and `check`'s UBSan skip cannot reason about
zero divisors.
**Expected:** `div0` is undefined on its whole domain, and `divvar` includes
`y != 0`.

### WRONG-3 — oversized and negative shift counts are not reported as C UB
**Severity:** WRONG
_Original classification: `WRONG / LIMIT`._
**Expected:** _not recorded_
Also promised by the README as a domain condition; entirely absent in `c lower`.

**Reproducer:**
Reproducer** (golden `03_shift_ub.ucas` / `03_shift_ub.out`):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_ub_contracts
timeout 15 $ROOT/ucas 03_shift_ub.ucas
```

**Observed:** output** (excerpt):

```
> c lower nofile
  shl32(x: i32) = x << 32
  shl40(x: i32) = x << 40
  shlneg(x: i32) = x << -1
  shr32(x: i32) = x >> 0x20
  shr33(x: i32) = x >> 0x21
  shrneg(x: i32) = x >> -1
  shlvar(x: i32, n: i32) = x << n
  shrvar(x: i32, n: i32) = x >> n
  shluvar(x: u32, n: u32) = x << n
```

**Why it matters:** none of the constant shifts by 32/40/-1/0x20/-1, nor the variable
shifts, has a `defined where` clause. C99 6.5.7p3 makes a shift by a count >= the width
or < 0 undefined; the shift result must have a domain condition on the count. Note the
inconsistent constant rendering: `x << 32` keeps decimal `32`, while `x >> 32` becomes
`x >> 0x20` and `x >> 33` becomes `x >> 0x21`, and `x << -1` is printed verbatim.
The lowered value `x << 32` (no condition) is not a faithful C99 lowering. Expected a
condition such as `0 <= n < 32`, and constant oversized shifts flagged as UB.

### LIMIT-1 — sequence-point (unsequenced read/write) UB is silently resolved to one order
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (golden `07_seq_uninit.ucas` / `07_seq_uninit.out`):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_ub_contracts
timeout 15 $ROOT/ucas 07_seq_uninit.ucas
```

**Observed:** output** (excerpt):

```
  seq1(x: i32) = x
    defined where (no C UB): i64(x) >= -2147483648 && i64(x) <= 2147483647
  seq2(x: i32) = x + 1
    defined where (no C UB): t1 >= -2147483648 && t1 <= 2147483647 where t1 = i64(x) + 1
  seq3(x: i32) = x + 1
  seq4(x: i32) = x + 2
```

**Why it matters:** it is a limit:** `i = i++`, `i = ++i + i++` and `i++ + i++` are unsequenced
modifications/reads (C99 6.5p2, UB), but the frontend silently picks one evaluation
order and emits a defined value with no UB condition. The only conditions shown are
the incidental signed-overflow checks on the arithmetic involving `x`. A tool whose
purpose is to expose C UB as domain conditions should at least flag these; instead it
lowers them as if a particular order were mandated. Documented as LIMIT rather than
WRONG because no proof is claimed over the UB inputs.

### LIMIT-2 — constant out-of-range float-to-int conversions get no domain condition
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (golden `06_f2i.ucas` / `06_f2i.out`):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_ub_contracts
timeout 15 $ROOT/ucas 06_f2i.ucas
```

**Observed:** output** (excerpt):

```
  f2id(d: f64) = i32(d)
    defined where (no C UB): d > -2147483649 && d < 2147483648
  ...
  f2ibig() = i32(1e+20)
  f2ismall() = i32(-1e+20)
  f2if32big() = i32(inf)
```

**Why it matters:** it is a limit:** variable conversions get the correct range condition, but constant
`(int)1e20`, `(int)-1e20` and `(int)3.5e38f` are lowered with **no** condition, even
though each is out of range and UB in C99 6.3.1.4p1. Inconsistent with the adjacent
variable cases. (The `f2inan`/`f2iinf` cases do get a condition that is false, which is
correct.)

## Checks that passed

### Things that behaved correctly (recorded as goldens, no issue)
- Signed overflow: `add/sub/mul/neg/++/--` and narrowing all produce a proper
  `t1 >= INT_MIN && t1 <= INT_MAX` (or 64-bit xor-mask) condition — `01_signed_overflow.out`.
- Unsigned wrap: `u32` arithmetic has no condition, as expected — `02_unsigned_wrap.out`.
- `INT_MIN / -1`: correctly `x != -2147483648` / `!(x == INT_MIN && y == -1)` — `05_div_intmin.out`.
- `assume` narrowing on `c optimize`: `absv` with `x in [0,100]` becomes `x`, `div7`
  with `x in [0,1000]` gets `(x*1171)>>13`, each tagged `over: ... (assumed)` with an
  exhaustive proof on the assumed domain — `10_assume_narrow.out`. Checked the magic
  rewrite is right at the boundary (e.g. `x=1000`) and that without the assume no rewrite
  is emitted (`13_ub_no_rewrite.out`).
- `wrapv` removes only signed-overflow conditions; it leaves the float-to-int condition
  intact and does not change unsigned arithmetic — `09_wrapv.out`, `12_assume_wrapv.out`.
- Pointer/OOB/aliasing functions are cleanly refused with `not lowered: ... a parameter
  that is not an integer or a float` rather than silently miscompiled — `08_memory.out`.
- MCP `c` tool (`mcp_c_ub.jsonl`): `c_lower` / `c_optimize` / `c_targets` responses deterministic;
  note `c_lower` does **not** accept a MCP `nofile` argument (returns `bad_request`),
  unlike the CLI keyword — documented, not a bug.
