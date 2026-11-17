# Stress findings — `state_long_session`

_Original heading: FINDINGS — `state_long_session`_

# FINDINGS — `state_long_session`

Area: long-lived interpreter state and name resolution. Binary:
`$ROOT/ucas`. All reproducers were run from this folder under
`timeout`. All kept goldens were run twice and byte-diffed (deterministic).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | Builtin-named user definitions are listed as callable but calls resolve to the builtin |
| NLP | 1 | English `forget everything` forgets only assumptions, not definitions |
| LIMIT | 3 | Command names cannot be shadowed by definitions; the definition is misparsed instead |

## Findings

### WRONG-1 — Builtin-named user definitions are listed as callable but calls resolve to the builtin
**Severity:** WRONG
_Original classification: `WRONG (name resolution / state listing`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/state_long_session
$ROOT/ucas 01_builtin_shadow.ucas
```

**Observed:** output** (excerpt; full in `01_builtin_shadow.out`):
```
> sin(x: real) = x + 1000
> sin(0)
0
> cos(x: real) = 777
> cos(0)
1
> sqrt(x: real) = 42
> sqrt(9)
3
> pi(x: real) = 3
> pi(0)
0
> mySin(x: real) = x + 1000
> mySin(0)
1000
> funcs
sin(x: real) = x + 1000
  -> real
