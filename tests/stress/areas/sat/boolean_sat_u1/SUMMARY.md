# SUMMARY — `boolean_sat_u1`

## Counts
- Distinct expressions/queries tried: 460
- Goldens written: 51
- Files created: 105

### Coverage / counts

- **Distinct expressions / queries tried:** ~460
  - 348 oracle-verified CLI cases in `01_cases.ucas` … `44_cases.ucas`
    (all 2 one-input, all 16 two-input and all 256 three-input Boolean truth tables,
    9 named 3-input gates, 26 De Morgan / absorption / distributivity / XOR / consensus /
    majority identities, 9 MUX identities incl. 3 symbolic computed conditions, 4 chained
    comparisons, 15 coercion tables, 3 cross-type equiv, 8 one-bit `range` probes).
  - 32 oracle-verified CLI coercion / cross-type / partial-domain cases in `b2_01`…`b2_04`.
  - 23 MCP `analyze` calls (11 `equiv`, 4 `table`, 3 `gates`, 5 `parse`) + 26 `session define`
    in `mcp_bool_sat.jsonl`.
  - 5 MCP `--flat` calls in `mcp_bool_flat.jsonl`.
  - ~50 adversarial exploratory probes (deep nesting / wide domains / parse / nand basis /
    domain mismatch), including the `wrong_gates_nand.ucas` reproducer (10 statements).
- **Files created:** 105
  - 49 `.ucas` + 49 `.out` CLI golden pairs:
    precisely: `01_cases`…`44_cases` (88 files), `b2_01`…`b2_04` (8 files),
    `wrong_gates_nand.ucas/.out` (2 files).
  - `mcp_bool_sat.jsonl` + `.out` (2), `mcp_bool_flat.jsonl` + `.out` + `.flags` (3).
  - `FINDINGS.md`, `SUMMARY.md` (2).
- **Oracle:** independent Python truth-table evaluation over all 2^n inputs for every golden
  case; 0 mismatches in the verified set. All goldens run twice and byte-for-byte identical.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | gates … basis nand: false "no program found / basis not complete" for NOT and AND, which have 1- and 2-gate NAND networks (confirmed by equi |
| LIMIT | 1 | parse !x / parse ~x rejected though not x / (!x) work (cross-reference: syntax_weird). |

### Issues by severity

| Severity | Count | Summary |
|----------|-------|---------|
| WRONG | 1 | `gates … basis nand`: false "no program found / basis not complete" for NOT and AND, which have 1- and 2-gate NAND networks (confirmed by `equiv`). |
| CRASH | 1 (3 syntactic forms) | SIGSEGV stack overflow on deep `!` / parens / right-nested `xor` / deep ternary in Boolean expressions (cross-reference: already known in other areas). |
| LIMIT | 1 | `parse !x` / `parse ~x` rejected though `not x` / `(!x)` work (cross-reference: `syntax_weird`). |
| DETERMINISM | 0 | — |
| HANG | 0 | — |

Also observed (cross-reference only, not counted as new): `equiv` ignoring G's `where`
domain, already filed in `sat_ranges_where`.


## Takeaway
Pure Boolean/u1 semantics, truth tables and SAT verdicts are solid (380 oracle-checked cases all correct and deterministic); the one genuine new defect is `gates basis nand` refusing to tie a gate's inputs, so it misses the NAND-only implementations of NOT and AND and wrongly calls the basis incomplete.

### Original takeaway (verbatim)

Pure Boolean/u1 semantics, truth tables and SAT verdicts are solid (380 oracle-checked cases
all correct and deterministic); the one genuine new defect is `gates basis nand` refusing to
tie a gate's inputs, so it misses the NAND-only implementations of NOT and AND and wrongly
calls the basis incomplete.
