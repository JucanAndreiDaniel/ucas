# Stress findings — `trig_identity_sweep`

_Original heading: FINDINGS — `trig_identity_sweep`_

# FINDINGS — `trig_identity_sweep`

Area: trig/hyperbolic identity consistency. All reproducers are deterministic and were run with
`timeout` against `$ROOT/ucas` (already built). Oracles: `mpmath` 1.3.0 at 50–60 dps.

Oracles used: `_scratch/harness.py` (59 identities, incl. 13 deliberately false, checked against
mpmath), `_scratch/evalharness.py` (134 special-point evaluations checked against mpmath),
plus CLI (`simplify`, `trig`, `limit`, `period`, `parity`, `bounded`, `zeros`, `asymptotes`,
`continuity`, `domain`, `range`, `identify`, `equiv`, `taylor`, `diff`, `antiderivative`, `integrate`)
and MCP (`algebra`, `properties`, `calculus`).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | `limit` of reciprocal trig at a singularity returns a huge finite number instead of ±inf /… |
| NLP | 1 | NLP/PARSER: standard reciprocal/arc-hyperbolic names silently parsed as multiplication |
| LIMIT | 1 | `simplify` fails to prove many *true* trig/hyperbolic identities (false negatives) |

## Findings

### WRONG-1 — `limit` of reciprocal trig at a singularity returns a huge finite number instead of ±inf / DNE
**Severity:** WRONG
_Original classification: `WRONG: limit of reciprocal trig at a singularity returns a huge fini`._
**Why it matters:** _not recorded_
When the limit point makes the denominator trig value only *approximately* zero in floating point
(e.g. `cos(pi/2) ≈ 6.1e-17`, `sin(pi) ≈ 1.22e-16`), `limit` substitutes a near-singular float and
returns a large finite value. The tool's own numeric check prints `DISAGREES`, and MCP returns a
structured `limit.kind:"number"`. Contrast: at `x -> 0` (where `sin(0) == 0` exactly) the same tool
correctly reports a two-sided "does not exist" with `±inf`.

**Reproducer:**
Reproducer (CLI):
```sh
cd $ROOT/tests/stress/areas/math/trig_identity_sweep
printf 'limit 1/cos(x) x -> pi/2\n' > /tmp/f.ucas
$ROOT/ucas /tmp/f.ucas
# or the full batch:
$ROOT/ucas 07_limits_singularity_WRONG.ucas
```

**Observed:**
```
> limit 1/cos(x) x -> pi/2
limit of 1/cos(x) as x -> pi/2:
  = 1.633123935e+16 (from both sides)
  numeric from the left (a - h, h = 0.1*2^-k, k = 0..21): 6.392453221, 101.8607998, 1629.74672, 26075.94588, 417215.134, 13350884.28
    the values grow without bound (+): DISAGREES with 1.633123935e+16
  numeric from the right (a + h, h = 0.1*2^-k, k = 0..21): -6.392453221, -101.8607998, -1629.74672, -26075.94588, -417215.134, -13350884.3
    the values grow without bound (-): DISAGREES with 1.633123935e+16
```

MCP reproducer: `mcp_trig_identity.jsonl`, id 15 (`calculus.limit` of `1/cos(x)` at `pi/2`).
Structured result: `{"kind":"limit","limit":{"kind":"number","value":1.633123935319537e+16}}`.

**Expected:** left `+inf`, right `-inf`, two-sided limit does not exist — exactly what
`limit tan(x) x -> pi/2` (same file, last line) correctly produces. Same bug affects:
`sec(x)`, `sec(x)^2` at `pi/2` (→ 2.667e32), `csc(x)`, `1/sin(x)` at `pi` (→ 8.17e15) and
`2*pi` (→ -4.08e15), `cot(x)` at `pi`/`2*pi`, `1/cos(x)` at `3*pi/2` (→ -5.44e15).
Note that `1/(1-cos(x))` at `0`/`2*pi` is handled correctly (`inf`), so the defect is specific
to the reciprocal of a trig function whose argument is not an exact float zero at the limit point.

