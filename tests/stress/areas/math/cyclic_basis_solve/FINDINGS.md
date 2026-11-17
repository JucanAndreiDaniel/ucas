# Stress findings — `cyclic_basis_solve`

_Original heading: FINDINGS — `cyclic_basis_solve` stress area_

# FINDINGS — `cyclic_basis_solve` stress area

All commands below were run with the absolute binary path
`$ROOT/ucas` and, where a timeout mattered, `timeout 15`.
Deterministic, non-crashing reproducers also have `.ucas`/`.out` or
`.jsonl`/`.out` goldens in this folder. No CRASH or true HANG was found in
the cyclic-inheritance code; the real defects are in `solve`/`dsolve`
soundness and in state handling after rejected definitions.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 6 | `solve` reports "no real solution" for identities (infinitely many solutions) |
| NLP | 2 | `solve for x` silently rewrites to `dsolve x` |
| LIMIT | 3 | LIMIT / timeout-boundary — cyclic-basis gate search can exceed the 15 s budget under load |

## Findings

### WRONG-1 — `solve` reports "no real solution" for identities (infinitely many solutions)
**Severity:** WRONG
**Reproducer:**
```sh
printf 'solve x = x for x\nsolve 2*x = 2*x for x\nsolve 0*x = 0 for x\nsolve 5 = 5 for x\nsolve sin(x) = sin(x) for x\n' \
  | $ROOT/ucas
```

**Observed:**
```
solve x = x for x
  x does not occur in the equation
  no real solution
solve 2*x = 2*x for x
  x does not occur in the equation
  no real solution
solve 0*x = 0 for x
  x does not occur in the equation
  no real solution
solve 5 = 5 for x
  x does not occur in the equation
  no real solution
solve sin(x) = sin(x) for x
  x does not occur in the equation
  no real solution
```

**Why it matters:** it is a bug
Each equation is a tautology that holds for *every* real `x`, so the solution
set is all of R (infinitely many solutions). ucas canonicalises the equation to
`0 = 0`, notices the unknown cancelled, and then emits the **false** claim
"no real solution". The MCP frontend makes the unsoundness machine-readable:
`mcp_solve_degenerate.jsonl` id 1 returns
`"structuredContent":{"result":{"solutions":[],"complex_solutions":0},...}`
with `ok:true` — i.e. a proof-like "there are no solutions" answer for an
equation whose solution set is all reals.
**Expected:** "all real x" / a free,
unconstrained variable (as already done correctly for `solve 0*x+0*y=0 for
x,y`, which reports both variables free).

Related true-negative cases are handled correctly, which isolates the bug:
`solve x = x + 1 for x` has no solution and `solve 0*x = 1 for x` has no
solution, yet they produce the same misleading "x does not occur" message.

**Goldens**: `sol01_solve.out` … `sol07_solve.out`, `sol39_solve.out`,
`sol40_solve.out`, `sol50_multi.out`, `mcp_solve_degenerate.out`.

### WRONG-2 — `solve` accepts NaN/±Inf as "solutions" and passes a vacuous check
**Severity:** WRONG
**Reproducer:**
```sh
printf 'solve 0/0 = x for x\nsolve x = 1/0 for x\n' | $ROOT/ucas
```

**Observed:**
```
solve 0/0 = x for x
  x = real(0/0)
  check: x = it substituted, the equation holds at 0 sample points of the other variables (residual 0)
solve x = 1/0 for x
  x = real(1/0)
  check: x = it substituted, the equation holds at 0 sample points of the other variables (residual 0)
```

**Why it matters:** it is a bug
`real(0/0)` is NaN and `real(1/0)` is infinity; neither is a real solution of
an equation over the reals. The attached "check" is marked `passed:true` with
`points:0` — a vacuous verification (MCP `structuredContent.checks` shows
`{"kind":"substitution","points":0,"max_diff":0,"passed":true}`).
**Expected:**
reject non-finite coefficients/solutions or report "no real solution".

**Goldens**: `sol16_solve.out`, `sol17_solve.out`, `mcp_solve_divzero.out`.

### WRONG-3 — `dsolve` silently resolves contradictory initial conditions
**Severity:** WRONG
**Reproducer:**
```sh
printf "y' = y; y(0) = 1; y(0) = 2; dsolve y from 0 to 1 steps 4\n" \
  | $ROOT/ucas
```

**Observed:**
```
y' = y, y(0) = 2
  linear with constant coefficients: eigenvalues 1
  y(t) = 2exp(t)
  check: satisfies the equations at 201 points of [0, 1] (max relative residual 0) and the initial values
```

