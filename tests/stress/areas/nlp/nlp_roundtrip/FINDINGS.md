# Stress findings — `nlp_roundtrip`

_Original heading: FINDINGS — `nlp_roundtrip`_

# FINDINGS — `nlp_roundtrip`

Area: round-trip integrity between the English frontend and the ucas language.
Method: for each English query, obtain the emitted `ucas:` statements from the
`english` MCP tool (and CLI), feed those statements into a **fresh** `ucas --mcp`
process via the `ucas` tool (with `defaults:true`, matching CLI behaviour), and
compare (a) parses-without-error and (b) printed answer.

Binary: `$ROOT/ucas`. All runs bounded with `timeout`.
Golden `mcp_*.out` files are deterministic (run twice, `diff` clean) and can be
replayed with `ucas --mcp < FILE` (add `--flat` for `mcp_roundtrip_flat`).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | emitted `f(3)` silently becomes multiplication in a fresh process |
| NLP | 1 | the frontend emits statements that themselves error |
| LIMIT | 2 | the frontend's disambiguation `note:` lines are lost on round-trip |

## Findings

### WRONG-1 — emitted `f(3)` silently becomes multiplication in a fresh process
**Severity:** WRONG
**Reproducer:**
Reproducer** (CLI, two separate processes):

```sh
# Half A — English frontend (definition in the same session)
printf 'let f of x be x squared plus 1 where x is between 0 and 10\nwhat is f of 3?\n' \
  | $ROOT/ucas
# Half B — fresh process fed ONLY the emitted statement
printf 'f(3)\n' | $ROOT/ucas
```

MCP golden: `mcp_session_roundtrip.jsonl` ids 1–4 (`ucas --mcp < mcp_session_roundtrip.jsonl`).

**Observed:** output

Half A (English):
```
  ucas: f(x in 0..10) = x^2 + 1
  ucas: show f
f(x: int in 0..10) = x^2 + 1
  -> int
  ucas: f(3)
10
```
The emitted statement is `f(3)`; the English answer is `10`.

Half B (fresh process, `f(3)`):
```
  note: f(...) read as multiplication: f is not a function
_(f: real) = 3f
  -> real
```

**Why it matters:** it is a bug / expected**: the emitted statement `f(3)` is not self-contained —
it relies on the `f` definition established earlier in the session, which the frontend
does **not** re-emit. In a fresh process `f` is not a function, so `f(3)` is parsed as
the multiplication `f*3`, silently producing a meaningless function definition instead
of `10`. The round-trip answer differs completely.
**Expected:** either emit the defining
statement(s) alongside `f(3)`, or emit a form that cannot be misread as multiplication.

### WRONG-2 — emitted `range h` gives a different answer in a fresh process
**Severity:** WRONG
**Reproducer:**
Reproducer**: `mcp_session_roundtrip.jsonl` ids 6–9.

```sh
$ROOT/ucas --mcp < $ROOT/tests/stress/areas/nlp/nlp_roundtrip/mcp_session_roundtrip.jsonl
```

Equivalent CLI: `printf 'let h of x be x squared where x is between 0 and 10\nwhat is its range?\n' | ucas`
then, in a fresh process, `printf 'range h\n' | ucas`.

**Observed:** output

Half A (English, after `h(x in 0..10) = x^2` was defined; emitted statement `range h`):
```
  ucas: range h
range of h -> int:
  0..100
  fits in u7
  over all 11 points of the domain
```

Half B (fresh process, emitted statement `range h`):
```
range of h:
  [-10, 10]   min at h ≈ -10, max at h ≈ 10
  grid of 20001 points over [-10, 10] (default; give x a range), extrema refined at critical points
```

**Why it matters:** it is a bug / expected**: same root cause as Finding 1 — the emitted `range h`
omits `h`'s definition and domain. In a fresh process `h` is treated as a free real
variable, so the answer changes from the exact integer range `0..100` to a sampled
real range `[-10,10]`.
**Expected:** a self-contained emitted statement (definition
included) or a translation that preserves the answer.

