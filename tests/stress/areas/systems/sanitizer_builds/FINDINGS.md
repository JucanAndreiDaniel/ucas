# Stress findings — `sanitizer_builds`

_Original heading: FINDINGS — `sanitizer_builds`_

# FINDINGS — `sanitizer_builds`

A **separate** ASan+UBSan-instrumented binary was built in this folder:

```
$ROOT/tests/stress/areas/systems/sanitizer_builds/ucas_san
```

It does **not** overwrite `$ROOT/ucas`; `make` was never run and no source was edited.
`build_sanitized.sh` reconstructs the Makefile's flags (`-std=gnu99 -I src -I .`,
`-DCF_HAVE_X86`, `-DUCAS_SNIPDIR=...`, `-lm`) and compiles all 144 `src/*.c` plus the
5 `src/snxglslc/*.c` sources with `-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer`.
The two generated headers the Makefile writes into the repo root (`nlp_words.h`,
`thy_absalg.inc`) were copied into this folder. The full per-case raw output is kept in
`evidence/` (not as golden `.out` files, since crash cases would break a runner).

All runs used (addresses in reports vary with ASLR — only the file:line frames are stable):

```sh
export ASAN_OPTIONS="detect_leaks=1:abort_on_error=0:print_stacktrace=1:symbolize=1"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=0"
export UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none
SAN=$ROOT/tests/stress/areas/systems/sanitizer_builds/ucas_san
```

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 3 | ASan `stack-overflow` on deeply nested input (parser recursion) |
| LIMIT | 3 | LeakSanitizer: `hy_def` leaks its parameter string on `where`/table definitions |

## Findings

### CRASH-1 — ASan `stack-overflow` on deeply nested input (parser recursion)
**Severity:** CRASH
_Original classification: `CRASH (SIGSEGV in the regular binary; ASan stack-overflow here`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (copy-pasteable):
```sh
cd /tmp/opencode
python3 -c "open('deep.ucas','w').write('show '+'('*2000+'x'+')'*2000+'\n')"
timeout 30 $ROOT/tests/stress/areas/systems/sanitizer_builds/ucas_san deep.ucas 2>&1 | tail -30
```

**Observed:** (exit 1; `evidence/OOB_stack_overflow_parens.log`):
```
==2484803==ERROR: AddressSanitizer: stack-overflow on address 0x7ffeca6ae438 (...)
    #0 0x5560331ff030 in prefix $ROOT/src/parse.c:1472
    #1 0x5560332073be in parse_expr $ROOT/src/parse.c:1657
    #2 0x5560332050a7 in prefix $ROOT/src/parse.c:1501
    #3 0x5560332073be in parse_expr $ROOT/src/parse.c:1657
    ... (#4..#247 repeat prefix/parse_expr) ...
SUMMARY: AddressSanitizer: stack-overflow $ROOT/src/parse.c:1472 in prefix
```
Confirmed for all of: 2000/5000 nested parens; 2000 unary `-`; 3000 nested `sqrt(`;
2000 unary `-` inside a function body; 3000 nested `abs(`; 20000 unmatched `(`; 20000
unmatched `[`. Also through `--json` and `--mcp` (a single deep `ucas` request kills the
whole server). The regular binary gives exit 139 (SIGSEGV) for these; ASan converts it
into a precise `prefix`/`parse_expr` mutual-recursion stack overflow.

**Why it matters:** finite malformed input should hit a depth limit (like the JSON
frontend's "nested too deeply") and return `parse_error`, not exhaust the C stack.
The recursion is `prefix (parse.c:1472) -> parse_expr (parse.c:1657) -> prefix ...`.

### CRASH-2 — CRASH / OOB — ASan `global-buffer-overflow` in NLP `isw()` for "differentiate …`
**Severity:** CRASH
**Expected:** _not recorded_
the uninstrumented binary silently reads the byte before the array and exits 0)

**Reproducer:**
Reproducer (minimal, copy-pasteable):
```sh
cd /tmp/opencode
printf 'differentiate x^3 sin x\n' > oob.ucas
timeout 30 $ROOT/tests/stress/areas/systems/sanitizer_builds/ucas_san oob.ucas 2>&1 | head -40
```
(The original is line 106 of the repo's `tests/calculus2.ucas`. Note: the explicit
`english differentiate ...` command does **not** trigger it — only a bare English line
in a `.ucas` file does.)

