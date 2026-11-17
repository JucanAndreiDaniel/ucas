# Stress findings — `nlp_british_dialect`

_Original heading: FINDINGS — NLP frontend, English dialect / spelling variation_

# FINDINGS — NLP frontend, English dialect / spelling variation

Area: `nlp_british_dialect`. All queries go through the MCP `english` tool
(translate English -> ucas statements -> run). The "baseline" for each comparison
is the same request in clean standard English; we compare the emitted
`structuredContent.result.statements` array and `understood`/`error` fields.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 5 | number-word parser adds instead of multiplying when two scale words are present |
| NLP | 7 | US spelling `factor` routes differently from `factorise`/`factorize` |
| LIMIT | 2 | supported number-word vocabulary is small / scale defaulted to short scale |

## Findings

### WRONG-1 — number-word parser adds instead of multiplying when two scale words are present
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "one thousand million"` (also in `mcp_number_words.jsonl`)

**Observed:** (`structuredContent.result.statements`, `text`):
```
understood=true, statements=["1001000"]
  ucas: 1001000
1001000
```
**Expected:** `1000000000` (one thousand millions = 10^9). The last scale word is
silently added to, not multiplied with, the preceding quantity. Systematic:

| query | emitted statement | mathematically correct |
|---|---|---|
| `one thousand million` | `1001000` | `1000000000` |
| `two thousand million` | `1002000` | `2000000000` |
| `one hundred thousand million` | `1100000` | `100000000000` |
| `one million million` | `2000000` | `1000000000000` |
| `two million million` | `3000000` | `2000000000000` |
| `one billion billion` | `2000000000` | `1000000000000000000` |
| `one million million million` | `3000000` | `10^18` |

This is an unsound translation: it returns `ok:true` with a confidently wrong
integer. Relevant to the billion-scale ambiguity: the "British" way of saying
10^9 (`one thousand million`) is parsed as ~10^6, while `one billion` is read as
the American short scale 10^9.

### WRONG-2 — `one billionth` silently read as `one billion`
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "one billionth"`

**Observed:**
```
  note: read "billionth" as "billion"
  ucas: 1000000000
1000000000
```
`statements=["1000000000"]`. Expected 10^-9 (or `1/1000000000`). The ordinal is
silently defaulted to the cardinal, an unsound reading with a note rather than
an error. `one billionth of x` then fails: `not_understood: I didn't follow "of x"`.
Contrast `one over a billion` -> `1/1000000000` (correct).

### WRONG-3 — unknown word in verb position silently becomes a variable (`ok:true`, no ucas statement)
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "a billion"` (and `q "normalise x+x"`, `q "centre x^3"`, `q "simplfy x+x"`)

**Observed:**
```
understood=false, ok=true, statements=[], no note, no "sorry"
_(a: real, billion: real) = a*billion
  -> real
```
There is no emitted ucas statement and no error, yet `ok:true`: the frontend
silently invents an implicit function with the unknown English words as variable
names. Same for:
- `a million` -> `_(a: real, million: real) = a*million`
- `a dozen` -> `_(a: real, dozen: real) = a*dozen`
- `normalise x+x` -> `_(normalise: real, x: real) = normalise*x + x`
- `normalize x+x` -> `_(normalize: real, x: real) = normalize*x + x`
- `centre x^3` -> `_(centre: real, x: real) = centre*x^3`
- `simplfy x+x` -> `_(simplfy: real, x: real) = simplfy*x + x`

**Expected:** either proper translation (`a billion` = `1000000000`) or an explicit
`not_understood`. Instead a bogus function is returned with no diagnostic —
exactly the "silent default reading" failure mode.

### WRONG-4 — hyphen in a number word silently read as subtraction
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "ninety-nine billion"`

**Observed:**
```
_(ninety: real, nine: real, billion: real) = ninety - nine*billion
  -> real
```
`understood=false, statements=[]`. Compare `q "ninety nine billion"` -> `99000000000`.
The hyphenated British/standard form is mis-parsed into a bogus expression
`ninety - nine*billion` with no diagnostic.

### WRONG-5 — semicolon immediately after the verb drops the verb
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "differentiate; x squared"` (also in `mcp_punctuation.jsonl`)

**Observed:**
```
  sorry: the sentence ends where I expected a value
  ucas: it(x) = x^2
  ucas: show it
it(x: real) = x^2
  -> real
```
`statements=["it(x) = x^2","show it"]`, `err=not_understood`. Expected
`diff it` (the baseline `differentiate x squared` -> `['it(x) = x^2','diff it']`).
The `;` is a valid command separator elsewhere (`differentiate x squared; find its
range` correctly emits `['it(x) = x^2','diff it','range it']`), so a trailing
separator after a verb silently changes the operation to `show`.

### NLP-1 — US spelling `factor` routes differently from `factorise`/`factorize`
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "factor x^2-1"` vs `q "factorise x^2-1"`

