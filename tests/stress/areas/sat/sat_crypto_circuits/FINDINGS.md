# Stress findings — `sat_crypto_circuits`

_Original heading: FINDINGS — `sat_crypto_circuits`_

# FINDINGS — `sat_crypto_circuits`

All commands below use the absolute binary `$ROOT/ucas`.
Golden files live in this directory; every golden was run twice and `diff`ed
identically (see `SUMMARY.md`). Exploratory cases that crash, error, or would be
nondeterministic are **not** kept as goldens unless noted.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | `range` headline excludes a trivially reachable value |
| LIMIT | 8 | SAT budget give-up on a true masked-multiplier identity |

## Findings

### WRONG-1 — `range` headline excludes a trivially reachable value
**Severity:** WRONG
_Original classification: `WRONG (reported max is too small; a sound bound is printed separately`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (self-contained golden `09_gf2n_mul.ucas`):

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 09_gf2n_mul.ucas > /tmp/g.out 2>&1
grep -A6 'range of gm16' /tmp/g.out
grep -A4 'range of mx' /tmp/g.out
```

`09_gf2n_mul.ucas` defines `gm16` as carry-less multiply in GF(2^16) with the
reduction polynomial `0x2d`, and adds `mx(x: u16) = gm16(1, x)`.

**Observed:** output (exact):

```
range of gm16 -> u16:
  0..65534   (41254 distinct values)
  fits in u16
  sampled 65536 points (domain has 4294967296 points); not exhaustive
  sound bound (intervals): 0..65535
```

```
range of mx -> u16:
  0..65535   (65536 distinct values)
  fits in u16
  over all 65536 points of the domain
