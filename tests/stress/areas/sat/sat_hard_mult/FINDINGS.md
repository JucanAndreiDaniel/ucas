# Stress findings — `sat_hard_mult`

_Original heading: FINDINGS — area `sat_hard_mult` (SAT/proof on hard multiplication & bit mixing)_

# FINDINGS — area `sat_hard_mult` (SAT/proof on hard multiplication & bit mixing)

All commands below use the already-built `$ROOT/ucas`. No source was
edited, no rebuild, no git. Every file in this folder was generated from its own
directory and each would-be golden was run twice and `diff`ed (all 15 goldens are
deterministic). Crashes/nondeterministic cases are **not** kept as goldens.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | `equiv` segfaults on a deeply chained product (>= 786 factors) |
| LIMIT | 4 | SAT budget boundary is sharp and highly structure-dependent |

## Findings

### CRASH-1 — `equiv` segfaults on a deeply chained product (>= 786 factors)
**Severity:** CRASH
**Expected:** _not recorded_
**Reproducer:**
Reproducer (CLI):
```sh
python3 -c "open('/tmp/deep.ucas','w').write('a(x: u32) = '+'*'.join(['x']*800)+'\nequiv a a\n')"
timeout 30 $ROOT/ucas /tmp/deep.ucas ; echo "rc=$?"
```
**Observed:** (rc=139, SIGSEGV; deterministic across repeated runs):
```
> a(x: u32) = x*x*x*x*... (800 factors) ...
> equiv a a
timeout: the monitored command dumped core
```
(the last line is printed by `timeout`, not by ucas; the ucas partial output ends at
`> equiv a a`). The definition alone with 2000 factors is fine (`rc=0`), `cost a` is
fine, and `x^800` (power form) is fine — the crash is in AIG construction for `equiv`.

**Boundary (u32, `x*x*...`, `equiv a a`):** n <= 785 → `rc=0`; n = 786, 787, ... →
`rc=139`. Two different 800-factor functions (`equiv a b`) crash too. A 900-term
`+`-chain also segfaults, so this is a general large-AIG bug; an u8 800-factor product
does not crash (small domain takes the exhaustive path).

**Reproducer:**
Reproducer (MCP wire — also crashes the server):
```sh
python3 - <<'PY'
import json
src='*'.join(['x']*800)
lines=[
 {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}},
 {"jsonrpc":"2.0","method":"notifications/initialized"},
 {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":"a(x: u32) = "+src}}},
 {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"equiv","args":{"f":"a","g":"a"}}}}]
open('/tmp/deep.jsonl','w').write("\n".join(json.dumps(l) for l in lines)+"\n")
PY
timeout 30 $ROOT/ucas --mcp < /tmp/deep.jsonl > /tmp/deep.out 2>&1 ; echo "rc=$?"
```
**Observed:** `rc=139`; only the `initialize` and definition responses are emitted, then
the process dies on the `equiv` call.

**Why it matters:** `equiv` should return a proof/give-up (or a clean resource error),
never SIGSEGV. Keep-away: do not put this in a golden (crash). Not kept as a golden.

### LIMIT-1 — SAT budget boundary is sharp and highly structure-dependent
**Severity:** LIMIT
_Original classification: `LIMIT (documented behaviour, mapped precisely`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** `06_boundary_u11_u12.ucas` (also `03_swap_giveup`, `04_xor_giveup`,
`05_lowbit_sat`).
```sh
cd $ROOT/tests/stress/areas/sat/sat_hard_mult
timeout 30 $ROOT/ucas 06_boundary_u11_u12.ucas
```
**Observed:** `(x*y) xor 5` vs `(y*x) xor 5` is `(exhaustive)` through `u11`, but from
`u12` onward it is `sampled, not proved; SAT gave up on <N> AIG nodes within its budget
of 100000 conflicts or 100000000 steps`. AIG-node counts grow monotonically and
deterministically: u12=1216, u13=1441, ..., u16=2230, u24=5170, u32=9326 (xor) /
35081 (`^5`, power), u64=38110 (xor) / 148857 (power).

Low-bit masks are *proved* while wider masks give up: `(x*y)&1` and `(x*y)&3` vs swap
are `proved by SAT` at u16/u32/u64 (0 conflicts: 2175 / 9207 / 37863 nodes), but
`(x*y)&255`, `&0xffff`, `&0xffff0000` etc. all give up at u16/u32/u64. Signedness does
not change the boundary. Plain `x*y` vs `y*x` is always `proved by algebra` (any width),
so the give-up is specifically about the bit-mixing layer, not multiplication itself.

**Why it matters:** this is the exact "proves vs sampled" boundary;
it is deterministic (AIG counts, not wall time), so it is safe as a golden.