`factor x^2-1`:
**Observed:**
```
understood=false, statements=[]
factor x^2 - 1
  = (x - 1)*(x + 1)
  check: exact (both sides have the same normal form)
```
`factorise x^2-1`:
```
understood=true, statements=["factor x^2-1"]
  ucas: factor x^2-1
factor x^2 - 1
  = (x - 1)*(x + 1)
```
The American spelling takes a raw-command fallback path (no ucas statement emitted,
`understood=false`) while the British spellings `factorise`/`factorize` produce a
proper `factor` statement. Same meaning, different translation/routing.

### NLP-2 — British `analyse` mis-normalised to the noun `analysis`
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "analyse x squared"` (also in `mcp_british_spelling.jsonl`)

**Observed:**
```
  note: read "analyse" as "analysis"
  sorry: I didn't follow "x squared"
```
`err=ambiguous`, message `I don't know the word "analysis"`. The British verb
`analyse` is rewritten to the noun `analysis` and then rejected. Baseline
`what do you make of x squared` -> `['it(x) = x^2','show it']`.

### NLP-3 — misspellings accepted inconsistently
**Severity:** NLP
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The frontend has fuzzy matching for many misspellings (e.g. `differntiate`,
`differnetiate`, `derivitive`, `derivatave`, `equivlent`, `equivelent`,
`equivilent`, `gradiant`, `hessien`, `lapacian`, `wronksian`, `tayor`, `peroid`,
`symetry`, `continuos`, `criticle`, `injevtive`, `assymptotes`, `asymtotes`,
`raneg`, `milion`, `milllion`, `biliion`, `thausand`, `hunderd` all translate
identically to their clean baselines). But close variants of the **same** words
fail — inconsistent coverage:

| misspelling | result | clean baseline emits |
|---|---|---|
| `differentiat x squared` | ambiguous `"differentiat" is not a word I know` | `diff it` |
| `integrel x from 0 to 1` | `not_understood: of what?` (noun form `the integrel of x^2` *works*) | `integrate it` |
| `integrell x squared` | ambiguous `"integrell" is not a word I know` | `integrate it` |
| `is x^2 equivellant to x*x` | `not_understood: I didn't follow "equivellant to x*x"` | `equiv it that` |
| `the asimtotic behaviour of 1/x` | note `read "asimtotic" as "asymptotic"` then ambiguous on `behaviour` | `asymptotes it` |
| `is x^2 convext` | ambiguous `"convext" is not a word I know` | `convexity it` |

**Reproducer:**
Reproducer e.g. `q "differentiat x squared"`.

### NLP-4 — archaic / formal phrasing universally not understood
**Severity:** NLP
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "thou shalt differentiate x squared"`, `q "please be so kind as to differentiate x squared"`, `q "prithee, what is the integral of x"`.

- `thou shalt ...` -> ambiguous `I don't know the word "thou"`
- `please be so kind as to ...` -> `not_understood: I don't understand "be so kind" here`
- `would you be so good as to ...`, `I beseech thee to ...`, `hark, ...`,
  `if it please you, ...`, `most humbly, ...`, `wherefore art thou ...`,
  `condescend to ...`, `vouchsafe to ...`, `prithee, ...`, `do thou ...`
  all fail (`not_understood`/`ambiguous`).
- `kindly differentiate x squared` is the one polite form that works
  (-> `['it(x) = x^2','diff it']`).

None of these should be expected to work semantically, but they are included to
show the frontend has no register/politeness handling; they fail at the first
formal word rather than extracting the math request.

### NLP-5 — regional synonyms not understood; `whilst` clause emits a malformed ucas statement
**Severity:** NLP
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "whilst find the range of x squared"`, `q "solve x^2=4, whilst x is real"`.

- `whilst` (leading/trailing), `amongst`, `perchance`, `hereafter`, `henceforth`,
  `whereupon`, `thereof`, `therein`, `forthwith` all fail
  (`I don't know the word "whilst"/"perchance"/"amongst"` or
  `I didn't follow "..."`). Their plain synonyms (`while`-clauses, `perhaps`,
  `among`) are also not supported, so there is no consistent synonym layer.
- `find the range of x squared whilst x is positive` ->
  `not_understood: I didn't follow "whilst x is positive"` (the core request is
  dropped).
- `solve x^2=4, whilst x is real` ->
  `statements=["solve x^2 = 4, whilst x is real"]`, `ok=false`,
  `err=ambiguous: "is" read as i*s (single-letter variables)`. The frontend emits
  a **malformed ucas statement** containing raw English (`whilst x is real`) as
  if it were code, instead of rejecting it.

