# Stress findings — `external_oracle_diff`

_Original heading: Findings — external_oracle_diff (ucas vs independent Python oracles)_

# Findings — external_oracle_diff (ucas vs independent Python oracles)

All oracles are computed in Python (fractions.Fraction, float/math, brute force,
hand-coded polynomial arithmetic) — no ucas mode is used to check another ucas
mode. Harness: `oraclelib.py` + `run_diff.py` (370 generated cases, all passing
except the deliberate findings below, which are kept as deterministic goldens).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | expanded polynomial prints a rounded decimal constant while claiming "check: exact" |
| LIMIT | 2 | u4/u8 function with a constant (x-independent) body is typed `int` and not wrapped |

## Findings

### WRONG-1 — expanded polynomial prints a rounded decimal constant while claiming "check: exact"
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (copy-pasteable):
```sh
cd $ROOT/tests/stress/areas/math/external_oracle_diff
$ROOT/ucas 10_inexact_constant.ucas
# or a single statement:
printf 'cancel (-4x^3 - 2x^2 - 2x + 2)/(6x - 3)\n' | $ROOT/ucas
```

**Observed:** output (exact):
```
> cancel (-4x^3 - 2x^2 - 2x + 2)/(6x - 3)
cancel (-4x^3 - 2x^2 - 2x + 2)/(6x - 3)
  = -2x^2/3 - 2x/3 - 0.6666666667
  holds where 2x - 1 != 0 (cancelled there)
  check: exact (both sides have the same normal form)
```
`expand` of the same rational function gives the same `-0.6666666667` constant.

**Oracle (independent, exact):** my polynomial gcd gives the reduced form
`-2/3 x^2 - 2/3 x - 2/3`, i.e. `-2(x^2+x+1)/3`. At x=0 the true value is
`2/(-3) = -0.6666...`; ucas's own `simplify` and `factor` on the same input
print the exact `-2(x^2 + x + 1)/3`. For `expand 1/3*x + 2/3` ucas prints
`= x/3 + 0.6666666667` — the leading coefficient is an exact fraction
(`x/3`) but the constant term is a 10-digit decimal in the same expression.

**Why it matters:** the printed constant `-0.6666666667` is a truncation of
`-2/3` (relative error ~5e-11), the *expanded-polynomial printer* emits a
finite decimal for a rational constant while the x-coefficients in the very
same result use exact fraction notation. Yet ucas prints
`check: exact (both sides have the same normal form)`, which is false for a
rounded decimal. `simplify`/`factor` on identical input stay exact, so this is
an output-formatting defect specific to the `expand`/`cancel` printer, not a
fundational limit of the exact core. Severity WRONG: silent precision loss and
a misleading soundness claim.

Deterministic across repeated runs — kept as golden `10_inexact_constant.*`.

### LIMIT-1 — u4/u8 function with a constant (x-independent) body is typed `int` and not wrapped
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/external_oracle_diff/_scratch
cat > wrapinv.ucas <<'EOF'
f(x: u4) = ~(12)
range f
table f
g(x: u4) = ((1 << 1) * 14)
range g
EOF
$ROOT/ucas wrapinv.ucas
```

**Observed:** output (exact):
```
range of f -> int:
  -13..-13
  fits in i5
  over all 16 points of the domain
...
range of g -> int:
  28..28
  fits in u5
```

**Oracle / manual spot-check:** over 4 bits, `~12` (0b1100) = 0b0011 = 3, and
`2*14 = 28` does not fit a u4 (must wrap to 12). A brute-force `u4` oracle
expects min=max=3 for `f` and 12 for `g`; ucas returns -13 and 28 and reports
the function's return type as unbounded `int`.

**Why it matters:** it is worth recording:** the parameter is declared `u4`, but because the
body never references `x`, ucas infers the *result* type from the body (plain
`int`) and does not wrap, so `range`/`table` emit values outside the declared
width. This appears internally consistent with ucas's "result type inferred
from expression" design rather than a proof unsoundness, so severity LIMIT,
but it is surprising and a caller expecting u4-wrapped values would be wrong.
(Differential harness was adjusted to only generate x-dependent bodies.)

### LIMIT-2 — `show` prints only ~10 significant digits (no bit-exact float readout)
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'show 1/3\nshow 0.1 + 0.2\nshow 100000000/3\n' | $ROOT/ucas
```

**Observed:** output:
```
_() = 0.3333333333
_() = 0.3
_() = 33333333.33
```

**Oracle / spot-check:** IEEE-754 double `100000000/3 = 33333333.333333336`;
ucas prints `33333333.33`, discarding ~6 significant digits. `1/3` is printed
as `0.3333333333` (10 digits). This is a display limit, not a computation bug
(the symbolic core stays exact). Consequence for this area: `show` cannot be
used as a bit-exact f64 oracle; float differential checks were therefore done
at a 2e-9 relative tolerance and all 35 float cases agreed with Python.

## Checks that passed

### Notes on non-findings (oracle assumptions that were corrected)
- `(x*13)>>2` over u8: ucas wraps the multiply to u8 *before* the shift
  (range 0..63). A naive "mask only at the end" oracle reports 0..255 and 44
  apparent mismatches; with correct per-operation wrapping ucas is right.
- Integer `mod` for negative operands is C-style truncated remainder
  (`(-3) mod 7 = -3`), not Python's non-negative `%`. All 35 modular cases
  matched once the oracle used truncated remainder.
- `equiv` "not equal" verdicts read `a and c differ at N points, e.g. x=K: v1
  vs v2`; the printed counterexample values were cross-checked against brute
  force and all agreed.