**Observed:** (exit 1; `evidence/OOB_nlp_isw.log`):
```
$ROOT/src/nlp.c:707:10: runtime error: index -1 out of bounds for type 'word [324]'
    #0 0x... in isw $ROOT/src/nlp.c:707
    #1 0x... in c2_sentence $ROOT/src/nlp_calc2.inc:821
    #2 0x... in sentence $ROOT/src/nlp.c:6675
    #3 0x... in translate $ROOT/src/nlp.c:7989
    #4 0x... in translate_asking $ROOT/src/nlp.c:8041
    #5 0x... in nlp_run $ROOT/src/nlp.c:8173
    #6 0x... in run_text_plain $ROOT/src/nlp.c:9850
    #7 0x... in run_text $ROOT/src/nlp.c:9795
    #8 0x... in main $ROOT/src/main.c:109
==...==ERROR: AddressSanitizer: global-buffer-overflow on address 0x... (READ of size 1)
    #0 isw $ROOT/src/nlp.c:707
    #1 c2_sentence $ROOT/src/nlp_calc2.inc:821
0x... is located 20 bytes before global variable 'nw' ... (nlp.c:368)
SUMMARY: AddressSanitizer: global-buffer-overflow $ROOT/src/nlp.c:707 in isw
```

**Why it matters:** `c2_sentence` (nlp_calc2.inc:819-821) calls
`isw(s4-1, ...)`, `isw(s4-2, ...)` where `s4 = wi`. When a sentence begins with
"differentiate"/"derive"/"implicit differentiation", `wi == 0`, so `isw(-1, ...)` and
`isw(-2, ...)` index the global word array `W[]` (`word[324]`) before its start.
`isw()` at nlp.c:707 dereferences `W[i]` with no `i>=0` guard. The read is of a byte in
the global redzone, i.e. genuine memory-unsafe behavior (UBSan flags `index -1`, ASan
flags a 1-byte global-buffer-overflow). Deterministic on every run.

### CRASH-3 — OOB — ASan `heap-buffer-overflow` in SPIR-V `mem_uni_at`
**Severity:** CRASH
**Expected:** _not recorded_
**Why it matters:** _not recorded_
uninstrumented binary silently reads it and exits 0 — a latent memory-safety bug).

**Reproducer:**
Reproducer (minimal, copy-pasteable):
```~sh
cd /tmp/opencode
cat > hbo.ucas <<'EOF'
spvsimplify nofile
```spv
%a = OpIAdd %uint %x %y
OpStore %out %a
```
EOF
timeout 30 $ROOT/tests/stress/areas/systems/sanitizer_builds/ucas_san hbo.ucas 2>&1 | head -40
```~
(The original is the last statement of the repo's `tests/glslview.ucas` and
`tests/glslview_absent.ucas`.)

**Observed:** (exit 1; `evidence/OOB_spv_mem_uniformity.log`):
```
==...==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x... (READ of size 1)
    #0 mem_uni_at $ROOT/src/spv_mem.inc:269
    #1 mem_uniformity $ROOT/src/spv_mem.inc:424
    #2 mem_pass $ROOT/src/spv_mem.inc:4022
    #3 spirv_simplify $ROOT/src/spirv.c:15974
    #4 statement $ROOT/src/parse.c:3669
0x... is located 0 bytes after 9-byte region [...]
allocated by thread T0 here:
    #0 malloc
    #1 xmalloc $ROOT/src/util.c:10
    #2 mem_uniformity $ROOT/src/spv_mem.inc:377
    #3 mem_pass $ROOT/src/spv_mem.inc:4022
SUMMARY: AddressSanitizer: heap-buffer-overflow $ROOT/src/spv_mem.inc:269 in mem_uni_at
```
Deterministic. An off-by-one in the uniformity-analysis lookup table: a 9-byte buffer is
allocated at spv_mem.inc:377 and indexed one past its end in `mem_uni_at`.

### LIMIT-1 — LeakSanitizer: `hy_def` leaks its parameter string on `where`/table definitions
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
wrong answer observed)

**Reproducer:**
Reproducer (minimal, copy-pasteable):
```sh
cd /tmp/opencode
printf 'b(x: u8) = x where x < 5\nshow b\n' > leak.ucas
ASAN_OPTIONS=detect_leaks=1:print_stacktrace=1 \
  timeout 30 $ROOT/tests/stress/areas/systems/sanitizer_builds/ucas_san leak.ucas 2>&1 | tail -30
```