...
```

`funcs` lists `sin`/`cos`/`sqrt`/`real`/`pi` with the user bodies, yet `sin(0)=0`,
`cos(0)=1`, `sqrt(9)=3`, `pi(0)=0` are the *builtin* results, not `1000`/`777`/
`42`/`3`. The control name `mySin` works (`mySin(0)=1000`). Same via MCP:
`mcp_builtin_shadow.jsonl` ids 2–3 define `sin`/`sqrt`, id 4 `state` lists all
three functions, but id 6 `show sin(0)` → `_() = 0` and id 7 `show sqrt(9)` →
`_() = 3` while id 5 `show myfun(0)` → `_() = 7`.

**Why it matters:** it is a bug / expected:** a definition that `funcs`/`state` reports as
present should be what a call resolves to — or the definition should be refused.
Here the listing and the call table disagree: the stored definition is dead
data. This is exactly "list output does not match what is actually callable".

### WRONG-2 — `session state` omits underscore-prefixed functions that `funcs` lists and that are callable
**Severity:** WRONG
_Original classification: `WRONG (listing inconsistency`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/state_long_session
$ROOT/ucas --mcp < mcp_state_funcs.jsonl
```

**Observed:** output** (parsed from `mcp_state_funcs.out`):
```
id 4 (session funcs): normal(x: real) = x + 1
                      _under(x: real) = x + 2
                      __x(x: real) = x + 3
id 5 (session state): functions = [ "normal" ]          <-- _under, __x missing
id 6 (analyze show _under(10)): _() = 12                <-- callable!
id 7 (analyze show __x(10)):    _() = 13
id 8 (analyze show normal(10)): _() = 11
```

**Why it matters:** it is a bug / expected:** `state()` is the structured "what is callable"
inventory, but it hides any function whose name begins with `_`. Those functions
are real, listed by `funcs()`, and evaluate correctly. A client that trusts
`state()` will conclude they do not exist. (Redefinition ordering itself is
fine: in `01`/`03`/`stress_big` redefinitions stay in insertion order.)

### WRONG-3 — English `assume`/`forget` and `session assume`/`state` are two independent stores; `state.assumptions` disagrees with actual resolution
**Severity:** WRONG
_Original classification: `WRONG (state coherency; also order-dependent`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/state_long_session
$ROOT/ucas --mcp < mcp_assume_divergence.jsonl
```

**Observed:** output** (parsed from `mcp_assume_divergence.out`):
```
id 1  english: what is log of 8?        -> error (ambiguous) "log without a base"
id 2  english: assume log means base 2  -> ok: log means base 2
id 3  session state                     -> assumptions = {}                       <-- not recorded
id 4  english: what is log of 8?        -> log(8)/log(2) = 3                       <-- base 2 is in effect
id 5  session assume set {log: base 10} -> assumptions {"log":"base 10"}
id 6  session state                     -> assumptions = {log: base 10}           <-- reports base 10
id 7  english: what is log of 1000?     -> log(1000)/log(2) = 9.96578              <-- still base 2!
id 8  english: forget log               -> ok: forgot log
id 9  session state                     -> assumptions = {log: base 10}           <-- still reports base 10
id 10 english: what is log of 1000?     -> log(1000)/log(10) = 3                   <-- now base 10
```

**Why it matters:** it is a bug / expected:** there are two separate assumption maps. The
English one actually drives parsing but is invisible to `state()`; the session
one is reported by `state()` but is ignored while the English one is active,
and is *not* cleared by English `forget log`. So `state()` is wrong both before
and after the `assume`/`forget`. Results are order-dependent in the sense that
the "winner" is whichever store was touched last in a way the client cannot see
from `state()`. Per-request `args.assume` works on a clean session (verified:
`{"assume":{"log":"base 2"}}` → `log(8)/log(2)=3`) but is likewise masked while
an English assumption is active.

### WRONG-4 — A user function named `_` is silently clobbered by internal anonymous-function results
**Severity:** WRONG
_Original classification: `WRONG / LIMIT (name collision with internal placeholder`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/state_long_session
$ROOT/ucas --mcp < mcp_underscore_collision.jsonl
```

**Observed:** output** (parsed from `mcp_underscore_collision.out`):
```
id 1  define _(x: real) = x+4          -> signature _(x: real)
id 2  analyze show _(10)               -> _() = 14       <-- correct
id 3  analyze show 7+8                 -> _() = 15       <-- unrelated analysis writes internal "_"
id 4  analyze show _(10)               -> _() = 140      <-- WRONG: was 14
id 6  session state                    -> functions = [ ] <-- the user definition vanished
```

**Why it matters:** it is a bug / expected:** `_` is the internal name for anonymous result
functions. Allowing a user to define `_`, then overwriting it on the next
unrelated analysis call, changes the meaning of later calls (14 → 140) and
removes the function from `state()`. Either reject `_` as a definition name or
keep the user symbol in a separate namespace.

### NLP-1 — English `forget everything` forgets only assumptions, not definitions
**Severity:** NLP
_Original classification: `NLP / LIMIT`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/state_long_session
$ROOT/ucas 05_english_state_mix.ucas
```

**Observed:** output** (lines 31–45 of `05_english_state_mix.out`):
```
> forget everything
  ok: forgot every assumption
> what is f of 3?
  ucas: f(3)
300
> funcs
f(x: real) = 100x
  -> real
g(x: real) = x^2 + 1
  -> real
```

**Why it matters:** it is a bug / expected:** "forget everything" reads as clearing the whole
transient session. It clears only English assumptions; function definitions
survive. The response text ("forgot every assumption") reveals the real scope,
but the command wording is misleading. Note `session reset` (MCP) *does* clear
functions, assumptions, bases and active model (verified in `mcp_long_session`
and scratch probes), so the two mechanisms have different reach.

### LIMIT-1 — Command names cannot be shadowed by definitions; the definition is misparsed instead
**Severity:** LIMIT
_Original classification: `LIMIT (parser routing`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/state_long_session
$ROOT/ucas 04_shadow_command_type.ucas
```

**Observed:** output** (lines 1–13, 35–44 of `04_shadow_command_type.out`):
```
> range(x: real) = x * 7
  note: '=' inside an expression read as '=='
range of x == 7x -> bool: ...
> show(x: real) = x * 9
  note: '=' inside an expression read as '=='
_(x: real) = x == 9x
> table(x: real) = x * 11
  note: '=' inside an expression read as '=='
  x=-10 -> 0 ...   (a 21-row table, not a definition)
> int(x: real) = x + 3
> bool(x: real) = x + 4
> f64(x: real) = x + 5
> funcs
int ... bool ... f64 ...
```

**Why it matters:** it is a bug / expected:** `range`, `show`, `table` win over the definition
syntax and `=` is silently downgraded to `==`, so a user "definition" becomes a
command invocation and no function is created (and `funcs` confirms). Type names
`int`/`bool`/`f64` *can* be shadowed. This is inconsistent name resolution
between commands and types; at minimum the note does not say the definition was
lost.

### LIMIT-2 — Unicode identifiers are rejected on all three front ends (consistent LIMIT)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducers:**
**Observed:**
**Reproducer:**
```sh
cd $ROOT
./ucas -e 'αβγ(x: real) = x+7'                       # -> error: unexpected character '?'
./ucas -e 'let café of x be x squared plus 1'        # -> sorry: I can't read the character '<?>'
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"session","arguments":{"op":"define","args":{"name":"π","params":[{"name":"x","type":"real"}],"body":"x+1"}}}}' | ./ucas --mcp
# -> error (bad_request): name: a name
```

**Why it matters:** it is a bug / expected:** not a crash — all three paths reject cleanly and
the session continues. Recorded because the FOCUS explicitly calls for Unicode
names; the system supports none. Case-differing ASCII names (`Foo`/`foo`/`FOO`)
and 240-character names work correctly (see `02_case_and_long.ucas/.out`).

### LIMIT-3 — Duplicate JSON key in `session assume.set` is dropped with a JSON-RPC parse error
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"session","arguments":{"op":"assume","args":{"set":{"log":"base 10","log":"base 2"}}}}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"session","arguments":{"op":"state"}}}' \
 | ./ucas --mcp
```

**Observed:**
```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}
```
and the subsequent `session state` still shows `assumptions = {}` (request lost).

**Why it matters:** it is a bug / expected:** strict JSON rejects duplicate keys, so the
rejection is defensible, but answering a JSON-RPC *request* with `id:null`
`-32700` makes response correlation impossible for clients. A `bad_request`
with the original id would be preferable.

## Checks that passed

### Non-issues / confirmed good behaviour
- **Determinism:** all ten kept goldens (incl. 172-statement CLI and 92-call MCP
  sessions) are byte-identical across two runs; no random witnesses or hash-order
  listings observed. Redefinition keeps insertion order.
- **Forward references** fail at define time (`'g' is not defined`) and the failed
  definition is never recovered even after `g` appears — consistent, not a crash.
- **Captured bodies:** a function body inlines the definitions current at define
  time, so redefining a dependency does not change an already-defined function
  (`b(x)=a(x)` stays at 6 after `a` is redefined). Results are order-independent
  in this respect.
- **Self/mutual recursion** cannot be entered: direct self-reference is a
  parse_error at define time; no hangs found.
- **No crashes, hangs, or truncated JSON** in any run (all exited 0 under timeout).
