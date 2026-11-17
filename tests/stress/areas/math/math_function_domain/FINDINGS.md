# Stress findings — `math_function_domain`

_Original heading: FINDINGS — `math_function_domain`_

# FINDINGS — `math_function_domain`

Area: systematic domain / definedness / range / wrap / derivative / integral / alias behaviour of every
function in the README list (`sin cos tan exp log ln sqrt isqrt abs floor ceil roundeven sign min max
clz ctz popcount sec csc cot atan copysign fma asin acos atan2 sinh cosh tanh asinh acosh atanh
W/W0/Wm1 productlog lambertw`).

All reproducers below were run with the built binary
`$ROOT/ucas` and are bounded by `timeout 30`. Deterministic reproducers were kept as
goldens (see `NN_*.ucas` / `mcp_*.jsonl` and their `.out`). Every golden was generated twice and `diff`ed:
all 24 outputs are byte-identical across runs.

Expected special values were cross-checked against `mpmath 1.3.0` / `sympy 1.14.0`
(e.g. `isqrt(255)=15`, `log(10)=2.302585093`, `W(10)=1.745528003`, `W(1)=0.567143290`,
`-1/e=-0.367879441`, and `lim_{x->pi/2} sec x = DNE` with left `+oo`, right `-oo`).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | `domain` omits the division singularities of `sec`, `csc`, `cot` |
| LIMIT | 2 | `continuity` / `discontinuities` miss poles of `sec`/`csc`/`cot` (and `tan`) |

## Findings

### WRONG-1 — `domain` omits the division singularities of `sec`, `csc`, `cot`
**Severity:** WRONG
_Original classification: `WRONG: domain omits the division singularities of sec, csc, cot`._
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/math_function_domain
timeout 30 $ROOT/ucas 03_domain_recip_trig.ucas
# or minimal:
timeout 10 $ROOT/ucas -e 'domain sec(x: real)'
```

**Observed:** (excerpt of `03_domain_recip_trig.out`):

```
> domain sec(x: real)
domain of sec(x):
  x: real (default [-10, 10])
  no conditions: total on its parameter types
  defined on (numerically, grid of 20001 over [-10, 10]):
    x in [-10, 10]
> domain csc(x: real)
domain of csc(x):
  no conditions: total on its parameter types
  defined on (numerically, grid of 20001 over [-10, 10]):
    x in [-10, 0)
    x in (0, 10]
```

But the algebraically identical anonymous expression is analysed correctly:

```
> domain 1/cos(x: real)
domain of 1/cos(x):
  requires cos(x) != 0  (in 1/cos(x))
  defined on (numerically, grid of 20001 over [-10, 10]):
    x in [-10, 10]
    except x ≈ -7.853981634  (cos(x) = 0)
    except x ≈ -4.71238898  (cos(x) = 0)
    except x ≈ -1.570796327  (cos(x) = 0)
    except x ≈ 1.570796327  (cos(x) = 0)
    ...
```

`equiv f g` with `f=sec(x)`, `g=1/cos(x)` (and `csc`↔`1/sin`, `cot`↔`cos/sin`) reports
"equal on the domain of f (exhaustive)", and `diff sec(x)` correctly says
"holds for cos(x) != 0" — so ucas itself knows `sec` has poles.

**Expected:** `domain sec` should require `cos(x) != 0` and exclude `x = pi/2 + k*pi`;
`domain csc`/`cot` should require `sin(x) != 0` and exclude `x = 0, ±pi, ±2pi, ±3pi` in `[-10,10]`.
Declaring `sec` total on the reals is an unsound domain verdict. MCP confirms it in the machine-readable
result: `analyze(domain, sec)` returns `"conditions":[],"except":[]` (`mcp_domain.out`, id 1).
`tan(x: real)` is the only reciprocal trig that reports `requires cos(x) != 0` (with no `except`
listing), so the three functions are also mutually inconsistent.

### WRONG-2 — `limit` of reciprocal trig at a pole returns a spurious finite number
**Severity:** WRONG
_Original classification: `WRONG: limit of reciprocal trig at a pole returns a spurious finite`._
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/math_function_domain
timeout 30 $ROOT/ucas 10_limit_poles.ucas
# or minimal:
timeout 10 $ROOT/ucas -e 'limit sec(x) as x -> pi/2'
```

