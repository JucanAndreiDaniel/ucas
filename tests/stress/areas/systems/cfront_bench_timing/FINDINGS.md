# Stress findings — `cfront_bench_timing`

_Original heading: FINDINGS — `cfront_bench_timing`_

# FINDINGS — `cfront_bench_timing`

Area: the `c optimize … bench` command, rdtsc timing, `check`+`bench`, `timed`,
`UCAS_NO_TIMES`, targets, budgets and the JSON/MCP equivalents.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | 1 — `bench` reports a ~1.2× speedup for byte-identical code (no rewrite proved) |
| LIMIT | 4 | 1 — Default `cc` cannot build the bench harness; misleading "cannot time it" diagnostic |
| DETERMINISM | 3 | 1 — `bench` timing lines change every run; `UCAS_NO_TIMES` does not suppress them |

## Findings

### WRONG-1 — 1 — `bench` reports a ~1.2× speedup for byte-identical code (no rewrite proved)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (with the clang shim):

````sh
cd $ROOT/tests/stress/areas/systems/cfront_bench_timing
cat > /tmp/addbench.ucas <<'EOF'
c optimize nofile bench budget 0
```c
int add(int a,int b){return a+b;}
```
EOF
PATH=$PWD/bin:$PATH timeout 20 $ROOT/ucas /tmp/addbench.ucas
````

**Observed:** output (five consecutive runs, `bench add` line only):

```
  bench add: 8.56 -> 7.14 cycles per call (rdtsc, median of 15, 3 runs: x1.20 x1.21 x1.20)
  bench add: 8.89 -> 7.29 cycles per call (rdtsc, median of 15, 3 runs: x1.21 x1.19 x1.25)
  bench add: 9.82 -> 8.16 cycles per call (rdtsc, median of 15, 3 runs: x1.20 x1.14 x1.20)
  bench add: 9.99 -> 8.29 cycles per call (rdtsc, median of 15, 3 runs: x1.19 x1.20 x1.21)
  bench add: 8.14 -> 6.82 cycles per call (rdtsc, median of 15, 3 runs: x1.20 x1.19 x1.19)
```

Each run also printed `c optimize: 1 function, 0 rewrites proved …` and an
`optimised C:` block byte-identical to the input (`int add(int a,int b){return a+b;}`).

**Why it matters:** the harness reports a consistent `x1.20` improvement even
though nothing was rewritten. The two benchmarked wrappers (`cfw_orig_add`,
`cfw_opt_add`) have identical bodies and are compiled with identical `-O2
-march=` flags (the `-Wall/-Wextra` difference does not affect codegen), so the
gap is a harness layout/asymmetry artifact, presented as a measured speedup.
Timing numbers are being used as proof of an optimisation that did not happen.

### WRONG-2 — 2 — `bench` keeps a rewrite it measured as *slower* (and costlier)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (clang shim):

````sh
cat > /tmp/sumbench.ucas <<'EOF'
c optimize nofile bench budget 0
```c
int sum(int n){int s=0;for(int i=0;i<n;i++)s+=i;return s;}
```
EOF
PATH=$PWD/bin:$PATH timeout 20 $ROOT/ucas /tmp/sumbench.ucas
````

**Observed:** output (excerpt):

```
c optimize: 1 function, 1 rewrite proved (0 exhaustive, 0 by SAT, 1 by induction) for x86-64-v3
  sum (line 1): loop in closed form: s += sum of degree 1 in i
    proof: induction (...); cost 3.0 -> 15.8 (before: per iteration of the loop)
  check: compiled both with cc -O2 -march=x86-64-v3; 20000 calls of 1 functions agree (edge and random inputs)
  bench sum: 8.02 -> 8.57 cycles per call (rdtsc, median of 15, 3 runs: x0.94 x0.91 x1.01)
```

**Why it matters:** the applied rewrite's model cost rises `3.0 -> 15.8` and
the rdtsc measurement shows a slowdown (`8.02 -> 8.57`, two of three runs
`x0.94`/`x0.91`), yet it is counted as `1 rewrite proved` and kept. `bench`
only judges vector/loop-body rewrites, not the closed-form rewrite; it exposes
a regression without acting on it, while the headline still reads as a win.

### DETERMINISM-1 — 1 — `bench` timing lines change every run; `UCAS_NO_TIMES` does not suppress them
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** WRONG-1's file, run twice, then with the env var:

```sh
PATH=$PWD/bin:$PATH timeout 20 ./ucas /tmp/addbench.ucas > /tmp/b1
PATH=$PWD/bin:$PATH timeout 20 ./ucas /tmp/addbench.ucas > /tmp/b2
diff /tmp/b1 /tmp/b2
PATH=$PWD/bin:$PATH UCAS_NO_TIMES=1 timeout 20 ./ucas /tmp/addbench.ucas | grep '^  bench'
```

