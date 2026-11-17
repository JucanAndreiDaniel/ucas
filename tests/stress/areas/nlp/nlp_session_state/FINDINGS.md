# Stress findings — `nlp_session_state`

_Original heading: Findings — `nlp_session_state`_

# Findings — `nlp_session_state`

All commands below run from
`$ROOT/tests/stress/areas/nlp/nlp_session_state` with binary
`$ROOT/ucas`. Every golden in this folder was generated with
`timeout 15` (CLI) / `timeout 30` (MCP) and verified deterministic by running it
twice and diffing (the double-init golden five times). No crashes, hangs or
nondeterminism were found — the issues are wrong-resolution / state bugs.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | English `assume` and JSON `session assume` are two different stores |
| NLP | 2 | pronoun `its` binds to the last *defined* function, not the one just named |
| LIMIT | 1 | reserved word `square` cannot be defined; malformed arguments are silently accepted |

## Findings

### WRONG-1 — English `assume` and JSON `session assume` are two different stores
**Severity:** WRONG
There are two independent assumption stores. `english` "assume X" writes one;
`session assume set` writes another. They disagree with each other, with
`session state`, and with `forget`/`clear`. Four concrete wrong behaviours:

#### (a) English assumptions are invisible to `session state`  — `WRONG`

Reproduce:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_session_state
$ROOT/ucas --mcp < mcp_assume_forget.jsonl
```

**Observed:** (ids 1–3, trimmed):

```
id=1  english  ok: log means base 2
id=2  english  ucas: log(8)/log(2) -> 3        (base 2 is active)
id=3  state    functions: []  assumptions: {}  (base 2 is NOT reported)
```

**Expected:** `assumptions` should contain `{"log": "base 2"}`.
**Why it matters:** it's a bug: a client that queries state cannot see meanings the user set in
plain English, so it cannot know how later English lines will be parsed.

#### (b) `session assume clear` does not clear English assumptions — `WRONG`

Same run, ids 4, 7, 8:

```
id=4  session assume set {"log":"base 10"}  -> assumptions {"log":"base 10"}
id=7  session assume clear                   -> assumptions {}
id=8  english "what is the log of 8?"        -> ucas: log(8)/log(2) ; 3
```

**Expected:** after `clear`, the earlier English "log means base 2" is gone, so the
log question falls back to the natural-log ambiguity (or the base-10 setting if
that were meant to survive). Why it's a bug: the tool reports `assumptions: {}`
but the English parser still uses base 2 — the cleared assumption is still live.

#### (c) English `forget everything` does not clear JSON assumptions — `WRONG`

Reproduce:

```sh
cd $ROOT/tests/stress/areas/nlp/nlp_session_state
$ROOT/ucas --mcp < mcp_forget_json_assume.jsonl
```

**Observed:** (ids 1–5):

```
id=1  session assume set {"log":"base 10"}  -> assumptions {"log":"base 10"}
id=2  state    assumptions {"log":"base 10"}
id=3  english  "forget everything"           -> ok: forgot every assumption
id=4  state    assumptions {"log":"base 10"}   (still there!)
id=5  english  "what is the log of 100?"      -> ucas: log(100)/log(10) ; 2
```

**Expected:** "forget everything" empties every assumption store, so `state` shows
`{}` and the log question becomes the natural-log ambiguity again.
**Why it matters:** it's a bug: the user is told "forgot every assumption" while nothing was
forgotten. (In the pure CLI `.ucas` path "forget everything" *does* work on
English meanings — see `02_forget_assume.out`.)

#### (d) An older English meaning wins over a newer JSON assumption — `WRONG`

Same `mcp_assume_forget.jsonl` run, ids 1, 4, 5, 6:

```
id=1  english  "assume log means base 2"          -> ok
id=4  session  assume set {"log":"base 10"}       -> assumptions {"log":"base 10"}
id=5  english  "what is the log of 100?"          -> ucas: log(100)/log(2) ; 6.64386
id=6  state    assumptions {"log":"base 10"}
```

**Expected:** `2` (`log(100)/log(10)`), because the JSON assumption was set last.
**Why it matters:** it's a bug: state claims base 10, but the English frontend silently uses
the stale base-2 meaning from an earlier turn. This is a wrong answer, not just
a reporting problem. Setting the JSON assumption *without* a prior English
meaning does work (`log(100)/log(10) = 2`), so it is specifically a precedence
bug between the two stores.

### NLP-1 — pronoun `its` binds to the last *defined* function, not the one just named
**Severity:** NLP
Reproduce:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_session_state
$ROOT/ucas 03_pronoun_binding.ucas
```

