# Stress findings — `nlp_checklist`

_Original heading: nlp_checklist — findings_

# nlp_checklist — findings

CheckList-style testing of the English frontend (RESEARCH.md §6). 207 distinct
English queries across three categories (MFT / DIR / INV). All reproducers below
were run with `timeout` against `$ROOT/ucas`. Working-directory
for every command: `$ROOT/tests/stress/areas/nlp/nlp_checklist`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | `WRONG` — negation is ignored: "unequal" is silently read as "equal" |
| NLP | 4 | `NLP` / `LIMIT` — no English phrasing for a negated equivalence is understood |
| LIMIT | 1 | `LIMIT` — some natural-language synonyms / intent phrasings are not supported |
| DETERMINISM | 1 | `DETERMINISM` — MCP `english` response shape flips when stdout capture fails |

## Findings

### WRONG-1 — `WRONG` — negation is ignored: "unequal" is silently read as "equal"
**Severity:** WRONG
**Expected:** _not recorded_
**Reproduce (CLI, from this folder):**

**Reproducer:**
```sh
timeout 15 $ROOT/ucas 03_inv_cli.ucas | sed -n '64,69p;77,82p'
```

**Observed:**

```
> are x times x and x^2 unequal for an unsigned byte x?
  note: read "unequal" as "equal"
  ucas: it(x: u8) = x*x
  ucas: that(x: u8) = x^2
  ucas: equiv it that
it and that are equal on the domain of it (exhaustive)
...
> are x plus 1 and x unequal for an unsigned byte x?
  note: read "unequal" as "equal"
  ucas: it(x: u8) = x + 1
  ucas: that(x: u8) = x
  ucas: equiv it that
it and that differ at 256 points, e.g. x=0: 1 vs 0
```

MCP equivalent (`mcp_inv_negation.out`, ids 1–2 and 5–6):

```
[1] "is x times x equal to x squared for an unsigned byte x"     -> equal:true
[2] "are x times x and x^2 unequal for an unsigned byte x"      -> equal:true   (note: read "unequal" as "equal")
[5] "is x plus 1 equal to x for an unsigned byte x"              -> equal:false
[6] "are x plus 1 and x unequal for an unsigned byte x"         -> equal:false  (note: read "unequal" as "equal")
```

**Why it matters:** the negation word is silently mis-corrected towards `equal`,
so the reported `equiv` answer is *identical* to the positive question instead of
its opposite. A user asking "are f and g unequal" receives the answer to "are f
and g equal". The `equal` field in `structuredContent` is not flipped either, so a
machine client consuming the typed result gets the wrong boolean. The note is
disclosed in `text`, but the answer itself is wrong and cannot be trusted.

### NLP-1 — `NLP` / `LIMIT` — no English phrasing for a negated equivalence is understood
**Severity:** NLP
_Original classification: `NLP / LIMIT`._
**Expected:** _not recorded_
**Reproduce:**

**Reproducer:**
```sh
timeout 30 $ROOT/ucas --mcp < mcp_inv_negation.jsonl \
  | grep -o '"ucas": "[^"]*"\|"message": "[^"]*"' | grep -E 'different|not equal|not the same|differ from|not equal|unbounded'
```

**Observed:** (`mcp_inv_negation.out`, ids 3, 4, 7, 8, 19, 26, 21):

```
[3]  "is x times x different from x squared for an unsigned byte x"    -> not_understood: I didn't follow "different from x squared for an unsigned byte x"
[4]  "is x times x not equal to x squared for an unsigned byte x"      -> not_understood: I didn't follow "not equal to x squared for an unsigned byte x"
[7]  "is x plus 1 different from x for an unsigned byte x"             -> not_understood
[8]  "is x plus 1 not the same as x for an unsigned byte x"            -> not_understood
[19] "does x*x differ from x squared for an unsigned byte x"           -> not_understood
[26] "is x times x not the same as x squared for an unsigned byte x"   -> not_understood
[21] "is x*x unbounded for an unsigned byte x"                         -> not_understood
```

The only form that survives (`is x*x != x^2 ...`, ids 17–18) is translated to
`it(x: u8) = x*x != x^2 | show it`, i.e. it becomes a boolean-valued *function*
to display, not an `equiv` question with a true/false answer. Same for the
property-negation pair `bounded` / `unbounded`.

**Why it matters:** it is a bug / limitation:** the required CheckList negation pair
has no correct implementation in the frontend. Combined with F1, there is
currently no way to ask a negated equivalence and get a trustworthy answer.

