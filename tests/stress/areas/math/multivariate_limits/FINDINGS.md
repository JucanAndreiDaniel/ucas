# Stress findings — `multivariate_limits`

_Original heading: FINDINGS — multivariate_limits_

# FINDINGS — multivariate_limits

Area: limits and continuity in 2+ variables. Binary: `$ROOT/ucas`.
All commands below are copy-pasteable from the repo root.

Severity key: CRASH | HANG | WRONG | NLP | LIMIT | DETERMINISM.

No CRASH, HANG or DETERMINISM issue was found: ~900 queries were run under
`timeout 15`, all exited 0, none timed out, and every golden was produced twice
and diffed byte-for-byte.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | L'Hôpital differentiates `floor`/`ceil` as 0, giving wrong limits at infinity |
| NLP | 1 | English frontend cannot express a multivariate limit / continuity request |
| LIMIT | 2 | no joint limit/continuity: multivariate inputs are rejected or require fixing all but one … |

## Findings

### WRONG-1 — L'Hôpital differentiates `floor`/`ceil` as 0, giving wrong limits at infinity
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/multivariate_limits && $ROOT/ucas 07_wrong_floor.ucas
```

**Observed:** output (exact)

```
limit of floor(x)/x as x -> inf:
  inf/inf: L'Hôpital: lim (0)/(1) = lim 0
  = 0
  numeric (x = 10*2^k, k = 0..21): 1, 1, 1, 1, 1, 1
    extrapolated (Richardson): 1 (estimated error 0): DISAGREES with 0
limit of ceil(x)/x as x -> inf:
  inf/inf: L'Hôpital: lim (0)/(1) = lim 0
  = 0
  numeric (x = 10*2^k, k = 0..21): 1, 1, 1, 1, 1, 1
    extrapolated (Richardson): 1 (estimated error 0): DISAGREES with 0
limit of floor(2x)/x as x -> inf:
  inf/inf: L'Hôpital: lim (0)/(1) = lim 0
  = 0
  numeric (x = 10*2^k, k = 0..21): 2, 2, 2, 2, 2, 2
    extrapolated (Richardson): 2 (estimated error 0): DISAGREES with 0
limit of (x - floor(x))/x as x -> inf:
  inf - inf: x - floor(x) = (1/(floor(x)) - 1/(x))/(1/((x)*(floor(x))))
  0/0: L'Hôpital: lim (1/x^2)/(-floor(x)/(x^2*floor(x)^2)) = lim -floor(x)
  inf/inf: L'Hôpital: lim (1)/(1) = lim 1
  = 1
  numeric (x = 10*2^k, k = 0..21): 0, 0, 0, 0, 0, 0
    extrapolated (Richardson): 0 (estimated error 0): DISAGREES with 1
```

**Why it matters:** it is a bug**: the printed answers are wrong. True limits are
`floor(x)/x -> 1`, `ceil(x)/x -> 1`, `floor(2x)/x -> 2`,
`(x - floor(x))/x -> 0`. Sympy agrees (`floor(x)/x -> 1`,
`floor(2*x)/x -> 2`, `(x-floor(x))/x -> 0`). The tool's own numeric check
prints `DISAGREES` on every one, i.e. it detects its own wrong answer and still
reports it. Root cause: `try_diff` returns derivative 0 for `floor`/`ceil`, so
`lhopital()` (`src/calc2.c:3329`) applies L'Hôpital to an `inf/inf` form using a
bogus derivative. More reproducers (same root cause):
`limit floor(x)/x x->-inf` -> 0 (true 1);
`limit (x+floor(x))/x x->inf` -> 1 (true 2);
`limit (floor(x)+1)/x x->inf` -> 0 (true 1);
`limit (x-floor(x)) x->inf` -> `-inf` (true: no limit, oscillatory in [0,1)).
Also exposed over MCP (`mcp_wrong_floor.out`, `calculus.limit` returns
`ok:true` with the wrong `limit.value`).

### WRONG-2 — `continuity` reports a finite "undefined" interval for `exp(1/x)` from float overflow
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/multivariate_limits && $ROOT/ucas 08_wrong_overflow_domain.ucas
```

**Observed:** output (exact)

```
continuity of exp(1/x):
  continuous wherever it is defined on [-10, 10] (and on all real x where defined)
  undefined on (0, 0.001408881876) (the ends located numerically)
  proved: built from operations that are continuous where defined, so it is continuous on its domain; points outside it located numerically; x has no range: searched [-10, 10]
```

