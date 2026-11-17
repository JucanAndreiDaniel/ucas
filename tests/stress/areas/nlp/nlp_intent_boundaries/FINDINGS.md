# Stress findings — `nlp_intent_boundaries`

_Original heading: FINDINGS — `nlp_intent_boundaries`_

# FINDINGS — `nlp_intent_boundaries`

All probes used `$ROOT/ucas` (CLI stdin/file, and `--mcp` wire protocol).
247 distinct English queries were run. No crashes, no hangs, no malformed/truncated JSON:
the 221-query labeled corpus completed in 2.8 s and a 10-query adversarial chained-intent
probe in 0.1 s, all with exit 0 and a response per request. Issues are routing/correctness,
not stability. Golden files were verified deterministic by running each twice and `diff`-ing.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | "unequal" is silently read as "equal", inverting the answer |
| NLP | 7 | "equivalence of f and g" silently misroutes to `find` (cheaper implementations) |
| LIMIT | 2 | "verify that … is equal to …" uses pointwise `==`/`show`, not `equiv` |

## Findings

### WRONG-1 — "unequal" is silently read as "equal", inverting the answer
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI golden, from this folder):
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_intent_boundaries
timeout 30 $ROOT/ucas 01_eq_neq_cli.ucas
```
**Observed:** (relevant lines of `01_eq_neq_cli.out`):
```
> is x^2 unequal to x^2?
  note: read "unequal" as "equal"
  ucas: it(x) = x^2
  ucas: that(x) = x^2
  ucas: equiv it that
it and that are equal on the domain of it (exhaustive)
```
MCP equivalent (`english`, `{"text":"is x^2 unequal to x^2","defaults":true}`):
`ok:true`, note `"read \"unequal\" as \"equal\""`, statements `["it(x) = x^2","that(x) = x^2","equiv it that"]`,
`result.results[0] = {kind:"equiv", equal:true, exhaustive:true, mismatch_points:0}`.

**Why it matters:** the user asks whether `x^2` is *unequal* to itself (correct answer: **no**). The
frontend silently rewrites "unequal"→"equal" and answers with the equality check, `equal:true`
(**yes, they are equal**) — the opposite polarity. There is no negation of `equiv` in the emitted
ucas. `is x^2 unequal to x^2 + 1` also routes to `equiv` (`equal:false`, only coincidentally
matching the English answer). This is the single most fragile point of the equal/different boundary.

### NLP-1 — "equivalence of f and g" silently misroutes to `find` (cheaper implementations)
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_intent_boundaries
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"english","arguments":{"text":"equivalence of f and g","defaults":true}}}' \
 | timeout 30 $ROOT/ucas --mcp
```
**Observed:** `ok:true`, `understood:true`, statements
`["it(f, g) = f & g", "find it 10"]`, notes:
```
"equivalence" is not a word I know: the default, equivalent (args.defaults)
"and"/"or" between numbers: the default, bitwise (& and |) (args.defaults)
f has no type: inferred int from the integer operations in the body
g has no type: inferred int from the integer operations in the body
```
**Why it matters:** a request for an *equivalence check* becomes a *find-cheaper-implementations
search on the bitwise-and of the two functions. Two stacked "default" resolutions (unknown word,
then "and"→bitwise-&) turn the whole intent upside down with no error. Contrast `check if f equals g`
which correctly emits `equiv`.

### NLP-2 — the whole "different / not equal / distinct / differ" side of the boundary is unsupported
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_eq_neq.jsonl` (run with `timeout 30 $ROOT/ucas --mcp < mcp_eq_neq.jsonl`),
and the labeled corpus. Observed `english` errors:
**Observed:**
```
"is f different from g"        -> not_understood: I didn't follow "different from g"
"are f and g different"        -> not_understood: I didn't follow "different"
"is f not equal to g"          -> not_understood: I didn't follow "not equal to g"
"is x^2 distinct from x^2"      -> not_understood: I didn't follow "distinct from x^2"
"does x^2 differ from x^3"      -> not_understood: I didn't follow "differ from x^3"
"are x^2 and x^3 not the same"  -> not_understood: I didn't follow "not the same"
"f differs from g" / "f is different than g" / "is f not g" / "how do f and g differ" / "are they different"
                               -> not_understood
