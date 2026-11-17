# Stress findings — `integer_division_semantics`

_Original heading: FINDINGS — `integer_division_semantics`_

# FINDINGS — `integer_division_semantics`

Binary: `$ROOT/ucas`. All repros are copy-pasteable from this directory.
Independent oracles: `python3 verify.py`, `python3 magic_verify.py`, `python3 crash_probe.py`,
`python3 find_verify.py`.  Goldens were each run twice and diffed; all are deterministic.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | `find` on a 16-bit `%` by any non-power-of-two divisor never returns |
| WRONG | 2 | `rem P, Q` and `quo P, Q` on integer constants return the rational quotient `P/Q` |
| NLP | 2 | "quotient" and "remainder" of a negative number are mutually inconsistent |
| LIMIT | 3 | integer range bounds above `2^63 - 1` are rejected, even for `u64` |

## Findings

### HANG-1 — `find` on a 16-bit `%` by any non-power-of-two divisor never returns
**Severity:** HANG
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'f(x: u16) = x %% 7\nfind f 1\n' | timeout 30 $ROOT/ucas
```

**Observed:** exit code `124` after 30 s (also after 60 s, with stdout sent to
`/dev/null`), with stable partial output (3,820 bytes) that ends inside the
lookup-table candidate:

```
find f: 1024 points (sampled; matches verified on the whole domain), computing in u16, costs from gt1030
  not applied (it would cost 10): the remainder x % 7 as a multiply and a shift in u32
      needs x <= 57343 (it is in [0, 65535]: its range)
