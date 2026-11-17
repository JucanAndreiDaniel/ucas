# Stress findings — `cfront_army`

Area: the C frontend's preprocessor and expression evaluator, exercised through
`c lower` (and `c optimize`, which shares the same preprocessor).  All files
here were mined from the owned sources `src/cf_pp.c`, `src/cf_emit.c`,
`src/cf_parse.c`, `src/cf_synth.c` and `src/cfx86.c`.

Binary: a freshly built `$ROOT/ucas`.  Goldens are the canonical
`env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ucas NAME.ucas > NAME.out`.

Severity legend: `CRASH` | `HANG` | `WRONG` | `LIMIT`.

Reference for the `#if` cases: `gcc -E -P` on the same C text.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | `//` comments ignored backslash-newline splicing; `#if` ignored C's signed/unsigned conversions and character-constant signedness |
| LIMIT | 2 | `#if` evaluated the dead side of `&&`, `\|\|` and `?:`; `__LINE__` / `__FILE__` were not predefined |

Six reproducible defects were found in `src/cf_pp.c` and fixed there (minimal,
local edits).  Four of them were already catalogued as un-fixed findings in the
sibling areas `cfront_preprocessor` (WRONG-1, WRONG-2, LIMIT-1, LIMIT-2) and are
now resolved; the `?:` half of the short-circuit bug and the macro-invocation
form of `__LINE__` were found during this hunt and are new.

Each fix has a durable CLI golden in this folder, plus control cases in the same
file that exercise the neighbouring correct behaviour.  `05_controls.ucas` is
an end-to-end control that exercises macros, `#if`/`defined`, comments, strings
and char literals without any of the trigger patterns.

---

## Fixes

### WRONG-1 — `//` comments did not observe backslash-newline splicing
**Severity:** WRONG  
**File:** `01_comment_splice.ucas` / `.out`

**Reproducer (before the fix):**
```
c lower nofile
```c
int w1(int x){
  // a comment \
  return 111;
  return 222;
}
```
```
Observed `w1(x) = 111`; `cc -E -P` leaves only `return 222;`.

**Why:** C translation phase 2 splices `\\\n` before comments are recognised, so
the whole thing is one comment and the live statement is `return 222;`.  In
`lex_file` (`src/cf_pp.c`) the `//` branch consumed up to the first `\n` and
ignored a preceding backslash.

**Fix:** the `//` scanner now recognises `\\\n` (and `\\\r\n`) inside the
comment, skipping it and incrementing the line counter, so the comment continues
onto the spliced line.  The top-level splice handling is unchanged.

### WRONG-2 — `#if` ignored C's signed/unsigned arithmetic conversions
**Severity:** WRONG  
**File:** `02_if_signed_unsigned.ucas` / `.out`

**Reproducer:** `#if -1 < 1U`, `#if 0xFFFFFFFFFFFFFFFF > 0`,
`#if -1 <= 0U`, `#if 9223372036854775808 > 0`, `#if '\xff' < 0`.

Observed (before): `111, 222, 111, 222, 222`.  Expected (gcc): `222, 111,
222, 111, 111`.

**Why:** `cx_prim` parsed every integer with `strtoull(..., 0)` and cast to
`int64_t`, and `cx_bin` did all arithmetic and comparisons in signed 64-bit.
C's `#if` uses `intmax_t`/`uintmax_t` with the usual arithmetic conversions: a
`U`-suffixed or too-large constant is unsigned and a negative operand converts
to the large unsigned value.  Plain character constants have type `int`; on
this signed-char target `'\xff'` is `-1` (and the old evaluator also failed to
parse hex/octal escapes, returning the letter `'x'`).

**Fix:** `#if` values now travel as a `{ int64_t bits, int unsigned }` pair.
`cx_prim` detects the `U` suffix and constants above `INT64_MAX`, decodes
character escapes (including `\xNN` and octal), and sign-extends plain char
constants from `signed char`; `cx_bin` applies the usual arithmetic conversions
to bitwise ops, `+ - * / %` and all comparisons, and keeps the result's
signedness for shifts and unary operators.

