# Stress findings — `cfront_fuzz`

_Original heading: cfront_fuzz — findings_

# cfront_fuzz — findings

Area: C99 frontend (`c optimize`, `c lower`, `c targets`, MCP tool `c`).
Binary: `$ROOT/ucas` (not rebuilt). All commands run from
`$ROOT/tests/stress/areas/systems/cfront_fuzz` unless stated otherwise.

Severity legend: `CRASH` | `HANG` | `WRONG` | `NLP` | `LIMIT` | `DETERMINISM`.

No `CRASH` and no soundness-`WRONG` rewrite was found: 253 additional exploratory
snippets and 140 catalog functions all exited 0, and every rewrite that `check`
could exercise (with a clang `cc` shim, see LIMIT-3) agreed with the original
(0 mismatches over ~700k calls). The issues below are hangs, one nondeterminism
case and frontend/toolchain limits.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 2 | 1 — `c lower` spins forever on a loop containing `break` with an input-dependent bound |
| LIMIT | 5 | 1 — `c optimize ... check` cannot compile with the host `cc` |
| DETERMINISM | 1 | 1 — `c optimize ... bench` output changes every run |

## Findings

### HANG-1 — 1 — `c lower` spins forever on a loop containing `break` with an input-dependent bound
**Severity:** HANG
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_fuzz
timeout 12 $ROOT/ucas hang_break_loop.ucas; echo "rc=$?"
```

`hang_break_loop.ucas`:

```c
c lower nofile
```c
int sumbreak(int n){int s=0;for(int i=0;i<n;i++){if(i>10)break;s+=i;}return s;}
```
```

**Observed:** output (exact, after 12 s):

```
> c lower nofile
rc=124
```

17 bytes of output, then no progress until killed. Confirmed at 4 s, 12 s and
20 s. Variants that also hang: `if(i==5)break;`, `while` + `break`,
`break` after the accumulation. A constant-bound version
(`for(int i=0;i<100;i++){if(i==5)break;...}`) returns instantly with
`f() = 10`, so the trigger is a `break` in a loop whose trip count is not a
compile-time constant. A nearby variant with a `goto` label returns with
`loop (line 1): no IR: line 1: goto` instead. `c optimize` on the same function
does **not** hang — see `26_break_loop_opt.ucas` (it says "kept the loop: the
cheapest proved form is the loop unrolled (749 operations)"), so the hang is in
the `c lower` loop-summarisation path only.

**Expected:** either a closed form, or the normal `not lowered` diagnostic with
the loop IR, as for the `continue` loops in `07_loops_continue.out`.

### HANG-2 — 2 — nested loop whose accumulator is updated with `s++` hangs both `c lower` and `c optimize`
**Severity:** HANG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_fuzz
timeout 12 $ROOT/ucas hang_nested_inc.ucas;        echo "rc=$?"
timeout 12 $ROOT/ucas hang_nested_inc_opt.ucas;    echo "rc=$?"
```

`hang_nested_inc.ucas` (the `_opt` file uses `c optimize nofile budget 3`):

```c
c lower nofile
```c
int tri(int n){int s=0;for(int i=0;i<n;i++)for(int j=0;j<i;j++)s++;return s;}
```
```

**Observed:** output (exact, after 12 s):

```
> c lower nofile
rc=124
> c optimize nofile budget 3
rc=124
```

**Why it matters:** the semantically identical `s+=1;` terminates immediately
with `not lowered: a loop that may run more than 66 times` plus the IR; so does
`for(int j=0;j<n;j++)s+=i+j;`. The hang is specific to post-increment `s++`
inside the inner loop (also `s+=++j;` and a `while` spelling). A single loop
with `s++` is fine. This is a genuine non-termination in the induction/IR pass,
not an expensive proof (no progress at 20 s either). There is deliberately **no**
`.out` golden for these two files.

### DETERMINISM-1 — 1 — `c optimize ... bench` output changes every run
**Severity:** DETERMINISM
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd /tmp
cat > bench_det.ucas <<'EOF'
c optimize nofile bench budget 3
```c
int add(int a,int b){return a+b;}
int pop(unsigned x){int c=0;while(x){c+=x&1;x>>=1;}return c;}
```
EOF
timeout 45 $ROOT/ucas bench_det.ucas
# run again and diff
```

**Observed:** output (two consecutive runs):

```
  bench add: 6.49 -> 6.29 cycles per call (rdtsc, median of 15, 3 runs: x1.11 x1.13 x1.03)
  bench pop: 81.38 -> 73.20 cycles per call (rdtsc, median of 15, 3 runs: x1.02 x1.11 x1.12)
```
```
  bench add: 7.69 -> 6.48 cycles per call (rdtsc, median of 15, 3 runs: x1.19 x1.10 x1.18)
  bench pop: 80.96 -> 75.86 cycles per call (rdtsc, median of 15, 3 runs: x1.11 x1.09 x0.96)
```

One run even produced `check: the harness does not build: ... unable to open
output file '/tmp/ucas-cfront-ANoABO/h.o': 'No space left on device'`, so the
same input can fail *qualitatively* differently depending on host state.
**Expected:** rdtsc numbers are inherently unstable; per the suite rules this case is
documented here and **no golden `.out` was kept**. All non-`bench` commands in
this folder were run twice and were byte-identical.

### LIMIT-1 — 1 — `c optimize ... check` cannot compile with the host `cc`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer / observed output:** `27_check_default_cc.ucas` +
`27_check_default_cc.out`:

**Observed:**
```
> c optimize nofile check budget 2
c optimize: 1 function, 0 rewrites proved (0 exhaustive, 0 by SAT) for x86-64-v3
  f (line 1): no cheaper form: lowered: 1 inputs, cost 1.0
  check: the original does not compile:
