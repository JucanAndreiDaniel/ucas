# SUMMARY — `coverage_gap_analysis`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 0
- Files created: not recorded

### Scope tried
- Corpus files available: **4071 `.ucas` + 588 `.jsonl`** under `tests/stress/`,
  plus the canonical `tests/`, `tests/json/`, `tests/mcp/` suites.
- Instrumented runs: **5281 invocations** (CLI, MCP, JSON modes; 3 s/file bound,
  16 workers, 259 s wall). 4299 profiles flushed; 989 timed out.
- Targeted probes: **19** (each under `timeout 10`, two under 30/60 s), all
  re-verified by function-entry counters from `llvm-cov show`.

### Files created (all under `tests/stress/areas/systems/coverage_gap_analysis/`)
- `build_coverage.py` — rebuilds the separate instrumented binary (repo untouched).
  The `ucas_cov` binary and the other build artifacts were removed after analysis.
- `sweep_corpus.py`, `analyze_coverage.py`, `analyze_ops.py`, `verify_probes.py`,
  `probes.json` — rebuildable pipeline.
- `FINDINGS.md`, this `SUMMARY.md`.
- The `reports/` data was generated during analysis and the artifacts were
  removed afterward. It held the sweep log, profile data, coverage export,
  totals, zero/lowest/top file and function lists, uncovered lines, ops and
  tool summaries, and the probe log and results.
- `work/`, `obj/`, `profiles/` held regenerated probe inputs/outputs and derived
  data; those artifacts were removed after analysis.

### Coverage baseline measured
67.46% lines · 81.02% functions · 55.99% branches. 11/174 files at 0%,
1533 zero-count functions. All 27 MCP tools reached; 17/248 internal jcmd
ops never invoked by name in the JSONL corpus (but reachable).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 18 | — |

### Results by severity (contract tags)
- **LIMIT — untested reachable code: 17 top gaps confirmed** (see FINDINGS RANK
  1/1b). Each has a concrete probe that raised the target function's counter
  from 0 to ≥1.
- **LIMIT — coverage suppressed by timeouts: 1 systemic issue** (989/5281 runs
  killed at 3 s; e.g. `rules infer` in a late corpus statement is never measured).
- **Dead code (not issues): 2** — `snxglslc/emit.c`, `props.c:fn_zeros`.
- CRASH / HANG / WRONG / NLP / DETERMINISM: none found (this area measured
  coverage rather than hunting semantic bugs).


## Takeaway
The corpus is broad at the tool level (27/27 MCP tools) but has hard blind spots: 11 files at 0% and ~1533 never-run functions, dominated by the elliptic-curve CM/binary/ECPP/NTT stack, texture-block encoders, `find`'s rule/e-graph passes, and nlp.c's plot/viz/help intents — all reachable, and each now has a confirmed one-line reproducer; only `snxglslc/emit.c` and `props.c:fn_zeros` are truly dead.

### Original takeaway (verbatim)
The corpus is broad at the tool level (27/27 MCP tools) but has hard blind spots:
11 files at 0% and ~1533 never-run functions, dominated by the elliptic-curve
CM/binary/ECPP/NTT stack, texture-block encoders, `find`'s rule/e-graph passes,
and nlp.c's plot/viz/help intents — all reachable, and each now has a confirmed
one-line reproducer; only `snxglslc/emit.c` and `props.c:fn_zeros` are truly dead.
