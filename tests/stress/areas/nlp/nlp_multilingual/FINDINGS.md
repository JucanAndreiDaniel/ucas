# Stress findings — `nlp_multilingual`

_Original heading: Findings — `nlp_multilingual` stress area_

# Findings — `nlp_multilingual` stress area

Focus: language variation in the English frontend. ~207 distinct English / multilingual /
code-switched / symbol queries were tried through MCP `english` and the CLI. The invariant
checked was: **the frontend must either parse correctly, or report "not understood" — never
silently emit a wrong statement.** Graceful refusals are not bugs; the items below are.

All commands are copy-pasteable. Binary: `$ROOT/ucas`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | 1 — WRONG: non-English "sentence" without `?` silently becomes a bogus definition |
| LIMIT | 4 | 4 — LIMIT: fuzzy "misspelling correction" misroutes foreign/archaic words |
| DETERMINISM | 1 | 1 — DETERMINISM: one-off empty-capture MCP run silently drops every answer |

## Findings

### WRONG-1 — 1 — WRONG: non-English "sentence" without `?` silently becomes a bogus definition
**Severity:** WRONG
**Reproducer:**
**Observed:**
```sh
printf 'integriere x zum quadrat von 0 bis 1\n' | timeout 10 $ROOT/ucas
```
Exact output:
```
_(integriere: real, x: real, zum: real, quadrat: real, von: real, bis: real) = 0
  -> real
```
MCP evidence (`mcp_multilingual.out`, id 5):
```json
{"id":5,"ok":true,"cmd":"english","result":{"kind":"english","statements":[],"understood":false,
"results":[{"kind":"show","definition":"_(integriere: real, x: real, zum: real, quadrat: real, von: real, bis: real) = 0","body":"0","type":"real"}]},
"notes":[],"text":"_(integriere: real, x: real, zum: real, quadrat: real, von: real, bis: real) = 0\n  -> real\n"}
```
**Why it matters:** a bug: the backend itself records `understood:false` / `statements:[]`, yet returns
`ok:true` and *emits an assertion* that a function of six real variables is identically `0`.
A German request ("integrate x squared from 0 to 1") is silently turned into a false
statement.
**Expected:** `not_understood` (or `ambiguous` on the unknown word), as happens when
the same query ends in `?`. Adding the `?` gives the correct graceful behaviour:
```sh
printf 'integriere x zum quadrat von 0 bis 1?\n' | timeout 10 $ROOT/ucas
# -> error (ambiguous): I don't know the word "integriere" ...
```

Same class, more refusals-that-should-have-been (all from `02_silent_misparse.out`):
```sh
printf 'berechne 2 hoch 10\n'             | timeout 10 $ROOT/ucas
# _(berechne: real, hoch: real) = 10(2berechne*hoch)
printf 'die quadratwurzel von 16\n'       | timeout 10 $ROOT/ucas
# _(die: real, quadratwurzel: real, von: real) = 16(die*quadratwurzel*von)
printf 'hello world\n'                    | timeout 10 $ROOT/ucas
# _(hello: real, world: real) = hello*world
printf 'foo bar baz qux\n'                | timeout 10 $ROOT/ucas
# _(foo: real, bar: real, baz: real, qux: real) = foo*bar*baz*qux
```
Mechanism: a line whose **first** token is not a known English keyword is treated as a bare
ucas expression (implicit multiplication), so arbitrary foreign/unknown words become free
variables and a "definition" is emitted. Known-English first tokens ("the quick brown fox…",
"to be or not to be") instead fail gracefully.

