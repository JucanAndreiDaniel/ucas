# Stress findings — `session_reset_systematic`

_Original heading: FINDINGS — `session_reset_systematic`_

# FINDINGS — `session_reset_systematic`

Systematic follow-up on Top-priority #5 (session state is not resettable). Every state-creating
operation was crossed with every clearing operation across the CLI, `--json` and `--mcp` frontends;
after each clear, `funcs` / `session state` / evaluation answers were inspected for residue.

All commands below run from `$ROOT/tests/stress/areas/frontend/session_reset_systematic` with
binary `$ROOT/ucas`. Every kept golden was generated with `timeout 20` (CLI) /
`timeout 30` (MCP), run twice and byte-diffed (all deterministic, all exit 0). Exploratory
sequences total >200; 22 goldens kept.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 6 | CLI has NO clearing operation for function definitions — state survives every CLI "clear" |
| NLP | 1 | Wrong function resolved: English `its` binds to the last *defined* function |
| LIMIT | 1 | `--json` frontend `state` omits an empty `assumptions` key that MCP `state` reports |
| DETERMINISM | 1 | long `session reset` batch occasionally truncates reply stream |

## Findings

### WRONG-1 — CLI has NO clearing operation for function definitions — state survives every CLI "clear"
**Severity:** WRONG
_Original classification: `WRONG (state survives all clears / limit`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/session_reset_systematic
$ROOT/ucas 01_no_reset_cmds.ucas
$ROOT/ucas 02_no_reset_cmds2.ucas
```

**Observed:** (exact, 01):** `reset`, `clear`, `forget f`, `undefine f` all leave `f` defined:
```
> reset
_(reset: real) = reset
> funcs
f(x: u8) = x + 1
> clear
_(clear: real) = clear
> funcs
f(x: u8) = x + 1
> forget f
  note: no meaning was kept for "f" (nothing to forget)
