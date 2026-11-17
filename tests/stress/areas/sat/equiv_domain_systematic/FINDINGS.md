# Stress findings — `equiv_domain_systematic`

_Original heading: FINDINGS — `equiv_domain_systematic`_

# FINDINGS — `equiv_domain_systematic`

Systematic follow-up on the confirmed "equiv ignores G's domain" root cause
(`sat_ranges_where/07`, `llm_mutators_findings/§1–2`). Cross-product of
**every domain-restriction mechanism × every comparison command × all four
frontends × function-object vs raw-string args**. Each case's true domain was
brute-forced in Python (`harness*.py`, `results_*.jsonl`); verdicts were
classified CORRECT / WRONG / DROPPED-RESTRICTION / LIMIT.

Binary: `$ROOT/ucas` (not rebuilt). All runs bounded by
`timeout`. Every golden below was generated twice and the two outputs
`diff`ed byte-identically. Scratch under `/tmp/opencode/eqdom_scratch`.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | `equiv` ignores every declaration-level restriction on G |
| NLP | 1 | NLP / frontend divergence — function-object `where` silently dropped by `domain`/`range`/`… |
| LIMIT | 3 | `differ` is not an op on any frontend |

## Findings

### WRONG-1 — `equiv` ignores every declaration-level restriction on G
**Severity:** WRONG
_Original classification: `WRONG (unsound "equal"`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
cover **8 restriction shapes** uniformly on **all four frontends** and in
**both arg modes**. Reproducer:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/equiv_domain_systematic
$ROOT/ucas 01_equiv_declaration_restrictions.ucas
```

**Observed:** (all six should say "differ" — G is undefined on part of F's domain):

```
f1 and g1 are equal on the domain of f1 (exhaustive)     # g1: where x < 5
f2 and g2 are equal on the domain of f2 (exhaustive)     # g2: in 0..7
f3 and g3 are equal on the domain of f3 (exhaustive)     # g3: in {0,1,2,3}
f4 and g4 are equal on the domain of f4 (exhaustive)     # g4: where x in {0,1,2,3}
f5 and g5 are equal on the domain of f5 (exhaustive)     # g5: where x != 0
f6 and g6 are equal on the domain of f6 (exhaustive)     # g6: where x < 3 || x > 250
```

New instances beyond the catalog (previously only `where x<N`, a single range
and a 4-element set were recorded): **`where x != 0`, `where` with `||` hull,
`where x in {…}`, where with arithmetic (`x*2 < 10`), two-parameter where,
i8/i16/u16 ranges, sparse far-apart declared sets, and large SAT-path
domains.** `03_equiv_sat_i8_twoparam.out` shows the SAT path affected too:

```
f3 and g3 are equal on the domain of f3 (proved by SAT: 33 AIG nodes, 0 conflicts)
f4 and g4 are equal on the domain of f4 (proved by SAT: 115 AIG nodes, 0 conflicts)
```

`domain g` in the same sessions correctly reports G's small domain (5, 8, 4,
11, 1024, 2 defined points), proving the information exists but is discarded
by `equiv`. Wire frontends return `result.equal:true, mismatch_points:0`
(`mcp_equiv_domain.out`, `mcp_flat_equiv_domain.out`).

**Control (correct):** body-level undefinedness *is* detected — see
`02_equiv_body_undefinedness.out`: partial match / table index / `1/0` /
`1<<x` all yield "differ … vs undefined". So the defect is specifically
*declaration-level* restrictions.

### WRONG-2 — `error` treats a where/range/set-restricted approximation as total
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/equiv_domain_systematic
$ROOT/ucas 04_error_drops_where.ucas
```

**Observed:**

```
> error gw ~ f        # gw(x:u8)=x where x<5
error of gw against f:
  max abs error 0 at -
  mean rel error 0 over 256 points
> error gr ~ f        # gr(x:u8 in 0..7)=x
error of gr against f:
  max abs error 0 at -
  mean rel error 0 over 256 points
> error gm ~ f        # gm = partial match (body-level)
error of gm against f:
  ...
  approximation is NaN/inf/undefined at 224 points where the target is finite, e.g. x=2
```

`gw`/`gr` are defined at only 5/8 points, yet `error` samples F's whole 256-point
domain and reports `bad_points:0` (structured: `{"max_abs_error":0,"points":256,
"bad_points":0}`; `mcp_equiv_domain.out` id 6). Body-level undefinedness (the
partial match) *is* counted. So `error` silently widens declaration-restricted
functions to total — the same root cause leaking into a second command.

### WRONG-3 — WRONG / internal contradiction — `wrap`: `exact:false` with `mismatch_points:0`
**Severity:** WRONG
_Original classification: `WRONG (structured self-contradiction + dangling witness`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/equiv_domain_systematic
$ROOT/ucas 06_wrap_exact_vs_zero_points.ucas
printf '%s\n' '{"id":1,"cmd":"wrap","args":{"f":{"body":"(x >= 8) ? (1 << x) : x","params":[{"name":"x","type":"u8"}]}}}' \
  | $ROOT/ucas --json --files none
```

**Observed:** (CLI):

```
domain of f: ... defined at 8 of 256 points ... C undefined behaviour at 248 points ...
wrap analysis of f:
  1 << x   (u8)
      nuw holds
      nsw holds
  end to end: differs from the mathematical result at 0 points, e.g. 
```

**Observed:** (structured): `"end_to_end": {"exact": false, "mismatch_points": 0}`.

`exact:false` says the machine result is *not* the mathematical result, yet
`mismatch_points:0` and the text "differs at 0 points" say there are no
differences, and the "e.g. " witness list is empty. "no wrapping or rounding"
also conflicts with `domain`'s 248 C-UB points. This is the one place where a
verdict string / structured field contradiction was found.

### NLP-1 — NLP / frontend divergence — function-object `where` silently dropped by `domain`/`range`/`wrap`
**Severity:** NLP
_Original classification: `NLP (silent default`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/equiv_domain_systematic
$ROOT/ucas --mcp < mcp_funcobj_where_drop.jsonl
```

**Observed:** (key fields from `mcp_funcobj_where_drop.out`):

```
id 2: ucas='graw(x: u8) = x where x < 5'      # define WITH where, via session
id 3: domain graw        -> defined_points=5,  points=5    # raw-string name
id 4: domain <obj where> -> ucas='it(x: u8) = x\n domain it'
                            defined_points=256, points=256  # <-- where dropped
id 5: equiv fraw graw    -> equal:true
id 6: equiv <obj><obj where> -> ucas has NO 'where'; equal:true
```

The function object carries `where:["x < 5"]`, but the emitted source is
`it(x: u8) = x` with no `where`; `domain`/`range`/`wrap` then report a *total*
function (256 defined points) where the equivalent raw-string/named-function
path reports 5. Systematic across `where`, `where-set`, `where !=`, `where ||`,
and a two-param where (`results_partB_*.jsonl`: raw 5/4/4/255/8/1024 defined
points vs object 256/256/256/256/256/65536). Declared `range` in params is
**not** dropped (`that(x: u8 in 0..7)` is emitted), so the divergence is
specific to `where`. All three wire frontends (`--json`, `--mcp`, `--flat`)
behave identically here.

### LIMIT-1 — `differ` is not an op on any frontend
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/equiv_domain_systematic
$ROOT/ucas --mcp < mcp_equiv_domain.jsonl | tail -1
```

**Observed:** `{"error":{"code":-32602,"message":"analyze needs \"op\", one of:
… equiv fit error …"}}` (grouped MCP). `--json` returns `unknown_command
"differ"`; `--mcp --flat` returns `unknown tool "differ"`. `equiv` (boolean +
counterexample) and `error` (numeric) are the available oracles. Confirms
`sat_ranges_where/§3` on all four frontends.

### LIMIT-2 — `fit` is inapplicable to pure domain comparisons
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf 'f(x: u8)=x\ng(x: u8)=x where x<5\nfit g ~ f\n' | $ROOT/ucas
```

**Observed:** `error: g has no parameters left to fit (it takes 1, f takes 1)`.
`fit` needs an approximation with *extra* parameters; it cannot be used as a
definedness/equivalence oracle for a restriction-only difference. Graceful
error, no crash.

### LIMIT-3 — a `where` bound that overflows the type silently becomes 0
**Severity:** LIMIT
_Original classification: `LIMIT/NLP`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/equiv_domain_systematic
$ROOT/ucas 05_where_literal_overflow.ucas
```

**Observed:**

```
  note: literal 256 does not fit u8; it becomes 0
domain of g: ... where x < 0 ... defined at 0 of 0 points
f and g are equal on the domain of f (exhaustive)     # vacuous "equal"
```

An intended "all u8" restriction collapses to the empty domain and `equiv`
then proves equality vacuously. The note is the only warning.

## Checks that passed

### Scope / method (counts)
- **23 distinct restriction scenarios** across 8 families: typed `in a..b`,
  typed `in {…}`, `where` (`<`, `!=`, `||`, `in {…}`, arithmetic, two-param),
  partial `match`, out-of-range table index, division by zero, shift ≥ width,
  sparse far-apart set, i8/i16/u16/u32 ranges, SAT-path large domains.
- **Commands**: `equiv`, `error`, `fit`, `domain`, `range`, `wrap`,
  `differ` (via `analyze`).
- **Frontends**: CLI, `--json`, `--mcp` (grouped), `--mcp --flat`.
- **Args**: full `.ucas` source, raw-string name args, and function-object args.
- **≈800 bounded case-runs** (165 source cross-product + 543 structured
  requests + 32 SAT/extra-scenario runs + 60 adversarial fuzz equivs), plus
  ad-hoc probes.

### Negative results / things checked but NOT found
- **No crashes, hangs, signals or truncated JSON** anywhere (all runs `rc=0`;
  MCP reply counts matched request counts in all batches).
- **No nondeterminism**: all 8 CLI/MCP goldens byte-identical across two runs;
  SAT AIG/conflict counts stable.
- **No text-vs-structured contradictions in `equiv`/`error`**: 60 adversarial
  fuzz `equiv` requests with random bodies/where clauses and all structured
  goldens had `result.equal` agree with the `text` verdict (0 contradictions).
  The only contradiction found is the `wrap` `exact` flag (§3).
- **No frontend verdict divergence** for the same logical case: CLI, `--json`,
  `--mcp`, `--flat` all return the same (wrong) "equal" for a given restriction;
  the divergence is between *arg modes* (raw name vs function object), §4.
- **`domain`/`range`/`wrap` correctly report body-based undefinedness** (match,
  table, div-0, shift) — only declaration-level restrictions are mishandled by
  the comparison commands.
- `sqrt`-negative undefinedness (`g=sqrt(x)-sqrt(x)`) is correctly detected as
  a "differ … vs undefined" control (probed, not kept as a golden).

### Confinement
All files live in `tests/stress/areas/sat/equiv_domain_systematic/`. No source, Makefile,
existing test, `opencode.json`, other stress area, or git state was modified.
