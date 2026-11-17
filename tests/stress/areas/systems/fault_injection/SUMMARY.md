# SUMMARY — `fault_injection`

## Counts
- Distinct expressions/queries tried: 346
- Goldens written: 2
- Files created: not recorded

### Coverage

- **Distinct commands / queries tried: 346**
  - 154 CLI corpus commands (`corpus/c001..c154.ucas`)
  - 156 MCP `--flat` calls (`mcp_corpus_flat.jsonl`)
  - 14 CLI baseline golden statements, 4 MCP flat golden calls
  - 5 + 4 + 4 focused MCP calls (timeout / crash / inline fixtures),
    3 file-writing commands, 1 JSON plot call, 1 adamfit TMPDIR call
- **Executions:** 5,236 CLI corpus runs (154 commands × 10 shims × several call
  indices) + MCP/JSON/fixture runs; every run bounded by `timeout 5..20`.
  Tallies: `matrix_results.txt`, `matrix_stdout.txt`.
- **Shims built** (`shim.c` → `fi_shim.so`): `malloc`, `calloc`, `realloc`,
  `strdup`, `fork`, `pipe`, `pipe2`, `waitpid`, `fopen`, `fopen64`, `open`,
  `open64`, `fwrite` — each fails the Nth call, configurable by env var.
- **Environmental faults:** read-only cwd, unwritable / nonexistent TMPDIR.
- **Determinism:** both kept goldens (`01_baseline`, `mcp_flat_baseline`) run
  twice and diffed byte-identical. The waitpid-bogus-signal case is explicitly
  nondeterministic and is documented, not kept as a golden.

### Files created

- `shim.c`, `fi_shim.so` — the fault-injection library and its source
- `gen_corpus.py`, `corpus/c001..c154.ucas`, `corpus/manifest.txt` — 154-command corpus
- `run_matrix.py`, `matrix_results.txt`, `matrix_stdout.txt` — evidence collector + results
- `01_baseline.ucas` / `.out`, `mcp_flat_baseline.jsonl` / `.out` / `.flags` — deterministic goldens
- `mcp_timeout_base.jsonl`, `mcp_crash_base.jsonl`, `mcp_inline_base.jsonl`,
  `mcp_corpus_flat.jsonl` / `.flags` — MCP fault fixtures
- `filewrite.ucas`, `adamfit_tmp.ucas` — file-write / TMPDIR fixtures
- `run_fault_injection.sh` — self-contained regression harness for the graceful paths (passes)
- `FINDINGS.md`, `SUMMARY.md`

All files live only in `tests/stress/areas/systems/fault_injection/`; no source file, Makefile,
existing test, or shared file was modified.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 2 | CRASH-1 (unchecked malloc → SIGSEGV), CRASH-2 (unchecked strdup → SIGSEGV) |
| WRONG | 2 | WRONG/DETERMINISM-1 (bogus waitpid signal), WRONG-2 ("wrote" on failed write) |
| LIMIT | 3 | LIMIT-1 (timeout silently ignored on fork/pipe failure), LIMIT-2 (partial file left on fwrite failure), LIMIT-3 (no MCP isolation for non-ti |
| DETERMINISM | 1 | WRONG/DETERMINISM-1 (signal number varies per run) |

### Issues by severity

| Severity | Count | IDs |
|---|---|---|
| CRASH | 2 | CRASH-1 (unchecked malloc → SIGSEGV), CRASH-2 (unchecked strdup → SIGSEGV) |
| WRONG | 2 | WRONG/DETERMINISM-1 (bogus waitpid signal), WRONG-2 ("wrote" on failed write) |
| DETERMINISM | 1 | WRONG/DETERMINISM-1 (signal number varies per run) |
| LIMIT | 3 | LIMIT-1 (timeout silently ignored on fork/pipe failure), LIMIT-2 (partial file left on fwrite failure), LIMIT-3 (no MCP isolation for non-timeout requests) |


## Takeaway
The clean `ucas: out of memory` path works for calloc/realloc and *some* malloc sites, but unchecked raw `malloc`/`strdup` allocations crash outright; MCP keeps serving through fork/pipe/waitpid faults yet silently drops the caller's timeout and can report a fabricated crash signal, while failed file writes leave zero-byte artifacts and still claim "wrote".

### Original takeaway (verbatim)

The clean `ucas: out of memory` path works for calloc/realloc and *some* malloc
sites, but unchecked raw `malloc`/`strdup` allocations crash outright; MCP keeps
serving through fork/pipe/waitpid faults yet silently drops the caller's timeout
and can report a fabricated crash signal, while failed file writes leave zero-byte
artifacts and still claim "wrote".
