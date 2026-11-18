# SUMMARY — `c11ub_correctness`

## Counts

- Distinct C snippets tried during development: ~50 (probes plus the
  functions in the nine goldens).
- Goldens written: 9 CLI pairs (`01_unsequenced` … `09_call_args`) and
  1 MCP pair (`mcp_c11ub.jsonl` / `.out`). `08_assign_rhs_read` and
  `09_call_args` were added for the two audit fixes (see `FINDINGS.md`).
- Files created: 9 `.ucas`, 9 `.out`, 1 `.jsonl`, 1 `.out`, `FINDINGS.md`,
  `SUMMARY.md`.

## Issues by severity

| Severity | Count | Headline |
|----------|-------|----------|
| UB newly modeled | 6 | unsequenced access; OOB subscript; uninitialised local; value-return fall-through; float-cast check in `cf_check`; unspecified-order disclosure |
| WRONG | 0 | no new wrong answers found |
| LIMIT | 4 | pointer/alignment/volatile/atomic/library categories are not reachable in ucas's C subset |

## Takeaway

The reachable part of the C11 core-language UB list is now a domain condition
or an explicit refusal in ucas's C frontend. Unsequenced access to one object
(undefined) refuses the lowering with a `requires` note; two effects on
different objects (unspecified) are lowered with a `requires` note instead of
a silently chosen order. All earlier UB conditions are preserved. Existing
goldens in `cfront_ub_contracts` and `cfront_float_semantics` were not edited;
the two that need recapture are listed in `/tmp/opencode/PAPER_C11UB.md`.
