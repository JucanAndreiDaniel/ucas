# Stress findings — `float_exhaustive`

_Original heading: Findings — float_exhaustive_

# Findings — float_exhaustive

Area: exhaustive bit-pattern float testing. Harness: `exhaustive.py`, `casts.py`,
golden generator: `make_goldens.py`. Oracle: exact IEEE bit decoding + mpmath at
200-bit precision + exact integer round-to-nearest-even (ties to even).

Summary of what was swept: **all 65536 f16 bit patterns for 8 unary ops**
(abs, sqrt, log, exp, sin, floor, ceil, roundeven) = 524288 comparisons;
**32892 strided/special-region f32 patterns** for the same ops; **all 65536
f16→f32 casts** and 2172 f32→f16 casts; **2619 rational→f32 conversions**.

Numerically, ucas's f16/f32 unary ops and conversions matched the exact oracle
**everywhere** (0 correct-rounding errors, 0 signed-zero errors in value
production, 0 f16↔f32 conversion errors). All bugs below are in the *analysis /
domain* layer and in NaN-payload handling of `abs`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `equiv` is unsound: float domain silently excludes `-0` and all NaNs |
| LIMIT | 2 | out-of-domain unary ops stay symbolic on direct calls; only `table` materialises the IEEE … |

## Findings

### WRONG-1 — `equiv` is unsound: float domain silently excludes `-0` and all NaNs
**Severity:** WRONG
**Why it matters:** _not recorded_
The float domain used by `domain` / `range` / `equiv` claims "every finite
value" but has one fewer point than there are finite patterns, and excludes
all NaNs and infinities. Consequently `equiv` proves two functions equal even
though exhaustive bit comparison shows 1023 differing f16 inputs (negative
zero plus all 1022 signalling NaNs).

False "equal" for f16 (also f32/f64 via SAT):

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/float/float_exhaustive
$ROOT/ucas 18_equiv_signed_zero.ucas
```

**Observed:** (`18_equiv_signed_zero.out`):

```
> equiv f16a ~ f16b
f16a and f16b are equal on the domain of f16a (exhaustive)
> equiv f16a ~ f16b nanbits
f16a and f16b are equal on the domain of f16a (exhaustive)
  NaN results compared by their bits, sign and payload (nanbits)
