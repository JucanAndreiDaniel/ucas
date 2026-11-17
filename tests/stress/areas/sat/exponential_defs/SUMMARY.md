# SUMMARY — `exponential_defs`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 13
- Files created: 34

### Original preamble

**Focus:** definition-chain fan-out and recursion-depth crashes (IDEAS_UNDERGROUND idea 1).

### Counts

- **296 systematically generated cases** (`generated_cases.tsv`): width 1–4 × depth 1–16 ×
  type {u8, i32, u64, real}, plus 40 base-expression variants; 94 of them crashed (SIGSEGV),
  0 timeouts in that batch.
- **~120 additional characterization probes**: depth sweep, width sweep, 13-type sweep,
  base-expression sweep, 12-command × 2-depth call-context matrix, leaf-count boundary
  (30+ points), stack-limit matrix, mutual recursion, state tests, and wire (MCP/JSON)
  containment. Total executions ≈ **420**, covering **200+ distinct source shapes/queries**.
- **Files created: 34** in this folder:
  - 10 CLI goldens (`NN_*.ucas` + `NN_*.out`) — all deterministic (run twice, `diff` clean).
  - 3 MCP goldens (`mcp_*.jsonl` + `mcp_*.out`) — all deterministic.
  - 5 crash reproducers (`crash_*.ucas`, source only, deliberately no `.out`).
  - `generated_cases.tsv`, `FINDINGS.md`, `SUMMARY.md`.

### Key thresholds

- Width 2 → first crash at depth **14**; width 3 → **9**; width 4 → **7**; width 1 → not by depth 2000. `bool` width 2 → **13**.
- On 8 MB stack the boundary is ~**16346** fully inlined `f0` applications; 16 MB stack survives depth 14 but not 15; 32 MB survives 14–16.
- All integer/float/real types crash at the same depth; `bool` one earlier. Constant/identity bases (`x`, `1`, `-x`) never crash.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 3 | — |
| WRONG | 1 | — |
| LIMIT | 1 | — |

### Issues by severity

| Severity | Count | One-line summary |
|---|---|---|
| CRASH | 3 | depth-14 doubling chain → SIGSEGV rc 139 (stack overflow at ~16346 nested calls on 8 MB stack); only full-unrolling commands (`show F(0)`, `parse`, `equiv`, `diff`) trigger it; `--mcp`/`--json` servers die too |
| HANG / LIMIT | 1 | `find f13` >30 s (0.13 s for a simple `x+1`), `wrap f13` ~10 s, `wrap f14` >15 s |
| STATE / WRONG | 1 | rejected self-referential definition leaves a fabricated `_(f: real) = f`; `range f` then returns a bogus `[-10, 10]` |
| PROTO | (folded into CRASH) | `timeout_s:3` contains the crash with `internal: the evaluation crashed (signal 11)`; default requests do not |


## Takeaway
The evaluator recursively inlines definition chains without any depth or node budget, so a 15-line fan-out program overflows the 8 MB stack (SIGSEGV); the crash also kills the default MCP/JSON server, and is only contained when the caller opts into `timeout_s` (forked child).

### Original takeaway (verbatim)

The evaluator recursively inlines definition chains without any depth or node budget, so a
15-line fan-out program overflows the 8 MB stack (SIGSEGV); the crash also kills the default
MCP/JSON server, and is only contained when the caller opts into `timeout_s` (forked child).

### Confinement:
all files were created under `$ROOT/tests/stress/areas/sat/exponential_defs/`;
scratch files used `/tmp/opencode/` only. No source, Makefile, test, or shared file was modified;
no `make`, `git`, or rebuild was run; all runs were `timeout`-bounded and no stray processes were left.