`07_limits_singularity_WRONG.ucas/.out` (deterministic, exit 0).

### WRONG-2 — pole / asymptote / discontinuity detection omits poles on the default unbounded range
**Severity:** WRONG
_Original classification: `WRONG: pole / asymptote / discontinuity detection omits poles`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
With the default `[-10, 10]` range, `asymptotes`/`continuity`/`discontinuities` miss some poles.
`tan(x)` has poles at `±pi/2, ±3pi/2, ±5pi/2` on `[-10,10]`; the tool reports only `±3pi/2, ±5pi/2`
(the innermost pair `±pi/2` is missing). `1/sin(x)` has poles at `0, ±pi, ±2pi, ±3pi`; the tool
reports only `0, ±pi`. Yet `zeros cos(x)` correctly lists `±pi/2` (poles of tan = zeros of cos),
so the tool's own zero-finder contradicts its pole-finder. Giving `x` an explicit bounded range
makes the poles appear, so this is a range/grid dependent false negative, not a math ambiguity.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/trig_identity_sweep
$ROOT/ucas 08_poles_WRONG.ucas
```

**Observed:** (excerpt):
```
> asymptotes tan(x)
asymptotes of tan(x):
  vertical: x = -7.853981634 (~-5*pi/2) ...
  vertical: x = -4.71238898 (~-3*pi/2) ...
  vertical: x = 4.71238898 (~3*pi/2) ...
  vertical: x = 7.853981634 (~5*pi/2) ...
  none as x -> -inf
  none as x -> +inf
> zeros cos(x)      # separate probe, _scratch/probe8.ucas
  ... x = -1.570796327 (~-pi/2)
  ... x =  1.570796327 (~pi/2)     <-- poles of tan exist but are not reported above
> f(x: real in -4..4) = tan(x)
> asymptotes f
asymptotes of f:
  vertical: x = -1.570796327 (~-pi/2) ...
  vertical: x =  1.570796327 (~pi/2) ...    <-- found once range is bounded
```

Same omission in `continuity tan(x)` and `discontinuities tan(x)`. Severity: **WRONG** (incomplete
pole/discontinuity set). Golden kept: `08_poles_WRONG.ucas/.out`; MCP id 11.

### WRONG-3 — `equiv` on real functions claims "differ", showing equal values
**Severity:** WRONG
_Original classification: `WRONG: equiv`._
**Why it matters:** _not recorded_
`equiv` uses raw float equality on sampled points, so rounding noise from a mathematically exact
identity is reported as a difference, with witnesses whose two printed values are identical.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/trig_identity_sweep
$ROOT/ucas 11_equiv_float_WRONG.ucas
```

**Observed:**
```
> f(x: real) = sin(x)^2 + cos(x)^2
> g(x: real) = 1
> equiv f g
f and g differ at 218 points, e.g. x=-9.98: 1 vs 1
> h(x: real) = sin(x)^2
> k(x: real) = 1 - cos(x)^2
> equiv h k
h and k differ at 705 points, e.g. x=-9.98: 0.277868 vs 0.277868
```

**Expected:** these are identically equal on R (Sin²+Cos²=1); `equiv` should use a tolerance for
`real` inputs (it already does exhaustive exact checks for machine integer types). Severity:
**WRONG** (false "differ" verdict with self-contradicting witness). Golden kept:
`11_equiv_float_WRONG.ucas/.out`.

### NLP-1 — NLP/PARSER: standard reciprocal/arc-hyperbolic names silently parsed as multiplication
**Severity:** NLP
_Original classification: `NLP/PARSER: standard reciprocal/arc-hyperbolic names silently parsed a`._
**Why it matters:** _not recorded_
`sech`, `csch`, `coth`, `arcsinh`, `arccosh`, `arctanh` are not recognized functions. The parser
emits a note and silently reads `sech(x)` as `sech * x`, creating a bogus two-variable function.
Downstream commands then produce confusing behavior: `limit coth(x) x -> 0` errors out with a
"function of several variables" message. The recognized inverse-hyperbolic names are `asinh`,
`acosh`, `atanh` (and hyperbolics `sinh`, `cosh`, `tanh`).

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/trig_identity_sweep
$ROOT/ucas 09_parser_hyperbolic_names.ucas
printf 'limit coth(x) x -> 0\n' > /tmp/f.ucas
$ROOT/ucas /tmp/f.ucas
```

**Observed:**
```
> sech(x)
  note: sech(...) read as multiplication: sech is not a function
