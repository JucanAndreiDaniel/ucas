# Stress findings — `transforms_ode_series`

_Original heading: FINDINGS — `transforms_ode_series`_

# FINDINGS — `transforms_ode_series`

All commands use `$ROOT/ucas` and are bounded with `timeout`.
MCP reproducers are one JSON-RPC `tools/call`; prefix every one with the two standard lines:

```
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | high-order symbolic differentiation explodes / never terminates |
| WRONG | 4 | `powerseries` with the matching `var` argument silently multiplies by the variable |
| LIMIT | 2 | the documented `f` parameter of `dtft` breaks parsing |

## Findings

### WRONG-1 — `powerseries` with the matching `var` argument silently multiplies by the variable
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
printf 'powerseries exp(x) x\n' | timeout 15 $ROOT/ucas
```

**Observed:**

```
power series of e^x*x about x = 0
  Taylor coefficients c_0..c_7: 0, 1, 1, 1/2, 1/6, 1/24, 1/120, 1/720
  = sum_{m>=1} c_m x^m, c_m = 1/(m - 1)!
  matches e^u: radius of convergence inf
```

The same via MCP (`{"op":"powerseries","args":{"f":"exp(x)","var":"x","at":0}}`) returns
`power series of e^x*x ...`. Without `var`, `powerseries exp(x)` correctly gives coefficients
`1, 1, 1/2, 1/6, ...` and `c_m = 1/m!`.

**Why it matters:** a bug:** the MCP schema documents `var` as the variable of expansion. Supplying the *correct
variable makes the tool build `powerseries exp(x) x`, which the CLI reparses as `exp(x)*x`
(cf. the note "the last word x is read as the variable (write *x to multiply by it)"). The answer
is the series of `x*e^x`, not of `e^x`, and is labelled as such — a wrong closed form caused by a
frontend argument-placement defect. Same for `sin(t)` with `var:"t"`, `e^z` with `var:"z"`, etc.

### WRONG-2 — `laplace_solve` / `zsolve` silently discard semicolon-separated initial conditions
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (MCP):

```
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"transforms","arguments":{"op":"laplace_solve","args":{"equations":"y' = y; y(0) = 1"}}}}
```

**Observed:**

```
y' = y, y(0) = 0
  note: y(0) not given: taken as 0
  transformed: (s - 1)Y(s) = 0
  Y(s) = 0
  y(t) = 0    for t >= 0
  check: residual of the equation at 201 points of [0, 10]: max 0; initial values hold (max difference 0)
```

**Expected:** `y(t) = e^t`. With comma separators the same tool is correct:
`laplace solve y'=y, y(0)=1` gives `y(t) = e^t`. The CLI must use commas, but the MCP tool accepts
a semicolon-separated `equations` string without validating it, silently drops everything after the
first `;`, and returns the zero solution with a *passing* self-check ("initial values hold"). The
same defect affects `zsolve` (`"x[n+1] = 2x[n]; x[0]=1"` → `x[n] = 0` instead of `2^n`) and
second-order problems (`y''+y=0; y(0)=1; y'(0)=0` → `y=0` instead of `cos t`). This is an unsound
answer produced from a natural, malformed argument, with the checker reinforcing the wrong result.

### WRONG-3 — Fourier transform of a polynomial returns `0` instead of a derivative-of-delta distribution
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (MCP):

```
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"transforms","arguments":{"op":"fourier","args":{"f":"x"}}}}
```

**Observed:**

```
F{x}(w) = 0
  convention: F(w) = int f(x) e^(-iwx) dx over the real line (angular frequency; the inverse has 1/(2pi))
  delta terms: f does not decay, the transform is a distribution (not checked numerically)
```

`fourier(x^2)` and `fourier(x^3)` also return `0`. `fourier(1)`, `fourier(cos x)`, `fourier(sin x)`
correctly return `2pi*delta(w)`, `pi*(delta(w-1)+delta(w+1))`, `i*pi*(delta(w+1)-delta(w-1))`.

