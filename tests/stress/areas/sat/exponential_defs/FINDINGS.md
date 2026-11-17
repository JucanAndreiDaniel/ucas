# Stress findings — `exponential_defs`

_Original heading: FINDINGS — `exponential_defs` (definition-chain / recursion-depth stress)_

# FINDINGS — `exponential_defs` (definition-chain / recursion-depth stress)

Binary: `$ROOT/ucas` (not rebuilt). All runs bounded with `timeout 15`
(30 s only for the deliberately long `find`/`wrap` probes). Work stayed inside this folder.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 3 | exponential definition chain: depth 14 segfaults (SIGSEGV, rc 139) |
| HANG | 1 | expensive analyses scale exponentially with chain depth |
| WRONG | 1 | STATE / WRONG — a rejected self-referential definition leaves a fabricated symbol |

## Findings

### CRASH-1 — exponential definition chain: depth 14 segfaults (SIGSEGV, rc 139)
**Severity:** CRASH
**Exact generator command** (from `IDEAS_UNDERGROUND.md` idea 1):

**Reproducer:**
```sh
python3 -c '
L=["f0(x: u8) = x + 1"]
for i in range(1,15): L.append("f%d(x: u8) = f%d(f%d(x))"%(i,i-1,i-1))
L.append("show f14(0)")
open("/tmp/opencode/bl14.ucas","w").write("\n".join(L)+"\n")'
timeout 15 $ROOT/ucas /tmp/opencode/bl14.ucas; echo "RC=$?"
```

Checked-in reproducer (same source, kept without `.out` because it crashes):

```sh
cd $ROOT/tests/stress/areas/sat/exponential_defs
timeout 15 $ROOT/ucas crash_dbl_d14.ucas; echo "RC=$?"
```

**Observed:** output** (tail):

```
> f12(x: u8) = f11(f11(x))
> f13(x: u8) = f12(f12(x))
> f14(x: u8) = f13(f13(x))
> show f14(0)
timeout: the monitored command dumped core
RC=139
```

Python `subprocess` sees `returncode == -11` (signal 11 = SIGSEGV). Crash takes ~0.5 s
(depth 13 takes ~0.03 s and returns `_() = 0`). Exit is 139 without `timeout`, so it is a
real segfault, not a timeout artifact.

**Why it matters:** `show f13(0)` succeeds; adding one more short definition and changing
only the called name kills the process.
**Expected:** either evaluate `f14(0)` (u8 wraps to 0)
or report a resource limit. No diagnostic is emitted. There is no depth check in the evaluator.

#### Threshold characterisation (all exit codes observed, `show fN(0)`)

| fan-out / level | widths tested | first crashing depth | leaf count at threshold |
|---|---|---|---|
| 2 (doubling) | 2 | **14** (bool: **13**) | 2^14 = 16384 |
| 3 (tripling) | 3 | **9** | 3^9 = 19683 (3^8 = 6561 is OK) |
| 4 (quadrupling) | 4 | **7** | 4^7 = 16384 (4^6 = 4096 is OK) |
| 1 (linear `f_i(x)=f_{i-1}(x)`) | 1 | **none up to depth 2000** | 2000 (no crash) |

So it is **semantic fan-out**, not raw syntactic/call depth, that kills it — a linear chain
of 2000 defs is fine, while a doubling chain of 14 defs dies.

**Exact boundary on an 8 MB stack** (binary-decomposed call tree, mixed levels so the fully
expanded expression has `N` nested `f0` applications):

```
N = 16340  rc=0
N = 16344  rc=0
N = 16345  rc=0
N = 16346  rc=-11 (SIGSEGV)
N = 16348  rc=-11
N = 16384  rc=-11
```

The crash occurs when the **fully inlined expression contains ~16346 nested `f0` calls**.

**Stack-size proof** (`ulimit -s` before the same depth-14 run):

```
ulimit -s 1024   -> rc=-11
ulimit -s 2048   -> rc=-11
ulimit -s 8192   -> rc=-11   (default)
ulimit -s 16384  -> rc=0
ulimit -s 32768  -> rc=0, depth 15 also rc=0, depth 16 also rc=0
ulimit -s unlimited -> rc=0
```

At 16 MB the depth-14 case passes but depth 15 segfaults; at 32 MB depths 14–16 pass.
This confirms an **unbounded-recursion stack overflow** whose threshold scales linearly with
`RLIMIT_STACK`.