```

**Why it matters:** the headline range of `gm16` says `0..65534`, but `65535`
is reachable — `gm16(1, 65535) = 65535`, proved exhaustively by `range mx` in
the very same file. The trailing "sound bound ... 0..65535" line does not
change the printed range, so a caller reading the `range` field gets a max that
excludes a reachable value. An independent Python bit-level model of the same
circuit also hit `0xffff` in 200k random pairs.

### WRONG-2 — `domain` calls an everywhere-undefined shift "total"
**Severity:** WRONG
_Original classification: `WRONG (self-contradictory domain report`._
**Expected:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas -e 'sh(x: u32) = x << 32' -e 'domain sh'
```

**Observed:** output (exact):

```
domain of sh:
  x: u32, 0..4294967295
  no conditions: total on its parameter types
  defined at 0 of 65536 points
  undefined e.g. at x=0; x=4294967295; x=1; x=4294967294
  C undefined behaviour at 65536 points, e.g. x=0
  sampled 65536 points (domain has 4294967296 points); not exhaustive
```

Same for `x >> 32` and `x >> 64`; `x << 31` correctly reports "total" with
"defined at 65536 of 65536 points". This is also captured via MCP in
`mcp_sat_crypto.out`, call id 8.

**Why it matters:** "no conditions: total on its parameter types" contradicts
"defined at 0 of 65536 points" and "C undefined behaviour at 65536 points".
A constant shift by the width is undefined by the tool's own README, so the
symbolic domain pass should report a condition rather than "total".

### WRONG-3 — WRONG / UNSOUND-LOOKING — vacuous `equiv` proof of an arbitrary equality
**Severity:** WRONG
_Original classification: `WRONG (misleading "proved by SAT" on an empty domain`._
**Expected:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas \
  -e 'u1(x: u32) = x << 32' -e 'u2(x: u32) = x + 12345' -e 'equiv u1 u2'
```

**Observed:** output (exact):

```
u1 and u2 are equal on the domain of u1 (proved by SAT: 193 AIG nodes, 0 conflicts)
```

`x / 0` behaves the same ("proved by SAT: 64 AIG nodes, 0 conflicts" against an
arbitrary function). MCP form is in `mcp_sat_crypto.out`, call id 9.

**Why it matters:** `u1` is undefined at every input (finding 2), so the
equality is vacuous. Reporting "proved by SAT" with zero conflicts for two
unrelated formulas invites callers to trust a proof that establishes nothing.
At minimum the answer should say the domain is empty.

### LIMIT-1 — SAT budget give-up on a true masked-multiplier identity
**Severity:** LIMIT
_Original classification: `LIMIT (budget give-up; deterministic output`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** golden `14_budget_equiv.ucas`

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 14_budget_equiv.ucas > /tmp/g.out 2>&1
```

**Observed:** output (exact, after the two echoed definitions):

```
b1 and b2 are equal on the domain of b1 (sampled, not proved; SAT gave up on 9262 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```

**Why it matters:** `(x*y) & 0xffff == (y*x) & 0xffff` is unconditionally true,
but the multiplier circuit exceeds the solver budget. The answer is honest
("sampled, not proved") but the tool cannot prove a basic commutativity identity
once the product is masked. Taken 7.7 s; also exposed through MCP in
`mcp_sat_crypto.out`, call id 4.

### LIMIT-2 — SAT budget give-up on GF(2^16) multiplication commutativity
**Severity:** LIMIT
_Original classification: `LIMIT (budget give-up; deterministic output`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** golden `16_budget_gf16.ucas`

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 16_budget_gf16.ucas > /tmp/g.out 2>&1
```

**Observed:** output (exact):

```
gm16 and gm16r are equal on the domain of gm16 (sampled, not proved; SAT gave up on 2276 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```

**Why it matters:** `gm16(a,b) = gm16(b,a)` is a true field/ring identity, but
the xtime-chain circuit defeats SAT within budget. Note the same statement over
GF(2^8) **is** proved exhaustively (`01_gf8_mul.ucas`, 65 536 points), so the
give-up is purely a function of circuit width/bit-blast size, not of the math.

### LIMIT-3 — SAT budget give-up on GF(2^8) associativity (2^24-point domain)
**Severity:** LIMIT
_Original classification: `LIMIT (budget give-up; deterministic output`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** golden `01_gf8_mul.ucas`

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 01_gf8_mul.ucas > /tmp/g.out 2>&1
grep -A1 'equiv assoc1 assoc2' /tmp/g.out
```

**Observed:** output (exact):

```
assoc1 and assoc2 are equal on the domain of assoc1 (sampled, not proved; SAT gave up on 1173 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```

**Why it matters:** `gm(gm(a,b),c) == gm(a,gm(b,c))` is true in GF(2^8). The
domain is 2^24 points (too big to enumerate) and SAT gives up. A cheaper,
more compositional proof strategy would be needed for crypto circuits.

### LIMIT-4 — SAT budget give-up on XOR of two multipliers
**Severity:** LIMIT
_Original classification: `LIMIT (budget give-up; deterministic output`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** golden `18_budget_xor_mul.ucas`

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 18_budget_xor_mul.ucas > /tmp/g.out 2>&1
```

**Observed:** output (exact):

```
f and g are equal on the domain of f (sampled, not proved; SAT gave up on 9326 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```

**Why it matters:** `(x*y) xor (y*x) == 0` is true for all u32 inputs; the two
independent multiplier circuits blow the budget (8.3 s wall time).

### LIMIT-5 — `gates` node-budget give-up on a 6-bit S-box
**Severity:** LIMIT
_Original classification: `LIMIT (exact synthesis gives up; result is an upper bound, not minimal`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** golden `15_gates_budget.ucas`

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 15_gates_budget.ucas > /tmp/g.out 2>&1
head -5 /tmp/g.out
```

**Observed:** output (exact):

```
> sb6(x: u6) = match x { 0=>3, 1=>7, 2=>2, 3=>5, 4=>1, 5=>6, 6=>0, 7=>4, _=>x }
> gates sb6
gates for sb6: 6 input bits -> 6 output bits, basis c
  exact search stopped (node budget at cost 7); Shannon decomposition instead:
  cost 35, 35 steps (an upper bound, not proved minimal)
```

**Why it matters:** a 6-input S-box is within the documented "up to 6 input
bits" range, but exact synthesis still hits its node budget and silently
downgrades to a 35-gate upper bound. Took 9.9–11.4 s (varies slightly with
load) but the *text output* is deterministic — verified by repeated `diff`.

### LIMIT-6 — `find` term-bank full; no cheaper form for popcount parity
**Severity:** LIMIT
_Original classification: `LIMIT (search terminates at a bank limit, not a proof of optimality`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** golden `13_find_crypto.ucas`

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 13_find_crypto.ucas > /tmp/g.out 2>&1
grep -A3 'find fp' /tmp/g.out
```

**Observed:** output (exact):

```
find fp: 256 points, computing in u8, costs from gt1030
  cost 7   [0, 1, 1, 0, 1, 0, ...] lookup table (baseline)
  [searched every term up to cost 4: 65536 distinct columns, bank full; 'more' continues]
```

**Why it matters:** `find` reports only the 256-entry lookup table (cost 7) for
`popcount(x) & 1`; real cheaper forms (e.g. XOR-fold the word down to one bit)
are outside the enumerated term space, so the catalogue stops at "bank full".
The "bank full" notice is a search limit, not a negative proof.

### LIMIT-7 — `equiv f f` is "sampled, not proved" when `f` contains `^`
**Severity:** LIMIT
_Original classification: `LIMIT (reflexivity not established for power expressions`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** golden `17_power_no_sat.ucas`

```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
timeout 30 $ROOT/ucas 17_power_no_sat.ucas > /tmp/g.out 2>&1
```

**Observed:** output (exact):

```
> g64(a: u64, b: u64) = a ^ b
  note: '^' is power; use 'xor' or '⊕' for exclusive or
> equiv g64 g64
g64 and g64 are equal on the domain of g64 (sampled, not proved; no SAT proof: a power)
```

**Why it matters:** a formula compared to itself should be provably equal with
zero search. Because `^` is exponentiation (not XOR, despite the common C/Python
reading) and power is not bit-blasted, even the reflexive check degrades to a
sample. Relevant to crypto code where `^` is routinely meant as XOR.

### LIMIT-8 — `gates` > 6 input bits errors with exit code 0
**Severity:** LIMIT
_Original classification: `LIMIT (unsupported range; error signalled only on stderr with exit 0`._
**Expected:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas \
  -e 'par8(x: u8) = popcount(x) & 1' -e 'gates par8'; echo "EXIT=$?"
```

**Observed:** output (exact):

```
<arg>:1:11: error: gates handles up to 6 input bits (8 here); exact synthesis beyond that needs SAT, not implemented yet
    gates par8
              ^
EXIT=0
```

**Why it matters:** `gates` on an 8-bit parity (a classic crypto predicate)
is refused, and the process still exits 0. A test harness that trusts exit
codes would treat this as success. The error is deterministic and is therefore
**not** kept as a golden `.out`.

## Checks that passed

### Negative results (no finding)
- **No crash or hang** was observed: every one of the ~358 candidate statements
  finished within its `timeout 15` (deliberate long searches ≤ 30 s). No signal
  deaths, truncated JSON, or empty-after-timeout outputs.
- **No nondeterminism** was found: all 18 golden `.ucas` files and the MCP
  golden were each generated twice and `diff`ed byte-for-byte; SAT witnesses
  (`differ at N points ... e.g. x=...`), AIG-node/conflict counts, `find` and
  `phash` results, and `stoke`/`pit`/`find more` with fixed seeds were also
  stable over 3 repeated runs. `phash` reports "K drawn at random" but the
  default `seed 1` makes its output reproducible.
- **No unsound `equal:true` proof** was found on genuinely different functions:
  differing wide multipliers, CRC feedback variants, and SHA mixing variants
  all returned a verified counterexample when they differed. The only
  misleading "equal" cases are the vacuous empty-domain ones in finding 3.
- `params` with `where` clauses were respected by SAT (narrowed domain proved
  equal, differing functions produced witnesses inside the narrowed domain).
