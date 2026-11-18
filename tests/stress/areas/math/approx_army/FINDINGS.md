# Findings — `approx_army`

Owner sources: `src/approx.c`, `src/adamfit.c`, `src/remez.c`, `src/numsearch.c`,
`src/find.c`, `src/closed.c`, `src/rounderr.c`.  The two `approx` crashes are
in `src/approx.c`; the SIGFPE is in `src/find.c`.  Every reproducer was run
from this directory with the canonical command (`env
UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none $ROOT/ucas NAME.ucas` for `.ucas`, and
`env ... $ROOT/ucas --json --files none < NAME.jsonl` for `json_*`).  Goldens
are from the fixed binary and reproduce byte-identically.

## Summary

| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 3 | `approx` heap overflow at 16 exact points; `approx more <huge>` wraps the cursor and segfaults; `find`'s `holes()` traps on `INT64_MIN % -1` |
| LIMIT | 1 | `c optimize budget 2` does not cap a single find-engine run (the caller gives find at least 60 s) |

## Findings

### CRASH-1 — `core_sample()` overflows its arrays with 16 exact points

**Severity:** CRASH
**Reproducer:** `01_keep16_overflow.ucas` (control `02_keep8_control.ucas`).
The command asks for 14 explicit exact points and `keep endpoints`, so
`A.nkeep = AMAXK = 16`, at a degree high enough that the constrained fit
succeeds and `core_round()` reaches `core_sample()`.

**Before the fix:**

```sh
# 16 exact points, degree 20, f32
$ROOT/ucas 01_keep16_overflow.ucas
# Segmentation fault (exit 139) after the "deg ... fits" table
valgrind $ROOT/ucas 01_keep16_overflow.ucas
# Invalid write of size 8 at core_sample (approx.c:572/578)
# ERROR SUMMARY: hundreds of thousands of errors
```

`core_sample()` allocated `2*m + 8` slots (`m = 1500` fixed) but writes
`m` Chebyshev points + `m` float keys + `A.nkeep` exact points before the
finite/in-range filter.  With `A.nkeep = 9..16` that is up to 3016 writes
into 3008 slots: 8 floats of heap overflow, enough to corrupt the heap and
segfault in the common case.  The filter runs after the writes, so it cannot
save the buffer.  `A.nkeep` can legitimately be 16: `cmd_approx` accepts
`AMAXK - 2 = 14` explicit points and `keep endpoints` adds 2.

**After the fix:** allocate `2*m + AMAXK + 8` slots.  The reproducer exits 0
and prints a candidate; `05_keep16_search.ucas` confirms the search now sees
exactly 3016 sample points with 16 exact points.  `02_keep8_control.ucas`
(8 exact points, the old in-bounds boundary) is unchanged in shape.  No
existing golden uses more than `keep endpoints` (2 points), so no existing
golden changes.

### CRASH-2 — a huge `approx more` count corrupts the cursor

**Severity:** CRASH
**Reproducer:** `03_more_huge.ucas` (control `04_more_control.ucas`).

**Before the fix:**

```sh
$ROOT/ucas 03_more_huge.ucas
#  8 more: 'approx more [n]'
# > approx more 2147483647
#   -2147483639 more
# > approx more 1
# Segmentation fault (exit 139)
```

`cmd_approx`'s `more` branch cast the parsed number straight to `int` with no
range check, and `approx_more()` computed `print_rows(A.shown, A.shown + n)`.
For `n = INT_MAX` the addition wrapped to a negative `to`; `print_rows()`
then assigned that negative value to `A.shown`.  The next `approx more`
called `print_rows(A.shown, A.shown + 1)`, whose loop indexed `A.cd[]` with a
negative offset and crashed.  A non-integer huge value also hit undefined
behaviour in the `(int)` cast.

**After the fix:** the count is parsed as a `double`, rejected below 1 and
clamped to 1e6 before the cast; `approx_more()` additionally clamps `n` to
`A.nc - A.shown` so `A.shown + n` can never wrap.  The reproducer now prints
all remaining candidates and the following `more` prints `no more
candidates`.  Ordinary counts (`04_more_control.ucas`) are unchanged.

### CRASH-3 — `holes()` traps on `INT64_MIN % -1` (find.c)

**Severity:** CRASH
**Source:** `/tmp/opencode/FUZZ_C.md` finding #2, independently confirmed here.
**Reproducer:** `json_find_sigfpe.jsonl` (control `json_find_shift_control.jsonl`,
CLI control `06_find_u64_shift_control.ucas`).

Before the fix:

```sh
printf '%s' '{"cmd":"c_optimize","args":{"code":"unsigned long long f(unsigned long long x, int n) { return x << n; }","nofile":true,"budget":2}}' \
  | $ROOT/ucas --json --files none
# exit 136 (SIGFPE)
# gdb: #0 holes() at src/find.c:562
```

The `find` engine samples the target `x << n`, whose column reaches
`INT64_MIN`.  `holes()` picks `p` with `c[p] != c[0]`, but then evaluated
`(y[p] - y[0]) % (c[p] - c[0])`.  At the failing sample `y[0] = 0`,
`y[p] = INT64_MIN` and `c[p] - c[0] = -1`: the divisor is *not* zero, but
`INT64_MIN % -1` overflows the x86 `idiv` and raises SIGFPE.  (The signed
subtraction `y[p] - y[0]` could also overflow on other columns.)

Fix: form both differences with unsigned subtraction (two's-complement, no
signed-overflow UB) and skip the affine template when the divisor is zero or
the dividend/divisor pair would trap (`INT64_MIN` / `-1`).  The reproducer
now exits 0 with the ordinary `no cheaper form` result; the signed-shift
control and the CLI `find` control are unchanged.

### LIMIT-1 — `c optimize budget 2` does not cap one find-engine run

**Severity:** LIMIT (documented, not fixed — the fix is outside my files)
`src/cf_bridge.c:2735` calls `find_cands(&f, 4, secs > 60 ? secs : 60, ...)`.
So even with `budget 2` (find's CPU share ≈ 0.4 s) a single find invocation
gets at least 60 s; several snippets in `/tmp/opencode/FUZZ_C.md` §3 take
14–19 s.  The deadline check in `find.c`'s `find_cands()`
(`if ((clock()-t0)/CLOCKS_PER_SEC > seconds) break;`) *does* work — it just
receives a floor of 60 seconds.  `ebudget 0`/`steps 0` do not change this.
Owner of `cf_bridge.c` should pass `secs` (or `eng_left()`) without the 60 s
floor if `budget` is meant to bound a single run.  No test golden added: this
is timing-dependent.

## Checks that passed

- Fresh `bmake` after each edit; retried once past a transient failure caused
  by a concurrent relink of the shared binary.
- `valgrind` on the fixed binary: CRASH-1 reproducer reports zero invalid
  writes (it previously reported a heap overflow); CRASH-2 reproducer exits 0.
- All three crash reproducers were run under the fixed binary twice and
  produced byte-identical output, so they are kept as goldens.  The SIGFPE
  reproducer was confirmed to exit 136 on the pre-fix binary and 0 afterwards.
- `STRESS_AREA=approx_army` and `STRESS_AREA=approx_fit_search` both pass via
  `bmake stress-test STRESSLIST=...` (see the parent report).
- Controls: `08_approx_options.ucas`, `01_approx_polynomials.ucas` and the
  other `approx_fit_search` goldens are byte-identical after the fixes.
