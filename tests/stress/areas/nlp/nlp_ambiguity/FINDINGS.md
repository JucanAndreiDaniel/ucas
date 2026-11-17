# Stress findings — `nlp_ambiguity`

_Original heading: FINDINGS — area `nlp_ambiguity`_

# FINDINGS — area `nlp_ambiguity`

All commands use the absolute binary `$ROOT/ucas`.
~180 CLI English queries + ~60 MCP `english` calls were tried. No exit code
was nonzero and no call hung; the issues are wrong answers, bad notes/readings,
and wire-format corruption. All kept goldens were diff-checked twice.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `7/8 of 64` (a README-documented expression) parses as `7/(512(o*f))` |
| NLP | 5 | English function words silently become variable products (`o*f`, `i*t`) |
| LIMIT | 2 | `word` type ambiguity is reachable only through `range of a word x` |

## Findings

### WRONG-1 — `7/8 of 64` (a README-documented expression) parses as `7/(512(o*f))`
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf '7/8 of 64\n' | timeout 15 $ROOT/ucas 2>&1
```

**Observed:**

```
  note: 'of' read as o*f (single-letter variables)
  note: 7/512(o*f) read as 7/(512(o*f)); write (7/...)... for the other reading
_(o: real, f: real) = 7/(512(o*f))
  -> real
```

The README (English "Expressions") explicitly lists `7/8 of 64` as meaning
**56**. Here the preposition "of" is read as the product of single-letter
variables `o*f`, so the documented expression silently produces a bogus
2-variable function. Kept in `04_scope_juxtaposition.out` and
`06_it_juxtaposition.out`.

### NLP-1 — English function words silently become variable products (`o*f`, `i*t`)
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Reproducers:

**Reproducer:**
```sh
printf 'wrap of x+1\n'     | timeout 15 $ROOT/ucas 2>&1
printf 'make it faster\n'  | timeout 15 $ROOT/ucas 2>&1
printf 'it\n'              | timeout 15 $ROOT/ucas 2>&1
```

**Observed:** (fresh process each time):

```
  note: 'of' read as o*f (single-letter variables)
wrap analysis of o*f*x + 1: ...
  note: 'it' read as i*t (single-letter variables)
_(make: real, i: real, t: real, faster: real) = make*(i*t)*faster
  note: 'it' read as i*t (single-letter variables)
_(i: real, t: real) = i*t
```

`wrap of x+1` is meant to analyse wrapping of `x+1` (compare with the
correct `the wrap of x+1`, which produces the intended `it(x)=x+1; wrap it`).
`make it faster` is a documented code-block request; with no referent it
becomes a meaningless product. `it` is documented as "the last function" but
is read as `i*t` when none exists. These are silent misparses (only a terse
`note:`), not errors. Kept in `04_scope_juxtaposition.out` and
`06_it_juxtaposition.out`.

### NLP-2 — MCP `juxtaposition` ambiguity offers the WRONG two readings
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (`mcp_ambiguity_juxtaposition.jsonl`, ids 4–5):

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_ambiguity
timeout 30 $ROOT/ucas --mcp < mcp_ambiguity_juxtaposition.jsonl > /tmp/x.out 2>&1
```

**Observed:** for `english "7/8 of 64"` (id 4):

```json
"error": {"code":"ambiguous","key":"juxtaposition","readings":[
  {"index":1,"reading":"product","default":true},
  {"index":2,"reading":"one name","default":false}], ...}
```

Reading 1 (`product`) reproduces the wrong `7/(512(o*f))`; reading 2
(`one name`) stays ambiguous ("needs different input"). **Neither reading is
the intended one** — the English preposition "of" (fraction-of / possessive)
is not offered at all, so no `args.assume.juxtaposition` value can recover the
documented answer 56. Same bad readings for `wrap of x+1` (id 6) and
`make it faster` (id 8). This is an "incorrect/incomplete readings" defect.

### WRONG-2 — MCP JSON response contains invalid UTF-8 (raw 0xf0 byte) for non-ASCII input
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (self-contained):

```sh
cd /tmp/opencode
cat > emoji.jsonl <<'EOF'
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"english","arguments":{"text":"😀 is x even? 🎉"}}}
EOF
timeout 30 $ROOT/ucas --mcp < emoji.jsonl > emoji.out 2>&1
python3 -c 'open("emoji.out","rb").read().decode("utf-8")'   # raises
```

**Observed:** the response line contains the single raw byte `0xf0` (the first
byte of the 4-byte UTF-8 encoding of 😀) inside the error message:

```
... "text": "error (not_understood): I can't read the character '\xf0'\n\n  sorry: ...
```

`python3` raises `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf0 ...:
invalid continuation byte`. A strict JSON parser rejects the whole reply.
The CLI echoes the first byte instead of the full code point. NOT added as a
golden `.out` because it would inject invalid UTF-8 into the repo.

