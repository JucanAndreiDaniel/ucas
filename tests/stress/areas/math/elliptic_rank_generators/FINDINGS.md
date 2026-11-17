# Stress findings — `elliptic_rank_generators`

_Original heading: FINDINGS — elliptic_rank_generators_

# FINDINGS — elliptic_rank_generators

Scope: `elliptic` (curves over Q) and `elliptic_ff` (finite fields) MCP tools / CLI `ec*`
commands. Over 1500 distinct queries were run, plus independent Python cross-checks of the
group law (589 Q ops, 374 F_p ops), Frobenius traces (212 (curve,p) pairs) and canonical
heights (36 relations). All goldens in this folder are deterministic and exit 0.

Notes on methodology:
- Group law over Q and F_p was re-implemented independently with `fractions.Fraction` /
  modular inverses; **all** add/mul/on/point-enumeration checks passed.
- a_p from the Q side matched p+1-#E(F_p) from the FF side for all 212 good-reduction pairs.
- Canonical height scaling h(nP) = n^2 h(P) held for 36 relations.
- BSD `#Sha_an` was within 1e-3 of an integer for 193/193 curves that reported it; the
  functional-equation mismatch was < 1e-5 in every case.
- Singular curves over Q are rejected with `ec: the curve is singular (discriminant 0)` and
  over F_p with `singular: 4a^3 + 27b^2 = 0 mod p (not an elliptic curve)` — both correct.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | Internal invariant errors in Tate's algorithm on valid nonsingular curves |
| LIMIT | 3 | Schoof not available on P-521 |

## Findings

### WRONG-1 — Internal invariant errors in Tate's algorithm on valid nonsingular curves
**Severity:** WRONG
**Expected:** _not recorded_
good curve). Not a crash: exit code 0, stable partial output.

**Reproducer:**
Reproducer (minimal, CLI):
```sh
cd $ROOT
timeout 30 ./ucas -e 'ec y^2 = x^3 - 12*x local'
```

**Observed:** output:
```
minimal model: y^2 = x^3 - 12*x
  from the given curve by [u, r, s, t] = [1, 0, 0, 0]
  minimal discriminant: 110592
<arg>:1:4: error: internal: -32 is not divisible by 64
    ec y^2 = x^3 - 12*x local
       ^
```

Other reproducers (same bug class, different internal divisibility checks):
```sh
timeout 30 ./ucas -e 'ec y^2 = x^3 - 108*x local'        # internal: -224 is not divisible by 64
timeout 30 ./ucas -e 'ec y^2 = x^3 - 115*x - 14 local'    # internal: 384 is not divisible by 256
timeout 30 ./ucas -e 'ec y^2 = x^3 - 120*x - 11 local'    # internal: -243 is not divisible by 729
timeout 30 ./ucas -e 'ec [-266,386,-238,218,111] local'   # internal: 20391397623387790261877823387520 is not divisible by 256
```
MCP reproducer: `tests/stress/areas/math/elliptic_rank_generators/mcp_errors.jsonl` ids 4 and 5.
CLI golden capturing five variants: `06_q_tate_internal_errors.ucas` / `.out`.

**Why it matters:** a bug:** The discriminant is nonzero in every case (e.g. 110592 for `-12*x`,
110539728 for `-120*x - 11`), so these are nonsingular elliptic curves. The invariants,
minimal model and minimal discriminant are all computed and printed successfully; the
failure is in Tate's algorithm at p=2 (`not divisible by 64` / `256` / `1024`) or p=3
(`not divisible by 729`). A `internal:` message denotes a violated internal invariant, not
a graceful domain error. The command should print the Kodaira symbol / c_p / conductor.
Affected surface is broad: an exhaustive scan of `y^2 = x^3 + A x + B` with
`A,B in [-120,120]` hit **615 failures out of 58074 nonsingular curves (~1%)**:
558 `/64`, 30 `/729`, 26 `/256`, 1 `/1024`. `op: on`, `op: points`, `op: rank` on the same
curves work; only the local/conductor path fails.

