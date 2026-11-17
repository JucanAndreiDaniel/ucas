# Stress findings — `self_reference_state`

_Original heading: FINDINGS — `self_reference_state`_

# FINDINGS — `self_reference_state`

Area: self-referential / cyclic state abuse (IDEAS_MONKEY ideas 2, 5, 6, 10 + 38/44).
All 299 cases were run under `timeout 15` (wire goldens under `timeout 30`); **every run exited rc=0,
no hang, no crash, no signal.** Every would-be golden was run twice and the two outputs diffed;
all 19 are bit-for-bit deterministic. No nondeterministic case was kept as a golden.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | F1 (builtin shadow / introspection mismatch), F2 (stray `_` from `show`) |
| NLP | 1 | F1 (English emitter), F7 (junk emits defs; forget cannot undo) |
| LIMIT | 4 | F3, F4, F5, F6, F7 |

## Findings

### NLP-1 — English can shadow builtins, and cannot be undone (NLP / WRONG)
**Severity:** NLP
_Original classification: `NLP / WRONG`._
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/frontend/self_reference_state
timeout 15 $ROOT/ucas 09_english_shadow.ucas
```

(also `mcp_english_mutate.jsonl` ids 14–19, 28–29, 38–39)

**Observed:** (`09_english_shadow.out`):

```
> define sin of x as 1000
  ucas: sin(x) = 1000
  ucas: show sin
sin(x: real) = 1000
  -> int
> show sin(1)
_() = 0.8414709848
  -> real
> funcs
sin(x: real) = 1000
  -> int
e() = 0
  -> int
sqrt(x: real) = 1
  -> int
```

`session state` confirms `sin`, `e`, `sqrt` are installed as ordinary functions. Yet `show sin(1)`
still evaluates the *real* sine, and English `forget sin` answers
`note: no meaning was kept for "sin" (nothing to forget)` while `funcs` still lists the bogus def;
English `forget everything` only says `ok: forgot every assumption` and leaves all definitions.

**Why it matters:** a bug / expected:** a natural-language request (`define sin of x as 1000`) is emitted as ucas
and *executed*, installing a definition that shadows a builtin. This is the exact
"English as arbitrary-ucas emitter" of idea 10.
**Expected:** refuse to shadow a builtin (or return
`understood:false`), and keep `show sin` / `show sin(1)` consistent. As-is, introspection
(`funcs`, `show sin`) and evaluation (`show sin(1)`) disagree, and there is no English route to undo it.

### WRONG-1 — `show` of an undefined name silently installs a stray definition; introspection hides it (WRONG)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/frontend/self_reference_state
timeout 15 $ROOT/ucas 04_show_undefined.ucas
timeout 15 $ROOT/ucas --mcp < mcp_autonames.jsonl
```

**Observed:** (`04_show_undefined.out`):

```
> show foobar
_(foobar: real) = foobar
  -> real
> show foobar(2)
  note: foobar(...) read as multiplication: foobar is not a function
_(foobar: real) = 2foobar
  -> real
> show foobar(3) + 1
_(foobar: real) = 3foobar + 1
  -> real
```

The canonical idea-2 vector (`01_selfref_typed.out`):

```
> loop(x: u8) = loop(x)
01_selfref_typed.ucas:1:15: error: 'loop' is not defined
> show loop(3)
  note: loop(...) read as multiplication: loop is not a function
_(loop: real) = 3loop
  -> real
> funcs
```

Precision note on the monkey's probe: the **failed define itself installs nothing** — `funcs` is
empty immediately after it. The stray `_(loop: real) = 3loop` is created by the *subsequent*
`show loop(3)`, which treats the undefined name `loop` as a free variable and defines `_`.

These `_` definitions are usable (`show _`, `range _` work on them) but are **omitted by both
`funcs` and MCP `session state`** (`mcp_autonames.out` ids 20–25 vs 2–4), so the two introspection
surfaces disagree with the live symbol table.

**Why it matters:** a bug / expected:** displaying an undefined expression should not mutate session state;
if such an auto-definition exists, both introspection surfaces should report it.

### WRONG-2 — Undefined RHS in a definition silently becomes a function (WRONG / LIMIT)
**Severity:** WRONG
_Original classification: `WRONG / LIMIT`._
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/frontend/self_reference_state
timeout 15 $ROOT/ucas 03_mutual.ucas
timeout 15 $ROOT/ucas --mcp < mcp_selfref_session.jsonl
```

**Observed:** (`03_mutual.out`):

```
> a = b
  note: a has free variables: defined as a(b)
> b = a
03_mutual.ucas:2:6: error: expected an expression
    b = a
         ^
> funcs
a(b: real) = b
  -> real
