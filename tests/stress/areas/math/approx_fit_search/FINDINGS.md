# Stress findings — `approx_fit_search`

_Original heading: Findings — `approx_fit_search`_

# Findings — `approx_fit_search`

Every reproducer below was run with
`timeout <T> $ROOT/ucas <file>` from this directory (or with a
one-line heredoc as shown).  Binary: `$ROOT/ucas`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | long numeric searches do not finish within the budget |
| WRONG | 3 | `fit` returns a magic constant that is not the best one |
| NLP | 1 | the English front-end does not route magic-constant requests |
| LIMIT | 2 | degenerate / reversed / negative `degree` silently reinterpreted |
| DETERMINISM | 1 | `adamfit` prints a wall-clock time that changes every run |

## Findings

### WRONG-1 — `fit` returns a magic constant that is not the best one
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/approx_fit_search
printf 'rsqrt(x: f32 in 0.01..100) = 1/sqrt(x)\nguess(x: f32, K: u32) = asfloat(K - (asuint(x) >> 1))\nfit guess ~ rsqrt\n' > /tmp/fit.ucas
timeout 15 $ROOT/ucas /tmp/fit.ucas
python3 verify_fit_oracle.py
```

**Observed:** (ucas)

```
fit guess to rsqrt (max relative error, 4096 sample points):
  K = 1597465581  (0x5f3763ed)
  objective 0.0342066
  asfloat(1597465581 - (asuint(x) >> 1))
  max abs error 0.341896 at x=0.0100000007
  max rel error 0.0342164 (3.42%) at x=59.6959572
```

**Observed:** (independent exhaustive oracle, all 111,421,686 f32 values in [0.01,100])

```
K=0x5f3763ed: exhaustive max-rel = 0.03421690177 at x=0.0145740155   <-- fit's answer
K=0x5f376423: exhaustive max-rel = 0.03421356909 at x=0.0145741161   <-- strictly better
```

**Why it matters:** `fit` claims to minimise max relative error ("objective
0.0342066") and returns K = 0x5f3763ed.  Exhaustive evaluation over the whole
domain shows that constant has true max-rel error **0.03421690**, while
K = 0x5f376423 achieves **0.03421357** — strictly smaller.  The returned
"best constant" is therefore not best.  The cause is visible in the output:
the objective is computed on only 4096 sample points, and even the reported
"max rel error 0.0342164 ... over 65536 points" *underestimates* the true max
by ~5e-7.  A sampled objective cannot certify a minimax constant for a function
whose worst case sits at a specific mantissa pattern (x ≈ 0.01457).  The
`find rsqrt` path inherits the same K (see `11_fit_magic.ucas` / golden).

### WRONG-2 — `error` / `fit` ignore the approximation's declared domain
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/approx_fit_search
printf 'f(x: f32 in 0..1) = x*x\nerror f ~ sin\n' > /tmp/dom.ucas
timeout 15 $ROOT/ucas /tmp/dom.ucas
```

**Observed:**

```
> f(x: f32 in 0..1) = x*x
> error f ~ sin
    note: sin alone read as sin(x)
  error of f against sin(x):
    max abs error 100.544 at x=10
    max rel error 18573.1 (1.86e+06%) at x=-9.42
    mean rel error 206.874 over 1001 points
    max 2180859541 ulp
```

**Why it matters:** `f` is declared only on `x in 0..1`, yet the reported worst
cases are at `x = 10` and `x = -9.42`, far outside that domain, and the sample
count (1001 points over [-10,10]) is the target `sin`'s *default* domain, not
`f`'s.  The claimed max error is measured at points where the approximation is
not defined.  The same happens via MCP (`mcp_domains_args.jsonl`, id 2) and in
`fit f2 ~ sin` (golden `12_fit_odd.ucas`): an `x in 0..1` declaration is ignored
in favour of the target's domain.
**Expected:** use the intersection of the two
domains, or reject incompatible domains.

### WRONG-3 — `fit` silently accepts an undefined target
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/approx_fit_search
printf 'guess(x: f32, K: u32) = asfloat(K - (asuint(x) >> 1))\nfit guess ~ nosuchfunc\n' > /tmp/nf.ucas
timeout 15 $ROOT/ucas /tmp/nf.ucas
```

**Observed:**

```
  fit guess to nosuchfunc (max relative error, 257 sample points):
    K = 546308096  (0x20900000)
    objective 306.2
    asfloat(546308096 - (asuint(f32(nosuchfunc)) >> 1))
    max abs error 47.5 at nosuchfunc=-0.02
    max rel error 2375 (2.38e+05%) at nosuchfunc=-0.02
```

**Why it matters:** `nosuchfunc` is not defined anywhere, but instead of
reporting an unknown identifier, `fit` reinterprets it as a free variable over
a default interval and produces a confident-looking "best K" and error report.
This is an accepted malformed argument returning a bogus answer.  Also
reproducible when the target's definition itself failed to parse (a 2..1 empty
range) — `fit g ~ r` still succeeds against the undefined `r`.  See
`12_fit_odd.ucas`.

### LIMIT-1 — degenerate / reversed / negative `degree` silently reinterpreted
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/approx_fit_search
printf 'approx sin(x) in 0..1 degree 0..0 as f32 list 1\n' > /tmp/d0.ucas
timeout 15 $ROOT/ucas /tmp/d0.ucas | grep -E '^  fits|^    [0-9]+ |no polynomial'
```

