# SUMMARY — `cfront_float_semantics`

## Counts
- Distinct expressions/queries tried: ~410
- Goldens written: 17
- Files created: 17

### Counts

- **Distinct snippets / queries tried:** ~410 generated float functions through
  `c lower` and `c optimize` (24 fuzz batches × 15 functions), plus a second
  stress set (120-deep expression, 120-function block, `budget 0`, `timed
  trace`, hard f64 `equiv`, `wrap` on deep expressions), plus ~120 hand-written
  snippets covering promotion, conversions, literals, special values, aliasing,
  volatile/restrict, uninitialized reads, assume/wrapv, fma, and fast-math
  patterns, plus 5 MCP `c` calls and ~12 `equiv`/`wrap`/`range` analyser
  queries. Total well over 150 distinct expressions/queries.
- **Files created:** 17 CLI golden pairs (`.ucas`+`.out`, numbered 01-13 and
  16-19) plus 2 MCP golden pairs (`.jsonl`+`.out`, 14-15) = 38 golden files,
  plus `FINDINGS.md` and this `SUMMARY.md` = 40 files total. All 19 `.out`
  files were produced by running twice under `timeout 30` and were
  byte-identical (no nondeterministic golden kept).
- **Issues by severity:**
  - `CRASH`: 0
  - `HANG`: 0
  - `WRONG`: 2 (sample-based `nnan holds` for `x/x`; dropped constant UB
    condition in `c lower`'s `defined where`/MCP `where`)
  - `NLP`: 0 (the inline `range (a:T) BODY` "prepended parameter" behaviour was
    verified as the documented operator-section syntax, not a bug)
  - `LIMIT`: 4 (float `check` harness skips all floats; finite-only float
    parameter domain / signed-zero equality; no lowering of punning/volatile/
    aggregates/math calls; MCP `c` has no `nofile` or `c_check`)
  - `DETERMINISM`: 0


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 4 | — |

## Takeaway
The C frontend's float lowering and its five IEEE rewrites are sound and crash-free across 400+ generated functions, but the `wrap` analyser's `nnan` flag is a sampled claim that can be false at an isolated in-domain point (`x/x` at `x=0`), and constant out-of-range float→int casts silently lose their UB condition in `c lower`'s report.

### Original takeaway (verbatim)

The C frontend's float lowering and its five IEEE rewrites are sound and
crash-free across 400+ generated functions, but the `wrap` analyser's `nnan`
flag is a sampled claim that can be false at an isolated in-domain point
(`x/x` at `x=0`), and constant out-of-range float→int casts silently lose their
UB condition in `c lower`'s report.

### Confirmation

All work stayed inside `$ROOT/tests/stress/areas/systems/cfront_float_semantics/`.
No source, Makefile, existing test, `opencode.json`, or other subagent folder
was touched; no `make` and no `git` commands were run.
