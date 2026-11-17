# SUMMARY — `schema_conformance`

## Counts
- Distinct expressions/queries tried: 164
- Goldens written: 386
- Files created: not recorded

### Counts
- Distinct requests tried: **164** curated commands covering all **27** tool
  families (every op family at least once; many ops individually), plus
  ~40 targeted error/id/edge probes — **~205 distinct requests** across
  exploration.
- Replies collected and checked: **~730** during exploration; **386** in the
  committed goldens (all pass `schema_check.py --all` with 0 issues).
- Determinism: every golden re-run byte-identical; 0 nondeterministic files.
- Issues by severity: `CRASH` 0, `HANG` 0, `WRONG` 0, `NLP` 0,
  `DETERMINISM` 0, **`LIMIT` 2** (cross-layer id gating + pre-envelope op
  validation; see FINDINGS.md).

### Files created
- `schema_check.py` — reusable Python envelope schema-checker (documented
  vocabularies, type checks, `ok`/`error` and `structured`/`result` invariants,
  MCP `isError` and `structuredContent.id` echo checks).  Run:
  `python3 schema_check.py --all` or `python3 schema_check.py FILE.out ...`.
- Goldens (JSON Lines frontend, run with `--json --files none`):
  - `json_envelope_01..09.jsonl` + `.out` — 164 commands in 9 files of ≤20,
    covering all families; ids include string / null / large / negative.
  - `json_errors.jsonl` + `.out` — 43 replies exercising
    `bad_json`, `bad_request`, `unknown_command`, `parse_error`, `domain_error`,
    `unsupported`, `failed`, `timeout`, `not_understood`, `ambiguous`, and
    `assumed`/`default`/`rule`/`info` note kinds.
  - `json_ids.jsonl` + `.out` — id echo for string/float/bool/negative/huge/
    array/object ids.
- Goldens (MCP stdio frontend, run with `--mcp`):
  - `mcp_envelope_01..09.jsonl` + `.out` — the same 164 commands as tools/calls.
  - `mcp_errors.jsonl` + `.out` — tool-level error envelopes (`isError:true`),
    checking error prefix text, `pos`, `key`, `readings`, `how`.
  - `mcp_ids.jsonl` + `.out` — MCP id echo for valid id types.
- `_scratch/` — generator (`gen.py`) and probe inputs used during exploration.
- `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 2 | — |

## Takeaway
The ucas reply envelope is schema-clean across all 27 command families and both frontends (386/386 goldens pass, fully deterministic); the only deviations are two intentional cross-layer/protocol limits where the MCP transport rejects ids or ops before a typed envelope is produced.

### Original takeaway (verbatim)
The ucas reply envelope is schema-clean across all 27 command families and both
frontends (386/386 goldens pass, fully deterministic); the only deviations are
two intentional cross-layer/protocol limits where the MCP transport rejects ids
or ops before a typed envelope is produced.
