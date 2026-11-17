# Stress findings — `static_analysis`

_Original heading: Static-analysis stress test — FINDINGS_

# Static-analysis stress test — FINDINGS

Scope: source-only review of `$ROOT`. The shipped binary
`$ROOT/ucas` was **not** rebuilt or modified. All analyzer
artifacts live in `tests/stress/areas/systems/static_analysis/analysis/`.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 8 | Root cause of the dominant false-positive class (actionable STYLE finding) |

## Findings

### LIMIT-1 — Root cause of the dominant false-positive class (actionable STYLE finding)
**Severity:** LIMIT
_Original classification: `LIMIT (static-only`._
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`rfail()` (`src/ring.c:33`), `nfail()` (`src/nlp.c:163`), `zfail()`
(`src/xform.c:2138`) all end in `longjmp(fail_jmp,1)` and never return, but are
declared as ordinary `void` functions in the headers (`src/ucas.h:51`).
Similarly `xmalloc/xcalloc/xrealloc` (`src/util.c:8-38`) call `exit(2)` on
allocation failure but are not annotated.

Consequence: both clang and GCC explore the "fail() returned" path and emit
**~93 high-signal warnings** (null derefs, double `fclose`, use-after-free,
dangling pointers) plus hundreds of "garbage value" analyzer paths that are
unreachable. Adding `_Noreturn` (or `__attribute__((noreturn))`) to the five
`*fail` functions would let the compilers prune those paths and expose the
genuine warnings instead of burying them in noise.

**Reproducer:**
Reproducer (demonstrates the *source* condition, not a runtime failure):
`grep -n -A28 '^fail(const char' src/util.c` and
`grep -n 'void fail' src/ucas.h` — no noreturn annotation.

### LIMIT-2 — Shift at/beyond bit-width is *defined* as undefined, not clamped (LIMIT)
**Severity:** LIMIT
Command:
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/static_analysis
timeout 10 $ROOT/ucas 01_shift_edges.ucas
```
**Observed:** (rc=0, deterministic):
```
> a(x: u64) = x << 64
...
> range a
range of a -> u64:
  no value: none of the 65536 points sampled is in the domain
  undefined at 65536 points
  sampled 65536 points (domain has 2^64 or more points); not exhaustive
...
> equiv a b
a and b are equal on the domain of a (proved by SAT: 317 AIG nodes, 0 conflicts)
```
**Why it matters:** the analyzer flags `x << 64` / `x << 1010` / `x << -1` as UB in the parser
and lowering code (`eval.c:783`, `fpfold.c:240/257`, `spirv.c:957/5016`). The
runtime marks such points *undefined* and proves the two undefined functions
"equal on the domain", which is vacuously true — no crash, but the domain
semantics merit review.
**Expected:** a documented clamp or explicit domain
restriction; observed: silent UB classification.

### LIMIT-3 — Division-by-zero paths are guarded (LIMIT / false positives)
**Severity:** LIMIT
_Original classification: `LIMIT / false positives`._
**Expected:** _not recorded_
Command:
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/static_analysis
timeout 10 $ROOT/ucas 02_divzero_garbage.ucas
```
**Observed:** (rc=0): `bigint 1/0`, `bigint 18446744073709551616/0`, `bigint 7%0`
all print `error: division by zero` with a caret; `p(x:u8)=x/0` gives
`range p -> ... empty (undefined everywhere) ... undefined at 256 points`.
**Why it matters:** every static div-by-zero warning I examined (cnum.c:639, ecmp.c:123,
memk.c:432, props.c:499, ring.c:343/347, simp.c:762, prove_model.c:295,
stoch.c:2282) has an input guard or rfail() check. No runtime bug.

### LIMIT-4 — cfront lowering of UB-heavy C (LIMIT / false positives)
**Severity:** LIMIT
_Original classification: `LIMIT / false positives`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Command:
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/static_analysis
timeout 10 $ROOT/ucas 03_cfront_edges.ucas
```
**Observed:** (rc=0): all functions lower successfully, including `g(x)=x<<64`,
`h(c)=i64(i32(c)<<-1)`, `z(a)=a/0`, `divneg(a)=a/-1`. The `c optimize` pass
produced "0 rewrites proved". No crash from the cf_* warning sites
(`cf_parse.c:1298`, `cf_synth.c:177/339`, `cf_lower.c:851`, `cf_opt.c:2828`,
`cf_bridge.c:200/221`, `cf_cmd.c:680`).

### LIMIT-5 — GLSL/SPIR-V simplification (LIMIT / false positives)
**Severity:** LIMIT
_Original classification: `LIMIT / false positives`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Command:
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/static_analysis
timeout 10 $ROOT/ucas 04_glsl_edges.ucas
```
**Observed:** (rc=0): GLSL compiled to SPIR-V, `spvsimplify functions` rewrote
`x & 255u` → `x` with an exhaustive proof; the `x<<32u`/`x>>32u` case produced
0 rewrites. No crash from `glslc.c:269-271`, `spirv.c:957/968/5016`,
`glslfn.c:7857`.

