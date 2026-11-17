# Stress findings — `llm_mutators_findings`

_Original heading: FINDINGS — `llm_mutators_findings`_

# FINDINGS — `llm_mutators_findings`

Neighbourhood-mutation campaign: the confirmed catalog in `MASTER_FINDINGS.md`
and the per-area `FINDINGS.md` files was distilled into 14 families of bug
*shapes*, then each shape was re-applied in a different type, command, frontend
and context by a seeded generator.

Binary: `$ROOT/ucas` (not rebuilt). Every mutation ran under
`timeout 15`. Crashes/hangs/nondeterministic cases are documented here, never
added as goldens. All goldens in this folder were generated twice and `diff`ed
byte-identically.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | deep-parenthesis/unary/abs nesting at depth 1600 (no golden) |
| WRONG | 12 | `equiv` ignores G's domain restriction: 38 new instances |
| NLP | 2 | JSON/MCP `equiv` silently drops a supplied function-object `where` field |

## Findings

### WRONG-1 — `equiv` ignores G's domain restriction: 38 new instances
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden reproducer:**

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/llm_mutators_findings
$ROOT/ucas 01_equiv_domain_u16.ucas
```

**Observed:**

```
> fu(x: u16) = x
> gu(x: u16 in 0..100) = x
> equiv fu gu
fu and gu are equal on the domain of fu (exhaustive)
```

`gu` is defined only on `0..100`, but `equiv` reports equality over `fu`'s
whole `u16` domain. This is the confirmed `sat_ranges_where/07` bug broadened
to **u16, i16, i32, value-set restrictions (`where x in {…}`), the `x ^ x`
body, and both `equiv F G` / `equiv F ~ G` spellings**. All 30 CLI variants and
all 8 object-form wire variants matched the oracle; none were refuted.

### NLP-1 — JSON/MCP `equiv` silently drops a supplied function-object `where` field
**Severity:** NLP
_Original classification: `NLP (new interface finding`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer** (one of the 8 mutations; written out here because it is a
protocol-level observation):

```sh
printf '%s\n' \
 '{"id":1,"cmd":"equiv","args":{"f":{"body":"x","params":[{"name":"x","type":"u8"}]},"g":{"body":"x","params":[{"name":"x","type":"u8"}],"where":"x < 5"}}}' \
 | $ROOT/ucas --json --files none
```

**Observed:** (key fields): `"ucas": "it(x: u8) = x\nthat(x: u8) = x\nequiv it that"`,
`"result": {"equal": true, ...}`. The `where` field is absent from the emitted
source on **all three wire frontends** (`--json`, `--mcp`, `--mcp --flat`) — the
generator simply drops it. A caller who narrows a function with `where` in the
structured API gets a silently wider (total) function back. This is the
JSON/MCP-surface counterpart of §1 and is easy to miss because the response is
`ok:true, structured:true`. (The object-form `where` key is not documented as
a supported field, so this is recorded as NLP / silent-drop, not a crash.)

### WRONG-2 — true `real` identity refuted with identical-printing counterexample: 10 new identities
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden reproducer:**

**Reproducer:**
```sh
$ROOT/ucas 02_real_identity_newexpr.ucas
```

**Observed:**

```
> a(x: real, y: real) = (x - y)^2
> b(x: real, y: real) = x^2 - 2*x*y + y^2
> equiv a ~ b
a and b differ at 548026 points, e.g. x=-9.98, y=-10: 0.0004 vs 0.0004
```

Both values print `0.0004` yet `equiv` says "differ". New instances span
`(x-y)^2`, `x²−1`, `(x+y)³`, `(a+b)(a−b)`, `sin²+cos²`, `(x+1)²`, `5x`, and
`2x−y` style identities (some previously correct on `real` are now refuted).

**Negative control (important):** the same identities over `f32`/`f64` were
*also* refuted, but with genuinely different printed values (overflow →
`inf` vs `-nan`, rounding → `−0.999999166` vs `−0.999999225`). Those are
legitimate IEEE-754 non-associativity, **not** this bug, and were excluded from
the count. Only the 10 `real` cases with byte-identical "vs" values count.

### WRONG-3 — cast coercion: 15 new instances (now including an i16 source)
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 03_cast_i16.ucas`

**Observed:**
**Reproducer:**
```sh
> a(x: i16) = u8(x)
> b(x: i16) = i32(x)
> equiv a ~ b
a and b are equal on the domain of a (exhaustive)
```

`u8(-1)=255` but `i32(-1)=-1`; these cannot be equal, yet an "exhaustive
proof" claims they are. The catalog had only `i8 → u8/i32`; this broadens the
source type to `i16` and adds target pairs `(u16,i64)`, `(i16,i32)`, `(u32,i64)`,
`(u8,u16)`.

### WRONG-4 — `domain` says "total" while reporting 0 defined points: 10 new instances
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 04_domain_total_u16.ucas`

**Observed:**
**Reproducer:**
```sh
domain of sh:
  x: u16, 0..65535
  no conditions: total on its parameter types
  defined at 0 of 65536 points
  undefined e.g. at x=0; x=1; x=2; x=3
  C undefined behaviour at 65536 points, e.g. x=0
```

New instances: `u16 (x<<16)`, `u16 (x<<20)`, `u64 (x<<64)`, `u32 (x>>32)`,
`u32 (x % (x-x))`. **Negative result:** the same contradiction does *not*
appear for `x/(x-x)` — `domain` there correctly prints `requires 0 != 0`.
The defect is specific to shift/modulo past width, not to all UB bodies.

### WRONG-5 — WRONG + boundary refinement — f32 `range` misses an interior point spike
**Severity:** WRONG
_Original classification: `WRONG + boundary refinement`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 05_range_spike_boundary.ucas`

**Observed:**
**Reproducer:**
```sh
> range pin          # x == f32(0.1) ? 1e30 : 0
range of pin -> real:
  [0, 0]
  sampled 65536 points (...); not exhaustive
> range pend         # x == f32(1.0) ? 1e30 : 0
range of pend -> real:
  [0, 1e+30]
  sampled 65536 points (...); not exhaustive
```

14 interior spikes (at `f32(0.1)`, `f32(0.5)`, `f64(0.25)`) are missed; 4
spikes placed at the domain endpoint `f32(1.0)` are found. **New refinement of
`fp_edge`:** the miss is not simply "sampling" — it is that the spike value is
off the sampled grid; a spike on a sampled point is reported. This makes the
bug more predictable (and more dangerous for interior spikes).

### WRONG-6 — mixed signed/unsigned reinterpretation: 14 instances
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 06_mixed_sign.ucas`

**Observed:**
**Reproducer:**
```sh
  note: mixing u8 and i8: computed as u8
_() = 255
  -> u8
  note: mixing i64 and u64: computed as u64
_() = 0
  -> bool
```

`u8(1)+i8(-2)` should be `-1`, is `255`; `i64(-1)<u64(1)` should be true, is
false. Broadened across `(u8,i8)`, `(i8,u8)`, `(i64,u64)`, `(u16,i16)`,
`(i32,u32)`, `(u32,i32)` and 7 operators.

### WRONG-7 — nonzero function claimed both symmetric and antisymmetric: 12 instances
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 07_symmetry_both.ucas`

**Observed:**
**Reproducer:**
```sh
symmetry of sy:
  f(x, y) = f(y, x): yes (symmetric)
  f(x, y) = -f(y, x): yes (antisymmetric)
```

Impossible for a nonzero function. Also reproduced through `identify fma(x,y,-x*y)`,
with `real` and `f32`, across 6 near-zero functions.

### WRONG-8 — `powerseries` multiplies the series by the variable: 12 instances
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 08_powerseries.ucas`

**Observed:**
**Reproducer:**
```sh
power series of e^x*x about x = 0
  Taylor coefficients c_0..c_7: 0, 1, 1, 1/2, ...
```

New instances: `sin(x)`, `cos(x)`, `log(1+x)`, `1/(1-x)`, `exp(-x)`,
`1/(1+x)` — all emit the series of `f(x)*x`, not `f(x)`.

### WRONG-9 — English integral bound flip: 16 instances + phrasing refinement
**Severity:** WRONG
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 09_english_boundflip.ucas`

**Observed:**
**Reproducer:**
```sh
  note: read the interval as [0, pi]
  ...
  from 0 to 3.14159: F(3.14159) - F(0) = 4.93480220054468
```

**Expected:** `−4.9348`; the frontend sorted `from pi to 0` ascending. New
functions/intervals: `x²` 1→−1, `x³`, `sin x` 5→1, `exp x` 10→3, `log`, etc.

**New refinement:** the flip is specific to the *"the integral of … from A to
B"* phrasing. The alternative *"integrate … from A to B"* phrasing is
**correct** (2 cases: `integrate exp x from 10 to 3` → `-22006.38…`;
`integrate sin x from 5 to 1` → `-0.2566…`, both negative and matching their
`from A to B: F(B)-F(A)` lines). So a user can avoid the bug by rephrasing.

### WRONG-10 — vacuous "equal, proved by SAT" on an empty domain: 10 instances
**Severity:** WRONG
_Original classification: `WRONG/LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `$ROOT/ucas 10_vacuous.ucas`

**Observed:**
**Reproducer:**
```sh
domain of d: ... defined at 0 of 65536 points ...
> equiv d e
d and e are equal on the domain of d (proved by SAT: 48 AIG nodes, 0 conflicts)
```

The catalog recorded the exhaustive variant; this broadens it to a **SAT**
proof line and to u8/u16/i8 with bodies `x/(y-y)`, `x/(x-x)`, `x%(y-y)`,
`x/0`, `1/(y*y-y*y)`. A differential-testing oracle that trusts "proved" on
an empty domain is unsafe.

### WRONG-11 — stale `it`/`that` self-comparison: 12 new instances
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `cd … && $ROOT/ucas --mcp < mcp_stale_autoname.jsonl`

id 2 asks `equiv it that` where both zero-param bodies are `(x+y)^2`:

**Observed:**
**Reproducer:**
```json
{"kind":"equiv","equal":false,"exhaustive":true,"mismatch_points":1701,
 "method":"exhaustive","counterexample":"x=1, y=1: 2 vs 0"}
```

A function compared to itself returns `equal:false` with a 2-parameter witness
that can only come from request 1 (`x<<y` vs `x>>y`). Reproduced with bodies
`3^5&1`, `x<<y`, `x+1`, `(x+y)^2`, `a*b+c`, `x^y` on all of `--json`,
`--mcp`, `--mcp --flat`. This is the confirmed `type_mutation_diff` bug on a
much wider body set — notably it also fires for `x+1` and `(x+y)^2`, so *any*
zero-param inline `equiv` after an earlier typed request is suspect.

### WRONG-12 — `laplace_solve` drops `;`-separated initial conditions: 10 instances
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Golden:** `cd … && $ROOT/ucas --mcp < mcp_laplace_ic.jsonl`

Request: `y' = -y; y(0) = 5`. Observed:

**Observed:**
**Reproducer:**
```json
"result": {"transformed":"(s + 1)Y(s) = 0","Y(s)":"0",
           "y(t)":{"value":"0","valid_for":"t >= 0"},
           "headline":"y' = -y, y(0) = 0"}
"notes": [{"kind":"rule","text":"y(0) not given: taken as 0"}]
```

The true solution is `5 e^{-t}`; instead the engine reports "y(0) not given"
and returns `y=0`, while its own `checks` claim the residual / RK4 comparison
"passed" (trivially, for the zero solution). New instances cover `y'=2y`,
`y'=-y`, `y'=y+1`, and `y''=y` with two ICs, on both MCP frontends.

### CRASH-1 — deep-parenthesis/unary/abs nesting at depth 1600 (no golden)
**Severity:** CRASH
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
python3 -c 'print("show "+"abs("*1600+"1"+")"*1600)' > /tmp/deep.ucas
timeout 15 $ROOT/ucas /tmp/deep.ucas >/dev/null 2>&1; echo $?   # 139
```

**Observed:** `Segmentation fault`, exit 139, with ~8 KB of echoed input before the
crash. 4 crashes in the corpus: `minus`×1600, `abs`×1600 (CLI) and `paren`×1600
(CLI and **MCP**). **New detail:** at depth 1600 the whole `--mcp` server also
dies (exit 139) — MCP containment is *not* universal; the corpus's `paren`
nesting at 1100/1400 and `sqrt` at 1100/1400 were contained/returned normally,
so containment is depth- and form-dependent. Consistent with `parser_json_fuzz`
(server-wide crash) rather than the blanket "MCP contains it" claim.

### NLP-2 — chained comparisons and number scale words (new instances)
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Representative (CLI `english`):

**Reproducer:**
```sh
printf 'is 1 < 2 < 3?\nwhat is one trillion?\n' | $ROOT/ucas
```

**Observed:** `(1 < 2) < 3` → `note: literal 3 does not fit bool; it becomes 1` → `0`
(expected `true`); `one trillion` → `note: "trillion" is not a word I know:
read as million` → `1000000`. 11 `nlp_misparse` hits across chained `<`/`>` of
length 3 and 4, `trillion` scale words, `7/8 of 64`, `wrap of`, and `make it
faster`. Same known classes as `nlp_arith`/`nlp_numbers`, new phrasings.

## Checks that passed

### Method / validation
- `generate.py` — deterministic (`SEED = 20261116`), 224 mutations, reproducible byte-for-byte.
- `run_corpus.py` — materialises each mutation (a `.ucas` file for CLI; JSON-Lines, MCP or `--mcp --flat` for the wire frontends), runs it under `timeout 15`, classifies the outcome and applies a per-family oracle.
- `mutations.json` / `MUTATIONS.md` — the full corpus + family index.
- `results.jsonl` / `run_summary.txt` — per-mutation outcome, exit code, class and matched known-bug signatures.

**Validation result (which mutations still parse / reach a semantic pass):**

| outcome | count |
|---|---:|
| semantic (reached a semantic pass / structured response) | 209 |
| parse error only | 8 |
| crash (SIGSEGV) | 4 |
| hang | 0 |
| other (benign semantic text not matched by keyword list) | 3 |

So 217/224 mutations produced a real structured/semantic response; the 8
parse-errors are the deliberately malformed NLP/number probes plus 1, and the
4 crashes are the deep-nesting probes (bucket recorded as requested).

**No entirely new bug *class* was found**, but the campaign produced 185
new instances of known classes in the table below (plus 11 NLP misparses,
§15), two useful boundary refinements of known bugs, and one new
interface-level finding (`where` silently dropped on the JSON/MCP surface, §2).

#### Breadth: new instances of known classes

| family (severity) | new instances | contexts varied | golden |
|---|---:|---|---|
| `equiv` ignores G domain (WRONG) | 38 | u8/u16/u32/i8/i16/i32; `where`/declared range/value-set; CLI + JSON/MCP/flat; bodies incl. `x^x` | `01_equiv_domain_u16` |
| JSON/MCP object `where` dropped (NLP) | 8 | u8/u16/i8 × json/mcp/flat | §2 |
| true real identity refuted (WRONG) | 10 | 8 different identities (`(x-y)^2`, `x^2-1`, `(x+y)^3`, `a^2-b^2`, `sin²+cos²`, …) | `02_real_identity_newexpr` |
| cast coercion unsound (WRONG) | 15 | i8 **and i16** sources; u8/u16/i16/i32/u32/i64 targets | `03_cast_i16` |
| `domain` "total" while 0 defined (WRONG) | 10 | u16/u32/u64, `<<`/`>>`/`%` | `04_domain_total_u16` |
| f32 `range` misses point spike (WRONG) | 14 | spike values/locations × f32/f64 | `05_range_spike_boundary` |
| mixed signed/unsigned (WRONG) | 14 | 6 type pairs × 7 operators | `06_mixed_sign` |
| symmetry both yes (WRONG) | 12 | 6 functions × real/f32, `symmetry`/`identify` | `07_symmetry_both` |
| `powerseries` × variable (WRONG) | 12 | 7 functions × orders | `08_powerseries` |
| English integral bound flip (WRONG) | 16 | 6 functions × 6 intervals × CLI/MCP | `09_english_boundflip` |
| vacuous "equal" proof (WRONG/LIMIT) | 10 | u8/u16/i8 × 5 undefined bodies, SAT + exhaustive | `10_vacuous` |
| stale `it`/`that` self-compare (WRONG) | 12 | 6 bodies × json/mcp/flat | `mcp_stale_autoname` |
| `laplace_solve` drops `;` IC (WRONG) | 10 | 5 ODE/IC pairs × MCP/flat | `mcp_laplace_ic` |
| deep-nesting parser overflow (CRASH) | 4 | paren/minus/abs × depth 1600 | §14 (no golden) |

### Golden determinism
Every `.out` in this folder was produced twice with `timeout 30` and the two
runs `diff`ed identical. The crash case (§14) is intentionally left without a
golden. Sampled outputs (e.g. `symmetry`'s "400 random points",
`equiv`'s sampled witness) were also stable across the two runs for the chosen
goldens; if they ever move, the golden will fail loudly rather than mislead.

### Confinement
All files created live in `tests/stress/areas/sat/llm_mutators_findings/`. No source,
Makefile, existing test, `opencode.json`, other stress area, or git state was
modified. Scratch inputs were written under `/tmp/opencode/llm_mut_scratch/`.
