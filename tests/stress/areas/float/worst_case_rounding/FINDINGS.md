# Stress findings — `worst_case_rounding`

_Original heading: worst_case_rounding — findings_

# worst_case_rounding — findings

All commands use the prebuilt `$ROOT/ucas` and were run under
`timeout`.  The oracle is `oracle.py`: an exact 200-bit mpmath image of the
function at the *exact* float input, rounded once to IEEE binary16/32/64 with
ties-to-even and subnormals.  Its rounding was validated against Python's
correct `mpf -> float` conversion on 4000 random values (0 mismatches), and the
key results below were re-checked at 1000 bits.  `gen.py` generated **406
adversarial cases** and compared all of them; `cases.json` / `gen_report.txt`
hold the full result table.  Result: 368 match, 33 confirmed numeric
mismatches, 5 unevaluated expressions.

uca's `scalar_float` (src/eval.c) calls the host libm `double` functions
directly for `exp/log/sqrt/sin/cos` and then applies `fround(w, r)` for f32/f16.
The mismatches below are exactly the two failure modes that creates: **libm not
correctly rounded at Table-Maker's-Dilemma inputs**, and **double rounding** on
the f64 -> f32/f16 narrowing.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 6 | published double-precision worst case for `exp` is 1 ulp high |
| LIMIT | 1 | float division whose result overflows stays unevaluated |

## Findings

### WRONG-1 — published double-precision worst case for `exp` is 1 ulp high
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'show asuint(exp(asfloat(u64(0xc0412d31a20fb38b))))\n' \
  | timeout 15 $ROOT/ucas
```

This is the published hardest-to-round case for `exp` (round-to-nearest, whole
domain): input `-0x1.12D31A20FB38Bp+5` (Lefèvre 2013).

**Observed:**
```
_() = 4383604147543638539
  -> u64
```
`= 0x3cd5b0bf3244820b`.

Oracle (stable 200/400/800/1000 bits): `0x3cd5b0bf3244820a`
(= 4383604147543638538).  The exact image is
`0x1.5B0BF3244820A...p-50`, only 1.5e-18 ulp below the midpoint, so the
correctly rounded result is the **lower** double.  ucas returns the upper one.
The published tail `01[58]0010` confirms the round bit is 0.
**Expected:** the
lower double; ucas is off by one ulp.

### WRONG-2 — published double-precision worst case for `log` is 1 ulp low
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'show asuint(log(asfloat(u64(0x6dbfd15daa6ce332))))\n' \
  | timeout 15 $ROOT/ucas
```

Input `0x1.FD15DAA6CE332p+732`, the published hardest-to-round case for `log`.

**Observed:**
```
_() = 4647645698816238377
  -> u64
```
`= 0x407fc12387d06329`.

Oracle (1000 bits): `0x407fc12387d0632a` (= 4647645698816238378).  Exact
`log x = 508.0711744442110955333...`, 2.1e-19 ulp above the midpoint, so the
correct result is `0x...2A`; ucas gives `0x...29`.  One ulp low.

### WRONG-3 — `sin` of a large argument is 1 ulp off (host libm)
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'show asuint(sin(asfloat(u64(0x4a77814ea6142e5b))))\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:**
```
_() = 4595533273553887150
  -> u64
```
`= 0x3fc69d2a03aadfae`.

Oracle: `0x3fc69d2a03aadfad` (= 4595533273553887149).  At 400/800/1200 bits the
true value is `0.176671268263587519171748945735644457277...`, which is
5.99e-20 *below* the midpoint `0.1766712682635875192316...`; the correct double
is `...ad`.  ucas/libm returns `...ae`.  This is a genuine libm argument-
reduction/rounding error that ucas inherits for large |x| (x here ~2^168).

