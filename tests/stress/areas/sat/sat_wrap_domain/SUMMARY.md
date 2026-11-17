# SUMMARY — `sat_wrap_domain`

## Counts
- Distinct expressions/queries tried: 340
- Goldens written: 13
- Files created: not recorded

### Counts

- Distinct expressions/queries tried: **~340** (263 statements in the 13 CLI goldens plus
  22 tool calls in the 2 MCP goldens, ~13 exploratory batches, a fuzz sweep of 35 one-shot
  programs, and ~15 Python cross-checked i8 `wrap` cases).
- Files written:
  - 13 CLI goldens: `01_i8_wrap` … `13_piecewise_wrap` (`.ucas` + `.out`).
  - 2 MCP goldens: `mcp_wrap_domain_range.{jsonl,out}` and
    `mcp_flags_flat.{jsonl,out,flags}` (the latter uses `--flat`).
  - 2 crash reproducers with **no** `.out` (per contract):
    `repro_crash_int64min.ucas`, `repro_crash_int64min.jsonl`.
  - `FINDINGS.md`, `SUMMARY.md`.
  - All 15 goldens ran twice with identical bytes (deterministic); exit 0; each under 15 s.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | Constant INT64_MIN / -1 SIGFPEs the process (CLI and MCP). |
| WRONG | 4 | i64 wrap end-to-end always 0 mismatches; i64 range "proved" max 2^63 unreachable; u64→f32/f64 bogus 1.84e19 rel error; equiv with undefined  |
| NLP | 1 | English "wrap x plus one for a signed byte x" -> "sorry: of what?". |
| LIMIT | 1 | Shared in-process MCP server keeps global definitions and can exit; use isolated --mcp < file runs. |
| DETERMINISM | 1 | Shared in-process MCP server keeps global definitions and can exit; use isolated --mcp < file runs. |

### Issues by severity

| Severity | Count | Short description |
|----------|-------|-------------------|
| CRASH    | 1     | Constant `INT64_MIN / -1` SIGFPEs the process (CLI and MCP). |
| WRONG    | 4     | i64 `wrap` end-to-end always 0 mismatches; i64 `range` "proved" max 2^63 unreachable; u64→f32/f64 bogus 1.84e19 rel error; `equiv` with undefined name says "equal". |
| NLP      | 1     | English "wrap x plus one for a signed byte x" -> "sorry: of what?". |
| DETERMINISM/LIMIT | 1 | Shared in-process MCP server keeps global definitions and can exit; use isolated `--mcp < file` runs. |


## Takeaway
`wrap`/`domain`/`range` are solid for i8–i32, floats and bit casts, but the **i64 "ideal twin is int" design makes i64 `wrap` end-to-end blind to signed overflow and gives i64 `range` an unreachable 2^63 "proved" maximum, while a constant INT64_MIN/-1 kills the process**.

### Original takeaway (verbatim)

`wrap`/`domain`/`range` are solid for i8–i32, floats and bit casts, but the **i64 "ideal twin is
int" design makes i64 `wrap` end-to-end blind to signed overflow and gives i64 `range` an
unreachable 2^63 "proved" maximum, while a constant INT64_MIN/-1 kills the process**.
