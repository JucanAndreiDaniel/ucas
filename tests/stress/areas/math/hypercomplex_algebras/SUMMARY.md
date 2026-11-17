# SUMMARY — `hypercomplex_algebras`

## Counts
- Distinct expressions/queries tried: 1300
- Goldens written: 12
- Files created: 12

### Coverage numbers

* **Distinct expressions / queries tried:** ≈ 1300 (plus a cell-by-cell check of 1364 table entries) —
  - 176 CLI/golden statements in the 10 `.ucas` files (9 + 15 + 20 + 12 + 26 + 24 + 13 + 15 + 2 + 8),
  - 32 MCP calls (25 regular `hypercomplex` + 7 `--flat`),
  - plus exploratory sweeps: 5 multiplication tables and 1364 table cells checked cell-by-cell,
    64 quaternion associators, 512 octonion associators, 16 quaternion commutators,
    120 large-coefficient quaternion associators, 38 externally generated `frommatrix`
    matrices, ≈ 200 `rotate`, ≈ 60 `rotmatrix`/`axisangle`, ≈ 15 `slerp`, and ~80
    expression/norm/parse probes.
* **Files written (in this folder only):** 12 golden pairs / sessions + 2 docs:
  - CLI goldens: `01_tables`, `02_algebra_props`, `03_assoc_comm`, `04_zero_divisors`,
    `05_rotations`, `06_cross_algebra`, `07_cd_parse`, `08_norms_inverses` (`.ucas` + `.out`).
  - Bug goldens (current wrong behaviour, see FINDINGS): `81_bug_assoc_large`,
    `82_bug_ecoeff_parse` (`.ucas` + `.out`).
  - MCP goldens: `mcp_hypercomplex.jsonl`/`.out`, `mcp_flat.jsonl`/`.out` + `mcp_flat.flags`.
  - Docs: `FINDINGS.md`, `SUMMARY.md`.
* All 12 goldens were generated twice and diffed byte-for-byte: **12/12 stable**.
  Every run used `timeout 15`/`timeout 30`; no nonzero exits except deliberate error cases
  (`algebra cd 3`, `rotmatrix 0`, invalid `frommatrix`), which are deterministic.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | associator uses an absolute 1e-24 norm threshold → false "not associative" for quaternions with coefficients ≳ 100; 2e1 parsed as 20 in conj |
| NLP | 1 | (same 2e1 ambiguity, reported under WRONG/NLP) |
| LIMIT | 1 | cd16x / cd 2.9 silently accepted via atoi prefix; standalone cd(4) misparsed as cd |

### Issues by severity

| Severity | Count | One-line description |
|---|---|---|
| CRASH | 0 | no crash anywhere, including `cd(32)` |
| HANG | 0 | `table cd 32`, `algebra cd 32`, `zerodivisors cd 32` all < 0.2 s |
| WRONG | 2 | `associator` uses an absolute 1e-24 norm threshold → false "not associative" for quaternions with coefficients ≳ 100; `2e1` parsed as 20 in `conj`/`abs`/powers but as `2*e1` in products |
| NLP | 1 | (same `2e1` ambiguity, reported under WRONG/NLP) |
| LIMIT | 1 | `cd16x` / `cd 2.9` silently accepted via `atoi` prefix; standalone `cd(4)` misparsed as `c*d` |
| DETERMINISM | 0 | every golden reproduced identically |


## Takeaway
The Cayley–Dickson algebra core is sound — all five multiplication tables, zero divisors, unit associators/commutators, rotation machinery and cd(32) paths checked out — but the `associator` verdict is fooled by ordinary floating-point rounding on large inputs and the `2e1`-as-coefficient notation is parsed inconsistently, giving silently wrong answers in otherwise valid hypercomplex expressions.

### Original takeaway (verbatim)

The Cayley–Dickson algebra core is sound — all five multiplication tables, zero divisors,
unit associators/commutators, rotation machinery and cd(32) paths checked out — but the
`associator` verdict is fooled by ordinary floating-point rounding on large inputs and the
`2e1`-as-coefficient notation is parsed inconsistently, giving silently wrong answers in
otherwise valid hypercomplex expressions.
