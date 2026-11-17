# Stress findings — `build_variants`

_Original heading: Build-variants stress findings_

# Build-variants stress findings

Area: `tests/stress/areas/systems/build_variants/`. Eight **separate** binaries were built from the
Makefile's own 144-file source list (plus the 5-file `snxglslc` library and the
generated `nlp_words.h`/`thy_absalg.inc`):
`gcc -O0`, `gcc -O2`, `gcc -O3`, `clang -O2`, `gcc -O2 -fno-strict-aliasing`,
`gcc -O2 -mfpmath=sse -msse2`, `gcc -O3 -ffast-math -mfpmath=sse`,
`clang -O3 -ffast-math`. Base flags for every build:
`-std=c99 -D_GNU_SOURCE -w -DCF_HAVE_X86 -DUCAS_SNIPDIR=".../snippets" -Isrc -I.`.
Exact commands are in `build_logs/build_<variant>.log` and `build.sh`/`build_parallel.sh`.
The shipped `$ROOT/ucas` was **not** overwritten and was never rebuilt;
`make` was never run; no source was edited. All runs used
`UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none` and `timeout`, from this folder. Outputs contain
no absolute paths and no timestamps, so **no normalisation was needed** — diffs are byte-for-byte.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | 1 — `-ffast-math` breaks infinite-interval numeric integration (`-nan` / false "divergent"… |
| LIMIT | 1 | 1 — `gcc -O0` build is build-specifically slow (30 s timeout) on cost/gates synthesis |
| DETERMINISM | 1 | `corpus_07_cost.ucas` truncates at different points under a short timeout |

## Findings

### WRONG-1 — 1 — `-ffast-math` breaks infinite-interval numeric integration (`-nan` / false "divergent")
**Severity:** WRONG
_Original classification: `WRONG (optimisation-sensitive`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/build_variants
UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ./bin_ucas_gcc_O3_fastmath corpus_01_symbolic.ucas 2>&1 | grep -A3 'exp(-x^2) dx'
```

**Observed:** (`diffs/corpus_01_symbolic.vs_gcc_O2__{gcc,clang}_O3_fastmath.diff`):
```
 > integrate exp(-x^2) from 0 to inf
 ∫ exp(-x^2) dx
   no antiderivative found ...
-  numeric (adaptive Gauss-Kronrod 7-15, 105 evaluations): 0.886226925452757, estimated error 1.1e-14
+  numeric (adaptive Gauss-Kronrod 7-15, 2985 evaluations): -nan, estimated error 0     [gcc -ffast-math]
...
-  numeric (...): 0.886226925452757, estimated error 1.1e-14
+  numeric: the integrand is undefined or infinite inside the interval (singular or divergent)   [clang -ffast-math]
```
Also for `integrate 1/(1+x^2) from -inf to inf`: reference returns `3.14159265358979` with
an `atan(x)+C` antiderivative check; fast-math reports "undefined or infinite ...
quasi-Monte Carlo: the integrand is undefined at all 32768 points: no estimate".

**Why it matters:** √π/2 ≈ 0.886 and π are finite, well-defined integrals. `-ffast-math` assumes no
Inf/NaN, so the infinite-endpoint transformation and the singularity tests operate on
poisoned values and return a wrong number or a false "divergent" verdict. Any user relying
on certified numeric integration gets an unsound result from a fast-math build.

### WRONG-2 — 2 — `-ffast-math` yields an unsound `range` that excludes reachable values
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/build_variants
UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ./bin_ucas_clang_O3_fastmath corpus_03_wrap_range.ucas 2>&1 | grep -A4 'range f1'
```

**Observed:**
```
 > f1(x: f32 in -1..1) = x + 1e-8 - x
 > range f1
 range of f1 -> f32:
-  [0, 1.49011612e-08]
+  [9.99999994e-09, 1.00000001e-08]
   sampled 65536 points ...
```
Also `range f2` for `1/sqrt(x)` on [0.01,100]: reference `[0.100000001, 10]`,
fast-math `[0.1, 9.99999965]` (drops reachable endpoint values).

**Why it matters:** in f32 `x + 1e-8 - x` is not the constant `1e-8`; catastrophic cancellation makes the
true result range from 0 up to ~1.49e-8. The fast-math build reassociates the expression and
reports an interval that **does not contain reachable values** — a broken soundness
guarantee, the most dangerous class of failure for this tool.

### WRONG-3 — 3 — `-ffast-math` falsely reports that `1/x` has no infinities
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/build_variants
UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ./bin_ucas_gcc_O3_fastmath corpus_03_wrap_range.ucas 2>&1 | grep -A9 'wrap f3'
```

**Observed:**
```
 wrap analysis of f3:  (f3(x: f32 in -1..1) = 1/x)
   1/x   (f32)
       nnan holds (no NaN from non-NaN inputs)
-      ninf fails: inf at 144 points, e.g. x=-2.5064325e-39
-  end to end ... max abs error 1.01e+31 ...
-      the float result is infinite where the real one is finite at 144 points (overflow)
+      ninf holds
+  end to end ... max abs error 2.53e+30 ...
```

**Why it matters:** `1/x` with x near 0 genuinely overflows to inf; the reference correctly flags
`ninf fails` and 144 overflow points. Fast-math's "no infinities" assumption suppresses
the detection, so a build-variant silently loses an IEEE-safety diagnostic.

### WRONG-4 — 4 — more fast-math wrong answers (NaN range, subnormal FTZ, hidden rounding error)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/build_variants
UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ./bin_ucas_gcc_O3_fastmath corpus_11_adversarial.ucas 2>&1 | sed -n '1,10p;30,45p'
UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ./bin_ucas_clang_O3_fastmath corpus_11_adversarial.ucas 2>&1 | grep -A9 'error e3'
```

**Observed:**
```
 > range n1   (n1(x: f32 in -1..1) = asfloat(0x7fc00000) + x)
-  no value: none of the 65536 points sampled is in the domain
-  IEEE: NaN at 65536 points, ±inf at 0 points
+  [nan, -inf]                       [gcc -ffast-math: nonsensical interval]

 > wrap n5   (n5(x: f32 in 1e-40..1e-38) = x / 1e-40)
-  x/9.9999461e-41   (f32) ... sampled 65536 points (domain has 7064876 points)
+  x/0   (f32) ... over all 0 points of the domain   [gcc -ffast-math: FTZ kills divisor, all points dropped]
+  x/1e-40 ... over all 0 points                    [clang -ffast-math variant]

 > error e3 ~ x   (e3(x: f32 in 1..2) = (x*3)*(1/3))
-  max abs error 1.297e-06 ... max rel error 1.59336e-07 ... max 1 ulp
+  max abs error 1.77636e-15 ... max rel error 2.20392e-16 ... max 0 ulp   [clang -ffast-math only]
```
**Why it matters:** the NaN case shows a nonsense range `[nan,-inf]`; the subnormal case flushes `1e-40`
to zero and then reports an error analysis "over all 0 points"; the clang-only `e3` case
**algebraically cancels** `(x*3)*(1/3)` to `x` and reports it as exact (0 ulp), hiding a
real 1-ulp f32 rounding error. These are optimisation-induced unsound analyses.

### LIMIT-1 — 1 — `gcc -O0` build is build-specifically slow (30 s timeout) on cost/gates synthesis
**Severity:** LIMIT
_Original classification: `LIMIT (performance; not a correctness bug`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/build_variants
SECONDS=0; UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none timeout 30 ./bin_ucas_gcc_O0 corpus_07_cost.ucas >/dev/null 2>&1; echo "exit=$? secs=$SECONDS"
# -> exit=124 secs=30   (all 7 other builds finish this file in < 30 s, exit 0)
SECONDS=0; UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none timeout 180 ./bin_ucas_gcc_O0 corpus_07_cost.ucas >/tmp/o0.out 2>&1; echo "exit=$? secs=$SECONDS"
# -> exit=0 secs=39
```
**Observed:** at 30 s the `-O0` run is truncated mid-`gates g2` at 57 lines (exit 124);
the other seven builds emit 183 lines and exit 0. Given 180 s the `-O0` build completes
in ~39 s and its 183-line output is **byte-identical** to `gcc_O2`. The stalling point is
the exact gate synthesis in `gates g1`/`gates g2` and the `find m1 1`/`find m2 1` searches.

**Why it matters:** this is a real build-specific timeout that would break a 30 s test runner if the
reference binary were replaced by an `-O0` build, but it is a slow-computation difference,
not a hang or a wrong answer. Recorded as LIMIT, deliberately **not** kept as a golden.

### DETERMINISM-1 — `corpus_07_cost.ucas` truncates at different points under a short timeout
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (caveat, consequence of LIMIT-1`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Running `bin_ucas_gcc_O2 corpus_07_cost.ucas` twice with `timeout 30` produced different
partial output; with `timeout 60` both runs produce the same 183 lines, byte-identical to
the shipped binary. All other 10 batches are deterministic across repeated runs. The
golden outputs under `results/` were produced with a long enough timeout. No golden
`.out` files for hangs/crashes were added to the corpus folder.

## Checks that passed

### Headline result (negative)
The six builds **without** `-ffast-math` (`gcc_O0`, `gcc_O2`, `gcc_O3`, `clang_O2`,
`gcc_O2_noalias`, `gcc_O2_fpmath`) are **byte-for-byte identical on all 11 batches
(296 statements)**. My `gcc_O2` build is also byte-identical to the shipped binary on
all 11 batches. No observable strict-aliasing bug, no O0-vs-O2-vs-O3 UB symptom, and no
compiler-specific crash surfaced on this corpus. All differences below are caused by
`-ffast-math`, except the performance item (WRONG-4/LIMIT-1).

### Files / artefacts in this folder
- `build.sh`, `build_parallel.sh`, `worker.sh`, `config_*.sh`, `srclist.txt` — reproducible build.
- `build_logs/build_<variant>.log` — exact commands + compiler output for all 8 builds.
- `bin_ucas_<variant>` — the 8 separate binaries.
- `corpus_01..11_*.ucas` — the 296-statement shared corpus.
- `results/<batch>.<variant>.out`, `results/exit_codes.tsv` — every run's output + exit code.
- `diffs/*.diff` — byte-for-byte diffs vs `gcc_O2` (14 nonempty).
- `run_corpus.sh`, `run_log.txt`, `shipped_check/` — runner, log, shipped-binary cross-check.
