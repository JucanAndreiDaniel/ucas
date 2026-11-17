# Stress findings — `series_acceleration`

_Original heading: Stress findings — `series_acceleration`_

# Stress findings — `series_acceleration`

Area: infinite sums, convergence tests, power-series radius, acceleration, products,
generating functions, Euler–Maclaurin asymptotics, closed forms.
All queries below were run against `$ROOT/ucas` (CLI) and the same
binary's `--mcp` wire interface using the `transforms` / `calculus` tools.
Cross-checks used `mpmath 1.3.0` at 30–40 dps.

No crashes, hangs, or nondeterminism were found: every run exited 0, and replaying
the full 53-sum batch and every golden below gave byte-identical output.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 5 | Dirichlet/oscillatory series wrongly declared **divergent** — `WRONG` |
| NLP | 2 | `H(n)` silently misread; `sum H(n)/2^n` returns 1 instead of 2 — `NLP` / `WRONG` |
| LIMIT | 2 | `asymptotic` emits unusable unsimplified symbolic garbage for algebraic terms — `LIMIT` |

## Findings

### WRONG-1 — Dirichlet/oscillatory series wrongly declared **divergent** — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/series_acceleration
$ROOT/ucas 02_converge_dirichlet.ucas
# or, via MCP:
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"transforms","arguments":{"op":"converge","args":{"a":"sin(n)/n"}}}}' | \
  $ROOT/ucas --mcp
```
**Observed:** (CLI golden `02_converge_dirichlet.out`):
```
> converge sin(n)/n
sum(n, 1, inf, sin(n)/n)
  diverges: comparison with the p-series sum 1/n (a_n ~ C/n, p <= 1)
  partial sums: S_10 = 1.124518813, S_1000 = 1.070694154
> converge cos(n)/n
  diverges: comparison with the p-series sum 1/n (a_n ~ C/n, p <= 1)
```
`converge (-1)^n*sin(n)/n` and `converge sin(n^2)/n` get the same verdict; the MCP
`transforms.converge` and `transforms.infinite_sum` ops agree.

**Why it matters:** all of these converge by Dirichlet's test (bounded partial sums of
the oscillating factor times a monotone → 0 weight). Exact values:
`sum sin(n)/n = (pi-1)/2 = 1.0707963268`, `sum cos(n)/n = -log(2 sin(1/2)) =
0.0420195058`. mpmath confirms: partial sum to n=10^6 is 1.07079529 / 0.04201965.
The engine's naive `|a_n| ~ C/n` comparison ignores cancellation and returns a
flatly wrong convergence verdict. (Only `converge sin(n)` — terms do not tend to 0 —
is correctly divergent.)

### WRONG-2 — `radius` returns a finite-n numeric *approximation* ≈ 0.99999 for coefficients `1/log n` — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/series_acceleration
$ROOT/ucas 03_radius_logbug.ucas
```
**Observed:** (first block of `03_radius_logbug.out`):
```
power series sum(n, 2, inf, x^n/log(n)) in x
  center x = 0; coefficients a_n = 1/log(n) of x^(n)
  radius of convergence R = 0.9999933185 (ratio test: |a_(n+1)/a_n| -> 1.000006682)
  at x = -0.9999933185: converges conditionally ... |a_n| ~ C/n^(269/100) ...
  at x =  0.9999933185: converges absolutely (integral test (numeric): ...)
  interval of convergence: [-0.9999933185, 0.9999933185]
```
**Why it matters:** the exact radius is `R = 1` (`lim |a_n|^(1/n) = lim exp(-log log n / n) = 1`).
The tool evaluates the ratio at a single large finite n instead of taking the limit,
so R moves with n and is reported with a spurious 10-digit mantissa. The endpoint
verdicts are consequently wrong too: at `x = 1` the series `sum 1/log(n)` diverges
(terms exceed 1/n), giving the true interval `[-1, 1)`; the bogus `a_n ~ C/n^(269/100)`
is a meaningless local power-law fit to a slowly varying log. Same defect for
`x^n/log(n)^2` (R=0.9999866333), `x^n/sqrt(log n)`, `x^n*log(n)/n`
(R=1.000006678, i.e. **>1**), `x^n/(n log n)`, `x^n/log(log n)`, etc.

