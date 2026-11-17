# Stress findings — `precision_controls`

_Original heading: precision_controls — findings_

# precision_controls — findings

Area: exact vs numeric precision controls (`int`/`real`/`f16`/`f32`/`f64`, exact rational vs
decimal display, exact/numeric/sampled/proved claims, high-digit constants, rounding flags,
`approx`/`error` tolerances, `table`-forced numeric evaluation).
Binary: `$ROOT/ucas`. All commands below were run from this folder under
`timeout 15`. Every golden in this folder was generated twice and `diff`ed (deterministic).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `expand` claims `check: exact` on a rounded-decimal result (false "same normal form over Q… |
| LIMIT | 2 | missing "printed rounded" disclaimer for high-digit constants and coefficients > 2^53 |

## Findings

### WRONG-1 — `expand` claims `check: exact` on a rounded-decimal result (false "same normal form over Q")
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/precision_controls
$ROOT/ucas -e 'expand 1/999999937*x' -e 'expand 2^60*x' -e 'expand 2/7'
```

**Observed:** output

```
  ucas: expand 1/999999937*x
expand 1.000000063e-09x
  = 1.000000063e-09x
  check: exact (both sides have the same normal form)
  ucas: expand 2^60*x
expand 1.152921505e+18x
  = 1.152921505e+18x
  check: exact (both sides have the same normal form)
  ucas: expand 2/7
expand 0.2857142857
  = 0.2857142857
  check: exact (both sides have the same normal form)
```

MCP (`mcp_precision.jsonl`, ids 7 and 8) makes the false claim explicit:

```json
"proof": {"kind": "symbolic", "text": "both sides have the same normal form over Q"},
"result": {"kind": "expand", "input": "1.000000063e-09x", "result": "1.000000063e-09x"}
```

**Why it matters:** it is a bug** — the exact normal form of `1/999999937*x` is `x/999999937`, that of
`2^60*x` is `1152921504606846976*x`, and `2/7` is the rational `2/7`. The printed results
`1.000000063e-09x`, `1.152921505e+18x`, `0.2857142857` are rounded decimals, not equal to
the inputs over Q. `check: exact` / `proof.kind:"symbolic" ... "same normal form over Q"` is
therefore a false exactness claim on a rounded result. Note that the *same* engine prints
`x/999999937` and `x/7` correctly when the rational is a coefficient of a polynomial
(`expand x/999999937`, `expand 2*x/7 + 1/7`), so this is a display/claim inconsistency.
The README ("Printing stays exact: x^3/3, 1/(2(x + 1)) ...") promises exact rational output.

Golden reproducer: `05_high_digit_constants.ucas`, `04_exact_rational_display.ucas`.

### WRONG-2 — high-digit decimal silently snapped to `1/3`; `solve` reports `exact: true` / `residual 0`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/precision_controls
$ROOT/ucas -e 'solve 0.3333333333333333*x = 1 for x' \
                            -e 'solve 0.33333333333333*x = 1 for x'
```

**Observed:** output

```
  ucas: solve 0.3333333333333333*x = 1 for x
solve 0.3333333333333333*x = 1 for x
  x = 3
  check: each solution substituted (1 value): residual 0
  ucas: solve 0.33333333333333*x = 1 for x
solve 0.33333333333333*x = 1 for x
  x = 3
  check: each solution substituted (1 value): residual 1e-14
```

MCP (`mcp_precision.jsonl`, ids 9 and 10) returns
`"solutions":[{"x":"3","value":3,"exact":true,...}]` for the 16-digit coefficient but reports a
nonzero residual for the 14-digit one.

**Why it matters:** it is a bug** — `0.3333333333333333 * 3 = 0.9999999999999999` (exact decimal arithmetic),
so `x = 3` does **not** solve the equation as written; the true residual is `1e-16`. ucas
internally converts the 16-digit decimal to the `double` nearest `1/3` and then recognises that
double as the exact rational `1/3`, so its substitution check is done against a *different*
coefficient than the one the user wrote. The 14-digit version is handled honestly
(`residual 1e-14`), so the jump to `residual 0`/`exact: true` at 16 digits is a false exactness
claim caused by the constant-snapping rule, with no note telling the user the constant was
changed. Same class: `show 0.3333333333333333*3` prints `1`, not `0.9999999999999999`.

Golden reproducer: `06_claims_exact.ucas` (last two statements), `mcp_precision.jsonl` ids 9–10.

### LIMIT-1 — missing "printed rounded" disclaimer for high-digit constants and coefficients > 2^53
**Severity:** LIMIT
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/precision_controls
$ROOT/ucas -e 'show 0.1234567890123456789012345' -e 'expand 2^60*x'
```

**Observed:** output

```
_() = 0.123456789
  -> real
  ucas: expand 2^60*x
expand 1.152921505e+18x
  = 1.152921505e+18x
  check: exact (both sides have the same normal form)
```

**Why it matters:** it is a bug / what was expected** — the README states: "coefficients beyond 2^53 cannot
be represented in an expression and are printed rounded, with a note." Neither output has that
note. `src/alg.c:575` suppresses the note when `exact_same(in, out)` is true — which is exactly
the case when the input itself already contained the big coefficient (`2^60`), so the warning
never appears where it matters most. `show` truncates a 25-digit literal to 10 significant
digits with no note either.
**Expected:** a `note:` line announcing that the displayed value is
rounded, or exact rational output (`1152921504606846976*x`).

Golden reproducer: `05_high_digit_constants.ucas`, `mcp_precision.jsonl` id 12.

### LIMIT-2 — rounding-control flags silently accepted where they cannot apply, and conflicting flags silently combined
**Severity:** LIMIT
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/precision_controls
$ROOT/ucas -e 'a(x: real in 0..1)=x+1' -e 'b(x: real in 0..1)=1+x' \
  -e 'equiv a b ftz' -e 'equiv a b ftz noftz' \
  -e 'f(x: f32 in 0..1)=x+1' -e 'g(x: f32 in 0..1)=1+x' -e 'equiv f g ftz noftz'
```

**Observed:** output

```
a and b are equal on the domain of a (exhaustive)
a and b are equal on the domain of a (exhaustive)
f and g are equal on the domain of f (proved by SAT: 6627 AIG nodes, 0 conflicts)
```

**Why it matters:** it is a LIMIT** — `ftz` is given to `real`-typed functions (no float operation exists to
flush), and both `ftz` and `noftz` are supplied at once; in all cases the flags are silently
ignored or one silently wins, with no `note:` and no error. By contrast MCP refuses an
`equiv` of float formulas unless **both** `ftz` and `nanbits` are provided
(verified separately: error `"ftz" is missing ...` / `"nanbits" is missing ...`).
**Expected:** CLI should note that `ftz` does not apply to a
float-free function and reject or warn on the contradictory pair.

## Checks that passed

### Coverage / clean checks
* ~170 distinct `-e` statements/queries were tried across 12 probe batches plus 9 CLI golden
  files (122 statements) and 12 MCP calls. No crash, hang, or nondeterminism was observed in
  any case that was kept as a golden. `approx` was exercised (tolerances `error 0`, `error -1`,
  `ulp 0`, `ulp -1`, `error inf`, `error 1e400`, `error 1e-30`, `error nan`) but is deliberately
  **not** kept as a golden: repeated runs differ (search/timing), per the suite rules.
* "sampled" disclaimers were present on every sampled result checked: `range` of f32/f64
  ("sampled 65536 points ...; not exhaustive"), real grids ("grid of 20001 points ..."),
  `equiv` float powers ("sampled, not proved; no SAT proof: a float power"), `approx`
  ("candidates ranked ... (sampled floats); measured on 130809 f32"), and `error` ("over
  65536 points"). `table` forced numeric evaluation of `exp(1)`, `pi^2`, `sqrt(2)`, `W(2)`
  where `show` stayed symbolic, as expected.
* Type evaluation across `int`/`real`/`f16`/`f32`/`f64` differed only where rounding/truncation
  is expected (`x/3`, `1/x`, `x*0.1`, casts at 2^24/2^53/65504). No cross-type inconsistency
  beyond the constant-snapping issue in finding 2 was found.
