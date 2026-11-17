# SUMMARY — `below_tolerance_float`

## Counts
- Distinct expressions/queries tried: 247
- Goldens written: 22
- Files created: 18

### Coverage
- **Distinct expression pairs tried: 247** (all f32 or f64), organised in 9
  bug families: Racer InstanceNorm `1/rstd^2 ± eps` (52), sqrt-sign/reconstruction
  (14), reduction / sum-order changes (37), variance wrong-sign & Bessel
  off-by-one (8), off-by-one thresholds `>` vs `>=` (45), fused vs unfused
  multiply-add (12), `x==k` vs `|x-k|<=tol` (38), magic-constant/1-ULP drift
  (19), subnormal/FTZ and misc identities (22).
- Independent ground truth: Python `Fraction` on IEEE bit patterns
  (`_scratch/ground_truth.py`) — **201 genuinely different**, 46 genuinely equal.
- **Commands issued:** 247 `equiv` + 247 `error` (494 CLI analyses) plus
  dedicated `fit`, `approx`, `equiv ftz/noftz`, `nanbits` experiments.
- **Files written:** 18 numbered `NN_*.ucas/.out` golden pairs (36 files),
  4 `x_*.ucas/.out` golden pairs (8 files), `FINDINGS.md`, `SUMMARY.md`,
  and the `_scratch/` generator + corpus + ground-truth tooling.
- All goldens verified deterministic (generated twice, diff-identical), all runs
  bounded by `timeout 30`, exit code 0 everywhere, no crashes/hangs.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 57 | error = "max abs error 0" on 54 genuinely different pairs; equiv = "equal" on 3 genuinely different pairs (float division defeats SAT, sampl |
| LIMIT | 3 | fit masks a fixed sign bug by fitting eps→0; approx symbolic minimax = 0 for a unit spike; ftz proves a subnormal bug away. |

### Issues by severity
| Severity | Count | Short description |
|---|---|---|
| WRONG | 57 | `error` = "max abs error 0" on 54 genuinely different pairs; `equiv` = "equal" on 3 genuinely different pairs (float division defeats SAT, sampler misses the point). |
| LIMIT | 3 | `fit` masks a fixed sign bug by fitting eps→0; `approx` symbolic minimax = 0 for a unit spike; `ftz` proves a subnormal bug away. |
| CRASH / HANG / DETERMINISM | 0 | none observed. |


## Takeaway
`equiv`'s SAT engine finds point-like float bugs, but the `error`/`fit`/`approx` sampling-and-tolerance path routinely reports "0 error" on genuinely different functions — exactly the below-tolerance blind spot sampled differential testing is supposed to have, so a zero from `error` cannot be used as an equivalence certificate.

### Original takeaway (verbatim)
`equiv`'s SAT engine finds point-like float bugs, but the `error`/`fit`/`approx`
sampling-and-tolerance path routinely reports "0 error" on genuinely different
functions — exactly the below-tolerance blind spot sampled differential testing
is supposed to have, so a zero from `error` cannot be used as an equivalence
certificate.

### Confirmation
All files created are under `$ROOT/tests/stress/areas/float/below_tolerance_float/`.
No source files, Makefiles, shared tests, `opencode.json`, or other subagents'
folders were touched; no `make`, `git`, or unbounded processes were run.
