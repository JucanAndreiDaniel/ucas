# Stress findings — `bigint_extremes`

_Original heading: FINDINGS — `bigint_extremes`_

# FINDINGS — `bigint_extremes`

Area: arbitrary-precision integer limits. All runs used
`$ROOT/ucas` under `timeout 15` unless a longer bound is stated.
150+ distinct queries were tried; the deterministic, correct ones are kept as
goldens (`*.ucas`/`*.out`, `mcp_*.jsonl`/`*.out`). The issues below have
reproducer files but **no golden `.out`** so the suite stays runnable.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 2 | `bigint 10^1000000` (a 10⁶-digit integer) does not finish in 35 s |
| WRONG | 3 | `int` values at/above 2^63 in loops and sums fail with a bogus “complex or hypercomplex” e… |
| NLP | 1 | “continued fraction” is not understood and is silently misparsed as multiplication |
| LIMIT | 3 | integer literals > 2^64−1 are rejected even where bigint arithmetic is intended |

## Findings

### WRONG-1 — `int` values at/above 2^63 in loops and sums fail with a bogus “complex or hypercomplex” error
**Severity:** WRONG
**Why it matters:** _not recorded_
The `int` type is documented as the *ideal* (arbitrary-precision) integer type,
and `bigint` handles 2^1000+ exactly. But the moment a loop- or sum-carried
`int` value reaches 2^63, ucas aborts with a misleading error from the
hypercomplex module (`src/hyper.c` rejects `O_LOOP` with non-machine values).
This breaks Fibonacci/geometric loops at large indices.

**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'g(n: int in 0..200) = { a = 1; k = 0; while k < n { a = a * 2; k += 1 }; a }' -e 'g(62)' -e 'g(63)'
# also: timeout 15 ./ucas tests/stress/areas/math/bigint_extremes/bug_int_overflow.ucas
```

**Observed:** output:

```
4611686018427387904
<arg>:1:1: error: a loop or sum is not supported with complex or hypercomplex values
    g(63)
    ^
```

**Expected:** `g(63) = 9223372036854775808` (2^63), exactly as `bigint 2^63`
prints it. The same happens for the Fibonacci loop at `n=92` (where the
carried value `b = F(93) = 12200160415121876738` crosses 2^63) and for
`sum(i,0,63,2^i) = 2^64-1`. `g(62)=2^62` and `f(91)=F(91)` succeed, so the
cut-over is exactly the signed-64-bit boundary. The error text is simply
wrong (nothing is complex here) and the computation is refused even though
`int` is supposed to be arbitrary precision.

### WRONG-2 — `int` function evaluation with an argument ≥ 2^63 returns a symbolic expression, not a number
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'f(x: int) = x + 1' -e 'f(2^62)' -e 'f(2^63)'
# also: timeout 15 ./ucas tests/stress/areas/math/bigint_extremes/bug_int_symbolic.ucas
```

**Observed:** output:

```
4611686018427387905
_() = 2^63 + 1
  -> int
```

**Expected:** `f(2^63) = 9223372036854775809`. `f(2^62)` evaluates to a number;
`f(2^63)`, `f(2^64)`, `f(2^100)` just echo a symbolic `+ 1`. Even a decimal
literal `f(9223372036854775808)` yields `_() = int(9223372036854775808) + 1`.
Inconsistent with `int` = mathematical integer and with `bigint`, which
reduces the same arithmetic to a numeral.

### LIMIT-1 — integer literals > 2^64−1 are rejected even where bigint arithmetic is intended
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'f(x: int) = x + 1' -e 'f(100000000000000000000000000000000000000000)'
```

**Observed:** output:

```
<arg>:1:3: error: the integer literal 100000000000000000000000000000000000000000 is too large: the largest is 2^64 - 1 = 18446744073709551615 (a u64)
    f(100000000000000000000000000000000000000000)
      ^
```

`bigint 10^40` is accepted and computed exactly; the general expression
parser caps literals at u64. Worth noting because it blocks feeding very
large decimal constants into `int` functions.

### HANG-1 — `bigint 10^1000000` (a 10⁶-digit integer) does not finish in 35 s
**Severity:** HANG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
timeout 35 ./ucas -e 'bigint 10^1000000' > /tmp/million.out 2>&1; echo $?
# $? = 124, /tmp/million.out has 1000015 bytes, only the first line printed
```

**Observed:** after 35 s the process is still running (`timeout` kills it, exit
124); the single line `10^1000000 = 1000…000` (1,000,001 digits) is on disk
but the trailing `bits:` line never appears. `10^100000` (10⁵ digits) finishes
in <1 s with `bits: 33220`. So the 10⁶-digit target is a practical
hang under any reasonable bound (the digit-count and bits computation after
printing is the slow part).

