# Stress findings — `english_redos`

_Original heading: FINDINGS — area `english_redos`_

# FINDINGS — area `english_redos`

All commands use the absolute binary `$ROOT/ucas`.
202 distinct pathological-English queries were generated and run under
`timeout 15` (202 CLI + 23 MCP calls); see `measurements.tsv`. Every kept
golden (`.out`) was produced twice and `diff`-checked identical. No golden
contains timing data.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | exponential English parse for nested "X of the X of ..." compositional phrases [SEVERITY: … |
| NLP | 2 | ambiguity reports list only the FIRST ambiguity in a sentence; repeated triggers are silen… |
| LIMIT | 1 | hard sentence cap at 320 tokens; long flat repetition is rejected fast (not itself a hang) |

## Findings

### HANG-1 — exponential English parse for nested "X of the X of ..." compositional phrases [SEVERITY: HANG]
**Severity:** HANG
_Original classification: `HANG (ReDoS`._
Repeated *compositional* English phrases ("the sqrt of", "the log of", "the
inverse of", "the square root of", "the sign of", "the sin of", "the abs of")
make the English translator take time exponential in the nesting depth. This is
NOT protected by the 320-word sentence cap: the hanging inputs are only
**61 words**.

Exact CLI reproducer (verified twice, rc=124 = `timeout` killed it):

**Reproducer:**
```sh
python3 -c 'print("the sqrt of "*20 + "x")' | timeout 15 $ROOT/ucas
echo "rc=$?"     # rc=124
```

**Observed:** no output at all**, killed at `wall=15.019s`. The same happens for
each of these 61-word sentences:

```sh
for p in "the sqrt of " "the log of " "the inverse of " "the square root of "; do
  python3 -c "import sys;sys.stdout.write('$p'*20+'x\n')" | timeout 15 $ROOT/ucas
  echo "$p -> rc=$?"
done
# "the sqrt of "        -> rc=124, 15.021 s
# "the log of "         -> rc=124, 15.018 s
# "the inverse of "     -> rc=124, 15.027 s
# "the square root of " -> rc=124, 15.028 s   (81 words)
```

Measured growth for `("the sqrt of " * n + "x")`, median/single wall time:

| n (nested "sqrt") | words | time | result |
|---|---|---|---|
| 6  | 19 | 0.012 s | OK `it(x)=sqrt(sqrt(...))` |
| 10 | 31 | 0.064 s | OK |
| 11 | 34 | 0.104 s | OK |
| 12 | 37 | 0.294 s | OK |
| 13 | 40 | 0.527 s | OK |
| 14 | 43 | 0.801 s | `sorry: that sentence is too long for me` (arena cap hit) |
| 15 | 46 | 1.967 s | `... too long ...` |
| 16 | 49 | 4.066 s | `... too long ...` |
| 20 | 61 | **>15 s, TIMEOUT** | no output |

Time roughly doubles per extra nesting level (~2^n). The emitted expression
itself stays linear in size (`sqrt(sqrt(...sqrt(x)))`), so the cost is in the
translation algorithm, not in printing — a classic algorithmic-complexity /
ReDoS shape. `"the sign of "` shows the same curve but overflows the 256 KiB
string arena sooner: at n=12 it takes 0.284 s and still succeeds, at n=13 it
returns `sorry: that sentence is too long for me` after ~0.7 s, and deeper n
stays in that capped/time-wasting regime. MCP is affected identically — the
same `sqrt * 20` text sent to `english`/`--mcp` also TIMED OUT at 15.02 s.
A self-contained MCP reproducer:

```sh
python3 -c 'import json;print("\n".join(json.dumps(x) for x in [
 {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}},
 {"jsonrpc":"2.0","method":"notifications/initialized"},
 {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"english","arguments":{"text":"the sqrt of "*20+"x"}}}]))' \
 | timeout 15 $ROOT/ucas --mcp
# rc=124, no output
```

**Expected:** parsing a 61-word sentence should be fast (milliseconds) like the
other repetition shapes, or be rejected quickly.
**Why it matters:** an
unauthenticated English input can consume unbounded CPU (denial of service),
and the existing word/arena limits do not stop it. NOT added as a golden
(hang). Negative control: `("the negative of " * n + "x")` is linear — 0.014 s
at n=20 — so the defect is specific to the "`<word>` of" function-name path.

### LIMIT-1 — hard sentence cap at 320 tokens; long flat repetition is rejected fast (not itself a hang)
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The English tokenizer has `MAXW 320` (`src/nlp.c:358`); the 321st word makes
`push()` call `nfail("that sentence is too long for me")` (`src/nlp.c:376-377`).
Exact threshold for `("what is " + "a "*k + "x?")` measured: k=317 (320 words)
parses OK, k=318 (321 words) returns `sorry: that sentence is too long for
me`. CLI and MCP agree (`mcp_word_cap.jsonl` golden). Reproducer:

**Observed:**
**Reproducer:**
```sh
python3 -c 'print("what is " + "a "*400 + "x?")' | timeout 15 $ROOT/ucas
#   sorry: that sentence is too long for me
```

This is why the plain ReDoS shapes from idea #9 ("`a of `*400", "`what is `*1000",
"one one ...", etc.) do **not** hang — they are cut off in ~0.01 s. Important:
this cap does **not** protect against finding #1, which needs only 61 words.

### NLP-1 — ambiguity reports list only the FIRST ambiguity in a sentence; repeated triggers are silently defaulted
**Severity:** NLP
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
With several ambiguity-triggering words in one English sentence, MCP reports
only the first one via `error:"ambiguous"` and never offers the others. Kept in
`mcp_ambiguity_repeat.jsonl` (ids 3–5):

- id 3 `"is x odd and x sign and the range of x?"` → error reports only
  `"odd"` (key `question`, 2 readings). `sign` and `range` are never reported;
  the `text` even appends `sorry: I didn't follow "x sign and the range of x"`.
- id 4 `"is x even and x odd and x log and x sqrt?"` → only `"even"` is
  reported; `odd`, `log`, `sqrt` are hidden.
- id 5 `"is x odd and x even?"` → only `"odd"` reported.

CLI, by contrast, prints a `note:` for every occurrence (see
`09_ambiguity_words.out`, `06_alternating_synonyms.out`). Root cause is the
one-question-per-sentence guard (`clarify()` at `src/nlp.c:270`, `nlp_asked`).
**Why it matters:** an MCP client cannot discover the remaining ambiguities by
the documented `ambiguous` error, so it silently accepts the default for all
but the first. (Also visible: the `how` hint for the `even` ambiguity still
says `say "an odd function" or "always odd"` — guidance for the wrong word.)

### NLP-2 — alternating odd/even words fabricate a variable or fail after the first trigger
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Repeated/adjacent ambiguity words produce silent misparses (deterministic, kept
in `06_alternating_synonyms.out`):

**Reproducer:**
```sh
printf 'is x odd even?\nis x even odd?\n' | timeout 15 $ROOT/ucas
```

**Observed:**

```
> is x odd even?
  note: "odd": read as an odd function, ...
  sorry: I didn't follow "even"
> is x even odd?
  note: "odd": read as an odd function, ...
  ucas: it(x, even) = x*even
  ucas: parity it
parity it: 2 parameters; give the others values, e.g. parity it(x, 1)
```

`even` is silently demoted to a second variable parameter (`it(x, even) =
x*even`), changing a yes/no parity question into a 2-argument function. With a
long alternation (`"odd even "*n` through the corpus) the first trigger always
dominates and the rest become unparsed text or stray variables.

## Checks that passed

### Non-issues (measured, no bug)
- **No crash, no nonzero exit, no hang** in the 202-query flat-repetition
  corpus (`measurements.tsv`): all `rc=0` (the only non-rc=0 were the two
  deliberately hung cases of finding #1). Max CLI time in that corpus was
  0.70 s (from nested `sign of`, finding #1); max MCP time 0.048 s.
- **Flat repetition scales linearly**: `a of *n`, `not *n`, `and`/`or *n`,
  `what is *n`, number-word chains, `where`/`for *n`, and `odd and x *n`
  all stayed ≤0.08 s up to the word cap, with output length growing linearly
  with the number of repeated tokens. No quadratic/exponential blowup there.
- **Nested `the range of ...`, `the wrap of ...`** fail fast
  (`sorry: I don't understand "range of the" here`) at every depth — no blowup.
- All 12 golden `.out` files are byte-identical across two runs.