### NLP-6 — punctuation conventions change the translation or break parsing
**Severity:** NLP
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "differentiate x squared!"`, `q "(differentiate x squared)"`, `q "DIFFERENTIATE X SQUARED"`.

| query | statements | note |
|---|---|---|
| `differentiate x squared` (baseline) | `['it(x) = x^2','diff it']` | — |
| `differentiate x squared.` | same | trailing `.` fine |
| `Differentiate x squared` | same | capitalisation fine |
| `differentiate x squared?` | same | `?` fine |
| `differentiate x squared  ` (trailing spaces) | same | fine |
| `differentiate  x  squared` (double spaces) | same | fine |
| `differentiate x squared!` | `[]`, `not_understood: I didn't follow "!"` | `!` breaks it |
| `differentiate, x squared` | `[]`, `not_understood: I didn't expect ',' here` | comma after verb |
| `(differentiate x squared)` | `[]`, `ambiguous` | parentheses |
| `differentiate 'x squared'` / curly quotes | `[]`, `not_understood` | quoting expression |
| `DIFFERENTIATE X SQUARED` | `['it(X) = X^2','diff it']` | all-caps changes the variable from `x` to `X` — a different symbol |
| `solve x^2 = 4` vs `solve x^2=4` | `solve x^2 = 4` vs `solve x^2=4` | whitespace preserved in emitted statement |

(See `mcp_punctuation.jsonl`.)

### NLP-7 — "and" between number words rejected, while "plus" works
**Severity:** NLP
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "one billion and one"` vs `q "one billion plus one"`.

- `one billion and one` -> `ambiguous: "and"/"or" between numbers`, no statement.
- `one billion plus one` -> `['1000000000 + 1']`.
- `one thousand and one` -> `['1001']` (works for small numbers) — so the
  `and` rule is inconsistent across magnitudes.
- `one and a half billion` -> `not_understood: I didn't follow "billion"`.

### LIMIT-1 — supported number-word vocabulary is small / scale defaulted to short scale
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- `one trillion`, `half a trillion` -> ambiguous `"trillion" is not a word I know`.
- `one milliard` (the long-scale word for 10^9) -> `not_understood`.
- `one crore`, `one hundred crore`, `ten lakh` -> `not_understood`.
- `a score`, `a dozen`, `a gross` -> a gross gives `144`, but `a score`/`a dozen`
  silently become bogus implicit functions (see WRONG above).
- `one billion` alone is always read as short-scale 10^9; there is no way to ask
  for the British long-scale 10^12 (`one million million` is mis-parsed as
  `2000000`, see WRONG).

### LIMIT-2 — control characters in `text` are rejected by the tool schema
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer: `q "differentiate	x squared"` (literal tab) or a trailing newline.
**Observed:**
```
ok=false, err=bad_request,
msg: "text: one line of ucas text, without newlines, control characters or '#'"
```
This is the documented input constraint, not a crash; recorded so punctuation/
whitespace fuzzing does not misreport it. Exit code is 0.

## Checks that passed

### Reproducer helper
Paste this once, then any finding is reproducible with `q "<english text>"`:

```sh
q() { printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"english\",\"arguments\":{\"text\":\"$1\"}}}" \
| timeout 15 $ROOT/ucas --mcp; }
```

Full multi-query sessions are checked in as `mcp_*.jsonl` + deterministic `.out`;
re-run with:
`cd $ROOT/tests/stress/areas/nlp/nlp_british_dialect && timeout 30 $ROOT/ucas --mcp < mcp_number_words.jsonl`

### Non-findings (checked, none observed)
- **CRASH / HANG**: none. Every one of the ~236 queries in the comparison set
  and all exploratory probes exited 0 within the 15 s timeout; no truncated JSON,
  no signal, no timeout.
- **DETERMINISM**: none of the checked-in goldens vary. Each `mcp_*.out` was
  generated twice and the two runs were byte-identical (`diff -q` clean), and a
  third run reproduced the checked-in `.out` exactly.

### Coverage note
Many misspellings and British spellings are handled correctly and produce exactly
the baseline statements: `factorise`/`factorize`, `centre of symmetry`,
`visualise`/`visualize`, `differntiate`, `derivitive`, `equivlent`,
`assymptotes`, `gradiant`, `hessien`, `wronksian`, `tayor`, `peroid`, `symetry`,
`continuos`, `criticle`, `injevtive`/`surjevtive`/`bijevtive`, `milion`,
`biliion`, `thausand`, `hunderd`, `gcf`, `resultent`, `discriminent`, `fracions`,
`raneg`. The failures above are the exceptions, reported because they are the
ones that change meaning or silently fail.
