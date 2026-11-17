# Stress findings — `sat_ranges_where`

_Original heading: FINDINGS — area `sat_ranges_where`_

# FINDINGS — area `sat_ranges_where`

All commands below use the already-built binary `$ROOT/ucas`.
Golden tests in this folder are deterministic (each was generated twice and `diff`ed).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `equiv` ignores the second function's `where` clause (unsound "equal") |
| LIMIT | 4 | MCP `analyze` has no `differ` op |

## Findings

### WRONG-1 — `equiv` ignores the second function's `where` clause (unsound "equal")
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (copy-pasteable):

```sh
cd $ROOT/tests/stress/areas/sat/sat_ranges_where
$ROOT/ucas 07_equiv_domain_bug.ucas
```

Minimal (create `/tmp/eqw.ucas`):

```
fw(x: u8) = x where x < 10
gw(x: u8) = x where x < 5
equiv fw ~ gw
domain gw
```

**Observed:** output:

```
> fw(x: u8) = x where x < 10
> gw(x: u8) = x where x < 5
> equiv fw ~ gw
fw and gw are equal on the domain of fw (exhaustive)
  domain: x in 0..9 by the where clause (10 points enumerated)
> domain gw
domain of gw:
  x: u8, 0..255
  where x < 5
  no conditions: total on its parameter types
  defined at 5 of 5 points
  over all 5 points of the domain
```

**Why it matters:** `README.md` states that for `equiv F G`, "G must be defined and equal
wherever F is defined". `gw`'s own domain is `0..4` (`domain gw` says "defined at 5 of 5
points"), so `gw` is undefined at `x = 5..9`, which is inside `fw`'s domain `0..9`.
`equiv` should report a mismatch such as `x=5: 5 vs undefined`. Instead it evaluates
`gw`'s *body* at all of `fw`'s domain points and silently discards `gw`'s `where` clause,
claiming equality. This is an unsound "equal on the domain" answer.

**Corroborating probes:**

- Narrower *declared range* on G has the same defect:

  ```
  f(x: u8 in 0..15) = x
  g(y: u8 in 0..7) = y
  equiv f ~ g
  ```
  Output: `f and g are equal on the domain of f (exhaustive)` — but `g` is undefined
  at `x = 8..15`, so this should differ.