cc: error: unrecognized command-line option ‘-fsanitize-minimal-runtime’
```

**Why it matters:** the differential checker (the obvious way to validate a
rewrite) is unusable with the default compiler on this host. `src/cf_check.c:643`
passes clang-only flags (`-fsanitize=signed-integer-overflow,shift,
integer-divide-by-zero -fsanitize-minimal-runtime`) to a hardcoded `cc`, which
here is GCC. Setting `UCAS_CC=clang` does **not** help:

```sh
UCAS_CC=clang timeout 25 $ROOT/ucas 27_check_default_cc.ucas | grep -A1 'check:'
#   check: the original does not compile:
# cc: error: unrecognized command-line option '-fsanitize-minimal-runtime'
```

A working differential run needs a `cc` shim that execs clang on `PATH`:

```sh
mkdir -p /tmp/shim && printf '#!/bin/sh\nexec /usr/bin/clang "$@"\n' > /tmp/shim/cc && chmod +x /tmp/shim/cc
PATH=/tmp/shim:$PATH timeout 60 $ROOT/ucas <file>.ucas
#   check: compiled both with cc -O2 -march=x86-64-v3; ... calls ... agree (edge and random inputs)
```

With that shim I checked 10 arithmetic functions, 10 loop/peephole functions
and 28 peephole functions; all calls agreed and ~70k UB inputs were skipped by
UBSan. No wrong rewrite was observed.

### LIMIT-2 — 2 — the MCP `c` tool exposes only three ops; there is no `c_check`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer:** `timeout 30 $ROOT/ucas --mcp < mcp_c_errors.jsonl`
(golden `mcp_c_errors.out`). Calls 1 and 2 ask for `c_check` and `c_bogus`.

**Observed:** output (exact lines):

```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "c needs \"op\", one of: c_optimize c_lower c_targets"}}
{"jsonrpc": "2.0", "id": 2, "error": {"code": -32602, "message": "c needs \"op\", one of: c_optimize c_lower c_targets"}}
```

The error is graceful, but the expected MCP `c_check` op
does not match the registered tool (`c_optimize`, `c_lower`, `c_targets`).

### LIMIT-3 — 3 — aggregates, pointer/volatile parameters and `math.h` calls are not lowered
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Why it matters:** _not recorded_
**Reproducers / observed output:**

* `12_aggregates.out`: local `struct`, `union` and bitfield variables all give
  `not lowered: line N: a local of a non-integer type or whose address is taken (x)`.
* `13_volatile.out`: `volatile int *` params give `not lowered: ... a parameter
  that is not an integer or a float (p)`; a `volatile` global gives
  `not lowered: ... a volatile variable`; a loop reading `*p` also reports
  `no IR: line 3: a volatile access`.
* `24_bitfields.out`: three bitfield functions, zero rewrites, same diagnostic.
* `17_math_calls.out`: `sqrt`, `fabs`, `floor`, `fmin` all give
  `not lowered: line N: a call of sqrt (not defined in this file)` etc., so no
  math rewrite is ever attempted even with `#include <math.h>`.

**Expected:** /impact:** these are documented frontend restrictions rather than
crashes; enum-like inputs can still be handled via the vectoriser (see
`10_pointer_arith.out`, where loops over `int *` are proposed and proved lane by
lane), but the scalar value model does not cover them. Useful to know before
asserting equality on such snippets.

### LIMIT-4 — 4 — malformed C is silently accepted: duplicate parameter name
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer / observed output:** `19_invalid_c.out`, last block:

**Observed:**
```
> c lower nofile
  f(x: i32, x: i32) = x
```

Input was `int f(int x,int x){return x;}`, which is a constraint violation in
C99 (a parameter may not be redeclared in the same function definition). The
frontend accepts it and lowers it to a two-parameter ucas value with both
parameters named `x`. By contrast other malformed inputs in the same file are
correctly rejected (`expected ';' before '}'`, `expected a declaration`,
`'undeclared_thing' is not declared`). Note also that an unknown `#include` is
silently ignored and the rest of the block still lowers (`h() = 0`).

### LIMIT-5 — 5 — the "defined where (no C UB)" line is only the *extra* C condition
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducers:** `02_division.out`, `03_shifts.out`.

**Observed:**
**Reproducer:**
```sh
  divz(a: i32, b: i32) = a/b
    defined where (no C UB): !(a == -2147483648 && b == -1)
  shl(a: i32, n: i32) = a << n
  shl_const(a: i32) = a << 32
```

No `b != 0` / `0 <= n < 32` appears on that line. This is **not** an unsoundness:
those conditions belong to the domain of the `/` and `<<` operators in the
value itself. The generic analyser shows them when asked:

```
> domain ((a: i32) / (b: i32))
  requires b != 0  (in a/b)
  C assumes not (a == min and b == -1)  (in a/b)
> domain ((a: i32) << (n: i32))
  requires 0 <= n < 32  (shift amount; C UB otherwise)
  C assumes a << n does not overflow  (signed shift)
```

Recorded because the label reads like a complete domain and could mislead a
consumer of the MCP `result.functions[].where` field (e.g. `mcp_c_lower.out`).
`wrapv` correctly suppresses the C-specific part entirely, as shown in
`20_wrapv.out`.

## Checks that passed

_No separate passed checks were recorded in the original document._
