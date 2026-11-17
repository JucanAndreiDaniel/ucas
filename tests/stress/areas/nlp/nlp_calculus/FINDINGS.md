# Stress findings — `nlp_calculus`

_Original heading: Stress findings — `nlp_calculus` (English calculus / transforms / recurrences)_

# Stress findings — `nlp_calculus` (English calculus / transforms / recurrences)

All runs used `$ROOT/ucas`, bounded by `timeout`, from
`$ROOT`. ~200 English queries were exercised (see SUMMARY.md).
No crashes, hangs, or nondeterministic goldens were found. The real damage is
**silent misparses and wrong answers in the English frontend**.

Reproducer convention below: replace `QUERY` / `JSONL_LINE` as indicated.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | 1 — English silently swaps reversed definite-integral bounds (sign flips) |
| NLP | 5 | 1 — ODE with trailing `, solve from ... in N steps` silently produces NO output |
| LIMIT | 2 | 1 — Derivative / Taylor orders hard-capped at 12 |

## Findings

### WRONG-1 — 1 — English silently swaps reversed definite-integral bounds (sign flips)
**Severity:** WRONG
**Why it matters:** _not recorded_
to ascending order (`note: read the interval as [0, pi]`). That is fine for a
`range` interval but wrong for a *definite integral*: `∫_pi^0 x dx = -pi^2/2`,
yet ucas returns `+pi^2/2`. The raw `calculus integrate` tool with
`from=pi,to=0` returns the correct `-4.9348`, so the defect is in the English
bound parser, not the integrator.

**Reproducer:**
Repro (CLI):
```sh
cd $ROOT && printf '%s\n' 'the integral of x from pi to 0' > /tmp/r.ucas && timeout 15 ./ucas /tmp/r.ucas
```
**Observed:**
```
> the integral of x from pi to 0
  note: read the interval as [0, pi]
  ucas: it(x) = x
  ucas: integrate it from 0 to pi
∫ x dx
  = x^2/2 + C
  ...
  from 0 to 3.14159: F(3.14159) - F(0) = 4.93480220054468
  numeric (adaptive Gauss-Kronrod 7-15, 15 evaluations): 4.93480220054468, estimated error 5.4e-14
```
**Expected:** `F(0) - F(pi) = -4.93480220054468` (negative). Same bug for
`the integral of x^2 from 1 to -1` → returns `+2/3`, expected `-2/3`.

**Reproducer:**
Repro (MCP `english`, same wrong output) — one JSON-RPC line:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"english","arguments":{"text":"the integral of x from pi to 0","files":"none"}}}
```
Control (MCP `calculus`, correct):
```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"calculus","arguments":{"op":"integrate","args":{"f":"x","var":"x","from":"pi","to":"0","files":"none"}}}}
```
```
  from 3.14159 to 0: F(0) - F(3.14159) = -4.93480220054468
```

### WRONG-2 — 2 — Numeric limit check prints a false `DISAGREES` for `log(x) -> -inf`
**Severity:** WRONG
**Why it matters:** _not recorded_
verdict says the values "do not settle" and `DISAGREES`. `1/x -> inf` is
correctly reported as "grow without bound"; the logarithmic divergence is not
recognized, so the answer is flagged as inconsistent with itself.

**Reproducer:**
```sh
cd $ROOT && printf '%s\n' 'the limit of ln x as x approaches 0 from the right' > /tmp/r.ucas && timeout 15 ./ucas /tmp/r.ucas
```
**Observed:**
```
> the limit of ln x as x approaches 0 from the right
  ucas: it(x) = log(x)
  ucas: limit it x -> 0 from right
limit of it as x -> 0+ (from the right):
  = -inf
  numeric from the right (a + h, h = 0.1*2^-k, k = 0..21): -2.302585093, -5.075173815, -7.847762537, -10.62035126, -13.39293998, -16.85867588
    the values do not settle (the last ones lie in [-16.8587, -12.0066]): DISAGREES
```
**Expected:** values grow without bound (−), verdict `agrees`. Also reproduces
through MCP `english` and MCP `calculus op=limit`.

### WRONG-3 — 3 — CLI "closed form of fibonacci" silently misparses a named sequence into a nonsense answer
**Severity:** WRONG
_Original classification: `WRONG / NLP`._
**Why it matters:** _not recorded_
`fibonacci` ("read as a variable"), builds `it(fibonacci) = fibonacci`, runs
`closed it`, and answers "it has no loops" — a meaningless result. The named
sequence *is* understood elsewhere (`the generating function of fibonacci`
returns the Binet closed form). The MCP `english` tool correctly refuses with
an ambiguity error; only the CLI silently defaults and returns the bogus answer.

**Reproducer:**
```sh
cd $ROOT && printf '%s\n' 'the closed form of fibonacci' > /tmp/r.ucas && timeout 15 ./ucas /tmp/r.ucas
```
**Observed:**
```
> the closed form of fibonacci
  note: I don't know the word "fibonacci": read as a variable, not a mistake (stop here) (rephrase it, or name variables with one or two letters)
  ucas: it(fibonacci) = fibonacci
  ucas: closed it
