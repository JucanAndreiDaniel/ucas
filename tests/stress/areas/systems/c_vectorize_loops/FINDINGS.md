# Stress findings — `c_vectorize_loops`

_Original heading: FINDINGS — `c_vectorize_loops` stress area_

# FINDINGS — `c_vectorize_loops` stress area

Area: the C frontend's loop/vectorisation paths (`c lower`, `c optimize`, `vectorize`,
targets, `assume`, `check`, `bench`, `wrapv`), via CLI `.ucas` files and the MCP `c`
tool.  All commands below are copy-pasteable from this directory.

Binary: `$ROOT/ucas` (host `cc` is GCC 16; `clang` 23 is also installed).
The `check` harness uses a clang-only flag, so where differential checking was wanted
the runs used `PATH=/tmp/opencode/ccwrap:$PATH` (a `cc -> clang` symlink) — see F4.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | SIGFPE in `c optimize` on a signed-64-bit element-wise array loop |
| HANG | 1 | `check` differential harness on a nested loop with an unbounded inner trip count |
| WRONG | 1 | `assume` produces an unchecked out-of-range table read, and `check` ignores the assumption |
| LIMIT | 4 | `check` harness hard-codes a clang-only compiler flag |
| DETERMINISM | 1 | early `return` inside a loop reports a varying unrolled-operation count |

## Findings

### CRASH-1 — SIGFPE in `c optimize` on a signed-64-bit element-wise array loop
**Severity:** CRASH
**Why it matters:** _not recorded_
The default `c optimize` engine set divides by zero in the `find` engine while trying
to rewrite an element-wise loop over `long long` / `long` arrays.  Adding `vectorize`,
`vecstub`, or restricting engines to anything except `find` avoids it; `c lower` is fine.

**Reproducer:**
Reproducer (CLI):

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
printf 'c optimize nofile\n```c\nvoid f(int n,long long*d,const long long*s){for(int i=0;i<n;i++)d[i]=s[i]+1;}\n```\n' > /tmp/crash.ucas
timeout 15 $ROOT/ucas /tmp/crash.ucas; echo "exit=$?"
```

**Observed:**

```
> c optimize nofile
Floating point exception (core dumped)
exit=136
```

(exit 136 = 128 + SIGFPE).  The same crash occurs with `c optimize nofile engines find`
(the crashing engine is `find`; `engines none`, `gates`, `alg`, `ring`, `dio`, `gf2`,
`loops`, `bound`, `synth` all exit 0).  It also happens with `+`, `-`, plain copy
(`d[i]=s[i]`), and `+c`, but **not** with `s[i]*2`, not for `unsigned long long`, and
not for `int`/`short` arrays — a signed-64-bit load/store element-wise loop is the trigger.
`wrapv` does not avoid it.

**Reproducer:**
Reproducer (MCP — a single call terminates the whole server, exit 136):

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_optimize","args":{"code":"void f(int n,long long*d,const long long*s){for(int i=0;i<n;i++)d[i]=s[i]+1;}","nofile":true}}}}' \
 | timeout 30 $ROOT/ucas --mcp
```

**Expected:** a normal "0 rewrites proved" report, or a graceful "not vectorised" note —
never a divide-by-zero.  No golden `.out` is kept for this (crash).

