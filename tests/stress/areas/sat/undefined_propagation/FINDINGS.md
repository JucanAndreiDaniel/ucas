# Stress findings — `undefined_propagation`

_Original heading: FINDINGS — `undefined_propagation`_

# FINDINGS — `undefined_propagation`

All commands below are copy-pasteable from
`$ROOT/tests/stress/areas/sat/undefined_propagation` (binary
`$ROOT/ucas`).  Golden files listed here were generated twice and
diffed (`sh gen_goldens.sh` → `ALL GOLDENS DETERMINISTIC`).

No crashes or hangs were found: the 718-expression combinatorial sweep
(`sweep.py`, audit in `sweep_audit.txt`) produced `EXIT COUNTS: {0: 718}`, `BAD: 0`;
every run stayed under 15 s.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | `domain` and `range` contradict each other for NaN-valued IEEE results |
| NLP | 1 | a definition with a parse error silently becomes a free `real` parameter and gets a bogus … |
| LIMIT | 2 | `equiv ... nanbits` on a signalling NaN cannot prove a true equality |

## Findings

### WRONG-1 — `domain` and `range` contradict each other for NaN-valued IEEE results
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/undefined_propagation
$ROOT/ucas 17_domain_range_nan.ucas
```

**Observed:** output (exact)

```
> f(x: u32 in 0..3) = asfloat(x | 0x7fc00000)
> domain f
domain of f:
  x: u32, 0..3
  no conditions: total on its parameter types
  defined at 4 of 4 points
  over all 4 points of the domain
> range f
range of f -> f32:
  empty (undefined everywhere)
  IEEE: NaN at 4 points, ±inf at 0 points
  over all 4 points of the domain
```
The same pattern occurs for `g(x) = asfloat(x | 0x7f800001)` (signalling NaN;
`0x7f800001`): `domain g` → `defined at 4 of 4 points`, `range g` →
`empty (undefined everywhere)`, `IEEE: NaN at 4 points`.  For
`h(x) = asfloat(x | 0x7f800000)` the range is `[inf, inf]` although `IEEE: NaN at
3 points` — three of the four “defined” points are silently dropped from the
numeric min/max.  Via MCP the contradiction is visible in the typed result:
`mcp_undefined.jsonl` calls 8 and 9 return
`structuredContent.result.defined_points = 4, points = 4` (domain) and
`result.empty = true` (range).  See also `07_asfloat_nan.out` (sampled case:
`defined at 65536 of 65536 points` vs `no value: none of the 65536 points
sampled is in the domain`).

**Why it matters:** it is a bug / expected

A function cannot be “defined at every point” and “undefined everywhere” at
once.  `range` treats NaN results as “not in the domain” whereas `domain` treats
them as defined values.  A signalling NaN made by `asfloat` is never flagged as
undefined at all — it is treated as an ordinary NaN — yet `range` then calls the
function undefined everywhere.
**Expected:** agree on a single notion of definedness
(either report the range as “all NaN” with the points defined, or mark the points
undefined in `domain`).

### WRONG-2 — dead/alternative branches leak conditions into `domain`'s `requires` list
**Severity:** WRONG
**Reproducers**

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/undefined_propagation
$ROOT/ucas 15_spurious_requires.ucas
$ROOT/ucas 13_short_circuit_domain.ucas | head -12
$ROOT/ucas 14_real_power_domain.ucas | head -30
```

**Observed:** output (exact)

`15_spurious_requires.out`:
```
> f(x: real) = x > 0 ? min(sqrt(x),2) : max(log(-x),0)
> domain f
domain of f:
  x: real (default [-10, 10])
  requires -x > 0
  requires x >= 0
  defined on (numerically, grid of 20001 over [-10, 10]):
    x in [-10, 0)
    x in (0, 10]
```

`13_short_circuit_domain.out`:
```
> f(x: real) = (x > 0) && (sqrt(x) > 1)
> domain f
domain of f:
  x: real (default [-10, 10])
  requires x >= 0
  defined on (numerically, grid of 20001 over [-10, 10]):
    x in [-10, 10]
```
`table f` in the same golden prints `x=-10 -> 0` … `x=-1 -> 0`, confirming the
function is defined at negative x.

`14_real_power_domain.out`:
```
> f(x: real) = x^x
> domain f
domain of f:
  x: real (default [-10, 10])
  requires x >= 0  (real power)
  defined on (numerically, grid of 20001 over [-10, 10]):
    x in [-10, -10]
    ...
    x in [-1, -1]
    x in [0, 10]
```

**Why it matters:** it is a bug / expected

The `requires` lines contradict the numeric `defined on` lines printed immediately
below them.  For `x > 0 ? min(sqrt(x),2) : max(log(-x),0)` the two conditions
`-x > 0` and `x >= 0` are jointly unsatisfiable although the function is defined
at every `x != 0`.  For `(x > 0) && (sqrt(x) > 1)` the README states `&&` looks
only at the taken side, so `requires x >= 0` is simply wrong.  For `x^x` the
condition `x >= 0` excludes negative integers where the function is defined and
included in `range` (`min at x ≈ -1`).
**Expected:** `requires` conditions should
describe the actual domain (branch-conditioned for `?:`, empty for short-circuited
`&&`/`||`), not a blind union of every partial operation in the expression.

