# Stress findings — `boolean_sat_u1`

_Original heading: FINDINGS — `boolean_sat_u1`_

# FINDINGS — `boolean_sat_u1`

Area: pure Boolean / `u1` reasoning (truth tables of every 1/2/3-input Boolean function,
De Morgan / absorption / distributivity, XOR / majority / minterms, symbolic `c ? a : b`,
chained comparisons, `!`/`not`/`&&`/`||`, Boolean→integer coercion, `gates`/`equiv` on 1-bit
functions).  CLI + MCP (`--mcp` and `--mcp --flat`), all with the prebuilt
`$ROOT/ucas` under `timeout 15` (30 s for MCP).

**Oracle:** an independent Python truth-table oracle evaluated every expression over ALL
2^n inputs (n ≤ 24).  All 380 oracle-verified golden cases (348 in `NN_cases.*`, 32 in
`b2_NN.*`) and all 28 MCP analyze calls passed with **zero** wrong verdicts; all goldens were
run twice and were byte-identical.  The issues below are the exceptions found by adversarial
probes outside that verified set.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | stack overflow on deeply nested Boolean expressions |
| WRONG | 1 | `gates ... basis nand` claims NOT / AND are unimplementable |
| LIMIT | 1 | leading `!` / `~` rejected by the `parse` command |

## Findings

### WRONG-1 — `gates ... basis nand` claims NOT / AND are unimplementable
**Severity:** WRONG
_Original classification: `WRONG (medium`._
**Why it matters:** _not recorded_
NAND is a functionally complete basis, and ucas's own `equiv` confirms two explicit
NAND-only networks: `!a == ~(a & a)` (one NAND) and `a & b == ~(~(a & b) & ~(a & b))`
(two NANDs).  Yet `gates notb basis nand` and `gates andb basis nand` both answer
`no program found for output 0 (basis not complete, or more than 244 steps)`.  The built-in
`nand` basis *does* work for OR / XOR / NAND / minority, so the failure is specific to
functions that need a gate's two inputs tied to the same wire (NOT and AND).

Root cause (source inspection, no edits): `src/gates.c:dfs()` rejects a 2-input gate whose
operands are equal (`if (b == a ...) continue;`), and `lut_steps()` starts its second index
at `a+1`.  A NAND with both inputs on one wire — the only way to get NOT from NAND — is
therefore never generated, and the Shannon fallback inherits the restriction.  The message
"basis not complete" is false for NAND.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/boolean_sat_u1
timeout 20 $ROOT/ucas wrong_gates_nand.ucas
```

**Observed:** (excerpt; full output is `wrong_gates_nand.out`):
```
> equiv notb ~ notnand
notb and notnand are equal on the domain of notb (exhaustive)
> equiv andb ~ andnand
andb and andnand are equal on the domain of andb (exhaustive)
> gates notb basis nand
gates for notb: 1 input bit -> 1 output bit, basis nand
  exact search stopped (cost limit at cost 12); Shannon decomposition instead:
  no program found for output 0 (basis not complete, or more than 244 steps)
> gates andb basis nand
gates for andb: 2 input bits -> 1 output bit, basis nand
  exact search stopped (cost limit at cost 12); Shannon decomposition instead:
  no program found for output 0 (basis not complete, or more than 244 steps)
> gates orb basis nand
  minimal: cost 4, 4 steps ...     # control: works
