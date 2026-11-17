# Stress findings — `polynomial_gcd_resultant`

_Original heading: FINDINGS — `polynomial_gcd_resultant`_

# FINDINGS — `polynomial_gcd_resultant`

Area: exact polynomial algebra consistency (gcd/lcm, resultants, discriminants, factor/expand,
division certificates, multivariate, rational coefficients, high degree, resultant-based systems).
All commands were run with `timeout 15`. Oracle checks used sympy 1.14.0 (explicit Sylvester
determinant for resultants, since ucas uses the `lc(P)^deg(Q) * prod Q(root of P)` convention,
not sympy's transposed-Sylvester convention).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | gcd of degree > 64 polynomials silently returns 1, with a *passing* certificate |
| LIMIT | 2 | MCP structured `result` for `lcm` embeds a non-round-trippable `where` CSE |

## Findings

### WRONG-1 — gcd of degree > 64 polynomials silently returns 1, with a *passing* certificate
**Severity:** WRONG
_Original classification: `WRONG (high): gcd of degree > 64 polynomials silently returns 1, with`._
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/polynomial_gcd_resultant
printf 'gcd x^65-1, x^5-1\n' | timeout 15 $ROOT/ucas
```

**Observed:** output (exact):
```
gcd x^65 - 1, x^5 - 1
  = 1
  check: it divides both exactly, and the cofactors are coprime
  (normalized: integer coefficients without a common factor, leading coefficient positive)
```

**Expected:** `x^5 - 1`, because `gcd(x^65 - 1, x^5 - 1) = x^gcd(65,5) - 1 = x^5 - 1`.
The tool returns `1` and *still asserts* "it divides both exactly, and the cofactors are
coprime" — the cofactors `x^65 - 1` and `x^5 - 1` are obviously **not** coprime (they share
`x^5 - 1`), so the self-check is unsound. Same failure at larger sizes:
`gcd x^100-1, x^20-1` -> `1` (expected `x^20 - 1`); `gcd x^1000-1, x^600-1` -> `1`
(expected `x^200 - 1`). Degree <= 64 works (`gcd x^60-1, x^40-1` -> `x^20 - 1`),
so the cutoff is degree 64: above it a high power `x^n` is treated as an opaque atom and
distinct atoms are declared coprime. Verified with the MCP `gcd` tool too.

### WRONG-2 — `factor` falsely claims "factors are irreducible over the rationals" for reducible polynomials (degrees 41–64)
**Severity:** WRONG
_Original classification: `WRONG: factor falsely claims "factors are irreducible over the ratio`._
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/polynomial_gcd_resultant
printf 'factor x^41-1\n' | timeout 15 $ROOT/ucas
```

**Observed:** output (exact):
```
factor x^41 - 1
  = x^41 - 1
  check: exact (both sides have the same normal form)
  (factors are irreducible over the rationals)
```

**Expected:** `(x - 1)*(x^40 + x^39 + ... + x + 1)`. `x = 1` is plainly a root, so the
emitted "factors are irreducible over the rationals" note is **false**. The factoring
search gives up around degree 41 (cyclotomic `x^40-1` still factors fully), but the
irreducibility claim is printed unconditionally. Many reducible cases at degree 41–64
are affected: `x^42-1`, `x^48-1`, `x^50-1`, `x^60-1`, `x^64-1`, `(x-1)*(x^49+1)`.

A second manifestation loses even the power form:
```sh
printf 'factor (x-1)^50\n' | timeout 15 $ROOT/ucas
```
begins `= x^50 - 50x^49 + ...` (fully expanded, ~870 bytes) and ends
```
  (factors are irreducible over the rationals)
```
**Expected:** `(x - 1)^50`. (`factor (x-1)^40` correctly returns `(x - 1)^40`.)

For degree >= 65 the note is simply dropped (`factor x^65-1` -> `x^65 - 1` with only
the "check: exact" line), i.e. a silent give-up — see F3.

### WRONG-3 — polynomials of degree > 64 are re-parsed as opaque atoms, producing nonsensical results
**Severity:** WRONG
_Original classification: `WRONG/LIMIT: polynomials of degree > 64 are re-parsed as opaque atoms`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/polynomial_gcd_resultant
printf 'discriminant x^65-1\nresultant x^65-1, x^5-1\nrem x^150-1, x^75+1\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:** output (exact):
```
discriminant x^65 - 1
  in x^65 (degree 1): 1
  > 0: distinct roots
  check: lc^(2n-2) * product of (ri - rj)^2 over the roots = 1 (agrees)
resultant x^65 - 1, x^5 - 1
  in x: (x^65)^5 - 5(x^65)^4 + 10(x^65)^3 - 10(x^65)^2 + 5x^65 - 1
    = (x^65 - 1)^5
rem x^150 - 1, x^75 + 1
  the leading coefficient x^75 + 1 does not divide; divide by a polynomial with a numeric leading coefficient in x^150
```

The discriminant is taken "in x^65" (the high power is an atom) giving 1; if the variable
is forced with `discriminant x^65 - 1 in x`, ucas instead says
`note: x does not occur` / `the discriminant needs a polynomial in a variable` — both
responses are wrong for a polynomial where `x` plainly occurs. The resultant of two
univariate polynomials in `x` must be a scalar, not `(x^65 - 1)^5`. The remainder is
refused even though the divisor `x^75 + 1` has leading coefficient 1.

Worse, the header can disagree with the variable actually used:
```sh
printf 'resultant x^100-1, x^60+1\n' | timeout 15 $ROOT/ucas
```
starts
```
resultant x^100 - 1, x^60 + 1
  in x: (x^100)^60 - 60(x^100)^59 + ... - 60x^100 + 1
```
— header says "in x" but the answer is a degree-60 polynomial in the *atom* `x^100`,
with float coefficients in scientific notation (`1.415428015e+16`, ...). The true
resultant is a single (huge) integer. `discriminant x^120-1` similarly reports
"in x^120 (degree 1): 1". No crash/hang; all finish well under 15 s.

### WRONG-4 — rational coefficients printed as truncated decimals while the tool claims "check: exact"
**Severity:** WRONG
_Original classification: `WRONG/LIMIT: rational coefficients printed as truncated decimals while`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/polynomial_gcd_resultant
printf 'quo 2x+1, 3x+1\nquo 4x-1, 1-3x\nresultant x+1/3, x^2+1\ndiscriminant x^2 + x/3 + 1/6\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:** output (exact):
```
quo 2x + 1, 3x + 1
  = 0.6666666667
  (in x: P = Q*quotient + remainder, deg remainder < 1)
  check: exact (both sides have the same normal form)
quo 4x - 1, 1 - 3x
  = -1.333333333
  (in x: P = Q*quotient + remainder, deg remainder < 1)
  check: exact (both sides have the same normal form)
resultant x + 0.3333333333, x^2 + 1
  in x: 1.111111111
  nonzero: no common root
  check: lc(P)^deg(Q) * product of Q over the roots of P = 1.111111111 (agrees)
discriminant x^2 + x/3 + 0.1666666667
  in x (degree 2): -0.5555555556
  < 0: two complex conjugate roots
  check: lc^(2n-2) * product of (ri - rj)^2 over the roots = -0.5555555556 (agrees)
```

Exact answers: quotient `2/3` and `-4/3`; scalar resultant `10/9`; discriminant `-5/9`.
The printed decimals are truncated to ~10 significant digits yet each result is labelled
"check: exact" / "(agrees)". README states "Printing stays exact: `x^3/3`, `1/(2(x+1))`",
so this silently loses exactness. It also makes the MCP structured `result` a decimal
instead of the exact fraction (e.g. `584.8194444` instead of `42107/72` in a larger case).
Not every rational op is affected: `expand`, `factor` and constant denominators that are
powers of two round-trip exactly (`expand (x+1/2)^2` -> `x^2 + x + 1/4`), so the problem is
localised to `quo`/`rem`/`divide`, `resultant` and `discriminant` when the coefficients are
non-terminating fractions.

### LIMIT-1 — MCP structured `result` for `lcm` embeds a non-round-trippable `where` CSE
**Severity:** LIMIT
_Original classification: `LIMIT: MCP structured result`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (single-call JSONL):
```sh
cd $ROOT/tests/stress/areas/math/polynomial_gcd_resultant
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"algebra","arguments":{"op":"lcm","args":{"p":"4*x^2+x+5","q":"4*x^2+5"}}}}' \
 | timeout 15 $ROOT/ucas --mcp