### HANG-2 — `bigint factor` of a 61-digit semiprime times out (Pollard-Brent rho cap)
**Severity:** HANG
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'bigint factor 2000000000000000000000000000185000000000000000000000000004047' ; echo $?
# also: timeout 15 ./ucas tests/stress/areas/math/bigint_extremes/bug_hang_factor.ucas
```

**Observed:** no output within 15 s, exit 124 (`rho()` in `src/zint.c` caps at
2^21 iterations per `c`). The number is `nextprime(10^30) * nextprime(2·10^30)`;
`bigint isprime` on the same number returns 0 instantly.
**Expected:** a factor,
or an explicit “gave up” diagnostic rather than silence.

### LIMIT-2 — `rings` number-theory ops refuse n ≥ 2^64
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
MCP reproducer (`mcp_factor.jsonl` uses only in-range values):

**Reproducer:**
```sh
cd $ROOT
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"rings","arguments":{"op":"carmichael","args":{"n":"18446744073709551616"}}}}' \
| timeout 15 ./ucas --mcp | tail -1
```

**Observed:** `structuredContent.error`:

```json
{"code": "failed", "message": "lambda(n) for 1 <= n < 2^64", "pos": {"line": 1, "col": 12}}
```

`phi`, `carmichael`, `factorint`, `order_mod`, etc. only accept n < 2^64 even
though the `abstract_algebra.bigint`/`bigint_factor` tools handle arbitrary
size. Documenting the boundary; not a crash.

### NLP-1 — “continued fraction” is not understood and is silently misparsed as multiplication
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'continued fraction 355/113'
```

**Observed:** output:

```
_(continued: real, fraction: real) = 355(continued*fraction)/113
  -> real
```

No continued-fraction functionality exists in `bigint`; the English frontend
turns the phrase into a free-variable multiplication instead of reporting an
unknown command. (Closely related: `bigint 1/3` correctly errors with
“1/3 is not exact”, so no rational/continued-fraction path is reached.)

### LIMIT-3 — no built-in Fibonacci / modular-exponentiation functions in `bigint`; huge exponents hang
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`bigint powmod(...)`, `bigint modpow(...)`, `bigint fib(...)`,
`bigint fibonacci(...)` all return “unknown function” / “too many arguments”.
Modular exponentiation was therefore exercised as `bigint a^b % m` (works for
b up to ~10^5), and Fibonacci at large indices was computed *exactly* via the
binomial identity `F(n) = Σ_{k=0}^{⌊(n-1)/2⌋} C(n-1-k,k)` (golden
`11_fibonacci.ucas`, n = 10…1000, all values verified against Python).
A literal huge exponent such as `bigint 2^(2^20)` does not finish in 15 s.

### WRONG-3 — MCP `bigint_factor` structured `factors` drops the sign for negative n, yet the product check claims success
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (Code Mode / MCP `abstract_algebra`):

```js
await tools.ucas.abstract_algebra({op:"bigint_factor", args:{n:"-1000000007"}})
```

Equivalent copy-pasteable shell command (MCP wire):

```sh
cd $ROOT
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"abstract_algebra","arguments":{"op":"bigint_factor","args":{"n":"-1000000007"}}}}' \
| timeout 15 ./ucas --mcp | tail -1
```

**Observed:** `structuredContent`:

```json
{
  "ok": true,
  "result": {
    "value": "-1000000007",
    "factors": [{"prime": "1000000007", "exponent": 1}],
    "headline": "-1000000007 = -1000000007 (prime)"
  },
  "checks": [{"kind":"check","passed":true,
             "text":"the product is the number; each factor passes the primality test"}]
}
```

The product of the structured `factors` is **+1000000007**, not the
`"value": "-1000000007"`; the minus sign exists only in the human-readable
`headline`, not in the machine-readable certificate. A client that rebuilds
the number from `factors` and trusts `checks.passed:true` gets the wrong
number. Same for `-12` → `factors=[2^2, 3]` while the headline says
`-2^2 * 3`.
**Expected:** include a `-1` factor (or a `sign` field) so the
structured certificate is self-consistent.

## Checks that passed

### Notes on what went right (verified goldens)
- All 164 bigint statements in `01`–`12` were checked against a Python
  arbitrary-precision oracle: every value, every `bits:` field, every
  factorial/binomial digit count and all factor products matched.
- `isprime` on Mersenne primes (2^61−1, 2^89−1, 2^127−1) and on Carmichael
  numbers (561, 1729, 3215031751, 341550071728321, 3825123056546413051)
  was correct in every case; Miller-Rabin uses a fixed base set, so repeated
  runs were byte-identical (no nondeterminism).
- `bigint_factor` products and primality certificates verified for all golden
  factorizations; repeated runs were byte-identical (no nondeterminism).
- 10³-, 10⁴- and 10⁵-digit values produced correct decimal digit counts
  (e.g. 10^10000 → 10001 digits, 1000! → 2568 digits, 10000! → 35660 digits).
