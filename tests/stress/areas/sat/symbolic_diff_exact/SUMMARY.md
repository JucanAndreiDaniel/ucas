# SUMMARY — `symbolic_diff_exact`

## Counts
- Distinct expressions/queries tried: 242
- Goldens written: 5
- Files created: 4

### What was done

Built a differential-testing harness whose oracle is **independent of ucas
`equiv`**: an exact rational-function evaluator using Python `fractions.Fraction`
(no sympy available in this environment), with exact rational refutation at up
to 64 points per pair and ucas `expand`/`simplify` as a second check. Generated a
deterministic corpus of **242 expression pairs** (101 true identities, 141
near-misses) over `int`/`real` variables, including binomial expansions,
difference-of-squares/cubes, rational identities, complete-the-square
quadratics, trivariate expansions, and explicitly renamed/shifted variants.

Each pair was compared against ucas `equiv` on `real`, bounded `int in -4..4`,
and `i8`, plus `expand`/`simplify` of the difference: **1210 MCP tool calls**
(`ucas --mcp`), in 3 bounded chunks. Shape reduction used canonical rename
classes: prove/query once per class, reuse for verified renaming variants.

### Counts

- Distinct expression pairs tried: **242** (oracle agreed with construction on all 242).
- MCP tool calls: **1210**. CLI golden runs: 6 files × 2 for determinism + MCP × 2.
- Files created: 4 harness modules (`exprlib.py`, `corpus.py`, `shapes.py`,
  `harness.py`) + `run.sh`; 5 CLI goldens (`.ucas`+`.out`); 1 MCP golden
  (`.jsonl`+`.out`); `FINDINGS.md`; `SUMMARY.md`; generated data in `_scratch/`.

### Issues by severity

| Severity | Count | One-line description |
|---|---|---|
| WRONG | 101 | `equiv` over `real` rejects every true identity; witness prints identical values and fails exact evaluation |
| WRONG | 6 | Correct refutation but witness rounds both values to the same float (below-tolerance, un-diagnosable) |
| LIMIT (domain) | 23 | Machine-`int`/`i8` `equiv` disagrees only on division identities (integer division/overflow); not unsound |
| CRASH / HANG / DETERMINISM | 0 | All runs bounded, all goldens byte-identical across two runs |

Cross-checks that PASSED: `expand`/`simplify` agreed with the exact oracle on
242/242 pairs; **0** false `equal:true` verdicts in 726 `equiv` calls; 217 shape
classes structurally verified with 0 inconsistent verdicts.

### Reproduce

```sh
cd $ROOT/tests/stress/areas/sat/symbolic_diff_exact
./run.sh                                   # regenerates _scratch/ oracle report
ucas 01_equiv_real_true.ucas               # 101-case bug family (5 shown)
ucas 02_exact_diff_expand.ucas             # exact oracle says 0
ucas 05_counterexample_precision.ucas      # below-tolerance witness
ucas --mcp < mcp_oracle.jsonl              # structured equal:false + counterexample
```


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 107 | Correct refutation but witness rounds both values to the same float (below-tolerance, un-diagnosable) |
| LIMIT | 23 | Machine-int/i8 equiv disagrees only on division identities (integer division/overflow); not unsound |

## Takeaway
The independent exact oracle confirms ucas's algebra engine (`expand`/`simplify`) is exact on all 242 pairs and that machine-type `equiv` is sound on pure polynomials — but `equiv` over `real` is systematically wrong: it rejects all 101 true identities with self-contradicting, exactly-failing counterexamples, and even its correct refutations can print indistinguishable witness values.

### Original takeaway (verbatim)

The independent exact oracle confirms ucas's algebra engine (`expand`/`simplify`)
is exact on all 242 pairs and that machine-type `equiv` is sound on pure
polynomials — but `equiv` over `real` is systematically wrong: it rejects all 101
true identities with self-contradicting, exactly-failing counterexamples, and
even its correct refutations can print indistinguishable witness values.