...
  cost 6.875 [0, 1, 2, 3, 4, 5, 6, 0, 1, ...  (196456 more characters)
           65536 entries of u16 (131072 bytes of constant data), one for each point of x in 0..65535; ...
           priced as gt1030's load, a cache-resident access: the table has to stay in cache for that
           checked on every point of the domain
```

MCP shows the same hang: `analyze {op:"find", args:{f:{body:"x % 3",params:[x:u16]},n:1,timeout_s:5}}`
returns `error (timeout): timed out after 5 s; the state is unchanged`.

**Boundary mapped** (each run under `timeout 8`; `rc=124` = hang):

| type | `% 2,4,8,16` | `% 3,5,7,10,11` | `/ 3,5,7,10,11` |
|---|---|---|---|
| u8 / i8 | rc=0 | rc=0 | rc=0 |
| **u16 / i16** | rc=0 | **rc=124** | rc=0 |
| u32 / i32 | rc=0 | rc=0 | rc=0 |
| u64 / i64 | rc=0 | rc=0 | rc=0 |

**Why it matters:** it is a bug** — `find` terminates for the identical search on 8-, 32- and
64-bit types and on 16-bit *division*; only 16-bit remainder with an inexact
divisor wedges.  This is a HANG, so it is documented here rather than added as
a golden.  (The partial output is stable, but it is still a non-terminating
command.)

### WRONG-1 — `rem P, Q` and `quo P, Q` on integer constants return the rational quotient `P/Q`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/integer_division_semantics
cat 07_rem_quo_constants.out   # golden, produced by: ucas 07_rem_quo_constants.ucas
# or directly:
printf 'rem 7, 3\nrem -7, 3\nquo 7, 3\nquo -7, 3\n' | $ROOT/ucas
```

**Observed:**

```
rem 7, 3
  = 7/3
rem -7, 3
  = -7/3
quo 7, 3
  = 7/3
quo -7, 3
  = -7/3
```

More: `rem 8, 4 → 2`, `rem 6, 3 → 2`, `rem 9, 2 → 9/2`, `rem 1, 2 → 1/2`,
`rem -8, 3 → -8/3`, `rem 8, -3 → -8/3`.  But `rem x, 3 → 0` and
`quo x, 3 → x/3` (correct polynomial behaviour).

**Why it matters:** it is a bug** — for integer operands `rem -7, 3` should be `-1` (C) or `2`
(Euclidean), and `quo 7, 3` should be `2`; neither is `7/3`.  Even under the
polynomial reading of these commands (degree-0 polynomials), the remainder of
two nonzero constants must be `0`, as `rem x, 3` correctly returns — so `rem`
and `quo` behave identically and wrongly whenever both arguments are constants.
Captured deterministically in golden `07_rem_quo_constants.{ucas,out}`.

### WRONG-2 — `range` of `int x / int y` reports a sampled max that excludes reachable values
**Severity:** WRONG
**Reproducer:**

```sh
printf 'a(x: int, y: int) = x / y\nrange a\n' | $ROOT/ucas
printf 'a3(x: int in 4611686018427387904..4611686018427387904, y: int in 1..1) = x/y\ntable a3\n' | $ROOT/ucas
```

**Observed:**

```
range of a -> int:
  -9223372036854775807..27104
  fits in i64
  undefined at 1 points
  sampled 65536 points (domain has 2^64 or more points); not exhaustive

  x=4611686018427387904, y=1  ->  4611686018427387904
```

MCP `range` confirms `{"max":{"value":27104,...},"exhaustive":false}` with no
sound-bound field.  By contrast the same query on `i32` includes
`"sound_bound":[-2147483648,2147483647]`.

**Why it matters:** it is a bug** — the point `x = 2^62, y = 1` is in `a`'s domain and gives
`2^62`, hugely above the reported maximum `27104`.  The `min`/`max` fields are
presented as the function's range without a sound bound, so a consumer reading
the range is misled.
**Expected:** either a sound `i64` bound like the `i32` case,
or the full `int` bound.

### NLP-1 — "quotient" and "remainder" of a negative number are mutually inconsistent
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (MCP Code Mode `tools.ucas.english`)

```
q1 = "What is the quotient of -7 divided by 3?"
q2 = "What is the remainder of -7 divided by 3?"
```

**Observed:**

```
q1 -> understood=true, statements=["floor(-7/3)"]
q2 -> understood=true, statements=["-7 % 3"]
```

`show floor(-7/3) = -3` and `show -7 % 3 = -1`, so `-3*3 + (-1) = -10 != -7`.
For positive operands it is consistent; for negatives the English frontend
pairs a Euclidean (floor) quotient with a C-style (truncating) remainder.

**Why it matters:** it is a bug** — a user asking both questions gets a quotient/remainder
pair that does not reconstruct the dividend; the two phrases should use one
division convention (ucas's own truncating `/` and `%`).

### NLP-2 — English division requests misparse / silently default
**Severity:** NLP
**Expected:** _not recorded_
**Reproducers and observed output**

**Observed:**
**Reproducer:**
```sh
"Divide x by 3 for an unsigned byte x, cheaper"
  -> error (parse_error): expected a variable name
     <english>:1:22: error: expected a variable name
         divide x by 3 for an unsigned byte x, cheaper
                              ^
"Is x/3 cheaper as a multiply?"
  -> error (not_understood): I didn't follow "cheaper as a multiply"
"What is INT_MIN divided by -1?"
  -> understood=true, statements=["it(INT_MIN) = INT_MIN/(-1)"]
     show result: definition "it(INT_MIN: real) = INT_MIN/-1", type real
"what is 100 / 7 in integers"
  -> error (not_understood): I didn't follow "in integers"
```

**Why it matters:** it is a bug** — a natural request for an integer-division rewrite fails;
`INT_MIN` is silently treated as an undefined `real` variable rather than the
signed-integer minimum, producing a `real` answer with no domain/UB information.
Related: `divide -7 by 3` is understood but yields only `{kind:"divide",p,q}`
with no value.

### LIMIT-1 — integer range bounds above `2^63 - 1` are rejected, even for `u64`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'f(x: u64 in 0..18446744073709551615) = x / 3\nrange f\n' | $ROOT/ucas
```

**Observed:**

```
error: unsupported: x's range bound 18446744073709551615 is too large: an
integer range takes at most 2^63 - 1 = 9223372036854775807 (without a range a
u64 takes every value)
```

**Why it matters:** it is a limitation** — a `u64` whose natural domain reaches `2^64-1`
cannot be restricted to an interval ending near its own maximum; only an
unbounded `u64` is accepted.  Equivalent `u64` queries with range
`0..9223372036854775807` work.  12 of the 72 sampled-constant cases hit this.

### LIMIT-2 — MCP `algebra` `rem`/`quo` return no computed result
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (MCP Code Mode)

```
tools.ucas.algebra({op:"rem", args:{p:"7",q:"3"}})
tools.ucas.algebra({op:"quo", args:{p:"7",q:"3"}})
```

**Observed:** `{"kind":"rem","p":"7","q":"3"}` and `{"kind":"quo","p":"7","q":"3"}`
respectively: the operands are echoed, no value, proof or error.

**Why it matters:** it is a limitation** — the CLI at least prints a (wrong) value; the MCP
entry point silently returns an incomplete object, which a client could mistake
for a successful computation.

### LIMIT-3 — `domain` calls a division "total" while reporting C UB
**Severity:** LIMIT
_Original classification: `LIMIT (minor`._
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'm(x: i8) = x / -1\ndomain m\n' | $ROOT/ucas
```

**Observed:**

```
domain of m:
  x: i8, -128..127
  no conditions: total on its parameter types
  C undefined behaviour at 1 points, e.g. x=-128
```

**Why it matters:** it is a limitation** — `INT_MIN / -1` is C undefined behaviour, so the
function is not total over its parameter type; the two lines read as
contradictory (the UB is separately flagged in `wrap` as an end-to-end
mismatch at `x=-128`).  Documenting rather than asserting a bug because ucas
keeps "mathematical definedness" and "C UB" as separate concepts.

## Checks that passed

### Non-findings (verified correct)
- 76 constant `/` and `%` cases on `u8`/`i8` (incl. out-of-range constants that
  wrap, e.g. `i8 x/200` = `x/-56`) match a Python two's-complement truncating
  oracle on every point.
- 709 `magic D <type>` results across `u8..u64/i8..i64` and 80+ divisors were
  independently checked: `m`, shift `s`, and the multiply/shift formula are
  correct (exhaustive for 8/16-bit, dense 20k-point samples for 32/64-bit).
- All integer `find` rewrite candidates returned for `/` and `%` on 8/16/32-bit
  functions passed `equiv` against the original (float-pipe candidates need the
  MCP `ftz` argument, which is an API requirement, not a division bug).
- `div/mod` identity checks: `(x/d)*d + x%d == x`, `x%8 == x&7` (unsigned),
  `x/-1 == -x`, `x/-3 == -(x/3)`, and the false `x/2 == x>>1`,
  `(-x)/3 == -(x/3)`, Euclidean-vs-C modulo — all agreed with the oracle.
- 74 adversarial snippets (huge divisors, `INT_MIN/-1`, divisor wrapping to
  zero, nested division, where-clauses, mixed 64-bit signs) produced no crashes,
  empty outputs, or nondeterminism; each was run twice and output-hashed.
