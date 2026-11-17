# Stress findings — `fp_edge`

_Original heading: fp_edge stress findings_

# fp_edge stress findings

All commands below use the prebuilt binary `$ROOT/ucas` and were
run with a `timeout`.  Nothing here is a golden `.out` test on purpose: these are
crashes, wrong answers, or solver limits.  Goldens (the deterministic, correct
cases) are the `0*.ucas/.out`, `mcp_float_edges.jsonl/.out` and `mcp_flat.jsonl/.out`
files in this folder.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | stack overflow on deeply nested parentheses |
| WRONG | 3 | MCP `analyze equiv` with expression arguments returns a bogus answer |
| NLP | 1 | inline type annotation in a bare expression misparses |
| LIMIT | 2 | `error` reports max error 0 when every sample is NaN/inf |

## Findings

### CRASH-1 — stack overflow on deeply nested parentheses
**Severity:** CRASH
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (copy-paste; generates a one-line input with 1600 nested parens):

```sh
cd $ROOT/tests/stress/areas/float/fp_edge
python3 -c "n=1600; open('/tmp/fp_edge_crash.ucas','w').write('parse f32('+'('*n+'x'+')'*n+')\n')"
timeout 10 $ROOT/ucas /tmp/fp_edge_crash.ucas; echo EXIT=$?
```

**Observed:**

```
Segmentation fault         timeout 10 $ROOT/ucas /tmp/fp_edge_crash.ucas
EXIT=139
```

At 1200 parens the same command exits 0 and prints `f32(x)`; somewhere between
1200 and 1600 the recursive-descent parser overflows the stack.  Up to 100000
parens were tried, all exit 139.
**Expected:** either parse correctly or report a
clean "expression too deeply nested" error, not a SIGSEGV.  (Found while probing
deep float casts; not specific to floats.)

### WRONG-1 — MCP `analyze equiv` with expression arguments returns a bogus answer
**Severity:** WRONG
_Original classification: `WRONG / NLP`._
**Why it matters:** _not recorded_
The JSON/MCP `equiv` op concatenates the `f` and `g` strings plus the required
`ftz`/`nanbits` keyword into one command line: `equiv <f> <g> noftz`.  When
`f`/`g` are expressions rather than names of functions defined with
`session.define`, the parser greedily reads adjacent expressions as implicit
multiplication and takes the trailing keyword as the second function.  The tool
returns a confident, structured, *wrong* result with no error.

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/float/fp_edge
cat > /tmp/bugequiv.jsonl <<'EOF'
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"equiv","args":{"f":"x","g":"x","ftz":false,"nanbits":false}}}}
EOF
timeout 15 $ROOT/ucas --mcp < /tmp/bugequiv.jsonl | tail -1
```

**Observed:** (structuredContent, id 1):

```
"ucas": "equiv x x noftz",
"result": {"kind":"equiv","equal":false,"exhaustive":true,"mismatch_points":999,
           "method":"exhaustive","counterexample":"x=-10: 100 vs -10"},
"text": "x*x and noftz differ at 999 points, e.g. x=-10: 100 vs -10\n",
"isError": false
```

`equiv x x` must be trivially equal; instead the tool compared `x*x` with a
variable named `noftz`.  Other inputs show the same class of bug:

- `f="(x - x)", g="(0)", ftz=false, nanbits=false` -> `"equiv (x - x) (0) noftz"`,
  answer `"0 and noftz differ at 1000 points, e.g. x=-10: 0 vs -10"`,
  `equal:false`, no error.
- `f="x+0", g="x", ftz=false, nanbits=false` -> `"equiv x+0 x noftz"`, answer
  `"x and noftz are equal on the domain of x (exhaustive)"`, `equal:true`.

**Expected:** either parse the two expressions correctly (e.g. parenthesise each
argument when building the command) or return a clear error; never a structured
`equal` verdict about a mangled command.  Passing pre-defined function *names*
works correctly (see `mcp_float_edges.jsonl`, ids 1-3), so this is specific to
inline expression arguments.

### WRONG-2 — `symmetry` claims a function is BOTH symmetric and antisymmetric
**Severity:** WRONG
**Why it matters:** _not recorded_
Near-zero functions pass both the `f(x,y)=f(y,x)` and `f(x,y)=-f(y,x)` numeric
checks because of an absolute tolerance.  The two properties are mutually
exclusive for any nonzero function.

**Reproducer:**

```sh
printf 'symmetry 1e-20*(x + y)\n' | timeout 15 $ROOT/ucas
```

**Observed:**

```
symmetry of 1e-20(x + y):
  f(x, y) = f(y, x): yes (symmetric)
  f(x, y) = -f(y, x): yes (antisymmetric)
  checked numerically at 400 random points of [-10, 10]^2
