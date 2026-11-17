# Stress findings — `sat_wide_bitops`

_Original heading: FINDINGS — `sat_wide_bitops`_

# FINDINGS — `sat_wide_bitops`

Scope: wide-machine-integer bit operations that stress SAT bit-blasting
(u16/u32/u64 shifts by variable amounts, rotates, masks, sign extension,
popcount/clz/ctz, de Bruijn-style tricks, div/mod, isqrt, bit-table lookups,
`(x & mask)==0`, comparison chains).  All commands below use the absolute
binary `$ROOT/ucas`.  Reproducers use `ucas -e $'...'` so they
are self-contained (no scratch files).  All findings below were checked twice
and are deterministic; no CRASH / HANG / DETERMINISM cases were found.

Bugs/limits reproducers are intentionally **not** kept as golden `.out` files —
they would bake wrong or give-up behaviour into the catalogue.  They live only
here.  Every kept golden `.out` was run twice and `diff`-clean.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `wrap` end-to-end result is false for u64 values with bit 63 set |
| NLP | 1 | short inline function names hit the juxtaposition ambiguity |
| LIMIT | 3 | SAT gives up (gracefully) on 64-bit SWAR popcount equivalence |

## Findings

### WRONG-1 — `wrap` end-to-end result is false for u64 values with bit 63 set
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (identity function — can never differ from the mathematical result):

```sh
timeout 15 $ROOT/ucas -e $'id(x: u64) = x\nwrap id'
```

**Observed:**

```
wrap analysis of id:
  no wrapping or rounding operations
  end to end: differs from the mathematical result at 32755 points, e.g. x=18446744073709551615
  sampled 65536 points (domain has 2^64 or more points); not exhaustive
```

**Expected:** `end to end: equals the mathematical (unbounded) result everywhere`
— a bare identity has no operations and must agree on all inputs.  About half
of the sampled points (~32755/65536) are flagged, exactly those with the u64
sign bit set, so the end-to-end checker is comparing the u64 output as a
**signed** value against the unbounded mathematical integer.  Controls:
`i64`, `i32`, `u32` identity all report "equals everywhere", and
`a(x:u64)=x & 0xffff` (result always < 2^63) also reports "equals everywhere".

Same defect on other u64 functions (all give bogus "differs" verdicts):

```sh
timeout 15 $ROOT/ucas -e $'g(x: u64, n: u64) = x >> n\ndomain g\nwrap g'
```

```
domain of g:
  x: u64, 0..9223372036854775807
  n: u64, 0..9223372036854775807
  ...
  sampled 65536 points (domain has 2^64 or more points); not exhaustive
wrap analysis of g:
  no wrapping or rounding operations
  end to end: differs from the mathematical result at 1 points, e.g. x=18446744073709551615, n=0
  sampled 65536 points (domain has 2^64 or more points); not exhaustive
```

Here `x >> 0` **is** `x`, yet it is reported as differing from the mathematical
result at `x=2^64-1, n=0`.  Note also the internal contradiction: `domain`
prints the u64 range clipped to `0..2^63-1`, while the `wrap` witness uses
`x=2^64-1` which lies outside that printed domain.  Same wrong verdict for
`x | 1`, `x ^ 1`, `~x`, `u64(i64(x))`, and `x << n` on u64.  Related:
`wrap` of `x - 1` on u64 reports nuw failure "at 2 points, e.g. x=0" although
unsigned underflow occurs at exactly one point (`x=0`).

### WRONG-2 — inline function *definitions* passed to analysis commands silently misparse into a bogus answer
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas -e 'cost foo(x: u32) = x + 1'
```

**Observed:** (no error — only "notes", then a garbage cost):

```
  note: foo(...) read as multiplication: foo is not a function
  note: '=' inside an expression read as '=='
cost of foo*real(x) == real(x + 1) under gt1030: 10.375 (5 operations, shared subterms counted once)
  iadd             1 x 1     = 1
  cmp              1 x 2.375 = 2.375
  conv             2 x 3     = 6
  fmul             1 x 1     = 1
```

**Expected:** either accept the definition (as `range isqrt(x: u4)` accepts an
inline typed expression) or reject it.  Instead `foo(x: u32) = x + 1` is
reinterpreted as the arithmetic expression `foo * (x) == (x + 1)`, a brand-new
free variable `foo : real` is invented with a default range, and a confident
but meaningless cost/range/wrap is returned.  The same silent misparse happens
for `range bar(x: u8) = x + 1` (returns `range of bar*real(x) == real(x + 1)
-> bool: 0..1`), `wrap baz(x: u8) = x << 1` (invented `baz : real`, witness
`baz=-2474078709182176629`), and `domain qux(x: u8) = x / 2`.  `equiv` is the
exception — it hard-errors (`expected ')', found ':'`).  This is an
unsound-input-acceptance bug: malformed input yields a bogus answer rather
than a parse error.

### LIMIT-1 — SAT gives up (gracefully) on 64-bit SWAR popcount equivalence
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 28 $ROOT/ucas -e $'pc(x: u64) = popcount(x)\nr(x: u64) = x - ((x >> 1) & 0x5555555555555555)\ns(x: u64) = (r(x) & 0x3333333333333333) + ((r(x) >> 2) & 0x3333333333333333)\nt(x: u64) = (s(x) + (s(x) >> 4)) & 0x0f0f0f0f0f0f0f0f\nq(x: u64) = (t(x) * 0x0101010101010101) >> 56\nswar(x: u64) = q(x)\nequiv pc swar'
```

