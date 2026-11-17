# Stress findings — `cas_tricky_corpus`

_Original heading: FINDINGS — `cas_tricky_corpus` (GEMM/cas-testing methodology, idea 3)_

# FINDINGS — `cas_tricky_corpus` (GEMM/cas-testing methodology, idea 3)

Area: a 200+ input corpus of *known-tricky CAS inputs* from the literature / textbook patterns,
with every relevant symbolic command (`limit`, `integrate`, `sum`, `product`, `simplify`,
`expand`, `factor`, `series`/`taylor`, `residue`, `converge`, `range`, `domain`, `equiv`)
run over them.  Goldens are in `NN_*.ucas` + `NN_*.out`; `mcp_wrong_checks.jsonl` captures the
same wrong answers in MCP structured form (note the `passed:false` check fields).

Independent oracle used throughout: `python3` with `mpmath` (high-precision `nsum`) and
`sympy` (`series`, exact sums).  Every "WRONG" below was double-checked with it.

No crashes or hangs were observed: all ~300 symbolic queries finished with exit 0 in < 130 ms.
Findings are unsoundness / capability gaps, not robustness failures.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | 1 (WRONG, high) — Dirichlet (oscillating) series declared divergent |
| LIMIT | 5 | 1 (LIMIT) — conditionally convergent integrals reported as "singular or divergent" |

## Findings

### WRONG-1 — 1 (WRONG, high) — Dirichlet (oscillating) series declared divergent
**Severity:** WRONG
_Original classification: `WRONG-1 (WRONG, high`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (copy-pasteable):
```sh
cd $ROOT/tests/stress/areas/math/cas_tricky_corpus
$ROOT/ucas 01_dirichlet_series.ucas
```
Minimal single statement: `sum(n,1,inf,sin(n)/n)` in a one-line `.ucas` file.

**Observed:** (exact):
```
> sum(n,1,inf,sin(n)/n)
sum(n, 1, inf, sin(n)/n)
  diverges: comparison with the p-series sum 1/n (a_n ~ C/n, p <= 1)
> converge sin(n)/n
sum(n, 1, inf, sin(n)/n)
  diverges: comparison with the p-series sum 1/n (a_n ~ C/n, p <= 1)
  partial sums: S_10 = 1.124518813, S_1000 = 1.070694154
```
The same verdict is given for `cos(n)/n`, `sin(n)/n^(1/2)`, `sin(2*n)/n`,
`(-1)^n*sin(n)/n` and `converge sin(n)/log(n)`.

**Why it matters:** it is wrong / proof.**  The absolute-convergence p-series test is applied to an
oscillating series.  The partial sums of `sin(n)` are bounded
(`∑_{k=1}^N e^{ik} = e^{i(N+1)/2} sin(N/2)/sin(1/2)`, modulus ≤ `1/|sin(1/2)| ≈ 2.08`),
and `1/n` decreases to 0, so **Dirichlet's test** gives convergence.  Exactly
`∑_{n≥1} sin(n x)/n = (π - x)/2` on `0 < x < 2π`; with `x = 1` the value is `(π-1)/2`.
Oracle (`mpmath.nsum`): `1.0707963267948966...`; sympy agrees.  ucas's *own* printed
`S_1000 = 1.070694154` is already converging to that value — internally contradictory.
Other exact values (all confirmed by mpmath, all mislabelled "diverges" by ucas):
`∑ cos(n)/n = -log(2 sin(1/2)) ≈ 0.0420195`, `∑ sin(n)/√n ≈ 1.0439821`,
`∑ sin(2n)/n = (π-2)/2 ≈ 0.5707963`, `∑(-1)^n sin(n)/n = -1/2`,
`∑ sin(n)/log n ≈ 0.6839138` (Dirichlet again).

`converge sin(n)/log(n)` is a second error in the same statement: it claims
`"nth-term test: a_n does not tend to 0 (a_1000000 = -0.02533)"`.  A single nonzero
sample is not the limit; in fact `a_n → 0` because `|sin n| ≤ 1` and `log n → ∞`.