**Observed:** for `degree 0..0`** (the degenerate range is ignored and the *default
odd degrees 1,3,5,7,9 are fitted instead — degree 0, a constant, is never tried):

```
  fits in real arithmetic (max relative error of x*P(x^2)):
      1    0.0918 ...
      3    0.00118 ...
      5    7.12e-06 ...
      7    2.49e-08 ...
      9    5.69e-11 ...
```

**Observed:** for `degree -1`**: "no polynomial fit in the degree range", but the
command still emits a degree-2/2 Bhaskara rational candidate — a negative
polynomial degree silently falls back to a rational form.

**Observed:** for `degree 9..5`** (reversed): "no polynomial fit in the degree
range" and an empty candidate table, with no complaint about the reversed
range.

**Why it matters:** it is a bug / limitation:** malformed degree arguments are accepted and
silently mapped to a different computation instead of being rejected.  A caller
asking for a degree-0 constant gets a degree-1..9 polynomial fit.
See golden `02_approx_degrees.ucas`.

### HANG-1 — long numeric searches do not finish within the budget
**Severity:** HANG
_Original classification: `HANG / LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd /tmp/opencode
printf 'approx sin(x) in 0..1 degree 5 as f32 list 2 search anneal\n' > _h.ucas
time timeout 30 $ROOT/ucas _h.ucas >/dev/null 2>&1; echo "rc=$?"
printf 'approx sin(x) in 0..1 degree 100 as f32 list 1\n' > _d.ucas
time timeout 20 $ROOT/ucas _d.ucas >/dev/null 2>&1; echo "rc=$?"
```

**Observed:** : default `search anneal` produced no candidate table and `rc=124`
after 30 s (partial output only: it stops after the "piecewise" line); degree
100 needs between 20 s and 30 s and emits a partial table before completing
(`rc=0` at 30 s, `rc=124` at 20 s).  By the suite rules, no further output
after the timeout is a hang.  These are not kept as goldens; use a small
explicit `search anneal budget ...` or a moderate degree for deterministic goldens.

### DETERMINISM-1 — `adamfit` prints a wall-clock time that changes every run
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Reproducer:**

```sh
cd /tmp/opencode
for i in 1 2; do printf 'adamfit cos(x) in 0..1 count 100 steps 30 auto list 1\n' > _a.ucas; timeout 20 $ROOT/ucas _a.ucas | tail -1; done
```

**Observed:**

```
0.56 s
0.52 s
```

**Why it matters:** it is a bug for testing:** every other numeric search (`fit`, `error`,
`find`, `stoke` with a seed, `approx` with the default walk) is byte-for-byte
deterministic and was kept as a golden.  `adamfit` appends a timing line whose
value moves between runs, so its output cannot be a golden.  Reported here
rather than as a `.out` (SPEC.md §8, Determinism).  The numeric candidates themselves
were identical; only the trailing `X.XX s` line differs.

### NLP-1 — the English front-end does not route magic-constant requests
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/approx_fit_search
printf 'fit the quake magic constant\nfind the fast inverse square root bit hack\n' > /tmp/nlp.ucas
timeout 15 $ROOT/ucas /tmp/nlp.ucas
```

**Observed:**

```
> fit the quake magic constant
    note: I don't know the word "quake": read as a variable, not a mistake (stop here) (rephrase it, or name variables with one or two letters)
    sorry: fit it to what?
> find the fast inverse square root bit hack
    note: I don't know the word "fast": read as a variable, not a mistake (stop here) (rephrase it, or name variables with one or two letters)
    sorry: I didn't follow "inverse square root bit hack"
```

**Why it matters:** it is a bug / limitation:** natural-language phrasings for the exact ops
in this area ("fit the quake constant", "find the rsqrt bit hack") are not
recognised and produce a "sorry".  By contrast "what is the error of x squared
as an approximation of sin on 0 to 1" is routed correctly (golden
`15_nlp_frontend.ucas`).  See golden `15_nlp_frontend.ucas`.

### LIMIT-2 — MCP `approx more` and the strict-ambiguity path differ from CLI
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/approx_fit_search
timeout 30 $ROOT/ucas --mcp < mcp_approx.jsonl | head -3 >/dev/null
grep -n 'no more candidates' mcp_approx.out
```

**Observed:** : in MCP mode `approx ... list 1` does not print the CLI's
"N more: 'approx more [n]'" line, and the following `approx_more` call answers
`no more candidates` even though the same CLI sequence has 8 further
candidates (golden `16_approx_more.ucas`).  Also, MCP turns the CLI's note-only
"keep endpoints?" ambiguity into a hard `ambiguous` error requiring
`args.assume.keep_ends` or `defaults:true` (see `mcp_domains_args.jsonl`, id 4).
These are behaviour differences between the two front-ends, documented here;
the MCP goldens set `defaults:true` and were kept as deterministic.

## Checks that passed

_No separate passed checks were recorded in the original document._
