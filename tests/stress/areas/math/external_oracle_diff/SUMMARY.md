# SUMMARY — `external_oracle_diff`

## Counts
- Distinct expressions/queries tried: 370
- Goldens written: 10
- Files created: not recorded

### What was done
Compared `ucas` against independent oracles implemented in Python stdlib only
(no SymPy/mpmath/Z3 installed): `fractions.Fraction` for exact polynomial /
rational arithmetic and gcd reduction, `float`+`math` + composite Simpson for
numeric derivatives/integrals, brute-force enumeration for u4/u8, Python
integers with truncated remainder for modular arithmetic, and `struct`-style
IEEE-double semantics for floats. A reusable harness (`oraclelib.py`,
`run_diff.py`) parses ucas's *output expressions* and checks them semantically
against these oracles; no ucas mode is used as an oracle for another ucas mode.

### Counts
- **Expressions / queries tried:** 370 generated differential cases across 10
  categories (expand 45, factor 35, cancel/simplify 45, together 20, diff 45,
  definite integrate 35, u4/u8 range 40, equiv-vs-brute-force 35, modular 35,
  float 35), plus ~40 targeted manual probes to characterize findings.
- **Result:** 369/370 automatic cases agreed with the oracle. The single
  automatic disagreement reproduced the WRONG finding below and was promoted
  to a deterministic golden; the random-seed ordering is why a full clean run
  shows all PASS (the finding is kept as an explicit reproducer golden).
- **Files written (deliverables):**
  - `oraclelib.py` (parser + exact poly engine + oracle helpers)
  - `run_diff.py` (campaign generator / differential driver)
  - `diff_results.json` (per-case machine-readable results)
  - 10 CLI goldens: `01_expand_exact` … `10_inexact_constant` (`.ucas`+`.out`)
  - `FINDINGS.md`, `SUMMARY.md`
  - `_scratch/` (manual probes, not part of the golden set)

All 10 goldens were run twice and diffed — all DETERMINISTIC.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | cancel/expand print a rounded decimal constant (-0.6666666667) in an otherwise exact result while claiming "check: exact" |
| LIMIT | 2 | constant-body uN function inferred as int (no wrap); show limited to ~10 significant digits |

### Issues by severity
| Severity | Count | One-line |
|----------|-------|----------|
| WRONG | 1 | `cancel`/`expand` print a rounded decimal constant (`-0.6666666667`) in an otherwise exact result while claiming "check: exact" |
| LIMIT | 2 | constant-body uN function inferred as `int` (no wrap); `show` limited to ~10 significant digits |
| CRASH / HANG / NLP / DETERMINISM | 0 | — |


## Takeaway
The exact algebra, calculus, range, equiv, modular and float cores agreed with independent Python oracles on ~400 cases; the only substantive defect found is the expanded-polynomial printer emitting a truncated decimal for rational constant terms under `expand`/`cancel`, together with a false "check: exact".

### Original takeaway (verbatim)
The exact algebra, calculus, range, equiv, modular and float cores agreed with
independent Python oracles on ~400 cases; the only substantive defect found is
the expanded-polynomial printer emitting a truncated decimal for rational
constant terms under `expand`/`cancel`, together with a false "check: exact".