### WRONG-2 — 2 (WRONG, high) — L'Hôpital applied to `floor`/`ceil` at infinity
**Severity:** WRONG
_Original classification: `WRONG-2 (WRONG, high`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/cas_tricky_corpus
$ROOT/ucas 02_floor_limits.ucas
```
Minimal: `limit floor(x)/x x -> inf`.

**Observed:** (exact):
```
limit of floor(x)/x as x -> inf:
  inf/inf: L'Hôpital: lim (0)/(1) = lim 0
  = 0
  numeric (x = 10*2^k, k = 0..21): 1, 1, 1, 1, 1, 1
    extrapolated (Richardson): 1 (estimated error 0): DISAGREES with 0
```
MCP (`mcp_wrong_checks.out`, id 1) reports `checks:[{"kind":"numeric_left","passed":false,...}]`.

**Why it matters:** it is wrong / proof.**  `floor` is not differentiable; differentiating it as `0`
is invalid, so L'Hôpital does not apply.  Write `{x} = x - floor(x) ∈ [0,1)`; then
`floor(x)/x = 1 - {x}/x → 1`.  ucas's own numeric check says `DISAGREES` (max_diff 1).
Family (all in `02_floor_limits.ucas`): `ceil(x)/x → 0` (true 1), `floor(2x)/x → 0`
(true 2), `floor(x^2)/x^2 → 0` (true 1), `floor(x)/x` at `-inf → 0` (true 1),
`(x-floor(x))/x → 1` (true: DNE, fractional part oscillates in `[0,1)`),
`(x-floor(x)) → -inf` (true: DNE).  Each carries the same L'Hôpital-on-a-step-function
error and an internal `DISAGREES`.

### WRONG-3 — 3 (WRONG, high) — wrong high-order Taylor coefficients, internal check fails
**Severity:** WRONG
_Original classification: `WRONG-3 (WRONG, high`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/cas_tricky_corpus
$ROOT/ucas 03_taylor_coeffs.ucas
```
Minimal: `taylor 1/(1+x^2) x at 0 order 8`.

**Observed:** (exact):
```
Maclaurin (Taylor at 0) series of 1/(x^2 + 1) at x = 0, through order 8:
  1/(x^2 + 1) = 1 - x^2 + x^4 - x^6 + 23x^8/7 + O(x^9)
  as x -> 0; coefficients c_k = f^(k)(0)/k!: 1 0 -1 0 1 0 -1 0 23/7
  check FAILED: Taylor-jet arithmetic gives coefficients differing by 0.696
  check: |f - P| = 2.3e-08 at x = 0 ± 1/10, ... (shrinks like h^8.0; expected >= 9)
```
MCP (id 3): `checks:[{"kind":"taylor_jet","max_diff":0.6956521739130435,"passed":false}]`.

**Why it matters:** it is wrong / proof.**  `1/(1+x^2) = ∑_{k≥0} (-1)^k x^{2k}`, so the `x^8` coefficient
is `+1`, not `23/7 ≈ 3.2857`; the `x^10` coefficient is `-1`, not `-5648/525`.
`sympy.series(1/(1+x**2), x, 0, 11)` gives `1 - x**2 + x**4 - x**6 + x**8 - x**10`.
Numeric refutation at `x = 0.1`: `1/(1.01) = 0.9900990099...`, ucas polynomial
`= 0.9901226...`, difference `2.3e-8 = (23/7 - 1)·10^-8` — exactly the reported error,
and the error decays like `h^8` instead of the expected `h^9`.
Family: `1/(1+x^2)` order 10 (`23/7`, `-5648/525` wrong), `1/(1+x^3)` order 9
(`-40/21 x^9`, should be `-x^9`), `1/(2+x^2)` order 8 (`23x^8/224`, should be `x^8/32`).
Orders 4 and 6 are correct; the recurrence breaks at order ≥ 8.

### LIMIT-1 — 1 (LIMIT) — conditionally convergent integrals reported as "singular or divergent"
**Severity:** LIMIT
_Original classification: `LIMIT-1 (LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`04_integrals_singular.ucas`: `integrate sin(x)/x from 0 to inf`, `integrate sin(x^2) from 0 to
inf`, `integrate cos(x^2) from 0 to inf`, `integrate 1/cosh(x) from -inf to inf`:
**Observed:**
**Reproducer:**
```sh
∫ sin(x)/x dx
  no antiderivative found ...
  numeric: the integrand is undefined or infinite inside the interval (singular or divergent)
```
The integrand is bounded at every interior point and each integral exists:
`∫_0^∞ sin x/x = π/2`, `∫_0^∞ sin(x²)dx = ∫_0^∞ cos(x²)dx = √(π/8) ≈ 0.6267`,
`∫_{-∞}^∞ sech x dx = π`.  No value is returned; the diagnostic is factually wrong,
though no incorrect number is asserted.  `integrate 1/(x*log(x)^2) from 2 to inf` likewise
finds the antiderivative `-1/log x` but never returns `1/log 2`.

### LIMIT-2 — 2 (LIMIT) — L'Hôpital loop on flat/non-analytic forms
**Severity:** LIMIT
_Original classification: `LIMIT-2 (LIMIT`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`05_limits_essential.ucas`: `limit exp(-1/x^2)/x x -> 0` and
`limit (log(1+x)-x)/x^2 x -> 0` iterate L'Hôpital ~12 times, print growing garbage
coefficients, then `= not found symbolically`.  The correct limits are `0` and `-1/2`
(numeric extrapolation by ucas itself agrees).  `exp(-1/x^2)` is flat at 0 (all derivatives
vanish), so L'Hôpital can never terminate.

### LIMIT-3 — 3 (LIMIT) — residue at an essential singularity
**Severity:** LIMIT
_Original classification: `LIMIT-3 (LIMIT`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`08_residue_taylor_nonan.ucas`: `residue exp(1/z) at 0` prints
`"the integral around small circles does not settle (an essential singularity or a branch
point)"` and no value.  The true residue is `1` (coefficient of `1/z` in `∑ z^{-k}/k!`).

### LIMIT-4 — 4 (LIMIT) — simplification / factorisation gaps on classic tricky inputs
**Severity:** LIMIT
_Original classification: `LIMIT-4 (LIMIT`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`06_simplify_identities.ucas`: `simplify abs(x)^2 - x^2` returns the expression unchanged
(it is identically 0 for real x); `simplify (sqrt(x))^2` returns `sqrt(x)^2` unchanged
(it is x for x ≥ 0).  `07_poly_factor.ucas`: `factor x^100 - 1` returns `x^100 - 1`
unchanged instead of the cyclotomic factors `∏_{d|100} Φ_d(x)` (README claims cyclotomic
factors are handled).

### LIMIT-5 — 5 (LIMIT/cosmetic) — inconsistent complex display and branch cuts
**Severity:** LIMIT
_Original classification: `LIMIT-5 (LIMIT/cosmetic`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`09_complex_branch.ucas`: `complex (-1)^(1/2)` prints
**Observed:**
**Reproducer:**
```sh
(-1)^(1/2) = (-1)^(1/2)
  Re = (-1)^(1/2),  Im = 0
  check: equal numerically (1i, complex arithmetic)
```
The check says the value is `i` but the printed `Re`/`Im` are the unevaluated expression
as `Re` and `0` as `Im` (should be `Re = 0`, `Im = 1`).
Branch-cut gap: `integrate 1/x^(1/3) from -1 to 1` uses the antiderivative
`x^(2/3)/(2/3)` with a "check equal at 200 points of [-1,1]" but the real odd cube-root
makes the integrand odd (integral 0); QMC instead returns ≈ 3, treating `x^(1/3)` as even.

## Checks that passed

### Method notes / determinism
- Each candidate was run with `timeout 15..30`; exit codes recorded (all 0).
- Every golden was generated twice and `diff`ed — all 11 CLI files and the MCP JSONL are
  byte-for-byte deterministic (the QMC "seed 1" and Richardson samples are fixed).
- Bugs minimised to single statements and cross-checked with `mpmath`/`sympy`; WRONG-2 and
  WRONG-3 are additionally self-flagged by ucas's own `passed:false` checks (visible in
  `mcp_wrong_checks.out`).
- Crashes / hangs / nondeterminism: none found; documented separately only if they appear.