**Observed:** (`10_limit_poles.out`, first case):

```
limit of sec(x) as x -> pi/2:
  = 1.633123935e+16 (from both sides)
  numeric from the left (a - h, h = 0.1*2^-k, k = 0..21): 6.392453221, 101.8607998, ... 13350884.28
    the values grow without bound (+): DISAGREES with 1.633123935e+16
  numeric from the right (a + h, h = 0.1*2^-k, k = 0..21): -6.392453221, -101.8607998, ... -13350884.3
    the values grow without bound (-): DISAGREES with 1.633123935e+16
```

Same wrong pattern for `csc(x) as x -> pi` (`= 8.165619677e+15`), `cot(x) as x -> pi`
(`= -8.165619677e+15`), `csc(x) as x -> 0`, `cot(x) as x -> 0`, `sec(x) as x -> -pi/2`
(`= 1.633123935e+16`), `sec(x) as x -> 3*pi/2` (`= -5.443746451e+15`), and the anonymous
`1/cos(x) as x -> pi/2` / `1/sin(x) as x -> pi`. By contrast `tan(x) as x -> pi/2` is handled
correctly ("the one-sided limits differ: the (two-sided) limit does not exist").

**Expected:** (sympy): left `+oo`, right `-oo`, two-sided limit does not exist. The finite number is
`1/cos(pi/2_as_double)`: ucas evaluates the function at the floating-point approximation of the pole
instead of detecting the pole. The tool's own numeric check flags `DISAGREES` yet still prints the wrong
value as the answer. MCP exposes the wrong value as a number:
`calculus(limit, sec(x), pi/2)` → `"limit":{"kind":"number","value":16331239353195370}`
(`mcp_limits.out`, id 1).

### WRONG-3 — inline `x: T in a..b` annotations are silently misparsed in anonymous command arguments
**Severity:** WRONG
_Original classification: `WRONG / NLP: inline x: T`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/math_function_domain
timeout 30 $ROOT/ucas 15_annot_bug.ucas
# or minimal:
timeout 10 $ROOT/ucas -e 'range isqrt(x: int in 0..255)'
```

**Observed:** (`15_annot_bug.out`):

```
> range isqrt(x: int in 0..255)
range of isqrt(x >= 0 && x <= 255) -> bool:
  0..1   (2 distinct values)
> range log(x: real in 1..10)
range of log(real(x >= 1 && x <= 10)):
  [0, 0]   min at x ≈ 1, max at x ≈ 1
> range asin(x: real in -1..1)
range of asin(real(x >= -1 && x <= 1)):
  [0, 1.570796327]
> range W(x: real in 0..10)
range of W(real(x >= 0 && x <= 10)):
  [0, 0.5671432904]
> domain sqrt(x: real in 0..10)
  note: sqrt of the integer x >= 0 && x <= 10 read as floor square root isqrt(); ...
domain of isqrt(x >= 0 && x <= 10):
  x: real (default [-10, 10])
  defined ... x in [-10, 10]
```

The `in a..b` is absorbed into the *argument* (`x >= a && x <= b`, a boolean cast with `real(...)`)
and the parameter becomes an unannotated `real` on the default `[-10,10]`. Expected ranges:
`isqrt(int in 0..255)` = `0..15` (mpmath: `isqrt(255)=15`), `log` = `[0, 2.302585093]`,
`asin` = `[-pi/2, pi/2]`, `W` = `[0, 1.745528003]`, `domain sqrt` on `[0,10]`.

The named-function form is correct: `f(x: int in 0..255) = isqrt(x)` gives
`range f -> int: 0..15 ... over all 256 points of the domain`. So the misparse is specific to
passing an inline-annotated anonymous expression directly to a command. This silently produces
wrong ranges/domains/derivatives (`diff sqrt(x: real in 0..10)` returns `= 0`) and is a systematic
hazard for every function in the list. MCP reproduces it as structured data
(`analyze(range, "isqrt(x: int in 0..255)")` → `{"type":"bool","min":{"value":0},"max":{"value":1}}`,
`mcp_equiv.out`, id 7).

### LIMIT-1 — `continuity` / `discontinuities` miss poles of `sec`/`csc`/`cot` (and `tan`)
**Severity:** LIMIT
_Original classification: `LIMIT / WRONG: continuity / discontinuities miss poles of sec/c`._
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/math_function_domain
timeout 30 $ROOT/ucas 14_continuity.ucas
# or minimal:
timeout 10 $ROOT/ucas -e 'continuity tan(x: real)'
```

