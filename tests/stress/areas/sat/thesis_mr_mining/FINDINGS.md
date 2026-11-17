# Stress findings — `thesis_mr_mining`

_Original heading: FINDINGS — `thesis_mr_mining`_

# FINDINGS — `thesis_mr_mining`

Area: MR-Scout / MR-Coupler / functional coupling / proof-kernel mutation.
All commands below were run from this directory with
`timeout 30 $ROOT/ucas <file>.ucas`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | `proof T` and `axioms T` disagree on the axiom set — `proof` prints an incomplete list |
| LIMIT | 2 | `equiv` is asymmetric when the two functions have different domains |

## Findings

### WRONG-1 — `proof T` and `axioms T` disagree on the axiom set — `proof` prints an incomplete list
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):
```sh
cd $ROOT/tests/stress/areas/sat/thesis_mr_mining
$ROOT/ucas 400_proof_axiom_mismatch.ucas
```
**Reproducer:**
Reproducer (MCP golden, ids 5–6):
```sh
cd $ROOT/tests/stress/areas/sat/thesis_mr_mining
$ROOT/ucas --mcp < mcp_proof_mutation.jsonl > /dev/null
# see mcp_proof_mutation.out, ids 5 (axioms) and 6 (proof)
```

**Observed:** output (relevant part):
```
> proof t_ab
t_ab: forall x y:el: 2*(x + y) - x = x + 2*y
route a: t_ab
  rests on:
    t_ab  (5 inferences)
axioms used:
> axioms t_ab
the axioms t_ab rests on (every route):
int_discrete   [integer arithmetic] forall n:int: n <= 0 or 1 <= n
ipow_zero      [definition] forall c:cpl, x:el: ipow(c,0,x) = x
ipow_succ      [definition] forall c:cpl, m:int, x:el: ipow(c,m+1,x) = i(c,ipow(c,m,x))
ipow_neg       [definition] forall c:cpl, m:int, x:el: m < 0 -> ipow(c,m,x) = 0
```

**Why it matters:** `proof T` ends with an empty `axioms used:` section while `axioms T`
reports four axioms for the very same theorem, in the same session. The task explicitly
asks that "`proof` prints a complete axiom list"; here it prints none. The `ipow_*`
axioms (iterates of the map `i` of an exact couple) cannot possibly be needed for an
abelian-group identity `2*(x+y)-x = x+2*y`, so the extra axioms reported by `axioms`
are spurious. The source confirms the asymmetry: `deps_of()` in `prove_cmd.c` filters
conversion homomorphism theorems with `uses_sym(...)`, but `used_axioms()` (used by
`axioms`) walks *every* declared homomorphism's theorem with `h < th` and no
`uses_sym` filter — it over-approximates the dependency set. Either way one of the two
commands misreports the axiom dependency set, so a proof audit cannot rely on them.

Also observed on library-proved theorems, e.g. `t1` (`forall p z:int: 2<=p and 1=p*z -> false`):
`proof t1` lists `int_discrete mul_nonneg` (2 axioms) while `axioms t1` lists 5
(adds `ipow_zero ipow_succ ipow_neg`). See `t_true_unit.out`.

### WRONG-2 — `domain` prints "no conditions: total on its parameter types" while reporting 0 defined points
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/thesis_mr_mining
$ROOT/ucas 401_domain_total_contradiction.ucas
```

**Observed:** output:
```
domain of f:
  x: u16, 0..65535
  no conditions: total on its parameter types
  defined at 0 of 65536 points
  undefined e.g. at x=0; x=1; x=2; x=3
  C undefined behaviour at 65536 points, e.g. x=0
```

**Why it matters:** The header asserts the function is total *and* has no conditions,
but the very next lines say 0 of 65536 points are defined and all 65536 are C UB.
The same contradiction appears for `x >> 8` (u8), `x << 8` (u8), `x >> 16` (u16),
`x >> 32` (u32) — i.e. constant shift counts ≥ the type width. The condition
extractor fails to emit a symbolic condition for a *constant* UB, so the header falls
back to "total" while the exhaustive evaluator correctly finds UB everywhere.
See `000_db.out`–`003_db.out`, `007_db.out`.

### WRONG-3 — `wrap` contradicts `range` on everywhere-undefined functions; dangling `e.g.`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/thesis_mr_mining
$ROOT/ucas 402_wrap_range_contradiction.ucas
```

