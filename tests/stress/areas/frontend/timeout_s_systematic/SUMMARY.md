# SUMMARY — `timeout_s_systematic`

## Counts
- Distinct expressions/queries tried: ~400
- Goldens written: 3
- Files created: not recorded

### Coverage

- **216 request streams** = full cross product of
  `{no timeout, numeric, string, zero, negative, huge}` (6)
  × `{CLI --json, MCP grouped, MCP --flat}` (3)
  × `{single, N-after-timeout, interleaved with define/English, two timeouts in a row,
     timeout then crash, timeout then reset}` (6)
  × 2 repetitions, via `systematic_harness.py`.
  Per stream: one-response-per-request, id correctness, session-state equality, stray children,
  `code == timeout`, and post-timeout canary behaviour. Raw data: `_scratch/results.json`.
- **120 focused desync pairs** (40 per interface) via `repro_desync_systematic.py`, plus a
  timing sweep in `_scratch/hunt_desync.py` (7 settings × 3 op shapes, with/without CPU load).
- **48 family checks** (8 command families × numeric/string timeout × 3 interfaces) via
  `family_timeout_sweep.py`.
- Total distinct requests/streams exercised: **~400**.

Total distinct expressions/queries: **216 streams + 120 desync pairs + 48 family checks ≈ 384**,
plus ~30 exploratory probes in `_scratch/`.

### Files created

| file | purpose |
|---|---|
| `systematic_harness.py` | durable 216-stream measurement harness (fixed, error-free run) |
| `repro_desync_systematic.py` | high-rate desync reproducer for all 3 interfaces |
| `family_timeout_sweep.py` | per-family numeric/string timeout sweep |
| `json_numeric_timeout.jsonl/out` | deterministic golden (CLI `--json`) |
| `mcp_numeric_timeout.jsonl/out` | deterministic golden (MCP grouped) |
| `mcp_flat_numeric_timeout.jsonl/out` + `.flags` | deterministic golden (MCP `--flat`) |
| `FINDINGS.md` | all issues with exact reproducers/output |
| `SUMMARY.md` | this file |
| `_scratch/` | exploratory probes + raw `results.json` (not goldens) |

All three goldens were verified byte-identical across 6 independent runs.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | string timeout_s accepted but silently disables limit (3 interfaces, 8 families) |
| LIMIT | 2 | non-positive/huge timeouts disable limit; stray worker children |

### Issues by severity

| severity | count | summary |
|---|---|---|
| CRASH | 0 | timeout mechanism itself never crashed |
| HANG | 0 (symptom inside LIMIT #2/#3) | string/zero/negative/huge caused unbounded runs |
| WRONG | 1 | string `timeout_s` accepted but silently disables limit (3 interfaces, 8 families) |
| DETERMINISM | 1 (critical) | timeout-child desync, 33-35/40 pairs at `timeout_s:0.0005` in all 3 interfaces |
| LIMIT | 2 | non-positive/huge timeouts disable limit; stray worker children |
| NLP | 0 | — |

Key measurements: 0 id mismatches / 216 streams when the timeout had a comfortable margin
(`gates`, 0.02 s) vs ~85% when `timeout_s` matched the request runtime (`english`, 0.0005 s);
numeric timeouts gave `code:timeout` in 36/36 streams; all 144 non-numeric-timeout streams hung;
session state unchanged in every clean numeric-timeout stream.


## Takeaway
The fork-based `timeout_s` isolation is sound for numeric positive limits with a comfortable margin (correct `code:timeout`, state intact, later calls fine), but it is **not trustworthy**: a timeout near the request's runtime forks a worker whose late duplicate reply desynchronises the whole one-reply-per-request stream of `--json`, MCP grouped and MCP `--flat`; and accepted string/zero/negative/huge values silently remove the limit entirely.

### Original takeaway (verbatim)

The fork-based `timeout_s` isolation is sound for numeric positive limits with a comfortable
margin (correct `code:timeout`, state intact, later calls fine), but it is **not trustworthy**:
a timeout near the request's runtime forks a worker whose late duplicate reply desynchronises the
whole one-reply-per-request stream of `--json`, MCP grouped and MCP `--flat`; and accepted
string/zero/negative/huge values silently remove the limit entirely.