```

`1e-20*(x+y)` is symmetric but not antisymmetric (at x=1,y=2 it is 3e-20, not
0).  The same contradiction appears via MCP `properties identify`:

```
identify fma(x, y, -x*y):
  ...
  f(x, y) = f(y, x): yes (symmetric)
  f(x, y) = -f(y, x): yes (antisymmetric)
```

and for `symmetry 1e-20*(x - y)` and `symmetry 1e-20*x*y`.  Output is
deterministic across runs.
**Expected:** at most one of the two yes/no verdicts,
or a relative/tolerance-aware check.

### WRONG-3 — `range` excludes a reachable value (point spike) on wide float domains
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf 'spike(x: f32 in 0..1) = x == f32(0.1) ? f32(1e30) : f32(0)\nrange spike\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:**

```
range of spike -> f32:
  [0, 0]
  sampled 65536 points (domain has 1065353217 points); not exhaustive
```

The function genuinely reaches `1e30` at `x = f32(0.1)`, which is in the domain,
so `[0,0]` is an unsound range.  It is labelled "sampled ... not exhaustive", so
this is a sampling limitation rather than a claimed proof; nevertheless a
`range` that silently misses an isolated spike is a wrong answer for the stated
domain.  The f16 analogue (`x == f16(0.5) ? 65504 : 0`) is exhaustive and gets
`[0, 65504]` correctly, confirming the issue is the f32 sampler.

### LIMIT-1 — `error` reports max error 0 when every sample is NaN/inf
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cat > /tmp/einf.ucas <<'EOF'
good(x: f16 in -1..1) = f16(0)
infonly(x: f16 in -1..1) = asfloat(u16(0x7c00))
error infonly ~ good
EOF
timeout 15 $ROOT/ucas /tmp/einf.ucas
```

**Observed:**

```
error of infonly against good:
  max abs error 0 at -
  max rel error 0 (0%) at -
  mean rel error 0 over 0 points
  max 0 ulp
  approximation is NaN/inf/undefined at 30721 points where the target is finite, e.g. x=-1
  rounding: not analysed (no input of the sample gives a finite, non-zero value)
```

The headline "max abs error 0" / "max rel error 0" directly contradicts the
note that the approximation is inf at all 30721 points.  Reporting 0 (an
attained minimum over an empty set) as the maximum error is misleading; it
should be inf/undefined when there are no finite samples.

### LIMIT-2 — `equiv ... nanbits`: SAT counterexample does not reproduce for sNaN payloads
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (from `03_equiv_nanbits.ucas`):

```sh
printf 'base(x: u32) = asfloat(x)\nf1(x: u32) = asfloat(x) + f32(0)\nequiv base f1 nanbits\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:**

```
base and f1 are equal on the domain of base (sampled, not proved; no SAT proof: its counterexample did not reproduce)
  NaN results compared by their bits, sign and payload (nanbits)
```

The SAT circuit quiets a signaling-NaN payload on `+ 0`; the evaluator leaves
`asuint(asfloat(u32(0x7f800001)) + f32(0)) == 0x7f800001` (payload unchanged).
So the SAT counterexample fails re-check and the tool falls back to "sampled,
not proved; equal".  Related: `asfloat(x) * f32(1)` and `/ f32(1)` against the
same base are *proved* equal with nanbits in the same session.  The result is
honestly labelled unproved, but the evaluator/circuit disagree on sNaN payload
propagation, which makes the nanbits verdict incomplete.  The README states
"what a signaling NaN gives" is left open, so this is recorded as a LIMIT.

### NLP-1 — inline type annotation in a bare expression misparses
**Severity:** NLP
_Original classification: `NLP / LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf 'range sqrt(x: f32 in -1..1)\nrange 1/(x: f32 in -1..1)\n' \
  | timeout 15 $ROOT/ucas
```

**Observed:** (first two significant lines of each):

```
  note: sqrt of the integer x >= -1 && x <= 1 read as floor square root isqrt(); write sqrt(real(...)) for the real one
range of isqrt(x >= -1 && x <= 1) -> bool: ...
range of 1/int(x >= -1 && x <= 1) -> int: ...
```

The `: f32 in -1..1` annotation is only interpreted correctly in a function
definition; in a bare expression it is parsed as a boolean/int condition, so
`sqrt` becomes integer `isqrt` and `1/x` becomes `1/int(cond)`.  Over MCP the
first case is instead refused as an ambiguity error (needs `assume`), so the
CLI silently returns a result about a different function.  Define a named
function first (as all goldens in this folder do) to avoid this.

## Checks that passed

_No separate passed checks were recorded in the original document._
