# Stress findings — `readme_examples`

_Original heading: Documentation-correctness findings — area `readme_examples`_

# Documentation-correctness findings — area `readme_examples`

Scope: every fenced code block / example statement / claimed output in
`$ROOT/README.md`, the skill's `.claude/skills/ucas/SKILL.md`,
and `.claude/skills/ucas/test.sh` was extracted and run with
`timeout 15` (long searches retried at `timeout 30`) against
`$ROOT/ucas`, from this folder.  All commands below are
copy-pasteable; `B=$ROOT/ucas`.

Most documented examples reproduce exactly (gates, algebra, all SAT/float
equivs, complex/hypercomplex, `approx sin`, all `error` examples, all `find`
rewrite examples, dot products, `cost pc`, every typed JSON example, MCP
handshake/tools/resources/prompts).  The mismatches are below.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 6 | `find days` lookup-table cost documented as 9, actually 8 |
| NLP | 1 | documented English example `is avg comutative?` errors as written |
| LIMIT | 3 | three documented `cost F(params) = expr` commands error |

## Findings

### WRONG-1 — `find days` lookup-table cost documented as 9, actually 8
**Severity:** WRONG
_Original classification: `WRONG: find days lookup-table cost documented as 9, actually 8`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- README **line 51** (inside the "A tour" block, lines 48–51):
  `  cost 9   [31, 28, 31, ...][m - 1]                lookup table (baseline)`
