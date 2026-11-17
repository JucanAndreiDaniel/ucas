# SUMMARY — `nan_subnormal_modes`

## Counts
- Distinct expressions/queries tried: 625
- Goldens written: 5
- Files created: not recorded

### Scope
Idea 5 of `FLOAT_MAGIC.md`: mode-sensitive float equivalence.  Pairs of float
functions that differ only under a specific `equiv` mode — `ftz`/`noftz`,
`nanbits` (sNaN vs qNaN payload preservation, quieting, subnormal flush of
inputs/outputs, signed zero, min/max NaN propagation) — plus `wrap`/`domain`/
`range` on the same functions and repeated calls in one session to check mode
flags do not leak.  Each verdict was compared to a hand-computed expectation
from IEEE-754 rules and the documented ucas semantics.

### Counts
- **Distinct function pairs generated:** 203 (`gen.py`, manifest `_scratch/pairs.json`),
  each expanded into 2–4 `equiv` queries.
- **`equiv` queries in the exhaustive batch:** 434 (`_scratch/analyze_all.ucas` /
  `.out`).  331 of them had a hand-computed expectation; 13 mismatches, all
  re-derived as errors in my own expectations (0 unexplained wrong verdicts
  from the sweep).
- **Other queries:** ~50 MCP tool calls across 4 `.jsonl` sessions, ~54 statements
  in 5 CLI golden files, and ~87 exploratory/probe statements in `_scratch/`.
  **Total distinct queries: ~625.**
- **Issues by severity:** `WRONG` × 2, `HANG` × 0, `CRASH` × 0, `NLP` × 0,
  `LIMIT` × 4 (plus 6 documented negative results).
- **Determinism:** all 9 goldens run twice and `diff`-identical (5 CLI `.out`,
  4 MCP `.out`).  No golden was kept for a nondeterministic case; none found.

### Files created (all under `tests/stress/areas/float/nan_subnormal_modes/`)
Generators / manifest:
- `gen.py`, `gen_mcp.py`
- `_scratch/pairs.json`, `_scratch/analyze_all.ucas`, `_scratch/analyze_all.out`,
  `_scratch/compare.py`, `_scratch/compare_results.json`

CLI goldens (`NAME.ucas` + `NAME.out`):
- `01_ftz_modes.ucas/.out` — subnormal flush toggles ftz on/off; folded `x*1` control
- `02_nanbits_modes.ucas/.out` — NaN payload bits, f16 exhaustive, sNaN quieting
- `03_zero_minmax.ucas/.out` — signed zero via `asuint`, min/max order sensitivity
- `04_aux_ops.ucas/.out` — `range`/`domain`/`wrap` around mode-flipped equivs
- `05_ftz_identity_unsound.ucas/.out` — WRONG #1 reproducer

MCP goldens (`NAME.jsonl` + `NAME.out`, each starts with `initialize` +
`notifications/initialized`):
- `mcp_mode_matrix.jsonl/.out` — full ftz × nanbits matrix on 5 defined pairs
- `mcp_state_leak.jsonl/.out` — 13 alternating mode calls (no leakage)
- `mcp_expr_misparse.jsonl/.out` — WRONG #2 reproducer (incl. correct object-form control)
- `mcp_aux_leak.jsonl/.out` — `range`/`domain`/`wrap` interleaved with mode flips

Reports:
- `FINDINGS.md`, `SUMMARY.md`


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 4 | — |

### Headline issues (see FINDINGS.md for exact output and repro commands)
1. **WRONG** — folded identities (`x*1`, `x-0`) escape FTZ operand flushing:
   `equiv mul1 passthru ftz` returns an unsound `equal:true`, while `mul1` still
   differs from an explicit-flush function.  Repro: `ucas 05_ftz_identity_unsound.ucas`.
2. **WRONG** — JSON/MCP `equiv` given expression-string args with spaces silently
   misparses them, returning a false `equal:false` and swallowing the `ftz` flag
   (`ftz:true` reported as `ftz:false`); correct object-form args give `equal:true`.
   Repro: `ucas --mcp < mcp_expr_misparse.jsonl`.


## Takeaway
Mode handling is largely sound and leak-free across 434+ equivalences, but two real wrong-verdict bugs were found — algebraic folding defeating `ftz`, and unquoted expression-string arguments corrupting MCP `equiv` (ignoring the mode flag) — with min/max NaN order dependence and sNaN quieting as documented LIMITs to watch.

### Original takeaway (verbatim)
Mode handling is largely sound and leak-free across 434+ equivalences, but two real
wrong-verdict bugs were found — algebraic folding defeating `ftz`, and unquoted
expression-string arguments corrupting MCP `equiv` (ignoring the mode flag) — with
min/max NaN order dependence and sNaN quieting as documented LIMITs to watch.

### Confinement
All files written are inside `tests/stress/areas/float/nan_subnormal_modes/`.  No source files,
Makefiles, existing tests, `opencode.json`, other subagents' folders, or build artifacts
were touched; no `make`/`git` commands were run.