it has no loops
```
**Expected:** the Binet closed form (as `genfunc fibonacci` prints), or a refusal.

### NLP-1 — 1 — ODE with trailing `, solve from ... in N steps` silently produces NO output
**Severity:** NLP
_Original classification: `NLP (silent no-op`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
When `solve from ...` follows the ODE + initial condition instead of
leading the sentence, the translator emits no `ucas:` statements, no result,
and no error — the line is silently dropped. Moving `solve` to the front makes
it work.

**Reproducer:**
```sh
cd $ROOT && printf '%s\n' "y' = -2y + 1, y(0)=3, solve from 0 to 2 in 2 steps" > /tmp/r.ucas && timeout 15 ./ucas /tmp/r.ucas
```
**Observed:** (entire output — nothing after the echoed line):
```
> y' = -2y + 1, y(0)=3, solve from 0 to 2 in 2 steps
```
Working control:
```sh
cd $ROOT && printf '%s\n' "solve y' = -2y + 1, y(0)=3, from 0 to 2 in 2 steps" > /tmp/r.ucas && timeout 15 ./ucas /tmp/r.ucas
```
```
  ucas: dsolve y from 0 to 2 steps 2
  y(t) = 2.5exp(-2*t) + 0.5
```
Also silent: `fib[0]=0, fib[1]=1, closed form of fib`.

### NLP-2 — 2 — Ambiguity "sin x squared" always parsed as `sin(x^2)`
**Severity:** NLP
**Why it matters:** _not recorded_
The frontend silently chooses `sin(x^2)` with no ambiguity note, so the
derivative/integral is of a different function. Explicit `sin^2 x` is rejected.

**Reproducer:**
```sh
cd $ROOT && printf '%s\n' 'the derivative of sin x squared with respect to x' > /tmp/r.ucas && timeout 15 ./ucas /tmp/r.ucas
```
**Observed:**
```
  ucas: it(x) = sin(x^2)
  ucas: diff it x
d/dx it = 2x*cos(x^2)
```
**Expected:** (if "squared" applies to sin): `it(x)=sin(x)^2`, `d/dx = 2sin(x)cos(x)`.
With explicit spelling it works: `the derivative of (sin x)^2 with respect to x`
→ `2sin(x)*cos(x)`. But `the integral of sin^2 x from 0 to pi` →
```
  sorry: I didn't expect '^' here
```

### NLP-3 — 3 — Many ordinary English phrasings are not recognized (grouped)
**Severity:** NLP
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
one-line failure (no `ucas:` translation). This is a coverage gap across
derivatives, limits, Taylor/cheby, sums/products, integrals, solids and Fourier.

| Query | Observed output |
|---|---|
| `the taylor series of log(1+x) at 0 order 4` | `  sorry: I didn't follow "order 4"` |
| `taylor polynomial of x^3 + 2x at 0 order 3` | `  sorry: I didn't follow "order 3"` |
| `taylor of exp(x) to order 25` | `  sorry: I didn't follow "to order 25"` |
| `cheby poly degree 4 of cos x` | `  sorry: of what?` |
| `the chebyshev polynomial approximation of degree 4 for sin x on 0 to 1` | `  sorry: of what?` |
| `the closed form of the sum of i from 1 to n` | `  sorry: the sum of what?` |
| `the sum of i squared for i from 1 to n, closed form` | `  sorry: I didn't follow "closed form"` |
| `closed form of sum(i, 1, n, i^2)` | `  sorry: I don't understand "sum(i" here` |
| `the product from k = 1 to n of k` | `  sorry: I don't understand "product from k" here` |
| `the sum of x^n / n!` | `  sorry: "+" needs two or more things, joined by "and"` |
| `the implicit derivative of x^3 + y^3 = 3xy` | note reads `implicit` as a variable, then `  sorry: I didn't follow "derivative of x^3 + y^3 = 3xy"` |
| `fx of x^2 y + 3y` | `  sorry: I didn't follow "of x^2 y + 3y"` |
| `calculate the derivative of sinh x with respect to x` | `  sorry: I don't understand "sinh x with" here` |
| `compute the integral of 2x from 0 to 3 numerically` | `  sorry: I didn't follow "numerically"` |
| `the numeric integral of sin(x^2) from 0 to 3` | note reads `numeric` as a variable, then `  sorry: I didn't follow "integral of sin(x^2) from 0 to 3"` |
| `limit at infinity of (2x^2 + 3x)/(x^2 + 1)` | raw: `error: expected a function` at `at` |
| `the volume of the solid obtained by revolving sin x about the x axis from 0 to pi` | note reads `solid` as a variable, then `  sorry: I didn't follow "obtained by revolving ..."` |
| `the surface area of y = x^3 revolved about the x axis from 0 to 1` | `  sorry: I didn't follow "revolve about the x axis from 0 to 1"` (the `y = x^3` function is dropped) |
| `the surface area of a sphere of radius r` | note reads `surface` as a variable, then `  sorry: I didn't follow "area of a sphere of radius r"` |

Note the "silently dropping `numeric`/`closed form`" family: `numeric`,
`numerically`, `closed form`, `solid`, `implicit` are either read as free
variables or rejected rather than mapped to a tool option.

### NLP-4 — 4 — Second-order ODE and `dy/dt` English phrasings fail; raw parse errors leak
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Repro / observed:
**Observed:**
```
> solve y'' + y = 0 with y(0) = 1, y'(0) = 0 from 0 to 2 in 4 steps
  sorry: expected '=' after y''
```
```
> solve dy/dt = 3y, y(0)=2, from 0 to 1 in 2 steps
  ucas: solve dy/dt = 3y, y(0)=2, from 0 to 1 in 2 steps
<english>:1:8: error: unexpected 'to' in from 0 to 1
```
(The Laplace route `solve y'' + y = 0 ... using laplace` *does* work — see
`05_ode_recurrence.out`.) `dsolve y from 0 to 2 in 4 steps` →
`error: unexpected 'in' after the statement`.

### NLP-5 — 5 — Recurrence "closed form" requests leak raw parser errors
**Severity:** NLP
**Why it matters:** _not recorded_
**Observed:**
**Reproducer:**
```sh
> fib[0] = 0; fib[1] = 1; fib[n+2] = fib[n+1] + fib[n]; closed form of fib
... error: expected an expression   (at "fib")
> recurrence a[n]=2a[n-1]+1, a[0]=0, closed form
... error: only a table [a, b, ...] can be indexed
> solve the recurrence fib[n] = fib[n-1] + fib[n-2], fib[0]=0, fib[1]=1
... error: only a table [a, b, ...] can be indexed
```
**Expected:** route to `closed`/`zsolve`/`genfunc`. Instead the untranslated
English is passed to the raw ucas parser, which errors.

### LIMIT-1 — 1 — Derivative / Taylor orders hard-capped at 12
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
requests error from the tool rather than being translated/handled:
**Observed:**
**Reproducer:**
```sh
the 50th derivative of sin x   ->  ucas: diff it 50
                                  <english>:2:11: error: the order is 1 to 12
taylor series of sin x to order 30 -> ucas: taylor it order 30
                                  <english>:2:19: error: order 0 to 12
```

### LIMIT-2 — 2 — Laplace transform has no rule for several standard factors
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
transform engine declines (documented limitation, recorded for completeness):
**Observed:**
**Reproducer:**
```sh
the laplace transform of log t       -> laplace log t
                                        error: laplace: no rule for the factor log(t)
the laplace transform of t^n         -> error: laplace: no rule for the factor t^n
the laplace transform of t^p sin t   -> error: laplace: no rule for the factor t^p
```
Likewise `the fourier transform of e^(-a|x|)` leaks a raw parse error because
`|x|` is read as integer bitwise-or:
```
  ucas: fourier e^(-a|x|)
<english>:1:8: error: '|' needs integer operands (declare the parameter as int or uN)
```

## Checks that passed

### No CRASH / HANG / DETERMINISM issues
- Every one of ~200 queries exited 0 within 0.01–0.7 s; none hit `timeout 15`.
- No signal, truncated process output, or non-JSON MCP reply was observed.
- Each golden `.out` was regenerated twice and `diff`-identical (see SUMMARY).
- Note: driving the shared in-process `tools.ucas.english` session can inherit
  another agent's `it(x: i8)` definition and give misleading integer-typed
  derivatives; fresh `ucas --mcp` / CLI processes (as used for all goldens and
  findings here) are unaffected.