### WRONG-3 — emitted statement omits the disambiguation/type the frontend chose; a different (legitimate) `assume` silently changes the answer
**Severity:** WRONG
**Reproducer:**
Reproducer**: `mcp_default_sensitivity.jsonl` (deterministic golden).

**Observed:**
```sh
$ROOT/ucas --mcp < $ROOT/tests/stress/areas/nlp/nlp_roundtrip/mcp_default_sensitivity.jsonl
```

#### 3a — `approx` (`keep_ends`)

The English frontend emits `it(x: real in 0..1) = x^2` / `approx it degree 5 keep crit`
and answers with the **default** reading of the `keep_ends` ambiguity (id 1 note:
`it has special points at the interval's ends ... not by default: say 'keep endpoints'`).
Re-running the *same emitted statement* under the other reading changes the result:

Half B1 (default, id 3):
```
  keep crit: no critical points inside [0, 1]
approx it on [0, 1] as f32, fma
  ...
  no polynomial fit in the degree range
  rational fits (num/den degree: minimax, Pade; max rel error): ...
  piecewise (2 pieces split at 0.5, max rel error): 1: 1 2: 1.08e-19 ...
  1   piecewise 5     horner+fma  0.988 ulp ... 17.5 at x=0.504203856
```

Half B2 (`assume.keep_ends = "yes, keep them exact (keep endpoints)"`, id 5):
```
  keep crit: no critical points inside [0, 1]
approx it on [0, 1] as f32, fma
  ...
  exact at: x = 0 -> 0, x = 1 -> 1
  no polynomial fit in the degree range
  piecewise (2 pieces split at 0.5, max rel error): 2: 2.11e-19 3: 1.08e-19 4: 1.79e-19 ...
  1   piecewise 5     horner+fma  0.988 ulp ... 19.125 at x=0.504203856  exact pts yes
```

The coefficients (`k3`,`k4`,`k5`), the `exact at` line, and the reported cost (17.5 vs
19.125) all change.

#### 3b — `sqrt` / `isqrt`

English query `what is the range of the square root of x for x in 0..16?` emits
`it(x in 0..16) = sqrt(x)` and answers `range of it -> int: 0..4` (floor sqrt, via a note).

Half B1 (default `isqrt`, id 8): `range of it -> int: 0..4 ... over all 17 points of the domain`.
Half B2 (`assume.isqrt = "real sqrt"`, id 10):
```
{"code": "ambiguous",
 "message": "sqrt of the integer x read as floor square root isqrt(); write sqrt(real(x)) for the real one (assume.isqrt: the other reading needs different input: write sqrt(real(n)))",
 "key": "isqrt", ...}
```

#### 3c — untyped `find`

`alt ((1 << 3) & x) + x*5` emits `it(x) = (1 << 3 & x) + x*5` / `find it 10` with **no type
annotation** on `x`. Default `untyped=inferred` makes `x` an `int` and the command succeeds
(`find it: 191 points ... computing in int ...`); `assume.untyped="real"` makes the same
emitted statement fail with `ambiguous` (`x has no type: inferred int from the integer
operations in the body`).

**Why it matters:** it is a bug / expected**: the English frontend resolves these ambiguities/type
inferences itself (and even prints a `note:` about them), but does **not** encode the
chosen reading in the emitted `ucas:` statement. The round-trip is only faithful if the
caller independently re-applies the identical default; choosing another legitimate
reading silently yields a different answer (or an error).
**Expected:** emit the resolved
form (`sqrt(real(x))`, `x: int`, explicit `keep endpoints`, ...) so the emitted statement
is a complete, self-contained translation.

### LIMIT-1 — the frontend's disambiguation `note:` lines are lost on round-trip
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer**: `mcp_note_loss.jsonl` (ids 1 and 3).

```sh
$ROOT/ucas --mcp < $ROOT/tests/stress/areas/nlp/nlp_roundtrip/mcp_note_loss.jsonl
```

Query `what are the critical points of x^4 - 4x^2 + 3 from -3 to 3?` emits
`it(x: real in -3..3) = x^4 - 4*x^2 + 3` / `crit it`.