_(sech: real, x: real) = sech*x
  -> real
> limit coth(x) x -> 0
  note: coth(...) read as multiplication: coth is not a function
/tmp/f.ucas:1:21: error: the limit of a function of several variables needs the others fixed (give them values)
    limit coth(x) x -> 0
                        ^
```

**Expected:** recognize these common function names, or issue a hard error instead of silently
constructing a wrong function. Severity: **NLP** (graceful note exists, but silent misparse yields
bogus expressions / misleading errors). Golden kept: `09_parser_hyperbolic_names.ucas/.out`
(the error case is documented here rather than as a golden).

### LIMIT-1 — `simplify` fails to prove many *true* trig/hyperbolic identities (false negatives)
**Severity:** LIMIT
_Original classification: `LIMIT: simplify fails to prove many true trig/hyperbolic identitie`._
**Why it matters:** _not recorded_
Across 59 identity candidates (46 true, 13 deliberately false) checked with mpmath, the 13 false
ones were all correctly *not* proven, and no false identity was ever claimed true. However ~15 true
identities were left unsimplified despite the tool's own numeric self-check saying "equal at
64 of 64 sample points" (that check compares the rewrite to its input, not to zero). Examples below.
This is a coverage/giving-up limitation, not unsoundness.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/trig_identity_sweep
$ROOT/ucas 10_simplify_false_negative_LIMIT.ucas
```

**Observed:** (excerpt; each mpmath-verified identically zero):
```
> simplify cot(x)^2 + 1 - 1/sin(x)^2
  simplest: cot(x)^2 + 1 - 1/sin(x)^2  (as given)
> simplify asin(x) + acos(x) - pi/2
  simplest: asin(x) + acos(x) - pi/2  (as given)
> simplify cosh(x) + sinh(x) - exp(x)
  simplest: cosh(x) + sinh(x) - exp(x)  (as given)
> simplify tanh(2*x) - 2*tanh(x)/(1+tanh(x)^2)
  simplest: tanh(2*x) - 2*tanh(x)/(1+tanh(x)^2)  (as given)
```

**Expected:** reduce these to `0` (the CAS already proves the sin/cos analogue of each via power
reduction or product-to-sum). Severity: **LIMIT**. Golden kept:
`10_simplify_false_negative_LIMIT.ucas/.out`.

## Checks that passed

### Positive results (no issue found)
- **134 special-point evaluations** (sin/cos/atan/tan/asin(sin θ)/acos(cos θ)/atan(tan θ) at
  `0, ±pi/6, ±pi/4, ±pi/3, ±pi/2, ±2pi/3, ±pi, ±3pi/2, ±2pi, ...`, inverse hyperbolics, degree
  forms `30/45/54/60/90/180/360 degrees`/`°`/`deg`, exact angles `pi/12, pi/5, pi/8`) all matched
  mpmath at high precision (`_scratch/evalharness.py`: 0 mismatches). Branch behaviour of
  `asin(sin x)`, `acos(cos x)`, `atan(tan x)` is reported with correct domain conditions.
- **No false `equal:true` / unsound proof** in the 59-identity sweep; all 13 deliberately false
  identities were correctly left nonzero.
- `period`, `parity`, `bounded`, `zeros`, `domain`, `range`, `identify`, `taylor`, `diff`,
  `antiderivative`, `integrate` outputs spot-checked and correct for trig/hyperbolic functions.
- No crashes or hangs observed; all 12 golden files (11 CLI + 1 MCP) exit 0 and are byte-identical
  across two runs. `timeout 30` used throughout.
