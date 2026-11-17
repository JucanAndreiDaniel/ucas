# Stress findings — `second_cas_oracle`

_Original heading: Findings — second_cas_oracle (ucas vs a real second CAS: SymPy 1.14 / mpmath 1.3)_

# Findings — second_cas_oracle (ucas vs a real second CAS: SymPy 1.14 / mpmath 1.3)

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `cancel`/`expand` print a rounded decimal for an exact rational constant and claim "check:… |
| LIMIT | 2 | ucas states a correct infinite limit but its own numeric check prints `DISAGREES` |

## Findings

### WRONG-1 — `cancel`/`expand` print a rounded decimal for an exact rational constant and claim "check: exact"
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (copy-pasteable):
```sh
cd $ROOT/tests/stress/areas/math/second_cas_oracle
$ROOT/ucas 01_rounded_cancel.ucas
```

**Observed:** (exact excerpt from `01_rounded_cancel.out`):
```
> cancel (-4x^3 - 2x^2 - 2x + 2)/(6x - 3)
  = -2x^2/3 - 2x/3 - 0.6666666667
  holds where 2x - 1 != 0 (cancelled there)
  check: exact (both sides have the same normal form)
> expand 1/3*x + 2/3
expand 0.3333333333x + 0.6666666667
  = x/3 + 0.6666666667
  check: exact (both sides have the same normal form)
```

**Oracle (SymPy, exact):** `cancel((-4x^3-2x^2-2x+2)/(6x-3))` is
`-2*x**2/3 - 2*x/3 - 2/3`; ucas's own `factor` on the identical input prints the exact
`-2(x^2 + x + 1)/3` (also in `01_rounded_cancel.out`). `-0.6666666667` is a truncation of
`-2/3` (absolute error ~3.3e-11).

**Why it matters:** the expanded-polynomial printer emits a finite decimal for the constant
term while the *x*-coefficients in the same expression use exact fraction notation, and the
block still asserts `check: exact (both sides have the same normal form)` — a claim the oracle
refutes. Silent precision loss plus a false soundness claim. Severity WRONG.
Deterministic; kept as golden `01_rounded_cancel.*`.

### WRONG-2 — symbolic limits that equal `e` are printed as a 10-digit decimal, not `e`
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/second_cas_oracle
$ROOT/ucas 02_rounded_limit.ucas
```

**Observed:** (from `02_rounded_limit.out`):
```
limit of (x + 1)^(1/x) as x -> 0:
  ...
  = 2.718281828 (from both sides)
limit of (1/x + 1)^x as x -> inf:
  ...
  = 2.718281828
```

**Oracle (SymPy/mpmath):** `E = 2.71828182845904523536...`. The printed value differs by
~4.6e-10 (relative ~1.7e-10). These are *symbolic* limits, so the exact constant `e` should
be returned (as SymPy does). The result is numerically close but silently loses exactness.
`02_rounded_limit.*`.

### LIMIT-1 — ucas states a correct infinite limit but its own numeric check prints `DISAGREES`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/second_cas_oracle
$ROOT/ucas 03_limit_check_disagree.ucas
```

**Observed:** (from `03_limit_check_disagree.out`):
```
limit of log(x) as x -> 0+ (from the right):
  = -inf
  numeric from the right (a + h, h = 0.1*2^-k, k = 0..21): -2.302585093, -5.075173815, ...
    the values do not settle (the last ones lie in [-16.8587, -12.0066]): DISAGREES
limit of sqrt(x)/x as x -> 0+ (from the right):
  = inf
  ...
    the values do not settle (the last ones lie in [404.772, 4579.47]): DISAGREES
```

**Oracle:** both limits are correct (`-oo` and `+oo`). The *numeric checker* is at fault: 22
halvings of `h=0.1` reach only `x~2.4e-8`, nowhere near enough for `log(x)` to look linear, so
the "values do not settle" heuristic contradicts the correct symbolic answer printed two
lines above. Self-contradictory output — a caller reading the `check:` line would reject a
correct result. Severity LIMIT (verifier quality, not a wrong answer). Deterministic; golden
`03_limit_check_disagree.*`.

