# SUMMARY — `concurrent_clients`

## Counts
- Distinct expressions/queries tried: 140
- Goldens written: 2
- Files created: not recorded

### What was exercised
- Interleaving and state isolation for multiple clients of one long-lived
  `ucas --mcp` process, and concurrent `--json` CLI runs sharing `--dir`.
- 2–4 Python client threads, a few dozen requests per run, all under `timeout 15`.
- Distinct expressions/queries tried: **~140** (unique `algebra/expand` marker
  expressions across id_echo ×3, 4-client run, large_interleave ×3, dup_id,
  longshort, plus state/define/assume/reset, stoke, plot, parse and init calls).

### Files created
- `harness.py` — reusable multi-client correctness harness (11 experiments).
- `mcp_id_echo.jsonl` + `mcp_id_echo.out` — deterministic golden, 8 distinct
  ids/markers, 0 crossed.
- `mcp_state_share.jsonl` + `mcp_state_share.out` — deterministic golden,
  define → observe → assume → reset → observe.
- `shdir/` — scratch directory used by the `--dir` experiments.
- `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 4 | — |

### Issues by severity
- CRASH: 0
- HANG: 0
- WRONG: 0
- NLP: 0
- DETERMINISM: 0 (both goldens diff clean across two runs)
- **LIMIT: 4** (process-global state; single-threaded head-of-line blocking;
  id collision / no per-client channel; large-write robustness note)


## Takeaway
The engine behaves correctly under interleaving — every reply carries the right id and no answer is crossed when clients demultiplex by id — but one `--mcp` process is a single shared, single-threaded session: state is global, `reset` is global, and a long request blocks every other client, so true client isolation requires separate processes and globally unique ids.

### Original takeaway (verbatim)
The engine behaves correctly under interleaving — every reply carries the right
id and no answer is crossed when clients demultiplex by id — but one `--mcp`
process is a single shared, single-threaded session: state is global, `reset`
is global, and a long request blocks every other client, so true client
isolation requires separate processes and globally unique ids.

### Confirmation
All files written only under `tests/stress/areas/frontend/concurrent_clients/`; no source,
Make, existing test, or `opencode.json` edits; no `git`/`make` commands; every
server run bounded by `timeout`; harness left no stray processes.
