# Stress findings — `x86_intrinsics_mca`

_Original heading: x86 intrinsics / µarch models / mca — findings_

# x86 intrinsics / µarch models / mca — findings

All commands below are copy-pasteable from
`$ROOT/tests/stress/areas/gpu/x86_intrinsics_mca` unless noted.
Binary: `$ROOT/ucas`. Every candidate was run with
`timeout 15..30`; all durable goldens were run twice and byte-diffed.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | MCP `mca` with an inline function-definition string invents `==` instructions and inflates… |
| LIMIT | 3 | `x86check` is dead in the shipped environment: it invokes `cc -ferror-limit=0`, but host `… |
| DETERMINISM | 1 | MCP server process died under a flood of parallel `mca` calls (environment caveat) |

## Findings

### WRONG-1 — MCP `mca` with an inline function-definition string invents `==` instructions and inflates the throughput estimate
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/gpu/x86_intrinsics_mca
$ROOT/ucas --mcp < mcp_x86_mca_inline.jsonl
```

**Observed:** (from `mcp_x86_mca_inline.out`, `structuredContent.result.blocks[0]`):

```
id 2  cmd "mca q on skl"                                   ok=true  cycles=10  instructions=6
        lea 3x / add 3x+7 / mulx (3x+7)/13 / shl ... / popcnt ... / add ...
id 3  cmd "mca q(x: u32) = (x*3+7)/13 + popcnt(x) on skl"  ok=true  cycles=11  instructions=7
        ... same 6 as above ...
        add       (3x + 7)/13 + popcount(x) == (… (24
id 6  cmd "mca h(x: u32) = x + 1 on skl"                   ok=true  cycles=13  instructions=5
        cvtsi2ss  real(x)
        vmulps    h*real(x)
        add       x + 1
        cvtsi2ss  real(x + 1)
        vcmpps    h*real(x) == real(x + 1)
id 5  cmd "mca g on skl"                                   ok=true  cycles=1  instructions=1   (add x + y)
id 4  cmd "mca g(x: u32, y: u32) = x + y on skl"           ok=true  cycles=2  instructions=2   (extra "add x + y == x + y")
```

**Why it matters:** it is a bug / expected.** The `mca` op builds the command string
`mca <f> on <model>`. When `f` is a *definition* rather than a bare name,
the parser reads the definition's `=` as boolean `==`, so a free variable
(`h`, `q`) is introduced and a bogus compare instruction is scheduled. For
`h(x: u32) = x + 1` an integer, 1-cycle, 1-instruction function is silently
reported as 13 cycles of float conversion/multiply/compare code.
**Expected:**
an inline definition gives the same answer as the by-name call, or is
rejected. The documented structured form *does* work — verified:

```json
{"f":{"body":"x + 1","params":[{"name":"x","type":"u32"}]},"model":"skl"}
```

