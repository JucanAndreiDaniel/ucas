# Stress findings — `numeric_arg_overflow`

_Original heading: Findings — `numeric_arg_overflow`_

# Findings — `numeric_arg_overflow`

All runs used the prebuilt binary `$ROOT/ucas` with `timeout 15`
(and `timeout 40/60` where noted to separate true hangs from merely slow cases).
Exit codes were recorded from `$?`: `124` = timeout, `0` = normal exit. Every would-be
golden was run twice and byte-compared; all 14 goldens in this folder are deterministic.
**No case produced a signal / SIGSEGV** (no crashes were found in this area). Hangs,
huge-output cases and nondeterministically-timed cases are documented here instead of
being kept as goldens.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 2 | 1 — `abselftest 2147483647` is an unbounded CPU loop (also hangs the MCP raw tool) |
| WRONG | 7 | 1 — Real literals overflow to `inf`/`0` without any diagnostic, yielding unsound compariso… |
| LIMIT | 3 | 1 — `diophantine ... count 2147483647` emits ~394 KB of solutions in ~10 s (no output cap) |

## Findings

### HANG-1 — 1 — `abselftest 2147483647` is an unbounded CPU loop (also hangs the MCP raw tool)
**Severity:** HANG
_Original classification: `HANG / LIMIT`._
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas -e 'abselftest 2147483647' > /tmp/h1.out 2>&1; echo $?
# -> 124   (0 bytes of output)
```

The identical hang reaches the MCP `ucas` escape-hatch tool (no `timeout_s`):

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":"abselftest 2147483647"}}}' | timeout 15 $ROOT/ucas --mcp; echo $?
# -> 124   (0 bytes)
```

**Observed:** rc `124`, no output at all. `abselftest N` uses bare `atoi(s)` with no
upper bound (`src/absalg_cmd.c:1288-1297`); N is the number of random group pairs and
there is no internal time limit. Scaling of the *fast* cases (measured):
`N=1000` → 0.32 s, `N=10000` → 2.32 s, so `N=100000` needs ~23 s and `N=2147483647`
never finishes.

**Expected:** either a documented cap on N or a wall-clock timeout inside the self-test.
(With the MCP tool an explicit `timeout_s` does contain it — see golden
`mcp_ucas_timeout.jsonl`, which returns `error (timeout): timed out after 1 s`.)