**Why it matters:** it is a bug
Two conflicting values `y(0)=1` and `y(0)=2` are supplied; the solver silently
keeps the **last** one and produces a solution as if nothing were wrong.
**Expected:** an inconsistency error (the initial data are over-specified and
contradictory), not a silently-chosen branch.

**Golden**: `ds03_dsolve.out` (MCP equivalent: `mcp_dsolve_degenerate.jsonl`
id 1).

### WRONG-4 — `dsolve` silently ignores extra, inconsistent derivative IC
**Severity:** WRONG
**Reproducer:**
```sh
printf "y' = y; y(0) = 0; y'(0) = 1; dsolve y from 0 to 1 steps 4\n" \
  | $ROOT/ucas
```

**Observed:**
```
y' = y, y(0) = 0
  linear with constant coefficients: eigenvalues 1
  y(t) = 0
  check: satisfies the equations at 201 points of [0, 1] (max relative residual 0) and the initial values
```

**Why it matters:** it is a bug
The added condition `y'(0)=1` contradicts `y'=y, y(0)=0` (which forces
`y'(0)=0`). The solver drops the extra condition without any note and even
asserts the solution satisfies "the initial values".
**Expected:** flag the
over-specified, inconsistent initial data.

**Golden**: `ds04_dsolve.out`.

### WRONG-5 — STATE / WRONG — a rejected `model`/`basis` definition leaves a phantom symbol with default costs
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
printf 'model m : nope { iadd: 1, fadd: 7 }\ncost x+y model m\nmodels\n' \
  | $ROOT/ucas
```

**Observed:**
```
<stdin>:1:11: error: unknown model
    model m : nope { iadd: 1, fadd: 7 }
              ^
cost of x + y under m: 1 (1 operations, shared subterms counted once)
  fadd             1 x 1     = 1
model m { iadd: 1, logic: 1, shift: 1, imul: 1, idiv: 1, ..., fadd: 1, fmul: 1, ... }
```

**Why it matters:** it is a bug
The definition is *rejected* ("unknown model"), yet a phantom model `m` is
installed in the session with every class defaulting to cost 1 — silently
discarding the declared `fadd: 7`. Subsequent `cost ... model m` succeeds with
the wrong costs and `models` lists the phantom. Error handling must be atomic:
a rejected definition must not mutate the symbol table. The basis case is the
same class of bug: after `basis a : nope { not(x) = ~x }`, `gates f basis a`
reports "basis a has no gates" (phantom empty basis) instead of "unknown
basis" (see `cb08_basis_unknown_parent.out`).

The MCP frontend makes this worse: `mcp_ucas_cyclic_model.jsonl` id 3 returns
an envelope with **both** `ok:false` + `error:{code:"parse_error"}` **and** a
fully-populated `result:{kind:"cost",...}` — contradictory success/failure
state in one reply.

**Goldens**: `cm04_model_unknown_parent.out`, `cb08_basis_unknown_parent.out`,
`mcp_ucas_cyclic_model.out`.

### WRONG-6 — `solve ... mod 1` claims "every x" then reports a single solution
**Severity:** WRONG
_Original classification: `WRONG / LIMIT`._
**Reproducer:**
```sh
printf 'solve x = 2 mod 1\n' | $ROOT/ucas
```

**Observed:**
```
  x = 2 mod 1: every x (the equation is 0 = 0 mod 1)
x = 0 (mod 1)
  check: the solution substituted into the congruence: it holds; brute force over 0..0: 1 solution
```

**Why it matters:** it is a bug
The explanation says *every* integer is a solution, but the reported answer is
a single residue and the check asserts "1 solution". These statements cannot
all be true.
**Expected:** report the single residue class `x ≡ 0 (mod 1)` while
stating that it denotes all integers, without the contradictory "1 solution".

**Golden**: `sol25_solve.out`.

### NLP-1 — `solve for x` silently rewrites to `dsolve x`
**Severity:** NLP
**Reproducer:**
```sh
printf 'solve for x\n' | $ROOT/ucas
```

**Observed:**
```
  ucas: dsolve x
