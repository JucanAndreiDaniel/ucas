# Stress findings — `prove_symbolic`

_Original heading: FINDINGS — `prove_symbolic` stress area_

# FINDINGS — `prove_symbolic` stress area

Scope: the `prove`/`theorem`/`proof`/`check`/`axioms` command and MCP `proofs`,
plus `equiv`, `calculus closed`, algebra `expand`/`simplify`, and MCP
`properties`/`identify`. All runs used the absolute binary
`$ROOT/ucas` under `timeout 30` (no longer). No source files
were modified. All reproducers below are committed as deterministic goldens in
this folder (each was run twice and `diff`ed — all matched).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | `equiv` over `real` rejects a true polynomial identity with an indistinguishable "countere… |
| NLP | 1 | documented MCP `equiv` on raw expressions fails to parse |
| LIMIT | 2 | large integer literals in theorem statements fail with a bare `error:` (no diagnostic) |

## Findings

### WRONG-1 — `equiv` over `real` rejects a true polynomial identity with an indistinguishable "counterexample"
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/prove_symbolic
$ROOT/ucas 08_equiv_identities.ucas
```
Exact output (excerpt):
```
> f(x: real, y: real) = (x+y)^2
> g(x: real, y: real) = x^2 + 2*x*y + y^2
> equiv f g
f and g differ at 529504 points, e.g. x=-9.98, y=-10: 399.2 vs 399.2
```
**Why it matters:** the two functions are the *same polynomial*, so they are equal
for every real input. `equiv` returns `equal:false`, `mismatch_points:529504`
(also in structuredContent), and the printed counterexample shows the *same*
value on both sides (`399.2 vs 399.2`) — the reported difference is only
last-bit floating-point noise from the two evaluation orders, and the display
rounds it away. This makes the verdict unusable and the counterexample
un-diagnosable. The very same identity over `i8` is correctly reported as
`equal ... (exhaustive)` in the same file; over `int` the true identity is
rejected at one point because of int64 overflow (`4 vs undefined`). The `real`
type is documented as "real (math)", so an algebraic-equality answer is
expected. (Related: the rational identity `(x^2-1)/(x-1)` vs `x+1` gives
`differ at 149 points, e.g. x=-8.98: -7.98 vs -7.98`, again identical display.)

### WRONG-2 — `identify` classifies the identically-zero bivariate polynomial as degree (1,1)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/prove_symbolic
$ROOT/ucas 09_identify_zero.ucas
```
Exact output (excerpt):
```
> identify (x+y)^2 - (x^2 + 2*x*y + y^2)
identify (x+y)^2 - (x^2 + 2*x*y + y^2):
  a function of 2 variables: polynomial, degree 1 in x, degree 1 in y
symmetry of (x + y)^2 - (x^2 + 2x*y + y^2):
  f(x, y) = f(y, x): yes (symmetric)
  f(x, y) = -f(y, x): yes (antisymmetric)
  checked numerically at 400 random points of [-10, 10]^2
```
**Why it matters:** the expression simplifies to `0`, a degree-0 constant. The
one-variable analogues in the same file are correctly identified as
`polynomial of degree 0 (constant), leading coefficient 0`, so the numeric
fit used on the 2-variable path is being polluted by floating-point noise and
produces a wrong degree and wrong structural classification. (It also calls
the function both symmetric and antisymmetric — individually true for 0, but
incoherent next to "degree 1".)

### WRONG-3 — `axioms NAME` reports axioms that `proof NAME`'s "axioms used" omits (proof-tree axiom mismatch)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/prove_symbolic
$ROOT/ucas --mcp < mcp_axioms.jsonl
```
Exact output (ids 3 and 4):
```
id 3  proof unit:
  rests on:
    unit_p  (29 inferences; axioms: int_discrete mul_nonneg)
axioms used:
  int_discrete   [integer arithmetic] forall n:int: n <= 0 or 1 <= n
  mul_nonneg     [integer arithmetic] forall a b:int: 0 <= a and 0 <= b -> 0 <= a*b

id 4  axioms unit:
the axioms unit rests on (every route):
int_discrete   [integer arithmetic] forall n:int: n <= 0 or 1 <= n
mul_nonneg     [integer arithmetic] forall a b:int: 0 <= a and 0 <= b -> 0 <= a*b
ipow_zero      [definition] forall c:cpl, x:el: ipow(c,0,x) = x
ipow_succ      [definition] forall c:cpl, m:int, x:el: 0 <= m -> ipow(c,m+1,x) = i(c,ipow(c,m,x))
ipow_neg       [definition] forall c:cpl, m:int, x:el: m < 0 -> ipow(c,m,x) = 0
```
**Why it matters:** the theorem is `all p z:int: 2<=p and 1=p*z -> false`; its
proof uses only the two integer-arithmetic axioms. `ipow_*` are exact-couple
definitions and cannot occur in this proof. The two commands that are supposed
to report the axioms a proof rests on disagree by three axioms. Any consumer
that reconstructs the proof's axiom set from `axioms NAME` gets a tree with
extra/missing axioms — directly relevant to "proof trees with missing
axioms". For the large `bockstein` proof the two lists do agree, so the
over-reporting is specific to small proofs that do not touch those definitions.

### LIMIT-1 — large integer literals in theorem statements fail with a bare `error:` (no diagnostic)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/prove_symbolic
$ROOT/ucas 06_overflow.ucas
```
Exact output:
```
> theorem o04: forall x:int: 9223372036854775800 > x
06_overflow.ucas:10:9: error: 
    theorem o04: forall x:int: 9223372036854775800 > x
            ^
```
**Why it matters:** the error message is empty. A binary search shows the first
rejected literal is `9223372036854775800` (= 2^63 − 8) while
`9000000000000000000` parses fine; the limit is undocumented and the failure
gives no explanation. (By contrast, an int64 overflow *during* a proof is
reported clearly: `integer overflow in a proof (coefficients beyond 64 bits)`
for the false claim `o03`. That refusal is correct — it does not accept the
false identity.)

