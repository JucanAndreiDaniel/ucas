# Stress findings — `hypercomplex_algebras`

_Original heading: Hypercomplex algebras — stress-test findings_

# Hypercomplex algebras — stress-test findings

Binary: `$ROOT/ucas` (already built; no rebuild). All commands below were
run under `timeout 15`/`timeout 30` from this folder. Exit codes were 0 unless stated.
`81_*.ucas` / `82_*.ucas` are *bug goldens*: they record the current (wrong) behaviour so the
bug stays reproducible; they are not assertions that the behaviour is correct.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `associator` reports non-associativity for quaternions (and for associative octonion subal… |
| LIMIT | 1 | malformed `cd(N)` spellings are accepted and a standalone `cd(4)` is not algebra syntax |

**Update (ARMY2):** WRONG-1 and WRONG-2 are now **FIXED** in `src/hyper.c`; the
two bug goldens (`81_`, `82_`) were recaptured from the fixed binary and now
record the corrected behaviour.  See `../hypercomplex_army/FINDINGS.md` for the
fixes, two further bugs found and fixed, and regression/control goldens.

## Findings

### WRONG-1 — `associator` reports non-associativity for quaternions (and for associative octonion subalgebras) when only floating-point rounding is at fault
**Severity:** WRONG — **FIXED** (ARMY2): `cmd_assoc` now uses `h_assoc()`, a
component-wise relative test (`|r1[k]-r2[k]| <= 1e-9 * max(|r1[k]|,|r2[k]|) + 1e-12`)
instead of the absolute `h_n2(r,d) < 1e-24`.  This also avoids the opposite
failure (a genuine failure in a small component hidden by huge components).
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI, copy-pasteable from this directory):

```sh
cd $ROOT/tests/stress/areas/math/hypercomplex_algebras
$ROOT/ucas -e 'associator 100.1+i, 100.2+j, 100.3+k'
$ROOT/ucas -e 'associator 1000.1+e1, 1000.2+e2, 1000.3+e3'
# or run the durable golden:
$ROOT/ucas 81_bug_assoc_large.ucas > /tmp/got 2>&1; diff -u 81_bug_assoc_large.out /tmp/got
```

**Observed:** output (verbatim):

```
> associator 100.1+i, 100.2+j, 100.3+k
[a, b, c] = (ab)c - a(bc) = 503005003/500 + 253754i/25 + 993983j/100 + 253258k/25 - (503005003/500 + 253754i/25 + 993983j/100 + 253258k/25) = 1.164153218e-10
  not associative: the grouping changes the product (in the quaternions)
> associator 1000.1+e1, 1000.2+e2, 1000.3+e3
[a, b, c] = (ab)c - a(bc) = 166099618095/166 + 25037504 e1/25 + 99939983 e2/100 + 25032508 e3/25 - (166099618095/166 + 25037504 e1/25 + 99939983 e2/100 + 25032508 e3/25) = -1.192092896e-07
  not associative: the grouping changes the product (in the octonions)
```

**Why it matters:** the quaternions **are** associative, and `{1, e1, e2, e3}` generates a
quaternion subalgebra of the octonions, so `[a,b,c] = 0` exactly for these inputs. The two
products printed in the headline are textually *identical* — the residual `1.16e-10` /
`1.19e-07` is pure IEEE-754 rounding at magnitude ~1e6 (relative error ~1e-16). The decision
in `cmd_assoc` uses an **absolute** threshold `h_n2(r,d) < 1e-24`, i.e. `|r| < 1e-12`,
which is meaningless once the operands are large. It should use a relative test (as `h_close`
does elsewhere in the same file). This is exactly the "non-associativity reported where it
should hold" failure mode. It is deterministic (same output on repeated runs), so a bug golden
is kept. A 120-case fuzz with coefficients drawn uniformly from [-1e6, 1e6] produced 119 false
"not associative" verdicts in the quaternions; the pattern above is the minimized form.

Related: the residual threshold also misbehaves at the other extreme — quaternion associators
with fractional coefficients print a mathematically-zero result as `0i + 0k` or
`0 - 0i - 0j - 0k` (tiny non-zero doubles that `%.10g` renders as 0), e.g.
`associator (1+i)/3, (1+j)/7, (1+k)/11`. Cosmetic, but it is the same missing relative scale.

### WRONG-2 — a numeric coefficient on an `e`-unit is parsed as scientific notation in isolation, but as `coef*eN` inside a hypercomplex expression
**Severity:** WRONG — **FIXED** (ARMY2): `hy_scan()` now makes a bare `2e1`,
`3e2` or `4e3` (coefficient > 1, unit index <= 3) force the octonion algebra,
so `conj(1+2e1)`, `abs(1+2e1+3e2+4e3)` and `(1+2e1)^2` take the unit reading
just as `(1+2e1)*(1+e2)` already did.  Canonical scientific forms (`1e3`,
`2e10`, `2.0e1`) are unchanged.  A separate fix stops `hy_prep()` from turning
`1e8` into a unit `e8` that does not exist in an octonion.
_Original classification: `WRONG / NLP`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/hypercomplex_algebras
$ROOT/ucas 82_bug_ecoeff_parse.ucas > /tmp/got 2>&1; diff -u 82_bug_ecoeff_parse.out /tmp/got
$ROOT/ucas -e 'conj(1+2e1)'
$ROOT/ucas -e '(1+2e1)*(1+e2)'
```

**Observed:** output (verbatim, selected lines):

```
> 2e1
20
> 1+2e1
21
> conj(1+2e1)
conj((1+2e1)) = 21
  check: equal numerically (21, complex arithmetic)