### LIMIT-2 — capabilities refuted by the oracle: incomplete symbolic answers
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/second_cas_oracle
$ROOT/ucas 04_incomplete.ucas
```

**Observed:** (from `04_incomplete.out`):
```
limit of x^x as x -> 0:
  from the left:
  = not found symbolically
  from the right:
  = 1
  (one side was not found symbolically)
∫ exp(-x^2) dx
  no antiderivative found (...)
∫ abs(x) dx
  no antiderivative found (...)
```

**Oracle:** SymPy gives `limit(x**x, x, 0, dir='+') = 1`, `integrate(exp(-x**2), x) =
sqrt(pi)*erf(x)/2`, and a piecewise antiderivative for `abs(x)`. ucas's answers are honestly
reported as unfound (not wrong), but they are genuine capability gaps for a CAS. Severity
LIMIT. Deterministic; golden `04_incomplete.*`.

## Checks that passed

### Setup / oracle provenance
- Real CAS oracle: **SymPy 1.14.0 + mpmath 1.3.0** (already installed; no Maxima/Sage/GP/PARI
  on this machine, no installation needed). Checked with
  `python3 -c 'import sympy, mpmath; print(sympy.__version__, mpmath.__version__)'`.
- Harness: `oracle_tasks.py` (262 tasks) + `run_oracle.py`. It batches all commands into
  `_generated_batch.ucas`, runs the ucas CLI once under a timeout, parses each printed
  answer into a SymPy expression (implicit multiplication, `^`→`**`, absolute value, etc.),
  computes ground truth with SymPy, and compares **semantically** (`simplify`/`expand`, with a
  high-precision numeric fallback and antiderivative-up-to-constant / root-set / product-of-factors
  special cases). Output: `report.json` + `report.txt`.
- Result: **262 tasks, 257 OK, 3 mismatches, 2 incomplete** (see `report.txt`). The full
  report is deterministic: two consecutive runs produced byte-identical `report.json`.

### 5. Non-findings — branch conventions and conditions that PASS (checked against SymPy)
These were explicit hunt targets; ucas handles them correctly. Kept as golden `05_branch_ok.*`.

- `limit tan(x) x -> pi/2+` → `-inf`, `x -> pi/2-` → `inf` (matches SymPy's `dir='+'/'-'`).
- `limit atan(1/x) x -> 0+` → `pi/2`, `x -> 0-` → `-pi/2` (correct branch).
- `solve a*x^2+b*x+c=0 for x` prints the quadratic formula **with** `where a != 0` and
  `real when b^2-4ac >= 0` — conditions present, not missing.
- `simplify (x^2-1)/(x-1)` prints `holds where x - 1 != 0 (cancelled there)`.
- `solve sqrt(x+1)=x-1` correctly labels `x=0` as *extraneous (from squaring)* and returns
  only `x=3` (matches SymPy's single real root).
- `simplify asin(sin(x))`: ucas prints the `= x` form **with** `for -pi/2 <= x <= pi/2` and
  notes "(outside: differs at 26 of 26 points, so the condition is needed)", ending with
  `simplest: asin(sin(x)) (as given)`. The branch condition is explicit, not missing.

### 6. Harness notes / oracle assumptions that were corrected (no ucas bug)
- Initial shortfalls were all in the *comparison* layer, not ucas: Symbol identity between
  parsed answer and SymPy operand; extracting `= ` from multi-form `trig` output (must use the
  final `simplest:` line); `solve` annotation lines (`(a double root)`, `extraneous`);
  prime factorization printed as `N = N (prime)`; `sin(1/x)` limit prints `none (it oscillates)`
  which SymPy represents as `AccumulationBounds(-1,1)`. Once fixed, all these agree.
- Antiderivatives compared up to an additive constant (ucas `-cos(x)^2/2` vs SymPy
  `sin(x)^2/2` differ by 1/2 — both valid); gcd/lcm compared up to a nonzero constant factor.
- `x^4 - 10x^2 + 1 = 0`: ucas's `±sqrt(2) ± sqrt(3)` roots are correct; my first oracle
  constants were wrong and were fixed.
