# Stress findings — `translation_validation`

_Original heading: Translation validation — findings_

# Translation validation — findings

Area: independently re-validate every form emitted by ucas's rewriters
(`find`, `gates`, `c optimize`, `spirv_simplify`, `simplify`).  The oracles never
call ucas's `equiv` to decide equivalence:

- small machine types: exhaustive enumeration in `harness/expr_eval.py`
- gate networks: independent bit-by-bit simulation in `harness/validate.py`
- int/real `simplify`: exact rational algebra with sympy
- floats: bit-exact f32 patterns (`validate_float.py`)
- `c optimize`: compile original and emitted C with system gcc and diff outputs
  (`validate_c.py`)
- `spirv_simplify`: interpret whole SPIR-V modules before/after each rewrite
  (`validate_spv.py`)

Result: **no emitted rewrite was found to compute a different function** across
301 independently checked emitted forms.  The issues below are proof-claim,
limit and crash issues.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | `find` segfaults on a `name(args) = expr` argument — CRASH |
| WRONG | 1 | `spirv_simplify` proof claim does not cover the rewrite's domain — WRONG |
| LIMIT | 4 | `gates` emits an unproved-minimal network with no `proof` field — LIMIT |

## Findings

### WRONG-1 — `spirv_simplify` proof claim does not cover the rewrite's domain — WRONG
**Severity:** WRONG
The top-level `proof` field claims *"each rewrite bit-blasted and proved equal
for every input (refinement)"* with `kind: "sat"`, but the only rewrite emitted
in this case is a `derivation` that ucas itself restricts with
`holds_where: "%x in [0, 255] (its range)"` under assumption `x in [0,255]`.
The proof statement therefore asserts a domain the emitted rewrite does not
have: for `x = 256` the emitted `%x - 3(171%x >> 9)` is `256 - 3*128 = -128`
(i.e. `0xffffff80` as u32), while the source `OpUMod %x 3` is `1`.

**Reproducer:**
Reproducer (copy-pasteable):

```sh
cd $ROOT/tests/stress/areas/systems/translation_validation
$ROOT/ucas --mcp < mcp_spv_assume.jsonl > /tmp/spv.out 2>&1
python3 -c "
import json; o=[json.loads(l) for l in open('/tmp/spv.out')]
s=o[-1]['result']['structuredContent']
print('top proof:',s['proof'])
print('rewrite:',s['result']['rewrites'][0])
print('holds_where:',s['result']['identities'][0]['holds_where'])
"
```

**Observed:** output:

```
top proof: {'kind': 'sat', 'text': 'each rewrite bit-blasted and proved equal for every input (refinement)'}
rewrite: {'from': '%r = OpUMod %uint %x %uint_3', 'to': '%x - 3(171%x >> 9)',
          'why': 'a division by a constant of a bounded dividend as a multiply and a shift',
          'gain': 4.5, 'line': 0, 'proof': 'derivation'}
holds_where: %x in [0, 255] (its range)
```

**Why it matters:** the rewrite is correct *under the assumption*, and ucas does
state `holds_where` in `identities`, but the response-level `proof` claim is
unconditional and names SAT/bit-blasting, which never ran for this rewrite.
A consumer that checks `proof.kind == "sat"` to decide "valid for every input"
will accept a rewrite that is only conditionally valid.
**Expected:** either the
top-level `proof` should be qualified (e.g. `kind: "derivation"`, text
"under assumptions …") or the claim should say "for every input in the
asserted domain".

### CRASH-1 — `find` segfaults on a `name(args) = expr` argument — CRASH
**Severity:** CRASH
**Expected:** _not recorded_
`find NAME(x: T) = BODY` with `NAME` not previously defined is read as
multiplication (`f * int(x)`) and an `=` inside the expression as `==`, after
which `find` crashes while searching the resulting comparison.

**Reproducer:**
Reproducer (CLI, deterministic; exit 139, stable partial output):

```sh
timeout 10 $ROOT/ucas -e 'find z(x: u8) = x & 15'
```

**Observed:** (last lines before the crash):

```
  note: z(...) read as multiplication: z is not a function
  note: '=' inside an expression read as '=='
  note: bitwise operators bind tighter than comparisons here (unlike C): read as ((z * int(x)) == int((x & 15)))
  note: the result is bool: searching in u8
find z*int(x) == int(x & 15): 32 points (sampled; matches verified on the whole domain), computing in u8, costs from gt1030
  dropping operations of the expression (cost 6 as written; each checked on the whole domain):
  cost 5   z*int(x) == int(x)                       drops & 15 (sampled, not proved)
Segmentation fault
```

The same crash occurs over MCP:

```sh
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"tv","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"find","args":{"f":"f(x: u8) = x & 15","n":1}}}}' \
| timeout 15 $ROOT/ucas --mcp
# exit 139 (core dumped) after the initialize response
```

**Why it matters:** a malformed but parseable argument to a rewriter must return a
diagnostic, not segfault.  The correctly formed AST form (`"f":{"body":...,
"params":[...]}`) works, so this is an input-validation hole.  Not kept as a
golden because the process crashes (rule: crashes are documented only).

