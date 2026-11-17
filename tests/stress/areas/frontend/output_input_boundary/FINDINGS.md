# Stress findings — `output_input_boundary`

_Original heading: FINDINGS — `output_input_boundary`_

# FINDINGS — `output_input_boundary`

Focus: the seam where one ucas tool's OUTPUT becomes another tool's INPUT.
Driver: `driver.py` (421 chained steps, 13 groups); raw log: `driver_results.json`.
Every reproducer below was run with `timeout` from this folder with
`$ROOT/ucas`. Severity labels follow `SPEC.md`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | Machine-generated display text is not re-ingestible and installs bogus |
| NLP | 1 | ucas's own derivative output is misrouted through NLP and gives a WRONG |
| LIMIT | 2 | Self-amplifying error output (unbounded growth) — `LIMIT` |

## Findings

### LIMIT-1 — Self-amplifying error output (unbounded growth) — `LIMIT`
**Severity:** LIMIT
**Reproducer:**
Reproducer** (feed each generation's *entire* output back as the next source):

```sh
printf 'show sin(1)\n' | ucas > g0
for i in 1 2 3 4 5; do ucas < g$i > g$((i+1)) 2>&1; done
wc -c g0 g1 g2 g3 g4 g5
```

**Observed:** (byte counts, from group `K_amplification`):

```
gen0=29   gen1=58   gen2=248   gen3=917   gen4=3118   gen5=10111
```

The error text is re-echoed with `'` characters and `^` carets inside the next
error, so each generation roughly triples the output. gen1's 58-byte error:

```
<stdin>:1:3: error: unexpected '=>'
      -> real
      ^
```

gen2 already contains nested copies:

```
<stdin>:1:32: error: unexpected character '''
    <stdin>:1:3: error: unexpected '=>'
                                   ^
<stdin>:1:7: error: unexpected '=>'
          -> real
          ^
<stdin>:1:7: error: unexpected '^'
          ^
          ^
```

**Why it matters:** a bug:** the focus list explicitly asks for "self-amplifying errors". A
pipeline that auto-feeds ucas output back into ucas does not reach a fixed
point; it diverges ~3×/generation and will exhaust memory/disk.
**Expected:** a
parse error is a stable, bounded fixed point (re-feeding it yields the same or
a cleanly rejected, bounded message).
Note: exit code stays `0` even when the output is an error message.

### WRONG-1 — Machine-generated display text is not re-ingestible and installs bogus
**Severity:** WRONG
    hidden definitions — `WRONG`

The `text` field of many answers is prose/annotation that (a) fails to parse,
and (b) where it *does* parse, silently installs garbage definitions that
introspection does not report.

#### 2a. `-> TYPE` annotation line (the headline output→input failure)

**Observed:**
**Reproducer:**
```sh
printf 'show sin(1)\n' | ucas          # output: _() = 0.8414709848\n  -> real\n
printf '_() = 0.8414709848\n  -> real\n' | ucas
# <stdin>:1:3: error: unexpected '=>'
```

This reproduces for `show`, `parse`, `simplify`, `expand`, `factor`, `diff`,
`integrate`, `taylor`, `gcd`, `complex`, ... — 42/43 Group-A seeds fail on the
first or second re-ingestion. Golden: `01_show_text_feedback.*`.

#### 2b. Prose note lines parse into anonymous "functions"

`diff` prints the note `holds for every real x`. Feeding that line back:

```sh
printf 'holds for every real x\n' | ucas
# _(holds: real, for: real, every: real, real: real, x: real) = holds*for*every*real*x
#   -> real
```

A printed proof's last lines do the same:

```sh
printf 'tc: forall x y:int: x + y = y + x\nroute a: tc\n  rests on:\n    tc  (5 inferences)\naxioms used:\n' | ucas
# <stdin>:1:3: error: unexpected ':' after the statement
# ...
#   note: 'tc' read as t*c (single-letter variables)
# _(t: real, c: real, inferences: real) = t*c*5inferences
#   -> real
```

A `check:` note line yields `error: no theorem : (state it with: theorem :: ...)`.

#### 2c. The bogus definitions are invisible to introspection

In a single MCP session, after feeding `holds for every real x` (group
`J_state_leak`), the raw `ucas` tool prints the `_(holds: real, ...)` definition,
but `session state` and `session funcs` both report `functions: []` / empty
text. So a silent state change is unobservable through the documented
introspection surface.

**Why it matters:** a bug:** merely *displaying* an answer and pasting that display back must
not mutate state; and any definition that is installed should be visible via
`state`/`funcs`.
**Expected:** clean rejection with no side effects, or a stable
re-parse. This is the "tool result is the attack" pattern applied to a CAS that
emits source.

### NLP-1 — ucas's own derivative output is misrouted through NLP and gives a WRONG
**Severity:** NLP
_Original classification: `NLP and gives a WRONG`._
**Expected:** _not recorded_
    derivative — `NLP`

**Observed:**
**Reproducer:**
```sh
printf 'd/dx x^3 - 3x = 3x^2 - 3\n' | ucas
#   ucas: it(x) = x^3 - 3*x == 3*x^2 - 3
#   ucas: diff it x
# d/dx it = 0
#   holds for every real x
#     (smooth at the suspect points ...)
#   check: matches central differences at 200 points (max relative difference 0)
```

This input is the verbatim headline emitted by `diff x^3 - 3x` (which correctly
prints `d/dx x^3 - 3x = 3x^2 - 3`). On re-ingestion the `=` makes the English
frontend reinterpret the line as an equation to verify, creating a *boolean*
`it(x) = (x^3-3x == 3x^2-3)`, so `diff it = 0`. The derivative of `x^3-3x` is
`3x^2-3`, not `0`.

**Why it matters:** a bug:** a tool's own output, pasted back unchanged, produces a wrong
answer rather than the same answer or a clean error. Raw `ucas` syntax
containing `d/dx ... = ...` should not be re-routed through the English
equation-checking translator.

### WRONG-2 — `parse` output drifts across one generation before failing — `WRONG`
**Severity:** WRONG
**Expected:** _not recorded_
**Observed:**
**Reproducer:**
```sh
printf 'parse x^2 + 3x + 2\n' | ucas
# (((x ^ 2) + (3 * x)) + 2)
printf '(((x ^ 2) + (3 * x)) + 2)\n' | ucas
# _(x: real) = x^2 + 3x + 2
#   -> real
# (next generation: the '-> real' line -> parse error, see finding 1/2a)
```

**Why it matters:** a bug:** a fully-parenthesized expression (the documented "parse output")
round-trips once into an anonymous `_` definition with a type annotation, then
fails — output drift plus the `_` clobber, with no stable fixed point.

### LIMIT-2 — MCP `files[]` advertises `path`/`base64` but emits neither; image bytes
**Severity:** LIMIT
**Expected:** _not recorded_
    arrive only in `result.content[].data` — `LIMIT`

MCP request `plot op:"plot" args:{"fs":"x^3 - 3x"}` with `files:"base64"` or
`files:"both"` returns:

**Observed:**
**Reproducer:**
```sh
structuredContent.files = [{"name":"plot.gif","mime":"image/gif","bytes":8390}]
result.content = [ {"type":"text",...}, {"type":"image","data":"R0lGODlh..."} ]
```

The `files[]` schema declares `path` and `base64` fields; neither is present,
even in `"both"` mode (nothing is written to `--dir`). A client that follows the
schema and reads `files[].base64` (the documented way to feed a generated GIF
back as `png_base64`) gets nothing.

**Why it matters:** a bug / consequence:** it breaks focus area #4's round-trip at the
schema boundary. Feeding the *actual* bytes from `content[].data` back as
`animate inputs:[{"png_base64": ...}]` does work (group `H_files`, `ok:true`),
so the seam is reachable only by an undocumented channel.

## Checks that passed

### Negative results / clean rejections (not bugs)
- **Proof text → verifier.** `proofs op:"proof_check" args:{"text": <printed
  proof>}` is rejected cleanly: `bad_request: proof_check has no argument
  "text"`. `proofs theorem` printed text *does* round-trip into raw `ucas`
  source (group `F_proofs`, OK). Raw proof text as source produces finding 2b.
- **English self-translation** (idea #25): `english text:<full output text>` is
  cleanly rejected with `bad_request: text: one line of ucas text, without
  newlines, control characters or '#'` (group `G_english`). English-emitted
  `ucas:` statements themselves round-trip into a fresh `ucas` process (golden
  `02_english_statements_roundtrip.*`).
- **Determinism:** every would-be golden was run twice and byte-compared;
  `01_*`, `02_*`, `03_*` and `mcp_output_to_input.*` are identical across runs.
  The `find`/`gates`/`equiv` chains were also stable. No nondeterminism found.

### Chains that round-trip cleanly (positive coverage)
- `find` → emitted `result.peephole[].expr` → define `g` → `equiv f g` → `find g`
  (group B, 10 steps): stable verdicts, derived expressions re-verify.
- `gates` → emitted program `expr`s → define → `equiv` (group C, 10 steps).
- `c_optimize` → `result.code` → `c_optimize` again **and** into
  `spirv_simplify` (group D, 16 steps): all `ok:true`.
- `spirv_simplify` → emitted code → `spirv_simplify` again (group E, 3 steps).
- `equiv` counterexample values → `show <value>` (group I, 24 steps): clean.
