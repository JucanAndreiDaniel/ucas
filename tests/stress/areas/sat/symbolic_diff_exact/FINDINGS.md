# Stress findings — `symbolic_diff_exact`

_Original heading: FINDINGS — `symbolic_diff_exact` stress area_

# FINDINGS — `symbolic_diff_exact` stress area

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `equiv` over `real` rejects every true identity (101/101), and the witness fails exact eva… |
| LIMIT | 1 | machine-type `equiv` disagreements are confined to division identities |

## Findings

### WRONG-1 — `equiv` over `real` rejects every true identity (101/101), and the witness fails exact evaluation
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Repro (CLI golden, all deterministic):
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/symbolic_diff_exact
$ROOT/ucas 01_equiv_real_true.ucas
```
Exact output (excerpt; full in `01_equiv_real_true.out`):
```
> equiv fA gA
fA and gA differ at 529504 points, e.g. x=-9.98, y=-10: 399.2 vs 399.2
> equiv fB gB
fB and gB differ at 738255 points, e.g. x=-9.98, y=-10: 2.55488e+06 vs 2.55488e+06
> equiv fC gC
fC and gC differ at 446257 points, e.g. x=-9.96, y=-10: -44.7984 vs -44.7984
> equiv fD gD
fD and gD differ at 453 points, e.g. x=-9.96: 35.5216 vs 35.5216
> equiv fE gE
fE and gE differ at 369 points, e.g. x=-9.96: 90.2416 vs 90.2416
```
MCP equivalent (`mcp_oracle.out`, id 1): `result.equal = false`,
`counterexample = "x=-9.98, y=-10: 399.2 vs 399.2"`, `mismatch_points = 529504`.

**Why it matters:** each `f`/`g` pair is the *same* polynomial / rational function;
the exact oracle and ucas's own `expand` both give `f - g = 0` (`02_exact_diff_expand.out`).
`equiv` on `real` returns `equal:false` for **all 101 true identities** in the
corpus (87 pure-polynomial identities + 14 rational identities valid on their
domain). It never once returns a false `equal:true` for any of the 141 near-misses.
The reported counterexample shown above prints the *identical number on both
sides*. Exact evaluation of the witness point confirms the verdict is fabricated:

| pair | reported point | exact f | exact g | exact f−g |
|---|---|---|---|---|
| `(x+y)²` vs `x²+2xy+y²` | x=−9.98, y=−10 | `998001/2500` | `998001/2500` | `0` |
| `(x+3y)⁴` vs full expansion | x=−9.98, y=−10 | `15968023992001/6250000` | `15968023992001/6250000` | `0` |
| `(x+0)²−(y−2)²` vs `(x−y+2)(x+y−2)` | x=−9.96, y=−10 | `−27999/625` | `−27999/625` | `0` |

The `real` type is documented as "real (math)"; a correct implementation either
recognises algebraic equality or, if it insists on sampled numeric comparison,
must not emit a "counterexample" whose two values are exactly equal. This is the
same root cause already seen in `prove_symbolic`, reproduced here at scale and
confirmed with an independent exact oracle. The 14 rational identities additionally
have removable singularities, so a not-equal verdict there could be defended on
totality grounds — but the printed witness still fails exact evaluation.

### WRONG-2 — counterexample values print identically even when they really differ (below-tolerance witness)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Repro (deterministic golden):
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/symbolic_diff_exact
$ROOT/ucas 05_counterexample_precision.ucas
```
Exact output:
```
> equiv fp gp
fp and gp differ at 1002001 points, e.g. x=-10, y=-10: 2.56e+06 vs 2.56e+06
> expand (x + 3 * y) ^ 4 - (...) + 1)
  = -1
```
**Why it matters:** here the verdict (`equal:false`) is **correct** — `expand` gives
`−1`. But at the reported witness point `x=−10, y=−10` the exact values are
`2560000` and `2560001`; the printed `2.56e+06 vs 2.56e+06` hides the difference
of 1. Six near-misses in the corpus have this shape (all high-degree binomial
expansions at large |x|,|y|). A user cannot reproduce or diagnose the claimed
difference from the witness, and any sampled differential test with a relative
tolerance would also miss it — exactly the "below-tolerance" blind spot. This is
distinct from finding 1 (there the verdict is wrong *and* the witness is equal;
here the verdict is right but the witness is uninformative).

