# SUMMARY — `c_vectorize_loops`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 17
- Files created: 38

### Scope
C frontend loop / vectorisation paths on the CLI (`c lower`, `c optimize`, `c targets`,
`vectorize`, `nofile`, `target`, `assume`, `check`, `bench`, `wrapv`, `engines`) and the
MCP `c` tool.  Categories covered: induction variables, closed-form reductions, nested
loops, strided access, strlen-style scans, memcpy/memset patterns, pointer aliasing and
overlap tests, loop-carried dependence, variable trip counts, early exits
(`break`/`continue`/`return`), multi-dimensional arrays, float/double accumulations,
polynomial sums proved by induction, all targets, and malformed loop C.

### Counts
- Distinct C snippets / queries tried: **~220**
  - 86 broad probe snippets (`hunt.py`)
  - 27 differential `check` probes (`diffhunt.py`)
  - 20 malformed-loop parser probes
  - 29 functions in the committed goldens
  - ~40 one-off minimisation/edge probes and 16 MCP calls
- Files written: **38** in this folder
  - 17 CLI goldens (`01_…` … `17_…`: `.ucas` + `.out`)
  - 1 MCP golden (`mcp_c.jsonl` + `mcp_c.out`)
  - `FINDINGS.md`, `SUMMARY.md`
- All 18 goldens were run twice and byte-for-byte diffed: **all deterministic**.
  No crash/hang/nondeterministic case was added as a golden.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | F1 — SIGFPE in c optimize (find engine) on signed-64-bit element-wise loops; also kills MCP server |
| HANG | 1 | F2 — check harness with unbounded inner-loop trip count (nest2) |
| WRONG | 1 | F3 — assume emits unchecked out-of-range table read; check ignores assumption (16 620 false mismatches) |
| LIMIT | 4 | F7 (MCP error text printed twice) |
| DETERMINISM | 1 | F8 — early return in a loop reports a varying unrolled-operation count |

### Issues by severity
| severity | count | ids |
|----------|-------|-----|
| CRASH | 1 | F1 — SIGFPE in `c optimize` (`find` engine) on signed-64-bit element-wise loops; also kills MCP server |
| HANG | 1 | F2 — `check` harness with unbounded inner-loop trip count (`nest2`) |
| WRONG | 1 | F3 — `assume` emits unchecked out-of-range table read; `check` ignores assumption (16 620 false mismatches) |
| LIMIT | 3 | F4 (`check` needs clang, fails with GCC `cc`), F5 (`c lower` ignores `assume`), F6 (MCP `c_lower` rejects `nofile`) |
| LIMIT (minor) | 1 | F7 (MCP error text printed twice) |
| DETERMINISM | 1 | F8 — early `return` in a loop reports a varying unrolled-operation count |


## Takeaway
The induction prover and lane-based vectoriser are sound on the exercised domain (float reductions and dependent/strided loops are correctly refused, closed forms differentially verified), but the C frontend has one deterministic SIGFPE in the `find` engine for signed-64-bit element-wise loops, a `check` harness that hangs on nested loops with large inner trip counts, and `assume`/`check` that do not compose.

### Original takeaway (verbatim)
The induction prover and lane-based vectoriser are sound on the exercised domain
(float reductions and dependent/strided loops are correctly refused, closed forms
differentially verified), but the C frontend has one deterministic SIGFPE in the
`find` engine for signed-64-bit element-wise loops, a `check` harness that hangs on
nested loops with large inner trip counts, and `assume`/`check` that do not compose.