**Why it matters:** a bug:** with the stated convention the correct answers are `2*pi*i*delta'(w)`,
`-2*pi*delta''(w)`, `-2*pi*i*delta'''(w)`. The tool explicitly notices that the result is a
distribution ("delta terms: ...") yet returns the identically-zero function, which is silently
wrong rather than an honest "no rule".

### WRONG-4 — oscillatory Dirichlet series reported as divergent
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducers:**

**Reproducer:**
```sh
printf 'converge sin(n)/n\nconverge cos(n)/n\nsum(n,1,inf,sin(n)/n)\n' | timeout 15 $ROOT/ucas
```

**Observed:**

```
sum(n, 1, inf, sin(n)/n)
  diverges: comparison with the p-series sum 1/n (a_n ~ C/n, p <= 1)
```

`converge cos(n)/n`, `infinite_sum(sin(n)/n)`, `infinite_sum(cos(n)/n)`, and
`infinite_sum((-1)^n*sin(n)/n)` all give the same "diverges: comparison with the p-series" verdict.

**Why it matters:** a bug:** `sum sin(n)/n` and `sum cos(n)/n` converge (by Dirichlet's test); their values are
`(pi-1)/2 ≈ 1.0707963` and `-log(2 sin(1/2)) ≈ 0.0420195`. The tool's own partial sums expose the
contradiction: `S_1000 = 1.070694154`, and direct `sum(n,1,10000,sin(n)/n) = 1.07087`,
`sum(n,1,100000,sin(n)/n) = 1.07081` — clearly converging. The "comparison with p-series" rule is
invalid for a sign-changing `a_n`; it should not conclude divergence. Captured as a golden in
`06_adversarial_series.out`.

### LIMIT-1 — the documented `f` parameter of `dtft` breaks parsing
**Severity:** LIMIT
_Original classification: `LIMIT / NLP`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (MCP):

```
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"transforms","arguments":{"op":"dtft","args":{"values":[1,2,3],"f":"w"}}}}
```

**Observed:** `error (parse_error): unexpected ']' in 3] w` (MCP builds `dtft [1, 2, 3] w`).
CLI equivalent: `printf 'dtft [1,1,1] w\n' | ucas` → `error: unexpected ']' in 1] w`.
Without `f`, `dtft [1,1,1]` works and prints `X(w) = ...`. A documented, well-typed argument makes
the tool emit an invalid statement; captured as a golden in `07_malformed_defaults.out`.

### HANG-1 — high-order symbolic differentiation explodes / never terminates
**Severity:** HANG
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'diff exp(x^2)*log(1+x) x 12\n' | timeout 30 $ROOT/ucas
```

**Observed:** no output after the echoed statement (only `> diff exp(x^2)*log(1+x) x 12`, 30 bytes),
exit code 124 from `timeout 30`. Order 11 also times out; order 10 terminates but emits **4,487,873
bytes** of unsimplified expression. `diff x^x x 8` similarly emits 2.45 MB.

**Why it matters:** a bug:** the permitted order is 1..12 and no warning is given; a legal request at the top of
the documented range hangs with no output for >30 s and an unbounded intermediate expression. This
is a denial-of-service / expression-swell limit. Documented here, deliberately **not** added as a
golden `.out` (it would hang the test runner).

### LIMIT-2 — trivial constant arc-length antiderivative is not found
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'arclength x from 0 to 1\n' | timeout 15 $ROOT/ucas
```

**Observed:**

```
L = ∫ sqrt(1 + (1)^2) dx from 0 to 1
  no antiderivative found: numeric only
  numeric (adaptive Gauss-Kronrod 7-15, 15 evaluations): 1.4142135623731, ...
```

**Why it matters:** a bug (minor):** the integrand is the constant `sqrt(2)`, whose antiderivative `sqrt(2)*x`
is elementary; the tool falls back to numeric-only. Numeric value is correct. Not a wrong answer,
just a missed trivial simplification.

## Checks that passed

### Notes on determinism
Every golden (8 CLI + 4 MCP) was run twice and diffed byte-for-byte; all were identical, including
the numeric "estimated error" figures and Wronskian witness points. The nondeterministic-looking
cases above were probed but none fluctuated.
