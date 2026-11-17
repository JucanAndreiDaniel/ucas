# Stress findings — `resource_limits`

_Original heading: Findings — `resource_limits`_

# Findings — `resource_limits`

All runs used the prebuilt binary `$ROOT/ucas` with `timeout 15` and, where
stated, an address-space cap via `ulimit -v <KB>`. Exit codes were recorded from `$?` (shell
`139` = signal 11 / `SIGSEGV`, `2` = clean error exit). Only deterministic, successful cases
were kept as goldens; crashes and hard limits are documented here instead.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 7 | 1 — Stack overflow (SIGSEGV) on deeply nested parentheses |
| HANG | 1 | HANG / DETERMINISM |
| LIMIT | 6 | 1 — Tables and list literals are capped at 1024 entries |

## Findings

### CRASH-1 — 1 — Stack overflow (SIGSEGV) on deeply nested parentheses
**Severity:** CRASH
**Reproducer:**
Reproducer** (2000 nested parens; 1500 succeeds, 1600 already crashes):

```sh
python3 -c 'open("/tmp/rl_paren.ucas","w").write("show "+"("*2000+"1+2"+")"*2000+"\n")'
timeout 15 $ROOT/ucas /tmp/rl_paren.ucas > /tmp/rl_paren.out 2>&1; echo $?
```

**Observed:** exit code `139` (`SIGSEGV`, signal 11). The output contains only the echoed
input (`> show (((((...`) — no answer, no diagnostic:

```
> show (((((((((((((((((((((((...   (4000 paren characters) ...))))))))))))))))))))))))
Segmentation fault (core dumped)
```

Threshold probing: `show (...)^1500` → exit 0; `^1600`, `^2000`, `^5000`, `^100000` → exit 139.

**Why it matters:** the expression parser/evaluator recurses once per nesting level with no
depth guard, so a well-formed expression overflows the process stack.
**Expected:** a graceful
`expression nested too deeply` error, or an iterative parser. A `1200`-paren version is kept
as the safe golden `04_parens_1200.ucas`.

**MCP note:** the same input via MCP is contained by the fork isolation and returns
`error (internal): the evaluation crashed (signal 11); the state is unchanged` (golden
`mcp_limits_errors.jsonl`, id 4), and the session keeps working. The underlying crash is still
present, just isolated.

### CRASH-2 — 2 — Stack overflow (SIGSEGV) on a long unary-minus chain
**Severity:** CRASH
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (1500 minuses OK, 2000 crashes):

```sh
python3 -c 'open("/tmp/rl_minus.ucas","w").write("show "+"-"*2000+"1\n")'
timeout 15 $ROOT/ucas /tmp/rl_minus.ucas > /tmp/rl_minus.out 2>&1; echo $?
```

**Observed:** exit `139` / SIGSEGV; output is just the echoed `> show -----...1` line,
no result. Also crashes at 3000, 5000, 50000, 100000 minuses.

**Why it matters:** the unary-operator production recurses per token with no depth limit;
expected a depth cap / graceful error.

### CRASH-3 — 3 — Stack overflow (SIGSEGV) on deeply nested function calls
**Severity:** CRASH
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (1500 calls OK, 2000 crashes):

```sh
python3 -c 'open("/tmp/rl_abs.ucas","w").write("show "+"abs("*2000+"1"+")"*2000+"\n")'
timeout 15 $ROOT/ucas /tmp/rl_abs.ucas > /tmp/rl_abs.out 2>&1; echo $?
```

**Observed:** exit `139` / SIGSEGV, echoed input only, no answer. Crashes at 2000/5000/20000.

**Why it matters:** call-argument parsing (or AST evaluation) recurses per nesting level;
expected a graceful depth limit. A `1200`-deep version is kept safe in `05_deep_ops_1200.ucas`.

### CRASH-4 — 4 — Stack overflow (SIGSEGV) on nested conversions `u8(u8(...))`
**Severity:** CRASH
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (1000 OK, 2000 crashes):

