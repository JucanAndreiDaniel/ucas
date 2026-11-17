# Stress findings — `nlp_numbers`

_Original heading: FINDINGS — `nlp_numbers` stress area_

# FINDINGS — `nlp_numbers` stress area

All commands below are copy-pasteable. Binary: `$ROOT/ucas`.
Every CLI query was run under `timeout 12`, every golden under `timeout 30`, and
the MCP JSONL under `timeout 30`. **No crashes, signals, hangs or truncated JSON
were observed** — every run exited 0. Each golden was run twice and `diff`ed:
all were byte-for-byte deterministic.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | "trillion" silently becomes "million" (10^6 instead of 10^12) in CLI |
| NLP | 5 | the `%` sign fails wherever "percent" works |
| LIMIT | 6 | trailing-`b` binary (`1010b`) is not recognised |

## Findings

### WRONG-1 — "trillion" silently becomes "million" (10^6 instead of 10^12) in CLI
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is one trillion?\n' | $ROOT/ucas
```
**Observed:**
```
  note: "trillion" is not a word I know: read as million, not billion or "trillion" as written
  ucas: 1000000
1000000
```
`a trillion` behaves identically; `one quadrillion` is rejected (`sorry: I
didn't follow "quadrillion"`).
**Expected:** 10^12, or a refusal. The CLI's
spell-fix heuristic takes its default reading silently. The same request over
MCP is **ambiguous** (`mcp_english_numbers.out`, id 5) with readings
`million (default)`, `billion`, `"trillion" as written`. Even the explicit
correct reading is unusable:
- `assume.spelling=3` (`"trillion" as written`) → `sorry: I didn't follow "trillion"`
- `assume.spelling=2` (billion) → `1000000000`
- `defaults=true` → `1000000` (with a default note, id 6)

So 10^12 cannot be produced at all. Golden: `03_spelled_big.out`.

### WRONG-2 — all tokens longer than 39 characters are silently truncated
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Root cause: `src/nlp.c:382-383` in `push()`:
`if (n >= sizeof w->s) n = sizeof w->s - 1;` (`struct word.s/o` are `char[40]`).
There is no warning. Numeric literals lose their tail, which can turn a valid
value into a different, still-valid value.

**Reproducer:**
Repro (64 binary ones → 37 ones → a wrong but legal u64):
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is 0b1111111111111111111111111111111111111111111111111111111111111111?\n' | $ROOT/ucas
```
**Observed:**
```
  ucas: 0b1111111111111111111111111111111111111
137438953471
```
(Expected 2^64-1 = 18446744073709551615, or a length error.) Threshold is
exactly 39 characters: 37 ones → 137438953471, 38 → 68719476735,
39 → 137438953471, and 38..64 ones are all truncated to 37 ones.
The same truncation hits decimal literals: a 40-digit `9...9` is emitted as
39 nines and then fails with a *wrong* "too large" error quoting the
truncated value. Golden: `08_truncation.out`, MCP `mcp_english_numbers.out` id 7.

### NLP-1 — the `%` sign fails wherever "percent" works
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is 15%% of x?\nwhat is 50%% of 200?\n' | $ROOT/ucas
```
**Observed:**
```
  sorry: I don't understand "of x" here
  sorry: I don't understand "of 200" here
```
`what is 15 percent of x?` and `what is 50 percent of 200?` both parse fine.
Golden: `01_percent.out`, MCP id 2.

### NLP-2 — spelled decimals ("zero point five") are not parsed
**Severity:** NLP
_Original classification: `NLP / LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is zero point five?\nwhat is three point one four?\n' | $ROOT/ucas
```
**Observed:**
```
  sorry: I didn't follow "point five"
  sorry: I didn't follow "point one four"
```
Digit decimals (`1.5`, `1e-5`) work. Golden: `05_decimals_sci.out`, MCP id 8.

### LIMIT-1 — trailing-`b` binary (`1010b`) is not recognised
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is 1010b?\n' | $ROOT/ucas
```
**Observed:** (CLI):
```
  ucas: it(b) = 1010*b
  ucas: show it
it(b: real) = 1010b
```
Over MCP (`english`) the same text instead returns
`error (not_understood): I didn't follow "b"`. Only the `0b1010` prefix form
is accepted (→ 10). Golden: `07_hexbin.out`.
Related minor misparse: `what is 0xG?` → `it(G) = 0x*G` → `it(G: real) = 0`.

### LIMIT-2 — Roman numerals are not numbers
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is XIV?\nwhat is the Roman numeral XLII?\n' | $ROOT/ucas
```
**Observed:**
```
  note: I don't know the word "XIV": read as a variable, not a mistake ...
  ucas: it(XIV) = XIV
  ...
  note: I don't know the word "Roman": read as a variable, not a mistake ...
  sorry: I didn't follow "numeral XLII"