### DETERMINISM-1 — `DETERMINISM` — MCP `english` response shape flips when stdout capture fails
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Reproduce:** re-run the same JSONL twice while `/tmp` is under space pressure
(it was at 91–100 % during this run); compare the first `english` response:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_checklist
for i in 1 2; do
  timeout 30 $ROOT/ucas --mcp < mcp_mft.jsonl 2>/dev/null \
    | grep -m1 '"statements"'
done
```

**Observed:** (two structurally different outputs for the identical request):

```
# run A — capture succeeded
"result":{"kind":"english","statements":["it(x: u8) = x^2","range it"],"understood":true, ...}
  content[0].text = "  ucas: it(x: u8) = x^2\n  ucas: range it\nrange of it -> u8:\n ..."
  structuredContent.text = "<the CLI transcript>"

# run B — capture failed
"result":{"kind":"english","statements":[],"understood":false, ...}
  content[0].text = "{\"kind\": \"english\", \"statements\": [], \"understood\": false, ...}"
  structuredContent.text = ""
```

**Why it matters:** `jsonmode.c:cap_begin()` uses `tmpfile()` to capture the
English run's transcript; `jsonmode.c:3028` derives `statements` by scanning that
transcript for `  ucas: ` lines. When `tmpfile()` returns NULL (e.g. ENOSPC),
`cap_end()` returns an empty string, so `statements` becomes `[]`, `understood`
becomes `false`, and `mcp.c:answer()` falls back to serialising `result` as the
text content. The same English sentence therefore changes not just its `text`
but the **typed fields a client relies on**. This makes every `mcp_*.jsonl`
English golden sensitive to host `/tmp` capacity. Not kept as a golden; the
committed `.out` files were regenerated in a healthy-`/tmp` window and checked
twice for stability.

### NLP-2 — `NLP` (INV violation) — all-caps changes the variable name in the translation
**Severity:** NLP
_Original classification: `NLP (INV violation`._
**Expected:** _not recorded_
**Reproduce:**

**Reproducer:**
```sh
grep '"id": 5,' mcp_inv_casepunct.out | cut -c1-260
```

**Observed:**

```
"WHAT IS THE RANGE OF X SQUARED FOR X AN UNSIGNED BYTE"
  -> "ucas: it(X: u8) = X^2" ...   (statements: ["it(X: u8) = X^2", "range it"])

"what is the range of x squared for x an unsigned byte"
  -> "ucas: it(x: u8) = x^2" ...   (statements: ["it(x: u8) = x^2", "range it"])
```

Also id 13 (`IS X TIMES X THE SAME AS X SQUARED ...` → `it(X: u8) = X*X | that(X: u8) = X^2 | ...`) and id 21 (`WHERE IS 1/X DEFINED ...` → `it(X: u8) = 1/X | domain it`). Title case, extra/trailing whitespace, leading `?` and trailing `?`/`.` all produced **byte-identical** statements.

**Why it matters:** capitalization is a meaning-preserving rewrite, but the
generated ucas is not identical — the free variable is renamed `x` → `X`. The
math is equivalent, so this is a translation-stability (INV) defect rather than a
wrong answer.

### NLP-3 — `NLP` / `LIMIT` — several meaning-preserving word orders and a comma are rejected
**Severity:** NLP
_Original classification: `NLP / LIMIT`._
**Expected:** _not recorded_
**Reproduce:**

**Reproducer:**
```sh
timeout 30 $ROOT/ucas --mcp < mcp_inv_wordorder.jsonl \
  | grep -o '"ucas": "[^"]*"\|"message": "I don.t[^"]*"' | grep -B1 -A0 "sorry\|I don"
```

**Observed:** (all `not_understood`; `mcp_inv_wordorder.out` ids 2, 3, 6, 10, 13, 15, 18, 22):

```
[2]  "what is the range, for x an unsigned byte, of x squared"       -> I didn't expect ',' here
[3]  "for x an unsigned byte, what is the range of x squared"        -> I don't understand "for x an" here
[6]  "x squared: what is its range for an unsigned byte x"           -> not_understood
[10] "for an unsigned byte x, are x times x and x squared the same"  -> not_understood
[13] "for x an unsigned byte, where is 1/x defined"                  -> not_understood
[15] "with respect to x, the derivative of x squared"                -> not_understood
[18] "for a signed byte x, does x times 2 overflow"                  -> not_understood
[22] "for x an unsigned byte, show a table of x squared"             -> not_understood
```

**Why it matters:** it is a limitation:** all of these carry exactly the same meaning as the
canonical phrases (which are understood). A fronted `for <type> x` clause, a
fronted `with respect to x`, or an appositive comma is enough to make the parser
give up. Minor robustness LIMIT, not a wrong answer or crash.

### LIMIT-1 — `LIMIT` — some natural-language synonyms / intent phrasings are not supported
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproduce:**

**Reproducer:**
```sh
timeout 30 $ROOT/ucas --mcp < mcp_inv_syn.jsonl \
  | grep -o '"id": 22,"result".*' | cut -c1-260
```

**Observed:**

```
[22] "what are the extrema of x cubed minus 3x" -> error (ambiguous):
     I don't know the word "extrema"
```

Further probes (not in goldens): "the best constant approximation to x^2 over
0..1" and "a constant approximation ..." → `I don't know the word
"approximation"`; "what is the minimum of x^2 - 2x ..." → `"minimum" needs two
or more things, joined by "and"`; "gates for x & y for unsigned 2-bit x ..." is
supported, but `gates` rejects > 6 input bits (`gates handles up to 6 input bits
(16 here)`).

**Why it matters:** it is a limitation:** the MFT intent "best constant" has no English
frontend path (the `approx`/`fit` ucas commands are needed), and `extrema` is not
a recognised synonym of `critical points` even though `slope`/`differential`
are recognised synonyms of `derivative`.

### NLP-4 — `understood:false` with a fully valid result
**Severity:** NLP
_Original classification: `NLP (minor`._
**Expected:** _not recorded_
**Reproduce:**

**Reproducer:**
```sh
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"english","arguments":{"text":"integrate x^2 from 0 to 1"}}}' \
 | timeout 15 $ROOT/ucas --mcp | grep -o '"statements": \[[^]]*\]\|"understood": [a-z]*\|"antiderivative": "[^"]*"'