```

**Observed:** (`structuredContent.result.result`, exact):
```
(t1 + x + 5)*(t1 + 5) where t1 = 4x^2
```
The CLI prints the clean `16x^4 + 4x^3 + 40x^2 + 5x + 25`. Feeding the structured string
back to ucas fails:
```
  ucas: expand (t + 5)*(t + x + 5) where t = 4x^2
<english>:1:21: error: unexpected 'where' in (t + 5)*(t + x + 5) where t = 4x^2
```
A structured field documented as "expressions as ucas strings that parse back" should be a
self-contained, parseable expression. (Also note the CSE name is `t1` in the result but
the same expression re-parsed/printed uses `t`.)

### LIMIT-2 — reserved constant `e` collides with a symbolic coefficient name, and prints inconsistently
**Severity:** LIMIT
_Original classification: `LIMIT: reserved constant e collides with a symbolic coefficient name`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/polynomial_gcd_resultant
printf 'resultant a*x^2 + b*x + c, d*x + e\n' | timeout 15 $ROOT/ucas
```

**Observed:** output (exact):
```
resultant a*x^2 + b*x + c, d*x + e
  in x: 7.389056099a - e*(b*d) + c*d^2
```

`e` is Euler's constant (so `e^2 = 7.389056099`), but the same symbol is also printed
as a named symbol in the middle term `- e*(b*d)`. Expected (treating `e` as the constant
it is) `7.389056099*a - 2.718281828*b*d + c*d^2`, or, if a user meant `e` as a free
parameter, `a*e^2 - b*d*e + c*d^2`. The mixed form is inconsistent and surprising;
uppercase `E` is available and gives the clean symbolic result
`a*E^2 - b*d*E + c*d^2`. Related: `expand (e+1)^2` -> `13.82561976`.

## Checks that passed

### Non-bugs / graceful limits observed (recorded for completeness)
- `gcd`/`lcm`/`resultant` on inputs whose coefficients overflow intermediate 64-bit
  arithmetic print `the coefficients grow past 64 bits: not done` and stop gracefully
  (e.g. `gcd -3*x^5-5*x^4-5*x^3-x^2-3*x+5, -4*x^6+5*x^5+x^4+3*x^3+2*x^2-5*x-1`).
  This matches the documented 64-bit limit.
- Division by zero (`quo x, 0`), non-polynomial inputs (`gcd x^-1, x`), zero resultants
  (`resultant 0,0` -> "the resultant needs a variable"), and constant discriminants are
  all reported cleanly with nonzero-free exits; no crashes or hangs were found in ~40
  adversarial edge cases, including exponents up to `x^1000000` (all finished < 15 s).
- Resultant sign convention: ucas computes the *untransposed* Sylvester determinant
  (`lc(P)^deg(Q) * prod Q(roots of P)`), which differs from `sympy.resultant` by
  `(-1)^(deg P * deg Q)` in some cases. Verified correct against an explicit sympy
  Sylvester matrix; this is a convention difference, not a bug.