### NLP-3 — MCP reports only the FIRST ambiguity in a sentence; the rest default silently CLI-side
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (`mcp_ambiguity_juxtaposition.jsonl`, ids 15–16):

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_ambiguity
timeout 30 $ROOT/ucas --mcp < mcp_ambiguity_juxtaposition.jsonl > /tmp/x.out 2>&1
```

**Observed:**
- `english "is x odd and the log of y?"` (id 15) → `ambiguous` with
  `key:"question"` (odd) **only**; the `log` ambiguity is never reported.
- `english "is x odd and the log of y?", assume.question:1` (id 16) →
  `not_understood: I didn't follow "the log of y"`, still with **no**
  `ambiguous log` error.

Source cause: `clarify()` in `src/nlp.c` has `if (nlp_asked) return dflt;`
(one question per sentence in MCP/rep mode). The CLI, by contrast, prints a
`note:` for every ambiguity. So a single English sentence with two ambiguous
words hides all but the first from an MCP client, which can never discover the
second ambiguity by the documented `ambiguous` error.

### NLP-4 — `modular inverse of 3`: the default spelling correction breaks the parse
**Severity:** NLP
_Original classification: `NLP/LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (`mcp_ambiguity_juxtaposition.jsonl`, ids 1–3):

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_ambiguity
printf 'modular inverse of 3\n' | timeout 15 $ROOT/ucas 2>&1
```

**Observed:** (CLI):

```
  note: "modular" is not a word I know: read as modulo, not modulus or "modular" as written
  sorry: I don't understand "modulo inverse of" here
```

MCP: `ambiguous` key `spelling` with readings `modulo` (default), `modulus`,
`"modular" as written`. Answering `modulo` (the default) yields
`not_understood`; answering `modulus` yields the nonsense statement
`modulus 1/3`; answering `as written` yields an `unknown_word` ambiguity.
The documented phrasing is "inverse of 3 mod 256"; "modular inverse" is not
supported, but the *default* correction actively makes parsing fail rather
than being a harmless note.

### LIMIT-1 — `word` type ambiguity is reachable only through `range of a word x`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Reproducers:

**Reproducer:**
```sh
printf 'w is a word\n'          | timeout 15 $ROOT/ucas 2>&1
printf 'range of a word x\n'    | timeout 15 $ROOT/ucas 2>&1
```

**Observed:**

```
  sorry: I don't understand "w is a" here
  note: "word": read as 32 bits (ARM word), not 16 bits (x86 WORD) or 64 bits (machine word) ...
```

`x is a byte/char/int/integer` all work and emit their ambiguity note, but the
symmetric `w is a word` does not; the `word` ambiguity (and its MCP `key:"word"`
error) only appears in the `range of a word x` phrasing. Natural phrasing for a
declared word variable is rejected. Kept in `07_more_keys.out`.

### NLP-5 — odd/even hint text always says "odd", even for the "even" question
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf 'is x even?\n' | timeout 15 $ROOT/ucas 2>&1
```

**Observed:**

```
  note: "even": read as an even function, f(-x) = f(x), not an even number for every input (say "an odd function" or "always odd")
```

MCP (`mcp_ambiguity_answers.jsonl`, id 1) gives the same wrong hint in
`error.how`: `... or: say "an odd function" or "always odd"`. Source:
`src/nlp.c:5156` hardcodes the hint string for both odd and even. A user
following the note for an "even" question is told to say "an odd function" or
"always odd" — guidance for the wrong question. Kept in `01_odd_even.out`.

### LIMIT-2 — misc. English words silently demoted to variables
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Observed:** notes from the corpus (all exit 0, no error):

**Reproducer:**
```sh
the complex number z -> note: I don't know the word "complex": read as a variable ...
the char c          -> note: I don't know the word "char": read as a variable ...
the int x           -> note: I don't know the word "int": read as a variable ...
powers of 2         -> note: I don't know the word "powers": read as a variable ...
does the addition overflow? -> note: I don't know the word "addition": read as a variable ...
```

These produce meaningless functions instead of a clear `not_understood`.
Lower severity (a note is printed), recorded for completeness.

## Checks that passed

### Non-issues checked (deliberately kept as goldens, no bug)
- CLI default notes match MCP default readings for `odd/even`, `log`, `byte`,
  `char`, `int`, `integer`, `word`, `nbit`, `sqrt`, `not`, `andor`, `z`, and
  `spelling` (see `mcp_ambiguity_answers.out` and the CLI `*.out` files).
- Answering an ambiguity with `args.assume.KEY` using each reading changes the
  result as documented (`log`: ln / log2 / log10; `sqrt`: isqrt / sqrt(real);
  `byte`: u8 / i8; `andor`: `&` / `&&`; `odd/even`: parity / "% 2" range). Some
  answers reveal a second ambiguity (`untyped`) — captured in
  `mcp_ambiguity_answers.out` ids 3–4 and `mcp_ambiguity_juxtaposition.out`
  ids 13–14.
- No crashes, hangs, nonzero exits, or nondeterministic goldens were found in
  this area.