```
Golden: `10_roman.out`.

### LIMIT-3 — decibel units unsupported; bare `rad`/`radians` rejected in request position
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is 20 dB?\nwhat is 20 decibels?\nwhat is 1.5 rad?\nwhat is pi radians?\n' | $ROOT/ucas
```
**Observed:**
```
  sorry: I didn't follow "dB"
  sorry: I didn't follow "decibels"
  sorry: I didn't follow "rad"
  sorry: I didn't follow "radians"
```
`90 degrees`, `90deg`, `90r`, and the conversions `90 degrees in radians`,
`pi/2 to degrees`, `3.14159 radians in degrees` all work. Golden: `09_units.out`.

### LIMIT-4 — fraction denominators are a closed list
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is one seventh?\nwhat is one ninth?\nwhat is one twentieth?\n' | $ROOT/ucas
```
**Observed:**
```
  sorry: I didn't follow "seventh"
  sorry: I didn't follow "ninth"
  sorry: I didn't follow "twentieth"
```
Only half/third/quarter/fourth/fifth/sixth/eighth/tenth (and plurals) are
known. Golden: `04_fractions.out`.

### NLP-3 — "ratio of A to B" fails; only "ratio of A and B" works
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is the ratio of 4 to 2?\nwhat is the ratio of 10 and 5?\n' | $ROOT/ucas
```
**Observed:**
```
  sorry: "/" needs two or more things, joined by "and"
  ucas: 10/5
2
```
Golden: `11_mixed_ratio.out`, MCP id 13.

### NLP-4 — mixed numbers written with digits hit bitwise-`&` error
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is 2 and 1/2?\n' | $ROOT/ucas
```
**Observed:**
```
  note: "and"/"or" between numbers: read as bitwise (& and |) ...
  ucas: 2 & 1/2
<english>:1:8: error: '&' needs integer operands (declare the parameter as int or uN)
```
Worded mixed numbers work (`two and a half` → 2.5). Golden: `11_mixed_ratio.out`.

### LIMIT-5 — ordinal words stop at "twelfth"; a spaced suffix misparses
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is 2 to the twentieth?\nwhat is 2 to the 15 th?\n' | $ROOT/ucas
```
**Observed:**
```
  note: I don't know the word "twentieth": read as a variable ...
  ucas: it(twentieth) = 2^twentieth
  ...
  ucas: it(th) = 2^15*th
  ...
it(th: real) = 32768th
```
`2 to the 10th`, `2 to the tenth`, `the 5th power of 3` work. Golden:
`02_ordinals.out`.

### LIMIT-6 — u64 literal arithmetic wraps silently to 0
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is 18446744073709551615 + 1?\nwhat is 0xFFFFFFFFFFFFFFFF + 1?\n' | $ROOT/ucas
```
**Observed:**
```
  ucas: 18446744073709551615 + 1
0
  ucas: 0xFFFFFFFFFFFFFFFF + 1
0
```
Consistent with ucas u64 semantics, but surprising from plain English: the
literal is inferred as u64 and wraps with no note. Golden: `12_large_digits.out`.
(By contrast `2^64` is kept as arbitrary-precision `int`.)

### NLP-5 — repeated scale words add instead of multiply
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_numbers
printf 'what is nine hundred ninety-nine billion billion?\nwhat is one billion billion?\n' | $ROOT/ucas
```
**Observed:**
```
  ucas: 1000000000000
1000000000000
  ucas: 2000000000
2000000000
```
`number_words()` in `src/nlp.c:1155` accumulates `total += cur * m` per scale
word, so "one billion billion" = 2·10^9 rather than 10^18. Golden:
`03_spelled_big.out`.

## Checks that passed

### Baseline (working, for contrast)
Percent with the word "percent", ordinals up to 12th/`NNth`, spelled integers
through "billion", half/quarter/thirds fractions, digit decimals, scientific
notation (incl. `1e309`→`inf`, `1e-400`→`0`), `0x`/`0b` literals, degree
units and worded mixed numbers all parse and evaluate correctly. Integer
literals > 2^64-1 are correctly rejected with a clear error (MCP id 14);
that is good behaviour, not a finding.

### No issues in these categories
- **Crashes / hangs / signals / truncated JSON**: none. All 167 CLI queries and
  all 14 MCP calls exited 0 within `timeout`.
- **Determinism**: all 13 golden files reproduced byte-for-byte on a second run.
- **Literal widths**: u64 boundary literals (2^63-1, 2^63, 2^64-1, 2^64) are
  typed and reported correctly; the only width-related defect is the 39-char
  truncation (#2) and the wrap in #12.
