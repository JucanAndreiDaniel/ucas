# Stress findings — `metamorphic_identities`

_Original heading: FINDINGS — metamorphic_identities_

# FINDINGS — metamorphic_identities

Area: verified/metamorphic identities as a bug oracle (`equiv`, `prove`, `range`).
Binary: `$ROOT/ucas`. All reproducers were run with `timeout`.

The catalog itself (216 `equiv` checks in `01_*`–`18_*`) is **clean**: every identity
that is true by construction on its declared type returned `equal:true`, and every
identity that is false outside its domain returned `equal:false`. No crash, hang,
or nondeterministic witness was found in the catalog; all 20 golden files were run
twice and byte-identical, and the MCP golden was run twice and byte-identical.

Three issues were found at the edges.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | undefined identifier becomes a free identity function; `equiv` claims equality |
| NLP | 1 | `^` silently switches from power to xor near bitwise operators |
| LIMIT | 1 | wide polynomial identities get a probabilistic verdict, not a proof |

## Findings

### WRONG-1 — undefined identifier becomes a free identity function; `equiv` claims equality
**Severity:** WRONG
_Original classification: `WRONG (bogus answer accepted from a malformed/typo'd argument`._
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/metamorphic_identities
$ROOT/ucas 22_undefined_ref.ucas
```

**Exact output:**
```
> f(x: u8) = x
> equiv f nonexistent_name
f and nonexistent_name are equal on the domain of f (exhaustive)
```

**Why it matters:** `nonexistent_name` is not defined anywhere. `show
nonexistent_name` reveals it has been silently materialised as
`_(nonexistent_name: real) = nonexistent_name` — a fresh *identity* function of type
`real`. Because an undefined name in the **second** position is turned into a free
variable matching the first function's parameter, `equiv f nonexistent_name` compares
`x` with `x` and reports `equal:true`. A user who typos a function name in an
equivalence check therefore gets a confident, exhaustive-looking `equal:true` instead
of an "undefined function" error. (With `f(x:u8)=x+1` the same typo reports
`differ at 256 points, e.g. x=0: 1 vs 0`, confirming the free-variable reading.)

This is not CLI-only: MCP `analyze` with `{"f":"f","g":"mystery"}` returned
`{"equal":false,"mismatch_points":256,...}` for `f(x)=x+1` under the same
interpretation. An undefined name in the **first** position does error
(`error: expected an expression`), so the behaviour is asymmetric.

Durable reproducer with golden: `22_undefined_ref.ucas` / `22_undefined_ref.out`.

### NLP-1 — `^` silently switches from power to xor near bitwise operators
**Severity:** NLP
_Original classification: `NLP (context-dependent parse of an identical subexpression`._
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/metamorphic_identities
$ROOT/ucas 20_caret_context.ucas
```

**Exact output:**
```
> a(x: u8) = x^2
> equiv a ~ x*x
a and x*x are equal on the domain of a (exhaustive)
> b(x: u8) = ~(~(x^2))
  note: "^" between integers, next to bitwise operators: read as xor (bitwise exclusive or), not power (write xor or ** to say which)
> equiv a b
a and b differ at 254 points, e.g. x=0: 0 vs 2
> show b
b(x: u8) = x xor 2
  -> u8
```

**Why it matters:** it is a bug / metamorphic relevance:** `~(~y) == y` is true for every `y`, so
`~(~(x^2))` must equal `x^2`. But the *same spelling* `x^2` parses as **power** in
`a` and as **xor** in `b` solely because `b` also contains `~`. A stacked rewrite that
wraps a polynomial in a bitwise identity therefore silently changes the polynomial,
and the metamorphic oracle reports a false difference. This is exactly the kind of
"identical subexpression, different parse" invariance failure CheckList INV is meant
to catch. There is a note, but it is not an error and the parse changes with context.

CLI-vs-MCP divergence: the CLI silently takes the xor default (with the note above);
MCP `ucas`/`analyze` refuses the same input with
`error (ambiguous): "^" between integers, next to bitwise operators` and requires
`args.assume.caret` or `args.defaults=true`. Same statement, two protocols,
different outcomes.

Durable reproducer with golden: `20_caret_context.ucas` / `20_caret_context.out`.
Workaround: write `**` for power and `xor` for xor explicitly.

### LIMIT-1 — wide polynomial identities get a probabilistic verdict, not a proof
**Severity:** LIMIT
_Original classification: `LIMIT (unsound-looking equal:true with no proof certificate`._
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/metamorphic_identities
$ROOT/ucas 19_poly_wide_limit.ucas
```

**Exact output:**
```
> p(a: u16, b: u16) = a^2 - b^2
> q(a: u16, b: u16) = (a-b)*(a+b)
> equiv p q
p and q are equal on the domain of p (sampled, not proved; SAT gave up on 3740 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
  polynomials of total degree at most 2, equal at 4 random points mod 2^61 - 1: two that differ agree at one with probability at most 2/(2^61 - 1) = 8.67e-19 (Schwartz-Zippel), at all 4 with at most 5.66e-73: equal over the integers except with that probability, and then for every input here (a probabilistic answer, not a proof)
```

**Why it matters:** The identity is true in `Z/2^16`, and `equiv` reports `equal:true`,
but the MCP result has **no** `proof` field and the text explicitly says "a
probabilistic answer, not a proof". A caller that keys on `result.equal` alone cannot
distinguish a proven exhaustive equivalence from a 4-point Schwartz-Zippel sample.
On u32/u64 this costs ~10–12 s per query (four such queries took ~29 s), which is why
they are kept out of the fast golden files. By contrast `(x*y)*z == x*(y*z)` on the
same wide types is proved instantly "by algebra", so the algebra normaliser is not
expanding `^` (power) into multiplication.

False wide polynomials are still correctly refuted — see `21_poly_wide_false.ucas`:
`(a+b)^2 == a^2+b^2` on u16/u32 returns `differ at ... points of the sample, e.g.
a=1, b=1: 4 vs 2`. So this is a proof-strength limit, not an unsound `equal:true`.

Durable reproducer with golden: `19_poly_wide_limit.ucas` / `19_poly_wide_limit.out`.

## Checks that passed

### Notes (not claimed as ucas bugs)
* While calling `tools.ucas.proofs` from Code Mode, one session returned
  `MCP tool "proofs" ... Connection closed: MCP server process exited`. The same
  requests replayed over the documented wire protocol
  (`$ROOT/ucas --mcp < proofs_probe2.jsonl`) returned valid
  JSON-RPC responses (including a proper `error (failed): no theorem bockstein`),
  so this was not reproducible and is treated as a harness/transport artefact, not a
  solver crash.
* Wide-type refutations such as `(x*y)/y == x` on u64 report `differ at 65530
  points of the sample` — the word "sample" is present and 65530 is a fixed sample
  size, so this is honest sampled reporting rather than a false exhaustive count.
