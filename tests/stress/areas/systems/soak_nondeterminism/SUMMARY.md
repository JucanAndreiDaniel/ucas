# SUMMARY — `soak_nondeterminism`

## Counts
- Distinct expressions/queries tried: ~200
- Goldens written: 286
- Files created: not recorded

### Counts

* **Distinct requests / expressions tried: ~200+**
  - 110 distinct sibling golden files (`.ucas`/`.jsonl`), each containing
    multiple statements, re-run 80× each.
  - 286 goldens discovered and calibrated once (the count grows as sibling
    agents add files).
  - 15 randomness-prone goldens (`find`/`stoke`/`gates`/`approx`/`phash`/SAT)
    probed 10× each.
  - 54 distinct long-lived request templates (29 `--json` + 25 `--mcp`),
    covering definitions, English queries, ambiguity answers, `assume`,
    `reset`, `state` and `timeout_s`; plus 20 distinct stateful-script steps
    (10 per interface) = **74 distinct live request types**.
  - Dedicated minimal reproducers for each issue.

* **Total executions: >17,000**
  - Golden repetition soak: **8,800** (110 cases × 80 runs, each under
    `timeout 15`).
  - Calibration: **286** single runs.
  - Randomness probe: **~140** runs (budget-capped).
  - Live soak: **8,000** main calls (4,000 loop iterations × 2 processes) plus
    **~670** checkpoint canary/stateful calls.
  - Reproducer/characterisation experiments: **~500** calls.

* **Files created (all under `tests/stress/areas/systems/soak_nondeterminism/`):**
  - `soak.py` — the harness (`calibrate`, `golden`, `live`, `report`, `all`).
  - `probe_interfaces.py`, `probe_random_goldens.py` — interface discovery and
    the randomness-target probe.
  - `repro_fd_leak.py`, `repro_timeout_desync.py` — minimal reproducers.
  - `FINDINGS.md`, `SUMMARY.md`.
  - `soak_golden.jsonl`, `soak_live.jsonl`, `soak_findings.json` — raw logs.
  - `work/calibration.json`, `work/golden/` (read-only staging copies of inputs
    and `.out` snapshots), `work/golden_run.log`, `work/live_run.log`.

* **Issues by severity:**
  - `DETERMINISM` — **1** (timeout response-stream desync; findings 1 & 3:
    113 canary-drift + 190 stateful-drift events, 20 ok-flapping tags,
    58/60 JSON and 51/60 MCP timeout pairs desynced, leaked worker child).
  - `LIMIT` — **3** (FD leak per reset; leaked timeout child; heavy SAT timing
    variance near the 15 s threshold).
  - `CRASH` — **0**. `HANG` — **0** (only the borderline-SAT LIMIT above).
  - `WRONG` — subsumed by finding 1 (pure `bigint` returned `ok:false`);
    no unsound proof/range/witness found. `NLP` — **0**.

### Conformance

Siblings were read only — golden inputs and `.out` files were copied into
`work/golden/` and all executions used those copies as the working directory,
so no sibling folder was modified. No source file, Makefile, existing test,
`opencode.json` or git state was touched; no rebuild and no git commands were
run. Every subprocess run was bounded by `timeout 15`, and all processes
started by the harness were closed/reaped.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 3 | — |
| DETERMINISM | 1 | — |

## Takeaway
the goldens are solid, but a long-lived session is not: `timeout_s` forks a worker that is never killed and whose late output desynchronises the one-reply-per-request stream, so a pure command can flip `ok` and answers depend on call order; separately, every `reset` leaks one file descriptor.

### Original takeaway (verbatim)
the goldens are solid, but a long-lived session is not: `timeout_s`
forks a worker that is never killed and whose late output desynchronises the
one-reply-per-request stream, so a pure command can flip `ok` and answers depend
on call order; separately, every `reset` leaks one file descriptor.