gives `cmd "it(x: u32) = x + 1 ; mca it on skl"`, cycles=1, 1 instruction.
Note the schema/example does not tell users that the string form must be a
bare name; `f: "x + 1"` is explicitly accepted ("a name, an expression, or
{body,params}") and is analysed as untyped `real` code (`vaddps`).

### WRONG-2 — the "unknown x86 µarch" error lists omit the valid `zen2` model
**Severity:** WRONG
_Original classification: `WRONG (minor`._
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'mca q on bogus\n' | $ROOT/ucas
printf 'use bogus\n' | $ROOT/ucas
printf 'mca q on zen2\n' | $ROOT/ucas
```

**Observed:**

```
<stdin>:1:15: error: unknown x86 µarch 'bogus' (skl skx glc rpl zen4 x86v2 x86v3 x86v4)
<stdin>:1:5:  error: unknown model 'bogus' (the models: gt1030, sm75, sm86, rdna2, ga104, vangogh, mali_g715, skl, skx, glc, rpl, zen2, zen4, x86v2, x86v3, x86v4)
mca of q on zen2 (znver2)     <- zen2 actually works
```

The same stale list appears in `model skl` errors from MCP `x86_model`
(missing `name`) and in `intrinsic ... on bogus` / `intrinsics ... on bogus`.

**Why it matters:** it is a bug / expected.** `zen2` is a first-class µarch (`x86 models`
prints it, `model zen2` works, `mca ... on zen2` works), so the diagnostic
that is supposed to enumerate the valid choices is wrong and misleads users.

### LIMIT-1 — `x86check` is dead in the shipped environment: it invokes `cc -ferror-limit=0`, but host `cc` is GCC
**Severity:** LIMIT
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/gpu/x86_intrinsics_mca
timeout 25 $ROOT/ucas 16_x86check_cc.ucas
cc --version | head -1
```

**Observed:**

```
> x86check _mm_add_epi32 n 4
x86check: cc failed:
cc: error: unrecognized command-line option '-ferror-limit=0'

cc (GCC) 16.2.1 20260810
```

Every `x86check` form fails this way (no filter, name filters, `avx512`,
`n 0`, `n 1`, `n 100`); `CC=clang` does not help because the command is
hardcoded in `src/x86intr_tab.inc`. The MCP `x86`/`x86check` op simply
returns the same text with `ok=true`.

**Why it matters:** it is a bug / expected.** `-ferror-limit` is a clang flag and
`/usr/bin/clang` is installed, but `x86check` hardcodes `cc` (GCC here), so
the documented "check lane semantics against the host cc" feature never
runs. With a shim (`mkdir -p /tmp/ccshim; ln -sf /usr/bin/clang /tmp/ccshim/cc;
PATH=/tmp/ccshim:$PATH ...`) it works and the catalogue is correct:
`x86check _mm_add_epi32 n 8` → "`1 agree, 0 differ`"; additionally `_mm_abs`,
`_mm_avg`, `_mm_min`, `_mm_max`, `_mm_sad`, `_mm_shuffle` (121 immediates),
`_mm_cmp`, `_mm_cvtt`, `_mm_movemask`, `aesenc`, `pclmul`, `crc32`, `popcnt`,
`lzcnt`, `_mm512_add_epi32`, `_mm512_sqrt`, `_mm512_fmadd` all reported
`0 differ`.
**Expected:** pick a compiler that accepts the flag, or degrade
gracefully instead of failing every call.

### LIMIT-2 — `mca` on an undefined/failed function returns a bare header, no body, no error
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/gpu/x86_intrinsics_mca
$ROOT/ucas 13_mca_freevar.ucas
```

**Observed:**

```
> a(x: u32) = x + y
13_mca_freevar.ucas:1:17: error: 'y' is not defined
> mca a on skl
mca of a on skl (skylake)          <- and nothing else
```

Also in MCP: a definition that fails on an ambiguity (e.g. `x&y|x^y` under
the MCP `ucas` op without `assume`) is followed by `mca f25 on skl`
returning `ok=true`, `blocks=[]` and just the header text.

**Why it matters:** it is a bug / expected.** A request for a throughput estimate that
cannot be produced should report an error/warning, not an apparently
successful empty analysis.

### LIMIT-3 — overriding an x86 model with `model NAME {...}` changes `cost` but not `mca`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'model skl { iadd: 99, imul: 77 }\nq(x: u32)=x*3+7\ncost q model skl\nmca q on skl\n' \
  | $ROOT/ucas
```

**Observed:**

```
cost of q under skl: 176 (2 operations, shared subterms counted once)
  iadd 1 x 99 = 99
  imul 1 x 77 = 77
mca of q on skl (skylake)
  0  lea  3x       3  1    1 p1
  1  add  3x + 7   1  0.25 1 p0156
```

**Why it matters:** it is a bug / expected.** The same name `skl` now means two different
things: the scalar cost model is overridden, while `mca` keeps using the
built-in µarch table. If this is intentional, it should be documented or
warned about; as it stands a user who "customises" a model gets silently
inconsistent numbers between `cost` and `mca`.

### DETERMINISM-1 — MCP server process died under a flood of parallel `mca` calls (environment caveat)
**Severity:** DETERMINISM
_Original classification: `DETERMINISM / LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Repro (Code Mode)

Dispatch ~116 simultaneous calls of
`tools.ucas.x86({op:"mca", args:{f:"a(x: u32) = x+1", model:"skl"}})`.

**Observed:**

```
Error: MCP tool "x86" on server "ucas" failed: Connection closed: MCP server process exited
```

for every call; the `ucas` tool namespace disappeared until the harness
restarted it. One of four runs of
`ucas --mcp < repro_x86check_mcp.jsonl` also timed out (rc=124) with only
2 of 4 replies emitted, while the other three runs finished with rc=0 and
byte-identical output.

**Caveat.** The machine was simultaneously running several other stress
subagents (aarch64 cross-compiles, builds, other ucas searches), and an
unrelated shell was OOM-killed (rc 137) during the same window; memory
pressure is the likely cause. Sequentially, 150 MCP `mca` calls in
`mcp_x86_stress.jsonl` complete in well under 30 s and are byte-identical
across repeated runs. Documented for reproducibility, not claimed as a
standalone code defect.

## Checks that passed

### Coverage notes (no bug found)
* All 9 µarchs (`skl skx glc rpl zen2 zen4 x86v2 x86v3 x86v4`) and all 3
  aliases tried (`skylake`, `znver4`, `goldencove`) produce `model` data.
* The intrinsics catalogue counts 2585 intrinsics; feature filters and class
  filters (`vpaddd`, `vpternlogd`) and the "similar names" suggestion for
  bogus intrinsics behave sensibly.
* 120 `mca` results (30 functions x 4 models) were checked for the invariant
  `simulated cycles >= max(recurrence/critical-path, ports, front-end)`;
  loop blocks report `cycles_per_iteration`/`total_cycles` instead and were
  checked separately. No inconsistent cost number was found.
* `cost F model M` and `use M; cost F` agree for every model tried.
* `x86check` with a clang shim found `0 differ` across every intrinsic
  family tested (details in finding 3).