### WRONG-2 — negative scalar on an equation-specified F_p curve is absorbed into the modulus
**Severity:** WRONG
**Expected:** _not recorded_
modulus is returned.

**Reproducer:**
Reproducer (MCP):
```sh
cd $ROOT/tests/stress/areas/math/elliptic_rank_generators
timeout 30 $ROOT/ucas --mcp < mcp_errors.jsonl   # id 7
```

**Observed:** output (structuredContent.error):
```
{"code":"failed","message":"87 is not prime (curves over Z/n: ecm uses them; here the field must be F_p)","pos":{"line":1,"col":7}}
```
and the rendered command shows the misparse:
```
ecmul y^2 = x^3 + 2x + 3 mod 97 -10 (73, 83)
```

Direct CLI reproducer:
```sh
timeout 30 $ROOT/ucas -e 'ecmul y^2 = x^3 + 2x + 3 mod 97 -10 (73, 83)'
```

**Variants:** `k=-2` → `95 is not prime`; `k=-1`, `k=-5` →
`the modulus must be an odd prime of at most 576 bits`. Expected result for `k=-10` is `O`
(the point (73,83) has order 10 on this curve).

**Why it matters:** a bug:** The scalar string is concatenated after the curve's `... mod 97` text, so
the parser reads it as `mod 97 - 10` = `mod 87` (a new modulus). Parenthesising the scalar
(`k = "(-10)"`) works and gives the correct answer `O`, and named curves (`secp256k1`,
`P-256`) accept bare negative scalars — this is specific to equation-specified curves plus
an unparenthesised negative scalar. The tool should parse the scalar token independently of
the curve expression.

### LIMIT-1 — Schoof not available on P-521
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer:** `mcp_errors.jsonl` id 8, or
```sh
timeout 30 $ROOT/ucas -e 'ecorder P-521 using schoof'
```
**Observed:** `error (unsupported): schoof: p too large for the prime table`.
**Notes:** `ec_info P-521`, `ec_mul P-521 123456789 G`, and all 30 built-in vectors pass
and are deterministic. README already documents the missing SEA and the impracticality of
Schoof at 256+ bits, so this is a known limit rather than a defect; recorded for coverage.

### LIMIT-2 — automatic generator search can miss a rank-1 generator; large point-search bound is slow but bounded by `timeout_s`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
timeout 30 $ROOT/ucas -e 'ec y^2 = x^3 - 29'
timeout 30 $ROOT/ucas -e 'ec y^2 = x^3 - 29 points 100000'
```
**Observed:** the summary reports `analytic rank: 1` and `so the rank is 1`, but prints no
`generator:`, no `regulator:` and no BSD line (`rank_lo = 0`). With an explicit larger
search bound it finds the generator, e.g. `(3133/9, 175364/27)` with `points 100000` —
so the answer is not wrong, the default search bound is just too small. A very large bound
(`10000000`) does not finish in 30 s, which is expected for that sieve; the documented
`timeout_s` option works correctly when placed inside the request `args`
(`{"args":{"curve":...,"op":"points","args":"10000000","timeout_s":5}}` returns a clean
`{"code":"timeout","message":"timed out after 5 s; the state is unchanged"}` in 5 s).

### LIMIT-3 — `ec_mul` with a negative scalar displays the negated base point
**Severity:** LIMIT
_Original classification: `LIMIT (cosmetic`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
With a parenthesised negative scalar the *result* is correct, but the echoed `P:` is the
negation of the requested point:
**Observed:**
**Reproducer:**
```sh
timeout 30 $ROOT/ucas -e 'ecmul y^2 = x^3 + 2x + 3 mod 97 (-3) (73, 83)'
```
prints `-3 P = (29, 43)` (verified correct) but `P: (73, 14)` although (73,83) was passed;
(73,14) = -(73,83) mod 97. Independent Python check confirms `-3*(73,83) = (29,43)`.
Cosmetic only — recorded because it can mislead a reader inspecting the certificate.

## Checks that passed

_No separate passed checks were recorded in the original document._