**Observed:** output:** `diff` differs on the `bench add:` line (8.56 → 7.14 vs
9.99 → 8.29 above). With `UCAS_NO_TIMES=1` a bench line is **still** printed:

```
  bench add: 8.50 -> 6.92 cycles per call (rdtsc, median of 15, 3 runs: x1.17 x1.24 x1.23)
```

**Why it matters:** `src/cf_cmd.c` prints the bench lines without consulting
`UCAS_NO_TIMES` (unlike `src/spirv.c` and `src/adamfit.c`, which do). The
repository convention is that `UCAS_NO_TIMES=1` (set by `make test`) leaves
times out; cfront ignores it, so bench output is never byte-reproducible and
goldens cannot be kept for the timing path.

### DETERMINISM-2 — 2 — `timed` prints variable seconds and ignores `UCAS_NO_TIMES`
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Reproducer:**

````sh
cat > /tmp/timed.ucas <<'EOF'
c optimize nofile budget 0 timed
```c
int pop(unsigned x){int c=0;while(x){c+=x&1;x>>=1;}return c;}
```
EOF
for i in 1 2 3; do timeout 20 ./ucas /tmp/timed.ucas | grep '^c optimize'; done
UCAS_NO_TIMES=1 timeout 20 ./ucas /tmp/timed.ucas | grep '^c optimize'
````

**Observed:** output:

```
c optimize: 1 function, 0 rewrites proved (...) for x86-64-v3 in 7.0 s
c optimize: 1 function, 0 rewrites proved (...) for x86-64-v3 in 5.5 s
c optimize: 1 function, 0 rewrites proved (...) for x86-64-v3 in 5.8 s
c optimize: 1 function, 0 rewrites proved (...) for x86-64-v3 in 6.3 s   <- UCAS_NO_TIMES=1
```

**Why it matters:** same convention violation as DETERMINISM-1; `timed`
output cannot be used in a golden test even with the documented suppression
flag.

### LIMIT-1 — 1 — Default `cc` cannot build the bench harness; misleading "cannot time it" diagnostic
**Severity:** LIMIT
_Original classification: `LIMIT (with a WRONG diagnostic`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (plain default environment, golden `17_bright_bench.ucas`):

```sh
cd $ROOT/tests/stress/areas/systems/cfront_bench_timing
timeout 20 $ROOT/ucas 17_bright_bench.ucas
```

**Observed:** output (excerpt):

```
c optimize: 1 function, 1 rewrite proved (0 exhaustive, 1 by SAT) for x86-64-v3
  ...
  check: the original does not compile:
cc: error: unrecognized command-line option ‘-fsanitize-minimal-runtime’
  bright (line 1): proved, not applied: bench could not time it (the harness cannot make its parameters), so it is not known to beat clang's own code; ...
```

**Why it matters:** `bench` silently does no benchmarking in the default
environment. The real cause is a compiler-flag incompatibility in the hardcoded
`cc` harness, but the rewrite report attributes it to "the harness cannot make
its parameters" (which is what is printed when `cf_bench_get` returns no
result). Users cannot tell from the `bench` output that timing was never done.

### DETERMINISM-3 — 3 — `bench` changes the chosen rewrite from rdtsc noise
**Severity:** DETERMINISM
_Original classification: `DETERMINISM / WRONG`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer** (clang shim; same function with and without `bench`):

````sh
cat > /tmp/bright_plain.ucas <<'EOF'
c optimize nofile budget 1
```c
void bright(unsigned char*d,const unsigned char*s,int n){for(int i=0;i<n;i++)d[i]=s[i]+1;}
```
EOF
PATH=$PWD/bin:$PATH timeout 20 ./ucas /tmp/bright_plain.ucas | head -5
PATH=$PWD/bin:$PATH timeout 20 ./ucas /tmp/vecbench.ucas | head -5
````

**Observed:** output:

```
# without bench:
c optimize: 1 function, 1 rewrite proved (0 exhaustive, 1 by SAT) for x86-64-v3
  bright (line 1): store 0: affine fit      <- applied
# with bench (clang):
c optimize: 1 function, 0 rewrites proved (0 exhaustive, 0 by SAT) for x86-64-v3
  bright (line 1): proved, not applied: clang's own vectorisation is as fast or faster (0.05 vs 0.05 cycles/element, bench: not faster by 5% in every run); the loop is kept as written ...
  bench bright: 176 -> 171 cycles per call of 4096 elements (0.04 -> 0.04 per element; rdtsc, median of 15, 3 runs: x1.02 x1.03 x1.03)
```

Three clang runs produced `176 -> 171`, `189 -> 189`, `189 -> 184` and the
`0.04 / 0.05` per-element numbers moved, while the keep/veto decision stayed
stable here. Under the default gcc (no timing at all) the affine-fit rewrite is
**applied** (`1 rewrite proved`), so the chosen rewrite depends on whether the
harness compiles and on noisy timing. The emitted code is therefore not a
function of the input and target alone.

