# Stress findings — `nlp_arith`

_Original heading: FINDINGS — `nlp_arith`_

# FINDINGS — `nlp_arith`

Binary: `$ROOT/ucas` (do not rebuild).  All reproducers below were run with
`timeout`.  Golden files in this folder were each generated twice (MCP golden 20x) and diffed;
every kept `.out` is deterministic.  In total **262 distinct English queries** were tried.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | 1 — chained comparisons are parsed left-associatively and answer FALSE for TRUE chains |
| NLP | 5 | 1 — the frontend's own "always odd" disambiguation hint gives the wrong reading |
| LIMIT | 2 | 1 — variable comparisons are only echoed as a bool function, not answered |
| DETERMINISM | 1 | 1 — one unconfirmed empty/anomalous MCP stdout (not reproducible) |

## Findings

### WRONG-1 — 1 — chained comparisons are parsed left-associatively and answer FALSE for TRUE chains
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (copy-pasteable):

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_arith
printf '%s\n' 'is 1 < 2 < 3?' 'is 3 > 2 > 1?' 'is 2^3 > 7 < 9?' | timeout 15 $ROOT/ucas
```

**Observed:** (see `02_chained.out`):

```
> is 1 < 2 < 3?
  ucas: (1 < 2) < 3
  note: literal 3 does not fit bool; it becomes 1
0
> is 3 > 2 > 1?
  ucas: (3 > 2) > 1
0
> is 2^3 > 7 < 9?
  ucas: (2^3 > 7) < 9
  note: literal 9 does not fit bool; it becomes 1
0
```

**Why it matters:** a chained comparison `a < b < c` in English means `a < b && b < c`, which
is true for all three examples.  The frontend emits a left-nested expression `(a < b) < c`;
the bool-valued left operand then coerces the literal `c` to a bool (`3 -> 1`, `9 -> 1`)
and compares `1 < 1`, producing `0`.  A silent wrong answer to the most basic comparison
request.  With variables the same misparse occurs:
`is x < y < z for u8 x, y and z?` -> `it(x,y,z) = u8(x < y) < z`.

MCP shows the same bug (`mcp_english.out`, id 2).

### WRONG-2 — 2 — "always"/"ever" before a comparison silently drops the comparison
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_arith
printf '%s\n' 'is x greater than 0 for u8 x?' 'is x always greater than 0 for u8 x?' | timeout 15 $ROOT/ucas
```

**Observed:** (see `08_always.out`):

```
> is x greater than 0 for u8 x?
  ucas: it(x: u8) = x > 0
  ucas: show it
it(x: u8) = x > 0
  -> bool
> is x always greater than 0 for u8 x?
  ucas: it(x: u8) = x
  ucas: range it
range of it -> u8:
  0..255   (256 distinct values)
```

**Why it matters:** adding the quantifier word "always" (also "ever") changes the analysed
function from the predicate `x > 0` to plain `x`.  The question "is x always greater than 0?"
is answered with the range of `x` (0..255).  The same happens for
`is x always less than 100 for u8 x?` and `is x ever greater than 0 for u8 x?` — all three
produce exactly `it(x: u8) = x; range it`.  The comparison operator is silently discarded.

### WRONG-3 — 3 — "x + 1 squared" binds `squared` to `1` with no ambiguity note
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_arith
printf '%s\n' 'is x + 1 squared equal to x^2 + 2x + 1 for u8 x?' 'is the square of x + 1 equal to x^2 + 2*x + 1 for u8 x?' | timeout 15 $ROOT/ucas
```

**Observed:** (see `03_scope.out`):

```
> is x + 1 squared equal to x^2 + 2x + 1 for u8 x?
  ucas: it(x: u8) = x + 1^2
  ucas: that(x: u8) = x^2 + 2*x + 1
  ucas: equiv it that
it and that differ at 254 points, e.g. x=1: 2 vs 4
> is the square of x + 1 equal to x^2 + 2*x + 1 for u8 x?
  note: what does "the square of" apply to: read as (x)^2 + ..., not (x + ...)^2 ...
  ucas: it(x: u8) = x^2 + 1