```

**Observed:**

```
"statements": []        "understood": false        "antiderivative": "x^3/3"
```

The response contains a complete `integrate` result (antiderivative `x^3/3`,
definite value `1/3`, check `d/dx` at 401 points) yet reports `understood:false`
and an empty `statements` list. The same request phrased as "the integral of x
squared times sin x from 0 to pi" reports `understood:true` with
`["it(x: i8) = x^2*sin(x)", "integrate it from 0 to pi"]`.

**Why it matters:** the typed "did the frontend understand this?" flag
contradicts the presence of a correct, checked answer. A client that gates on
`understood` would discard a valid result.

## Checks that passed

### Checks that passed (no issue)
- **DIR – narrowed range never increases the sampled point count.** `mcp_dir_range.out`:
  `256 → 16` points for `x^2`, `256 → 16` for `2x`, `256 → 16` for `x^2-2x`
  (ids 1→2, 4→5, 6→7); "how big can ... get" gives the same 16.
- **DIR – adding a `where` condition never widens the domain.**
  `mcp_dir_domain.out`: defined points `255 → 10`, `255 → 19`, `255 → 10`
  (ids 1→2, 4→5, 6→7).
- **DIR – cheapest cost ≤ original and ≤ any larger `find`.**
  `mcp_dir_cost.out`: original `cost = 12`; first implementation of `find 1`,
  `find 3`, `find 10` all cost `7` (≤ 12).
- **INV – synonym families are stable.** In `mcp_inv_syn.out`: `range`/`how big
  can` → identical `it(x: u8) = x^2 | range it`; `times`/`multiplied by` →
  identical `x*x`; `overflow`/`wrap around`/`have undefined behavior`/`cause ub`
  → identical `it(x: i8) = x*2 | wrap it`; `the same as`/`identical to`/
  `interchangeable with` → identical `equiv it that`; `derivative`/`slope`/
  `differential` → identical `diff it x`; `integer square root`/`isqrt` →
  identical `isqrt(x)`. `x squared` and `x^2` are identical, while `x*x` is a
  different (but provably equivalent) AST.
- **No crashes, hangs, or nonzero exits.** Every `.ucas` and `.jsonl` file ran to
  completion under `timeout 30` with exit 0; all English failures were structured
  JSON-RPC `isError:true` responses, not process failures.
- **Determinism:** every committed `.out` was regenerated and re-run byte-for-byte
  identical (twice each) once `/tmp` had space (see F3 for the caveat).