```sh
python3 -c 'open("/tmp/rl_conv.ucas","w").write("show "+"u8("*2000+"7"+")"*2000+"\n")'
timeout 15 $ROOT/ucas /tmp/rl_conv.ucas > /tmp/rl_conv.out 2>&1; echo $?
```

**Observed:** exit `139` / SIGSEGV, echoed input only.

**Why it matters:** same recursion-depth problem as CRASH-3, now through conversion nodes.

### CRASH-5 — 5 — Stack overflow (SIGSEGV) on nested table indexing `[[[...7...]...]`
**Severity:** CRASH
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (1000 OK, 2000 crashes):

```sh
python3 -c 'open("/tmp/rl_idx.ucas","w").write("show "+"["*2000+"7"+"]"*2000+"\n")'
timeout 15 $ROOT/ucas /tmp/rl_idx.ucas > /tmp/rl_idx.out 2>&1; echo $?
```

**Observed:** exit `139` / SIGSEGV, echoed input only.

**Why it matters:** index-expression nesting recurses without a depth cap.

### CRASH-6 — 6 — Stack overflow (SIGSEGV) on nested absolute-value bars `||||...`
**Severity:** CRASH
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (1000 OK, 2000 crashes):

```sh
python3 -c 'open("/tmp/rl_bars.ucas","w").write("show "+"|"*2000+"7"+"|"*2000+"\n")'
timeout 15 $ROOT/ucas /tmp/rl_bars.ucas > /tmp/rl_bars.out 2>&1; echo $?
```

**Observed:** exit `139` / SIGSEGV, echoed input only.

**Why it matters:** `|...|` parsing recurses per pair of bars without a depth cap.
`1000` bars succeeds; `2000`/`5000` crash.

### CRASH-7 — 7 — SIGSEGV at startup when the address space is capped at ~20 MB
**Severity:** CRASH
_Original classification: `CRASH (OOM handling`._
**Expected:** _not recorded_
**Reproducer:**

```sh
echo 'show 1+2' > /tmp/rl_tiny.ucas
( ulimit -v 20000; timeout 15 $ROOT/ucas /tmp/rl_tiny.ucas ); echo $?
```

**Observed:** exit `139` / SIGSEGV with **zero bytes** of output. With the same trivial input:
`ulimit -v 24000` → exit `127`, `ucas: error while loading shared libraries: libc.so.6: failed
to map segment from shared object` (loader fails cleanly);
`ulimit -v 26000` → exit `0`, normal answer. So there is a narrow band (≈20–23 MB) where the
binary starts but dies with a null/unchecked allocation before its own OOM handler is installed.

**Why it matters:** an allocation failure at startup should produce the same clean
`ucas: out of memory` error (exit 2) that the program already uses elsewhere, not SIGSEGV.

### LIMIT-1 — 1 — Tables and list literals are capped at 1024 entries
**Severity:** LIMIT
_Original classification: `LIMIT (graceful`._
**Expected:** _not recorded_
**Reproducer:**

```sh
python3 -c 'open("/tmp/rl_tab.ucas","w").write("show ["+",".join(str(k) for k in range(1025))+"]\n")'
timeout 15 $ROOT/ucas /tmp/rl_tab.ucas 2>&1 | grep error
```

**Observed:** `/tmp/rl_tab.ucas:1:4017: error: table too long`. Exactly 1024 entries succeed;
1025 fails. The same limit applies to `[...][i]` lookup tables used in definitions. A
100000-entry table produced a 716 KB echo but no lookup works because of this cap.

**Why it matters:** this is a hard, undocumented resource ceiling; large constant tables
(the focus of this area) are silently refused past 1024 entries. Documented here and exercised
at the boundary by golden `03_table_1024.ucas`.

