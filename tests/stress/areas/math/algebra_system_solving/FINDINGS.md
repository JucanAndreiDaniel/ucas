# Stress findings — `algebra_system_solving`

_Original heading: FINDINGS — algebra_system_solving_

# FINDINGS — algebra_system_solving

Area: systems of polynomial/rational equations, condition handling, back-substitution certificates.
Binary: `$ROOT/ucas`. All reproducers below were run with `timeout`, and every
would-be golden was run twice and `diff`ed — **all outputs recorded here are deterministic**.
No crashes, hangs, or nondeterminism were observed in 185 generated systems + 10 hard probes.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | resultant back-substitution drops solutions; false "no real solution" |
| LIMIT | 2 | `solve` rejects valid systems outside two narrow shapes |

## Findings

### WRONG-1 — resultant back-substitution drops solutions; false "no real solution"
**Severity:** WRONG
_Original classification: `WRONG (HIGH): resultant back-substitution drops solutions; false "no r`._
**Why it matters:** _not recorded_
When ucas solves two polynomial equations in two unknowns it prints a resultant in `x`, then
back-substitutes. For resultants with a root where the *eliminated* variable's coefficient
vanishes (e.g. `x*y = 0` → the factor `x`), that root is silently discarded: ucas divides by a
factor containing `x` when recovering `y`. Affected systems lose valid real solutions, and
several are reported as having **no real solution at all**.

**Reproducer:**
Reproducer (CLI):
```sh
cd $ROOT/tests/stress/areas/math/algebra_system_solving
timeout 15 $ROOT/ucas 05_bug_missing_solutions.ucas
```

**Observed:** output (excerpt):
```
solve x*y = 0, x + y = 1 for x, y
  eliminating y: the resultant in x is x*(x - 1)
  x = 1, y = 0
  check: 1 solution substituted into both equations: residual 0
solve x*y = 0, x + y = 0 for x, y
  eliminating y: the resultant in x is x^2
  no real solution
solve (x-1)*(y-2) = 0, x + y = 3 for x, y
  eliminating y: the resultant in x is (x - 1)^2
  no real solution
solve x*y = 0, x^2 + y^2 = 1 for x, y
  eliminating y: the resultant in x is x^2*(x - 1)*(x + 1)
  x = -1, y = 0
  x = 1, y = 0
  check: 2 solutions substituted into both equations: residual 0
```

**Expected:** (verified independently with sympy 1.14):
- `x*y=0, x+y=1` → `{(0,1), (1,0)}`; ucas returns only `(1,0)` — **missing (0,1)**.
- `x*y=0, x+y=0` → `{(0,0)}`; ucas returns **no real solution** — wrong.
- `(x-1)*(y-2)=0, x+y=3` → `{(1,2)}`; ucas returns **no real solution** — wrong.
- `x*y=0, x^2+y^2=1` → `{(0,1),(0,-1),(1,0),(-1,0)}`; ucas returns only `(±1,0)` — **missing (0,±1)**.

Same bug confirmed via MCP `algebra.solve` (`mcp_solve_bugs.jsonl`):
`x*y=0, x+y=1` → `solutions: [{"x":"1","y":"0"}]`, check `passed:true`;
`x*y=0, x+y=0` → `solutions: []`, check list empty. The certificate is *correct for the
solutions it does return* — the problem is **missing solutions**, so the substitution check
cannot catch it. Other reproducers from the catalog: `K01`–`K10`, `O01`–`O04`, `J25`, and
`x^20 + y^20 = 1, x + y = 1` (true solutions `(0,1),(1,0)`, ucas: "no real solution").

Root cause hypothesis: back-substitution solves the first equation for `y`, e.g. `y = 0/x`,
losing the branch `x = 0`; it should try the other equation (or retain the branch) when the
divisor can vanish.

### WRONG-2 — high-degree polynomials falsely report "no real solution"
**Severity:** WRONG
_Original classification: `WRONG (HIGH): high-degree polynomials falsely report "no real solution`._
**Why it matters:** _not recorded_
Numeric real-root isolation gives up above roughly degree 14 and the solver emits an
unsound "no real solution" instead of "could not isolate all roots" (it *does* use a
bisection fallback for some other high-degree inputs, e.g. `x^100 - 1 = 0` → `x = ±1`).

**Reproducer:**
Reproducer (CLI):
```sh
cd $ROOT/tests/stress/areas/math/algebra_system_solving
timeout 15 $ROOT/ucas 06_bug_identity_highdegree.ucas
```

**Observed:** output (excerpt):
```
solve x^20 + x - 1 = 0 for x
  no real solution
solve x^15 + x - 1 = 0 for x
  no real solution
solve (x^2-2)*(x^2-3)*(x^2-5)*(x^2-7)*(x^2-11)*(x^2-13)*(x^2-17) = 0 for x
  no real solution
```