### LIMIT-2 — 2 — `bench` never times float functions
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer** (clang shim, golden `12_floats_bench.ucas`):

```sh
PATH=$PWD/bin:$PATH timeout 20 ./ucas 12_floats_bench.ucas | grep -E 'check:|bench '
```

**Observed:** output:

```
  check: fadd not tested (a parameter or result the harness cannot make)
  check: ffma not tested (a parameter or result the harness cannot make)
  check: fdiv not tested (a parameter or result the harness cannot make)
  check: fscale not tested (a parameter or result the harness cannot make)
  check: compiled both with cc -O2 -march=x86-64-v3; 0 calls of 0 functions agree (edge and random inputs)
```

No `bench <fn>:` line is emitted for any float/double function. Integer and
pointer functions are timed; float functions are a coverage hole for the whole
`check`/`bench` path (the harness only materialises integer parameters).

**Related:** `mylen(const char*)` (golden `14_strlen_bench`) is checked but also
never benchmarked — `bench_bufs` returns early for `PK_STR` ("not for strings").

### LIMIT-3 — 3 — MCP/JSON structured results omit bench timing and decisions
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
timeout 20 ./ucas --json --files none < json_bench.jsonl
```

**Observed:** output:** the `result` object's keys are exactly
`kind, target, rewrites, exhaustive, sat, algebra, induction, structural,
same_as_clang, cost_before, cost_after, check_passed, code`. There is no
`bench` / `timing` / `check_passed_detail` field; the rdtsc lines (when the
harness builds) appear only inside the free-form `text` string, e.g.

```
"text": "c optimize: ...\n  bench add: 9.07 -> 7.63 cycles per call (rdtsc, median of 15, 3 runs: x1.20 x1.23 x1.19)\n..."
```

**Why it matters:** it is a limitation:** MCP/JSON clients cannot consume timing or the
bench-based keep/veto decision structurally; they would have to parse prose.
The MCP `c` tool (`op:c_optimize`, `args.bench:true`) reaches the same code
path and behaves identically (confirmed with `tools.ucas.c`).

### LIMIT-4 — 4 — Target handling: `skl` / `gt1030` / `bogus` rejected; `zen4` / `skylake` accepted
**Severity:** LIMIT
_Original classification: `LIMIT (documented behaviour, no bug`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer:** goldens `09_add_skl_bench`, `10_add_gt1030_bench`,
`11_add_bogus_bench`, `07_add_zen4_bench`, `08_add_skylake_bench`.

**Observed:** output:

```
> c optimize nofile target skl bench budget 0
error: c: unknown target skl (c targets lists them)
  note: the ```c code block was not used (animate exec and simplify take SPIR-V, c optimize takes C)
```

`gt1030` (a GPU) and `bogus` give the same clean error; `zen4` and `skylake`
are accepted (`zen4` additionally prints a note that this host lacks avx512f,
so the harness falls back to `-march=native`). All five are deterministic and
kept as goldens. `bench` is never reached for a rejected target.

## Checks that passed

### Environment note (read first)
On this host `cc` is **GCC 16.2.1**, which rejects the harness flag
`-fsanitize-minimal-runtime`. `src/cf_check.c` hardcodes `cc` (it ignores
`UCAS_CC`) and always adds that flag, so **with the default environment the
`check`/`bench` harness never builds and `bench` never actually benchmarks**.
Its output is then deterministic and is kept as goldens (`01_* … 18_*`,
`mcp_bench`, `json_bench`). To observe the real timing path I used a local
`cc → clang` shim:

```sh
cd $ROOT/tests/stress/areas/systems/cfront_bench_timing
# bin/cc already contains: #!/bin/sh  exec clang "$@"
PATH=$PWD/bin:$PATH timeout 20 $ROOT/ucas CASE.ucas
```

Every timing-dependent case below was run **only** under `timeout 20` and is
documented here, **not** kept as a golden (the numbers change every run).

### Note — no confirmed crashes or hangs in this area
Every golden was double-run and byte-identical. One generated case
(`pop` with `budget 0 timed`) hit `rc=124` inside the loaded matrix runner,
but re-run alone it completed in 5.5–8.1 s, so this was host contention from
many concurrent stress agents, not a non-termination bug. No `Assertion`,
segfault, sanitizer report or truncated JSON was observed in the matrix runs.

### Goldens vs timing-dependent cases
- Goldens (default `cc`=gcc, deterministic): `01_*`–`20_*`, `mcp_bench`,
  `json_bench`. They capture the "harness does not compile" branch — **they
  will differ on a host where `cc` supports `-fsanitize-minimal-runtime`.**
- Timing-dependent (clang shim, documented only, **no `.out`**): WRONG-1,
  WRONG-2, DETERMINISM-1/-3, LIMIT-2's positive timing cases.
- `timed` cases are deliberately **not** goldens (variable seconds).
