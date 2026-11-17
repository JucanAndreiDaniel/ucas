# Stress findings — `below_tolerance_float`

_Original heading: below_tolerance_float — findings_

# below_tolerance_float — findings

All commands use the prebuilt binary `$ROOT/ucas`. Every reproducer
was run under `timeout`.  Each `NN_*.ucas` / `NN_*.out` pair in this folder is a
deterministic golden (generated twice and `diff`-identical); the cases below are
the *wrong / masking* behaviours those goldens also exhibit.

Ground truth for every verdict was computed independently with Python `Fraction`
on the exact IEEE bit patterns (`_scratch/ground_truth.py`): the corpus has
**247 pairs**, of which **201 are genuinely different functions** and 46 are
genuinely equal.  ucas `equiv` (SAT) found 144 of the 201 real differences;
`error` found 144 too, but **on a different 54 pairs `equiv` found a real
difference while `error` reported "max abs error 0"**.  On 3 pairs `equiv` was
the one that missed the difference.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `error` reports "max abs error 0" on 54 genuinely different functions |
| LIMIT | 3 | `fit` hides a fixed sign bug by fitting the epsilon away |

## Findings

### WRONG-1 — `error` reports "max abs error 0" on 54 genuinely different functions
**Severity:** WRONG
**Expected:** _not recorded_
This is the central below-tolerance failure: the two functions differ at an
isolated point (or a very sparse set), which `equiv` finds by SAT but `error`
cannot see with its 65536 random samples.  Any sampled comparison with a
tolerance — the exact technique the Racer paper says misses these bugs —
concludes "no error".

**Reproducer:**
Reproducer (off-by-one `>` vs `>=`):

```sh
cd $ROOT/tests/stress/areas/float/below_tolerance_float
timeout 30 $ROOT/ucas 059_thresh_ge_zero.ucas
```

**Observed:** (verbatim from `059_thresh_ge_zero.out`):

```
> equiv f_thresh_ge_zero g_thresh_ge_zero
f_thresh_ge_zero and g_thresh_ge_zero differ, e.g. x=0: 0 vs 1 (found by SAT, checked by evaluation)
> error g_thresh_ge_zero ~ f_thresh_ge_zero
error of g_thresh_ge_zero against f_thresh_ge_zero:
  max abs error 0 at -
  max rel error 0 (0%) at -
  mean rel error 0 over 65536 points
  max 0 ulp
```

Second reproducer (`x==k` vs `|x-k|<=tol`, tol = 1e-4 — a whole shell of
differing inputs, not just one point):

```sh
timeout 30 $ROOT/ucas 102_eq_vs_tol_mask.ucas
```

```
f_eq_vs_tol_mask and g_eq_vs_tol_mask differ, e.g. x=0.4932...: 0 vs 1 (found by SAT, checked by evaluation)
error of g_eq_vs_tol_mask against f_eq_vs_tol_mask:
  max abs error 0 at -        mean rel error 0 over 65536 points
```

**Why it matters:** exact rational arithmetic on the IEEE pattern `x = 0x00000000`
gives `f = 0.0` (`0x00000000`) and `g = 1.0` (`0x3f800000`), an exact difference
of 1.  For `eq_vs_tol` the difference is an entire annulus around `0.5` (e.g.
`x = 0.499969482`): still missed because it occupies < 1/65536 of the domain.
`max abs error 0` is a false statement about the stated domain.  The headline
0 also disagrees with ucas's own `equiv` verdict in the same file.

Affected pairs (id : category): 32 × `thresh_ge` (59–80, 203–214),
11 × `eq_vs_tol` (102–128) and 11 × `ne_vs_tol` (103–129).  Full list is in
`_scratch/results.json` (54 cases with `equiv` = differ and `max_abs` = 0).
Pairs 81–83 are the mirror-image failure documented next.

### WRONG-2 — `equiv` answers "equal" for genuinely different functions when SAT gives up on division
**Severity:** WRONG
**Expected:** _not recorded_
The `> λ` vs `>= λ` pair with a `1/x` branch differs at exactly `x = λ`.  The SAT
circuit refuses "a float division (by other than a constant power of two)",
so `equiv` falls back to sampling, misses the single point, and says *equal*.

**Reproducer:**

```sh
timeout 30 $ROOT/ucas 081_thresh_val_div_eqv.ucas
```

**Observed:** (verbatim):

