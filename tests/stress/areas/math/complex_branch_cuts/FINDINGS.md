# Stress findings — `complex_branch_cuts`

_Original heading: FINDINGS — `complex_branch_cuts`_

# FINDINGS — `complex_branch_cuts`

Stress area: branch-cut / multi-valued-function consistency (`complex`, `properties`, `calculus` tools, CLI + MCP).
All listed reproducers were run with `timeout 30 $ROOT/ucas ...`. Every golden in this
folder was run **twice and diffed**: all are byte-for-byte deterministic. No crashes, hangs, or
nondeterministic cases were found in this area.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | 1 — `complex z^(p/q)` on a negative base reports a wrong (self-contradictory) Re/Im decomp… |
| NLP | 2 | 1 — "principal value of log(-1)" is misrouted to `arg log(-1)` (π/2) instead of log(-1) (π… |
| LIMIT | 3 | 1 — one-sided limits at a branch cut are impossible for complex-default variable names (`z… |

## Findings

### WRONG-1 — 1 — `complex z^(p/q)` on a negative base reports a wrong (self-contradictory) Re/Im decomposition, and its numeric check passes
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas 02_powers_roots.ucas | sed -n '/> complex (-1)^(1\/3)/,+3p'
# or, on the wire:
$ROOT/ucas --mcp < mcp_wrong_decomp.jsonl
```

**Observed:** output (CLI):
```
> complex (-1)^(1/3)
(-1)^(1/3) = (-1)^(1/3)
  Re = (-1)^(1/3),  Im = 0
  check: equal numerically (0.5 + 0.8660254038i, complex arithmetic)
```
MCP `complex` with `f="(-1)^(1/2)"` returns `structuredContent.result =
{"kind":"complex","input":"(-1)^(1/2)","result":"(-1)^(1/2)","re":"(-1)^(1/2)","im":"0"}`
together with `checks:[{"kind":"value","points":1,"passed":true}]`.

**Why it matters:** the reported decomposition says `Im = 0`, i.e. the value is *real*, yet the
same output's numeric check evaluates to a strictly complex number (`0.5 + 0.866i` for the cube
root, `1i` for the square root), and `Re` is reported as the original complex expression itself.
`Re = (-1)^(1/3)` and `Im = 0` cannot both be right — `(-1)^(1/3) = 1/2 + i√3/2` is not real.
The numeric "check" is vacuous (it checks the whole expression against itself) and is marked
`passed: true`, so the wrong decomposition is presented as verified. Affects every negative real
base with a fractional exponent: `(-1)^(1/2)`, `(-1)^(1/3)`, `(-1)^(2/3)`, `(-1)^(1/4)`,
`(-1)^(3/4)`, `(-8)^(1/3)`, `(-2)^(1/2)`, `(-1.0)^(0.5)`. Positive/complex bases such as
`i^(1/2)` and `(1+i)^(1/2)` are expanded correctly, so the defect is specific to this case.

### WRONG-2 — 2 — `re(...)` / `im(...)` of negative-base rational powers print formulas that FAIL their own numeric checks
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas 08_wrong_power_decomp.ucas
```

**Observed:** output:
```
> re((-1)^(1/2))
Re(((-1)^(1/2))) = (-1)^(1/2)
  check: FAILED at 1 of 1 sample points,  vs 6.123233996e-17 (rewrite 1i)
> im((-1)^(1/2))
Im(((-1)^(1/2))) = 0
  check: FAILED at 1 of 1 sample points,  vs 1 (rewrite 0)
> re((-1)^(1/3))
Re(((-1)^(1/3))) = (-1)^(1/3)
  check: FAILED at 1 of 1 sample points,  vs 0.5 (rewrite 0.5 + 0.8660254038i)
```
MCP `complex`/`re` with `f="(-1)^(1/3)"` returns `ok: true` and
`checks:[{"passed":false}]` while still setting `result:"(-1)^(1/3)"`.

**Why it matters:** the tool emits a closed-form answer that it simultaneously reports as wrong
(the check's `vs` column shows the true value: `Re = 0.5`, `Im = 1`, etc.). Callers consuming the
`result`/`re`/`im` fields (not the `checks` array) get a value that is not the real/imaginary part.
`arg((-1)^(1/2))` is worse: it returns `atan2(0, (-1)^(1/2))` with a `FAILED` check and a `nan`
rewrite (`08_wrong_power_decomp.out`).

### WRONG-3 — 3 — `poles` completely misses poles of order ≥ 2
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas 06_poles_residue.ucas | sed -n '/> poles 1\/(z-1)\^2$/,+3p'
$ROOT/ucas --mcp < mcp_wrong_decomp.jsonl   # ids 6,7
```

**Observed:** output:
```
> poles 1/((z-1)^2*(z+2))
poles of 1/((z - 1)^2*(z + 2)):
    z = -2  order 1, residue 1/9        <-- order-2 pole at z=1 is MISSING
> poles 1/(z-1)^2
poles of 1/(z - 1)^2:
  none in |Re z|, |Im z| <= 7           <-- WRONG: z=1 is a double pole
> poles 1/(z-1)^3
poles of 1/(z - 1)^3:
  none in |Re z|, |Im z| <= 7           <-- WRONG: z=1 is a triple pole
> poles 1/(z^2-1)^2
poles of 1/(z^2 - 1)^2:
  none in |Re z|, |Im z| <= 7           <-- WRONG: z=+1,-1 are double poles
```
MCP `complex`/`poles` on `1/(z-1)^2` returns `structuredContent.result.poles = []`.

**Why it matters:** the pole finder reports "none" for functions with obvious higher-order poles,
and silently omits the double pole when a simple pole is also present. The Newton-based search on
`1/f` apparently cannot converge to multiple roots. By contrast the `residue` op *does* find and
correctly characterize these poles (`residue 1/((z-1)^2*(z+2)) at 1 = -0.1111111111`, "a pole of
order 2"), so the two tools disagree about the same function. This directly undermines residue /
pole-based reasoning around singularities.

### NLP-1 — 1 — "principal value of log(-1)" is misrouted to `arg log(-1)` (π/2) instead of log(-1) (πi)
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas 09_nlp_branch.ucas | sed -n '1,20p'
```

**Observed:** output:
```
> the principal value of log(-1)
  ucas: arg log(-1)
arg(log(-1)) = pi/2
  the principal argument, -pi < arg <= pi
  check: equal numerically (1.570796327, complex arithmetic)
> the principal value of sqrt(-1)
  ucas: arg sqrt(-1)
arg(sqrt(-1)) = pi/2
...
> the value of log(-1)                       <-- control: same query without "principal"
  ucas: log(-1)
  note: log(-1) is undefined in the reals; its complex principal value follows
  note: on the branch cut of log: the principal value, log z = log|z| + i arg z with -pi < arg z <= pi
pi*i
```

**Why it matters:** adding the word "principal" to "value of log(-1)" changes the routed command
from `log(-1)` to `arg(log(-1))`. The principal value of `log(-1)` is `πi`, not `π/2`. The parser
apparently binds "principal" to `arg` (from "principal argument"), ignoring "value". Every
"principal value of X" phrasing is misrouted this way.

### NLP-2 — 2 — "principal value of (-1)^(1/2)" routes to `arg ((-1)^(1/2))` producing a FAILED check and `nan`
**Severity:** NLP
_Original classification: `NLP / WRONG`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas 09_nlp_branch.ucas | sed -n '/principal value of (-1)/,+5p'
```

**Observed:** output:
```
> the principal value of (-1)^(1/2)
  ucas: arg (-1)^(1/2)
arg((-1)^(1/2)) = atan2(0, (-1)^(1/2))
  the principal argument, -pi < arg <= pi; undefined where (-1)^(1/2) = 0 = 0
  check: FAILED at 1 of 1 sample points,  vs 1.570796327 (rewrite nan)
```

**Why it matters:** same misroute as NLP-1, plus the resulting `arg` of the unevaluated symbolic
power yields a `FAILED` numeric check with a `nan` rewrite. The requested principal value of the
square root is `i`.

### LIMIT-1 — 1 — one-sided limits at a branch cut are impossible for complex-default variable names (`z`, `w`, `i`)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas 11_complex_side_limit_parse.ucas
$ROOT/ucas --mcp < mcp_props_calculus.jsonl   # ids 3,4
```

**Observed:** output (CLI):
```
> lim x->0+ x
limit of x as x -> 0+ (from the right):
  = 0
...
> lim z->0+ z
11_complex_side_limit_parse.ucas:1:3: error: expected an expression
    0+
      ^
> lim w->0+ w
... same "expected an expression" at 0+
> lim i->0+ i
... same "expected an expression" at 0+
```
MCP `calculus`/`limit` with `side:"+"` (or `"-"`) and `assume.z="complex"` builds
`limit log(z) as z -> (-1)+` and returns `error parse_error: expected an expression` at `(-1)+`.

**Why it matters:** it is a limitation:** ucas assumes `z`/`w` are complex variables and `i` is the imaginary
unit, and the `VAR->a±` one-sided-limit grammar only accepts a real variable — but it fails with
a confusing "expected an expression" rather than a domain error. The `side` argument of the MCP
`calculus.limit` tool likewise cannot be used to approach a branch cut from above/below, so the
natural way to check continuity from both sides of a cut is unavailable. (The multi-directional
`limit log(z) z -> -1` does work and correctly reports "does not exist" with different values
above/below — see `07_limits_multivalued.out`.)

### LIMIT-2 — 2 — `properties.continuity` ignores `assume.z="complex"` and analyses the real line
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas --mcp < mcp_props_calculus.jsonl   # ids 5,6
```

**Observed:** output:
```
continuity of log(z):
  undefined on [-10, 0) (the ends located numerically)
  z = 0: end of the domain, f -> -inf from the right
  ... x has no range: searched [-10, 10]
continuity of sqrt(z):
  continuous wherever it is defined on [-10, 10] (and on all real x where defined)
  undefined on [-10, 0) (the ends located numerically)
```

**Why it matters:** it is a limitation:** despite `assume.z="complex"` (and in contrast to the `complex` and
`calculus` tools, which do honour it), `continuity` silently treats `z` as a real variable, prints
"x has no range", and searches `[-10,10]`. It cannot report continuity on `C` minus the branch cut,
so it is not usable for complex branch-cut continuity questions and can mislead a caller into a
real-only conclusion.

### LIMIT-3 — 3 — `complex atanh(1)` returns an unevaluated `log(0)` expression with no verified value
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/complex_branch_cuts
$ROOT/ucas 04_inverse_trig.ucas | sed -n '/> complex atanh(1)/,+4p'
```

**Observed:** output:
```
> complex atanh(1)
  note: atanh(1) is on the branch cut; the value is that of (log(1 + z) - log(1 - z))/2
atanh(1) = log(2)/2 - log(0)/2
  Re = log(2)/2 - log(0)/2,  Im = 0
  check: no sample point where both sides are defined
```

**Why it matters:** it is a limitation:** `atanh` has a pole at `z=1`; the tool writes it as `... - log(0)/2`
(`log 0 = -∞`) but leaves it symbolic and cannot check it. Documented as a limitation, not a wrong
finite value.

## Checks that passed

### Notes — verified-correct behaviour (not bugs)
* **Signed-zero / upper-lip convention is internally consistent.** ucas takes the negative real
  axis to belong to the *upper* lip: `arg(-1)`, `arg(-1+0.0i)` and `arg(-1-0.0i)` are all `pi`,
  and `sqrt(-1±0.0i) = i`. Points genuinely below the cut (`-1 - 1e-12 i`) give `arg = -pi`,
  `log = -i*pi`, `sqrt = -i`. This matches the advertised branch range `-pi < arg <= pi`.
  (C's `carg`/Python `cmath.phase` return `-pi` for `-1-0.0j`; ucas's choice is a different but
  self-consistent convention.)
* **Inverse trig uses the DLMF convention consistently** (`asin(2) = pi/2 - i log(2+√3)`,
  `acos(2) = +i log(2+√3)`), with `asin(z)+acos(z) = pi/2` holding; `atanh(2)`,
  `atanh(-2)`, `acosh(-2)` agree numerically with standard principal values.
* `nthroots` / `unity` return all roots with correct principal root labelling and verified checks;
  `residue` handles simple and higher-order poles correctly; `holomorphic` correctly flags
  `conj`, `sqrt`, `log` and non-integer powers as non-entire.
* `nthroots 0`, `unity 0`, `nthroots 65`, `nthroots -2` are rejected cleanly with
  "n must be in 1..64" (no crash).

### No crashes / hangs / nondeterminism found
Every one of the 11 CLI goldens and 3 MCP goldens in this folder was executed twice under
`timeout 30` and produced byte-identical output; all exited 0. The only nonzero-status MCP
results are the *intentional* `parse_error` findings LIMIT-1 (ids 3,4 of
`mcp_props_calculus.jsonl`), which are deterministic and kept as goldens.
