# SUMMARY — `mcp_codemode_schemas`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 11
- Files created: 24

### Counts

- **Distinct tool-call / protocol requests tried:** ~690
  - 239 group-op calls with empty args (`mcp_all_ops.jsonl`)
  - 239 group-op calls with type-appropriate required args (exploratory)
  - 27 empty-arg calls (all tools), 45 required-only calls, 27 extra-arg calls,
    45 wrong-typed calls, 11 name/case variants
  - 11 cross-layer MCP-vs-JSON pairs, 6 `tools/call` param variants, 8
    doc-vocabulary probes, 6 `tools/list` variants, 5 flat-mode calls
- **Catalog entries examined:** 27 MCP tools; 248 flat tools; 248 `session
  schema` commands; 239 group `op` enum values + 9 standalone tools
- **Files created:** 24 in this folder
  - 11 `.jsonl` goldens + 11 `.out` goldens
  - 2 `.flags` files (`--flat`): `mcp_flat_calls.flags`, `mcp_flat_catalog.flags`
  - `FINDINGS.md`, `SUMMARY.md`
- **Determinism:** every golden run twice, byte-identical. No golden retained
  for a crash/hang/nondeterministic case (none was observed).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 3 | extra top-level args ignored by grouped tools (declared additionalProperties:false unenforced); skill's x86 models op does not exist (x86_mo |

### Issues by severity

| Severity | Count | Summary |
|----------|-------|---------|
| CRASH | 0 | — |
| HANG | 0 | — |
| WRONG | 0 | — |
| NLP | 0 | — |
| DETERMINISM | 0 | — |
| LIMIT | 3 | extra top-level args ignored by grouped tools (declared `additionalProperties:false` unenforced); skill's `x86 models` op does not exist (`x86_models`); README tool/op table stale |


## Takeaway
The MCP catalog is complete and internally consistent (all 248 commands callable, `structuredContent` == JSON frontend, envelopes and protocol-version gating correct, fully deterministic); the only defects are schema-enforcement and documentation drift around extra args and a few advertised tool/op names.

### Original takeaway (verbatim)

The MCP catalog is complete and internally consistent (all 248 commands callable,
`structuredContent` == JSON frontend, envelopes and protocol-version gating
correct, fully deterministic); the only defects are schema-enforcement and
documentation drift around extra args and a few advertised tool/op names.