### WRONG-3 — `infinite_product` numeric value collapses to **0** for exponentially convergent products — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Repro (MCP golden):
```sh
cd $ROOT/tests/stress/areas/math/series_acceleration
$ROOT/ucas --mcp < mcp_product_accel.jsonl > /tmp/got.out 2>&1
grep -A2 'numeric' /tmp/got.out | head
```
**Observed:** (all five exponential-decay factors):
```
prod(n, 1, inf, 1 - 1/2^n)
  numeric: 0 (partial products to 4096, Richardson in 1/N twice; estimated error 0)
  recognised numerically (not proved): 0
```
The same `numeric: 0` for `1 + 1/2^n`, `1 - 1/3^n`, `1 + (-1)^n/2^n`, `1 - 2/3^n`.

**Why it matters:** true values (mpmath 30 dps) are
`prod(1-1/2^n)=0.2887880951`, `prod(1+1/2^n)=2.3842310290`,
`prod(1-1/3^n)=0.5601260779`, `prod(1+(-1)^n/2^n)=0.5686989463`,
`prod(1-2/3^n)=0.2312460376`. The partial products converge *exponentially*;
Richardson extrapolation "in 1/N" is the wrong acceleration model here and drives
the estimate to 0 with a bogus "estimated error 0". Algebraically convergent
products (`1 - 1/n^2`, `1 + 1/n^2`, `1 - 1/(2n)^2`, Wallis) are handled correctly.

### WRONG-4 — `prod n^2/(n^2-1)` from n=1 prints contradictory closed form and numeric value — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Repro: MCP golden `mcp_misc_wrong.jsonl`, id 1 (`$ROOT/ucas --mcp < mcp_misc_wrong.jsonl`).
**Observed:**
```
prod(n, 1, inf, n^2/(n^2 - 1))
  converges: the factors are 1 + O(1/n^2) (sum |a_n - 1| converges)
  = inf
  method: the factors as (n - a_i)/(n - b_i): prod Gamma(1 - b_i)/Gamma(1 - a_i)
  numeric: 0 (partial products to 4096, Richardson in 1/N twice; estimated error 0)
  check: DISAGREE (difference inf)
```
**Why it matters:** the n=1 factor is `1/0`, so the product diverges to +inf; the
closed form `inf` is right, but the numeric estimator returns 0 and the tool then
emits `DISAGREE (difference inf)` instead of rejecting the input. With `from: 2`
it correctly gives `= 2` and `numeric 1.999999999`. Internally inconsistent output.

### WRONG-5 — `binom(2n,n)/4^n`: overflow at n=86 and a missed divergence verdict — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Repro: `mcp_misc_wrong.jsonl`, id 2 (also id for `n*binom(2n,n)/4^n` in probe).
**Observed:**
```
sum(n, 1, inf, (2n)!/(n!*(2n - n)!*4^n))
  convergence unknown: the ratio, root, comparison and integral tests are inconclusive here
  numeric: a_n is undefined at n = 86
```
**Why it matters:** `(2n)!` at n=86 overflows binary64, so the term is evaluated in
floating point and declared undefined, although the exact central binomial
coefficient is finite. Mathematically `binom(2n,n)/4^n ~ 1/sqrt(pi n)`, so the
series **diverges** (p = 1/2); the tool reports "convergence unknown". The reciprocal
`1/binom(2n,n)` is handled fine (numeric 0.7363998587, = 1/3 + 2pi/(9 sqrt3)).

