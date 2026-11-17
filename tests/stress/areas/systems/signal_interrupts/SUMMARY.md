# SUMMARY — `signal_interrupts`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 0
- Files created: not recorded

### Counts

- **Interrupt scenarios executed: 169**
  - 153 in the machine-readable catalog (`driver.py` → `results.jsonl`):
    `cli_signal` 72, `json_signal` 9, `mcp_signal` 9, `json_childkill` 3,
    `mcp_childkill` 3, `json_parentkill` 4, `mcp_parentkill` 4,
    `tstp_cont` 12, `close_stdin` 9, `pty_ctrlc` 16, `double_int` 12.
  - 16 focused probes on a single genuinely long (~12 s) `approx` request with
    `timeout_s: 60` / `3` / `0.02`: server-kill (int term hup), child-kill
    (kill term) in both `--mcp` and `--json`, stdin-close, client-pipe EOF
    timing, orphan lifetime, and corrected CLI stdin-close (3 delays).
- **Distinct query bodies: 6 long-search workloads** (`find`, `gates`, `approx`,
  `fit`, `prove`, `range`) plus 9 request files. The `prove` workload contains
  30,000 syntactically distinct theorems (`q0`…`q29999` with varying exponent and
  coefficient); the other workloads contain 90–30,000 statements each, so the
  catalog exercises tens of thousands of distinct statements, not a single
  repeated query.
- **Signals / interruptions covered:** SIGINT, SIGTERM, SIGHUP, SIGQUIT (probe),
  SIGTSTP+SIGCONT, SIGKILL, stdin EOF, PTY Ctrl-C (`script -qec` and
  `pty.fork`), external child SIGKILL/SIGTERM, rapid double/triple interrupts
  (20 ms gaps).
- **Modes covered:** CLI script file, CLI interactive stdin, `--json --files none`,
  `--mcp` (and the PTY variants of CLI).

### Files created (all inside `tests/stress/areas/systems/signal_interrupts/`)

- `FINDINGS.md`, `SUMMARY.md`
- `reproduce.sh` — tested, copy-pasteable reproducer for every finding plus the
  verified-correct baseline and Ctrl-C check
- `results.jsonl` — 153 scenario records with exact command, delay, exit code,
  timing, child/orphan PIDs, fresh-process check and JSON validity
- `driver.py`, `analyze.py`, `harness.sh`, `reset_exec.py` — the harnesses used
- `scenarios/` — 10 workload/reproducer inputs (`long_*.ucas`,
  `mcp_longapprox.jsonl`, `json_longapprox.jsonl`, `mcp_short_t.jsonl`,
  `mcp_internal_timeout.jsonl`)
- `_scratch/` — raw per-run stdout/stderr (`runs/`), driver log and intermediate
  probes
- No golden `.out` files: every scenario is timing-dependent (which request is
  in flight, how much stdout is flushed at signal time). Per `SPEC.md`, these are
  documented here rather than added as goldens.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 1 | External kill of MCP/JSON server mid-search stalls the client until timeout_s elapses |
| WRONG | 1 | Killing the forked timeout child silently disables timeout_s (search runs unbounded) |
| LIMIT | 2 | External signals orphan the timeout child; closing stdin does not cancel a search |

### Issues by severity

| Severity | Count | Issue |
|----------|-------|-------|
| CRASH | 0 | — |
| HANG | 1 | External kill of MCP/JSON server mid-search stalls the client until `timeout_s` elapses |
| WRONG | 1 | Killing the forked timeout child silently disables `timeout_s` (search runs unbounded) |
| NLP | 0 | — |
| LIMIT | 2 | External signals orphan the timeout child; closing stdin does not cancel a search |
| DETERMINISM | 0 | No golden kept for interrupt cases (timing-dependent, per `SPEC.md`); no nondeterministic *answer* observed |


## Takeaway
CLI, PTY and rapid interrupts are clean (no crash, core, orphan or corrupted output; fresh process always works), but the `--json`/`--mcp` server's forked timeout child is the weak point: killing the parent leaves the client hung and orphans the child, while killing the child silently removes the caller's `timeout_s` protection.

### Original takeaway (verbatim)

CLI, PTY and rapid interrupts are clean (no crash, core, orphan or corrupted
output; fresh process always works), but the `--json`/`--mcp` server's forked
timeout child is the weak point: killing the parent leaves the client hung and
orphans the child, while killing the child silently removes the caller's
`timeout_s` protection.