### LIMIT-1 — `#if` did not short-circuit `&&`, `||` or `?:`
**Severity:** LIMIT (hard error on valid C)  
**File:** `03_if_shortcircuit.ucas` / `.out`

**Reproducer:** `#if 1 || (1/0)` and `#if 0 && (1/0)` used to report
`#if: cannot evaluate the expression`; `#if 1 ? 111 : (1/0)` and
`#if 0 ? (1/0) : 222` failed the same way (the `?:` form is new).

**Why:** `cx_bin` evaluated both operands before applying `&&` / `||`, and
`cx_cond` evaluated both arms of `?:`.  The division by zero on the dead side
set `c->err`, rejecting the whole translation unit.

**Fix:** a `skip` counter on the evaluator makes a dead operand consume its
tokens without evaluating them (so a division by zero there is harmless).
`cx_bin` sets it for the right operand of `&&` / `||` when the left already
decides the result, and `cx_cond` for the untaken `?:` arm.  The evaluated side
still checks division by zero.

### LIMIT-2 — `__LINE__` and `__FILE__` were not predefined
**Severity:** LIMIT  
**File:** `04_line_file.ucas` / `.out`

**Reproducer:** `int f(void){return x + __LINE__;}` used to report
`'__LINE__' is not declared`.

**Fix:** `dyn_macro` expands these two dynamic macros wherever an identifier is
read (ordinary text and `#if` expressions, including macro arguments).  A token
that came out of a macro expansion uses the line/file of the *invocation*
(its group origin in the main file), not of the macro definition — otherwise
`#define HERE __LINE__` would always expand to the `#define` line.  `__FILE__`
expands to a quoted string of the current file's name, so `sizeof(__FILE__)`
on the block is 8 (`"<block>"`).

---

## Controls
`05_controls.ucas` covers ordinary preprocessor behaviour with none of the
trigger patterns: header prelude, object/function macros, `#if defined(...)`
with `&&`, `//` and `/* */` comments, a string containing comment markers, and
a character constant.  The `*_controls` functions inside files `01`–`04` are
per-fix controls.

## Checks that passed
* All 23 goldens in `cfront_preprocessor`, all 30 in `cfront_fuzz`, all 14 in
  `cfront_ub_contracts` and all 19 in `cfront_float_semantics` still match
  byte-for-byte after the fixes.
* A 41-expression `#if` sweep was compared against `gcc -E -P`: all cases now
  agree except `(1 << 64) == 1`, which is undefined behaviour in C (the
  evaluator masks the shift count to 63) and is deliberately left alone.
* ~1,000,000 calls of 57 generated arithmetic functions and ~250,000 calls of
  13 vectorised loops agreed between original and rewritten code under
  `c optimize ... check` (clang shim), so no emitted-C regression was found.

## Existing goldens needing recapture (not caused by these fixes)
* `tests/cfront.out` is stale from before the earlier cf waves (the popcount
  rewrite and the vectoriser's "shift by a variable" refusal are missing).
  It does not use `#if`, `__LINE__`, `__FILE__` or spliced comments, so these
  PP fixes did not change it.  Let the owning wave recapture it.
* The `repro_bug_*` files in `cfront_preprocessor` have no `.out` goldens (by
  design) and now produce the correct branches; no recapture is needed there.

## Out of scope / not changed
* `#line` is still accepted but does not remap diagnostics (LIMIT-3 in
  `cfront_preprocessor`); fixing it would change that area's
  `09_pragma_line.out` golden, which is owned elsewhere.
* The vectoriser's gather and symbolic-lower-bound cases that `c check`
  reports as mismatches were investigated: standalone compiled comparisons of
  the emitted code agree with the original.  The harness reports inputs where
  it supplies out-of-range indices / negative lower bounds, i.e. UB in the
  original that UBSan does not instrument for intrinsic gathers and raw pointer
  reads; they are harness artifacts, not synthesis defects.