**Type dependence:** with width 2, depths 12/13 always pass and depth 14 always crashes for
`u8 u16 u32 u64 i8 i16 i32 i64 int real f32 f64`. Only `bool` crashes one level earlier
(depth 13), because the `int -> bool` argument conversions add extra expansion frames:

```sh
cd $ROOT/tests/stress/areas/sat/exponential_defs
timeout 15 $ROOT/ucas crash_bool_d13.ucas; echo "RC=$?"
# > f13(x: bool) = f12(f12(x))
#   note: argument 1 of f12 converted from int to bool
# > show f13(0)
# RC=139
```

**Base-expression dependence** (width 2, depth 14): `x+1`, `x+2`, `x-1`, `x*2+1`,
`x/2`, `x^2+1`, `x*x+1` crash; `x`, `1`, `-x` do **not** crash (constant/identity folding
collapses the expansion). Goldens `07_const_base_d14.ucas` and `08_identity_base_d14.ucas`
record the two surviving boundary cases.

### CRASH-2 — only full-unrolling commands crash; `range`/`domain`/`table`/`crit` survive
**Severity:** CRASH
**Expected:** _not recorded_
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/exponential_defs
timeout 15 $ROOT/ucas crash_ctx_equiv_d14.ucas; echo "RC=$?"
```

Same 15-line depth-14 chain, varying only the final command (depth 13 in parentheses):

| command | depth 13 | depth 14 |
|---|---|---|
| `show fN(0)` | rc 0 | **rc 139** |
| `parse fN(0)` | rc 0 | **rc 139** |
| `equiv fN fN` | rc 0 | **rc 139** |
| `diff fN` | rc 0 | **rc 139** |
| `show fN` (no argument) | rc 0 | rc 0 (prints a 57 KB inlined sum) |
| `range fN` | rc 0 | rc 0 (`0..255`) |
| `domain fN` | rc 0 | rc 0 (256/256 defined) |
| `crit fN` | rc 0 | rc 0 (`1x + 0`) |
| `table fN` | rc 0 | rc 0 |
| `funcs` | rc 0 | rc 0 |

**Why it matters:** the same expression is safe under `range`/`domain`/`crit` but fatal
under `show`/`equiv`/`diff`/`parse`; a user cannot predict which analysis command will kill
the process. The crashing commands are exactly those that fully inline/evaluate the call
tree.

Other crash repro files of this family: `crash_w3_d9.ucas`, `crash_w4_d7.ucas`.

### CRASH-3 — CRASH / PROTO — `--mcp` and `--json` frontends do not contain the crash
**Severity:** CRASH
_Original classification: `CRASH / PROTO`._
**Why it matters:** _not recorded_
**`--mcp` without `timeout_s`** — the whole server dies and later requests in the same
session are never answered:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/exponential_defs
python3 - <<'EOF' > /tmp/opencode/mcp_kill.jsonl
import json
def j(o): print(json.dumps(o,separators=(",",":")))
j({"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}})
j({"jsonrpc":"2.0","method":"notifications/initialized"})
src="\n".join(["f0(x: u8) = x+1"]+["f%d(x: u8) = f%d(f%d(x))"%(i,i-1,i-1) for i in range(1,15)]+["show f14(0)"])+"\n"
j({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":src}}})
j({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"show","args":{"f":"1+1"}}}})
EOF
timeout 15 $ROOT/ucas --mcp < /tmp/opencode/mcp_kill.jsonl; echo "RC=$?"
```

**Observed:** `RC=139`, stdout contains **only** the `id:0` `initialize` reply (765 bytes);
no reply for `id:1` or `id:2`. `stderr` is empty. A single client request kills the shared
MCP server for every client.

**`--json` without `timeout_s`:**

```sh
python3 - <<'EOF' > /tmp/opencode/json_kill.txt
import json
L=["f0(x: u8) = x+1"]+["f%d(x: u8) = f%d(f%d(x))"%(i,i-1,i-1) for i in range(1,15)]+["show f14(0)"]
print(json.dumps({"id":1,"cmd":"ucas","args":{"source":"\n".join(L)+"\n"}}))
print(json.dumps({"id":2,"cmd":"show","args":{"f":"1+1"}}))
EOF
timeout 15 $ROOT/ucas --json < /tmp/opencode/json_kill.txt; echo "RC=$?"
```

**Observed:** `RC=139`, **zero bytes** on stdout — even `id:1` is lost.

**Containment exists but is opt-in:** adding `"timeout_s":3` to the `--mcp` request runs it
in a forked child. Golden `mcp_contained_crash.jsonl` / `.out` records this deterministic
behaviour:

```json
{"id":1,"ok":false,"cmd":"ucas","error":{"code":"internal","message":"the evaluation crashed (signal 11); the state is unchanged"}}
```

`isError: true`, and the following `analyze show 1+1` request is answered normally
(`_() = 2`). Without `timeout_s` no such guard is applied. **
**Expected:** the default request
path should not let one expression take down the server (or should always fork like the
`timeout_s` path does).

### HANG-1 — expensive analyses scale exponentially with chain depth
**Severity:** HANG
_Original classification: `HANG / LIMIT`._
**Expected:** _not recorded_
`find` and `wrap` are not protected by the full-unrolling crash but blow up in time:

**Observed:**
**Reproducer:**
```sh
find g(x:u8)=x+1              rc 0   0.13 s
find f10  (doubling depth 10) rc 0   3.76 s
find f12  (doubling depth 12) rc 0  17.15 s
find f13  (doubling depth 13) TIMEOUT 30 s   (reproduced twice)
find f14                      TIMEOUT 30 s
wrap f13                      rc 0   8.5–10.7 s (repeatable)
wrap f14                      TIMEOUT 15 s
```

Commands to reproduce (use the 14-line chain source from §1 and change the last line):

```sh
python3 -c '
L=["f0(x: u8) = x+1"]
for i in range(1,14): L.append("f%d(x: u8) = f%d(f%d(x))"%(i,i-1,i-1))
print("\n".join(L+["find f13"]))' > /tmp/opencode/find13.ucas
timeout 30 $ROOT/ucas /tmp/opencode/find13.ucas; echo "RC=$?"
```

**Why it matters:** a 13-statement program can hold `find` for >30 s and `wrap` for ~10 s
with no progress or budget feedback; unlike `show f13(0)` (0.03 s) there is no warning.

### WRONG-1 — STATE / WRONG — a rejected self-referential definition leaves a fabricated symbol
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/exponential_defs
timeout 15 $ROOT/ucas 10_failed_def_state.ucas; echo "RC=$?"
```

**Observed:** (exact):

```
> f(x: u8) = f(x)
10_failed_def_state.ucas:1:12: error: 'f' is not defined
    f(x: u8) = f(x)
               ^
> show f
_(f: real) = f
  -> real
> funcs
> show 1
_() = 1
  -> int
```

The definition is rejected (`'f' is not defined`), yet `show f` immediately succeeds by
inventing an anonymous definition `_(f: real) = f`; `f` is now usable as a free `real`.
Worse, `range f` on that injected symbol returns a completely fabricated answer:

```
> f(x: u8) = f(x)
error: 'f' is not defined
> range f
range of f:
  [-10, 10]   min at f ≈ -10, max at f ≈ 10
  grid of 20001 points over [-10, 10] (default; give x a range), extrema refined at critical points
```

**MCP variant** (`mcp_failed_def_state.jsonl` / `.out`): `session.define` of `f(x)=f(x)`
returns `parse_error: 'f' is not defined`, `session.funcs` reports an empty function list,
`session.state` shows `"functions": []` — but the subsequent `analyze show f` returns
`_(f: real) = f`. So the failed definition is not in the symbol table, yet referencing the
rejected name silently creates a new anonymous definition. Error handling is not atomic:
a rejected definition should leave no usable name behind.

**Related (mutual recursion):** forward references are also rejected at definition time,
not hung on (`09_mutual_reject.ucas`): `f(x)=g(x)` before `g` is defined gives
`error: 'g' is not defined`, and a later `show f(0)` notes `f(...) read as multiplication:
f is not a function` and fabricates `_(f: real) = 0`. No hang or crash from genuine mutual
recursion — such cycles cannot be constructed because the second definition always fails.

50 repeated failed self-referential definitions (`z0..z49`) also produced no state leak in
`funcs`; the leak is limited to the anonymous-definition fallback on a later reference.

## Checks that passed

### Non-findings (handled gracefully)
- Linear chains `f_i(x)=f_{i-1}(x)` up to depth 2000: rc 0.
- Self-recursive definitions (`f(x)=f(x)`, `f(x)=f(f(x))`, `f(x)=f(x)+1`): rejected with a
  clean error, no infinite loop.
- 3-way mutual cycles (`f->g->h->f`) and guarded recursion: rejected cleanly.
- Constant/identity-folding bases at depth 14 (`x`, `1`, `-x`): rc 0.
- `range`/`domain`/`crit`/`table` at depth 14: rc 0.
