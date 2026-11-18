# Stress findings — `algebra_army`

Area: bugs in the code that backs the abstract-algebra / ring CLI and JSON/MCP
commands.  Owned sources: `src/absalg_cmd.c`, `src/alg.h`, `src/ring.c`,
`src/ring_nlp.c`.  All reproducers use the absolute binary `$ROOT/ucas` and
the canonical environment `env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`.
Every `.ucas` golden below was captured from the **fixed** binary and verified
byte-identical on a second run.

---

## Summary

| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | silent input truncation in `pmsnf`, `absub`, `groebner`/`idealeq` polynomial lists, and long variable-name collision |
| LIMIT | 1 | widening `struct up` (`UD=40`) is unsafe without poly.c changes; the flagged "irreducible" bug is already fixed another way |

Root cause of three of the four WRONGs is the same helper:
`split_commas(s, part, max)` in `absalg_cmd.c` stops recording parts once
`n == max` but **returns the capped count**.  Callers that allocate a
fixed-size `part[64]` / `part[256]` therefore silently discard input past the
cap and then assert a passing self-check on the truncated problem.  The fix
in each case is to count top-level parts first (`nparts()`) and allocate a
dynamic array.

---

## WRONG-1 (flagged) — `pmsnf` silently drops rows / columns past the 64th

- **Source:** `src/absalg_cmd.c:2278`/`2285` (old): `split_commas(body+1, rows, 64)`
  and `split_commas(r+1, cells, 64)` with `char *rows[64]`, `char *cells[64]`.
- **Reproducer:** `pmsnf_65rows.ucas` = 64 rows `[x]` followed by one row `[1]`;
  `pmsnf_65cols.ucas` = one row with 64 `x` cells followed by `1`.
- **Before:** Smith form `diag(x), rank 1` — the trailing `1` was never read,
  yet the output still printed `check: U A V = D; ... verified` for the
  truncated matrix.  MCP `abstract_algebra.pmsnf` was affected too (same
  command path).
- **After (fixed):** `diag(1), rank 1` in both cases.
- **Control:** `pmsnf_64rows_control.ucas` (63 `[x]` + one `[1]`, 64 rows
  total) → `diag(1)` in both old and fixed binaries: the trailing `1` was
  inside the old cap, so the control did not change.
- **Fix:** dynamic `rows`/`cells` via `nparts()` + `xcalloc`.

## WRONG-2 (mined) — `absub` silently drops generators past the 64th

- **Source:** `src/absalg_cmd.c:1129`/`1134` (old): `char *part[64]`,
  `split_commas(s, part, 64)`.
- **Reproducer:** `absub_64gens.ucas` = `absub Z/2, [0], ... (63 zeros) ..., [1]`.
  The group plus 63 zero generators fill the 64 parts; the only nonzero
  generator is part 65.
- **Before:** `the subgroup generated in Z/2: 0` (trivial), `quotient: Z/2`,
  `index: 2` — with `check: every generator is a member ... verified` on the
  truncated generator set.
- **After (fixed):** `the subgroup generated in Z/2: Z/2`, `quotient: 0`,
  `index: 1`.
- **Control:** `absub_63gens_control.ucas` (62 zeros + `[1]`, 64 parts total)
  → `Z/2` in both binaries (the `[1]` is inside the old cap).
- **Fix:** dynamic `part` via `nparts()` + `xcalloc`, freed on the normal path.

## WRONG-3 (mined) — long variable names sharing a 15-char prefix collide

- **Source:** `src/absalg_cmd.c:1974-1980` (`popts` identifier collection) and
  `:1936` (`read_popts` `vars`), both copying at most 15 chars into
  `char w[16]` / `o->var[MPL_MAXV][16]`; `struct mring.name[MPL_MAXV][16]` in
  `src/alg.h`.  The remaining characters of a long identifier are skipped, so
  distinct names with a common 15-char prefix become the same variable.
- **Reproducer:** `varname_long.ucas` = `groebner xaaaaaaaaaaaaaa1 + xaaaaaaaaaaaaaa2`.
- **Before:** `input: f1 = 3*xaaaaaaaaaaaaaa` — one variable, basis
  `g1: xaaaaaaaaaaaaaa`, ring printed `(grevlex, xaaaaaaaaaaaaaa, over Q)`.
  The "check: ... verified" line is printed for the collapsed problem.
- **After (fixed):** `input: f1 = xaaaaaaaaaaaaaa1 + xaaaaaaaaaaaaaa2`, ring
  `(grevlex, xaaaaaaaaaaaaaa1 > xaaaaaaaaaaaaaa2, over Q)`, basis keeps both.
- **Control:** `varname_short_control.ucas` = `groebner a1 + a2` → two variables
  in both binaries.
