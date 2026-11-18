# SUMMARY — `analysis_army`

## Counts
- Distinct reproducers tried: ~60 analysis probes (crit/domain/range/wrap/
  zeros/continuity/equiv across real, f32, f64 and integer parameters).
- Bugs with goldens: 3 (BUG-1 float `crit` misses extrema, BUG-2 domain
  except-list ignores `where`, BUG-3 kink at a noise coordinate).
- Bug documented without a golden: 1 (BUG-4 except-list explosion on a zero
  plateau, ~250 KB output).
- Controls: 1 golden covering the neighbouring stable behaviour.

### What was tried
- Systematic probing of `crit`, `domain`, `range`, `wrap`, `zeros`,
  `continuity` and `equiv` on: reciprocal trig, log/sqrt/exp compositions,
  removable singularities, piecewise `?:` and min/max, closed ranges,
  `where` clauses, f16/f32/f64 bit-pattern sampling and integer wrap.
- Cross-checks: the same expression with a `real` parameter vs a machine-float
  parameter (BUG-1, BUG-3); `range` vs `domain` for the same ranged function
  (BUG-2); polynomial `zeros` proved by algebra vs sampled `zeros`.

### Files created
- CLI goldens: `01_float_crit_missed`, `02_domain_where_except`,
  `03_kink_noise_coord`, `90_controls` (input + `.out`).
- Reports: `FINDINGS.md`, `SUMMARY.md`.

## Issues by severity
| Severity | IDs |
|----------|-----|
| WRONG | BUG-1, BUG-2, BUG-3, BUG-4 (no golden) |
| CRASH / HANG / DETERMINISM | none |

## Takeaway
After the flagged `crit`/domain fixes, the remaining analysis weaknesses are
concentrated in float-typed sampling (BUG-1), the `where`-awareness of the
`domain` except-list (BUG-2/BUG-4), and jump-localisation in `crit` (BUG-3).
The recorded goldens make all three regressions detectable.
