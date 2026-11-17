# SUMMARY — `x86_intrinsics_mca`

## Counts
- Distinct expressions/queries tried: ~311
- Goldens written: 22
- Files created: not recorded

### Original preamble

**Distinct expressions / queries tried:** ~311 in durable goldens
(80 CLI statements + 231 MCP tool calls), plus ~400 exploratory CLI/MCP
probes while hunting — comfortably above the 150 target.

### Files created (all inside `tests/stress/areas/gpu/x86_intrinsics_mca/`):

* 16 CLI goldens `NN_*.ucas` + `NN_*.out`
  (`01_models` … `16_x86check_cc`): µarch model dumps, bogus names,
  intrinsics catalogue counts and feature/class filters, lane semantics for
  SSE2/SSSE3/AVX2/FMA/AVX-512/BMI/GFNI/AES/CLMUL, mca across µarchs,
  loop mca, `cost` across models, malformed intrinsics, free-variable mca.
* 6 MCP goldens `mcp_*.jsonl` + `mcp_*.out`:
  `mcp_x86_models` (10 calls), `mcp_x86_intrinsics` (18),
  `mcp_x86_mca` (25), `mcp_x86_errors` (19),
  `mcp_x86_mca_inline` (6 — documents finding 1),
  `mcp_x86_stress` (150 mca calls / 30 functions x 4 µarchs).
* 1 MCP reproducer kept **without** a golden `.out`:
  `repro_x86check_mcp.jsonl` (3 x86check calls). One run of it timed out,
  so per the contract it is documented in FINDINGS.md, not used as a golden.
* `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | MCP mca mis-parses inline definitions (=→==), inflating cycles; the unknown-µarch error omits valid zen2. |
| LIMIT | 3 | x86check is dead against host GCC cc; mca silently returns an empty result for undefined functions; model skl {...} overrides cost but not m |
| DETERMINISM | 1 | Under a heavy parallel MCP mca flood the server process exited; likely resource pressure from concurrent subagents (caveat in FINDINGS.md). |

### Issues by severity:

| severity | count | one-line takeaway |
|---|---|---|
| WRONG | 2 | MCP `mca` mis-parses inline definitions (`=`→`==`), inflating cycles; the unknown-µarch error omits valid `zen2`. |
| LIMIT | 3 | `x86check` is dead against host GCC `cc`; `mca` silently returns an empty result for undefined functions; `model skl {...}` overrides `cost` but not `mca`. |
| DETERMINISM | 1 | Under a heavy parallel MCP `mca` flood the server process exited; likely resource pressure from concurrent subagents (caveat in FINDINGS.md). |
| HANG | 0 confirmed standalone | One `x86check avx512` MCP run timed out under load; kept as a reproducer only. |


## Takeaway
the µarch tables and intrinsic lane semantics are internally consistent and deterministic (2585 intrinsics, 120 mca results checked), but the MCP `mca` string-argument path silently returns wrong cycle counts, `x86check` is unusable with the shipped `cc`, and several diagnostics are stale or silent.

### Original takeaway (verbatim)
the µarch tables and intrinsic lane semantics are internally
consistent and deterministic (2585 intrinsics, 120 mca results checked),
but the MCP `mca` string-argument path silently returns wrong cycle counts,
`x86check` is unusable with the shipped `cc`, and several diagnostics are
stale or silent.
