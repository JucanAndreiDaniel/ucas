# Stress findings — `proof_kernel_axioms`

_Original heading: FINDINGS — LCF proof-kernel axiom accounting (area `proof_kernel_axioms`)_

# FINDINGS — LCF proof-kernel axiom accounting (area `proof_kernel_axioms`)

All runs use the built binary `$ROOT/ucas`, bounded by
`timeout 15` (goldens regenerated with `timeout 30` per `SPEC.md`).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | `axioms NAME` lists axioms the proof does not use (WRONG) |
| NLP | 1 | Hyphen in a theorem name is parsed as subtraction (NLP / LIMIT) |
| LIMIT | 1 | User theorem may shadow an axiom name (LIMIT) |

## Findings

### WRONG-1 — `axioms NAME` lists axioms the proof does not use (WRONG)
**Severity:** WRONG
**Expected:** _not recorded_
`axioms NAME` over-reports).

Cross-checking `proof NAME`'s **"axioms used:"** list against `axioms NAME`
for 156 generated theorems shows a systematic, one-directional disagreement:

* `axioms NAME` reports a superset, always adding `ipow_zero`, `ipow_succ`,
  `ipow_neg` (and often `int_discrete`) for any proof that contains a kernel
  `conv` step, even when the homomorphism `i` never occurs in the statement.
* `proof NAME` reports the accurate set: for a pure reflexivity or abelian-group
  equality it correctly says "axioms used:" with **no** axioms.

Worst case: `forall x:int: x = x` is proved by `refl`-style conversion with no
axioms, yet `axioms NAME` claims it rests on four axioms.

**Reproducer:**
Reproducer (CLI)** — copy-pasteable from this folder:

```sh
cd $ROOT/tests/stress/areas/sat/proof_kernel_axioms
timeout 15 $ROOT/ucas 01_axiom_overreport.ucas
```

**Observed:** output** (excerpt; full output in `01_axiom_overreport.out`):

```
> theorem g01: forall x:int: x = x
theorem g01: forall x:int: x = x
> prove g01
g01: proved automatically (4 kernel inferences); independent re-check: ok
> proof g01
g01: forall x:int: x = x
route a: g01
  rests on:
    g01  (4 inferences)
axioms used:
> axioms g01
the axioms g01 rests on (every route):
int_discrete   [integer arithmetic] forall n:int: n <= 0 or 1 <= n
ipow_zero      [definition] forall c:cpl, x:el: ipow(c,0,x) = x
ipow_succ      [definition] forall c:cpl, m:int, x:el: 0 <= m -> ipow(c,m+1,x) = i(c,ipow(c,m,x))
ipow_neg       [definition] forall c:cpl, m:int, x:el: m < 0 -> ipow(c,m,x) = 0
```

**Reproducer:**
Reproducer (MCP, same discrepancy in `structuredContent.result.axioms`)**:

```sh
cd $ROOT/tests/stress/areas/sat/proof_kernel_axioms
timeout 15 $ROOT/ucas --mcp < mcp_axiom_accounting.jsonl
```

**Observed:** output** (fields from `mcp_axiom_accounting.out`):

```
id 3  cmd proof   result.axioms = []
id 4  cmd axioms  result.axioms = [int_discrete, ipow_zero, ipow_succ, ipow_neg]
id 5  cmd proof_check  result = {"kind":"check","name":"ma1","ok":true,"inferences":123}
```

Also reproduced directly through the Code Mode MCP tool `tools.ucas.proofs`:
`proof(mcpv).result.axioms = []` while
`axioms(mcpv).result.axioms = [int_discrete, ipow_zero, ipow_succ, ipow_neg]`.

**Other concrete instances** (all deterministic):