### WRONG-2 — 2 — WRONG: Latin abbreviation `cf.` silently becomes a variable
**Severity:** WRONG
**Reproducer:**
**Observed:**
```sh
printf 'cf. x squared minus one\n' | timeout 10 $ROOT/ucas
```
Exact output:
```
  ucas: it(cf, x) = cf*x^2 - 1
  ucas: show it
it(cf: real, x: real) = cf*x^2 - 1
  -> real
```
**Why it matters:** a bug: `cf.` (Latin *confer*) is parsed as a free variable `cf`; the request "compare x²−1"
becomes the unrelated claim "a function `cf*x²-1`". `understood:true` is set in the MCP result
even though nothing comparable was asked.
**Expected:** not-understood, or a note. Related:
`i.e.`/`e.g.`/`a.k.a.` do fail gracefully ("I didn't follow …"), so `cf.` is inconsistent.
`q.e.d.` gives a bare `parse_error` on the internal '.'.

### WRONG-3 — 3 — WRONG: foreign number words become variables, producing wrong arithmetic
**Severity:** WRONG
**Why it matters:** _not recorded_
Reproducers:
**Observed:**
**Reproducer:**
```sh
printf 'what is zero plus cero\n' | timeout 10 $ROOT/ucas
#   note: I don't know the word "cero": read as a variable, not a mistake (stop here) ...
#   ucas: it(cero) = 0 + cero
# it(cero: real) = cero
printf 'what is the square root of dieciseis\n' | timeout 10 $ROOT/ucas
#   ucas: it(dieciseis) = sqrt(dieciseis)
# it(dieciseis: real) = sqrt(dieciseis)
```
With MCP `defaults:true` this is even more explicit — `what is deux plus deux` →
`it(deux) = deux + deux`, `what is dos plus dos` → `it(dos) = dos + dos`, each with only a
"the default, a variable" note. Why a bug: "how much is 2+2 in Spanish/French" is answered
with a symbolic identity about an invented variable, not a refusal.
**Expected:** not-understood.
(Number words that are close to English are simply *misspell-corrected*: `seize`→`size`,
`thine`→`thing`, `hither`→`higher`, `verily`→`verify` — see NLP-4.)

### LIMIT-1 — 4 — LIMIT: fuzzy "misspelling correction" misroutes foreign/archaic words
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
printf 'combien fait 5 plus 3 ?\n' | timeout 10 $ROOT/ucas
```
Exact output:
```
  note: read "combien" as "combine"
  note: I don't know the word "combine": read as a variable, not a mistake (stop here) (rephrase it, or name variables with one or two letters)
  sorry: I didn't follow "fait 5 plus 3"