**Why it matters:** it is a bug**: `exp(1/x)` as a real function is defined for every `x != 0`;
there is no mathematical domain hole on `(0, 0.0014...)`. That endpoint is
`1/ln(DBL_MAX) ~ 1/709.78 = 0.00140888`, i.e. where the double evaluation
overflows to `+inf`. The domain finder mistakes floating-point overflow for
undefinedness and reports it as a proved domain fact. This verdict also feeds
the structured `properties.continuity` result.

### WRONG-3 — `continuity` misses isolated discontinuities not on its 0.001 sampling grid
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/multivariate_limits && $ROOT/ucas 09_wrong_isolated_spike.ucas
```

**Observed:** output (exact)

```
continuity of x == 0.1234567 ? 1 : 0:
  continuous wherever it is defined on [-10, 10]
  checked numerically: a grid of 20001 points, jumps located by bisection, limits from both sides; x has no range: searched [-10, 10]
continuity of x == pi ? 1 : 0:
  continuous wherever it is defined on [-10, 10]
  checked numerically: a grid of 20001 points, jumps located by bisection, limits from both sides; x has no range: searched [-10, 10]
continuity of x == 0.3333333333 ? 1 : 0:
  continuous wherever it is defined on [-10, 10]
  checked numerically: a grid of 20001 points, jumps located by bisection, limits from both sides; x has no range: searched [-10, 10]
```

**Why it matters:** it is a bug**: each function equals 1 at one isolated point and 0
elsewhere, so it has a removable discontinuity there (f(p)=1, limit 0). The
tool declares it continuous. `disc_analyse` uses a fixed 20001-point grid on
[-10,10] (spacing 0.001) plus bisection, and cannot see equality at any
off-grid point. The same checker is used for slices `continuity f(x,c)` of
two-variable functions, so a spike along a slice is missed too. By contrast an
on-grid spike IS detected: `continuity (x==0?1:0)` reports
`x = 0: removable: both limits are 0, f has the value 1 there`.

### WRONG-4 — self-check prints `DISAGREES` for correct slowly-diverging limits
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/multivariate_limits && $ROOT/ucas 11_selfcheck_disagrees.ucas
```

**Observed:** output (exact, excerpts)

```
limit of log(x) as x -> 0+ (from the right):
  = -inf
  numeric from the right (a + h, h = 0.1*2^-k, k = 0..21): -2.302585093, -5.075173815, -7.847762537, -10.62035126, -13.39293998, -16.85867588
    the values do not settle (the last ones lie in [-16.8587, -12.0066]): DISAGREES
limit of 1/sqrt(x) as x -> 0+ (from the right):
  1/sqrt(x) -> inf (the numerator -> 1, sqrt(x) -> 0+)
  = inf
  numeric from the right (a + h, h = 0.1*2^-k, k = 0..21): 3.16227766, 12.64911064, 50.59644256, 202.3857703, 809.543081, 4579.467218
    the values do not settle (the last ones lie in [404.772, 4579.47]): DISAGREES
```

**Why it matters:** it is a bug**: the symbolic answers `-inf` and `inf` are correct, but the
tool's own verification says they disagree with the numeric samples. The
divergence detector in `numeric_limit()` (`src/calc2.c:4022-4032`) requires
`|v|` to grow by >5% each step AND `|v| > 1e4` over the last 6 samples; slowly
diverging functions (`log x`, `log(x)^2`, `1/sqrt x`, `1/log x`) fail this test
and are classified `LV_OSC`. The false `DISAGREES` is emitted as a failing
`checks[].passed` through MCP too, so a consumer that trusts `checks` would
reject a correct answer.

### NLP-1 — English frontend cannot express a multivariate limit / continuity request
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/multivariate_limits && $ROOT/ucas --mcp < mcp_english_multivariate.jsonl > /tmp/eng.out 2>&1
```

**Observed:** output (exact, per-call `content[0].text`)

```
error (not_understood): as what approaches what? (as x approaches 0)
error (not_understood): as what approaches what? (as x approaches 0)
error (ambiguous): I don't know the word "origin"
error (not_understood): which variable is [0, 0] for?
```

**Why it matters:** it is a bug**: natural requests — "limit of x*y/(x^2+y^2) as
(x,y) approaches (0,0)", "as x and y go to 0", "at the origin", "continuous at
(0,0)" — are all rejected or misparsed. Even a tool that cannot compute joint
limits should parse the intent and give a clear "multivariate not supported"
rather than suggesting a bogus single-variable reading ("as x approaches 0"),
which is exactly the wrong answer for a path-dependent function.

### LIMIT-1 — no joint limit/continuity: multivariate inputs are rejected or require fixing all but one variable
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/multivariate_limits && $ROOT/ucas --mcp < mcp_multivariate_reject.jsonl > /tmp/rej.out 2>&1
```