**Observed:** (exit 1; `evidence/LEAK_hy_def.log`):
```
==...==ERROR: LeakSanitizer: detected memory leaks

Direct leak of 64 byte(s) in 1 object(s) allocated from:
    #0 ... (/usr/lib/libasan.so.8+...)
    #1 xrealloc $ROOT/src/util.c:34
    #2 sb_reserve $ROOT/src/util.c:65
    #3 sb_printf $ROOT/src/util.c:97
    #4 hy_def $ROOT/src/hyper.c:1860
    #5 hyper_statement $ROOT/src/hyper.c:2025
    #6 hyper_hook $ROOT/src/parse.c:3422
    #7 statement $ROOT/src/parse.c:3470
    #8 run_source1 $ROOT/src/parse.c:4285
    #9 run_source $ROOT/src/parse.c:4205
    #11 run_text $ROOT/src/nlp.c:9795
    #13 main $ROOT/src/main.c:109
SUMMARY: AddressSanitizer: 64 byte(s) leaked in 1 allocation(s).
```

Root cause: `hy_def` (hyper.c:1858-1860) builds the parameter list into a local `sbuf
clean` with `sb_printf`. It is freed on the normal paths (hyper.c:1884, 1903), but the
early `return 0` after `hy_scan()` fails (hyper.c:1870-1871) does not free it. The
hyper hook runs for every statement; a body containing `where` or a table literal
(`[...][x]`) makes `hy_scan()` fail, leaking `clean.p`. Two such definitions → 128 bytes
in 2 allocations. Minimal triggers verified:
- `b(x: u8) = x where x < 5` → leak
- `t(x: u8) = [10,20,30][x]` → leak
- a plain `b(x: u8) = x` or `b(x: u8 in 0..5) = x` → **no** leak (control).

### LIMIT-2 — UBSan `signed integer overflow` in the analysis engine
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
the result depends on the compiler's wraparound assumptions)

These fire on the repo's **own** golden corpus files when run through the sanitized
binary. Reproducer form:
**Observed:**
**Reproducer:**
```sh
timeout 30 $ROOT/tests/stress/areas/systems/sanitizer_builds/ucas_san \
  $ROOT/tests/<FILE>.ucas 2>&1 | grep 'runtime error:'
```

| File | Report (first frame) | Stack (top frames) |
|---|---|---|
| `tests/catalogue.ucas` | `idrw.c:840:10: signed integer overflow: 9223372036854775807 - -9223372036854775808` | `map_keys idrw.c:840` → `idrw_maps idrw.c:946` → `irw_cands irw.c:488` → `rewrites find.c:1416` → `peephole find.c:1529` → `cmd_find find.c:2633` |
| `tests/eve.ucas` | `scheme.c:1506:10: signed integer overflow: 9171918600390238162 + 316672795858946371` | `poly_scheme scheme.c:1506` → `cmd_scheme scheme.c:2341` → `calc_command calc_syntax.inc:1399` |
| `tests/exptable.ucas` | `approx.c:1137:31: signed integer overflow: -9223372036854775808 + -4649368480934526976` (also `approx.c:568:34`) | `build_sample approx.c:1137` → `run approx.c:3527` → `cmd_approx approx.c:3853`. Minimal: `approx exp(x) in -700..700 as f64 ulp 2 nosplit norational free list 2` |
| `tests/idrw64.ucas` | `find.c:562:28: signed integer overflow: 0 - -9223372036854775808` (also `find.c:563:29`) | `holes find.c:562` → `build find.c:674` → `enumerate_level find.c:736` → `run_levels find.c:803` → `cmd_find find.c:2646` |

The full traces are in `evidence/CORPUS_catalogu.log`, `CORPUS_ev.log`,
`CORPUS_exptabl.log`, `CORPUS_idrw6.log`. These are signed `long` computations at
interval boundaries (`LONG_MIN`/`LONG_MAX`) and in accumulation loops; the code relies
on wraparound, which is UB in C99 and can change under `-O2`/different optimizers.
The evaluator's own machine-integer arithmetic is **not** implicated (see §7).

### LIMIT-3 — UBSan `null pointer passed as argument N` (nonnull violations)
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
UB per C even for n==0; benign in practice)

Same reproducer form as §5. Full traces are in the named `evidence/CORPUS_*.log` files.