> abs(1+2e1+3e2+4e3)
4321
> (1+2e1)^2
441
> (1+2e1)*(1+e2)
  note: 2e1 is read as 2*e1 (a unit), not the number 20; write 20 or 2.0e1 for the number
1 + 2 e1 + e2 + 2 e3
> 2*e1+3*e2
2 e1 + 3 e2
```

**Why it matters:** `2e1` is a C-style float literal (2×10¹) *and* the natural notation for
`2 * e1`. The tool resolves that ambiguity **inconsistently**: in `(1+2e1)*(1+e2)` it chooses
the unit reading and even prints a note saying so, but in `conj(1+2e1)`, `abs(1+2e1+3e2+4e3)`
and `(1+2e1)^2` it silently chooses the decimal reading. So a user asking for the conjugate
of the quaternion/octonion `1+2e1` gets `21`, and the norm of `1+2e1+3e2+4e3` gets `4321`
(the scalar 1+20+300+4000), with no hint that a hypercomplex interpretation was available.
`conj(1+2i)` and `conj(1+e1+e2+e3)` work correctly — the failure is specific to a *numeric
coefficient* glued to an `e`-unit. Severity WRONG because the returned number is mathematically
unrelated to the requested hypercomplex value, not merely a parse error.

### LIMIT-1 — malformed `cd(N)` spellings are accepted and a standalone `cd(4)` is not algebra syntax
**Severity:** LIMIT
_Original classification: `LIMIT / NLP`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/hypercomplex_algebras
$ROOT/ucas -e 'table cd16x'   # accepted: atoi("16x") == 16 -> sedenion table
$ROOT/ucas -e 'cd(4)'         # not read as the algebra
```

**Observed:** output:

```
> table cd16x
multiplication table of the sedenions (row times column), not symmetric: the product does not commute:
        |     1    e1 ...
...
> cd(4)
  note: 'cd' read as c*d (single-letter variables)
_(c: real, d: real) = 4(c*d)
  -> real
```

**Why it matters:** `alg_word` uses `atoi(w+2)` with no end-of-token check, so `cd16x`, `cd4zz`,
`cd 2.9` etc. silently name a valid algebra. Conversely `cd(N)` is only recognized after a
command keyword (`algebra`, `table`, `zerodivisors`); as a standalone expression it is parsed
as the product of variables `c` and `d`. Even `N` values that are not powers of two are
correctly rejected (`algebra cd 3` → `cd(N): N is 2, 4, 8, 16 or 32`), and there is no crash
or hang for any `cd(N)` up to 32, so this is a low-severity parsing/limit issue, not an
unsoundness in the algebra itself. `07_cd_parse.ucas/.out` covers these cases.

## Checks that passed

### Verified clean (no finding)
For the record, these focus-area checks found **no** defect and are preserved as goldens:

* **Multiplication tables** for `cd(2), cd(4), cd(8), cd(16), cd(32)` (`01_tables`) were parsed
  cell-by-cell and compared against an independently implemented Cayley–Dickson doubling in
  Python: 0 mismatches across all 2+4+8+16+32 = 62 rows / 1364 cells. Aliases `cd 4` ≡
  `quaternion`, `cd 8` ≡ `octonion`, `cd 16` ≡ `sedenion` produce byte-identical table and
  `algebra` output.
* **Zero divisors**: `zero_div` finds `(e1 - e10)(e4 + e15) = 0` in sedenions/cd(32); both
  sign variants evaluate to exactly `0` and `|ab| = 0` while `|a| = |b| = sqrt(2)`.
  `cd(2/4/8)` correctly report no zero divisors.
* **Associators/commutators** with integer unit arguments: all 64 quaternion triples and all
  512 octonion triples matched the reference associator exactly (0 wrong signs/values).
  20 selected cases are in `03_assoc_comm`.
* **Rotations**: 200+ `rotate` cases, 20+ `rotmatrix`, 38 externally generated `frommatrix`
  matrices (including all trace≤0 branches), 20+ `axisangle` and 15+ `slerp` calls. Internal
  checks never printed `DIFFERENT` or `FAILS`; spot-checked matrices (−90°/90°/180° about
  x/y/z, 90° about (1,1,1), 120° about (1,1,1)) match the analytic right-handed matrices.
  `slerp` at t=0/1, antipodal and coincident quaternions behaves consistently.
* **`algebra` properties** for all five algebras (commutativity, associativity, alternativity,
  flexibility/power-associativity, norm multiplicativity, division, inverses, conjugation)
  agree with the mathematical status of each algebra; `hrng = 4242` makes the random checks
  reproducible.
* **cd(32) robustness**: `table cd 32` (7069 bytes), full `algebra cd 32`, `zerodivisors cd 32`
  and `associator`/`commutator`/expression evaluation with e16..e31 all completed in <0.2 s
  with exit 0. No crash, hang, truncation or stack overflow observed.
* **Determinism**: every `.ucas` and `.jsonl` golden was generated twice and the two outputs
  diffed byte-for-byte — all 12 goldens are stable. (Float-formatting/GIF-checksum drift seen
  in the repo-root `hyper.diff` is from a *different*, complex-analysis test and does not
  affect these hypercomplex goldens.)