```
**Why it matters:** notable: French *combien* ("how much") is rewritten to English *combine*. Other observed
misroutes: `hither`→`higher`, `verily`→`verify`, `thine`→`thing`, `seize`→`size`,
`derivee`→`derive`, `world`→`word`. Some corrections are beneficial (`rango`→`range`,
`derivada`→`derivate`, `simplifie`→`simplified`, `facteurise`→`factorise`, `quadrat`→
`quadratic`, `fonction`→`function`) and parse correctly — the correction dictionary is
unprincipled across languages. No crash; documented as a LIMIT.

### LIMIT-2 — 1 — LIMIT: `?` flips behaviour from silent-misparse to graceful error
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (same tokens, only `?` differs):
**Observed:**
```sh
printf 'was ist der bereich von x zum quadrat?\n' | timeout 10 $ROOT/ucas
#   note: read "quadrat" as "quadratic"
#   sorry: I don't understand "was ist der" here        <- graceful
printf 'was ist der bereich von x zum quadrat\n'  | timeout 10 $ROOT/ucas
# (falls through to a bare expression / definition instead of refusing)
```
The frontend decides "English request" from punctuation ("ends in '?', starts with '?', or
reads like a sentence"). A trailing `?` is the difference between a refusal and a wrong
statement; a translated request that forgets the `?` silently misparses.

### LIMIT-3 — 2 — LIMIT: trailing unreadable character executes the rest and *also* errors
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (MCP `english`, JSONL id 19 of `mcp_multilingual.jsonl`):
```
text: "what is the range of x squared? 🙂"
```
**Observed:** (MCP): `ok:false`, `error.code:"not_understood"` ("I can't read the character …"),
but `result.understood:true`, `statements:["it(x) = x^2","range it"]`, a full `range` result
and a `proof`, and `text` containing the whole range answer followed by `sorry: I can't read
the character …`. The valid prefix is executed and reported even though the request is
declared not understood.
**Expected:** a clean refusal with no side-effect output.

### LIMIT-4 — 3 — LIMIT: non-Latin scripts and most math glyphs are rejected with poor diagnostics
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Reproducers (all graceful, exit 0):
**Reproducer:**
```sh
printf 'x的平方的范围是什么\n'     | timeout 10 $ROOT/ucas
printf 'каков диапазон x в квадрате\n' | timeout 10 $ROOT/ucas
printf 'x के वर्ग की सीमा क्या है\n'   | timeout 10 $ROOT/ucas
printf 'ما هو نطاق س س المربع\n'   | timeout 10 $ROOT/ucas
```
**Observed:** `error (parse_error): unexpected character '?'` — the offending non-ASCII
character is rendered as a literal `'?'` (MCP `pos.col` is a 1-based *character* column, e.g.
col 2 for `x的…`, col 1 for Cyrillic/Arabic, col 3 for Devanagari). Spanish inverted punctuation
and accented Latin instead give `error (not_understood): I can't read the character '?'`.
Same `'?'`-substitution for `Σ`, `∫`, `∏`, `∬`, `∈`, `ℝ`, `²`-in-superscript-form (`2¹⁰`),
emoji and combining accents. Greek *names* work (`θ`, `α`, `β`, `γ`, `φ`, `ω`, `Σ`→variable
names), `x²`/`√x`/`≤`/`∞`/`|x|` parse fine; `∂` gives "I didn't expect '∂' here". All graceful;
no hang/crash observed even for 200 nested parentheses, 400-digit literals, emoji, or a
repeated 700-char request.

### DETERMINISM-1 — 1 — DETERMINISM: one-off empty-capture MCP run silently drops every answer
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Observed:** on the very first run that produced `mcp_multilingual.out` (evidence preserved at
`/tmp/opencode/mcp_compact_anomaly_evidence.txt`, captured before regeneration). For *every*
successful request the response became:
**Reproducer:**
```json
{"id":1,"ok":true,"cmd":"english","ucas":"what is the rango of x squared",
"result":{"kind":"english","statements":[],"understood":false,
"results":[{"kind":"range","empty":false,"min":0,"max":100,"points":20001,
"method":"grid, extrema refined at critical points"}]},
"notes":[],"text":""}
```
i.e. `ok:true` and a `range` *result object*, but `text:""`, `statements:[]`,
`understood:false` and **no notes** (so the "read rango as range" note vanished too). Error
cases in that same run still had full error text. `src/mcp.c` explains the shape: when the
captured `text` is empty it JSON-prints `resp.result` into `content[0].text`; `src/jsonmode.c`
sets `understood = (statements.length > 0)`. This is the empty-subprocess-capture path: the
English child produced no stdout in that server process, so successful answers were silently
dropped instead of being reported as failures. 124 subsequent serial runs, 20 more repeated
runs and 30 concurrent runs were all byte-identical (`md5 7e035211…`) and correct, so this is
a rare transient, not a stable reproducer — documented, **not** kept as a golden.

## Checks that passed

### Summary of severity
- WRONG / NLP: 3 findings — NLP-1 silent bogus definitions (including the
  `understood:false`/`ok:true` contradiction), NLP-2 `cf.`, NLP-3 number words.
- LIMIT: 4 findings (NLP-4 misroutes, LIMIT-1 `?` flip, LIMIT-2 partial execution, LIMIT-3 glyphs).
- DETERMINISM: 1 (one-off empty-capture run).
- CRASH / HANG: **none found** — every candidate returned exit 0 within its `timeout`.