```

**Expected:** find `nand(a, a)` for NOT (cost 1) and the 2-NAND network for AND, or at worst
say the search cannot tie inputs — never assert the basis is incomplete.  Deterministic
(run twice, identical); golden `.out` intentionally captures the buggy answer.

**Confirmed over MCP too** (`tools.ucas.analyze`): `gates {body:"!a",params:[bool a]} basis nand`
and the AND analogue return `text: "…no program found for output 0 (basis not complete…)"`,
while `analyze equiv` on `!a` vs `~(a&a)` and on `a&b` vs `~(~(a&b)&~(a&b))` both return
`{"equal": true, "exhaustive": true, "mismatch_points": 0}`.  (`gates basis nand` on OR
returns a normal minimal cost-4 network — control.)

### CRASH-1 — stack overflow on deeply nested Boolean expressions
**Severity:** CRASH
_Original classification: `CRASH (medium, cross-reference`._
**Why it matters:** _not recorded_
Valid Boolean expressions with ~1600–2000 nested unary operators / parentheses / binary
groups segfault (SIGSEGV, rc 139) instead of returning a clean "too deeply nested" parse
error.  On this host `!`×1500 is fine, `!`×2000 crashes; nested parens crash at 3000;
right-nested `xor` at 3000; a 2000-deep `c ? a : …` chain at 2000.  The def line is echoed
and then the process dies.  This is the same unbounded `prefix`/`parse_expr` recursion
already reported in `resource_limits`, `syntax_weird`, `sanitizer_builds` and
`MASTER_FINDINGS.md`; recorded here because it is reached purely through Boolean syntax.

**Reproducer:**
Reproducer (copy-pasteable; writes into /tmp, no golden kept):
**Observed:**
```sh
python3 -c 'open("/tmp/deepnot.ucas","w").write("d(x: bool) = "+"!"*2000+"x\ntable d\n")'
timeout 15 $ROOT/ucas /tmp/deepnot.ucas >/dev/null 2>&1; echo $?   # 139
```
Parenthesis variant:
```sh
python3 -c 'n=3000; open("/tmp/deeppar.ucas","w").write("p(x: bool) = "+"("*n+"x"+")"*n+"\ntable p\n")'
timeout 15 $ROOT/ucas /tmp/deeppar.ucas >/dev/null 2>&1; echo $?   # 139
```

**Expected:** a depth guard or "expression too deeply nested" diagnostic, not SIGSEGV.
No `.out` golden is kept (crash case).

### LIMIT-1 — leading `!` / `~` rejected by the `parse` command
**Severity:** LIMIT
_Original classification: `LIMIT (low, cross-reference`._
**Why it matters:** _not recorded_
`parse !x`, `parse !(x & y)`, `parse ~x`, `parse !x && y` fail with
`error: unexpected '!' after the statement` (or `'~'`), even though the identical prefix
operators are accepted in function bodies (`d(x:bool)=!x` works), and `parse not x`,
`parse (!x)` and `parse x && !y` work.  Only a leading unary `!`/`~` token in an anonymous
expression is affected; same defect already documented in `syntax_weird/FINDINGS.md`.

**Reproducer:**
```sh
printf 'parse !x\nparse ~x\nparse not x\n' | timeout 15 $ROOT/ucas
```
**Observed:**
```
<stdin>:1:7: error: unexpected '!' after the statement
    parse !x
          ^
<stdin>:2:7: error: unexpected '~' after the statement
    parse ~x
          ^
(!(x != 0))
```
**Expected:** accept `!x` / `~x` as an expression, as everywhere else.

## Checks that passed

### 4. Cross-reference — `equiv` ignores G's declared `where` / range domain
Observed again in this area (`ft(x:bool)=x`, `gp(x:bool)=x where x==0`,
`equiv ft ~ gp` → "equal on the domain of ft", although `gp` is undefined at x=1).  This is
the already-documented unsound verdict in `sat_ranges_where/07_equiv_domain_bug.out` and is
listed only so the orchestrator can de-duplicate; not counted as a new finding here.

### Negative controls (checked, no bug)
* All 256 three-input, 16 two-input and 2 one-input Boolean truth tables match the Python
  oracle exactly (row order: first parameter varies fastest).
* De Morgan, absorption, distributivity, idempotence, complement, double-negation, XOR
  (associative/commutative/distributive), consensus, majority, XNOR, implication and nested
  MUX identities: all verdicts match the oracle, CLI and MCP.
* Cross-type `bool` vs `u1` `equiv`, Boolean→`u1`/`u8`/`int` coercion, `u1` add = XOR,
  `u1` multiply/negate wrap, logical ops on `u1`, and partial-function domains: correct.
* `u1` shifts by the full width (`x<<1`, `x>>1` on `u1`) correctly print `-> undefined`,
  not a value (oracle corrected accordingly).
* Out-of-range literals in a `bool`/`u1` context are narrowed with a note (`10`→`0`,
  `9`→`1`): internally consistent, not a bug (it initially looked like a verdict mismatch
  and was traced to this documented coercion).
* SAT-path `equiv` over u32/u16 Boolean identities (`~(x&y)==~x|~y`, `x&(x|y)==x`, etc.)
  gives correct equal/differ verdicts with stable AIG/conflict counts across 5 runs.
* 24-variable exhaustive `equiv` finishes within 15 s; no hang found.
* No nondeterminism anywhere: every CLI golden and both MCP goldens were run ≥2× and diffed
  byte-for-byte, including SAT proofs and gate networks.