> equiv f32a ~ f32b
f32a and f32b are equal on the domain of f32a (proved by SAT: 5531 AIG nodes, 1335 conflicts)
> equiv f64a ~ f64b
f64a and f64b are equal on the domain of f64a (proved by SAT: 12754 AIG nodes, 5670 conflicts)
```

where `f16a(x:f16)=x` and `f16b(x:f16)=x+0`. They actually differ:

```
p16(x:u16)=asfloat(x)
I16(x:u16)=asuint(p16(x));  A16(x:u16)=asuint(p16(x)+0.0)
I16(0x8000)   -> 32768   (= -0)
A16(0x8000)   -> 0       (= +0)      IEEE: (-0)+(+0) = +0
I16(0x7c01)   -> 31745   (sNaN 0x7C01)
A16(0x7c01)   -> 32257   (quieted 0x7E01)
```

Exhaustive table diff (`x` vs `x+0`): **1023 differing points** — `-0` and all
1022 sNaN patterns. `equiv ... nanbits` still says equal, i.e. the `nanbits`
mode flag cannot catch a NaN-payload counterexample because NaNs are excluded
from the domain. This is exactly the "silently drop a counterexample" failure
the suite rules warn about.

Domain counts are off by one, confirming `-0` is dropped
(`20_domain_counts.out`):

```
domain of id16:  defined at 63487 of 63487 points   (63488 finite f16 patterns exist)
domain of id32:  domain has 4278190079 points       (4278190080 finite f32 patterns exist)
domain of id64:  domain has 18437736874454810623    (one fewer than the true count)
```

**Expected:** `equiv` must report a counterexample at `x = -0` (and, with
`nanbits`, at an sNaN input), and the domain counts should include `-0`.

### WRONG-2 — WRONG / NAN — `abs` quiets sNaN for f32 and f64 but preserves it for f16
**Severity:** WRONG
_Original classification: `WRONG / NAN`._
**Why it matters:** _not recorded_
`abs` is a bit-level sign change; ucas's f16 implementation preserves the
signalling-NaN payload while f32/f64 change it into a quiet NaN. The same
operation is format-inconsistent. Reproducer (`16_nan_abs_inconsistent.ucas`):

**Reproducer:**
```sh
a16(x:u16)=asuint(abs(asfloat(x)))
a32(x:u32)=asuint(abs(asfloat(x)))
a64(x:u64)=asuint(abs(asfloat(x)))
a16(0x7c01); a16(0xfc01); a32(0x7f800001); a64(0x7ff0000000000001)
```

**Observed:** (`16_nan_abs_inconsistent.out`):

```
a16(0x7c01)                 -> 31745                (0x7C01, sNaN preserved)
a16(0xfc01)                 -> 31745                (0x7C01, sign cleared, sNaN preserved)
a32(0x7f800001)             -> 2143289345           (0x7FC00001, sNaN QUIETED)
a32(0xff800001)             -> 2143289345           (0x7FC00001, sNaN quieted, sign cleared)
a64(0x7ff0000000000001)     -> 9218868437227405313  (0x7FF8000000000001, sNaN QUIETED)
```

**Expected:** either preserve the payload in all formats (f16 behaviour) or quiet
it in all formats; the inconsistency itself is a bug. By contrast the
computational ops (`sqrt`, `sin`, `floor`, `ceil`, `roundeven`) quiet sNaN
consistently in f16 (`17_f16_snAN_quiet.out`), so only `abs` is anomalous.

### LIMIT-1 — out-of-domain unary ops stay symbolic on direct calls; only `table` materialises the IEEE result
**Severity:** LIMIT
**Why it matters:** _not recorded_
A `u16`/`u32`-valued wrapper around e.g. `log` does not evaluate on a direct
call when the mathematical result is -inf/NaN/+inf; it returns an unevaluated
`asuint(...)` expression instead of a concrete bit pattern. Forcing the same
expression through `table` yields the correct concrete value. Reproducers:
`13_f16_domain_symbolic.ucas`, `14_f32_domain_symbolic.ucas`,
`15_forced_domain_numeric.ucas`.

**Observed:** direct call:

**Reproducer:**
```sh
LG(x:u16)=asuint(log(asfloat(x)))
LG(0x0000)
_() = asuint(log(0))
  -> u16
SQ(0xbc00)
_() = asuint(sqrt(-1))
  -> u16
EX(0x7bff)
_() = asuint(exp(65504))
  -> u16
```

But the identical expression via `table`:

```
lgz(x:u16)=asuint(log(asfloat(0x0)));  table lgz max 1
  x=0  ->  4286578688                 (= 0xFF800000, -inf)
```

Same for `log(negative)` → NaN, `sqrt(negative)` → NaN, `exp(large)` → +inf.
**Expected:** a function whose declared result type is `u16` should return a
concrete bit pattern on a direct call, or at least behave the same way as the
`table` path. Severity LIMIT (definition/reduction inconsistency rather than a
wrong numeric value), but it is a real reproducibility trap: the answer
depends on whether you call the function or table it.

### LIMIT-2 — f32/f64 `range` is sampled yet `equiv` advertises SAT "proofs"
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`range` of an f32/f64 identity reports `sampled 65536 points (... not
exhaustive)`, so range claims for large formats are not sound. This matters
in combination with finding 1: an `equiv` "proved by SAT" result can still be
wrong because the encoded domain omits `-0` and NaNs. No concrete excluded
reachable value was found by the sampled sweeps, so this is recorded as a
LIMIT rather than a WRONG. (`20_domain_counts.out`, `24_equiv_sanity.out`.)

## Checks that passed

_No separate passed checks were recorded in the original document._
