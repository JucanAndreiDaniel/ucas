# Stress findings — `crit_classification`

_Original heading: FINDINGS — `crit_classification`_

# FINDINGS — `crit_classification`

Area: critical-point finding & classification via CLI `crit` + MCP `analyze.crit`,
cross-checked against an independent numerical oracle (`oracle.py`) and against
MCP `properties` (`zeros` / `monotonic` / `convexity`) and `calculus.hessian`.

All reproducers below exit 0 and are deterministic (each golden was run twice and
`diff`ed). No crashes or hangs were found (see SUMMARY).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | stationary inflections whose derivative only *touches* zero are missed off-grid |
| NLP | 1 | unknown function names are silently misparsed as multiplication |
| LIMIT | 4 | endpoints of closed real intervals are never reported |

## Findings

### WRONG-1 — stationary inflections whose derivative only *touches* zero are missed off-grid
**Severity:** WRONG
_Original classification: `WRONG: stationary inflections whose derivative only touches zero are`._
**Expected:** _not recorded_
`crit` finds derivative roots of even multiplicity only when they land exactly on
its search grid node (notably x = 0). Periodic touching zeros at ±π, ±2π, ±3π
are systematically dropped.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/crit_classification
timeout 30 $ROOT/ucas 07_missed_touching.ucas
```
**Observed:** (excerpt):
```
> crit x + sin(x)
critical points of x + sin(x):
  x + sin(x)' = cos(x) + 1
  none in [-10, 10]
> crit x - tan(x)
  x - tan(x)' = 1 - 1/cos(x)^2
  x ≈ 0: stationary inflection, x - tan(x) = 0
> a(x: real in 3..3.3) = x - tan(x)
> crit a
  none in [3, 3.3]