### HANG-2 — 2 — `diophantine ... search 9999999999999999999999` saturates `strtoll` and never finishes
**Severity:** HANG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas -e 'diophantine a/(b+c) + b/(a+c) + c/(a+b) = 4 search 9999999999999999999999' > /tmp/h2.out 2>&1; echo $?
# -> 124
```

**Observed:** rc `124`; the sieved point search prints only the preamble (567 bytes)
and then stops making progress:

```
equation: a^3 - 3*a^2*b - 3*a^2*c - 3*a*b^2 - 5*a*b*c - 3*a*c^2 + b^3 - 3*b^2*c - 3*b*c^2 + c^3 = 0  (with b + c != 0, a + c != 0, a + b != 0)
a plane cubic in P^2 (homogeneous of degree 3 in a, b, c)
rational points found by search: 18; base point P0 = (-1 : 1 : 0), a flex: its tangent line to infinity and P0 to O give Weierstrass form directly
Weierstrass form: y^2 + 36/91*x*y - 7776/8281*y = x^3 + 30456/8281*x^2 - 699840/753571*x - 10077696/68574961
minimal model E: y^2 + x*y + y = x^3 - 234*x + 1352, by [u, r, s, t] = [36/91, -10152/8281, 0, 559872/753571]
```

With `timeout 40` it still hangs (>40 s, same 567 bytes) — a true infinite/very-long
search, not a slow-but-finite run. `search` is parsed by `strtoll(t+6,&t,10)` with no
range check (`src/ec_cmd.c:977-978`); the out-of-range literal saturates to `LLONG_MAX`
and is passed as the point-search bound (`src/ecdio.c:1862`). Normal `search 60`/`200`
finish in 0.2–0.3 s.

### LIMIT-1 — 1 — `diophantine ... count 2147483647` emits ~394 KB of solutions in ~10 s (no output cap)
**Severity:** LIMIT
_Original classification: `LIMIT (resource asymmetry`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 40 $ROOT/ucas -e 'diophantine a/(b+c) + b/(a+c) + c/(a+b) = 4 count 2147483647' > /tmp/h3.out 2>&1; echo $?
# -> 0, time ~10 s, 393884 bytes, 360 "solution N" blocks with integers up to 891 digits
```

**Observed:** rc `0` after ~10.1 s, 393,884 bytes. Under the 10 s timeout used elsewhere
in the project this is a `124` timeout; under 15 s it completes (and was observed both ways
in this run depending on system load). The unchecked `count` (`src/ec_cmd.c:973-974`) is
used as the number of point combinations to print (`src/ecdio.c:1910`), with no cap on the
amount of output. A single CLI line can therefore generate hundreds of kilobytes of
huge-integer text. Not kept as a golden because of its size and load-sensitive timing.

### LIMIT-2 — 2 — `approx` negative/huge options are silently ignored; the underlying search is ~7 s
**Severity:** LIMIT
_Original classification: `LIMIT / WRONG (silently ignored option`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproduce:**

**Reproducer:**
```sh
timeout 15 $ROOT/ucas -e 'approx sqrt(x) in 1..2 as f32 list 0'       # rc 0, ~6.8 s
timeout 15 $ROOT/ucas -e 'approx sqrt(x) in 1..2 as f32 list 2147483647' # rc 0, ~6.8 s
timeout 15 $ROOT/ucas -e 'approx sqrt(x) in 1..2 as f32 degree 0'      # rc 0, ~7.3 s
```

**Observed:** each completes with the *same* 3.8 KB report as a plain `approx sqrt(x) in
1..2 as f32` — `list 0`, `list 2147483647` and `degree 0` have no effect. Under CPU load
these crossed 15 s in this run and were observed as rc `124` (0 bytes), so they are **not**
deterministic-timing goldens. `samples -1`, `nodes -1`, `max -1` are rejected cleanly
(`error: unknown approx option`) and `budget -1`/`seed -1` are range-checked
(golden `11_approx_rejected.ucas`). Not hangs: ~7 s is intrinsic to this `approx` search.

### WRONG-1 — 1 — Real literals overflow to `inf`/`0` without any diagnostic, yielding unsound comparisons
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer / observed:

**Observed:**
```sh
$ $ROOT/ucas -e 'show 1e400'
_() = inf
  -> real
$ $ROOT/ucas -e 'show -1e400'
_() = -inf
  -> real
$ $ROOT/ucas -e 'show f32(1e400)'
_() = inf
  -> f32
$ $ROOT/ucas -e 'show 1e400 == 1e401'
_() = 1            # two *different* overflowing literals compare equal
  -> bool
$ $ROOT/ucas -e 'show 1e400 - 1e400'
_() = 0            # inf - inf should be NaN
  -> bool/real
```

Other accepted nonsense: `1e400 != 1e400` → `0`, `1e400*0` → literal `inf*0`,
`1e400/1e400` → `inf/inf`, `1e-400` → `0`, `f32(1e40)` → `inf`. Integer literals, by
contrast, *are* ERANGE-checked (`... is too large ...`, golden
`resource_limits/08_huge_ints.out`). Root cause: `src/parse.c:280-300` sets `errno=0`
but the real branch `return`s at 292-294 before the `errno == ERANGE` check at 298.
Deterministic quick cases are pinned in `02_real_overflow.out` / `03_real_arithmetic.out`.

### WRONG-2 — 2 — Non-finite ids are smuggled through both JSON frontends as bare `1e400`
**Severity:** WRONG
_Original classification: `WRONG (protocol conformance / invalid JSON value`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1e400,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' | $ROOT/ucas --mcp
# -> {"jsonrpc": "2.0", "id": 1e400, "result": { ... }}
printf '%s\n' '{"id": 1e400, "cmd": "help", "args": {}}' | $ROOT/ucas --json
# -> {"id": 1e400, "ok": true, "cmd": "help", ...}
```

**Observed:** the exact original token (`1e400`, `-1e400`, `1E+400`, `1e9999`,
`99999999999999999999999`, `-0.0`, …) is copied verbatim into every response, including
`structuredContent.id`. Python's `json.loads` decodes `{"id":1e400}` to
`{'id': inf}` with `math.isfinite(id) == False`; strict JSON consumers reject a
non-finite number, and a client-side `isfinite(num)` validation is bypassed.
Root cause: `src/json.c:327` stores `strtod(v->s,NULL)` without an `isfinite` check
(unlike `jv_num()` at line 68) and `jv_write()` at 547-551 emits `v->s` verbatim.
Deterministic: pinned in `mcp_id_infinity.out`.

### WRONG-3 — 3 — `abselftest N`: negative, zero, overflowing and junk values are silently accepted
**Severity:** WRONG
_Original classification: `WRONG (silent clamping / unchecked atoi`._
**Why it matters:** _not recorded_
**Reproduce / observed:**

**Observed:**
**Reproducer:**
```sh
$ ucas -e 'abselftest -5'    -> 100 random pairs ...   # negative silently -> default 100
$ ucas -e 'abselftest 0x10'  -> 100 random pairs ...   # atoi stops at 'x' -> 0 -> 100
$ ucas -e 'abselftest 12junk'-> 12 random pairs ...    # trailing junk silently ignored
$ ucas -e 'abselftest 99999999999999999999999' -> 100 random pairs ...  # overflow -> <=0 -> 100
$ ucas -e 'abselftest 2147483648' -> 100 random pairs ...                 # INT overflow -> 100
```

**Expected:** a diagnostic for negative/overflowing/junk N, or at least acceptance with a
reported effective value. The summary line reports only the effective N, so the user
cannot tell that `0x10` or a 23-digit number was replaced by 100. Pinned (all fast and
deterministic) in `01_abselftest_defaults.out`.

### WRONG-4 — 4 — `diophantine` `count` / `maxmult` / `search` are parsed unchecked and silently change semantics
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproduce / observed** (on `a/(b+c) + b/(a+c) + c/(a+b) = 4`, which normally finds one
solution):

**Observed:**
**Reproducer:**
```sh
$ ucas -e 'diophantine ... = 4 count -1'
   ... rank 1 (proved ...)
   (NO "solution ..." block, NO "points tried" line)
$ ucas -e 'diophantine ... = 4 count 9999999999999999999999'
   ... rank 1 (proved ...)
   (NO solution printed -- strtoll saturates to LONG_MAX, (int) cast -> -1)
$ ucas -e 'diophantine ... = 4 maxmult 9999999999999999999999'
   ... solution 1, from -1*P1: ...     (huge maxmult -> int -1 -> silently ignored)
$ ucas -e 'diophantine ... = 4 count -1 search -1 maxmult -5'
   ... rank 1 (proved ...)             (all three options silently accepted, no solutions)
$ ucas -e 'diophantine x^2 + 2*y^2 = 3 count 12junk'
<arg>:1:13: error: diophantine: unknown option at "junk"     # trailing junk -> clean error
```

`count -1` sets `o.want < 0`, which sets `nvec=0` and suppresses *all* solutions
(`src/ecdio.c:1910-1912, 2025-2030`) — a negative count silently means "print nothing"
rather than an error. `src/ec_cmd.c:973-982` uses `(int)strtol`/`strtoll` with no sign,
range or end-pointer validation. Note the inconsistency: `count 12junk` produces a clean
"unknown option" error while `count -1` is silently accepted. Pinned in
`04_dio_options.out` and `05_dio_junk.out`. `maxmult 2147483647` is the one variant that
*is* rejected (`error: too many combinations (lower maxmult)`).

### WRONG-5 — 5 — `table f max <overflowing>` silently prints an empty table
**Severity:** WRONG
_Original classification: `WRONG (unchecked (int`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproduce / observed:**

**Observed:**
**Reproducer:**
```sh
$ printf 'f(x:u8)=x*x\ntable f max 2147483648\n' | ucas
> table f max 2147483648
(no rows at all)
$ printf 'f(x:u8)=x*x\ntable f max 18446744073709551615\n' | ucas
> table f max 18446744073709551615
(no rows at all)
$ printf 'f(x:u8)=x*x\ntable f max -1\n' | ucas
<arg>:2:14: error: unexpected '1' after the statement     # negative tokenizes as '-' '1'
```

`opt_int()` at `src/parse.c:3067-3073` returns `(int)N.ki[v]` with no range check;
`2147483648` → `INT_MIN`, `2^64-1` → `-1`, and a negative `max` makes `cmd_table` print
nothing. `table f max 0` prints `... (table max 0)`. Pinned in `06_table_max.out`.

### WRONG-6 — 6 — `find N` negative counts are silently remapped
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproduce / observed:**

**Observed:**
**Reproducer:**
```sh
$ printf 'f(x:u8)=x*x\nfind f -1\n' | ucas
find 1: 1 point, computing in u8, costs from gt1030    # -1 -> 1
$ printf 'f(x:u8)=x*x\nfind f -2147483648\n' | ucas
find 0: 1 point, computing in u8, costs from gt1030    # INT_MIN -> "find 0"
$ printf 'f(x:u8)=x*x\nfind f 18446744073709551615\n' | ucas
find f: 256 points, ...                               # u64 max -> (int)-1 -> default
```

`src/parse.c:3975-3976`: `want = (int)N.ki[number(p)]` with no validation. Pinned in
`07_find_counts.out`.

### WRONG-7 — 7 — `fit ... samples -1` / `trials -1` / `degree -1` invent free variables and fit nonsense
**Severity:** WRONG
_Original classification: `WRONG (silent misparse → bogus numeric result`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproduce / observed:**

**Observed:**
**Reproducer:**
```sh
$ ucas -e 'fit a*x+b ~ 2*x+1 samples -1'
fit a*x + b to 2x + samples - 1 (max relative error, 4096 sample points):
  b = 10
  objective 2206.99
  x*samples + 10
  max rel error 2.88915e+16 (2.89e+18%) at x=4.48, samples=-7.96
  mean rel error 2.05406e+12 over 1002001 points
```

`samples` is not a `fit` option, so the parser silently introduces it as a new free
variable (likewise `trials`, `degree`), producing a 2-variable fit with a meaningless
answer and no warning. `count -1` is handled differently still: `sorry: I didn't follow
"count -1"`. Pinned in `10_fit_misparse.out`.

### LIMIT-3 — 3 (positive controls) — `stoke` / `tcdot` / MCP numeric arguments *are* validated
**Severity:** LIMIT
_Original classification: `LIMIT (graceful, for contrast`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`stoke` steps/restarts/len/seed and all `tcdot` numeric options return clean range errors
for negative/huge values (`error: stoke: steps N, 1 to 100000000`,
`error: tcdot: samples from 1 to 100000`, …). In the JSON frontends a non-finite numeric
argument is also cleanly rejected with `bad_request: <field>: an integer`, e.g.
`tools/call analyze {op:"table", args:{f:"x", max:1e400}}` →
`error (bad_request): max: an integer`. This is inconsistent with the CLI, where the
same `1e400` is silently accepted (WRONG-2/5). Pinned in `08_stoke_rejected.out`,
`09_tcdot_rejected.out` and `mcp_numeric_args.out`.

## Checks that passed

### No crashes
No input in this area caused a non-zero signal exit (SIGSEGV/SIGABRT) or truncated JSON
from a crash. All non-timeout runs exited `0` (ucas reports errors on stdout with rc 0 by
design). The resource failures found here are hangs/huge-output/slow searches, not memory
corruption.
