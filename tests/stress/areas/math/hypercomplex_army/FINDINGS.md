# Stress findings — `hypercomplex_army` (ARMY2)

Binary: `$ROOT/ucas`, rebuilt from `src/hyper.c` with the fixes below.  All
goldens were generated twice under the stress environment
(`UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`) and diffed byte-for-byte — 5/5
stable.  No commit, no PR.

## Scope note

The two handed-down bugs (WRONG-1, WRONG-2 in `../hypercomplex_algebras/FINDINGS.md`)
live in `src/hyper.c`, as do the two further bugs mined here.  `src/hyper.c`
had to be edited to fix them even though the nominal source scope was
`cx.c`, `excouple.c`, `scheme.c`, `gfield.c`.  The latter four were reviewed;
no new CLI-observable bug was found in them (the only issue on record is the
benign dangling `multv` pointer at `src/gfield.c:1372`, already documented in
`systems/static_analysis/FINDINGS.md` and not changed here).

## Fixes (all in `src/hyper.c`)

### FIX-1 (formerly WRONG-1) — associator verdict uses relative, per-component scale
**Reproducer (before):** `associator 100.1+i, 100.2+j, 100.3+k` reported
"not associative" although the two products printed identically; residual
`1.16e-10` is IEEE-754 rounding at magnitude ~1e6.
**Root cause:** `cmd_assoc` used an absolute `h_n2(r,d) < 1e-24` (i.e. |r| < 1e-12).
**Fix:** new `h_assoc(a,b,d)` helper: associative iff for every component
`|a[k]-b[k]| <= 1e-9*max(|a[k]|,|b[k]|) + 1e-12`.  Verified that both the
original false positives and a regression found while testing (genuine
octonion non-associativity with all other components ~1e27, residual `2 e7`)
are now classified correctly; small non-associativity (`e1/1000, e2/1000,
e4/1000`) is still detected.

### FIX-2 (formerly WRONG-2) — consistent unit reading for `2e1`
**Reproducer (before):** `2e1` alone → `20`, `conj(1+2e1)` → `21`,
`abs(1+2e1+3e2+4e3)` → `4321`, but `(1+2e1)*(1+e2)` → `1 + 2 e1 + e2 + 2 e3`.
**Root cause:** `hy_scan` set `S->oct_num` for a numeric `NeM` token but never
contributed to `S->emax`, so `hy_decide` left `S->lg < 3` and `hy_prep` never
inserted the `2*e1` reading unless an explicit `eN` identifier was present.
**Fix:** a bare `NeM` with coefficient > 1 and unit index <= 3 (the natural
`2e1`, `3e2`, `4e3` forms) now bumps `emax`, forcing the octonion context.
Canonical scientific notation (`1e3`, `2e10`, `2.0e1`, `7e20`) is untouched —
this avoids the much larger regression of reading `1e3` as the unit `e3`.
All six reproducer spellings now agree, with the existing note.

### FIX-3 (NEW-1) — `1e8+e1` became a free variable `e8`
**Reproducer (before):** `1e8+e1` → `_(e8: real) = e8 + e1`;
`commutator 1e8+e1, 2e8+3e1` → "a constant is needed (e8 is a variable)".
**Root cause:** `hy_prep` rewrote every `NeM` to `N eM` whenever `lg >= 3`,
even when `eM` does not exist in the chosen algebra (e8 needs the sedenions;
the expression's `e1` had selected the octonions).
**Fix:** rewrite only when the exponent `eu` satisfies `0 < eu < (1<<lg)`.
`1e8+e1` is now `100000000 + e1` and the commutator/associator compute.

### FIX-4 (NEW-2) — non-finite rotation angle produced INT64_MIN garbage
**Reproducer (before):** `rotate (1,2,3) by inf about (1,0,0)` printed a
quaternion with components like `-9223372036854775808 - 8sqrt(2)` — `inf`
was taken as degrees and `cos(inf)/sin(inf)` (NaN) flowed into `forms_num`.
**Root cause:** `angle_of` never checked `isfinite`; the "large integer means
degrees" test also fired on `inf` because `inf == floor(inf)`.
**Fix:** reject non-finite angles with `the angle must be finite`.
Related: `cmd_rotate` printed `rotate (1, 2, 3)` before validating the angle
or axis, leaving a partial header concatenated with the error message; the
header is now emitted only after validation succeeds.

## Goldens in this folder

| File | Purpose |
|------|---------|
| `01_assoc_fix.ucas/.out` | FIX-1: associative verdicts for large/fractional inputs; genuine non-associativity (including a huge-component case) still detected |
| `02_ecoeff_fix.ucas/.out` | FIX-2: all six `2e1` spellings + scientific-notation controls (`2.0e1`, `1e3+1`, `2e10`) |
| `03_new_eunit_range.ucas/.out` | FIX-3: exponent at/above the algebra dimension stays numeric (`1e8`); `1e5` shows the valid-unit boundary |
| `04_new_inf_angle.ucas/.out` | FIX-4: `inf` angle cleanly rejected; finite 90-degree control unaffected |
| `05_controls.ucas/.out` | unit associators/commutators, `conj`/`abs`, `1e3`, `table quaternion`, `zerodivisors cd 8` — unchanged behaviour |

## Existing goldens needing recapture (done)

`../hypercomplex_algebras/81_bug_assoc_large.out` and
`82_bug_ecoeff_parse.out` recorded the old, wrong behaviour.  Both were
recaptured from the fixed binary; their `.ucas` inputs are unchanged.  The
`FINDINGS.md` there is annotated with the FIXED status.  No other golden in
`hypercomplex_algebras` changed (10/10 unaffected).

## Verification

`TMPDIR=/var/tmp/ucas-verify bmake stress-test STRESSLIST=/var/tmp/ucas-verify/stress-list STRESS_AREA=hypercomplex_algebras`
and `... STRESS_AREA=hypercomplex_army` both pass.
