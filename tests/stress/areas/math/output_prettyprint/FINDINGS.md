# Stress findings — `output_prettyprint`

_Original heading: FINDINGS — `output_prettyprint`_

# FINDINGS — `output_prettyprint`

Focus: pretty-printing of values (`show`, `parse`, `table`, `simplify`, `range`,
`equiv` witnesses) and re-parsing of the printed representation into the same
value. 170 CLI statements across 15 `.ucas` files plus 17 MCP calls. Every
candidate was run with `timeout 15` (goldens with `timeout 30`); every golden
was produced twice and `diff`-ed — all were byte-identical. No crashes, hangs,
signals or nondeterminism were observed (see "Negative results" at the end).

All reproducers below are copy-pasteable with
`cd $ROOT/tests/stress/areas/math/output_prettyprint` and the absolute
binary `$ROOT/ucas`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | f64 values printed with 17 digits do NOT round-trip: re-parsing truncates to 10 digits, ma… |
| LIMIT | 2 | `real` is advertised as "math" but overflows like f64; numeric literals cap at ~77 digits … |

## Findings

### WRONG-1 — f64 values printed with 17 digits do NOT round-trip: re-parsing truncates to 10 digits, max-finite becomes `inf` — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
`show` prints IEEE values with a round-trip-safe number of digits (f16: 5,
f32: 9, f64: 17), but a *bare decimal literal* is typed `real` and `show`/
`parse` render it with only **10** significant digits. A f64 printed value fed
back therefore changes value, and for the largest finite f64 it becomes `inf`.

**Reproducer:**
Reproducer (golden `07_roundtrip_f64.ucas`, `mcp_prettyprint.jsonl` ids 1–3):

```sh
$ROOT/ucas <<'EOF'
f64_bits(z: f64) = asuint(z)
show asfloat(u64(0x7fefffffffffffff))
show 1.7976931348623157e+308
parse 1.7976931348623157e+308
show 1.797693135e+308
show f64_bits(1.7976931348623157e+308)
show f64_bits(1.797693135e+308)
show 0.33333333333333331
show 0.3333333333
show f64_bits(0.33333333333333331)
show f64_bits(0.3333333333)
EOF
```

**Observed:**

```
> show asfloat(u64(0x7fefffffffffffff))
_() = 1.7976931348623157e+308
  -> f64
> show 1.7976931348623157e+308
_() = 1.797693135e+308
  -> real
> parse 1.7976931348623157e+308
1.797693135e+308
> show 1.797693135e+308
_() = inf
  -> real
> show f64_bits(1.7976931348623157e+308)
_() = 9218868437227405311        # 0x7FEFFFFFFFFFFFFF (max finite)
  -> u64
> show f64_bits(1.797693135e+308)
_() = 9218868437227405312        # 0x7FF0000000000000 (+inf)
  -> u64
> show 0.33333333333333331        # f64 1/3
_() = 0.3333333333
  -> real
> show f64_bits(0.33333333333333331)
_() = 4599676419421066581        # 0x3FD5555555555555
  -> u64
> show f64_bits(0.3333333333)
_() = 4599676419420466101        # 0x3FD55555555553A5 (different)
  -> u64
```

**Why it matters:** a bug: the printed representation of a value must re-parse to the *same
value. `show asfloat(u64(0x7fefffffffffffff))` emits `1.7976931348623157e+308`,
but feeding that string back through `show` or `parse` produces
`1.797693135e+308`, whose f64 bit pattern is `+inf` (0x7FF0000000000000) rather
than the original max-finite `0x7FEFFFFFFFFFFFFF`. 1/3 similarly changes bits.
The round-trip-safe 17-digit output is destroyed by the 10-digit `real` reader.
The same truncation appears over MCP (`structuredContent.result.body` is
`1.797693135e+308` for `show`/`parse` of the 17-digit literal, and `show` of
`1.797693135e+308` returns `inf`).

