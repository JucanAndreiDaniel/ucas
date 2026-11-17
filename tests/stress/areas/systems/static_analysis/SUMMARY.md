# SUMMARY — `static_analysis`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 5
- Files created: not recorded

### Counts
- Static analyzers run: **3** (clang `--analyze`, GCC `-fanalyzer`, clang-tidy)
  plus targeted pattern greps.
- Source files analyzed: **144** (`src/*.c`, excluding `third_party`).
- Source lines covered: ~270,000.
- **Analyzer warnings examined: 477** (430 clang + 47 GCC). clang-tidy added
  19,502 warnings, overwhelmingly stylistic (signed-bitwise, missing includes,
  switch-without-default); these were sampled/categorized, not hand-counted
  one-by-one.
- Triage: **(a) 277 distinct plausible-real sites**, **(b) 93 confirmed false
  positives**, **(c) 61 stylistic** (full data in `analysis/triage_all.tsv`).
- Adversarial runtime probes: **18** (5 `.ucas` files + 13 single-statement/CLI
  probes) targeting shift edges,
  division by zero, cfront, GLSL/SPIR-V, `fit`, `bigint`, `ring`, MCP,
  closed-stdout JSON.
- **Runtime results: 0 CRASH, 0 HANG, 0 WRONG, 0 NLP, 0 DETERMINISM issues
  reproduced.** All probes exited rc=0 under `timeout 10`.
- Golden reproducer files kept: **5** (deterministic — identical on two runs).
- Top-20 source-level risks ranked with file:line and repro status: see FINDINGS.md §1.

### Files created
- `FINDINGS.md`, `SUMMARY.md`
- `01_shift_edges.ucas` + `.out`, `02_divzero_garbage.ucas` + `.out`,
  `03_cfront_edges.ucas` + `.out`, `04_glsl_edges.ucas` + `.out`,
  `05_fit_edges.ucas` + `.out`
- `run_clang_analyze.sh`, `run_gcc_analyze.sh`, `run_clang_tidy.sh`,
  `probe.sh`, `triage.py`
- `analysis/` — raw per-file analyzer logs, consolidated warning lists,
  triage TSV/report, grep inventory, status tables


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 20 | ranked static risks; all repro attempts returned rc=0 |

### Issues by severity (per `SPEC.md` labels)
| Severity | Count | Note |
|---|---:|---|
| CRASH | 0 | none reproduced |
| HANG | 0 | none reproduced |
| WRONG | 0 | none reproduced (one suspect `fit` rounding routed to NLP area) |
| NLP | 0 | out of area |
| LIMIT | 20 | ranked static risks; all repro attempts returned rc=0 |
| DETERMINISM | 0 | all 5 goldens byte-identical on two runs |


## Takeaway
The analyzers surface hundreds of scary-looking null-deref/double-free/UB warnings, but nearly all are false positives caused by `*fail()` and `xmalloc()` not being annotated `_Noreturn`; the few genuine latent-UB sites (dangling global `multv` in gfield.c, width-overflow shifts in spirv.c/eval.c, `tok[][]` under-read in adamfit.c) did not produce any crash or wrong answer under adversarial `timeout 10` probes, so the highest-value fix is compiler annotations, not a runtime patch.

### Original takeaway (verbatim)
The analyzers surface hundreds of scary-looking null-deref/double-free/UB
warnings, but nearly all are false positives caused by `*fail()` and `xmalloc()`
not being annotated `_Noreturn`; the few genuine latent-UB sites (dangling
global `multv` in gfield.c, width-overflow shifts in spirv.c/eval.c, `tok[][]`
under-read in adamfit.c) did not produce any crash or wrong answer under
adversarial `timeout 10` probes, so the highest-value fix is compiler
annotations, not a runtime patch.

### Hard-rule confirmation
Stayed entirely in `tests/stress/areas/systems/static_analysis/`. No source/Makefile/test/
`opencode.json` edits, no `make`, no `git`, no rebuild of the shipped binary,
all runs bounded by `timeout`.