**Observed:** (excerpt):

```
> let alpha of x be x + 1
...
> let beta of x be 100 - x
...
> what is alpha of 5?
  ucas: alpha(5)
6
> what is its range?
  ucas: range beta
range of beta:
  [90, 110]   min at x ≈ 10, max at x ≈ -10
...
> what is alpha of 9?
  ucas: alpha(9)
10
> what is its derivative?
  ucas: diff beta
d/dx beta = -1
```

**Expected:** after "what is alpha of 5?", "its range" / "its derivative" should
refer to `alpha` (the function just evaluated), i.e. a range near 6 and
derivative `1`.
**Why it matters:** it's a bug: a follow-up pronoun silently resolves to a different, older
definition (`beta`). The wrong function is analysed, and the answer is
confidently wrong with no note that the referent changed. This is exactly the
"wrong function resolved by a pronoun/name" failure mode.

### WRONG-2 — a second `initialize` does not start a fresh session (state leaks across sessions)
**Severity:** WRONG
Reproduce:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_session_state
$ROOT/ucas --mcp < mcp_double_init.jsonl
```

**Observed:** (ids 0–8):

```
id=0   initialize (client-A)
id=1   define f(x)=x^2+1
id=2   state   functions: ['f']   assumptions: {}
id=3   initialize (client-B)          <- new handshake
id=4   state   functions: ['f']   assumptions: {}   <- A's function survived
id=5   english "what is f of 3?"       -> ucas: f(3) ; 10
id=6   session assume set {"log":"base 2"}
id=7   initialize (client-C)          <- another new handshake
id=8   state   functions: ['f']   assumptions: {'log':'base 2'}  <- both survived
```

**Expected:** a fresh `initialize` (a new client/session on the same process) starts
with no functions and no assumptions.
**Why it matters:** it's a bug: definitions and assumptions from one client leak into the next
client in the same process. Only an explicit `session reset` clears them.

### NLP-2 — after `reset`, "what is f of 3?" reports a misleading parse error
**Severity:** NLP
**Why it matters:** _not recorded_
Reproduce:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_session_state
$ROOT/ucas --mcp < mcp_state_calls.jsonl
```

**Observed:** (ids 10–14):

```
id=12  session reset                 -> ok
id=13  state    functions: []        -> ok
id=14  english "what is f of 3?"      -> ok=false, not_understood,
                                        "sorry: I didn't follow \"of 3\""
```

**Expected:** a message that says `f` is undefined, e.g. "sorry: I don't know a
function f", rather than blaming the words "of 3" which parsed correctly before
the reset. Why it's a bug: the diagnostic points at the wrong part of the
sentence, making the session state failure hard to recognise. (In CLI a bare
undefined `f of 3` also says "sorry: I didn't follow \"of 2\"" — see
`06_state_robustness.out`.)

### LIMIT-1 — reserved word `square` cannot be defined; malformed arguments are silently accepted
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Reproduce:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/nlp/nlp_session_state
$ROOT/ucas 08_prompts_and_scope.ucas
```

**Observed:**

```
> let square of x be x times x
  sorry: I don't understand "let square of" here
> what is square of 4?
  ucas: 4^2
16
```

`square` is a built-in word, so a user definition with that name is rejected and
later `square of ...` resolves to the builtin. Similarly `let it of ...` and
`let range of ...` are rejected (`06_state_robustness.out`).

Malformed session inputs are otherwise handled without crashing (crash sweep on
18 malformed calls: all returned a clean `bad_request`/JSON-RPC error or a
correct answer). Two soft spots worth noting:

- `english` with `assume: {"log": ["weird"]}` (an array instead of a string)
  is accepted and silently ignored; the request returns a normal answer.
- `session` with `op: "bogus"` returns
  `session needs "op", one of: define state assume reset schema funcs models use help`
  i.e. an invalid op is reported as a missing one.

These are LIMITs (no crash, no wrong answer produced from the bad value), but
they show argument validation is incomplete.

## Checks that passed

### No CRASH / HANG / DETERMINISM issues
- All 13 `.out` goldens were produced with exit code 0 under `timeout`.
- Each golden was run twice and diffed (double-init five times): all identical.
- `session schema` works via MCP (`tools.ucas.session({op:"schema"})` in Code
  Mode and `session schema` over `--mcp`); its reply is the full ~870 KB JSON
  schema, so it is exercised but deliberately not stored as a golden to avoid
  an 870 KB brittle file.
