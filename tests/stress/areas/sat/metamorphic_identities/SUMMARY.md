# SUMMARY — `metamorphic_identities`

## Counts
- Distinct expressions/queries tried: 272
- Goldens written: 1
- Files created: not recorded

### What was tried

* **216 catalogued `equiv` tests** in 18 generated files `01_*`–`18_*` (12 per file),
  each a true-by-construction or deliberately-false identity between two typed
  functions. Coverage: `u8/u16/u32/u64`, `i8/i16/i32/i64`, and `int` with ranges.
  Families: `x+x==x<<1`, `x xor x==0`, `(x&y)+(x xor y)==x|y`,
  `x xor y==(x|y)-(x&y)`, `~x==-x-1`, De Morgan, absorption, xor-constant
  self-cancellation, `x<<k>>k==x&(MAX>>k)`, xor+carry addition, pack/unpack and
  rotate, ring laws for `*` and `xor`, quadratic expansion (true on `int` ranges and
  under machine wrap), `isqrt` inequalities (true on narrow/int domains, false under
  full-width wrap), and **stacked** 2–5 identity rewrites applied to seeds `x`,
  `x+y`, `x*y`, `x|x`, `~(x&y)` and `(a+b)^2`.
* **6 extra CLI reproducer tests** in `19_*`–`22_*` (wide polynomial LIMIT, `^`
  context, false wide polynomial, undefined-name WRONG).
* **1 MCP golden** (`mcp_metamorphic.jsonl`): typed definitions via the `ucas`
  escape hatch, 7 `analyze`/`equiv` calls (exhaustive, SAT and refuting cases), and
  a `theorem`/`prove` pair via `proofs`.
* Roughly **40 additional exploratory probes** in `_scratch/` (corner cases,
  domain narrowing, SAT/witness behaviour, CLI↔MCP agreement) that were not kept
  as goldens.

**Total distinct expressions/queries tried: ~272** (222 `equiv` statements in
golden files + 10 MCP calls + ~40 probes).

### Files created (deliverables)

* `01_u8_core.ucas/.out` … `18_corners.ucas/.out` — 18 CLI golden pairs.
* `19_poly_wide_limit.ucas/.out`, `20_caret_context.ucas/.out`,
  `21_poly_wide_false.ucas/.out`, `22_undefined_ref.ucas/.out` — 4 CLI golden pairs
  (19 is a LIMIT reproducer kept with a golden; 22 captures a WRONG answer; see
  FINDINGS.md).
* `mcp_metamorphic.jsonl` + `mcp_metamorphic.out` — MCP golden.
* `FINDINGS.md`, `SUMMARY.md`.
* `_scratch/` — generator (`gen.py`), checker (`check.py`), manifest and probes
  (working material, not part of the golden set).

All 22 golden `.out` files and the MCP golden were produced with the documented
commands under `timeout`, and every golden was regenerated a second time and
compared byte-for-byte: **all deterministic**. All goldens complete in < 1 s except
`19_poly_wide_limit` (~5 s) and `12_poly_wrap_true` historically (now < 0.1 s after
the SAT-prone case was moved out).

### Scope confirmation

All files were created only under `tests/stress/areas/sat/metamorphic_identities/`. No source
file, Makefile, existing test, `opencode.json`, or another subagent's folder was
touched; no build or git command was run.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | Undefined identifier silently becomes a free identity variable; equiv f nonexistent_name returns equal:true |
| NLP | 1 | ^ parses as power or xor depending on nearby bitwise operators; stacked ~(~(x^2)) breaks; CLI defaults, MCP errors |
| LIMIT | 1 | Wide polynomial identities fall back to 4-point Schwartz-Zippel after SAT gives up: equal:true with no proof, ~10 s/query |

### Issues by severity

| Severity | Count | Short description |
| --- | --- | --- |
| CRASH | 0 | — |
| HANG | 0 | — |
| WRONG | 1 | Undefined identifier silently becomes a free identity variable; `equiv f nonexistent_name` returns `equal:true` |
| NLP | 1 | `^` parses as power or xor depending on nearby bitwise operators; stacked `~(~(x^2))` breaks; CLI defaults, MCP errors |
| LIMIT | 1 | Wide polynomial identities fall back to 4-point Schwartz-Zippel after SAT gives up: `equal:true` with no proof, ~10 s/query |
| DETERMINISM | 0 | — |

(One unconfirmed Code-Mode MCP transport error is recorded under "Notes" in
FINDINGS.md and is **not** counted as a ucas bug because it did not reproduce over
`ucas --mcp`.)


## Takeaway
The metamorphic oracle is sound on the identities themselves — 192/192 true ones returned equal and all 24 deliberately-false ones were refuted — but ucas can be fooled at the edges: a typo'd function name is reinterpreted as a free variable and reported equal, and `^` changes meaning under bitwise rewrites, so identity stacks must use explicit `xor`/`**` and golden callers must check `proof`, not just `equal`.

### Original takeaway (verbatim)

The metamorphic oracle is sound on the identities themselves — 192/192 true ones
returned equal and all 24 deliberately-false ones were refuted — but ucas can be fooled at the
edges: a typo'd function name is reinterpreted as a free variable and reported equal,
and `^` changes meaning under bitwise rewrites, so identity stacks must use explicit
`xor`/`**` and golden callers must check `proof`, not just `equal`.
