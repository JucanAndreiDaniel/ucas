# SUMMARY — `approx_army`

## Counts
- CLI goldens: 6 (`NN_*.ucas` + `NN_*.out`) and 2 JSON goldens
  (`json_*.jsonl` + `json_*.out`), each captured twice from the fixed binary
  under `UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none` and diff-checked.
- Reproducers: 3 (CRASH-1, CRASH-2, CRASH-3); controls: 5.

## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 3 | heap overflow at 16 exact points; `approx more <huge>` cursor wrap; `find holes()` `INT64_MIN % -1` trap |
| LIMIT | 1 | `c optimize budget 2` cannot bound one find-engine run (caller floors seconds at 60) |

## Takeaway
Two bugs are `approx` bookkeeping around a fixed sample buffer and a candidate
cursor; the third is an arithmetic trap in the `find` engine's affine-template
solver.  Fit values and ordinary `find` results are unchanged.  The sample
buffer now reserves room for all `AMAXK` exact points, the `more` count is
bounded before it is added to the cursor, and `holes()` skips divisions that
would trap.  Existing goldens (which use at most `keep endpoints` and normal
`more` counts) are unaffected.