### WRONG-4 — double rounding: `f32(exp(x))` differs from the correctly-rounded f32
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'show asuint(f32(exp(asfloat(u64(0x3fefbe8973eb2fcc)))))\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:** `_() = 1076663770` (`0x402c95da`).
Oracle (direct rounding of exact `exp(x)` to f32): `0x402c95db`
(= 1076663771).  ucas's result is exactly `round_f32(round_f64(exp(x)))`
(= its own `double` model in `cases.json`), i.e. the f64 intermediate landed on
the f32 midpoint and the second rounding chose the wrong neighbour.  This is
the classic double-rounding trap; the README's "every result rounds to nearest
even" is violated.  **24 such cases** were constructed for f64 -> f32 across
exp/log/sqrt/sin/cos/recip (category `05_f64_to_f32_dr` in `cases.json`), all
mismatching.

### WRONG-5 — double rounding: `f16(log(x))` differs from correctly-rounded f16
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'show asuint(f16(log(asfloat(u64(0x3ff5744b0651878d)))))\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:** `_() = 13490` (`0x34b2`).
Oracle: `0x34b1` (= 13489).  Again ucas's value equals the f64-then-f16 double
rounding.  **6 such cases** for f64 -> f16 (`06_f64_to_f16_dr`), covering log
and sqrt.

### WRONG-6 — `equiv` reports `equal:true` for float functions with a concrete counterexample
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`26_equiv_dr_claim.ucas` and `mcp_worst_rounding.jsonl` in this folder.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/float/worst_case_rounding
timeout 30 $ROOT/ucas 26_equiv_dr_claim.ucas
```

**Observed:** (`equiv` verdict plus two witnesses in the same file):
```
f16a and f16b are equal on the domain of f16a (sampled, not proved; no SAT proof: a float function)
...
_() = 15459    # f16(exp(x)),  x=0x3fb7bd4d2319c6f9  -> 0x3c63
_() = 15460    # f16(f32(exp(x)))                    -> 0x3c64
```
and for `x=0x3fbf2688349641d4`: 15493 (`0x3c85`) vs 15492 (`0x3c84`).

MCP (`mcp_worst_rounding.jsonl`, ids 4-6) returns
`"result":{"kind":"equiv","equal":true,"exhaustive":false,...,"method":"sampled"}`
and then shows the two differing values.  `equiv` therefore asserts equality
while returning two different bit patterns on concrete inputs in the very same
session.  It is labelled "sampled, not proved", but the unqualified
`equal:true` JSON field is a wrong answer that a caller could consume; the
witnesses are rare (~1 in 10^4) and random sampling misses them.

### LIMIT-1 — float division whose result overflows stays unevaluated
**Severity:** LIMIT
**Why it matters:** _not recorded_
`27_overflow_div.ucas` in this folder.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/float/worst_case_rounding
timeout 30 $ROOT/ucas 27_overflow_div.ucas
```

**Observed:**
```
> show asuint(f16(1)/asfloat(u16(0x0001)))
_() = asuint(1/5.9605e-08)
  -> u16
> show f16(1)/asfloat(u16(0x0001))
_() = 1/5.9605e-08
  -> f16
```
and the same for f32 (`1/1.40129846e-45`) and f64
(`1/4.9406564584124654e-324`).  `1 / smallest_subnormal` overflows to +inf in
every IEEE format, but ucas leaves the division as a symbolic expression and
never applies `fround` / `asuint`, so no bit pattern is produced.  5 of the
406 generated cases hit this (category `08_subnormal`).
**Expected:** the
infinity bit pattern (`0x7c00` / `0x7f800000` / `0x7ff0000000000000`), or a
clear overflow note — not an unevaluated expression.

## Checks that passed

### Non-findings / checked and correct
- 162 tie-to-even midpoint and neighbour casts to f16/f32, 49 subnormal/normal
  boundary inputs and all f16/f32 midpoint-hard cases for the six functions
  agreed with the oracle (368 matches total).  No wrong tie-to-even was found.
- `equiv` on the exact identities `exp(log x)=x`, `log(exp x)=x`,
  `sqrt(x^2)=x`, `sin^2+cos^2=1` correctly returns counterexamples by sampling.
- `x*y == f32(f64(x)*f64(y))` (README's proved identity) is safe: a product of
  two f32 significands fits in 53 bits, so no double rounding occurs there.
