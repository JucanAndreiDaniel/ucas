# Stress findings — `ode_boundary_problems`

_Original heading: FINDINGS — `ode_boundary_problems`_

# FINDINGS — `ode_boundary_problems`

All commands use `$ROOT/ucas` and are bounded with `timeout`.
MCP reproducers start with the two standard lines:

```
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

Every CLI golden in this folder was run twice and diffed byte-for-byte (all identical).
No crash or hang was found; the issues below are wrong answers, silent drops, and limits.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | `identify` proves a discontinuous RHS is "linear", invents a characteristic equation |
| LIMIT | 6 | `dsolve` only accepts the pre-solved form `y' = ...`; standard, singular-coefficient and i… |

## Findings

### WRONG-1 — `identify` proves a discontinuous RHS is "linear", invents a characteristic equation
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
printf "identify y' = sign(y)\n" | timeout 15 $ROOT/ucas
```

**Observed:**

```
identify y' = sign(y):
  an ordinary differential equation of order 1 in y(t)
  linear: every y-term appears to the first power [proved: the partial derivatives in y, y', ... do not involve y]
  homogeneous
  constant coefficients (and autonomous)
  characteristic equation: r = 0, roots 0
  homogeneous solutions: y(t) = a combination of 1
  autonomous: the independent variable does not appear explicitly
  first order: y' = sign(y)
  separable: yes (autonomous)
  solved for the highest derivative: y' = sign(y)  (then initial values and: dsolve y)
```

**Why it matters:** a bug:** `y ↦ sign(y)` is **not** linear and not homogeneous; the ODE has no
characteristic equation and no "homogeneous solutions y = const". The `[proved: the partial
derivatives in y ... do not involve y]` tag is a *false proof* (the derivative of `sign` is
0 away from 0, which is exactly the wrong criterion for linearity of a discontinuous map).
`identify y' = floor(y)` gives the same false "linear / r = 0" answer, and
`identify y' = (y>0 ? 1 : -1)` gives "linear ... inhomogeneous: forcing term -1".
Captured as a golden in `16_identify_ode.out` and `mcp_ode_identify.out` (MCP ids 3, 4).

MCP reproducer (after the two standard lines):

```
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"properties","arguments":{"op":"identify","args":{"f":"y' = sign(y)"}}}}
```

### WRONG-2 — `identify` chooses a parameter as the independent variable
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
printf "identify y'' + a*y' + b*y = 0\nidentify x' = k*x\n" | timeout 15 $ROOT/ucas
```

**Observed:**

```
identify y'' + a*y' + b*y = 0:
  an ordinary differential equation of order 2 in y(a)
  linear: every y-term appears to the first power [proved: the partial derivatives in y, y', ... do not involve y]
  homogeneous
  variable coefficients (they depend on a)
  not autonomous: it depends on the independent variable explicitly
  ...
identify x' = k*x:
  an ordinary differential equation of order 1 in x(k)
  ...
  exact (M + N x' = 0 with M = -k*x, N = 1): no [numeric: dM/dx - dN/dk = -k]
```

**Why it matters:** a bug:** for `y'' + a*y' + b*y = 0` the independent variable is the default `t` and
`a, b` are constant parameters; the tool picks the first free symbol (`a`) as the
independent variable, labels the coefficients "variable", and calls the ODE non-autonomous.
It does the same with `k` in `x' = k*x` and `c` in `u' = c*u`. This changes the whole
classification (constant/variable coefficients, autonomous or not) and the exactness test
(`dM/dk` instead of `dM/dt`). Golden: `16_identify_ode.out`, `mcp_ode_identify.out` (ids 5, 6).

### WRONG-3 — a smooth stiff ODE is reported as "blow-up, or the right side is undefined"
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
cd $ROOT/tests/stress/areas/math/ode_boundary_problems
timeout 30 $ROOT/ucas 21_stiff_misdiagnosis.ucas
```

**Observed:** (first block):

```
> y' = -1e8*y
> y(0)=1
> dsolve y from 0 to 1 steps 4
y' = -1e8*y, y(0) = 1
  linear with constant coefficients: eigenvalues -100000000
  y(t) = exp(-100000000*t)
  check: satisfies the equations at 201 points of [0, 1] (max relative residual 0) and the initial values
  numeric: the solution stops before 1 (blow-up, or the right side is undefined)
      t            y(t)
      0            1
```

**Why it matters:** a bug:** the right-hand side is defined and Lipschitz everywhere, the solution
`e^(-10^8 t)` was *just printed* and its residual is 0, yet the numeric integrator (explicit
Dormand–Prince) steps to a minimum step size and the tool reports a false blow-up/undefined
diagnosis, truncating the table to `t=0`. The same happens at `-1e9*y`. A user trusting the
numeric column would conclude the solution does not exist. Golden: `21_stiff_misdiagnosis.out`.
Related LIMIT: `y' = -1e7*y` on `[0,1]` "succeeds" only after **3,022,612** adaptive steps.

### WRONG-4 — extra/conflicting initial conditions and repeated equations are silently discarded
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
printf "y' = -y\ny(0)=1\ny'(0)=2\ndsolve y from 0 to 1 steps 2\nz' = -z\nz' = -2*z\nz(0)=1\ndsolve z from 0 to 1 steps 2\nlaplace solve w' = w, w(0)=1, w(0)=2\n" | timeout 15 $ROOT/ucas
```

**Observed:** (relevant lines):

```
y' = -y, y(0) = 1
  ...
z' = -2*z, z(0) = 1
  linear with constant coefficients: eigenvalues -2
laplace solve w' = w, w(0)=1, w(0)=2
w' = w, w(0) = 2
  ...
  w(t) = 2*e^t    for t >= 0
```

**Why it matters:** a bug:** `y'(0)=2` is a contradictory extra initial condition for a first-order ODE
(it is simply dropped with no note); the earlier equation `z' = -z` is silently overwritten
by `z' = -2*z` with no warning; duplicate initial conditions for the same order silently use
the **last** one. None of this is reported. (A sibling area documents the related MCP
semicolon-separator bug where *all* conditions after `;` are dropped.)

### LIMIT-1 — `dsolve` only accepts the pre-solved form `y' = ...`; standard, singular-coefficient and implicit ODEs are rejected
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
cd $ROOT/tests/stress/areas/math/ode_boundary_problems
timeout 15 $ROOT/ucas 07_singular_coeff.ucas
timeout 15 $ROOT/ucas 17_implicit_rejected.ucas
```

**Observed:**

```
> t*y' = y
  note: '=' inside an expression read as '=='
_(t: real, y': real, y: real) = t*y' == y
  -> bool
07_singular_coeff.ucas:3:29: error: no equation for y (write y' = ...)

> z'' + z'^2 + z = 0
  note: '=' inside an expression read as '=='
_(z'': real, z': real, z: real) = z'' + z'^2 + z == 0
  -> bool
17_implicit_rejected.ucas:7:29: error: no equation for z (write z' = ...)
```

**Why it matters:** a bug/limit:** `y'' + y = 0`, `t*y' = y`, `t^2*y'' + t*y' + t^2*y = 0`, `(y')^2 = 4y`,
`y'^2 + y^2 = 1`, Mathieu's equation, and the damped oscillator `y'' + 2*y' + 5*y = 0`
are all silently turned into *boolean function definitions* ("`=` inside an expression read
as `==`") and `dsolve` then says "no equation for y". The same equations are accepted by
`laplace solve` and by `properties identify`, so the two frontends disagree. Singular
coefficients and implicit ODEs are therefore completely out of reach of `dsolve`.

### LIMIT-2 — no boundary-value-problem support; a BVP is reported as a malformed IVP
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
cd $ROOT/tests/stress/areas/math/ode_boundary_problems
timeout 15 $ROOT/ucas 08_bvp_rejected.ucas
```

**Observed:**

```
> y'' = -y
> y(0)=0
> y(1)=1
> dsolve y from 0 to 1 steps 4
08_bvp_rejected.ucas:4:29: error: missing initial value y'(t0) = ...
```

**Why it matters:** a limit:** a well-posed Dirichlet BVP with two point conditions is rejected as an
incomplete initial-value problem, with no suggestion of a shooting/collocation alternative
(the tool's own `identify` output even suggests "then initial values and: dsolve y").
Golden: `08_bvp_rejected.out`.

### LIMIT-3 — polynomial forcing defeats the closed-form path of both ODE solvers
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
printf "y' = t\ny(0)=0\ndsolve y from 0 to 2 steps 2\ny'' = 1\ny(0)=0\ny'(0)=0\ndsolve y from 0 to 2 steps 2\nlaplace solve z' = t, z(0)=0\n" | timeout 15 $ROOT/ucas
```

**Observed:**

```
y' = t, y(0) = 0
  linear with constant coefficients (eigenvalues 0), but no closed form was found for the forcing: numeric only
y'' = 1, y(0) = 0, y'(0) = 0
  linear with constant coefficients (eigenvalues 0 (x2)), but no closed form was found for the forcing: numeric only
<stdin>:1:9: error: expected derivatives of y
```

**Why it matters:** a limit:** integrating a constant or `t` is elementary (`t^2/2`, `t^3/6`), yet
`dsolve` falls back to numeric and `laplace_solve` rejects the pure integrator form.
For comparison, `laplace solve y' - y = t, y(0)=0` (with a `y` term) *does* get a closed form.

### LIMIT-4 — `laplace_solve` rejects a pure first-order derivative equation
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
cd $ROOT/tests/stress/areas/math/ode_boundary_problems
timeout 15 $ROOT/ucas 19_laplace_rejects_integrator
```

**Observed:**

```
> laplace solve y' = 1, y(0)=0
19_laplace_rejects_integrator.ucas:1:9: error: expected derivatives of y
> laplace solve y' = t, y(0)=0
19_laplace_rejects_integrator.ucas:2:9: error: expected derivatives of y
> laplace solve y' = y, y(0)=1
laplace solve y' = y, y(0) = 1   (solved correctly: y(t) = e^t)
```

**Why it matters:** a limit:** `y' = f(t), y(0)=y0` is a perfectly valid first-order linear ODE
(pure integrator); the tool needs a `y` term on the left and rejects the basic case.
Golden: `19_laplace_rejects_integrator.out`.

### LIMIT-5 — non-uniqueness is never reported for ODEs with non-Lipschitz right-hand sides
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
cd $ROOT/tests/stress/areas/math/ode_boundary_problems
timeout 15 $ROOT/ucas 18_nonunique.ucas
```

**Observed:**

```
y' = 3*y^(2/3), y(0) = 0
  not linear with constant coefficients: numeric only
  numeric (Dormand-Prince 5(4), adaptive, 16 steps, tolerance 1e-10); a 1000x looser solve differs by 0
      t            y(t)
      0            0
      0.25         0
      ...
```

**Why it matters:** a limit:** `y(t)=t^3` (and the whole family `y=(t-c)^3` for `t>=c`) also satisfies
`y'=3y^(2/3), y(0)=0`, and `y=t^2/4` satisfies `y'=sqrt(y), y(0)=0`. The solver returns
the stationary solution and gives no indication that the IVP is non-unique. Golden:
`18_nonunique.out`.

### LIMIT-6 — symbolic linear solve gives up above ~9th order / 9 coupled variables
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
printf "y'''''''''' = y\ny(0)=1\ny'(0)=0\ny''(0)=0\ny'''(0)=0\ny''''(0)=0\ny'''''(0)=0\ny''''''(0)=0\ny'''''''(0)=0\ny''''''''(0)=0\ny'''''''''(0)=0\ndsolve y from 0 to 1 steps 2\n" | timeout 15 $ROOT/ucas
```

**Observed:**

```
y'''''''''' = y, y(0) = 1, ...
  not linear with constant coefficients: numeric only
  numeric (Dormand-Prince 5(4), adaptive, 68 steps, tolerance 1e-10); a 1000x looser solve differs by 5.5e-12
```

**Why it matters:** a limit:** order 6 (`y'''''' = y`) is solved symbolically with all six roots, but
order 10 is declared "not linear with constant coefficients" although it is; the numeric
fallback happens to be correct here (`y(1)=1.000000276`), so it is a missed symbolic solve,
not a wrong answer. A 10-variable companion system (`x0'=x1, ..., x9'=-x0`) shows the same
cutoff. Not kept as a golden (large, but deterministic).

## Checks that passed

### Notes — areas checked with no issue found
- Coupled linear systems of size 2–5: distinct real, repeated (defective and diagonal),
  complex and zero eigenvalues, forcing, non-zero initial time — all self-check residuals
  ~1e-16 and numeric agreement ~1e-11. (`01`–`05`, `mcp_ode_dsolve.out`.)
- Exact solutions (`exp`, `sinh`/`cosh`, damped/under/critical/over-damped, resonance),
  Laplace and Z solvers, transfer functions, Taylor/power series — cross-checks agree.
- Nonlinear/chaotic systems (van der Pol μ=1,10; Lorenz; Rössler; Lotka–Volterra; Duffing;
  pendulum; Mathieu parses only in pre-solved form) all produce smooth tables; Lorenz over
  `[0,20]` honestly flags the 1000× looser solve as differing by 0.092.
- Discontinuous right-hand sides expressible as `floor`/ternary are integrated accurately
  (e.g. `y'=floor(t)` gives `0, 0.5, 1, 2, 3` at `t=0,1.5,2,2.5,3`).
- Every would-be golden was run twice and diffed; no nondeterminism was observed in this area.
