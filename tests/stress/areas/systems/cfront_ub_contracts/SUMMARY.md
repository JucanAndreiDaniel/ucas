# SUMMARY — `cfront_ub_contracts`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 14
- Files created: 14

### Counts

- **Distinct C snippets / queries tried:** 172 distinct C function bodies, plus 18 MCP
  `c` tool calls and multiple `assume`/`wrapv`/target option combinations. Every run was
  bounded with `timeout` (5–35 s). All candidate goldens were run twice and `diff`ed;
  only deterministic outputs were kept (all kept goldens were identical across runs).
- **Files created (14 goldens + 5 docs/reproducers):**
  - CLI goldens (`.ucas` + `.out`): `01_signed_overflow`, `02_unsigned_wrap`,
    `03_shift_ub`, `04_divzero`, `05_div_intmin`, `06_f2i`, `07_seq_uninit`,
    `08_memory`, `09_wrapv`, `10_assume_narrow`, `11_assume_empty`,
    `12_assume_wrapv`, `13_ub_no_rewrite` (13 pairs).
  - MCP golden: `mcp_c_ub.jsonl` + `mcp_c_ub.out` (1 pair).
  - Durable crash/hang reproducers (no `.out`, deliberately): `repro_crash_int64min.ucas`,
    `repro_hang_int64min.ucas`.
  - `FINDINGS.md`, `SUMMARY.md`.
- **Issues by severity:** CRASH 1, HANG 1, WRONG 2 (reversed-assume unconditional rewrite;
  division-by-zero missing from domain condition), LIMIT 3 (shift-count UB missing,
  sequence-point UB ignored, constant float-to-int UB missing). Total 7.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| HANG | 1 | — |
| WRONG | 2 | — |
| LIMIT | 3 | — |

## Takeaway
The signed-overflow, `INT_MIN/-1`, `assume`-narrowing and `wrapv` contracts are handled correctly, but the C frontend's UB-domain reporting is incomplete for division by zero and oversized/negative shifts, an empty (`LO > HI`) assume still emits a wrong rewrite, and an `INT64_MIN` assume lower bound crashes or hangs `c optimize`.

### Original takeaway (verbatim)

The signed-overflow, `INT_MIN/-1`, `assume`-narrowing and `wrapv` contracts are handled
correctly, but the C frontend's UB-domain reporting is incomplete for division by zero
and oversized/negative shifts, an empty (`LO > HI`) assume still emits a wrong rewrite,
and an `INT64_MIN` assume lower bound crashes or hangs `c optimize`.

### Confirmation

All work stayed inside `tests/stress/areas/systems/cfront_ub_contracts/`. No source file, Makefile,
existing test, `opencode.json`, or other subagent's folder was modified; no `make`,
`git`, or commit was run. Stray processes were bounded by `timeout`.