```
**Why it matters:** every natural way to ask "are these different?" fails. The one accepted word
("unequal") is broken (F1). Users have no reliable way to express the inequality intent.

### NLP-3 — near-synonyms for "extrema" route to different commands (`range` vs `crit`) or fail
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_crit_maxmin_zeros.jsonl`:
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_intent_boundaries
timeout 30 $ROOT/ucas --mcp < mcp_crit_maxmin_zeros.jsonl
```
**Observed:** statements:
```
"max and min of sin x"                          -> ["it(x) = sin(x)", "range it"]
"what are the maxima and minima of x^3 - 3x"    -> ["it(x) = x^3 - 3*x", "crit it"]
"find the local extrema of x^3 - 3x"            -> ["it(x) = x^3 - 3*x", "crit it"]
"stationary points of x^3 - 3x"                 -> ["it(x) = x^3 - 3*x", "crit it"]
"critical points of f"                          -> ["it(f) = f", "crit it"]
"extrema of f" / "maxima of f" / "minima of f" / "find the extrema of x^3 - 3x"
                                                -> not_understood
```
**Why it matters:** `range` returns min/max *values*, `crit` returns critical *points* — different
intents. "max and min" selects `range`, while "maxima and minima"/"local extrema"/"stationary
points" select `crit`, and the bare "extrema"/"maxima"/"minima" fail. Small wording changes flip
the command or lose the intent entirely.

### NLP-4 — a leading "find" hijacks derivative and gate intents
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_find_gates.jsonl`:
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_intent_boundaries
timeout 30 $ROOT/ucas --mcp < mcp_find_gates.jsonl
```
**Observed:**
```
"find dy/dx for y = x^2"       -> ok:false, understood:true, unsupported:
                                  find needs integer parameters (or a float result)
                                  notes: "'dy' read as d*y", "'dx' read as d*x",
                                         "d*y/d*x*for*y read as d*y/(d*x*for*y)"
"find gates for x + y on u8"   -> ok:false, unsupported: find on a float result needs one f16/f32/f64 parameter
"find minimal gates for f"     -> ["it(f) = f", "gates it"]   (correct gates routing)
"gates for f"                  -> ["it(f) = f", "gates it"]   (correct)
```
**Why it matters:** "find" is an over-strong trigger for the *cheaper-implementation* intent. In
"find dy/dx ..." and "find gates for ..." the user wants `diff`/`gates`, but the parser emits `find`
(and then misparses `dy/dx` as multiplication). The same word boundary also breaks mixed requests.

### NLP-5 — NLP/API — `ok:true` with empty `statements` and `understood:false` for requests that actually ran
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_integral_area_anti.jsonl`, `mcp_range_domain_wrap.jsonl`, `mcp_solve_ode_eq.jsonl`.
**Observed:** (`english`, `defaults:true`):
```
"integrate x^2 from 0 to 1"   -> ok:true, understood:false, statements:[],
                                 result.results[0]={kind:"integrate", antiderivative:"x^3/3", definite 1/3 ...}
"identify y'' + y = 0"        -> ok:true, understood:false, statements:[],
                                 result.results[0]={kind:"identify", properties:{...}}
"area between x^2 and x"      -> ok:true, understood:false, statements:[], result.results[0]={kind:"area", ...}
"wrap f"                      -> ok:true, understood:false, statements:[], result.results[0]={kind:"wrap", ...}
"domain of f"                 -> ok:true, understood:false, statements:[], result.results[0]={kind:"domain", ...}
```
16 of 221 corpus queries had `ok:true` + `understood:false` + `statements:[]` (others include
`suppose f is x^2`, `assume bytes are signed`, `forget everything`, `integrate f`).

**Why it matters:** `statements` is the documented record of "the translated statements that ran"
and `understood` signals successful comprehension. For computational requests a correct answer is
returned while both fields say nothing was understood/translated. A client that validates routing
via `statements` (exactly the technique used here to find F1–F5) cannot see these commands.
Session no-ops (`assume ...`, `forget everything`) are legitimate empty-statement cases, but the
computational ones are not.

