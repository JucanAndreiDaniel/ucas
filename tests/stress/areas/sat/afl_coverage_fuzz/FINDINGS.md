# Stress findings — `afl_coverage_fuzz`

_Original heading: FINDINGS — `afl_coverage_fuzz`_

# FINDINGS — `afl_coverage_fuzz`

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | stack overflow on deeply nested expressions (deterministic) |
| NLP | 2 | `checklim equiv ...` silently parsed as four free variables |
| LIMIT | 3 | pervasive memory leaks block naive ASan fuzzing |
| DETERMINISM | 1 | fuzzer-found stack overflow needs accumulated in-process state |

## Findings

### CRASH-1 — stack overflow on deeply nested expressions (deterministic)
**Severity:** CRASH
`01_deep_unary_crash.ucas`, `02_deep_sin_crash.ucas`, `03_deep_paren_crash.ucas`,
`04_deep_sqrt_crash.ucas` (no `.out` — these crash; per `SPEC.md` they are not goldens).

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/afl_coverage_fuzz
timeout 15 $ROOT/ucas 01_deep_unary_crash.ucas >/dev/null 2>&1; echo $?
timeout 15 $ROOT/ucas 02_deep_sin_crash.ucas   >/dev/null 2>&1; echo $?
timeout 15 $ROOT/ucas 03_deep_paren_crash.ucas >/dev/null 2>&1; echo $?
timeout 15 $ROOT/ucas 04_deep_sqrt_crash.ucas  >/dev/null 2>&1; echo $?
```

**Observed:** (all four, two runs each, identical partial output):

```
Segmentation fault (core dumped)
exit=139
```

The crash threshold on the shipped `-O2` binary is ~1,512 nested `sin(...)`,
~1,526 nested `(...)` and ~1,525 unary `-` (binary-searched). Each reproducer
uses depth 1,600 for margin. Partial stdout is deterministic (the echoed
statement, then death before/while printing the result).

**Why it matters:** unbounded recursion in the expression printer/parser. The
libFuzzer stack trace from three independent campaigns is identical:

```
ERROR: AddressSanitizer: stack-overflow ...
  #0 __printf_buffer_write
  #4 sb_printf                src/util.c:93
  #5 pr                       src/node.c:1919
  #6 pr                       src/node.c:1920
  #7..#250 pr                 src/node.c:1920   (same frame repeated)
SUMMARY: AddressSanitizer: stack-overflow in __printf_buffer_write
```

`pr()` (`src/node.c:1919-1926`) recursively prints `N.a[n]` with no depth
guard; the parenthesised-parser path recurses similarly. A user script of
~1,600 characters kills the process with SIGSEGV instead of a parse/domain
error.
**Expected:** a depth limit with a clean "expression too deep" error.

### DETERMINISM-1 — fuzzer-found stack overflow needs accumulated in-process state
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (same root cause as #1, but not a single-file repro`._
**Expected:** _not recorded_
Three separate campaigns found the same `pr()` stack overflow, each from a
mutation of `tests/gauss.ucas` involving `model dearf : gt1030 { ... }`,
`scheme f more model dearf`, `scheme g more`, `scheme q more model dearf`.
Artifacts:

**Reproducer:**
```sh
crashes/crash-f03f8f0723eec9bcd25ebba8a068e5d5c4bdc80e   (ASan, printf_common)
crashes/f1-crash-917950f9aea0f9a81e4a5ea3c0e8a500af7ea3b3 (UBSan, __printf_buffer_write)
crashes/a2-crash-a08cf2eae88b40f887c32a7a6e7db7c58d561911 (ASan, printf_common)
```

Exact reproduction of the *stack trace* (the campaign that produced it):

```sh
cd $ROOT/tests/stress/areas/sat/afl_coverage_fuzz/run
UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ASAN_OPTIONS=detect_leaks=0 \
  ../fuzz_ucas -max_total_time=240 -timeout=25 -rss_limit_mb=2048 \
  -max_len=2048 -detect_leaks=0 -ignore_timeouts=1 -ignore_crashes=1 \
  -dict=../dict/ucas.dict -artifact_prefix=../crashes/a2- \
  -jobs=3 -workers=3 ../corpus_fast/
```

**Observed:** `ERROR: UndefinedBehaviorSanitizer: stack-overflow` with ~250
recursive `pr()` frames at `node.c:1920`; `SUMMARY: ... in __printf_buffer_write`.

**Why it matters:** it is reported here and not as a golden:** ucas keeps definitions/models
in globals across `run_text()` calls, so libFuzzer inputs mutate accumulated
state. Each artifact above runs cleanly on a fresh process
(`timeout 15 $ROOT/ucas <artifact>` → exit 0), so it cannot
serve as a stable CLI reproducer. The deterministic single-file form is #1.

### NLP-1 — `checklim equiv ...` silently parsed as four free variables
**Severity:** NLP
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/afl_coverage_fuzz
timeout 15 $ROOT/ucas 05_nlp_checklim.ucas
```

**Observed:**

```
> checklim equiv x*!x x^2
_(checklim: real, equiv: real, x: real) = checklim*equiv*x*real(!(x*x^2 != 0))
  -> real