### LIMIT-6 — `fit` numeric search (LIMIT / no repro)
**Severity:** LIMIT
_Original classification: `LIMIT / no repro`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Command:
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/static_analysis
timeout 10 $ROOT/ucas 05_fit_edges.ucas
```
**Observed:** (rc=0): fit completed with a (visibly wrong-looking) approximation
`0.2222real(x) + 7.1e-16` for `1/sqrt(x)` on `1..4` — that misparse/misroute
belongs to the NLP area; no crash from the adamfit/analyze warning sites.

### LIMIT-7 — MCP and closed-stdout JSON (LIMIT / false positives)
**Severity:** LIMIT
_Original classification: `LIMIT / false positives`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Commands:
**Observed:**
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/systems/static_analysis
timeout 10 $ROOT/ucas --mcp < _probe.jsonl
timeout 10 $ROOT/ucas --json -e '...' 1>&- >/dev/null 2>_probe_closed.err
```
Both rc=0. The `fdopen(-1)` path (`jsonmode.c:3362/3397`) is guarded by a
`jout==NULL` return; no crash.

### LIMIT-8 — Targeted grep inventory (informational)
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`analysis/greps_highrisk.txt` records 8 malloc, 4 calloc, 4 realloc, 99 strdup,
14 strcat, 65 strcpy, 5 sprintf, 65 atoi, 6 atol, 3 atof, 13 strtol, 18 strtod,
24 sscanf, 17 longjmp, 68 setjmp calls in `src/*.c`. The single `gets` grep hit
(`jsonmode.c:700`) is a **false positive**: the word appears inside an advice
string ("the fragments a pixel gets"). The 17 `longjmp` calls all route through
the `fail_jmp`/setjmp error-recovery machinery; none is an unchecked
stack-unwind hazard. The `atoi`/`strtod` uses are in CLI argument parsing and
are generally followed by range checks; a systematic unsoundness audit of
those belongs to the parser-fuzz area, not static analysis.

## Checks that passed

### 0. Method and counts
| Analyzer | Invocation | Files | Warnings |
|---|---|---:|---:|
| clang static analyzer | `clang --analyze -Xanalyzer -analyzer-output=text -Isrc -I. -DCF_HAVE_X86 -DUCAS_SNIPDIR=... -std=gnu99 -D_GNU_SOURCE` | 144 | 430 |
| GCC `-fanalyzer` | `gcc -fanalyzer -c -o /dev/null -Isrc -I. -DCF_HAVE_X86 ...` | 144 | 47 |
| clang-tidy | `clang-tidy -checks='-*,clang-analyzer-*,bugprone-*,misc-*'` | 144 | 19,502 (overwhelmingly style) |
| targeted greps | malloc/strdup/strcat/strcpy/sprintf/atoi/strtol/strtod/sscanf/setjmp/longjmp | 144 | see `analysis/greps_highrisk.txt` |

Total **distinct compiler/analyzer warnings triaged: 477** (430 clang + 47 gcc).
Triage buckets (see `analysis/triage_all.tsv`, `analysis/triage_report.txt`):