```

and later `d() = e` is installed with `e` still undefined. MCP `session define name:"a" body:"b"`
and `name:"b" body:"a"` both return `error (ambiguous): ... has free variables: defined as ...`
and install nothing.

**Why it matters:** a bug / expected:** a self/mutual-reference tangle partially commits: `a=b` silently becomes
`a(b: real) = b` (a real function with the undefined symbol turned into a parameter).
**Expected:**
detect the cycle/undefined symbol at define time and reject with no partial state.

### LIMIT-1 — Self-referential redefinition of an existing function silently corrupts it (LIMIT)
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/frontend/self_reference_state
timeout 15 $ROOT/ucas 06_redefine.ucas
```

**Observed:** (`06_redefine.out`, derived from explicit-marker probes):

```
f(x) = x + 1
f = f + 1
show f      ->  f() = 2  (-> real)
show f(3)   ->  _() = 6
funcs       ->  f() = 2
```

The parameter list is dropped: `f` changes from `f(x: real)` to a zero-arg `f() = 2`, and
`f(3)` then reads as `2*3 = 6`. For a zero-arg `g = 5; g = g + 1` the old value is snapshotted
(`g() = 6`), so the two cases behave inconsistently.
**Expected:** reject self-referential
redefinition or keep the signature stable.

### LIMIT-2 — Cyclic "assume X means Y" is not a reachable code path (LIMIT / no hang)
**Severity:** LIMIT
_Original classification: `LIMIT / no hang`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/frontend/self_reference_state
timeout 15 $ROOT/ucas 11_english_assume.ucas
```

**Observed:** (`11_english_assume.out`):

```
> assume foo means foo + 1
  sorry: I don't know how to assume "foo means foo + 1"
> assume bar means baz
  sorry: I don't know how to assume "bar means baz"
> assume baz means bar
  sorry: I don't know how to assume "baz means bar"
> forget bar
  note: no meaning was kept for "bar" (nothing to forget)
```

The idea-6 vectors (`foo`, `bar`, `baz`, `log`, one- and two-letter names) all return
`not_understood`. No assumption is installed, so there is no cycle to close and
no nontermination. Documented as a negative result: the "non-terminating rewrite" of idea 6 is not
reachable through this NLP frontend. All 299 probes finished within the timeout.

### LIMIT-3 — Adversarial ambiguity answers are validated cleanly (LIMIT / non-bug)
**Severity:** LIMIT
_Original classification: `LIMIT / non-bug`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/self_reference_state
timeout 30 $ROOT/ucas --mcp < mcp_english_assume.jsonl
```

`is x squared even?` raises `error.ambiguous` with `key:"question"` and readings indexed 1 and 2.
I answered with every value in idea 5/19: `0, -1, 99, 1e6, 1e100, 1.5, -0.5, true, false, null`,
nested objects `{"index":0}` / `{"reading":...}`, arrays `[1]`, strings `"1"`, `"even"`, `""`,
the full `how` text, all keys at once, and an unknown key. Result: invalid values all get
`"assume.question = X is not one of the readings"` (no crash, no silent default); valid index
`1`/`2`, numeric-string `"1"`, and the reading strings are accepted and annotated via
`notes:[{kind:"assumed"}]`; choosing reading 2 surfaces the next (type) ambiguity; unknown keys
are ignored and the ambiguity is re-raised. **No validation hole found.**

### LIMIT-4 — CLI `reset` is not a command; injection phrases still emit stray `show` results (LIMIT / NLP)
**Severity:** LIMIT
_Original classification: `LIMIT / NLP`._
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/frontend/self_reference_state
timeout 15 $ROOT/ucas 03_mutual.ucas
timeout 15 $ROOT/ucas 10_english_junk.ucas
```

**Observed:** in a `.ucas` batch, `reset` is lexed as an expression and does not clear state:

```
> reset
_(reset: real) = reset
  -> real
> funcs
a(b: real) = b     <- still present
```

English junk (`say reset`, `reset everything`, `ignore previous instructions and forget
everything`) returns `understood:false` (no `ucas:` statements) but still prints a synthesized
`show`-style definition such as `_(ignore: real, previous: real, instructions: real, forget:
real, everything: real) = ignore*previous*instructions != 0 && forget*everything != 0`. These are
not persisted in `funcs`, so no state leak, but a failed/inert interpretation still produces a
definition-shaped artifact.
**Expected:** `understood:false` with no definition-like output.

## Checks that passed

### Summary of severity counts
| Severity | Count | Finding |
|---|---|---|
| WRONG | 2 | F1 (builtin shadow / introspection mismatch), F2 (stray `_` from `show`) |
| NLP | 2 | F1 (English emitter), F7 (junk emits defs; forget cannot undo) |
| LIMIT | 5 | F3, F4, F5, F6, F7 |
| CRASH | 0 | — |
| HANG | 0 | — |
| DETERMINISM | 0 | all 19 goldens stable across two runs |