**Observed:** (`14_continuity.out`):

```
continuity of tan(x):
  x = -7.853981634 (~-5*pi/2): infinite (a pole) ...
  x = -4.71238898 (~-3*pi/2): infinite (a pole) ...
  x = 4.71238898 (~3*pi/2): infinite (a pole) ...
  x = 7.853981634 (~5*pi/2): infinite (a pole) ...
```

Within the searched `[-10,10]`, `tan` (and `sec`) have six poles at `±pi/2, ±3pi/2, ±5pi/2`;
the `±pi/2` pair is missing. `continuity csc(x)` / `cot(x)` list only `0, -pi, pi` and miss
`±2pi` (`±6.283`) and `±3pi` (`±9.425`). Contrast `zeros cot(x: real)` which correctly finds all
six zeros at `±pi/2, ±3pi/2, ±5pi/2`, so the pole locator is inconsistent with the zero locator.
**Expected:** all poles in the searched interval; the current output is an incomplete definedness map.

### LIMIT-2 — parity "proof" for `log` and `acosh` uses an undefined point as the witness value
**Severity:** LIMIT
_Original classification: `LIMIT / NLP: parity "proof"`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/math_function_domain
timeout 30 $ROOT/ucas 18_parity.ucas
# or minimal:
timeout 10 $ROOT/ucas -e 'parity log(x: real)'
```

**Observed:** (`18_parity.out`):

```
parity of log(x):
  neither even nor odd
  not even: f(x) = 0, f(-x) = 0 at x = 1
  not odd:  f(x) = 0, f(-x) = 0 at x = 1
```

`log(-1)` and `acosh(-1)` are undefined on the reals (ucas's own `domain log/acosh` says so), so
`f(-x) = 0` is not a legitimate witness — the tool substitutes `0` for an undefined value. The
verdict "neither even nor odd" happens to be correct, but the certificate is invalid. Same output for
`parity acosh(x: real)`. Low severity, but misleading for a tool that advertises checked certificates.

## Checks that passed

### Verified-correct behaviour (no issue)
- All alias spellings are consistent: `equiv` says "equal on the domain of f (exhaustive)" for
  `asin`↔`arcsin`, `acos`↔`arccos`, `atan`↔`arctan`, `asinh`↔`arsinh`, `acosh`↔`arcosh`,
  `atanh`↔`artanh`, `log`↔`ln`, `W`↔`W0`↔`lambertw`↔`productlog`; `W0`↔`Wm1` correctly
  *differ* (519 points). (`09_aliases.ucas`, `mcp_equiv.jsonl`.)
- Symbolic derivatives (`06_diff_trig`, `07_diff_more`) and antiderivatives (`08_integrate`,
  `20_definite_integral`) match standard calculus and pass ucas's own numerical checks
  (e.g. `W' = 1/(exp(W)(W+1))`, `∫W = x(W-1)+exp(W)`, `∫tan = -log|cos|`).
- Float domains (`f16/f32/f64`) correctly report "no conditions: total" (IEEE `inf`/`NaN`
  semantics); machine-integer `isqrt` negative half, `clz/ctz` zero, and `abs(i8)=-128` domain/wrap
  witnesses are correct; `atan2(0,0)` and `atan2(u8,u8)` correctly excluded; `wrap` correctly
  reports `nnan` failures for `sqrt`/`log` on negative floats and `nsw`/`nuw` failure for `abs(i8)`.
- All 24 golden outputs are deterministic across repeated runs.
- No crashes, hangs, or truncated JSON were observed in any of the 236 bounded queries.