### WRONG-2 — negative zero loses its sign on round-trip — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `08_signed_zero_nan.ucas`, MCP ids 4–5):

```sh
$ROOT/ucas <<'EOF'
show asfloat(u64(0x8000000000000000))
show -0.0
show -0
parse -0
show asfloat(u32(0x80000000))
show asfloat(u16(0x8000))
EOF
```

**Observed:**

```
> show asfloat(u64(0x8000000000000000))
_() = -0
  -> f64
> show -0.0
_() = -0
  -> real
> show -0
_() = 0
  -> int
> parse -0
0
> show asfloat(u32(0x80000000))
_() = -0
  -> f32
> show asfloat(u16(0x8000))
_() = -0
  -> f16
```

**Why it matters:** a bug: `-0` is printed for f16/f32/f64 negative zero, but re-reading that
printed token gives integer/real `0` (positive zero). `f64_bits(-0)` returns 0,
not `0x8000000000000000`. The sign bit is irretrievably lost, so a
print→parse→print cycle changes the value. Affects all three IEEE widths.

### WRONG-3 — negative NaN re-parses as a free variable; NaN payloads are dropped in printing — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `08_signed_zero_nan.ucas` / `05_f32_patterns.ucas`, MCP ids 6–8):

```sh
$ROOT/ucas <<'EOF'
show asfloat(u32(0xffc00000))
show -nan
parse -nan
show (-nan)
show asfloat(u32(0x7fc00001))
show asfloat(u32(0xffffffff))
EOF
```

**Observed:**

```
> show asfloat(u32(0xffc00000))
_() = -nan
  -> f32
> show -nan
_(nan: real) = -nan
  -> real
> parse -nan
(-nan)
> show (-nan)
_(nan: real) = -nan
  -> real
> show asfloat(u32(0x7fc00001))
_() = nan            # payload 0x000001 lost
  -> f32
> show asfloat(u32(0xffffffff))
_() = -nan           # payload 0x7fffff and sign collapsed
  -> f32
```

**Why it matters:** a bug: a printed `-nan` is not a self-contained value — re-parsing it
introduces an implicit free variable `nan` (`_(nan: real) = -nan`), i.e. a
symbolic expression rather than a NaN. The `nanbits` mode elsewhere in ucas
compares NaN sign and payload, but printing collapses all NaNs to `nan`/`-nan`,
losing the payload, so a NaN bit pattern cannot round-trip through the printer.

### WRONG-4 — `simplify` claims "exact: both sides have the same normal form" while printing a truncated decimal on the left — `WRONG` (misleading exactness claim)
**Severity:** WRONG
_Original classification: `WRONG (misleading exactness claim`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (golden `11_exact_rational.ucas`):

```sh
$ROOT/ucas <<'EOF'
simplify 22/7
simplify 3.142857143
simplify 1/3 + 1/7
simplify 0.4761904762
EOF
```

**Observed:**

```
> simplify 22/7
simplify 3.142857143
  = 22/7
  check: exact (both sides have the same normal form)
> simplify 3.142857143
simplify 3.142857143
  = 3.142857143
  check: exact (both sides have the same normal form)
> simplify 1/3 + 1/7
simplify 0.4761904762
  = 10/21
  check: exact (both sides have the same normal form)
> simplify 0.4761904762
simplify 0.4761904762
  = 0.4761904762
  check: exact (both sides have the same normal form)
```

**Why it matters:** a bug: `simplify 22/7` prints the left side as `3.142857143` and the right
side as exact `22/7`, asserting "exact". But `simplify 3.142857143` is itself
exact-equal to `3.142857143`, not `22/7`. The two printed decimals
`3.142857143` and `0.4761904762` are 10-digit truncations, not the exact
rationals they are printed next to. A user who copies the printed LHS obtains a
different value than the RHS the tool says it equals. The exact rational form
(`10/21`, `22/7`) also does not survive `show`/`parse`: both print
`0.4761904762` / `3.142857143`.