```
**Why it matters:** `cos(x)+1` has zeros at ±π, ±3π (4 in [-10,10]) and
`1-1/cos(x)^2 = -tan(x)^2` has zeros at 0, ±π, ±2π, ±3π (7 in [-10,10]); at each
of these f is defined and has a horizontal stationary inflection. Narrowing the
range to `[3,3.3]` (which contains π) still returns `none`. The internal oracle
agrees with the mathematics — MCP `properties zeros` of `cos(x)+1` reports all 4
zeros and of `1 - 1/cos(x)^2` reports all 7. So `crit` is inconsistent with the
same binary's derivative-root routine (`mcp_oracle_crosscheck.jsonl` ids 5–8).

### WRONG-2 — underflow creates spurious "stationary inflection" points with wrong classification
**Severity:** WRONG
_Original classification: `WRONG: underflow creates spurious "stationary inflection" points with`._
**Expected:** _not recorded_
For a function that is strictly monotone on each side of a flat singularity,
`crit` reports two points where the derivative underflows to 0 and labels them
"stationary inflection".

**Reproducer:**
```sh
timeout 30 $ROOT/ucas 08_underflow_rounding.ucas
```
**Observed:**
```
> crit exp(-1/x^2)
  exp(-1/x^2)' = exp(-1/x^2)*(2x/(x^2)^2)
  x ≈ -0.02: stationary inflection, exp(-1/x^2) = 0
    (exp(-1/x^2)' is 0 to real rounding within 0.015 of it: one point)
  x ≈ 0.02: stationary inflection, exp(-1/x^2) = 0
    (exp(-1/x^2)' is 0 to real rounding within 0.015 of it: one point)
```
**Why it matters:** `exp(-1/x^2)` is decreasing on x<0 and increasing on x>0; the
true inflection points (where f'' changes sign) are x = ±0.8164965809 — MCP
`properties convexity exp(-1/x^2)` reports exactly those, and no inflection near
±0.02. The reported ±0.02 points are numerical-underflow artifacts, not
stationary inflections. The same false pair appears for
`exp(-1/x^2)*sin(1/x)` (`08_underflow_rounding.out`). `crit` admits the zero is
"to real rounding" yet still emits a definite classification.

### WRONG-3 — flat plateaus handled inconsistently (spurious arbitrary points, missed flat rays)
**Severity:** WRONG
_Original classification: `WRONG / LIMIT: flat plateaus handled inconsistently (spurious arbitrar`._
**Expected:** _not recorded_
**Reproducer:**
```sh
timeout 30 $ROOT/ucas 04_plateaus.ucas
```
**Observed:**
```
> crit max(x,0)
  max(x, 0)' = x >= 0 ? 1 : 0
  x ≈ -5.0025: stationary inflection, max(x, 0) = 0
    (max(x, 0)' is 0 to real rounding within 5 of it: one point)
> crit min(x,0)
  min(x, 0)' = x <= 0 ? 1 : 0
  none in [-10, 10]
> crit abs(x)+x        -> x ≈ -5.0025: stationary inflection
> crit abs(x)-x        -> none in [-10, 10]
> crit max(min(x,1),-1)-> x ≈ -5.5025: stationary inflection (= -1)
> crit abs(x)+abs(x-1)-> x ≈ 0.5: local minimum (= 1)
```
**Why it matters:** whole rays/segments are stationary, but `crit` either (a) picks
one arbitrary grid point out of a continuum and mislabels it "stationary
inflection" (max(x,0) flat on x<0; clamp flat on x<-1), or (b) reports `none`
for an equally flat ray (min(x,0) flat on x>0; abs(x)-x flat on x>0), or (c)
collapses an entire flat interval into a single point (|x|+|x-1| is **constant = 1
on [0,1]**, so every point there is a non-strict extremum; `crit` emits only
x≈0.5 with a ±0.495 rounding tolerance). The behavior is asymmetric between a
flat ray to the left of the grid origin and one to its right. MCP `properties
monotonic` calls in `mcp_plateaus.jsonl` show the companion inconsistency.

### WRONG-4 — MCP structured `analyze.crit` silently truncates the point list at 500
**Severity:** WRONG
_Original classification: `WRONG: MCP structured analyze.crit silently truncates the point list`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/math/crit_classification
timeout 30 $ROOT/ucas --mcp < mcp_cap.jsonl > /tmp/cap.out 2>&1
python3 -c 'import sys,json; [print(len(json.loads(l)["result"]["structuredContent"]["result"]["points"])) for l in open("/tmp/cap.out") if "\"id\"" in l and json.loads(l).get("id") in (1,2)]'
```
**Observed:** for `sin(100x)` the `text` field ends with `... 636 in all` while
`result.points` has length **500**; for `sin(x^3)` text says `... 637 in all`
while `result.points` has length **500**.
**Why it matters:** a programmatic MCP consumer receives an incomplete critical
point set with no truncation flag/count. The CLI text correctly prints the full
count; the structured result does not. (`10_highfreq_cap.ucas` / `.out` capture
the CLI side.)

### LIMIT-1 — endpoints of closed real intervals are never reported
**Severity:** LIMIT
_Original classification: `LIMIT: endpoints of closed real intervals are never reported`._
**Expected:** _not recorded_
**Reproducer:**
```sh
timeout 30 $ROOT/ucas 06_ranges_endpoints.ucas
```
**Observed:**
```
> e1(x: real in 0..1) = x
> crit e1
  e1' = 1
  none in [0, 1]
> e2(x: real in 0..1) = -x
  e2' = -1
  none in [0, 1]
```
**Why it matters:** it is a gap: on the closed interval [0,1] these functions attain a min and a
max at the endpoints, but `crit` only solves f' = 0 and never examines the range
bounds. (Interior range handling is correct: `e3`, `e4` find x=5 and x=50; `e6`
correctly excludes the out-of-range x=-1.)

### LIMIT-2 — multivariate `crit` returns only the gradient — no saddle/extremum classification
**Severity:** LIMIT
_Original classification: `LIMIT: multivariate crit returns only the gradient`._
**Expected:** _not recorded_
**Reproducer:**
```sh
timeout 30 $ROOT/ucas 11_multivariate.ucas
```
**Observed:** (for the three canonical cases):
```
f1 = x^2+y^2  -> gradient d/dx=2x, d/dy=2y     (min at origin)
f3 = x^2-y^2  -> gradient d/dx=2x, d/dy=-2y    (saddle at origin)
f4 = x*y      -> gradient d/dx=y,   d/dy=x     (saddle at origin)
```
**Why it matters:** it is a gap: `crit` never solves the gradient system nor classifies the
stationary points as min/max/saddle, so none of the requested 2D classifications
are produced. The independent MCP `calculus.hessian` oracle (in
`mcp_oracle_crosscheck.jsonl` ids 9–11) gives determinants +4 (min), -4 (saddle),
-1 (saddle), confirming what is missing. (Documented in README, still a
functional gap for this area.)

### NLP-1 — unknown function names are silently misparsed as multiplication
**Severity:** NLP
_Original classification: `NLP / LIMIT: unknown function names are silently misparsed as multipli`._
**Expected:** _not recorded_
**Reproducer:**
```sh
timeout 30 $ROOT/ucas 09_parse_nondiff.ucas
```
**Observed:**
```
> crit round(x)
  note: round(...) read as multiplication: round is not a function
critical points of round*x:
  gradient (solve all = 0): d/dround = x ; d/dx = round
> crit Gamma(x)
  note: Gamma(...) read as multiplication: Gamma is not a function
  -> gradient of Gamma*x
> crit heavy(x)
  note: heavy(...) read as multiplication: heavy is not a function
```
**Why it matters:** a request to find critical points of a (non-differentiable)
function `round`, `Gamma` etc. silently becomes a *different, meaningless* 2-D
bilinear function, and `crit` returns a bogus gradient instead of erroring or
reporting the discontinuity. `W`, `atan2`, `floor`, `ceil`, `sign` are recognized.

### LIMIT-3 — cusps / vertical tangents reported as "not differentiable" at noise-level coordinates
**Severity:** LIMIT
_Original classification: `LIMIT: cusps / vertical tangents reported as "not differentiable" at n`._
**Expected:** _not recorded_
**Reproducer:**
```sh
timeout 30 $ROOT/ucas 03_cusps_kinks.ucas
```
**Observed:** (excerpt):
```
> crit sqrt(abs x)
  x ≈ -1.972152263e-33: not differentiable, sqrt(abs(x)) = 4.440892099e-17
> crit x^(1/3)
  x ≈ 1.972152263e-33: not differentiable, x^(1/3) = 1.254046039e-11
```
**Why it matters:** it is a gap: the cusp of sqrt|x| at x=0 is a genuine **local minimum**; the
point is reported only as "not differentiable", at a noise coordinate
(~2e-33) rather than 0, with a noise function value. `x^(1/3)` has a vertical
tangent at 0 (not a stationary point), again surfaced only as a noisy
"not differentiable" point. No min/max classification is offered for cusps.

### LIMIT-4 — infinitely many critical points near an essential singularity are only sampled
**Severity:** LIMIT
_Original classification: `LIMIT: infinitely many critical points near an essential singularity a`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
timeout 30 $ROOT/ucas 08_underflow_rounding.ucas
```
**Observed:** `crit x^3*sin(1/x)` lists only 24 extremums (|x| ≥ ~0.0116); `crit
cos(1/x)` lists a finite set. The true functions have infinitely many critical
points accumulating at 0. Expected as a numerical limit; documented, not a
golden failure.

## Checks that passed

_No separate passed checks were recorded in the original document._