| theorem | `proof` axioms used | `axioms NAME` | extra listed |
|---|---|---|---|
| `forall x y:el: 2*(x+y)-x = x+2*y` | (none) | int_discrete, ipow_zero, ipow_succ, ipow_neg | all four |
| `forall x y:int: x<=y and y<=x -> x=y` | int_discrete, le_antisym | + ipow_zero, ipow_succ, ipow_neg | three |
| `forall S:set,x:el: subgroup(S) and x in S -> -x in S` | subgroup_def | subgroup_def | (agrees — no conv) |

**Why it matters:** it is a bug / expected:** the two public axiom-accounting views of the
same proved theorem disagree, so a consumer cannot trust `axioms NAME` as the
set of assumptions a proof depends on. The narrower `proof` set is the correct
one. Source cause (do not edit): `used_axioms()` in `src/prove_cmd.c` adds
*every* declared homomorphism theorem for any `KR_CONV` node unconditionally,
while `deps_of()` (used by `proof`) filters hom theorems with `uses_sym()` so
only a hom symbol actually present in the conclusion is included. `ipow_*` are
the hom-declaration axioms for `i`; their premises pull in `int_discrete`, which
is why that axiom is over-reported too.
Note the reverse error (`proof` listing an axiom that `axioms` omits) was **not**
found in 156 theorems, and `proof` is internally consistent: for six large
library proofs the per-node inline `axioms:` annotations exactly equal the final
"axioms used:" set.

### LIMIT-1 — User theorem may shadow an axiom name (LIMIT)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf 'theorem int_discrete: forall x:int: x = x\nprove int_discrete\naxioms int_discrete\n' | timeout 15 ./ucas
```

**Observed:** output:

```
theorem int_discrete: forall x:int: x = x
int_discrete: proved automatically (4 kernel inferences); independent re-check: ok
the axioms int_discrete rests on (every route):
int_discrete   [integer arithmetic] forall n:int: n <= 0 or 1 <= n
ipow_zero      [definition] ...
```

**Why it matters:** it is a bug / expected:** `theorem ec_subD: ...` is correctly rejected
("ec_subD is a library lemma; choose another name") but axiom names are not in
that protected set. A user can define a theorem called `int_discrete`; the
`axioms int_discrete` lookup then resolves to the user theorem and prints a list
in which the built-in axiom `int_discrete` appears as a dependency of the user
theorem of the same name — confusing and easy to misread.

### NLP-1 — Hyphen in a theorem name is parsed as subtraction (NLP / LIMIT)
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf 'theorem e-dash: forall x:int: x = x\nprove e-dash\n' | timeout 15 ./ucas
```

**Observed:** output (deterministic across repeated runs):

```
theorem e: forall x:int: x = x
  sorry: ucas can't prove yet: it measures functions
```

**Why it matters:** it is a bug / expected:** `theorem e-dash: ...` silently creates a theorem
named `e` (the `-dash` is consumed as an expression), and `prove e-dash` is then
routed to the general expression/function-measuring frontend instead of the
proof kernel. No error warns that the intended name was not used.

## Checks that passed

### Negative results (checked, no issue found)
* **No crash / no hang:** all 156 generated sequences, 26 adversarial edge
  cases (empty statement, missing name, unknown sort/symbol, free variable,
  colliding names, huge coefficients/powers, 200-term sums, 40 nested
  quantifiers, huge multiplication, malformed ops) and MCP JSONL sessions
  exited 0 within `timeout 15`.
* **No proof_check disagreement:** every `prove` line claiming
  "independent re-check: ok" was matched by a successful `proof_check`
  (`N inferences re-checked`); none printed `FAILED`.
* **No unsoundness found:** deliberately false claims (`x = x+1`,
  `x*x >= x+1`, `3*(x+y)-x = x+3*y`) were all rejected as NOT proved; true
  contradictions (`2<=x and 1=3*x -> false`) were accepted. No false statement
  was accepted as a kernel theorem.
* **Determinism:** every golden in this folder was generated twice and the two
  outputs diffed identical (both CLI and MCP).