```

**Why it matters:** the word form `x + 1 squared` is read as `x + (1^2)` — i.e. `x + 1` —
with **no** ambiguity note, whereas the equivalent word form `the square of x + 1` does emit
a scope note.  A user asking whether `(x+1)^2` equals `x^2+2x+1` gets an analysis of
`x+1` and a false "differ" answer; there is no warning that the scope may be wrong.

### NLP-1 — 1 — the frontend's own "always odd" disambiguation hint gives the wrong reading
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI and MCP):

```sh
cd $ROOT
printf '%s\n' 'is x odd for u8 x?' 'is x always odd for u8 x?' | timeout 15 ./ucas
```

**Observed:**

```
  note: "odd": read as an odd function, f(-x) = -f(x), not an odd number for every input (say "an odd function" or "always odd")
  ...
  note: "odd": read as an odd function, ... (say "an odd function" or "always odd")
  ucas: it(x: u8) = x
  ucas: parity it
```

The MCP ambiguity error (`mcp_english.out`, ids 5) ends with the same broken advice:

```
repeat ... or: say "an odd function" or "always odd"
```

**Why it matters:** when the frontend cannot decide between "odd function" and "odd number
for every input" it tells the user to say **"always odd"** to get the odd-number reading.
Actually `is x always odd for u8 x?` takes the *odd function* branch again (the quantifier
is consumed as an ignorable word before the ambiguity check).  The suggested escape hatch
does not work, so a user can never get the odd-number check from plain CLI English; the
only working forms are MCP `assume.question=2` / `answers:["2"]`.

### NLP-2 — 2 — a truly unsupported word is silently taken as a new variable
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf '%s\n' 'what is the range of frobnicate for u8 x?' | timeout 15 ./ucas
```

**Observed:**

```
  note: I don't know the word "frobnicate": read as a variable, not a mistake (stop here) (rephrase it, or name variables with one or two letters)
  note: x is declared but not used here
  ucas: it(frobnicate) = frobnicate
  ucas: range it
range of it:
  [-10, 10]   min at frobnicate ≈ -10, max at frobnicate ≈ 10
  grid of 20001 points over [-10, 10] (default; give x a range), extrema refined at critical points
```

**Why it matters:** "frobnicate" is not a word, not a defined function, and not a declared
variable, yet the frontend silently creates a real-valued variable from it and returns a
plausible-looking range `[-10, 10]`.  A two-option clarification exists ("a variable" vs
"a mistake (stop here)") but the non-interactive default always picks "a variable", so the
"stop" path is unreachable without a TTY.  The intended `u8 x` declaration is ignored
(`x is declared but not used here`), so the answer is about a different function entirely.

### NLP-3 — 3 — a type annotation on the wrong variable silently changes the function analysed
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf '%s\n' 'what is the range of x + 1 for u8 y?' | timeout 15 ./ucas
```

**Observed:**

```
  note: y is declared but not used here
  ucas: it(x) = x + 1
  ucas: range it
range of it:
  [-9, 11]   min at x ≈ -10, max at x ≈ 10
  grid of 20001 points over [-10, 10] (default; give x a range), extrema refined at critical points
```

**Why it matters:** a one-letter slip in the type clause (`for u8 y` instead of `for u8 x`)
leaves `x` untyped (real) and the frontend analyses the *unbounded* `x + 1` on the default
grid instead of the `u8` function.  Only a note is emitted; the numerical answer looks
authoritative.  Similarly `does x + 1 overflow for u8 y?` reports "no wrapping operations
... over all 101 points" for an untyped function.

### NLP-4 — 4 — `find 0 cheaper implementations` is silently replaced with `find 10`
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_arith
printf '%s\n' 'find 0 cheaper implementations of x^2 for u8 x' | timeout 20 $ROOT/ucas | head -3
```

**Observed:** (see `06_find.out`):

```
> find 0 cheaper implementations of x^2 for u8 x
  ucas: it(x: u8) = x^2
  ucas: find it 10
```

**Why it matters:** the explicit count `0` is ignored and the default count `10` is used.
Word counts work (`find three ...` -> `find it 3`, `find two ...` -> `find it 2`), so the
digit `0` in this position is silently dropped.  The user asked for zero results and got
ten, with no note explaining the substitution.

### NLP-5 — 5 — "is x even?" is answered with "odd: f(-x) = -f(x)"
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf '%s\n' 'is x even for u8 x?' | timeout 15 ./ucas
```

**Observed:**

```
  note: "even": read as an even function, f(-x) = f(x), ...
  ucas: it(x: u8) = x
  ucas: parity it
