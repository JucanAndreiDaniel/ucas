# Stress findings — `suite_mutation_testing`

_Original heading: Findings — `suite_mutation_testing`_

# Findings — `suite_mutation_testing`

Scope: the top-level "500-file" regression suite (`$ROOT/tests/*.ucas` +
matching `*.out`, 250 pairs). No source, Makefile, existing test, or git state was modified.
All new artifacts live in `tests/stress/areas/systems/suite_mutation_testing/`.

Severity key: `CRASH` · `HANG` · `WRONG` · `NLP` · `LIMIT` · `DETERMINISM` (per `SPEC.md`).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `WRONG` (high): 31 of 32 confirmed bug classes have NO covering golden |
| LIMIT | 1 | `LIMIT` (low): suite mixes fast goldens with long searches; short-timeout runs truncate 79… |
| DETERMINISM | 1 | `DETERMINISM` / `LIMIT` (medium): goldens embed platform-dependent numeric check values |

## Findings

### WRONG-1 — 31 of 32 confirmed bug classes have NO covering golden
**Severity:** WRONG
_Original classification: `WRONG (high): 31 of 32 confirmed bug classes have NO covering golden`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
python3 tests/stress/areas/systems/suite_mutation_testing/data/build_matrix.py
```

**Observed:** output

```
{
  "total_checks": 188,
  "covered": 1,
  "gaps": 31,
  "classes": 32
}
```

Full matrix: `COVERAGE_MATRIX.md`; per-check evidence: `data/checks.csv` (188 rows);
machine-readable: `data/matrix.json`.

**Why it matters:** this is a bug

A bug class is "covered" only if some stored `.out` exhibits its observable buggy signature,
so that a correct fix would change that golden. Only **B04** (`domain` says "total on its
parameter types" while only 7 of 10 points are defined) is covered — by `texfetch.out` (and
`whereor.out`). The other 31 classes — including the top-priority soundness bugs from
`MASTER_FINDINGS.md` — have **no** covering test in the suite:

- B01 real `equiv` refutes true identities with an identical-value "counterexample"
  (`symbolic_diff_exact`): no golden contains `differ at …: V vs V` with equal values.
- B02 `equiv` ignores G's `where` narrowing; B03 `u8(x)==i32(x)` cast coercion;
  B06 `wrap` "differs at 0 points" despite `nsw` failing; B07 vacuous SAT proof on an
  empty domain; B09 f32 point-spike `range` miss; B10 symmetry both symmetric and
  antisymmetric; B13 `taylor` order-8 wrong coefficient; B21 `groebner` drops the 257th
  polynomial; B22 `pmsnf` drops rows past 64; B25 silent `1e400` overflow; B26 mixed
  signed/unsigned reinterpretation.
- Several classes (B08 stale `it`/`that`, B19 `laplace_solve` IC, B20 `fourier(x^n)=0`,
  B23 `primroot` arg swap, B29 `timeout_s` desync) are MCP/JSON-session bugs that the
  top-level CLI `.ucas` goldens cannot express at all.
- Crash/hang classes (B24 `abselftest`, B27 ReDoS, B28 deep-nesting SIGSEGV) are correctly
  absent from goldens, but there is no non-hanging golden for their safe boundary either.

Consequence: fixing any of these 31 bugs would change **zero** `.out` files, so the
regression suite provides no protection against their reintroduction.

### WRONG-2 — mutation blind spot — semantic output unchanged by a coefficient change
**Severity:** WRONG
_Original classification: `WRONG (medium): mutation blind spot`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests
diff counter.out stress/suite_mutation_testing/mutations/m15.out
```

**Observed:** output

```
1c1
< > f(x in 0..4) = x*(x - 1)/2
---
> > f(x in 0..4) = x*(x - 2)/2
```

Every other line is byte-identical, notably:

```
f and g differ at 5 points, e.g. x=0: 0 vs 1
```

**Why it matters:** this is a bug

Mutant `m15` changes the function `f` from `x*(x-1)/2` to `x*(x-2)/2` — a genuinely
different function. The stored golden's only reaction is the echoed `> ` command line;
its semantic content does not change because `x=0` remains the first counterexample with
the same printed values (`0 vs 1`). Thus a real semantic regression that preserves the
first witness is invisible to this golden. In the full mutation run, 29/30 mutations were
detected semantically; `m15` is the one blind spot. Details: `MUTATION_RESULTS.md`.

### DETERMINISM-1 — goldens embed platform-dependent numeric check values
**Severity:** DETERMINISM
_Original classification: `DETERMINISM / LIMIT (medium): goldens embed platform-dependent nume`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests
timeout 25 $ROOT/ucas algebra.ucas > /tmp/alg.out 2>&1
diff algebra.out /tmp/alg.out | head -6
timeout 25 $ROOT/ucas xform.ucas > /tmp/xf.out 2>&1
diff xform.out /tmp/xf.out | head -6
```

**Observed:** output

```
# algebra.out
116c116
<   check: equal at 64 sample points (max relative difference 1.9e-15)
---
>   check: equal at 64 sample points (max relative difference 1.8e-15)

# xform.out
30c30
<   check: matches int_0^inf f(t) e^(-st) dt (...) max relative difference 0
---
>   check: matches int_0^inf f(t) e^(-st) dt (...) max relative difference 1.2e-16
```

`calculus2.out` likewise differs at line 461 (`to 2e-16` vs `to 0`). Three consecutive
runs of the shipped binary are byte-identical to each other, so this is a **stale golden
across platforms/libm**, not run-to-run nondeterminism.

**Why it matters:** this is a bug

Exact-diff golden comparison produces false failures on a different host even though
all results are semantically correct. It also contaminates mutation testing: a raw diff
cannot distinguish "mutation detected" from "floating-point check noise". My mutation
analysis therefore strips `> ` echo lines and numeric-check noise lines before comparing
(`semantic` column in `data/mutations.csv`).

### LIMIT-1 — suite mixes fast goldens with long searches; short-timeout runs truncate 79/250
**Severity:** LIMIT
_Original classification: `LIMIT (low): suite mixes fast goldens with long searches; short-timeo`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
python3 tests/stress/areas/systems/suite_mutation_testing/data/baseline.py
cat tests/stress/areas/systems/suite_mutation_testing/data/baseline.log
```

**Observed:** output

```
total 250
match 107 differ 143
timeouts 79 nonzero_rc 2
```

**Why it matters:** this is a limitation

With a 4 s per-file cap (chosen to bound this analysis), 79 of 250 goldens do not finish
and produce truncated output; of the remainder, many differ only in the numeric check
noise of F3. A conventional fast test runner cannot compare these goldens byte-for-byte
without both a generous timeout and a numeric-noise-tolerant comparison. This is an
artifact of the analysis cap, not a binary bug; it is recorded so the coverage counts are
not mistaken for "143 broken tests".

## Checks that passed

_No separate passed checks were recorded in the original document._