### HANG-1 — `check` differential harness on a nested loop with an unbounded inner trip count
**Severity:** HANG
**Why it matters:** _not recorded_
When the second integer parameter of a nested-loop function is an inner trip count,
`check` generates random values for it from a full 64-bit edge list (up to 2^31-1), so
the reference C loop runs billions of iterations and the harness never finishes.
The first integer parameter is clamped to `0..64`, but later ones are not.

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
printf 'c optimize nofile budget 5 vectorize check\n```c\nint nest2(int n,int m){int s=0;for(int i=0;i<n;i++)for(int j=0;j<m;j++)s+=1;return s;}\n```\n' > /tmp/nest.ucas
PATH=/tmp/opencode/ccwrap:$PATH timeout 20 $ROOT/ucas /tmp/nest.ucas; echo "exit=$?"
```

**Observed:** no output after the echoed command line; `exit=124` (timeout).  Repeats
deterministically.  The generated harness (`/tmp/ucas-cfront-*/h.c`) contains
`int a1 = (int)pick(...)` with `pick()` returning e.g. `2147483647`, used as the
inner loop bound.

**Expected:** the input generator should clamp every loop-bound parameter, or cap total
work in the harness.

### WRONG-1 — `assume` produces an unchecked out-of-range table read, and `check` ignores the assumption
**Severity:** WRONG
_Original classification: `WRONG (code generated outside the stated domain is arbitrary`._
**Why it matters:** _not recorded_
`c optimize ... assume n 0 10` lowers the closed form to a 11-entry lookup table with
**no bounds check**: `return cf_tab0[(int)n];`.  For any `n` outside `0..10` this is an
out-of-bounds read (real C UB in the "optimised" output).  That is inherent to an
unchecked range assumption, but the `check` option does not restrict its test inputs
to the assumed range: it then reports thousands of spurious mismatches and fails the
check.  Combining `assume` and `check` is therefore unusable.

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
printf 'c optimize nofile budget 5 check assume n 0 10\n```c\nint f(int n){int s=0;for(int i=0;i<n;i++)s+=i;return s;}\n```\n' > /tmp/am.ucas
PATH=/tmp/opencode/ccwrap:$PATH timeout 40 $ROOT/ucas /tmp/am.ucas 2>&1 | grep -A5 'DIFFERENCES'
```

**Observed:** (excerpt):

```
  check: DIFFERENCES between the original and the output:
MISMATCH f: a0=11 orig=55 opt=990059265
MISMATCH f: a0=12 orig=66 opt=168
MISMATCH f: a0=13 orig=78 opt=20
TEST f 16620 0
```

and the emitted code:

```c
static const int32_t cf_tab0[11] = { 0, 0, 1, 3, 6, 10, 15, 21, 28, 36, 45, };
int f(int n){ return (int)cf_tab0[((int64_t)((n)))]; }
```

**Expected:** either a runtime guard/bounds clamp when the domain is restricted, or
`check` should generate inputs only within the assumed range and say so.  (Note:
golden `03_induction_assume.out` shows that `c lower` silently *ignores* `assume`
altogether — see F5.)

### LIMIT-1 — `check` harness hard-codes a clang-only compiler flag
**Severity:** LIMIT
**Why it matters:** _not recorded_
`check` invokes `cc -fsanitize=signed-integer-overflow,shift,integer-divide-by-zero
-fsanitize-minimal-runtime ...`.  `-fsanitize-minimal-runtime` is a clang option; the
host `cc` is GCC, so with the default environment the differential test never runs.

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
printf 'c optimize nofile check\n```c\nint f(int x){return x+1;}\n```\n' > /tmp/chk.ucas
timeout 20 $ROOT/ucas /tmp/chk.ucas 2>&1 | grep 'check:'
```

**Observed:**

```
  check: the original does not compile:
cc: error: unrecognized command-line option '-fsanitize-minimal-runtime'
```

**Expected:** detect a non-clang `cc` and either drop the clang-only flag or report that
the differential check needs clang.  Workaround used here:
`PATH=/tmp/opencode/ccwrap:$PATH` (symlink `cc -> /usr/bin/clang`); with it, check
passes, e.g. "20000 calls of 1 functions agree (edge and random inputs)".

### LIMIT-2 — `c lower` silently ignores `assume`
**Severity:** LIMIT
**Why it matters:** _not recorded_
`assume NAME LO HI` is parsed by both `c lower` and `c optimize`, but `c lower` never
uses it: the lowered value is the generic closed form, unlike `c optimize`, which
specialises to a table over the assumed range (see F3).

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
timeout 15 $ROOT/ucas 03_induction_assume.ucas
```

**Observed:** (golden `03_induction_assume.out`):

```
> c lower nofile assume n 0 8
  f(n: i32) = i32(t1 & 1 == 0 ? (t1 >> 1)*(t1 - 1) : t1*(t1 - 1 >> 1)) where t1 = n > 0 ? u64(i64(n)) : 0
```

**Expected:** either apply the assumption or warn that it is ignored by `c lower`.

### LIMIT-3 — API quirk: MCP `c_lower` rejects `nofile`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The MCP `c` tool accepts `nofile` for `c_optimize` but rejects it for `c_lower`, even
though the CLI `c lower` accepts `nofile` (the CLI `c lower` help lists it and it is
harmless).  A client that sets `nofile` uniformly gets a bad_request.

**Reproducer:**
Reproducer (part of golden `mcp_c.jsonl` variant):

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_lower","args":{"code":"int sum(int n){int s=0;for(int i=0;i<n;i++)s+=i;return s;}","nofile":true}}}}' \
 | timeout 30 $ROOT/ucas --mcp | grep -o 'c_lower has no argument[^"]*'