```
> equiv f_thresh_val_div_eqv g_thresh_val_div_eqv
f_thresh_val_div_eqv and g_thresh_val_div_eqv are equal on the domain of f_thresh_val_div_eqv (sampled, not proved; no SAT proof: a float division (by other than a constant power of two))
```

**Why it matters:** at `x = 0` (a point in the declared domain `-1..101`) `f = 0`
while `g = 1/0 = +inf` (`0x7f800000`); they are not equal.  The answer is
honestly labelled "sampled, not proved", but it still asserts *equal* and would
be read as a pass by any automated checker.  The same happens for thresholds
0.5 and 100 (ids 82, 83).  This is a second, independent demonstration of the
same measure-zero blind spot as finding 1, now in `equiv` itself.

### LIMIT-1 — `fit` hides a fixed sign bug by fitting the epsilon away
**Severity:** LIMIT
**Expected:** _not recorded_
The Racer InstanceNorm bug is `1/rstd^2 + eps` where `- eps` is required (a
2·eps error).  When the epsilon is left as a free parameter, `fit` chooses
`e = 0`, deleting the epsilon from the buggy expression, and then reports a
tiny error — certifying the buggy *form* as accurate when in reality a fixed
`eps = 1e-5` would give ~2e-5 relative error.

**Reproducer:**

```sh
timeout 30 $ROOT/ucas x_fit_mask.ucas
```

**Observed:** (verbatim from `x_fit_mask.out`):

```
fit buggy to correct (max relative error, 4096 sample points):
  e = 0
  objective 2.35443e-07
  1/(1/sqrt(x + 0)*(1/sqrt(x + 0))) + 0
  max abs error 2.28882e-05 at x=98.880249
  max rel error 2.4754e-07 (2.48e-05%) at x=0.0150492154
```

**Why it matters:** a parameter-fitting "equivalence" check is not an equivalence
check; it can mask a logic error by absorbing the wrong constant.  The reported
2.5e-7 should not be read as evidence that the `+ eps` form is correct.

### LIMIT-2 — `approx` symbolic minimax table says error 0 for a function with a unit spike
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 30 $ROOT/ucas x_approx_spike.ucas
```

**Observed:** (verbatim from `x_approx_spike.out`):

```
  fits in real arithmetic (max absolute error of P(x)):
    deg  cheb interp  cheb econ    minimax
    0    1            -            0
  ...
  1   minimax   0     horner+fma  1 abs                    1             1             0    at x=0
      P(x): 0.0
```

The real-arithmetic minimax column for degree 0 is `0`, i.e. "the constant zero
approximates this function perfectly", while the very next measured candidate
reports max abs error `1` at `x = 0`.  The symbolic fitter discards the
measure-zero spike (consistent with finding 1/2) even though the sampled stage
keeps it.  A tolerance-based acceptance of the symbolic result would accept a
zero function for a function that takes the value 1.

### LIMIT-3 — `equiv ... ftz` proves equality for a subnormal logic bug
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 30 $ROOT/ucas x_ftz_mask.ucas
```

**Observed:** (verbatim from `x_ftz_mask.out`):

```
equiv hf qf noftz
hf and qf differ at 99 points, e.g. x=2: 1.40129846e-45 vs 0
equiv hf qf ftz
hf and qf are equal on the domain of hf (exhaustive)
  every float operation flushed subnormals to zero (ftz)
```

`hf(x)=asfloat(x)*0.5` and `qf(x)=asfloat(x)*0.25` are genuinely different on
99 subnormal inputs.  With `ftz` the tool returns a *proved* equality.  This is
documented FTZ semantics, but it is exactly a "tolerance choice that masks a
real bug": a downstream checker using `ftz` would never see the error.

## Checks that passed

### Non-findings (verified correct — kept as goldens)
- `110_eq_vs_tol_below_ulp.ucas`: tol = 1e-8 < ½ ulp near 0.5, so `x==0.5` and
  `|x-0.5|<=tol` really are bit-identical f32 functions; SAT proves equality.
  A "below tolerance" bug that is genuinely invisible in the target type.
- `236_sqrt_square_eqv.ucas`: `sqrt(x^2) == x` for all positive f32/f64 in range
  (checked exactly with `Fraction` and by exhaustive-style sampling); the
  "equal (sampled)" verdict is correct, only unproved because SAT rejects `^`.
- The 46 genuinely-equal pairs all get `max abs error 0` from both tools — correct.
- No crashes, hangs, or nondeterminism were observed: all 42 corpus batches and
  all 22 golden files exited 0 under `timeout 30`; every golden was generated
  twice and diffed identical.