- **Fix:** add `MPL_NAMELEN 64` in `alg.h`, widen `mring.name` and
  `popts.var`/local buffers to that length.  `mring_init` (ideal.c) uses
  `snprintf(..., sizeof R->name[i], ...)`, and `mpl_parse` compares full
  identifier lengths, so both automatically honour longer names.  Short-name
  output is unchanged (all existing goldens pass).

## WRONG-4 (mined) — `need_polys` silently drops polynomials past the 256th

- **Source:** `src/absalg_cmd.c:2041-2042` (old): `char *part[256]`,
  `split_commas(s, part, 256)`.  Affects `groebner`, `idealmember`, `idealeq`.
- **Reproducer:** `grob_257polys.ucas` = `groebner x, x, ... (256 x's) ..., 1`.
  The trailing `1` (which forces the unit ideal) is part 257.
- **Before:** the `1` is discarded; the basis of `<x>` is reported
  (`g1: x`) instead of the whole ring.
- **After (fixed):** `g1: 1` — the trailing polynomial is read.
- **Control:** `grob_256polys_control.ucas` (255 `x` + `1`, 256 parts total) →
  `g1: 1` in both binaries (the `1` is inside the old cap).
- **Fix:** dynamic `part` via `nparts()` + `xcalloc`.

---

## LIMIT-1 — `UD` widening and the flagged "irreducible" claim

The flagged `struct up` cap (`UD=40` in `src/alg.h`) causing false
"factors are irreducible over the rationals" claims past degree 40 is
**already fixed at HEAD** (commit `7505ec8`, which added
`mp_factor_uni_hi` / `mp_factor_sqf_hi` in `src/poly.c`).  Verified on the
current binary:

```
factor x^41-1   -> (x - 1)*(x^40 + ... + 1), check exact
factor (x-1)^50 -> (x - 1)^50
gcd x^65-1, x^5-1 -> x^5 - 1
```

so no wrong answer remains to fix in my files.  I did **not** widen `UD`,
because doing so is not safe without poly.c changes (poly.c is not mine):

1. `kronecker()` in poly.c declares `int64_t cand[40], cv[40]; int cnd[40]`
   but fills them with `for (i = 0; nc < 2*k+6 && i < 80; i++)` where `k` is
   the candidate factor degree (up to `g.d/2`).  With `UD > 40`, `k` can reach
   32, so `2*k+6 = 70` and the loop writes past these 40-element arrays —
   a stack buffer overflow.  (The arrays are already undersized for `k>=17`
   at `UD=40`.)  poly.c must bound the candidate count by the array size or
   size the arrays from `UD` before any widening.
2. `up_factor()`'s `struct up s[UD]` and `factor_sqf()`'s
   `static struct up cyc[UD+1]` grow linearly; `kronecker()`'s `A[UD+1]` and
   the repeated `up_mul` in Newton interpolation grow the hot path.  Callers
   in `rint.c` / `solve.c` grow too, notably
   `struct q A[(UD+2)*(UD+2)]` in rint.c (quadratic: 42^2 → 66^2 ≈ 70 KB at
   `UD=64`, still acceptable, but worth measuring).
3. The comment at poly.c:1622 ("struct up is capped at UD=40") becomes stale;
   the `mp_factor_uni_hi` fallback must still cover degrees `UD+1..HD(255)`.

A sensible follow-up (owned by the poly.c owner) is: fix `kronecker`'s array
bounds, then raise `UD` to 64 so degrees 41-64 use the complete Kronecker
factorisation instead of the linear+cyclotomic-only sparse fallback.  Until
then, leaving `UD=40` keeps the false-irreducible bug fixed and avoids
introducing an overflow.

---

## Existing goldens needing recapture (outside this area)

The pmsnf fix changes output in two goldens in
`tests/stress/areas/math/sparse_large_matrices/`, which record the old buggy
answer and must be recaptured by that area's owner:

- `04_repro_pmsnf_65cols.out`: `diag(x)` → `diag(1)`
- `05_repro_pmsnf_65rows.out`: `diag(x)` → `diag(1)`

`03_repro_pmsnf_64rows.out` (`diag(x)`, all-`x` rows) and
`06_repro_pmsnf_65rows_control.out` (`diag(1)`, 64 rows) are unchanged.
No goldens in `polynomial_gcd_resultant` change: the fixes touch only
argument parsing/name storage, not the gcd/factor/resultant arithmetic.

## Checks that passed

- All 9 new goldens in this area reproduce byte-identically on a second run.
- Controls at/below each old cap are unchanged.
- `factor x^41-1`, `factor (x-1)^50`, `gcd x^65-1, x^5-1` confirm the
  already-fixed high-degree algebra behaviour.