```

**Observed:**

```
error (bad_request): c_lower has no argument "nofile"
```

### LIMIT-4 — Minor: MCP `c` errors are printed twice in `content[0].text`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
For some error paths (e.g. an unknown `target`), the JSON-RPC `content` text contains
both the generic `error (CODE): message` wrapper and the raw `error: message` line,
while `structuredContent.error` correctly holds a single error.  Cosmetic, but it
breaks exact text matching on the error string.

**Reproducer:**
Reproducer: golden `mcp_c.jsonl` id 4 (`target: no_such_target`).  Observed text:

**Observed:**
```
error (c_target): c: unknown target no_such_target (c targets lists them)

error: c: unknown target no_such_target (c targets lists them)
```

### DETERMINISM-1 — early `return` inside a loop reports a varying unrolled-operation count
**Severity:** DETERMINISM
**Why it matters:** _not recorded_
For a loop whose body has an early `return`, `c optimize` reports "the cheapest proved
form is the loop unrolled (N operations)" but `N` changes between runs (749 / 758 /
768 / 778 on repeated runs of the same file).  No golden is kept for this case; the
committed `13_early_exit.out` uses only `break`/`continue` loops, which are stable.

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/c_vectorize_loops
printf 'c optimize nofile vectorize\n```c\nint ret(int n){for(int i=0;i<n;i++)if(i==5)return i;return -1;}\n```\n' > /tmp/rt.ucas
for i in 1 2 3; do timeout 20 $ROOT/ucas /tmp/rt.ucas 2>&1 | grep 'kept the loop'; done
```

**Observed:** (three consecutive runs):

```
  ret (line 1): kept the loop: the cheapest proved form is the loop unrolled (768 operations)
  ret (line 1): kept the loop: the cheapest proved form is the loop unrolled (758 operations)
  ret (line 1): kept the loop: the cheapest proved form is the loop unrolled (778 operations)
```

**Expected:** a deterministic report.  The number appears to come from a randomised
search/cost step that is not seeded, so any golden containing it would be flaky.

## Checks that passed

### Notes on behaviour that was checked and found CORRECT
- Float reductions (`float`/`double` accumulate or dot product) are **not** vectorised:
  "a float reduction (reassociating it changes the rounding)" — golden `09_vec_float_reduce.out`.
- Strided/reverse access, loop-carried dependence, 2-D indexed stores, and `volatile`
  stores are rejected with explicit reasons — golden `08_vec_rejects.out`.
- `strlen`-style zero scans become `strlen` with a structural proof — `11_scan_strlen.out`.
- Closed-form induction proofs for sums of polynomials (degrees 0–3) were
  differentially verified with `check` (clang): 20000 calls each, all agree.
- `bench`, `check`, `vectorize` and their interaction with `target` completed under
  timeout in the non-pathological cases.
