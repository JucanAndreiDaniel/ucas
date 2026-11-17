# Stress findings — `coverage_gap_analysis`

_Original heading: Coverage-gap analysis — findings_

# Coverage-gap analysis — findings

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 4 | source files with 0% line coverage, and their reachability |

## Findings

### LIMIT-1 — source files with 0% line coverage, and their reachability
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The full list was generated during analysis; the `reports/` artifacts were removed afterward. 11 of 174 code-bearing files have 0 lines hit.

| file | lines | reachable? | confirming probe (copy-pasteable) | result |
|---|---|---|---|---|
| `emit.c` (snxglslc) | 2243 | **NO — dead code** | `spirv_simplify(lang=glsl)` via MCP (`glsl_emit`) | count 0: glslfn.c calls `glslc_parse` only; `glslc_emit`/`snx_glslc_compile` have zero callers outside snxglslc |
| `astcblk.c` | 1109 | YES | `ucas_cov $ROOT/tests/stress/areas/sat/afl_coverage_fuzz/seeds/texastc.ucas` | `astcb_encode` count 13 |
| `bc7blk.c` | 572 | YES | file `Q=[100,40,10,40,10,40,10,40,10,40,10,40,10,40,10,40]` + `texenc Q bc7` | `bc7_encode` count 1 |
| `eccm.c` | 468 | YES | `eccm D = -3 bits 20` | `cm_build` count 19 (in `ecff_cm.inc`) |
| `egraph.c` | 437 | YES | `f(x: u8 in 0..15) = x+x` + `find f 1 saturate` | `egraph_best` count 1 |
| `ecpp.c` | 307 | YES | `ecpp 170141183460469231731687303715884105727` | `ecpp_prove` count 1 |
| `ecalg.c` | 272 | likely YES (CM/isogeny helpers) | not probed (lower rank) | — |
| `ecb2.c` | 252 | YES | `ecb2 K-163 mul 3` | `b2_count_koblitz` count 1 |
| `ecff_cm.inc` | 238 | YES | `eccm D = -3 bits 20` | `cm_build` count 19 |
| `ecntt.c` | 199 | likely YES (NTT crypto helper) | not probed (lower rank) | — |
| `ecff_b2.inc` | 129 | YES | `ecb2 K-163 mul 3` | reached with `ecb2.c` |

**LIMIT-1 (severity LIMIT — coverage suppressed by timeouts).**
`rules infer` is present in the corpus
(`tests/stress/areas/systems/source_hotspots/06_clock_short.ucas`) but its handler
`cmd_rules_infer` had **0 coverage**: the preceding `find … stoke` consumes the
5 s budget, so the 3 s sweep bound killed the run before the handler.
Standalone probe `rules infer inputs 2 width 8 cost 4 seconds 1` →
`cmd_rules_infer` count 1 (21 rules printed). Any statement late in a
multi-statement slow corpus file is at risk of being unmeasured.

### LIMIT-2 — representative zero-count functions in key files
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The full list was generated during analysis; the `reports/` artifacts were removed afterward. 1533 zero-count functions overall.

| function | file | reachability / probe |
|---|---|---|
| `sat_selftest` | sat.c | YES — `ucas_cov --sat-selftest` (60 s bound), count 1 |
| `show_help` | nlp.c | YES — MCP `english` with text `what can you do`, count 2 |
| `nlp_translate` | nlp.c | YES — `animate exec of best found approximation of x*x`, count 1 (30 s bound) |
| `self_exec` | jsonmode.c | YES — JSONL `{"cmd":"state"}` `{"cmd":"reset"}` `{"cmd":"state"}`, count 1 |
| `egraph_best` | egraph.c | YES — `find f 1 saturate`, count 1 |
| `kahan_scheme` | scheme.c | YES — Kahan f32 loop + `scheme p more`, count 1 |
| `crit_int_real` | analyze.c | YES — `f(x: int in 0..8) = x*x/3.0` + `crit f`, count 1 |
| `floordiv` | closed.c | YES — `f(n: int in 0..20) = sum(k, 0, n, k mod 3)` + `closed f`, count 12 |
| `bc7_encode` / `etc2_encode_r` / `astcb_encode` | bc7blk/etc2blk/astcblk.c | YES — `texenc Q bc7` / `texenc Q etc2` / ASTC seed, counts 1/1/13 |
| `cm_build` | ecff_cm.inc | YES — `eccm D = -3 bits 20`, count 19 |
| `b2_count_koblitz` | ecb2.c | YES — `ecb2 K-163 mul 3`, count 1 |
| `ecm_*` | ecm.c | YES — `ecm 8051` (a composite; a prime short-circuits), count 2 |
| `ecpp_prove` | ecpp.c | YES — a >2^64 prime, count 1 |
| `iz_symbolic` | xform.c | YES — `iztrans e^(a/z)` (the rational path is taken for numeric poles), count 1 |
| `fn_zeros` | props.c | **NO — dead code**: declared in props.h, no caller anywhere |

### LIMIT-3 — lines never executed in key areas
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Per-key-file instrumented/uncovered line counts and uncovered-line lists were
generated during analysis; the `reports/` artifacts were removed afterward:

| file | inst lines | uncovered | % hit |
|---|---|---|---|
| nlp.c | 5174 | **795** | 84.6 |
| xform.c | 2534 | **531** | 79.0 |
| find.c | 1725 | **471** | 72.7 |
| closed.c | 1781 | 294 | 83.5 |
| calc2.c | 2561 | 269 | 89.5 |
| parse.c | 2042 | 245 | 88.0 |
| series.c | 1335 | 233 | 82.5 |
| forms.c | 2485 | 228 | 90.8 |
| props.c | 2882 | 187 | 93.5 |
| scheme.c | 1141 | 153 | 86.6 |
| jsonmode.c | 1261 | 149 | 88.2 |
| eval.c | 1621 | 144 | 91.1 |
| analyze.c | 1503 | 139 | 90.8 |
| sat.c | 470 | 92 | 80.4 |
| xfrat.c | 1137 | 88 | 92.3 |
| loop.c | 510 | 84 | 83.5 |

The largest single concentration of never-run lines is **nlp.c (795)**, almost
all in rarely-used intent handlers (help, plot/viz, image blocks, `annotate`,
`dcond`, `vs_sep`). These are reachable: `show_help` and `nlp_translate` were
confirmed above; the plot/viz handlers need a plotting frontend and are the
next layer to target. In **xform.c (531)**, the 0-count transform helpers
(`indicator`, `indicator_d`, `cond_interval`, `ft_numeric`, `prod2sum`,
`cp_scale`) are reachable through `laplace`/`fourier`/`ztrans` option
combinations; `iz_symbolic` was confirmed with `iztrans e^(a/z)`.
In **find.c (471)**, the rule-inference family (`rmatch`, `rstep`, `rinst`,
`rvars`, `rbound`, `rderived`, `sf_*`) is reached by `rules infer` (confirmed).

### LIMIT-4 — commands / ops never reached
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- **MCP tools: 27/27 reached** — no gap at the tool level.
- **jcmd ops (248 internal ops in `jsonmode.c:cmds[]`): 231 invoked by name in
  the JSONL corpus; 17 never invoked by name** (from the analysis; artifacts removed):
  `ec_add, ec_cm, ec_compress, ec_decompress, ec_divpoly, ec_pairing,
  ec_validate, ec_volcano, ec_weak, ecdh, ecdsa_verify, ed25519_sign,
  ed25519_verify, modpoly, scheme, x448, x86check`.
  Coverage probes show these are **reachable, not dead**: `ec_cm` (via `eccm`),
  `scheme` (via `scheme p more`), and the `ecb2`/`ecm`/`ecpp` family were
  confirmed. They are simply absent from the accumulated `.jsonl` corpus —
  most elliptic/protocol ops are exercised only through `.ucas` CLI files,
  and `ecdh`/`x448`/`ed25519_*`/`x86check` deserve dedicated JSONL golden
  tests. Note `cmd_more` (find.c) also had 0 coverage — the `more` command's
  handler is never reached in the sweep because its corpus files time out.

## Checks that passed

### Method (objective, not guesswork)
- Built a **separate** clang source-coverage binary from `build_coverage.py`
  (`ucas_cov`); the binary was removed after analysis. The repo binary and
  sources were not touched and `make` was not run.
- Swept `sweep_corpus.py` over **5281 invocations** of the accumulated corpus
  (all `tests/stress/**/*.ucas`, each `.jsonl` under both `--mcp` and
  `--json --files none`, plus the canonical `tests/`, `tests/json`, `tests/mcp`
  suites). 4299 runs produced flushed profiles; 989 hit the 3 s per-file bound
  (their coverage is lost — see LIMIT-1).
- `llvm-profdata merge` → `llvm-cov export` → ranked reports (generated during analysis; the
  `reports/` artifacts were removed afterward).
- **Overall: 67.46% line, 81.02% function, 55.99% branch coverage**
  (159967/237142 lines, 6485/8004 functions).

Every gap below was then probed with the instrumented binary under `timeout 10`
(30/60 s only where noted), and reachability was **confirmed** by a nonzero
function-entry counter from `llvm-cov show` on a fresh profile. 17/19 top gaps
confirmed reachable; 2 are dead code. The full probe log and machine results were
generated during analysis; the `reports/` artifacts were removed afterward. The
probe specs stay in `probes.json`.

### Dead code (not reachable; do not aim to cover)
1. `snxglslc/emit.c` (2243 lines, 105 functions) — `glslc_emit` and
   `snx_glslc_compile` have no callers outside snxglslc; GLSL simplify uses
   only `glslc_parse`.
2. `props.c:fn_zeros` — declared in props.h, never called.

### Probe reproduction
`verify_probes.py` re-runs all 19 probes and re-verifies reachability from the
profiles. It regenerates inputs into `work/probe_<name>.ucas|jsonl` and outputs
into `work/probe_<name>.out` at run time; those artifacts were removed after
analysis.

```
cd $ROOT/tests/stress/areas/systems/coverage_gap_analysis
python3 verify_probes.py                 # 17/19 REACHED, 2 dead code
```