### LIMIT-2 — 2 — `x in { ... }` value lists are capped at 128 values
**Severity:** LIMIT
_Original classification: `LIMIT (graceful`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
python3 -c 'open("/tmp/rl_in.ucas","w").write("f(x: u32 in {"+",".join(str(k) for k in range(129))+"}) = x\n")'
timeout 15 $ROOT/ucas /tmp/rl_in.ucas 2>&1 | grep error
```

**Observed:** `/tmp/rl_in.ucas:1:416: error: x: at most 128 values in a list`. 128 values
succeed. Kept as golden `07_inlist_128.ucas`; the over-limit case is in
`mcp_limits_errors.jsonl` id 2.

### LIMIT-3 — 3 — `match` arms and piecewise branches are capped at 255
**Severity:** LIMIT
_Original classification: `LIMIT (graceful`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
python3 -c 'open("/tmp/rl_m.ucas","w").write("f(x: u32) = match x { "+",".join("%d => %d"%(k,k) for k in range(256))+", _ => 0 }\n")'
timeout 15 $ROOT/ucas /tmp/rl_m.ucas 2>&1 | grep error
```

**Observed:** `/tmp/rl_m.ucas:1:2620: error: too many match arms`. 255 arms OK, 256 fails.
Piecewise `{ x if c, ... }` has the same 255 limit (`error: too many pieces`). Kept at the
boundary in `11_match_255.ucas`.

### LIMIT-4 — 4 — `taylor` order capped at 12
**Severity:** LIMIT
_Original classification: `LIMIT (graceful`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
echo 'taylor sin(x) order 13' > /tmp/rl_t.ucas
timeout 15 $ROOT/ucas /tmp/rl_t.ucas 2>&1 | grep error
```

**Observed:** `/tmp/rl_t.ucas:1:23: error: order 0 to 12`. High-order series recursion
(50/200/1000 requested) is refused rather than attempted; golden `09_expand_series.ucas`
exercises order 12.

### LIMIT-5 — 5 — `expand (1+x)^n` silently stops expanding above degree 64
**Severity:** LIMIT
_Original classification: `LIMIT (silent no-op`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
echo 'expand (1+x)^65' > /tmp/rl_e.ucas
timeout 15 $ROOT/ucas /tmp/rl_e.ucas 2>&1
```

**Observed:**

```
> expand (1+x)^65
expand (x + 1)^65
  = (x + 1)^65
  check: exact (both sides have the same normal form)
```

At n=64 the polynomial is expanded but the output carries
`note: coefficients beyond 2^53 are printed rounded (numbers in expressions are doubles), so no check is printed`.
At n>=65 the request is a silent no-op with no note that a size/depth limit was hit; expected
either an explicit "degree too high" note or a symbolic-but-labelled result. Golden
`09_expand_series.ucas` covers both sides of the boundary (50, 200).

### LIMIT-6 — 6 — Large `find` under a tight address-space cap exits 2 with a clean OOM message
**Severity:** LIMIT
_Original classification: `LIMIT (clean, positive control`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cat > /tmp/rl_oom.ucas <<'EOF'
f(x: u16) = ((x*5+3)>>2) xor (x>>4)
find f
EOF
( ulimit -v 100000; timeout 15 $ROOT/ucas /tmp/rl_oom.ucas > /tmp/rl_oom.out 2>&1 ); echo $?
tail -1 /tmp/rl_oom.out
```

**Observed:** exit `2`, last line `ucas: out of memory` (the 65536-entry u16 table candidate
cannot be materialized under 100 MB). With `ulimit -v 200000` the same input exits `0` and
completes. This is correct OOM handling and is recorded here as a reference: contrast with
CRASH-7, where an early startup allocation failure is not handled.

### HANG-1 — HANG / DETERMINISM
**Severity:** HANG
_Original classification: `HANG / DETERMINISM`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
No hangs and no nondeterministic outputs were found in this area. Every golden in this folder
was run twice under `timeout 15` + `ulimit -v 2000000` and the two outputs were byte-identical;
all 15 CLI goldens and both MCP goldens also match the no-`ulimit` output produced by
`tests/stress/run.sh`. The MCP crash-recovery message (CRASH-1 note) is itself deterministic
and is captured in `mcp_limits_errors.out`.

Note: quadratic-complexity operations that might have hung (4M-point `range` over `isqrt`,
`popcount`, division; 20k `find` budgets; 20k definitions; 100k-entry tables) all completed in
under 5 s, so no `HANG` finding is warranted.

## Checks that passed

_No separate passed checks were recorded in the original document._