- Reproducer (README lines 48–49):
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/frontend/readme_examples
  timeout 15 $ROOT/ucas -e 'days(m: u8 in 1..12) = match m { 2 => 28, 4 | 6 | 9 | 11 => 30, _ => 31 }' -e 'find days'
  ```
- Expected (documented): a `cost 9` baseline line.
- Observed (deterministic over 3 runs):
  ```
    cost 6   u8(0x3bbeecc >> (u32(m) << 1) & 3) + 28  packed table in one constant
    cost 8   [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1] lookup table (baseline)
  ```
- Why: the documented cost model is stale (or the baseline changed).  The
  `cost 6` packed-table line still matches.  Golden: `02_days_find.ucas` / `.out`.

### LIMIT-1 — three documented `cost F(params) = expr` commands error
**Severity:** LIMIT
_Original classification: `LIMIT: three documented cost F(params) = expr commands error`._
**Why it matters:** _not recorded_
- README **lines 2115, 2165, 2170**, written as one-line inline definitions:
**Observed:**
**Reproducer:**
```sh
  > cost s1(x: f32, y: f32, z: f32) = min(max(x * y + z, 0.0), 1.0)
  > cost lop3(a: u32, b: u32, c: u32, k: u32) = ((a & b) | (~a & c)) + k
  > cost sh(a: u32, b: u32, c: u32) = a * b + (a * b) * c
  ```
- Reproducer:
  ```sh
  timeout 15 $ROOT/ucas -e 'cost lop3(a: u32, b: u32, c: u32, k: u32) = ((a & b) | (~a & c)) + k'
  ```
-
**Expected:** a cost report, e.g. `cost of lop3 under gt1030: 2 (5 operations, shared subterms counted once)` (the README's own claimed output at line 2166).
- Observed:
  ```
  <arg>:1:17: error: expected ')', found ','
      cost lop3(a: u32, b: u32, c: u32, k: u32) = ((a & b) | (~a & c)) + k
                      ^
  ```
  (rc=0 because ucas recovers; no cost report is produced.)  Same failure for
  the other two lines, and generally for any inline **multi-parameter** command
  function (`range f(a: u8, b: u8) = a + b` also errors).  Single-parameter
  inline works (`range isqrt(x: u4)`).
- Why: the README's stated rule (line 152–153: "A command's function argument is
  a name or an anonymous expression with inline annotations") holds only for one
  parameter.  Workaround — define first, then price:
  ```sh
  timeout 15 $ROOT/ucas -e 'lop3(a: u32, b: u32, c: u32, k: u32) = ((a & b) | (~a & c)) + k' -e 'cost lop3'
  ```
  — gives the documented `cost of lop3 under gt1030: 2 (5 operations, shared
  subterms counted once)`, and `sh` gives the documented `cost of sh under
  gt1030: 6 (3 operations, shared subterms counted once)`.  Golden for the
  failures: `18_cost_inline_doc_fail.ucas` / `.out`.

### NLP-1 — documented English example `is avg comutative?` errors as written
**Severity:** NLP
_Original classification: `NLP: documented English example is avg comutative? errors as written`._
**Why it matters:** _not recorded_
- README **lines 1320–1324**:
**Observed:**
**Reproducer:**
```sh
  > is avg comutative?
    note: read "comutative" as "commutative"
    ucas: lhs(a: u8, b: u8) = avg(a, b)
    ucas: rhs(a: u8, b: u8) = avg(b, a)
    ucas: equiv lhs rhs
  ```
- Reproducer:
  ```sh
  timeout 15 $ROOT/ucas -e 'is avg comutative?'
  ```
-
**Expected:** the three `ucas:` statements above.
- Observed:
  ```
    note: read "comutative" as "commutative"
    sorry: commutative needs two arguments; it has one
  ```
- Why: the documented example silently assumes `avg` is already a defined
  2-argument function in the session; the isolated block in the README does not
  define it, so the translator cannot find the second argument.  With
  `avg(a: u8, b: u8) = (a + b) / 2` defined first, the translation succeeds —
  but prints an *extra* line the README omits:
  `  note: commutative: avg(a, b) = avg(b, a) everywhere?`
  Goldens: `17_english_avg_doc_fail.ucas` / `.out` (documented form),
  `16_english.ucas` / `.out` (working form).

### WRONG-2 — SKILL.md claims 818 SAT conflicts; observed 833 (stable)
**Severity:** WRONG
_Original classification: `WRONG: SKILL.md claims 818 SAT conflicts; observed 833 (stable`._
**Why it matters:** _not recorded_
- `.claude/skills/ucas/SKILL.md` **lines 38, 68, 78** all state
  `"proved by SAT: 745 AIG nodes, 818 conflicts"`.
- Reproducer:
**Observed:**
**Reproducer:**
  ```sh
  timeout 15 $ROOT/ucas \
    -e 'avg(x: u32, y: u32) = (x & y) + ((x xor y) >> 1)' \
    -e 'avg2(x: u32, y: u32) = u32((u64(x) + u64(y)) >> 1)' -e 'equiv avg avg2'
  ```
-
**Expected:** `avg and avg2 are equal on the domain of avg (proved by SAT: 745 AIG nodes, 818 conflicts)`
- Observed (identical on 3 runs; identical via MCP `analyze`/`equiv`):
  `avg and avg2 are equal on the domain of avg (proved by SAT: 745 AIG nodes, 833 conflicts)`
- Why: the AIG node count still matches (745), only the conflict count drifted.
  `test.sh` line 20 checks only the pattern `proved by SAT`, so the stale number
  is not caught.  Golden: `mcp_equiv_avg.jsonl` / `.out`.

### WRONG-3 — documented MCP `tools/list` sizes are ~2x too small
**Severity:** WRONG
_Original classification: `WRONG: documented MCP tools/list sizes are ~2x too small`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- README **line 1868** "As one tool each they make a 340 KB `tools/list`";
  **line 1897** "about 4 KB a tool and 60 KB in all";
  **lines 1902–1903** "`--flat` ... to keep the list at 340 KB rather than 690 KB"
  (also "about 150 commands", line 1867).
- Reproducer (send `initialize`, `notifications/initialized`, `tools/list` to
  `ucas --mcp`, with and without `--flat`; the files `/tmp/mcp_list.jsonl`
  used are reproduced by the same three lines as `mcp_calculus_integrate.jsonl`):
**Observed:**
**Reproducer:**
  ```sh
  printf '%s\n' \
   '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"r","version":"1"}}}' \
   '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
   '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
   | timeout 15 $ROOT/ucas --mcp
  ```
- Expected (documented): grouped ≈ 60 KB; flat ≈ 340 KB.
- Observed (raw response-line bytes; stable):
  - grouped (`--mcp`): **27 tools, 133554 bytes (~133.5 KB)**, per-tool descriptions ≈ 4.9 KB.
  - flat (`--mcp --flat`): **248 tools, 508715 bytes (~508.7 KB)**.
- Why: the tool inventory grew (and its descriptions) since those numbers were
  written.  Size claims are documentation drift, not a protocol fault.  No
  golden kept (this is a measurement, not a stable command output).

### WRONG-4 — `cost quant` total documented as 134, actually 190.25
**Severity:** WRONG
_Original classification: `WRONG: cost quant total documented as 134, actually 190.25`._
**Why it matters:** _not recorded_
- README **line 2412** `cost of quant under gt1030: 134 (0 operations outside loops and 1 loop, ...)`,
  **line 2418** `per iteration: body 20 + overhead 5 (index add, compare, branch) = 25`,
  **line 2420** `once: 9 (initial values and loop-invariant subterms, hoisted)`,
  **line 2421** `loop total: 134` (block lines 2407–2423).
- Reproducer: run `15_cost_loops.ucas` (function copied verbatim from README
  lines 2407–2410), i.e.:
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/frontend/readme_examples
  timeout 15 $ROOT/ucas 15_cost_loops.ucas
  ```
-
**Expected:** total 134; per-iteration 25; once 9.
- Observed (deterministic over 2 runs):
  ```
  cost of quant under gt1030: 190.25 (0 operations outside loops and 1 loop, shared subterms counted once)
    ...
    loop d in -2..2:
      per iteration: body 23.625 + overhead 9.625 (index add, compare, branch) = 33.25
      trip count: 5 (constant bounds)
      once: 24 (initial values and loop-invariant subterms, hoisted)
      loop total: 190.25
  ```
- Why: the loop cost under the active `gt1030` model has grown (the output now
  also lists `cmp 2.375`, `select 1.625`, `branch 6.25`, `sdivk 21` prices).
  The `cost pc` example in the same README section (lines 2391–2399) still
  matches exactly.  Golden: `15_cost_loops.ucas` / `.out`.

### WRONG-5 — `polar` numeric check drifted 4e-16 → 3e-16
**Severity:** WRONG
_Original classification: `WRONG (minor): polar numeric check drifted 4e-16 → 3e-16`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Why it matters:** _not recorded_
- README **line 492**: `  check: equal at 64 of 64 sample points (max relative difference 4e-16)`
- Reproducer: `timeout 15 $ROOT/ucas -e 'polar x + i y'`
-
**Expected:** `... max relative difference 4e-16`
- Observed: `  check: equal at 64 of 64 sample points (max relative difference 3e-16)`
  (appears twice).  Everything else in the block (note, formula, principal
  argument) matches.  Golden: `07_complex_trig.ucas` / `.out`.

### WRONG-6 — documented JSON `ucas` echo omits `wrt x`
**Severity:** WRONG
_Original classification: `WRONG (minor): documented JSON ucas echo omits wrt x`._
**Why it matters:** _not recorded_
- README **line 1562**: `"ucas": "integrate x/x from -1 to 1", ...`
- Reproducer:
**Observed:**
**Reproducer:**
  ```sh
  timeout 15 $ROOT/ucas --json -e '{"id": 7, "cmd": "integrate", "args": {"f": "x/x", "var": "x", "from": -1, "to": 1}}'
  ```
-
**Expected:** `"ucas": "integrate x/x from -1 to 1"`
- Observed: `"ucas": "integrate x/x wrt x from -1 to 1"` — the generated
  statement includes `wrt x` (all other fields, `result`, `notes`, `conditions`,
  `checks`, `text`, match the documented example).  No golden (CLI `--json`
  example); this is the exact observed field.

### LIMIT-2 — documented `approx ... search anneal` example does not finish within 30s
**Severity:** LIMIT
_Original classification: `LIMIT: documented approx ... search anneal example does not finish w`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- README **lines 788–795** show a complete candidate/search/certified table for
  `approx sin(x) in 0..0.7853981 degree 5 as f32 list 2 search anneal`.
- Reproducer:
**Observed:**
**Reproducer:**
  ```sh
  timeout 30 $ROOT/ucas -e 'approx sin(x) in 0..0.7853981 degree 5 as f32 list 2 search anneal'
  ```
- Observed: exit code 124 (timeout) at both 15s and 30s; only the preamble,
  the real-arithmetic fit table, the rational fits and the first piecewise
  line are printed — none of the documented `1 minimax 5 ... search:` /
  `certified:` lines are reached.
- Why: this documented example is a long stochastic search that exceeds the
  stress-test bound on this machine.  Kept out of the goldens (it would break a
  test runner); genuine LIMIT, not a crash.  The earlier `approx sin ... degree
  5..9` example (README lines 708–723) completes and matches.

### LIMIT-3 — `basis` code block contains literal `...` placeholders
**Severity:** LIMIT
_Original classification: `LIMIT (minor): basis code block contains literal ... placeholders`._
**Why it matters:** _not recorded_
- README **line 1930**:
  `basis a64sha : a64 { bsl(s, x, y) = (s & x) | (~s & y); eor3(...); bcax(...) }`
- Reproducer: run the README lines 1926–1934 verbatim as a `.ucas` file
  (`19_bases_doc_ellipsis_fail.ucas`).
-
**Expected:** all seven `basis` declarations run.
- Observed:
**Observed:**
**Reproducer:**
```sh
  $ROOT/tests/stress/areas/frontend/readme_examples/19_bases_doc_ellipsis_fail.ucas:4:64: error: unexpected character '.'
      basis a64sha : a64 { bsl(s, x, y) = (s & x) | (~s & y); eor3(...); bcax(...) }
                                                                     ^
  ```
- Why: `...` is documentation shorthand, not ucas syntax; as written the
  fenced block does not parse.  Deleting `eor3(...); bcax(...)` makes all seven
  declarations parse and run.  Golden: `19_bases_doc_ellipsis_fail.ucas` / `.out`.

## Checks that passed

### Notes on cases that MATCH (no finding)
- Tour: `gates isqrt4` (both bases, including the exact "660213 candidates
  searched" and `bsl` line), `fit guess ~ rsqrt` (`K = 1597465581`, 3.42%),
  `error quake ~ rsqrt` (`0.00175224 (0.175%)`), `wrap s` (128 points,
  `exact for: -64..63`).
- Symbolic algebra: every `factor`/`simplify`/`integrate`/`solve` line of lines 354–373.
- Proofs: `equiv f g` (algebra), `q1/q2`, `m1/m2` nanbits, `l2a/l2b`
  (16609 AIG nodes, 0 conflicts), `u1/u2` counterexample — all byte-for-byte.
- `complex`, `trig sin*cos`, and the whole hypercomplex block.
- `approx sin` fits table and minimax deg-9 candidate; all `error` examples
  (`qz`, `dot2`/`naive`, `s20`) including their rounding lines.
- All `find` examples: `sd`, `ud`, `dv`, `d`, `sw`, `q`, `cv`, `ld`, `tx`,
  `f`/`g` dot products (including "proved by SAT: 755 AIG nodes, 0 conflicts").
- Cost models `xmad`, `sat`, `sgf`, `rdna2` outputs (lines 2111–2112, 2116–2119,
  2145–2149, 2197–2202) match when the model/function are defined first.
- `show`/`range` dot products, `cost pc`, all typed JSON requests of lines
  1691–1702, the JSON `integrate` and ambiguity examples, the MCP handshake,
  `tools/call`, `resources/read` and `prompts/list`.
