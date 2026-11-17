# SUMMARY — `mcp_resources_prompts`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 9
- Files created: 9

### Original preamble

**Area:** the MCP surface other than tools (resources, prompts, completion,
logging, notifications, ping, tools/list cursors).

### Counts

- **JSON-RPC messages tried:** ~850 exploratory + **151 durable** in goldens
  (≈1000 total). All runs bounded by `timeout 15`.
- **Distinct cases:** 33 resource URIs, 29 prompt-name/argument variants,
  19 cursor values, 17 list-method/cursor combinations, 12 notification methods,
  8 log levels, 4 completion/subscribe method variants, 8 id types, 6 parse-error
  triggers, plus catalog/liveness/state-cross-checks (~180 distinct probes).
- **Files created:** 9 `mcp_*.jsonl` + 9 `mcp_*.out` goldens, `FINDINGS.md`,
  `SUMMARY.md` (20 files total).
- **Issues by severity:** WRONG 1, LIMIT 1, CRASH 0, HANG 0, DETERMINISM 0.
  (No new bug classes: the WRONG is the same NUL root cause as
  `mcp_api_fuzz` finding 2, here confirmed on resources/prompts/cursors; the
  LIMIT is strict JSON handling.)


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| LIMIT | 1 | — |

### Goldens (all deterministic, exit 0 under `timeout 15`)

| file | msgs | purpose |
|---|---|---|
| `mcp_resource_list.jsonl` | 21 | `resources/list`, `resources/templates/list`, `tools/list`, `prompts/list` with cursors |
| `mcp_resource_read.jsonl` | 22 | valid/invalid/wrong-typed/missing URIs |
| `mcp_resource_schema.jsonl` | 4 | large `ucas://schema` resource (determinism) |
| `mcp_prompts_list_get.jsonl` | 28 | prompts list/get, valid/invalid names & arguments |
| `mcp_ping_ids.jsonl` | 17 | ping params & id echo (string/float/large/negative ids) |
| `mcp_unsupported.jsonl` | 20 | completion/logging/subscribe/unsubscribe/unknown → -32601 |
| `mcp_notifications.jsonl` | 21 | notification silence + post-burst liveness |
| `mcp_parse_errors.jsonl` | 10 | NUL + duplicate-key parse errors, server stays alive |
| `mcp_state_resource.jsonl` | 8 | `ucas://state` reflects define/reset |

### Issues (one-line reproducer each)

1. **WRONG** — legal `\u0000` in a URI/prompt-name/argument/cursor returns
   `-32700 parse error` with `id: null`:
   `timeout 15 $ROOT/ucas --mcp < tests/stress/areas/frontend/mcp_resources_prompts/mcp_parse_errors.jsonl`
2. **LIMIT** — duplicate JSON object keys are rejected as `-32700` with
   `id: null` (same golden, ids 5–6).


## Takeaway
The advertised resources/prompts surface is implemented, correct in shape and error codes, stable under 1000+ messages, and has **no crashes, hangs, or capability mismatches**; its only defects are the shared `\u0000` parse-error / id-loss bug and strict rejection of duplicate JSON keys.

### Original takeaway (verbatim)

The advertised resources/prompts surface is implemented, correct in shape and
error codes, stable under 1000+ messages, and has **no crashes, hangs, or
capability mismatches**; its only defects are the shared `\u0000` parse-error /
id-loss bug and strict rejection of duplicate JSON keys.

### Folder confinement:
all files written only under
`tests/stress/areas/frontend/mcp_resources_prompts/` (plus throwaway scratch under
`/tmp/opencode/mrp/`); no source, Makefile, test, or `opencode.json` edits;
no `make`/`git`; no other subagent's folder touched.