**Observed:** output (exact, per-call)

```
error (unsupported): the limit of a function of several variables needs the others fixed (give them values)
continuity of x*y/(x^2 + y^2):
continuity x*y/(x^2 + y^2): 2 parameters; give the others values, e.g. continuity f(x, 1)
```

**Why it matters:** it matters**: `c2_limit()` (`src/calc2.c:4197`) and the continuity property
both refuse >1 free parameter. The only way to probe a joint limit is to bind
all but one variable (`limit f(x, m*x) x->0`), and each such slice is treated as
a standalone one-variable limit. There is no joint-limit verdict, so a
path-dependent function such as `x*y/(x^2+y^2)` is never flagged as such by the
system — its slices return 0, 1/2, 2/5, -1/2, ... with no indication that these
disagree. Recorded here as a capability gap (not a wrong answer), but it is the
central limitation for this area.

### LIMIT-2 — tuple conditions in `where` clauses cannot be parsed (blocks piecewise multivariate definitions)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
printf '%s\n' 'f(x,y) = (x*y)/(x^2+y^2) where (x,y) != (0,0)' | $ROOT/ucas
```

**Observed:** output (exact)

```
<stdin>:1:34: error: expected ')', found ','
    f(x,y) = (x*y)/(x^2+y^2) where (x,y) != (0,0)
                                     ^
```

**Why it matters:** it is a limitation**: the canonical "separately continuous but not
jointly continuous" example needs a piecewise definition with the origin
removed and a value assigned at the origin. Tuple-valued conditions are
rejected at the parser, so such functions cannot be defined and their joint
continuity cannot be investigated even slice-by-slice.

## Checks that passed

### LIMIT — symbolic limit gives up ("not found symbolically") on valid limits
**Reproducer**

```sh
cd $ROOT/tests/stress/areas/math/multivariate_limits && $ROOT/ucas 10_giveups.ucas
```

**Observed output (exact, claims)**

```
limit of cot(x) - 1/x as x -> 0:
  = not found symbolically
limit of exp(-1/x^2)/x as x -> 0:
  = not found symbolically
limit of (log(x + 1) - x)/x^2 as x -> 0:
  = not found symbolically
limit of (tan(x) - sin(x))/x^3 as x -> 0:
  = not found symbolically
limit of (x - log(x + 1))/x^2 as x -> 0:
  = not found symbolically
```

**Why it is a limitation**: all five limits exist and are finite (respectively
0, 0, -1/2, 1/2, 1/2; verified with sympy and high-precision mpmath). L'Hôpital
is capped at 12 iterations (`src/calc2.c:3333`) and the `inf - inf` rewrite
repeatedly bloats the expression, so the engine returns `LV_UNKNOWN`. The
numeric estimate is right but is labeled "not a proof". Many two-variable path
limits hit the same give-up, e.g. `f(x,y)=(1-cos(x*y))/(x^2+y^2)` with
`y=sin(1/x)`, and `f(x,y)=(x*y)/sqrt(x^2+y^2)` with `y=+-x^2`.

### Coverage notes
- Correct path-dependent behaviour (kept as goldens): `01_path_dependent.out`
  shows `x*y/(x^2+y^2)` giving 0, 1/2, 2/5, -1/2, 0, 0 along
  `y=0, x, 2x, -x, x^2, 1/x`; `02_dir_paths.out`, `03_removable_paths.out`,
  `04_asymptotic_inf.out`, `mcp_calculus_paths.out` cover more paths and infinity.
- Correct slice-continuity verdicts (removable singularities, poles, jumps,
  essential oscillations) are in `05_continuity_slices.out` and
  `mcp_properties_slices.out`; all were checked against high-precision Python.
- All 17 golden files were generated twice and `diff`-ed: byte-identical.