### NLP-1 — `H(n)` silently misread; `sum H(n)/2^n` returns 1 instead of 2 — `NLP` / `WRONG`
**Severity:** NLP
_Original classification: `NLP / WRONG`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Repro: `mcp_misc_wrong.jsonl`, id 3.
**Observed:**
```
sum(n, 1, inf, u(n)/2^n)
  converges absolutely: ratio test: |a_(n+1)/a_n| -> 1/2 < 1
  = 1
  method: geometric series a r^lo/(1 - r)
  numeric: 1 ...
```
`parse H(n)` separately reports `(H * n)` with note `H(...) read as multiplication:
H is not a function`; inside the sum pipeline the symbol is rewritten to `u(n)`
and the series is evaluated as `sum 1/2^n = 1`. If the user meant harmonic numbers,
the correct answer is `sum_{n>=1} H_n/2^n = 2`. No warning is emitted that `H` is
unknown; the wrong closed form is silently returned with a self-consistency "check"
that passes. (By contrast `harmonic(n)` does produce an error, "harmonic is not a
function", so the two spellings behave inconsistently.)

### LIMIT-1 — `asymptotic` emits unusable unsimplified symbolic garbage for algebraic terms — `LIMIT`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Repro: goldens `04_asymptotic_ugly.ucas` / `.out` (MCP equivalent:
`transforms.asymptotic` with `sum: "sum(k, 1, n, sqrt(k))"`).
**Observed:** (excerpt):
```
sum(k, 1, n, sqrt(k)) ~ 2sqrt(n)^3/3 + sqrt(n)/2 + -0.20788622496184 + 1/(24sqrt(n))
  - ((0*sqrt(n) + 0/(2sqrt(n)) - (0*sqrt(n) + 0/(2sqrt(n)) + 0/(2sqrt(n))
     + 2(0*sqrt(n) - (0*sqrt(n) + 1/sqrt(n)))/(2sqrt(n))^2))*(2sqrt(n))^2
     - 4(...)*sqrt(n)*(...))/(720((2sqrt(n))^2)^2) + ...
```
and for `sum 1/sqrt(k)` an even larger expression with nested `(0*sqrt(n) - 1/(2sqrt(n)))`
factors. The constant is also reported unrecognised (`-0.20788622496184`, actually
`zeta(-1/2)`, and `-1.46035450880959`, actually `zeta(1/2)`).

**Why it matters:** it is a problem: the Bernoulli correction is never simplified, so the answer is
unreadable and unusable even though the numeric checks pass. `sum(k,1,n,1/k)`,
`sum(k,1,n,k^2)`, `sum(k,1,n,1/k^2)`, `sum(k,1,n,log k)` are fine.

### LIMIT-2 — CLI finite `sum` silently returns a symbolic placeholder for large upper bounds — `LIMIT`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Repro: golden `06_cli_sum_limits.ucas` / `.out`.
**Observed:**
```
> sum(i, 1, 100000, 1/2^i)
  note: 1/2^i would divide integers by the index i: i taken as real
_() = sum(i, 1, 100000, 1/2^i)
  -> real
```
`sum(i,1,1000,1/2^i)` correctly prints `1`, and `sum(i,1,1000000,1/i^2)` prints
`1.64493`. No warning explains why the 100000-term geometric sum is left unevaluated.
Similarly `sum(i, 1, 1000000000, 1/i)` returns `_() = sum(...) -> real`. Not a crash
(exit 0) but an unexplained silent failure to compute.

### NLP-2 — CLI `sum` cannot parse factorial terms, unlike `radius` — `NLP` / `LIMIT`
**Severity:** NLP
_Original classification: `NLP / LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Repro: golden `06_cli_sum_limits.ucas` / `.out`.
**Observed:**
```
> sum(i, 0, 100, 1/i!)
06_cli_sum_limits.ucas:3:19: error: expected ')', found '!'
> sum(i, 0, 100, 1/factorial(i))
  note: factorial(...) read as multiplication: factorial is not a function
  note: 1/factorial*real(i) read as 1/(factorial*real(i)); ...
_(factorial: real) = sum(i, 0, 100, 1/(factorial*real(i)))
  -> real
```
Yet `radius x^n/n!` and the MCP `infinite_sum` of `1/n!` work and give `e`/`e-1`.
The same notation is accepted in power-series parsing but rejected (or misread as a
free variable) in the finite-sum term parser — an inconsistency worth fixing.

## Checks that passed

### Coverage / negative results
Everything else that was cross-checked matched high-precision values: the p-series
closed forms `pi^2/6, zeta(3), pi^4/90, zeta(5), pi^6/945, zeta(7), pi^8/9450,
pi^10/93555`; alternating eta sums (`log 2`, `pi^2/12`, `3 zeta(3)/4`, `7 pi^4/720`);
telescoping sums (`1`, `1/4`, `1/18`, `1/96`); geometric and arithmetico-geometric
sums (`2`, `6`, `26`, `4/9`, `2/9`); `-log(1-r)` sums; `sum 1/(n^2+1) =
(pi/2)coth(pi) - 1/2`; Wallis and `sinh(pi)/pi` products; binomial/Fibonacci/Catalan
generating functions; radius/interval boundaries for `x^n/n`, `x^n/n^2`, `x^n/sqrt n`,
`(x-1)^n/n^2`, etc.; divergence verdicts for `1/n`, `1/sqrt n`, `1/(n log n)`,
and the large-index CLI `sum`/`prod` (no crash, correct results or explicit symbolic
fallback). All goldens in this folder were diffed across repeated runs and are
byte-identical.