### LIMIT-1 — machine-type `equiv` disagreements are confined to division identities
**Severity:** LIMIT
_Original classification: `LIMIT (domain caveat, not a soundness bug`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
On the **220 pure-polynomial pairs**, `equiv` on bounded `int in -4..4` agreed
with the exact oracle on **220/220**, and `equiv` on `i8` agreed on **219/220**.
The sole `i8` exception is `(x³−1)/(x−1) = x²+x+1`, which contains division.
All 9 bounded-`int` disagreements and 14 of 15 `i8` disagreements are the
division-containing "rational" family. Example (`oracle_report.json`, p164):
**Observed:**
**Reproducer:**
```sh
f = 1/x + 1/y ;  g = (x+y)/(x*y) ;  oracle = EQUAL (rational functions)
equiv over bounded int -> equal:false, e.g. truncated integer division is not
a ring homomorphism (1/2 + 1/3 = 0 but 5/6 = 0; other points differ).
```
`i8` additionally overflows (`x*x` at x=−128), so a rational identity can fail a
full-width integer type even where bounded int succeeds. These are legitimate
type-semantics differences, **not** WRONG verdicts. Importantly, across all
`242 × 3 = 726` `equiv` checks there were **zero** cases of ucas answering
`equal:true` for a pair the exact oracle refuted — no false-positive soundness
failure was found on any type.

## Checks that passed

### Scope and method
An oracle **independent of ucas's `equiv`** was built in Python with
`fractions.Fraction` (`exprlib.py`, `corpus.py`, `harness.py`, `shapes.py`). For
242 deterministic rational-function pairs (101 true identities, 141 near-misses)
it decides exact equality by evaluating `f - g` at up to 64 rational points;
a nonzero value at any point where both sides are defined refutes the identity
exactly, and all-zero over strictly more points than the polynomial degree proves
it. ucas `algebra expand`/`simplify` of the difference is used as a *second*,
independent cross-check (it agreed on all 242 pairs — see "Verified clean").

Every pair was queried over MCP (`ucas --mcp`) with `equiv` on `real`, on bounded
`int in -4..4`, and on `i8`, plus `expand`/`simplify` of the difference:
**1210 tool calls in 3 chunks**. All reproducers below were run twice and
`diff`ed byte-for-byte (all deterministic). No source file was modified; all
runs used `$ROOT/ucas` under `timeout 30`.

### Verified clean (no issue)
- **Exact oracle cross-validation:** ucas `expand` and `simplify` of `f − g`
  returned `0` for all 101 true identities and a nonzero constant for all 141
  near-misses — **0 disagreements** with the independent Fraction oracle across
  all 242 pairs. `simplify` correctly reported cancellation conditions (21 pairs,
  e.g. `x - 1 != 0`). This localises the bug to `equiv` on `real`, not to the
  algebra engine.
- **Shape reduction:** 217 canonical (rename-invariant) equivalence classes, all
  structurally verified; 25 engine queries were provably reusable across
  renamed variants; **0 classes** had inconsistent ucas verdicts. The swapped
  variant `(y+x)² = y²+2yx+x²` received the *same* wrong verdict and the *same*
  fabricated `399.2 vs 399.2` counterexample as the base (`04_shape_rename.out`),
  confirming the defect is shape-invariant ( renaming x↔y is a verified bijection
  that must preserve the verdict).
- **No CRASH, no HANG, no DETERMINISM issue** in any of the 1210 MCP calls or the
  golden runs. All seven golden files are byte-identical across two runs.

### Files
- Harness: `exprlib.py`, `corpus.py`, `shapes.py`, `harness.py`, `run.sh`.
- Generated data (not goldens): `_scratch/oracle_report.json`,
  `_scratch/mismatches.md`, `_scratch/shape_report.json`.
- CLI goldens: `01_equiv_real_true`, `02_exact_diff_expand`, `03_near_miss_control`,
  `04_shape_rename`, `05_counterexample_precision` (`.ucas` + `.out`).
- MCP golden: `mcp_oracle.jsonl` + `mcp_oracle.out`.