> funcs
f(x: u8) = x + 1
> undefine f
... error: expected an expression
> funcs
f(x: u8) = x + 1
```
**02:** `del g`, `clear g`, `erase g` are parse errors; `forget everything` prints
`ok: forgot every assumption` yet `funcs` still lists `g(x: u8) = 2x`.

**Why it matters:** it's a bug:** `reset`/`clear` are not commands at all — they parse into junk free-variable
definitions (`_(reset: real) = reset`), and none of the plausible "forget/undef/del/erase/remove"
forms removes a definition. `forget everything` clears only the English assumption store.
The only operation that clears definitions is `session reset`, which exists solely in the
`--json`/`--mcp` frontends (verified: `cmd:reset` and `session reset` both empty `functions`).
A CLI user therefore cannot reset definitions at all.

### WRONG-2 — Only `session reset` clears everything; every other "clearer" leaves residue
**Severity:** WRONG
_Original classification: `WRONG / LIMIT (clearing operations have inconsistent reach`._
**Expected:** _not recorded_
**Reproducer:**
```sh
$ROOT/ucas --mcp < mcp_clear_matrix.jsonl
$ROOT/ucas --mcp < mcp_reset_matrix1.jsonl
```

**Observed:** (`mcp_clear_matrix`, parsed from `.out`):
```
id1  define f              -> f
id2  state                 -> functions ['f']
id3  session assume clear  -> assumptions {}
id4  state                 -> functions ['f']                <-- def survived
id5  define g ; id6 "forget everything"
id7  state                 -> functions ['f','g']             <-- defs survived
id8  let h ... ; id9 second initialize
id10 state                 -> functions ['f','g','h']          <-- ALL survived
id11 assume set {log:base2}; id12 "forget everything"
id13 state                 -> functions ['f','g','h'], assumptions {'log':'base 2'}  <-- survived
id14 use zen4; id15 session reset
id16 state                 -> functions [], active_model gt1030, assumptions {}
```
Contrast `mcp_reset_matrix1`: for each of `session define`, raw `ucas` define, English `let`,
English `define`, `session reset` returns `functions:[]` in the immediately following `state`.

**Why it matters:** it's a bug:** `session assume clear` is assumption-only (expected by name), but a second
`initialize` clears nothing (functions *and* assumptions leak across "sessions"), and English
`forget everything` leaves both definitions and JSON assumptions intact. `session reset` is the
only full clear. A client has no single operation whose scope is documented or predictable.

### WRONG-3 — Second `initialize` does not start a fresh session (state leaks across clients)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
$ROOT/ucas --mcp < mcp_double_init.jsonl
```

**Observed:** (exact, parsed):
```
id1  define f(x:u8)=x^2+1
id2  state      -> functions ['f']
id3  initialize (client-B)                    <- new handshake
id4  state      -> functions ['f']             <- A's function survived
id5  english "what is f of 3?" -> 'f(3)' (callable)
id6  session assume set {log:base2}
id7  initialize (client-C)
id8  state      -> functions ['f'], assumptions {'log':'base 2'}   <- both survived
id9  session reset
id10 state      -> functions [], assumptions {}
```

**Why it matters:** it's a bug:** a fresh `initialize` handshake on the same process inherits all prior
functions and assumptions; only an explicit `session reset` clears them. This is a cross-client
state-leak / wrong-function-resolution surface.

### WRONG-4 — Two independent assumption stores; English `forget everything` / `session assume clear` only clear one
**Severity:** WRONG
_Original classification: `WRONG (introspection/evaluation disagreement + wrong answer`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
$ROOT/ucas --mcp < mcp_two_stores.jsonl
```

**Observed:** (exact, parsed; `log` question answers from `text`):
```
id1 english "assume log means base 2"    -> ok (text: "log means base 2")
id2 english "what is the log of 8?"      -> log(8)/log(2)  = base 2 active
id3 state   -> assumptions {}            <-- English meaning invisible to state
id4 session assume set {log:base10}      -> assumptions {'log':'base 10'}
id5 state   -> assumptions {'log':'base 10'}
id6 english "what is the log of 100?"    -> log(100)/log(2) = 6.64  <-- STALE base 2 wins
id7 english "forget everything"          -> ok: forgot every assumption
id8 state   -> assumptions {'log':'base 10'}   <-- JSON assumption NOT cleared
id9 english "what is the log of 100?"    -> log(100)/log(10) = 2
```
A newer JSON assumption (`base 10`) is masked by an older English meaning (`base 2`) in the
English parser, giving a wrong numeric answer while `state()` claims `base 10`. On the clean
CLI, `forget everything` *does* clear English meanings (`07_assume.out`, natural log after forget),
confirming the stores are frontend-specific. `session reset` clears both stores (scenario D in
exploration: after E2+S10+reset, `log(8)` becomes ambiguous again).

### WRONG-5 — Failed `basis` definition still registers a phantom in `session state`
**Severity:** WRONG
_Original classification: `WRONG (introspection/evaluation disagreement; residue from a failed operation`._
**Expected:** _not recorded_
**Reproducer:**
```sh
$ROOT/ucas --mcp < mcp_phantom_basis.jsonl
```

**Observed:** (exact, parsed):
```
id1 state -> bases_extra []
id2 ucas "basis ghost { and(x,y) = x&y cost 3 }"
       -> ok:false, text: "<json>:1:30: error: 'cost' is not defined"
id3 state -> bases_extra ['ghost']          <-- phantom from FAILED definition
id4 analyze gates f=x&y basis ghost -> ok:false (error, unusable)
id5 session reset
id6 state -> bases_extra []                 <-- reset does remove it
```

**Why it matters:** it's a bug:** the definition failed and returned `ok:false`, yet `state.bases` advertises
`ghost` as an available basis. A client that trusts `session state` will try to use a basis that
has no gates. (The `basis ... cost 3` syntax itself failing is a separate documented LIMIT in
`gates_find_cost`; the novel point here is the phantom residue in state after the failure.)

### WRONG-6 — Introspection/evaluation disagreement: `_`-prefixed and builtin-named definitions
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
$ROOT/ucas --mcp < mcp_introspection.jsonl
$ROOT/ucas 03_builtin_shadow.ucas
$ROOT/ucas 04_underscore.ucas
```

**Observed:** (`mcp_introspection`):
```
id4 funcs  -> lists __x(x:real)=x+3 (and others)
id5 state  -> functions ['normal']          <-- _under / __x hidden
id6 show _under(10) -> _() = 12             <-- callable
id9 show sin(0)     -> _() = 0              <-- builtin, despite sin def listed
id10 funcs -> sin(x: real) = x + 1000       <-- listed but dead
```
**`04_underscore.out`:** user `_(x)=x+4`: `show _(10)` = 14; an unrelated `show 7+8` writes the
internal `_`; a later `show _(10)` = **140** (wrong value) and `funcs` is empty.

**Why it matters:** it's a bug:** `state()` is the structured "what is callable" inventory but hides `_`-prefixed
functions that `funcs` lists and that evaluate; conversely, builtin-named definitions appear in
`funcs` but calls resolve to the builtin. Both are introspection/evaluation disagreements that a
reset cannot fix (the same listings/evaluations recur until `session reset` removes the defs).

### NLP-1 — Wrong function resolved: English `its` binds to the last *defined* function
**Severity:** NLP
_Original classification: `NLP / WRONG`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
$ROOT/ucas 05_pronoun.ucas
$ROOT/ucas --mcp < mcp_pronoun_reset.jsonl
```

**Observed:** (`05_pronoun.out`):
```
> what is alpha of 5?    -> 6
> what is its range?     -> ucas: range beta    [90,110]   <-- WRONG referent
> what is its derivative?-> ucas: diff beta     -1
```
After a `session reset` the pronoun has nothing to bind (`mcp_pronoun_reset` ids 7–8: empty
statements), so it fails gracefully rather than resolving to a stale function.

### LIMIT-1 — `--json` frontend `state` omits an empty `assumptions` key that MCP `state` reports
**Severity:** LIMIT
_Original classification: `LIMIT (cross-frontend introspection shape mismatch`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf '%s\n' \
 '{"id":1,"cmd":"state"}' \
 '{"id":2,"cmd":"assume","args":{"set":{"log":"base 10"}}}' \
 '{"id":3,"cmd":"state"}' \
 | $ROOT/ucas --json
```

**Observed:** `id1` `state` has keys `functions/models/active_model/bases` but **no** `assumptions`
key; MCP `session state` always includes `"assumptions": {}`. Once an assumption exists (`id3`),
`--json` includes `"assumptions":{"log":"base 10"}`. A client parsing `--json` state cannot rely
on a stable shape. (Also: `--json cmd:reset` clears both functions and the English assumption
store — verified — so the clear reach matches MCP, only the state shape differs.)

### DETERMINISM-1 — long `session reset` batch occasionally truncates reply stream
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (documented with evidence; no golden kept`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (probe):
```sh
python3 -c '
import json
print(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}))
print(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}))
for i in range(1,1201): print(json.dumps({"jsonrpc":"2.0","id":i,"method":"tools/call","params":{"name":"session","arguments":{"op":"reset"}}}))
' | timeout 60 $ROOT/ucas --mcp > /tmp/many_reset.out 2>&1
```

**Observed:** (1 of 14 runs):** exit 0 but the last reply line was cut mid-JSON:
```
{"jsonrpc": "2.0", "id": 979, "result": {"content": [...], "structuredContent": {"id": 979, "ok": true, "cmd": "reset", "st
```
ids 980–1200 got no reply at all (221 requests silently lost). 13/14 reruns of the identical
input produced all 1201 well-formed replies with exit 0; a 1200-call `session state` control
always produced all 1201 replies. The one-off truncation is consistent with the rare MCP
"empty/dropped answer" sightings in other areas (likely the `timeout_s` fork / stream-desync
class). Because it is not reproducible, **no `.out` golden was kept** for it.

## Checks that passed

### Negative results / confirmed-good behaviour
- `session reset` is thorough in MCP/`--json`: it clears functions, both assumption stores,
  the active cost model (`use zen4` → `gt1030`), custom bases and custom models, and fails-
  definition phantoms. `mcp_reset_matrix{1,2,3}`, `mcp_model_basis_reset` confirm this.
- 1200 `session state` calls: all answered, no truncation.
- No crashes, signals, or hangs: all 22 goldens exit 0 under `timeout`.
- All three frontends agree that a *fresh process* starts with empty functions/assumptions and
  default model/bases (baseline probes).
