# SUMMARY — `type_coercion`

## Counts
- Distinct expressions/queries tried: 200
- Goldens written: 11
- Files created: 28

### Counts

- **Distinct expressions / queries tried:** ~200 distinct expressions and queries
  (~480 total runs including repeat/determinism runs and exploratory probes).
  Final goldens contain **181 CLI statements** (files 01–11) and **18 MCP tool calls**
  (`mcp_type_coercion` 14, `mcp_range_boundary` 4).
- **Adversarial single-expression probes:** 49, each under `timeout 8` — all exit 0
  (no crash, no hang).
- **Files written:** 28
  - 11 CLI golden pairs: `01_mixed_infer` … `11_quat_cd` (`.ucas` + `.out`)
  - 2 MCP golden pairs: `mcp_type_coercion`, `mcp_range_boundary` (`.jsonl` + `.out`)
  - `FINDINGS.md`, `SUMMARY.md`
- **Determinism:** every golden generated twice and `diff`ed — all identical.
- **Issues by severity:** WRONG ×5, LIMIT ×2, CRASH 0, HANG 0, DETERMINISM 0.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 15 | Mixed signed/unsigned silently reinterprets & narrows (u8(1)+i8(-2)=255) |
| LIMIT | 13 | Free z/w default to complex on CLI but are ambiguous over MCP |

### Issues at a glance

| # | Severity | Title | Repro |
|---|----------|-------|-------|
| 1 | WRONG | `equiv` proves `u8` identity == `i8` reinterpretation | `ucas 06_equiv_reinterpret.ucas` |
| 2 | WRONG | Monotonicity "proved bound" wrong for i56–i63 range | `ucas 05_range_signed_boundary.ucas`, `ucas --mcp < mcp_range_boundary.jsonl` |
| 3 | WRONG | `re`/`im`/`abs`/`arg`/`conj`/`real` of complex infer as `complex` | `ucas 03_complex_infer.ucas` |
| 4 | WRONG | `domain` "no conditions: total" yet 10/11 undefined; `wrap` disagrees | `ucas 07_domain_wrap_int.ucas` |
| 5 | WRONG | Mixed signed/unsigned silently reinterprets & narrows (`u8(1)+i8(-2)=255`) | `ucas 01_mixed_infer.ucas`, `ucas 07_domain_wrap_int.ucas` |
| 6 | LIMIT | Inline definition after `range`/`wrap` misparsed into bogus free variable | `printf 'wrap u8ovf(x: u8 in 250..255) = x+10\n' \| ucas` |
| 7 | LIMIT | Free `z`/`w` default to complex on CLI but are `ambiguous` over MCP | `03_complex_infer.out` vs `mcp_type_coercion.out` |


## Takeaway
Type coercion is where the unsoundness lives: `equiv` proves signed and unsigned reinterpretations equal and `range`'s monotonicity proof reports a wrong max for wide signed types, while complex-valued real functions are mistyped and `domain`/`wrap` disagree on int64 overflow.

### Original takeaway (verbatim)

Type coercion is where the unsoundness lives: `equiv` proves signed and unsigned
reinterpretations equal and `range`'s monotonicity proof reports a wrong max for
wide signed types, while complex-valued real functions are mistyped and `domain`/`wrap`
disagree on int64 overflow.