### LIMIT-2 — automation rejects many true claims (nonlinear, existential, divisibility, even an axiom instance)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/prove_symbolic
$ROOT/ucas 05_automation_limits.ucas
```
Exact output (all ten theorems report `NOT proved`, e.g.):
```
> theorem l01: forall x:int: 0 <= x*x
l01: NOT proved
  automation: could not prove forall x:int: 0 <= x*x
  no counterexample among the standard spaces (...), p, n, r <= 4
> theorem l05: forall n:int: n <= 0 or 1 <= n
l05: NOT proved
  automation: could not prove forall n:int: n <= 0 or 1 <= n
  no counterexample among the standard spaces (...)
```
**Why it matters:** the documented automation is linear-only, but the rejected set
includes genuinely trivial true statements — `0 <= x*x` (the `mul_nonneg`
axiom with a=b), `exists y:int: y = x+1`, parity/evenness via `exists k`, and
`n <= 0 or 1 <= n`, which is *literally the `int_discrete` axiom*. So the
automation does not consult the axiom database for direct matches, and the
"no counterexample" message can be mistaken for a disproof. False
abelian-group equalities (`forall x y:el: x+y=x`) are likewise `NOT proved`
with "no counterexample" despite being false in any nontrivial group. These
are completeness/limits, not unsoundness.

### NLP-1 — documented MCP `equiv` on raw expressions fails to parse
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Repro (golden `mcp_equiv.jsonl`, id 1):
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/prove_symbolic
$ROOT/ucas --mcp < mcp_equiv.jsonl
```
Exact output:
```
id=1 isError=true: error (parse_error): expected an expression
<json>:1:22: error: expected an expression
    equiv (x*y)^5 (y*x)^5
                         ^
```
**Why it matters:** this is an example MCP `equiv` call. The call fails; the
second expression argument is rejected.
`equiv` only works over *defined function names* (the same file defines `f8`,
`g8` and then `equiv f8 g8` succeeds, exhaustive). Defining a function named
`qr` also trips an ambiguity (`'qr' read as q*r (single-letter variables)`),
so short function names need care. Documentation/frontend mismatch.

### WRONG-4 — numeric `identify` of the zero trig identity reports fabricated properties
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Repro (golden `mcp_properties.jsonl`, id 6):
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/prove_symbolic
$ROOT/ucas --mcp < mcp_properties.jsonl
```
Exact output (excerpt):
```
identify sin(x)^2 + cos(x)^2 - 1:
  transcendental: trigonometric
  periodic: yes, period pi/32 ≈ 0.09817477042 [numeric]
  monotonic: not monotonic (6042 intervals of monotonicity) [numeric]
  zeros: 15884 (-10, -9.999, ...) [numeric]
  values on [-10, 10]: from -2.220446049e-16 to 2.220446049e-16 [numeric]
```
**Why it matters:** `sin^2+cos^2-1` is identically zero, so it is constant,
non-strictly monotonic, periodic with every period, and zero everywhere. The
numeric-only classification turns FP round-off into a fake "period pi/32",
"6042 monotonicity intervals" and "15884 zeros". No claims are tagged `proved`;
they are `[numeric]`, but they are presented as facts about the function.

## Checks that passed

### Soundness checks that PASSED (no issue)
- 120 generated linear-arithmetic implication theorems (bulk golden
  `11_fuzz_linear.ucas`, ground truth by brute force over `[-40,40]^2`): the
  5 valid implications were all `proved` and all 115 invalid ones were
  correctly `NOT proved`. No false theorem was accepted.
- Polynomial identities proved through the kernel `conv` path
  (`03_polynomial_identities.ucas`): all 7 true identities proved, all 5 false
  ones rejected with counterexamples. `proof_check` re-checked every proved
  theorem ok.
- Recurrence closed forms (`07_recurrences.ucas`, `mcp_calculus.jsonl`): sums
  of i, i^2, i^3, geometric sums and `x[k+1]=2x[k]` are solved and checked by
  direct iteration; the geometric closed form correctly flags its own int64
  domain loss at `n=62`.
- **No CRASH, no HANG and no truncated/non-JSON MCP response was observed.**
  Malformed theorem statements (unknown sort/name, missing term, bad `using`,
  `proof`/`check` of unproved theorems), `x^100000`, 26-variable equalities,
  and int64-overflow attempts all returned clean errors or results well within
  `timeout 30`.