### LIMIT-1 — `gates` emits an unproved-minimal network with no `proof` field — LIMIT
**Severity:** LIMIT
For five of the 24 `gates` cases (`g008`, `g013`, `g018`, `g019`, `g021`), exact
synthesis hit its node budget and ucas fell back to Shannon decomposition:

**Observed:**
```
exact search stopped (node budget at cost 7); Shannon decomposition instead:
cost 19, 19 steps (an upper bound, not proved minimal)
checked: the program reproduces every output bit on all 16 care inputs
```

Independent simulation confirmed all five networks reproduce the source on
every care input (so they are *correct*).  However the MCP `structuredContent`
has **`proof: null`** for these cases — only `checks: [{kind: truth_table,
passed: true}]` remains.  For the other 19 cases there is a
`proof: {kind: "exhaustive", text: "iterative deepening on cost: no program of
a lower cost exists"}`.

**Why it matters:** a consumer that reads `proof` to decide "was this translation
checked?" sees *no proof at all* for a network that ucas did emit, even though
it is equivalence-checked by truth table.
**Expected:** a `proof` entry with
`kind: "exhaustive"` for the truth-table equivalence check and a separate
`minimal: false` flag for the missing cost proof (the structured `result`
indeed drops the `minimal` key in these cases).

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/translation_validation
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"tv","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"gates","args":{"f":{"body":"x % 3","params":[{"name":"x","type":"u4"}]}}}}}' \
| $ROOT/ucas --mcp | tail -1 | python3 -c "import sys,json;s=json.loads(sys.stdin.read())['result']['structuredContent'];print('proof=',s['proof'],'checks=',s['checks'])"
```

### LIMIT-2 — `find` marks an unbounded-int rewrite `verified` while the proof is sampled — LIMIT
**Severity:** LIMIT
For source `x * 2` over unbounded `int`, `find` emits `x + x` with:

**Observed:**
```
JSON:  verify=true, proof="sampled", exhaustive=false, why="exact"
text:  "cost 1   x + x   exact (sampled)"
header: "473 points (sampled; matches verified on the whole domain)"
```

**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'it(x: int) = x*2
find it 1'
```

**Why it matters:** `verified: true` and `why: "exact"` together read as a proof,
but `proof: "sampled"` says otherwise; "verified on the whole domain" is also
impossible for `int`.  The rewrite is actually true for all integers
(`2*x == x+x`), so this is a claim-quality issue rather than unsoundness, but
it is exactly the "sampled result presented as a rewrite" pattern.
**Expected:**
`verified: false` (or `proof_kind: "sampled"` only) for non-enumerable domains.

### LIMIT-3 — `c optimize` emits unconditional C for an assumed-range rewrite — LIMIT
**Severity:** LIMIT
With `range: "x 0 1000"`, `c optimize` rewrites `unsigned f(unsigned x){return
x/7;}` to `return (x*1171u)>>13;` with `proof: "exhaustive"` — exhaustive over
the asserted 1001 inputs (structured `rewrite.domain = "x in [0, 1000]
(assumed)"`).  The emitted C has no guard for inputs outside that range: for
`x = 12345`, original gives `1763` and emitted gives `1764` (checked by
compiling both with gcc).

**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/systems/translation_validation
$ROOT/ucas --mcp < mcp_c_range.jsonl > /tmp/c.out 2>&1
python3 -c "
import json;o=[json.loads(l) for l in open('/tmp/c.out')];s=o[-1]['result']['structuredContent']
w=s['result']['rewrites'][0];print('proof:',w['proof'],'domain:',w.get('domain'));print(w['after'])
"
```

**Why it matters:** the "exhaustive" proof covers only the asserted domain; an
unconditional reader of the emitted code would be wrong outside it.  This is a
documented contract (the `domain` field and the text both say "assumed"), so
low severity, but it is a case where a proof's domain is narrower than the
emitted form's domain.
**Expected:** a note in the emitted C, or an assertion, or
a `proof.kind = "exhaustive-under-assumption"`.

### LIMIT-4 — Float `min`/`max` rewrites are conditional and the condition is disclosed — LIMIT
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`find a < b ? a : b` (f32) emits `min(a, b)`; `find a > b ? a : b` emits
`max(a, b)`.  Bit-exact evaluation confirms equality on all non-NaN, non
opposite-signed-zero pairs; for NaN operands GLSL `min`/`max` is undefined and
for `+0/-0` the sign may differ.  ucas states this in `holds_where` ("neither
compared value is NaN … zeros of opposite signs the zero's sign may differ").
No proof field is attached (correctly, since the rewrite by derivation is
conditional).  Recorded here only to document that the domain caveat was
checked independently and found accurate — not a bug.

## Checks that passed

### Note: MCP session-length output degradation (harness workaround)
While collecting 156 mixed rewriter calls in a single `--mcp` session, after
roughly 110 calls the `structuredContent.text` started coming back as a
JSON-encoded string and `analyze parse` returned an empty `text` (the same
requests work when issued alone).  `harness/collect.py` therefore batches calls
into fresh processes of 40 (`run_batched`), after which all 156 requests return
normal text and 99/104 expression normalisations succeed.  This is recorded as
a harness observation, not a graded finding, because a minimal stand-alone
reproducer was not isolated (130 identical `parse` calls in one session do *not*
trigger it).