### LIMIT-2 — `^` is power, `differ` is not an op, raw-string `equiv` fails
**Severity:** LIMIT
_Original classification: `LIMIT (footguns / silent reinterpretation`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**3a. `^` means exponentiation, not xor.** With `(x*y) ^ 5` ucas prints
`note: '^' is power; use 'xor' or '⊕' for exclusive or` and proves/gives-up about
`x^5*y^5` vs `y^5*x^5`, **not** about bit-mixing. Writing `x*y ^ 5` without parens
binds as `x*(y^5)`. A user asking for "(x*y) xor C" equivalence can therefore be
answered about a different function. Compare `03_swap_giveup.ucas` (power, includes a
Schwartz–Zippel note) with `04_xor_giveup.ucas` (xor, no polynomial note):
**Observed:**
**Reproducer:**
```sh
timeout 30 $ROOT/ucas 03_swap_giveup.ucas
timeout 30 $ROOT/ucas 04_xor_giveup.ucas
```

**3b. `differ` is not a command in this build.** CLI `differ a b` is parsed as an
undefined identifier (multiplication / function application), silently creating junk
definitions such as `_(differ: real, x: real) = differ*real(...)`, instead of an error:
```sh
printf 'a(x: u8) = x*x\ndiffer a b\n' | timeout 15 $ROOT/ucas
```
`analyze` with `op:"differ"` is rejected by the MCP schema (not one of its ops).
Equivalence/difference must be asked through `equiv`.

**3c. MCP `analyze equiv` on raw strings fails.** The example
`{"op":"equiv","args":{"f":"(x*y)^5","g":"(y*x)^5"}}` produces
`error (parse_error): expected an expression` (`equiv (x*y)^5 (y*x)^5`) because the
two bare expressions cannot be delimited. Named functions defined via `tools.ucas.ucas`
work — see `mcp_equiv_fields.jsonl` / `mcp_flat.jsonl`.

### LIMIT-3 — `equiv` silently crosses signedness and compares only "domain of a"
**Severity:** LIMIT
_Original classification: `LIMIT (semantics easy to misread; no wrong value observed`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** `10_domains.ucas`, `mcp_domains.jsonl`
```sh
timeout 30 $ROOT/ucas 10_domains.ucas
```
**Observed:**
- `a(x: u32)=x*x` vs `b(x: i32)=x*x` → `equal ... (proved by algebra ... mod 2^32)` —
  the tool accepts an `equiv` between different parameter types and reports equality
  of bit patterns.
- `a(x,y)=x*y where x<y` vs `b=x*y+1` → `differ at 32640 points` but the domain note
  says `(65025 points enumerated)` — that number is the bounding box (255x255), not
  the count of where-filtered points (32640). Misleading but not incorrect.
- Restricted-domain results are explicitly "on the domain of a": `c=0 where x==0` vs
  `d=x*y` is `proved by SAT ... 1 conflicts` even though the functions differ for
  x!=0. Correct per its stated contract, but a caller ignoring the domain clause
  would read it as global equality.

**Why it matters:** any automated consumer of `equal:true` must also consume the
domain/exhaustive fields from the structured result.

### LIMIT-4 — give-ups are ~15 s each; long MCP batches hit client timeouts
**Severity:** LIMIT
_Original classification: `LIMIT (operational, not a wrong answer`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
A single `xor` give-up (`04_xor_giveup.ucas`) takes ~14–16 s wall clock (the fixed
100000-conflict/100000000-step budget); the `^5` power give-up takes ~4 s. Several
give-ups in one CLI file or one `--mcp` session therefore exceed short test timeouts:
a 4-call MCP batch of give-ups was killed by the surrounding harness (rc=137/SIGKILL,
~15 s/call, RSS stayed <65 MB — no ucas OOM). Keep give-up goldens to one statement
each. This is a client timeout, not a ucas hang: each call does return.

## Checks that passed

### Negative result — no unsoundness found (checked, not assumed)
186 systematic expression pairs (commutation under xor/mask/shift, multi-operand
permutations/associations, `(x*x) xor (y*y)`, mod-2^k low-byte identities, i32/i64/u32/u64,
magic constants, Horner/multiply-add, polynomial-vs-bit forms, and a u8..u24 width sweep)
plus ~80 targeted/adversarial probes. Every "equal" claim was cross-checked with an
independent Python two's-complement oracle (exhaustive for <=12-bit domains, 6000
random+edge samples otherwise): **0** cases where `equal:true` disagreed with the
oracle. Structured `equiv` results were inspected via `--mcp`: `mismatch_points` was
0 for equal claims and equal to the sample size for sampled differences; `conflicts`
was only ever 0 or 1 (restricted-domain proofs), never negative, never above the
100000 budget; no `steps` field anomaly; give-up structured `sat` contains only
`result:"gave_up"` + `aig_nodes` (budget/steps appear only in the prose). Malformed MCP
args (`consecutive:-3`, `nanbits:-1`, `ftz:"yes"`) are rejected cleanly; `timeout_s:-5`
is accepted but ignored.