Half A (English, id 1) — leads with a note:
```
  note: x taken as real on [-3, 3] (say "integer x" for whole numbers)
critical points of it:
  ...
```
Half B (fresh process, id 3) — no note:
```
> it(x: real in -3..3) = x^4 - 4*x^2 + 3
> crit it
critical points of it:
  ...
```

The mathematical answer is identical; only the interpretation note disappears.
**Observed:** on 5 queries in the batch: the above, `is (x+y)^2 the same as x^2+2xy+y^2`
(note `read "xy" as x*y`), `cos of pi/2 to -pi/2 w/o crit. points` (note `read the
interval as [-pi/2, pi/2]`), `approximate x^2 in 0..1 degree 5 crit` (note `x taken as
real`), and `what is the taylor series of e^x at 0?` (note `no order given: through
order 5`). Low severity — information loss, not a wrong answer.

### NLP-1 — the frontend emits statements that themselves error
**Severity:** NLP
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer** (MCP `english`, `defaults:true`, text below; or CLI):

**Observed:**
```sh
printf 'find cheaper implementations of x*5 + 3\n' | $ROOT/ucas
```

Query `find cheaper implementations of x*5 + 3` emits `it(x) = x*5 + 3` / `find it 10`.
Both halves then fail identically (only the filename prefix differs):

```
<english>:2:11: error: find on a float result needs one f16, f32 or f64 parameter
    find it 10
              ^
<json>:2:11: error: find on a float result needs one f16, f32 or f64 parameter
    find it 10
              ^
```

Same for `find cheaper implementations of x*7 + x*3`. And `what is the 100th derivative
of sin x?` emits `it(x) = sin(x)` / `diff it 100`, which errors with `the order is 1 to
12` in both halves.
**Expected:** the frontend should not emit a statement that its own
backend rejects — e.g. add a typed machine parameter (`x: u8`) for `find`, or clamp the
derivative order / report the limit during translation.

### LIMIT-2 — large fraction of phrasings not understood (informational)
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Of 178 primary queries, 54 produced `sorry: ...` (no emitted statements), usually because
the phrasing is outside the frontend's grammar rather than a round-trip defect. Examples:

- `does 255 + 1 overflow for u8?` → `sorry: I didn't follow "for u8"`
- `are x+y and y+x equal for u8?` → `sorry: I didn't follow "for u8"`
- `what is the minimum of x squared for x from -5 to 5?` → `sorry: "minimum" needs two or more things, joined by "and"`
- `what is the sum of i from 1 to n?` → `sorry: the sum of what?`
- `make a table of x squared for x from 1 to 5` → `sorry: I didn't follow "a table of ..."`
- `how accurate is a fast reciprocal sqrt approximation?` → `sorry: compared with what?`

Some `sorry` cases do emit a full answer but no `statements` array (e.g. `identify
y'' + y = 0`, `identify x^2 + y^2 = 1`), because the line is passed through as a raw ucas
command; round-trip is simply N/A for those. `assume ...` / `forget everything` lines
change session state and likewise emit no statement (expected).

## Checks that passed

### Non-findings / clean results
- No crashes, hangs, truncated JSON, or nondeterministic golden outputs were observed in
  the round-trip path (all 7 goldens reproduced byte-identically across two runs).
- For 156/228 harness queries the emitted statements parsed in a fresh process and the
  answer matched exactly, including range, wrap/domain, equiv, critical points,
  derivatives/integrals, closed forms, working `find`/`gates`/`cost`, tables, min/max,
  accuracy, ODE solving, and `let ...` definitions.
- Assumption-state cases that **do** round-trip correctly: the frontend encodes the
  assumption into the emitted statement, e.g. `assume bytes are signed` → `it(x: i8) = ...`;
  `assume int means unbounded` → `it(x: int) = ...`; `assume log means base 2` →
  `log(x)/log(2)`. The bug (Findings 1–2) is specific to user-defined function names
  whose definitions are not re-emitted.
