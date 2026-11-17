# Stress findings — `simplify_idempotence`

_Original heading: FINDINGS — simplify_idempotence_

# FINDINGS — simplify_idempotence

Area: idempotence and canonicity of `simplify` / `expand` / `factor`, via CLI and the
`algebra` / `analyze` MCP tools (wire protocol `ucas --mcp`).
Binary: `$ROOT/ucas`. Every run was bounded with `timeout`.

Main corpus: **217** expressions (58 polynomials, 32 rational, 23 trig, 23 log/exp,
22 abs/min/max, 15 piecewise, 24 complex, 20 machine-type) plus ~160 targeted
probes. Checks: `simplify(simplify(e)) == simplify(e)`, `expand(expand(e)) == expand(e)`,
`factor(factor(e)) == factor(e)`, `simplify(expand(e)) == simplify(factor(e))` for
polynomials, rewrite-order independence, cancellation conditions, determinism.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | `simplify`, `expand`, and `factor` are not idempotent on rational differences |
| LIMIT | 2 | complex powers of `I` are not reduced; canonicity gap for complex expressions |

## Findings

### WRONG-1 — `simplify`, `expand`, and `factor` are not idempotent on rational differences
**Severity:** WRONG
_Original classification: `WRONG (a claimed "exact / same normal form" result is not a fixed point`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):
**Observed:**
```sh
cd $ROOT/tests/stress/areas/math/simplify_idempotence
$ROOT/ucas 01_rat_nonidem.ucas
```

**Exact observed output (abridged to the `=` lines; full text in `01_rat_nonidem.out`):**
```
> simplify 1/x - 1/y
  = -(x - y)/(x*y)
  check: exact (both sides have the same normal form)
> simplify -(x - y)/(x*y)
  = (y - x)/(y*x)
  check: exact (both sides have the same normal form)
> simplify (y - x)/(y*x)
  = (y - x)/(y*x)
  check: exact (both sides have the same normal form)
> simplify (-(x - y)/(x*y)) - ((y - x)/(y*x))
  = 0
  holds where y != 0, x != 0 (cancelled there)
```

So `s1 = simplify(e) = -(x - y)/(x*y)`, but `simplify(s1) = (y - x)/(y*x) != s1`.
The form stabilizes only on the **third** application. Both forms are equal
(their difference simplifies to `0`), and ucas labels each step
`check: exact (both sides have the same normal form)` — yet the "normal form"
changes, i.e. it is not canonical/idempotent.

**Same bug through the `algebra` MCP tool** (`mcp_algebra_nonidem.jsonl`):
```
cd $ROOT/tests/stress/areas/math/simplify_idempotence
$ROOT/ucas --mcp < mcp_algebra_nonidem.jsonl
```
Structured results (`id: input -> result`):
```
1  simplify  1/x - 1/y            -> -(x - y)/(x*y)
2  simplify  (y - x)/(x*y)        -> (y - x)/(y*x)
3  simplify  (y - x)/(y*x)        -> (y - x)/(y*x)
4  expand    1/x - 1/y            -> -(x - y)/(x*y)
5  factor    1/x - 1/y            -> -(x - y)/(x*y)
6  simplify  1/x + 1/y            -> (x + y)/(x*y)     <- idempotent control
7  simplify  (x + y)/(x*y)        -> (x + y)/(x*y)
```

**Root pattern:** whenever the combined rational's numerator has a **negative
leading coefficient**, the first pass emits a leading `-(...)/(...)`; the second
pass pushes the sign into the numerator (`y - x`) and reverses the denominator
factor order (`y*x`). This is systematic, not a one-off:

- 24 / 52 rational-sum/difference variants were non-idempotent
  (`02_nonidem_variants.ucas`, `03_expand_factor_nonidem.ucas`), including
  `2/x - 3/y`, `1/a - 1/b`, `1/x - 1/y - 1/z`, `x*(1/x - 1/y)`,
  `1/(x*y) - 1/(y*z)`.
- All-positive sums such as `1/x + 1/y` **are** idempotent, confirming the
  negative-sign trigger.