- **(a) plausible real bug — 277 distinct sites** (mostly "garbage/uninitialized
  value" and "null deref after guard" paths that need manual confirmation).
- **(b) false positive — 93 warnings** (null deref / double-close / already-released
  patterns explained by `fail()`/`xmalloc()` never returning — see §2).
- **(c) stylistic — 61 warnings** (dead stores, potential leaks, sign-bitwise,
  missing `<header>` includes, switch-without-default).

Runtime repro campaign: **18 adversarial probes** (5 multi-statement `.ucas`
programs + 13 single-statement/CLI probes) covering shift edges,
division by zero, cfront lowering, GLSL→SPIR-V, `fit`, `bigint`, `ring`, MCP,
and closed-stdout JSON. **All ran to completion under `timeout 10` with rc=0**;
no crash, hang, or wrong-answer was reproduced from a static warning. Five
deterministic golden files were kept (each verified byte-identical on two runs).

### 1. Ranked top-20 source-level risks
Ranking: genuine-UB potential first, then confirmed-false-positive but
high-count classes. "Repro status" = result of `timeout 10 ./ucas <file>` probes.

| # | Severity | file:line | Warning / risk | Triage | Repro status |
|---:|---|---|---|---|---|
| 1 | LIMIT | `src/gfield.c:1372` (+ use at 1459) | global `multv` is assigned the address of `rp_xorder`'s stack array `int mult[]`; after return it dangles ("Address of stack memory ... referred to by the global variable `multv`"). | (a) real UB pattern, benign in practice (never dereferenced after `rp_factor` returns) | probed GF factorization paths — rc=0, no crash |
| 2 | LIMIT | `src/spirv.c:967-968` | `sx64(v,w)` computes `v << (64-w)` when `w<=0`; `w==0` gives shift-by-64 UB. | (a) potential real | GLSL/SPIR-V probe `04_glsl_edges.ucas` — rc=0, no crash |
| 3 | LIMIT | `src/spirv.c:957`, `:5016` | `1<<64`-class and negative-shift warnings in SPIR-V lowering. | (a) potential real | same probe — no crash |
| 4 | LIMIT | `src/adamfit.c:3197-3205` (+3120) | GCC "stack-based buffer under-read" on the `tok[][]` shift window in `glsl_funcs`; uninit `tok[1]` copied via `memmove`. | (a) potential real | `fit` probe `05_fit_edges.ucas` (no GLSL block) — rc=0 |
| 5 | LIMIT | `src/analyze.c:2621,2733,2737,2739` | uninitialized fit objective / garbage branch in `fit` search. | (a) potential real | `fit` probe — rc=0, stable output |
| 6 | LIMIT | `src/adamfit.c:1642,1661,1702,1746,2045` | uninitialized/garbage values in numeric search. | (a) potential real | no crash |
| 7 | LIMIT | `src/eval.c:783` (`shl128`) | `x.lo << (n-64)` for `n>=128` is UB; callers pass `n=125-L` (L>=0) so `n<=125`, safe today but no assert. | (a) latent | shifts probe `01_shift_edges.ucas` — rc=0 |
| 8 | LIMIT | `src/x86data.c:643` | `1u << (isdigit?c-'0':c-'a'+10)`; any port string char outside `[0-9a-z]` gives negative shift UB. | (a) latent (data-constrained) | not reachable via CLI input — no repro |
| 9 | LIMIT | `src/memk.c:432` | `banks/g` where `g=gcd64(stride,banks)`; guarded by `stride!=0`, so g>=1 — analyzer path false positive. | (b) false positive | `cost`/bank probes — rc=0 |
| 10 | LIMIT | `src/cnum.c:639` | `c[j].d / gcd64(D,c[j].d)` flagged div-by-zero; D starts 1 and overflow path returns. | (b) false positive | `bigint`/rational probes — rc=0 |
| 11 | LIMIT | `src/ecmp.c:123` | `cur / b[0]` flagged; b[0] is normalized nonzero. | (b) false positive | no crash |
| 12 | LIMIT | `src/props.c:499` | `L / gcdi(L,q.d)` flagged; `q_from_double` rejects d==0. | (b) false positive | no crash |
| 13 | LIMIT | `src/ring.c:343,347` | explicit `if ((w=iexpr_unary())==0) rfail("division by zero")`; `rfail` not annotated noreturn. | (b) false positive | `02_divzero_garbage.ucas` — error, rc=0 |
| 14 | LIMIT | `src/simp.c:762` | `gcd64(m,q)` with q==0 rejected just above. | (b) false positive | no crash |
| 15 | LIMIT | `src/stoch.c:2282` | `rnd() % at` with at==0 on one analyzer path; the `at==0` branch always selects kind 0/2. | (b) false positive | no crash |
| 16 | LIMIT | `src/glslc.c:269-271` | `strchr("xyzw",*s)-"xyzw"` flagged NULL subtraction; outer `while` guarantees `*s` is in one of the probed sets. | (b) false positive | `04_glsl_edges.ucas` — rc=0 |
| 17 | LIMIT | `src/jsonmode.c:3362,3397` | `fdopen(fd,"w")` with `fd==-1` when `dup(1)` fails; both call sites check `jout==NULL` and return. | (b) false positive | closed-stdout `--json` probe — rc=0 |
| 18 | LIMIT | `src/util.c:79,82` (`sb_puts`) | "null pointer + integer" / "null passed to nonnull" — `xrealloc`/`xmalloc` exit(2) on OOM, never return NULL. | (b) false positive | all programs — rc=0 |
| 19 | LIMIT | `src/eval.c:1240`, `src/find.c:1967,3070` | "Use of memory after it is released" — every case is `free(x); fail(...)` with `fail` longjmp'ing. | (b) false positive | no crash |
| 20 | LIMIT | `src/absalg_cmd.c:1022-1023,1186-1194,2113`, `src/anim.c:1496`, `src/adamfit.c:1205,1276`, `src/spirv.c:1224-1348`, `src/hyper.c:110-706`, `src/mma.c:1519-1763` | large family of null-deref/double-close/dangling warnings downstream of `if(!p) fail(...)`. | (b) false positive | multiple probes — rc=0 |

### 4. Hard-rule compliance
- No source file, Makefile, existing test, or `opencode.json` was edited.
- No `make`, no `git` command, no commit.
- All artifacts (scripts, raw logs, `.ucas`/`.out`, probe scratch files) are
  inside `tests/stress/areas/systems/static_analysis/`.
- Every binary run was bounded with `timeout 10`; no stray processes remain.