### WRONG-3 — direct evaluation silently turns an undefined subexpression into `0`/`1` (or an unrelated complex value)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/undefined_propagation
$ROOT/ucas 12_direct_eval.ucas
```

**Observed:** output (exact, relevant lines)

```
> sqrt(-1)
  note: sqrt(-1) is undefined in the reals; its complex principal value follows
  note: on the branch cut of sqrt: the principal value, sqrt z = e^(log(z)/2): i sqrt|z| on the negative reals (the other root is its negative)
i
> sqrt(-1)*0
  note: sqrt(-1)*0 is undefined in the reals; its complex principal value follows
  note: on the branch cut of sqrt: the principal value, sqrt z = e^(log(z)/2): i sqrt|z| on the negative reals (the other root is its negative)
0
> log(0)*0
_() = 0log(0)
  -> real
> 1 < 2 ? 5 : sqrt(-1)
5
> 1 > 2 ? sqrt(-1) : 5
5
> asfloat(0x7f800001)*0
  note: asfloat of an untyped integer: read as u32 -> f32
nan
```
Additional one-liners (not in the golden): `sqrt(-1)-sqrt(-1)` → `0`,
`sqrt(-1)/sqrt(-1)` → `1`, `sqrt(-1)==sqrt(-1)` → symbolic `_() = ... -> bool`,
`min(sqrt(-1),1)` → symbolic `_() = min(sqrt(-1), 1) -> real`.

**Why it matters:** it is a bug / expected

The same undefined real subexpression is variously reported as a complex number
(`i`), silently collapsed to `0`, silently collapsed to `1`, left as an
unevaluated symbol, or turned into `nan` depending on the surrounding operator.
The task requires an expression containing an undefined subexpression to be
flagged; here `sqrt(-1)*0` yields a concrete real `0` with no undefined result
(the note only announces a complex fallback that is never returned).  The two
`?:` lines do confirm that a dead branch is not evaluated.

### WRONG-4 — `wrap` claims a correct-rounding/ulp result for NaN-valued functions
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/undefined_propagation
$ROOT/ucas 07_asfloat_nan.ucas | sed -n '1,12p'
```

**Observed:** output (exact)

```
> range f
range of f -> f32:
  no value: none of the 65536 points sampled is in the domain
  IEEE: NaN at 65536 points, ±inf at 0 points
  sampled 65536 points (domain has 4294967296 points); not exhaustive
```
and `wrap f` for the same definition prints
`end to end vs the real-number result: max abs error 0, max rel error 0, max 0 ulp (correctly rounded)`.

**Why it matters:** it is a bug / expected

A value that is NaN at every sampled point has no real-number counterpart and no
ulp distance; claiming “max 0 ulp (correctly rounded)” is a bogus soundness claim.
**Expected:** `wrap` should say the comparison is inapplicable for NaN results.

### NLP-1 — a definition with a parse error silently becomes a free `real` parameter and gets a bogus answer
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/undefined_propagation
$ROOT/ucas 16_parse_error_default.ucas
```

**Observed:** output (exact)

```
> f(x: u8) = [1,2,3][x][0]
16_parse_error_default.ucas:1:25: error: only a table [a, b, ...] can be indexed
    f(x: u8) = [1,2,3][x][0]
                            ^
> domain f
domain of f:
  f: real (default [-10, 10])
  no conditions: total on its parameter types
  defined on (numerically, grid of 20001 over [-10, 10]):
    f in [-10, 10]
> range f
range of f:
  [-10, 10]   min at f ≈ -10, max at f ≈ 10
  grid of 20001 points over [-10, 10] (default; give x a range), extrema refined at critical points
```

**Why it matters:** it is a bug / expected

After the definition failed to parse, subsequent `domain f`/`range f` should be
refused.  Instead `f` is silently reinterpreted as a free real variable and the
tool returns confident, entirely bogus domain/range results (the variable is
even named `f` and the real parameter `x` vanished).  This is a silent default
after a malformed input — exactly the NLP failure mode the stress contract asks
to catch.

### LIMIT-1 — `equiv ... nanbits` on a signalling NaN cannot prove a true equality
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
$ROOT/ucas \
  -e 'f(x: u32) = asfloat(x|0x7f800001)' \
  -e 'g(x: u32) = asfloat(x|0x7f800001)+0' \
  -e 'equiv f g nanbits'
```

**Observed:** output (exact)

```
f and g are equal on the domain of f (sampled, not proved; no SAT proof: its counterexample did not reproduce)
  NaN results compared by their bits, sign and payload (nanbits)
```

**Why it matters:** it is worth recording

The two sides are identical except for `+0`, which quiets a signalling NaN
(`0x7f800001` → `0x7fc00001`) without changing its payload; the equality is true.
The message “no SAT proof: its counterexample did not reproduce” is a documented
sampled answer, not a proof.  Note the contrast: `equiv q1 q2 nanbits` for
`asfloat(x|0x7f800001)` vs `asfloat(x|0x7f800001)` *is* proved by SAT (33 AIG
nodes), so this limit is specific to arithmetic on a signalling NaN.

### LIMIT-2 — `wrap` prints an empty witness when zero points differ
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
$ROOT/ucas -e 'f(x: u8) = 1 << x' -e 'wrap f' | tail -3
```

**Observed:** output (exact)

```
  end to end: differs from the mathematical result at 0 points, e.g. $
      exact for: 0..7
  over all 256 points of the domain
```

**Why it matters:** it is worth recording

`e.g. ` is followed by nothing when the count is zero; the witness field should
be omitted.  Cosmetic, but it produces a malformed-looking line in machine
consumers.

## Checks that passed

_No separate passed checks were recorded in the original document._
