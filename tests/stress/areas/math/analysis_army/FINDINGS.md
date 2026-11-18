# Stress findings — `analysis_army`

Area: additional reproducible analysis bugs mined while fixing the flagged
`crit_classification` / `math_function_domain` findings. All reproducers below
were captured from the **fixed** binary (the binary that includes the
`crit_roots`/`cmd_crit` and `list_conditions` fixes for the flagged WRONG
findings). Every golden was produced twice under the canonical environment
(`UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`) and `diff`ed byte-identical; all exit
0. The bugs below are **documented, not fixed** — the goldens lock in current
behaviour so a future change is noticed. `90_controls.ucas` exercises the
neighbouring behaviour that must stay stable.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | float-typed `crit` silently drops extrema; `domain` except-list ignores `where`; a kink is located at ~2e-33 instead of 0 |
| WRONG | 1 (no golden) | `domain` except-list emits ~10 000 spurious singularities when the denominator is zero on a whole interval |

## Findings

### BUG-1 — `crit` on a float-typed parameter silently drops critical points
**Severity:** WRONG
**Golden:** `01_float_crit_missed.ucas` / `.out`

**Reproducer:**
```sh
cd tests/stress/areas/math/analysis_army
$ROOT/ucas 01_float_crit_missed.ucas
```

**Observed:** for `a(x: f64 in -5..5) = sin(x)`, `crit a` reports a single
point (`x ≈ -1.570796327`), although `sin` has extrema at ±π/2 and ±3π/2
(four in `[-5,5]`). For `b(x: f64 in 0..10) = sin(x)` it reports the two
maxima at π/2 and 5π/2 but misses the minimum at 3π/2. For
`c(x: f64 in -10..10) = cos(x)` it reports four of the seven extrema in
`[-10,10]` (missing ±3π). `f32` is affected too (two of four for `d`).

**Why it matters:** the same function with a `real` parameter reports every
extremum (see `90_controls.ucas`, `c(x: real in -5..5) = sin(x)` → four
points). `cmd_crit` detects extrema by a sign change of `f'` between
*consecutive* samples, which assumes a monotonically ordered sweep. A
machine-float domain is sampled by bit pattern (`diter_next` in `eval.c`:
`rnd(d) % sz` after the two endpoint keys), so `x` is not monotonic; the
`x <= prevx` sweep-reset in `cmd_crit` fires at almost every step and clears
the `prevd` needed for a sign change. The result is a silent, deterministic
under-count with no warning. Root cause: `cmd_crit`'s consecutive-sample
sign-change detector combined with the non-monotonic float sampler.

### BUG-2 — `domain`'s "except" singularity list ignores a `where` narrowing
**Severity:** WRONG
**Golden:** `02_domain_where_except.ucas` / `.out`

**Reproducer:**
```sh
$ROOT/ucas 02_domain_where_except.ucas
```

**Observed:**
```
domain of f:  f(x: real in -10..10) = 1/x where x > 5
  where x > 5
  defined on ... x in [5.001, 10]
    except x ≈ 0  (x = 0)
```
`x = 0` is outside the `where x > 5` domain (the "defined on" interval is
`[5.001, 10]`), so listing it as an excluded point is spurious. The same
happens for `g` (`except x ≈ 1` while `x < -2`) and `h` (`except x ≈ 0.5`
while `x < 0.2`).

**Why it matters:** `domain_real1`'s "except" scan walks every real `O_DIV`
denominator over the parameter's whole `[rlo,rhi]` and never tests the
`where` clause at the candidate, so it reports singularities the function
can never reach. Root cause: `domain_real1()` in `analyze.c` (the
`except` scan added to `list_conditions`-adjacent domain reporting).

### BUG-3 — a kink is located at a noise coordinate instead of the grid point
**Severity:** WRONG
**Golden:** `03_kink_noise_coord.ucas` / `.out`

**Reproducer:**
```sh
$ROOT/ucas 03_kink_noise_coord.ucas
```

**Observed:**
```
crit (x>=0 ? x : -x):
  x ≈ -1.972152263e-33: local minimum, x >= 0 ? x : -x = 1.972152263e-33
```
The function is `abs(x)` written as a conditional; its minimum is exactly at
`x = 0` with value 0. `bisect()` converges to the jump in `f'` from the left
and returns `-2e-33` (and a noise function value) instead of snapping to the
grid node `x = 0`. By contrast `crit abs(x)` (control, `90_controls.ucas`)
reports `x ≈ 0: local minimum, abs(x) = 0` cleanly, because the built-in
`abs` derivative gives `sign(0) = 0` and is caught by the zero-run path.

**Why it matters:** a programmatic consumer reading `analyze.crit` gets a
physically meaningless coordinate/value for a kink at 0, and the result
depends on how the same function was spelled. Root cause: `bisect()` in
`analyze.c` bisects a jump discontinuity to machine epsilon instead of
recognising that the sign change sits at a grid endpoint.

### BUG-4 — `domain` except-list explodes on a zero plateau (no golden)
**Severity:** WRONG
**Reproducer (documented only; ~10 000 lines, omitted as a golden):**
```sh
$ROOT/ucas -e 'domain 1/sin(x>=0)' | wc -l    # ~10005
```
When a denominator is exactly 0 on a whole interval (here the
`real(x >= 0)` cast is 0 for `x < 0`, so `sin(0) = 0` there), the `fa == 0`
clause of the except-scan reports *every* grid node in that interval as a
separate `except x ≈ ...`. This is a pre-existing issue in the real `O_DIV`
except-scan; the new `sec`/`csc`/`cot` singularity cases inherit it when an
inline-annotated argument is boolean-cast. Not promoted to a golden because
its output is ~250 KB.

## Controls (`90_controls.ucas`)
- `crit abs(x)` → clean `x ≈ 0` local minimum (contrast with BUG-3).
- `crit x^3 - x`, `crit (x: real in -5..5) = sin(x)`, `crit cos(x)` → all
  isolated extrema found (contrast with BUG-1).
- `domain 1/x` → single `except x ≈ 0` (correct isolated singularity).
- `range f` for `f(x) = 1/x where x > 5` → `[0.1, 0.2]` (range respects the
  `where` clause even though the `domain` except-list does not — BUG-2).
- `crit x + sin(x)` (off-grid touching zeros), `crit exp(-1/x^2)` (no
  underflow points) → the flagged WRONG-1/WRONG-2 fixes hold.

## Checks that passed
- All four goldens are deterministic (two runs, byte-identical) and exit 0.
- No crashes or hangs were found in the mined cases.