**Expected:**
- `x^20 + x - 1` has real roots `≈ -1.036193717, 0.893895412` (`f(0)=-1, f(1)=1` by IVT).
- `x^15 + x - 1` has a real root in `(0,1)`.
- The product of 7 quadratics has 14 real roots `±√2, ±√3, ±√5, ±√7, ±√11, ±√13, ±√17`.
  The 6-quadratic version in the same golden correctly returns all 12 roots — so this is a
  solver failure, not an inherent limit.
- `x^n + x - 1 = 0` returns correct numeric roots for `n = 8,10,13,14` but "no real solution"
  for `n = 15,16,20`. MCP confirms `solutions: []` for all three failing cases.

### WRONG-3 — identity equations report "no real solution"
**Severity:** WRONG
_Original classification: `WRONG (MEDIUM): identity equations report "no real solution"`._
**Why it matters:** _not recorded_
For an equation that is an identity (true for every `x` in its domain), ucas first says
"every x is a solution (where the equation is defined)" / "x does not occur in the
equation", then contradicts itself with "no real solution". In MCP the result carries
`every_value: true` while `solutions: []` — so the machine-readable answer is also wrong.

**Reproducer:**
Reproducer (CLI):
```sh
cd $ROOT/tests/stress/areas/math/algebra_system_solving
printf 'solve (x-3)/(x-3) = 1\nsolve 0*x = 0\nsolve (x+1)^2 - (x^2+2x+1) = 0\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:** output:
```
solve (x-3)/(x-3) = 1 for x
  every x is a solution (where the equation is defined)
  no real solution
solve 0*x = 0 for x
  x does not occur in the equation
  no real solution
solve (x+1)^2 - (x^2+2x+1) = 0 for x
  x does not occur in the equation
  no real solution
```

**Expected:** the solution set is all real `x` (excluding `x = 3` where the denominator vanishes
in the first case); it must not be reported as "no real solution". Note the *conditional*
case `solve (x^2-1)/(x-1) = 2` is handled correctly (excludes `x=1`, no solution) — so this
is specific to the identity / `every_value` path. MCP structured for `(x-3)/(x-3)=1`:
`{"kind":"solve", ..., "solutions": [], "every_value": true, "complex_solutions": 0}`.

### LIMIT-1 — `solve` rejects valid systems outside two narrow shapes
**Severity:** LIMIT
_Original classification: `LIMIT (LOW): solve rejects valid systems outside two narrow shapes`._
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT
printf 'solve x + y + z = 6, x*y = 6, z = 1\nsolve 1/x + 1/y = 1, 1/x - 1/y = 1/3\n' \
  | timeout 15 ./ucas
```
**Observed:**
```
solve x + y + z = 6, x*y = 6, z = 1 for x, y, z
  only linear systems and two polynomial equations in two unknowns are solved
solve 1/x + 1/y = 1, 1/x - 1/y = 1/3 for x, y
  not a polynomial system in x, y
```
**Expected:** these are solvable (first has `(x,y,z)=(2,3,1),(3,2,1)`; second reduces to a
polynomial system after clearing denominators with `x,y ≠ 0`). This is a capability limit,
not an unsound answer; reported for completeness. Single rational equations with division
(e.g. `(x^2-1)/(x-1)=0`) are handled correctly.

### LIMIT-2 — trig identity returns an arbitrary finite numeric sample
**Severity:** LIMIT
_Original classification: `LIMIT (LOW): trig identity returns an arbitrary finite numeric sample`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `printf 'solve sin(x)^2 + cos(x)^2 = 1\n' | timeout 15 ./ucas`
**Observed:** prints a note "no exact method applies; sign changes in [-100, 100] … solutions
may be missed" and then ~64 grid values (`x = -1999/20`, `x = -999/10`, …) as "solutions".
Each listed value does satisfy the identity, but the answer is a finite sample of an
infinite solution set and is presented as the solution set. Deterministic across runs.
Classified LIMIT rather than WRONG because no listed value is invalid.

## Checks that passed

### F6 — CHECK: crash / hang / nondeterminism — none found
All 185 catalog systems (`systems.py`) and 10 deliberately hard probes (degree-100 polys,
degree-20 resultants, 4-variable nonlinear systems) exited 0 within 15 s. Every golden
(`.ucas`/`.out` and `.jsonl`/`.out`) was generated twice and `diff`ed identically. The NLP
frontend's `solve` routing (`english`) worked for "solve the system …" and "solve x^2+y^2=1
and y=x …"; it failed on "solve x squared minus 5 x plus 6 equals 0" (`not_understood`),
an NLP coverage gap outside this area's correctness scope.
