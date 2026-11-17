# SUMMARY — `numeric_arg_overflow`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 11
- Files created: 30

### Original preamble

**Focus:** unchecked numeric parsing (bare `atoi`/`strtol`/`strtoll`, missing `ERANGE`,
unchecked `(int)` casts) and the resource asymmetry those values create — plus the
JSON/MCP number path that echoes non-finite tokens verbatim. Ideas 1, 4, 5, 7 and 10 of
`IDEAS_SOURCE.md` were read as background; the concrete work followed the FOCUS brief.

### Counts

- **~300 distinct cases / queries tried**, across quick CLI probes (`-e`), multi-line
  `.ucas` sessions, MCP `--mcp` JSONL calls, `--json` calls and the `ucas` escape-hatch tool:
  - `abselftest N` for N = 0, ±1, ±5, 1, 2, 3, 5, 10, 42, 100, 1000, 10000, `+7`,
    `010`, `0x10`, `12junk`, `abc`, empty, `INT_MIN`, `INT_MAX±1`, `2^64-1`,
    `99999999999999999999999` and `2147483647`;
  - real/FP literals `1e400`, `-1e400`, `1e309`, `1e9999`, `1e-400`, `f32/f64(1e400)`,
    `3.5e38`, plus ~15 arithmetic/comparison contexts on overflowed literals;
  - `diophantine` on two base equations (rank 0 and rank 1) with `count`, `search`,
    `maxmult` = −5/−1/0/1/2/5/60/200/2000000000/`INT_MAX`/`9999999999999999999999`/
    trailing-junk, singly and combined;
  - `table max`, `find N`, `find max`, `find -1/INT_MIN/u64-max`, `stoke` steps/restarts/
    len/seed, `fit` pseudo-options, `approx` list/degree/budget/seed, `tcdot n/samples/
    seed`, both CLI and MCP `--mcp`/`--json` forms;
  - MCP ids `1e400`, `-1e400`, `1E+400`, `1e9999`, `99999999999999999999999`, `1e-400`,
    `-0.0`, `1.5e400`, `0e9999`, `1e1000000` on initialize, tools/call and `--json`;
  - `ucas` raw tool with/without `timeout_s` around the `abselftest` hang.
- **Files written: 30** — 11 CLI golden pairs (`01_`…`11_`), 3 MCP golden pairs
  (`mcp_id_infinity`, `mcp_numeric_args`, `mcp_ucas_timeout`), plus `FINDINGS.md` and this
  `SUMMARY.md`.
- **Issues by severity:** 2 HANG, 0 CRASH, 7 WRONG, 3 LIMIT, 0 DETERMINISM.
- Every golden was generated from its own folder under `timeout 30`, run twice and
  byte-compared: all 14 outputs are byte-identical. Slow/load-sensitive cases
  (`count 2147483647`, `approx` searches) were deliberately **not** kept as goldens and
  are described in FINDINGS.md instead.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 2 | — |
| WRONG | 7 | — |
| LIMIT | 3 | — |

## Takeaway
Numeric option parsing is the weak point: negative, overflowing and junk values are silently clamped, ignored or reinterpreted (`abselftest`, `table max`, `find N`, `diophantine count/search/maxmult`, real literals, `fit` pseudo-options), and JSON/MCP echoes non-finite id tokens as bare `1e400`.

### Original takeaway (verbatim)

Numeric option parsing is the weak point: negative, overflowing and junk values are
silently clamped, ignored or reinterpreted (`abselftest`, `table max`, `find N`,
`diophantine count/search/maxmult`, real literals, `fit` pseudo-options), and JSON/MCP
echoes non-finite id tokens as bare `1e400`. Two genuine unbounded-resource commands were
found — `abselftest 2147483647` (never returns, even through the MCP raw tool) and
`diophantine ... search 9999999999999999999999` (saturates `strtoll` and never finishes);
`diophantine ... count 2147483647` finishes but dumps ~394 KB / 360 solutions in ~10 s.
`stoke`, `tcdot` and the JSON numeric-argument validators are the clean positive controls.
No crashes were observed.