```

**Why it matters:** a fuzzer mutation of "check limit / equivalence" is not
rejected or flagged as unknown; `checklim` and `equiv` are silently taken as
ordinary real variables and a confident-looking definition is returned.
**Expected:** `note: I read "checklim", "equiv" as variable names` or an error.

### NLP-2 — `solve x%olv = 4` silently guesses the solve variable
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/afl_coverage_fuzz
timeout 15 $ROOT/ucas 06_nlp_solve_olv.ucas
```

**Observed:**

```
> solve x%olv = 4
  ucas: solve x%olv = 4
  note: solve for which variable?: read as x, not olv
solve x%olv = 4 for x
  note: no exact method applies; sign changes in [-100, 100], refined by bisection ...
  no real solution
```

**Why it matters:** `%` is read as an identifier character, producing a bogus
name `olv`; the frontend then guesses `x` and answers a question the user did
not ask. The `note:` mitigates it, but the answer ("no real solution") is
presented as authoritative for malformed input. Documented as a stable golden
because the output is deterministic (verified twice).

### LIMIT-1 — pervasive memory leaks block naive ASan fuzzing
**Severity:** LIMIT
_Original classification: `LIMIT (low severity, but loud enough to halt a campaign`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/afl_coverage_fuzz
printf 'identify 1,4,9,16,25\n' > /tmp/_leak.ucas
ASAN_OPTIONS=detect_leaks=1 timeout 20 ./fuzz_ucas -runs=1 /tmp/_leak.ucas 2>&1 \
  | grep -E '^SUMMARY: AddressSanitizer'
```

**Observed:**

```
ERROR: LeakSanitizer: detected memory leaks
Direct leak of 1000 byte(s) in 1 object(s) allocated from:
  ... xcalloc (src/util.c:22) -> cs_parse_frag (src/calc_syntax.inc:311)
      -> cmd_identify (src/props.c:5518) -> props_command (src/props.c:4245)
SUMMARY: AddressSanitizer: 1688 byte(s) leaked in 6 allocation(s).
exit=77
```

**Why it matters:** LeakSanitizer aborts on the initial corpus, so all campaigns
needed `ASAN_OPTIONS=detect_leaks=0 -detect_leaks=0`. Leaks are not directly
exploitable from the CLI, so they are documented rather than counted as crashes.

### LIMIT-2 — libFuzzer "timeouts" on `mma`/`hmma` are false positives
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Example:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/afl_coverage_fuzz
timeout 15 $ROOT/ucas \
  crashes/c1-timeout-aeb652ace2adfe56d3e52862d2b069b71e8fbef7 >/dev/null 2>&1; echo $?
# 124 with a 15 s cap
timeout 32 $ROOT/ucas <same file> >/dev/null 2>&1; echo $?
# 0 after 18 s
```

**Observed:** `mma`/`hmma` cost search tries 8,488 dataflows and then emits a
GLSL file; it completes in ~18 s but exceeds a 5 s libFuzzer timeout. These are
**not hangs** — campaigns used `-ignore_timeouts=1` and later `-timeout=25`.
One such run wrote `mma_m16n8k16_f32.glsl` and `simplified.spvasm` into the
folder; all fuzzing was confined to this folder and the stray files removed.

### LIMIT-3 — harness/compiler fidelity gap for deep-recursion threshold
**Severity:** LIMIT
_Original classification: `LIMIT (methodology note`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
shipped CLI is `-O2`. Stack-frame sizes differ, so the harness survives some
nesting depths that crash the CLI (e.g. `02_deep_sin_crash.ucas` at depth 1,600
runs clean under `fuzz_ucas_echo -runs=1`, but SIGSEGVs under the real CLI).
This does **not** affect the finding — the crash class was found by all three
campaigns and the single-file reproducers in #1 use the real binary. It means
the fuzzer slightly under-counts depth-sensitive stack-overflow cases.

## Checks that passed

### Tooling note / method (read first)
AFL++ / honggfuzz are **not installed** (`which afl-fuzz afl-clang-fast honggfuzz afl-tmin`
all fail). `clang` **does** ship libFuzzer, so this area ran **real coverage-guided
fuzzing** with libFuzzer (SanitizerCoverage, inline-8-bit counters) instead of AFL.
Two binaries were compiled from `src/*.c` entirely inside this folder (see
`build.sh`, `build_fast.sh`); the repo binary, Makefile, objects and `git` were
never touched.

- `fuzz_ucas`    — libFuzzer + AddressSanitizer (172,252 coverage counters).
- `fuzz_ucas_fast` — libFuzzer + UBSan, no ASan (higher throughput).
- Harness `fuzz_ucas.c` feeds each mutated buffer to `run_text()` (ucas.h:1048).
- Seeds: copies of all 250 `tests/*.ucas`, filtered to 43 fast ones plus 24 tiny
  grammar seeds, grown to ~2,000 corpus entries by coverage feedback.
- Dictionary `dict/ucas.dict`: 200+ command/type/operator/boundary tokens.
- Campaigns (all bounded): 45 s validation; three 240 s × 3-worker campaigns.
  ~35,900 total executions, ~2,500 new coverage cells discovered.
- Flags used: `AFL_SKIP_CPUFREQ` equivalent N/A; `-timeout=5/15/25`,
  `-rss_limit_mb=2048`, `-max_len=2048`, `-ignore_timeouts=1
  -ignore_crashes=1 -ignore_ooms=1 -use_value_profile=1`, `-detect_leaks=0`.