| File | Report | Top frames |
|---|---|---|
| `tests/absalg.ucas` | `pgrp.c:321:2 / 324:2 / 334:2: null pointer passed as argument 2` | `ss_pack pgrp.c:321` → `pg_build pgrp.c:383` → `pg_init pgrp.c:391` → `pg_normal_closure pgrp.c:845` → `pg_commutator pgrp.c:890` → `pg_derived_series pgrp.c:919` → `cmd_permgroup absalg_cmd.c:1629`. Minimal: `permgroup (1 2)(3 4), (1 3)(2 4)` |
| `tests/homal.ucas` | `simp.c:306:3: null pointer passed as argument 1` | `b_commit simp.c:306` → `hs_rp simp.c:626` → `hs_parse simp.c:1329` → `get_space homalg_cmd.c:172` → `cmd_space homalg_cmd.c:382`. Minimal: `cohomology RP^4` |
| `tests/cfbridge_icl.ucas` (also `csimp.ucas`) | `cf_opt.c:1505:3: null pointer passed as argument 1` | `optimize_value cf_opt.c:1505` → `whole_function cf_opt.c:1971` → `cf_optimize cf_opt.c:3036` → `cfront_run cf_cmd.c:292` |
| `tests/cfbridge.ucas` (also `csimp.ucas`) | `find.c:3821:2: null pointer passed as argument 1` | `find_cands find.c:3821` → `eng_find cf_bridge.c:2727` → `optimize_value cf_opt.c:1473` |
| `tests/findloophoist.ucas` | `find.c:1401:2: null pointer passed as argument 1` | `with_rewrites find.c:1401` → `peephole find.c:1534` → `cmd_find find.c:2633` |

Example (from `pgrp.c:321`): `memcpy(G->base, s->base, (size_t)s->nb * sizeof *G->base)`
where `s->base == NULL` and `nb == 0`. These are low-severity but real UBSan diagnostics
that the uninstrumented binary silently tolerates.

## Checks that passed

### 7. Not observed / verified-good (important negative results)
- **No use-after-free, no misaligned access, no null *dereference* (SEGV on address 0),
  and no double-free** in any of the ~350 hand-written expressions/queries or the
  (time-bounded) golden-corpus sweep. ASan did not emit any `heap-use-after-free`,
  `stack-use-after-return`,
  `alignment`, or `SEGV on unknown address 0x000000000000` report.
- **No UBSan report in the language evaluator** itself: 37 hand-picked UB edge inputs
  (`i64(MAX)+1`, `i64(MIN)/-1`, `i64(1)<<63`, `i8(127)+1`, `x/(x-x)`, `i8` shifts,
  `f64(1e300)`→`i64`, `0.0/0.0`, `2^100000`, …) produced **zero** `runtime error:` lines.
  The evaluator deliberately uses checked/wrapping arithmetic; the overflows in §5 are
  in analysis/search code, not in expression evaluation.
- **fp_edge NaNs** (29 cases: `asfloat` of NaN/Inf/subnormal/signed-zero bit patterns for
  f16/f32/f64, NaN arithmetic/comparison/min/max, `sqrt(-inf)`, `inf-inf`, `0*inf`,
  NaN through `range`/`equiv`) → no sanitizer report.
- **type_coercion** (all u8/i8/…/f16/f32/f64/int/real/bool casts, out-of-range casts,
  `asuint`/`asint`/`asfloat`, u64 wrap) → no sanitizer report.
- **resource-limit inputs**: 1024-entry table, 1025-entry (`table too long`),
  `2^1000000`, `10000!`, 10000-digit literal, 300 statements, 500 nested lists,
  50 000-char identifier → no ASan/UBSan report (other than the leak in §4 for tables).
- **Malformed `--json` / `--mcp` requests** (null/wrong-type args, 61-level nested JSON,
  bogus tools/call, undefined tools) → no sanitizer report; all return clean errors.
- The two OOB findings (§2, §3) are **deterministic** (re-run 3× each; identical reports
  apart from ASLR addresses). No DETERMINISM issue was found.

### 8. LIMIT — sanitized build notes
- Built with GCC 16.2.1; ASan+UBSan runtime works here, so no build LIMIT.
- The Makefile's BSD-make grammar was not executed; flags were reconstructed by reading
  it. The two generated files it writes into the repo root (`nlp_words.h`, via
  `nlp_words.awk`; `thy_absalg.inc`, via `sed` on `thy_absalg.thy`) were copied verbatim
  into this folder. All other `.inc` files already live in `src/` and are found via
  `-I src`. `src/snxglslc/*.c` objects are named `snx_*.o` to avoid colliding with
  `src/glslc.o`.
- Build artifacts (`obj/*.o`, the 111 MB `ucas_san`, `evidence/*.log`) are all inside this
  folder; no core files remain.