**Observed:** (exit 0, deterministic, no crash/hang):

```
pc and swar are equal on the domain of pc (sampled, not proved; SAT gave up on 12084 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```

The two functions are in fact equal, and the 32-bit version of the same proof
succeeds (`proved by SAT: 2964 AIG nodes, 21469 conflicts`), but the 64-bit
bit-blast exceeds the budget and the answer degrades to "sampled, not proved".
Recorded as a LIMIT, not a golden.  A correctness caveat: the fallback claim
"are equal" is only sample-backed, so this is exactly the situation where a
wrong `equiv:true` could slip through if a crafted pair differed only on a
rare input.

### LIMIT-2 — MCP `analyze equiv` rejects the documented plain-expression form
**Severity:** LIMIT
_Original classification: `LIMIT / NLP`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The documented example call fails.  Reproducer:

**Reproducer:**
```sh
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"equiv","args":{"f":"(x*y)^5","g":"(y*x)^5"}}}}' \
 | timeout 15 $ROOT/ucas --mcp
```

**Observed:** (`isError:true`):

```
error (parse_error): expected an expression

<json>:1:22: error: expected an expression
    equiv (x*y)^5 (y*x)^5
                         ^
```

`equiv`'s `f`/`g` are typed *functions*, not bare expressions.  They must be
supplied as objects, e.g.
`{"f":{"body":"(x*y)^5","params":[{"name":"x","type":"u32"},{"name":"y","type":"u32"}]}, ...}`,
or as names defined in an earlier `session/define` call.  With the object form
the same pair is proved by algebra (see `mcp_wide_bitops.jsonl`, calls 22–25).
The MCP documentation example is misleading; no crash, just a parse rejection.

### LIMIT-3 — `wrap` on an always-undefined constant shift prints an empty witness
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas -e $'s1(x: u32) = x << 32\nwrap s1\ndomain s1'
```

**Observed:** (partial):

```
wrap analysis of s1:
  x << 32   (u32)
      nuw holds on the sample (intervals cannot prove it)
      nsw holds
  end to end: differs from the mathematical result at 0 points, e.g. 
  sampled 65536 points (domain has 4294967296 points); not exhaustive
```

`domain s1` correctly says `defined at 0 of 65536 points` / C UB at all points,
but `wrap` reports "differs ... at 0 points, e.g. " with a dangling empty
example and claims nuw/nsw "hold" on a set with no defined points.  Cosmetic /
empty-domain formatting issue rather than unsoundness; recorded as a LIMIT.

### NLP-1 — short inline function names hit the juxtaposition ambiguity
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
timeout 15 $ROOT/ucas -e 'show sh(x: u32) = x << 1'
```

**Observed:** on the CLI (it silently takes the default "product" reading — no error):

```
  note: 'sh' read as s*h (single-letter variables)
  note: '=' inside an expression read as '=='
_(s: int, h: int, x: u32) = s*h*int(x) == int(x << 1)
  -> bool
```

Through the MCP tool (`tools.ucas.analyze`) the *same* input instead hard-errors
with `error (ambiguous): 'sh' read as s*h ... ambiguous: set
args.assume.juxtaposition ...`.  So the CLI silently misparses the definition
into `s*h*x == (x<<1)` with invented free variables, while MCP rejects it —
an inconsistently handled ambiguity.  Not a SAT correctness bug, but a frontend
gotcha for machine-generated names; use >=3-character names or set
`args.assume.juxtaposition`.

## Checks that passed

### Non-findings / verified-good
- No crash, hang, signal, truncated JSON, or nonzero exit in any of the 175+
  distinct expressions/queries tried — including shift-by >= width (u8/u16/
  u32/u64), shift by full-width constants (`x << 32`, `x << 64`), out-of-bounds
  bit-table indices, division by zero, `clz(0)`/`ctz(0)`, and 64-bit SAT proofs.
- Every kept golden `.out` (12 CLI + 2 MCP JSONL) is byte-identical across two
  runs; no random witnesses or timing-dependent numbers were observed.
- `equiv` verdicts that were checked manually against the stated witnesses
  (rotates, xor-fold, `(x+y)*(x-y)=x^2-y^2`, popcount-vs-bit-SUM on u16,
  bit-reversal on u4) all agreed.  The one "gave up" result is item 3 above.
