# SUMMARY — `float_exhaustive`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 25
- Files created: not recorded

### Coverage (distinct expressions / comparisons tried)

- **f16 exhaustive**: all 65536 bit patterns × 8 unary ops (`abs`, `sqrt`,
  `log`, `exp`, `sin`, `floor`, `ceil`, `roundeven`) = **524288** exact-oracle
  comparisons via `table` (one ucas process per op, ~0.13 s each).
- **f32 sampled**: 32892 strided/special-region bit patterns (whole 2^32 space
  at 2^17 stride, plus dense zero/subnormal/min-normal/max-normal/inf/NaN
  neighbourhoods and all powers of two) × 8 ops = **263136** comparisons.
- **f16→f32 casts**: all 65536 patterns. **f32→f16 casts**: 2172 patterns.
- **f16 asuint/asfloat round-trip**: all 65536 patterns (0 mismatches).
- **Rational→f32 conversions**: 2619 exact fractions (0 mismatches).
- `range`/`domain`/`equiv` probes on f16/f32/f64 (signed zero, NaNs, modes).
- Direct exploratory probes of special values for every op (zeros, subnormals,
  min/max normal, ±inf, qNaN/sNaN, ±).

Total distinct oracle comparisons: **~870,000**. Distinct golden statements:
**268** across 25 `.ucas`/`.out` pairs.

### Files created

- `exhaustive.py` — exhaustive f16 + sampled f32 harness with exact oracle
  (IEEE bit decode, mpmath 200-bit transcendentals, exact integer
  round-to-nearest-even).
- `casts.py` — f16↔f32 conversion checker.
- `make_goldens.py` — deterministic golden generator (runs each file twice,
  writes `.out` only if byte-identical).
- `01_*.ucas` … `25_*.ucas` + matching `.out` (25 pairs, 268 statements).
- `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 2 | — |

### Issues by severity

- **WRONG: 2**
  1. `equiv` unsound — float domain drops `-0` and all NaNs, so
     `x ≡ x+0` is "proved" equal (f16 exhaustive, f32/f64 SAT). `nanbits`
     cannot catch NaN-payload counterexamples. (FINDINGS §1)
  2. `abs` quiets sNaN on f32/f64 but preserves it on f16 — format-inconsistent
     NaN payload handling. (FINDINGS §2)
- **LIMIT: 2**
  3. Out-of-domain unary ops return unevaluated symbolic expressions on direct
     calls; `table` forces the correct concrete IEEE result. (FINDINGS §3)
  4. f32/f64 `range` is sampled (65536 points), limiting soundness of range
     claims. (FINDINGS §4)
- **CRASH / HANG / DETERMINISM: 0** in this area. All 25 goldens reproduced
  byte-identically on two runs.


## Takeaway
ucas's numeric float kernels are correctly rounded across the entire f16 space and densely sampled f32 space (no rounding, signed-zero, conversion, or transcendental errors found); the defects live in the *domain model* used by `domain`/`range`/`equiv` (which silently excludes `-0` and NaNs, yielding an unsound equivalence proof) and in f32/f64 `abs` quieting sNaN payloads that f16 `abs` preserves.

### Original takeaway (verbatim)

ucas's numeric float kernels are correctly rounded across the entire f16 space
and densely sampled f32 space (no rounding, signed-zero, conversion, or
transcendental errors found); the defects live in the *domain model* used by
`domain`/`range`/`equiv` (which silently excludes `-0` and NaNs, yielding an
unsound equivalence proof) and in f32/f64 `abs` quieting sNaN payloads that f16
`abs` preserves.

Confinement: all files written only under `tests/stress/areas/float/float_exhaustive/`.