**Observed:** output:
```
> f(x: u8) = x/0
> range f
range of f -> u8:
  empty (undefined everywhere)
  undefined at 256 points
> wrap f
wrap analysis of f:
  no wrapping or rounding operations
  end to end: equals the mathematical (unbounded) result everywhere
> g(x: u8) = x >> 8
> range g
range of g -> u8:
  empty (undefined everywhere)
> wrap g
wrap analysis of g:
  no wrapping or rounding operations
  end to end: differs from the mathematical result at 0 points, e.g.
```

**Why it matters:** `range` reports "undefined everywhere" (0 defined points), but
`wrap` claims the expression "equals the mathematical result everywhere" — false for a
function that has no defined result. In the shift case `wrap` also emits a dangling
`e.g.` with an empty witness (`"at 0 points, e.g. \n"`) because a difference count of
zero still triggers the example printer. The dangling `e.g.` also appears for partially
undefined functions such as `isqrt(x-1)`, `1 << x`, `x >> x` (see `004_db.out`–`006_db.out`,
`012_db.out`). `wrap` should restrict its end-to-end claim to the defined domain, or
state that the result is undefined.

### LIMIT-1 — `equiv` is asymmetric when the two functions have different domains
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/thesis_mr_mining
$ROOT/ucas 403_equiv_domain_asymmetry.ucas
```

**Observed:** output:
```
f(x: u8) = x/x      (defined at 255 of 256 points)
g(x: u8) = 1        (total)
equiv f g  ->  f and g are equal on the domain of f (exhaustive)
equiv g f  ->  g and f differ at 1 point, e.g. x=0: 1 vs undefined
```

**Why it matters:** this matters (not counted as a bug):** the help text says the comparison is
"on the domain of f", so the asymmetry is by design. It is recorded because a
metamorphic oracle that assumes `equiv` is symmetric will produce false alarms when
the two sides have different UB sets. Any MR-Coupler over `equiv` must first align
domains (e.g. with `domain`) before applying the symmetry MR.

### LIMIT-2 — Proof automation is incomplete for some true theorems (no unsound acceptance found)
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Examples that are true but reported `NOT proved`:
**Observed:**
**Reproducer:**
```sh
t_true_discrete : forall n:int: n <= 0 or 1 <= n        (it is an axiom!)
t_true_ex       : forall x:int: exists y:int: y > x
t_false_even    : forall x:int: 2*x != 1 -> false       (vacuously true)
t_true_square2  : forall x:int: x*x >= 0
```
The need for a case split / non-linear reasoning is a known automation limit.
Importantly, across the 80 false/vacuously-true proof statements tried
(`f01.ucas`–`f40.ucas`, `t_*.ucas`), **no false theorem was accepted** and no case of
`prove` succeeding while the independent `check` re-checker failed was seen. The
mutation requirement therefore holds: a mutated false theorem gets `proved:false`
and `proof_check` returns a JSON error with `isError:true` and code `failed`
(see `mcp_proof_mutation.out`, ids 8–9).

## Checks that passed

### Notes on negative results (no issue found)
* 152 mined MR files (`NNN_mr_*.ucas`): applying 9 meaning-preserving rewrites
  (parentheses, `+0`, `*1`, `xor 0`, `& all-ones`, identity cast, `0+E`, `-0`, double
  parentheses) to both sides and to one side of corpus-mined equivalences never
  changed the `equiv` verdict. No crash, hang or nondeterminism.
* 80 functional-coupling files (`NNN_cpl_*.ucas`): single-point forced-difference
  witnesses always pointed at the intended input with `differ at 1 point`; transitive
  rewrite chains were all `EQ`; `range`/`domain` undefined counts agreed on all total
  and guarded cases. The only coupling oracles that "failed" were explained by
  findings 2–4 above (constant-shift UB, and my candidate-extraction regex, not a
  ucas bug).
* `gates isqrt4` claims minimal cost 5 with "no program of cost ≤ 4 exists";
  `gates isqrt4 max 4` correctly reports "an upper bound, not proved minimal" and
  `max 5` reports "minimal". No contradiction.

All 330 CLI goldens were generated from this directory and each was run twice and
`diff`ed before being kept; the MCP golden was likewise run twice and is byte-stable.
There were **no hangs, no nonzero exits, and no nondeterministic outputs** in this area.
