# SUMMARY — `resource_limits_extended`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 4
- Files created: 10

### Scope
OS resource limits beyond virtual memory, applied with `ulimit` and outer `timeout 15`
(12 s for deliberately long searches): `-n` (FDs), `-f` (file size), `-t` (CPU time),
`-u` (processes/forks), `-s` (stack), `-l` (locked memory), `-v` (very tight memory).
Combined with CLI text mode, `--json` (`--files write|base64`), `--mcp` (`--dir`, `--flat`),
plots/GIFs, C-module writes and forked `timeout_s` searches. Binary:
`$ROOT/ucas` (prebuilt; no rebuild, no source/Make/git edits).

### Counts
- **Distinct ucas commands / queries tried:** ~45 (show/range/parse/diff/equiv/find/more/stoke/
  plot/heatmap/animate/c-optimize/define/state plus nested-expression variants at 6 depths).
- **Total bounded invocations:** ~215, of which ~200 ran under a non-default `ulimit`
  (`-f` 44, `-n` 47, `-s` 40, `-v` 35, `-t` 15, `-u` 14, `-l` 8, plus combinations).
- **Frontends covered:** 3 (CLI, `--json`, `--mcp`) × the three relevant limits.
- **Files created (all inside `tests/stress/areas/systems/resource_limits_extended/`):** 10 —
  `01_baseline_ops.ucas/.out`, `02_plot_nofile.ucas/.out`,
  `03_searches_seeded.ucas/.out`, `mcp_limits_baseline.jsonl/.out`, `FINDINGS.md`, `SUMMARY.md`.
  Scratch probes and 4096-byte partial `plot.gif` artefacts were confined to `/tmp/opencode/rlx`.
- **Determinism:** each of the 4 goldens run twice → byte-identical outputs; no golden contains a
  crash, hang or limit-dependent value.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 3 | #1 SIGXFSZ mid-write (partial GIF; JSON/MCP lose reply), #3 MCP dies without timeout_s, #4 SIGKILL under -t |
| HANG | 1 | #2 timeout_s silently ignored when fork fails under -u |
| WRONG | 2 | #2 (no note/rollback when timeout disabled), #5 CPU SIGKILL mislabelled internal (signal 9) |
| LIMIT | 4 | #6 -s overflow thresholds, #7 -n threshold (clean at 3), #8 -l no-op, #9 -v bands across frontends |

### Issues by severity
| Severity | Count | Findings |
|----------|-------|----------|
| CRASH | 3 | #1 SIGXFSZ mid-write (partial GIF; JSON/MCP lose reply), #3 MCP dies without `timeout_s`, #4 SIGKILL under `-t` |
| HANG | 1 | #2 `timeout_s` silently ignored when fork fails under `-u` |
| WRONG | 2 | #2 (no note/rollback when timeout disabled), #5 CPU SIGKILL mislabelled `internal (signal 9)` |
| NLP | 0 | — |
| LIMIT | 4 | #6 `-s` overflow thresholds, #7 `-n` threshold (clean at 3), #8 `-l` no-op, #9 `-v` bands across frontends |
| DETERMINISM | 0 | — |

Non-issues / positive results: `-n 4` still writes a full GIF; `-l` never affects behaviour;
FD/stack/memory failures at the loader boundary are clean (exit 127 / exit 2); no orphaned
children after a `timeout_s` timeout; no hangs outside the documented fork-failure case.


## Takeaway
Resource limits expose two real robustness gaps — a file-size cap kills ucas mid-write leaving a truncated GIF and no protocol reply, and process-limit pressure silently strips the `timeout_s` safety guarantee — while FD/locked-memory/limits otherwise degrade cleanly and CPU/stack/stack caps turn well-formed work into SIGKILL/SIGSEGV at well-defined thresholds documented above.

### Original takeaway (verbatim)
Resource limits expose two real robustness gaps — a file-size cap kills ucas mid-write leaving a
truncated GIF and no protocol reply, and process-limit pressure silently strips the `timeout_s`
safety guarantee — while FD/locked-memory/limits otherwise degrade cleanly and CPU/stack/stack
caps turn well-formed work into SIGKILL/SIGSEGV at well-defined thresholds documented above.
