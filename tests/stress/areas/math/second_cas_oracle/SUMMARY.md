# SUMMARY — `second_cas_oracle`

## Counts
- Distinct expressions/queries tried: 262
- Goldens written: 7
- Files created: not recorded

### Original preamble

- **Oracle:** real second CAS — SymPy 1.14.0 + mpmath 1.3.0 (installed system-wide; no
  Maxima/Sage/GP/PARI available; no pip install or system modification needed).
- **Distinct expressions/queries tried:** 262 (expand 23, factor 22, simplify/together/
  cancel/apart 22, adv. simplify 15, diff 27, indefinite integrate 23, definite integrate 14,
  limits 12+14+10=36, taylor 9, gcd/lcm/resultant/discriminant/quo/rem 13, solve 13,
  det 10+5+3=18, factorint 15+12=27).
- **Harness:** `oracle_tasks.py` + `run_oracle.py` → `report.json`, `report.txt`
  (semantic comparison with SymPy; deterministic across two runs).
- **Golden files:** 6 `.ucas`/`.out` pairs (`01_rounded_cancel`, `02_rounded_limit`,
  `03_limit_check_disagree`, `04_incomplete`, `05_branch_ok`, `06_oracle_agree`) — all
  deterministic (each run twice and `diff`ed), all exit 0.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | rounded decimal in cancel/expand with false "check: exact"; e limits printed as 2.718281828 |
| LIMIT | 5 | self-contradictory DISAGREES numeric check (×2); incomplete x^x limit; incomplete exp(-x^2)/abs(x) antiderivatives; (taylor about a≠0 uses ~ |

### Issues by severity

| Severity | Count | Items |
|---|---|---|
| WRONG | 2 | rounded decimal in `cancel`/`expand` with false "check: exact"; `e` limits printed as `2.718281828` |
| LIMIT | 5 | self-contradictory `DISAGREES` numeric check (×2); incomplete `x^x` limit; incomplete `exp(-x^2)`/`abs(x)` antiderivatives; (taylor about a≠0 uses ~10-digit decimals) |
| CRASH / HANG / NLP / DETERMINISM | 0 | none observed |

- Result breakdown from `report.txt`: **257 OK, 3 mismatches (the WRONG/precision items),
  2 incomplete (LIMIT)**. No crashes, hangs, or nondeterminism.


## Takeaway
ucas agrees with SymPy on the overwhelming majority (257/262) of symbolic/numeric tasks including one-sided-limit branches and condition reporting, but its output layer silently truncates exact rationals/constants to 10-digit decimals while still claiming exactness, and its limit numeric verifier can contradict its own correct symbolic answer.

### Original takeaway (verbatim)
ucas agrees with SymPy on the overwhelming majority (257/262) of
symbolic/numeric tasks including one-sided-limit branches and condition reporting, but its
output layer silently truncates exact rationals/constants to 10-digit decimals while still
claiming exactness, and its limit numeric verifier can contradict its own correct symbolic answer.