### NLP-6 — a single-letter name after "of" is silently read as multiplication `o*f`
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_range_domain_wrap.jsonl`.
**Observed:** (`english`, `defaults:true`):
```
"domain of f"         -> note "'of' read as o*f (single-letter variables)",
                          statements:[], text:"domain of o*f*f: ... defined at 10201 of 10201 points"
"zeros of f"          -> note "'of' read as o*f", text:"zeros of o*f*f:
                          2 parameters; give the others values, e.g. zeros f(o, 1)"
"roots of x^3 - 3x"   -> note "'of' read as o*f", text:"zeros of o*f*x^3 - 3x:
                          3 parameters; give the others values"
```
Contrast (correct):
```
"range of f"                     -> ["it(f) = f", "range it"]
"what is the domain of sqrt(x)"  -> ["it(x) = sqrt(x)", "domain it"]
"what is the domain of days?"    -> ["it(days) = days", "domain it"]
"what are the zeros of x^3 - 3x" -> ["it(x) = x^3 - 3*x", "zeros it"]
```
**Why it matters:** "of" is ambiguous between the English preposition and the implicit product `o*f`.
When the following token is a single-letter name the default resolution picks multiplication,
silently analysing a *different expression* (`o*f*f`) or producing a nonsense multi-parameter
request. The same phrase with a multi-letter name or an expression works. This is precisely the
range/domain/wrap/zeros intent boundary hinging on a lexical detail.

### NLP-7 — "compare f and g" routes to the approximation-`error` intent
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_mixed_dual.jsonl`, query `compare f and g`.
**Observed:**
```
statements: ["that(g) = g", "it(g, f) = f", "error it ~ that"]
error: failed: it has 2 parameters, that has 1: 'fit' the extra ones first
```
**Why it matters:** "compare" is ambiguous between a function-equivalence check and an approximation
error measurement; it silently chooses `error`, and builds an asymmetric pair (`it` has two
parameters, `that` one) that then fails. `check if f equals g` correctly emits `equiv`, so two
"compare" phrasings diverge.

### LIMIT-1 — "verify that … is equal to …" uses pointwise `==`/`show`, not `equiv`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_eq_neq.jsonl`, query `verify that x + 0 is equal to x`.
**Observed:** statements: `["it(x) = x + 0 == x", "show it"]` (no `equiv`), whereas
`check if f equals g` emits `["it(f,g)=f","that(f,g)=g","equiv it that"]`.
**Why it matters:** semantically equivalent equality phrasings take different commands — a pointwise
boolean `show` versus whole-function `equiv` — with different checking/proof semantics.

### LIMIT-2 — mixed two-intent sentences cannot be composed (but are not silently merged)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_mixed_dual.jsonl`.
**Observed:** `not_understood` (or empty) for:
```
"find the range and domain of x^2", "the derivative and the integral of x^2",
"define f as x^2 and find its critical points",
"is f equal to g and what is the range of f", "range of x^2 and critical points of x^3",
"integrate x^2 and find the area under x^2", "zeros of x^2 and critical points of x^2",
"assume x is u8 and find the range of x+1", "diff f and crit f", "wrap f and range f"
```
The only composed form that works is a definition followed by a query separated by `;`:
`"let f be x^2; what is the range of f?"` -> `["f(x) = x^2", "show f", "range f"]`.
**Why it matters:** the parser refuses rather than guessing when two intents share a sentence (good —
no silent dual-intent handling found), but cannot express the common "do X and Y" composition.

## Checks that passed

### Stability note
No `CRASH`, `HANG`, or `DETERMINISM` issue was found in this area. Adversarial chained-intent and
repeated-keyword inputs (`"is f equal to g equal to h ..."`, `"range range range ... f"`,
`"what is the range of the domain of the wrap of f"`, `"compare the range and the domain and the
wrap and the zeros of f and g"`) all returned an error or `understood:false` promptly with exit 0.
All 10 goldens were run twice and produced byte-identical `.out` files.