- When G's body is changed so it differs outside G's `where`, `equiv` does find those
  points (`f(x)=x where x<10`, `g(x)=x+1 where x<5` → "differ at 10 points, e.g. x=0:
  0 vs 1"). This proves the where clause alone is ignored for G, not that G is checked
  on the intersection of domains.

- The bug is inconsistent with other kinds of undefinedness on G, which *are* detected:
  a partial match (`match x { 0=>0, 1=>1 }`), an out-of-range table index and a division
  by zero on G all produce "… vs undefined" counterexamples. Only `where`-clause /
  declared-range restrictions on G are dropped.

- The SAT path has the same defect (large domain):
  `equiv fa ~ ga` with `fa(x: u32 in 0..10000000) = x where x < 1000000` and
  `ga(x: u32 in 0..10000000) = x where x < 500000` reports "equal on the domain of fa
  (exhaustive)".

`07_equiv_domain_bug.ucas` + its `.out` capture the current (buggy) answers as a
regression test; they should change when the bug is fixed.

### WRONG-2 — out-of-domain restriction silently widened by `equiv`
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/sat_ranges_where
printf 'a(x: u8 in 0..255) = x\nb(x: u8 in 0..255) = x where x in {0,1,2,3}\nequiv a ~ b\n' > /tmp/eqset.ucas
$ROOT/ucas /tmp/eqset.ucas
```

**Observed:**

```
a and b are equal on the domain of a (exhaustive)
```

**Expected:** `b` is defined only at `x in {0,1,2,3}`, so `equiv` should report
differences at `x = 4..255` (`b` undefined). Listed via `x in {…}` is treated exactly
like a range `where` clause: ignored for G's definedness.

### LIMIT-1 — MCP `analyze` has no `differ` op
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/sat_ranges_where
$ROOT/ucas --mcp < mcp_sat_ranges_where.jsonl | tail -1
```

**Observed:** (last JSON-RPC line):

```json
{"jsonrpc": "2.0", "id": 12, "error": {"code": -32602, "message": "analyze needs \"op\", one of: show table parse range domain wrap crit equiv fit error cost rop gates find more approx approx_more adamfit dword foldproof banks intatomic mma stoke pit phash"}}
```

**Why it matters:** the task asks to try MCP `analyze` with `differ`/`equiv`. `equiv`
works and returns a structured result (`equal`, `mismatch_points`, `counterexample`,
`method`), but `differ` is not a valid op on either the MCP tool or the wire; the closest
ops are `equiv` (boolean + counterexample) and `error` (numeric approximation error).
No crash — just an interface limitation worth recording.

### LIMIT-2 — `gates` counts input bits from the parameter *type*, not the narrowed range
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'days(m: u8 in 1..12) = match m { 2 => 28, 4 | 6 | 9 | 11 => 30, _ => 31 }\ngates days\n' > /tmp/g8.ucas
$ROOT/ucas /tmp/g8.ucas
```

**Observed:**

```
scratch/p14.ucas:3:11: error: gates handles up to 6 input bits (8 here); exact synthesis beyond that needs SAT, not implemented yet
```

(Exact prefix path depends on where the file lives.)

**Why it matters:** the function's domain has only 12 points and could be encoded in
4 bits, but `gates` refuses because the declared type is `u8`. A `u4` table of the same
size (`gates tbl` in `mcp_sat_ranges_where.jsonl`) works. No wrong answer or crash.

### LIMIT-3 — lookup tables are capped at 1024 entries ("table too long")
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
python3 -c 'print("b(x: u16 in 0..1024) = [" + ",".join("0" for _ in range(1025)) + "][x]")' > /tmp/big.ucas
$ROOT/ucas /tmp/big.ucas
```

**Observed:**

```
/tmp/big.ucas:1:...: error: table too long
```

Boundary found by bisection: 1024 entries parse fine, 1025 → `table too long`. Tables
of 16, 64 and 256 entries (the focus of this sweep) all work correctly, including exhaustive
`range`/`equiv` and table-index definedness.

### LIMIT-4 — headline `range` on a sampled domain is only the sampled max
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf 'g(x: u32 in 0..4194304) = x*x\nrange g\n' > /tmp/cap.ucas
$ROOT/ucas /tmp/cap.ucas
```

**Observed:**

```
range of g -> u32:
  0..4294868313
  fits in u32
  sampled 65536 points (domain has 4194305 points); not exhaustive
  sound bound (intervals): 0..4294967295
```

Brute force over all 4194305 points gives a true maximum of `4294966857` (at
`x = 926819`). The first line `0..4294868313` is therefore *not* a bound on the
reachable values; only the separate `sound bound (intervals)` line is sound. The output
does say "sampled … not exhaustive", so this is a presentation limitation rather than
an unsound claim, but a reader taking the headline range at face value would miss a
reachable value. At exactly `2^22` points (`0..4194303`) `range` is exhaustive and exact
(`0..4294966857`).

## Checks that passed

### Things checked but NOT found
- No crashes, hangs, signals or truncated output on any candidate (all ran with
  `timeout 15`, goldens with `timeout 30`; exit code 0 everywhere).
- No nondeterministic witnesses: every would-be golden was generated twice and
  `diff`ed identically, including SAT counterexamples (`x=1234567`, `x=7777777`),
  SAT conflict/node counts, `find days`, and MCP JSON-RPC output.
- No out-of-domain counterexamples from SAT: a difference placed strictly outside
  F's `where`-narrowed domain is correctly ignored (`equiv` proves equal, e.g.
  `p(x)=x where x<10000000` vs `q(x)=x+(x==15000000?1:0)` on `0..20000000`).
- `match` duplicate arms are first-match-wins; overlapping arms and explicit
  select-chain equivalents agree; negative arms on `i8` and type-boundary ranges
  behave correctly.
- Where-clause narrowing (conjunctions, disjunctions via hull, explicit value sets,
  local bindings, wrapping arithmetic inside the where clause, empty domains) produced
  correct `domain`/`range`/`equiv` results throughout.
