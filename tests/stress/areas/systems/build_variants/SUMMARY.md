# SUMMARY — `build_variants`

## Counts
- Distinct expressions/queries tried: 296
- Goldens written: 0
- Files created: 8

### Scope
Built **8 separate binaries** from the Makefile's 144-file source list, entirely inside
`tests/stress/areas/systems/build_variants/` (no `make`, no source edits, shipped binary untouched):

| variant | compiler/flags |
|---|---|
| gcc_O0 | gcc -O0 |
| gcc_O2 | gcc -O2 (reference build) |
| gcc_O3 | gcc -O3 |
| clang_O2 | clang -O2 |
| gcc_O2_noalias | gcc -O2 -fno-strict-aliasing |
| gcc_O2_fpmath | gcc -O2 -mfpmath=sse -msse2 |
| gcc_O3_fastmath | gcc -O3 -ffast-math -mfpmath=sse |
| clang_O3_fastmath | clang -O3 -ffast-math |

Base flags identical for all: `-std=c99 -D_GNU_SOURCE -w -DCF_HAVE_X86
-DUCAS_SNIPDIR=... -Isrc -I.` (The shipped binary is byte-for-byte identical to the
gcc_O2 build on the whole corpus, validating the build reproduction.)

### Counts
- **Distinct statements/queries tried: 296** across **11 corpus batches** (symbolic,
  equiv/SAT, range/wrap/domain/crit, FP tables, FP numeric, exact algebra, cost/gates/find,
  C/GLSL frontends, float-bits/double-word, extremes, adversarial NaN/subnormal).
- Runs: 80 in the main matrix + batch 11 across 8 binaries = **88 binary runs** (plus
  repeat determinism and shipped-binary cross-check runs). Exit codes: **79 × 0, 1 × 124**
  (the single 124 is the gcc_O0 30 s timeout on batch 07).
- Files created: 8 binaries, 8 build logs, 5 build scripts/configs + srclist, 11 corpus
  files, 98 result `.out` files, 77 `.diff` files (14 nonempty), runner + logs, and
  `FINDINGS.md` + this `SUMMARY.md`.
- Output normalisation: **none** (inputs are relative paths, times suppressed with
  `UCAS_NO_TIMES=1`, no timestamps or absolute paths appear).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | — |
| LIMIT | 1 | — |
| DETERMINISM | 1 | — |

### Issues by severity
- **WRONG: 4** (all `-ffast-math`-induced): WRONG-1 infinite-interval integration returns
  `-nan` / false "divergent"; WRONG-2 unsound `range` excluding reachable values;
  WRONG-3 false "ninf holds" for `1/x` (misses real infinities); WRONG-4 NaN range
  `[nan,-inf]`, subnormal FTZ producing "over all 0 points", and clang-only hidden 1-ulp
  rounding error in `(x*3)*(1/3)`.
- **LIMIT: 1** — gcc_O0 build times out at 30 s on `corpus_07_cost.ucas` (~39 s to finish;
  output then identical to gcc_O2). Build-specific performance, not a hang.
- **DETERMINISM: 1** — batch 07 truncated under a 30 s timeout yields varying partial
  output; deterministic with a longer timeout (consequence of LIMIT-1).
- **CRASH / HANG: 0** — no build-specific crashes; the one 124 was a slow-but completing run.
- **Negative result (important)**: the six non-fast-math builds are byte-for-byte
  identical on all 296 statements — **no observable strict-aliasing / O-level / compiler
  UB symptoms** in the non-fast-math configurations.


## Takeaway
The tool is stable across gcc/clang and -O0/-O2/-O3 and `-fno-strict-aliasing`/`-mfpmath=sse`, but `-ffast-math` demonstrably invalidates its core soundness claims (interval ranges, infinity/overflow detection, certified integration, rounding-error analysis) and would silently produce WRONG answers; an `-O0` build is also unfit for a 30 s test runner purely on speed.

### Original takeaway (verbatim)
The tool is stable across gcc/clang and -O0/-O2/-O3 and `-fno-strict-aliasing`/`-mfpmath=sse`,
but `-ffast-math` demonstrably invalidates its core soundness claims (interval ranges,
infinity/overflow detection, certified integration, rounding-error analysis) and would
silently produce WRONG answers; an `-O0` build is also unfit for a 30 s test runner purely
on speed.