parity of it:
  odd: f(-x) = -f(x)
  proved, exhaustive, ...
```

**Why it matters:** `is x odd for u8 x?` and `is x even for u8 x?` produce byte-identical
analysis (`parity it`), whose headline is "odd: f(-x) = -f(x)".  The CLI never answers the
yes/no question actually asked — it always prints the function's classification.  In MCP
the `assume.question=2` path does answer the odd/even-number question, so CLI and MCP
disagree on what "is x even?" means.

### LIMIT-1 — 1 — variable comparisons are only echoed as a bool function, not answered
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf '%s\n' 'is x > 0 for u8 x?' 'is x + 1 greater than x for u8 x?' | timeout 15 ./ucas
```

**Observed:**

```
  ucas: it(x: u8) = x > 0
  ucas: show it
it(x: u8) = x > 0
  -> bool
```

**Why it matters:** it is a limitation: the question "is x > 0 for u8 x?" has a meaningful answer (true for
255 of 256 inputs) but the frontend just shows the predicate's type.  Numeric comparisons
with no variables *are* evaluated (`is 2^10 greater than 1000?` -> `1`), so the behaviour is
inconsistent.

### LIMIT-2 — 2 — supported/unsupported request vocabulary is uneven
**Severity:** LIMIT
**Expected:** _not recorded_
Reproducers and observed output:

**Observed:**
**Reproducer:**
```sh
cd $ROOT
printf '%s\n' \
  'what is the maximum of x^2 for u8 x?' \
  'what is the minimum of x^2 for u8 x?' \
  'which is bigger, x + 1 or x + 2, for u8 x?' \
  'what is the range of x for u8 y and u8 z?' \
  'find a few cheaper implementations of x^2 for u8 x' \
  'is x greater than 0 everywhere for u8 x?' | timeout 20 ./ucas
```

```
  sorry: "maximum" needs two or more things, joined by "and"
  sorry: "minimum" needs two or more things, joined by "and"
  sorry: I don't understand "bigger, x" here
  sorry: I didn't follow "z"
  note: I don't know the word "few": read as a variable ...
  sorry: I didn't follow "cheaper implementations of x^2 for u8 x"
  sorry: I didn't follow "everywhere for u8 x"
```

**Why it matters:** it is a limitation: "maximum"/"minimum" of one function are only accepted as
"maximum value"/"minimum value" (mapped to `range`); "which is bigger", multi-variable type
declarations, the quantifier "a few" for `find`, and "everywhere" after a comparison all
fail.  These are graceful `sorry` failures (no crash), but the advertised request forms
("range/maximum/minimum", "comparison requests") are only partially covered.

### DETERMINISM-1 — 1 — one unconfirmed empty/anomalous MCP stdout (not reproducible)
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer that was run:

**Observed:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_arith
timeout 30 $ROOT/ucas --mcp < mcp_english.jsonl > /tmp/try.out 2>&1
wc -c /tmp/try.out
```

Observation: on the very first attempt this produced exit 0 but a stdout where every
`english` result had `content[0].text` equal to a JSON string with `statements: []` and
`understood: false`, and the immediately following run produced **zero bytes** of stdout
with exit 0.  Twenty subsequent runs of the identical command all produced 8791 bytes,
byte-identical; the kept `mcp_english.out` comes from those stable runs.  Root cause unknown
— reported here for visibility, *not* asserted as a deterministic bug.  No golden was kept
from the anomalous runs.

## Checks that passed

### Explicitly checked and found correct (focus typos)
The deliberate misspellings named in the task are all handled with a correction note in
CLI (`01_typos.out`, `mcp_english.out` id 1): `comutative` -> commutative,
`asociative` -> associative, `add ivite` -> additive (two-word concatenation),
`monotonik` -> monotonic, `injctive` -> injective.  Also `surjctive`, `bijctive`, `domian`,
`tabel`, `cheeper`, `equivalant`, `overflw`, `peridic`, `continous`, `identfiy` are corrected.
No crash, hang, or nonzero exit was found in 151 adversarial inputs (empty input, 1000-letter
words, 200-term sums, unicode, deeply nested parentheses, typo sweep over all property
words), all under `timeout 6`.