**Why it matters:** a simplifier that reports "same normal form" must be
idempotent; callers that normalize once and cache the result get a different
answer than callers that normalize twice. It breaks the contract that
`simplify` produces *the* normal form. No crash or hang — wrong canonical result.

Durable reproducers with goldens: `01_rat_nonidem.*`, `02_nonidem_variants.*`,
`03_expand_factor_nonidem.*`, `mcp_algebra_nonidem.*`. All were run twice and
were byte-identical, so the goldens are safe.

### LIMIT-1 — complex powers of `I` are not reduced; canonicity gap for complex expressions
**Severity:** LIMIT
_Original classification: `LIMIT (mathematically equal expressions get different "normal forms"`._
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
printf 'simplify I**2\nsimplify I**2 + 1\nsimplify -1\nsimplify I**4\n' | $ROOT/ucas
```

**Exact observed output:**
```
simplify I^2
  = I^2
simplify I^2 + 1
  = I^2 + 1
simplify -1
  = -1
simplify I^4
  = I^4
```

**Why it matters:** `I^2 = -1` and `I^4 = 1`, so `I**2 + 1` is mathematically `0`,
yet `simplify` returns `I^2 + 1` and still prints
`check: exact (both sides have the same normal form)`. Two mathematically equal
complex expressions (`I**2 + 1` and `0`) therefore have different normal forms,
breaking canonicity for the complex domain. No crash; a completeness/canonicity
limitation of the normalizer.

### LIMIT-2 — `simplify` on machine-typed functions: bitwise ops rejected with a misleading message
**Severity:** LIMIT
_Original classification: `LIMIT (unsupported operation + contradictory diagnostic`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/math/simplify_idempotence
$ROOT/ucas 06_machine_types.ucas
```

**Exact observed output (relevant tail):**
```
> simplify f8
  ucas: simplify f8
<english>:1:10: error: shift needs integer operands
    simplify f8
             ^
> simplify f9
  ucas: simplify f9
<english>:1:10: error: '&' needs integer operands (declare the parameter as int or uN)
    simplify f9
             ^
```

Here `f8(x: u8) = x << 1` and `f9(x: u8) = x & 255`. The parameter **is** an
integer type (`u8`), so "needs integer operands" / "declare the parameter as int
or uN" is contradictory — `u8` is `uN`. The same rejection occurs for `<<`, `>>`,
`~`, `&` on `int, u4, u8, i8, u16, i32`, while `|` and `xor` are accepted. This is
an inconsistency in which bitwise operators the symbolic simplifier supports,
with a misleading error routed through the `<english>` frontend. (Golden
`06_machine_types.*` also shows the clean cases: `x+1-1 -> x`, `~(~x) -> x`,
`x xor x -> 0`, `x|0 -> x`, `x+(-x) -> 0`.)

Related minor note: `simplify` of a `u8` function body `x + 255 + 1` returns
`x + 256` rather than folding the wrap to `x`; the two are equal on `u8`, so this
is only a missed simplification, not a wrong value.

Durable reproducer with golden: `06_machine_types.*` (deterministic, verified twice).

## Checks that passed

### Notes — areas checked and found clean
- **Cancellation conditions:** all 43 rational/log cases examined
  (`05_cancel_conditions.ucas`, plus `cancel_hunt*.py`) reported the correct
  excluded set — e.g. `(x**2-1)/(x-1) -> x+1` under `x-1 != 0`,
  `(x**2-1)/((x-1)**2) -> (x+1)/(x-1)` with **no** condition (correct, both
  undefined at `x=1`), `((x+1)/(x-1))*((x-1)/(x+1)) -> 1` under both inequalities.
  No wrong/too-strong/too-weak condition found.
- **Canonicity `simplify(expand(e)) == simplify(factor(e))`:** held for all 205
  expressions where both `expand` and `factor` succeeded (0 differences).
- **Rewrite-order independence:** every sequence that included a parseable first
  op and ended in `simplify` produced the same final form. `apart F` is simply
  inapplicable to most expressions (parse error) — a harness limitation, not a
  normal-form divergence.
- **Crashes / hangs / nondeterminism:** none. All 217 corpus expressions and all
  MCP calls returned promptly; all 6 CLI goldens and the MCP golden were
  byte-identical across two runs.