<english>:1:9: error: no equation for x (write x' = ...)
    dsolve x
            ^
```

**Why it matters:** it is a bug
A bare `solve for x` (missing algebraic equation) is misrouted by the English
fallback into the ODE solver `dsolve x`, producing an unrelated error.
**Expected:** an algebraic-solve parse error ("no equations to solve"), or a
clarifying question — not a silent jump to a different command family.

**Golden**: `sol42_solve.out`.

### NLP-2 — English frontend rejects common solve phrasing
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/cyclic_basis_solve
timeout 15 $ROOT/ucas --mcp < mcp_english_solve.jsonl
```
(case id 1: `english` tool with `text = "solve x equals x for x"`)

**Observed:**
```json
{"id": 1, "ok": false, ..., "text": "  sorry: I didn't follow \"equals x for x\"\n",
 "error": {"code": "not_understood", "message": "I didn't follow \"equals x for x\""}}
```

**Why it matters:** it is a bug
"x equals x" is ordinary phrasing for `x = x`; the English grammar recognises
`solve x = 1 and x = 2 for x` (same file, id 2) but not the spelled-out
`equals`. Expected equivalent handling of both spellings.

**Golden**: `mcp_english_solve.out`.

### LIMIT-1 — LIMIT / timeout-boundary — cyclic-basis gate search can exceed the 15 s budget under load
**Severity:** LIMIT
_Original classification: `LIMIT / timeout-boundary`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (unbounded form; the kept golden adds `max 4`)
```sh
cat > /tmp/opencode/cb19_unbounded.ucas <<'EOF'
basis a { inv(x) = ~x }
basis b : a { andp(x, y) = x & y }
basis a : b { orp(x, y) = x | y }
f(x: u4) = x ^ 0xf
gates f basis a
EOF
timeout 15 $ROOT/ucas /tmp/opencode/cb19_unbounded.ucas
```

**Observed:**
Isolated runs finished in 7.5 s / 7.8 s / 12.0 s with byte-identical output
(cost 14 via Shannon decomposition); during a loaded campaign the same input
hit `timeout 15` (rc 124) on two consecutive runs. No crash, no wrong answer —
this is a search-cost hazard, not unsoundness.

**Why it matters:** it matters
A deterministic input sits right at the test budget, so whether it is a
"passing golden" depends on machine load. The committed golden uses
`gates f basis a max 4` to bound the search. Do not add the unbounded form as
a golden.

**Golden (bounded)**: `cb19_basis_cycle_u4.out`.

### LIMIT-2 — negative/zero/huge `dsolve` step counts are silently accepted
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
printf "y' = 1; y(0) = 0; dsolve y from 0 to 1 steps 0\n" | $ROOT/ucas
printf "y' = 1; y(0) = 0; dsolve y from 0 to 1 steps -1\n" | $ROOT/ucas
```
(`steps 100000` is likewise silently capped at 1024 rows.)

**Observed:** `steps 0` and `steps -1` both silently produce the default 10-row
table; `steps 100000` clamps to 1024 rows. No diagnostic is emitted for the
invalid negative value.

**Why it matters:** it matters** Not a crash, but a silent coercion of invalid input;
documented so callers do not rely on a negative step count being rejected.

**Goldens**: `ds08_dsolve.out`, `ds09_dsolve.out`, `ds10_dsolve.out`.

### LIMIT-3 — non-unique ODE solution silently selected
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
printf "y' = sqrt(y); y(0) = 0; dsolve y from 0 to 1\n" | $ROOT/ucas
```

**Observed:** returns `y(t) = 0` for all sampled `t` with no note that the
right-hand side is non-Lipschitz at `y = 0` and therefore admits infinitely
many solutions (the solution may leave zero at an arbitrary time).

**Why it matters:** it matters** A single solution is presented without warning; the
"numeric differs by 0" self-check cannot detect the missing family.

**Golden**: `ds15_dsolve.out`.

## Checks that passed

### Negative controls (behaviors verified correct / gracefully handled)
* Cyclic basis inheritance — `basis a : a`, 2-, 3-, 5-, 10-, 20-node cycles,
  unknown parents, redefinition cycles — does **not** hang or crash through
  `gates`, `cost` or `mca`; cycles are broken by a visited-set. Files `cb01`–`cb24`.
* Cyclic model inheritance — self, 2/3/5/10-node cycles, `use` cycles — does
  not hang or crash through `cost`/`mca`/`use`. Files `cm01`–`cm15`.
* Caps are enforced gracefully (no crash): at most 24 bases / 24 gates / 24
  models (`error: too many bases/gates/models`), `gates` accepts at most 6
  input bits (`error: gates handles up to 6 input bits (8 here)`).
* `solve` handles inconsistent linear systems correctly
  (`solve x=1, x=2 for x` → rank-1 vs rank-2 inconsistency),
  correctly reports free unknowns, and correctly finds real + complex roots
  (`x^2+1=0` → "no real solution / (and 2 complex solutions)").
* `solve ... mod 0` and negative modulus produce a clean English error
  ("the modulus must be positive"); CRT systems are solved correctly.
* `dsolve` correctly rejects missing initial values, reversed intervals,
  `y'=y'`, non-constant initial values and missing equations.
* `zsolve` correctly rejects non-recurrences (`1=2`, `x=x`, `y[n]=y[n]` →
  "the highest order term vanishes") and division-by-zero coefficients.
* All 129 goldens were run twice and compared byte-for-byte: outputs are
  deterministic (no random witness/ordering/timing fields).