### LIMIT-1 — `real` is advertised as "math" but overflows like f64; numeric literals cap at ~77 digits — `LIMIT`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (goldens `02_reals.out`, `03_exponent_fmt.out`, `14_digitlimit.ucas`):

```sh
$ROOT/ucas <<'EOF'
show 1e999999
show 1e-999999
show 1e309
show 1e-325
show 1e9223372036854775807
EOF
python3 -c "print('show 0.'+'1'*78)" | $ROOT/ucas
python3 -c "print('show 0.'+'1'*77)" | $ROOT/ucas
```

**Observed:**

```
_() = inf     -> real        (1e999999, 1e309, 1e9223372036854775807)
_() = 0       -> real        (1e-999999, 1e-325)
<stdin>:1:6: error: number too long
    show 0.1111...(78 ones)
         ^
_() = 0.1111111111            (77 ones accepted)
  -> real
```

**Why it matters:** a limitation: help advertises `real (math)`, i.e. exact mathematical
reals, but values beyond f64 range print `inf`/`0`, and a decimal literal with
78+ fractional digits is rejected with a bare `number too long` error (no
threshold, no guidance). Note this is asymmetric with the `int` type, where
`show 2^100` is kept symbolic. A >10-digit literal is silently rounded to 10
digits when displayed (`show 0.12345678901234567` → `0.123456789`), so even
accepted input loses precision on output.

### LIMIT-2 — complex / symbolic values are printed unevaluated and lose their type on re-parse — `LIMIT`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (goldens `09_complex.ucas`, `07_roundtrip_f64.ucas`):

```sh
$ROOT/ucas <<'EOF'
show 1+2i
show (1+2i)*(3+4i)
show i^2
show conj(1+2i)
parse 2i + 1
show -0
EOF
```

**Observed:**

```
> show 1+2i
_() = 2i + 1
  -> complex
> show (1+2i)*(3+4i)
_() = (2i + 1)*(4i + 3)      # not folded to -5+10i
  -> complex
> show i^2
_() = i^2                    # not folded to -1
  -> complex
> parse 2i + 1
((2 * i) + 1)
> show -0
_() = 0
  -> int                     # f64/real -0 became int 0
```

**Why it matters:** a limitation: `show` leaves many arithmetic forms symbolic rather than
canonicalising them (e.g. `i^2`, complex products, `2^100`, `1e300*1e300`).
Feeding the printed form back changes the textual representation
(`2i + 1` → `((2 * i) + 1)`) and can change the inferred type (`-0` → int).
For a "print → parse → same value" contract the canonical value/type is not
stable across all value kinds. (No wrong numeric value was found here: the
expressions denote the same mathematical value, only the representation/type
differs.)

## Checks that passed

### Negative results / things that were checked and found OK
- f16 (5 digits) and f32 (9 digits) printed values re-parse to the **same bit
  pattern** when fed through a typed function (`asuint`): all special patterns
  in `04_f16_patterns` / `05_f32_patterns` round-trip for finite values; the
  only f16/f32 failures are the signed-zero and NaN issues in F2/F3.
- `1e2147483647`, `1e-2147483648`, `1e9223372036854775807`, 10 000-digit
  integer/float literals, 1 000-digit exponents, a 200-level power tower,
  2 000-term sums, 500 nested parens, and 200 repeated `parse` calls all return
  promptly (<0.02 s) with exit 0 — no crash, hang, or OOM.
- `table` sampling (e.g. `table f(x: int) = x^2`) is deterministic across
  separate invocations (identical random values each run).
- `equiv` counterexample floats (`x=-1.93719168e-23`) re-parse to the same f32
  bit pattern (2579192459); integer witnesses round-trip too.
- All 15 CLI goldens and the MCP golden were byte-identical across two runs
  (`diff` clean) — no nondeterminism.
