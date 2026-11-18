# SUMMARY — `ntheory_army`

## Counts
- Fix verifications: 2 (large-prime-square factorization, bounded honest budget)
- Flags recorded but out of source ownership: 1 (English "zerodivisors mod 12")
- New mined bugs: 3 (BUG-A overflow diagnostic, BUG-B MCP crt `x`, BUG-C MCP sqrtmod `modulus`)
- Goldens: 4 CLI (`.ucas`) + 3 MCP (`.jsonl`), each with a `.out`
- Controls: `00_controls.ucas` plus in-golden negative/positive pairs

## Files
- `00_controls.ucas` / `.out` — unchanged correct number-theory behaviour
- `01_fixed_factorization.ucas` / `.out` — FIX-1/FIX-2: large prime squares factor completely
- `02_budget_honesty.ucas` / `.out` — FIX-1: hard cofactors return honest `not fully factored`
- `03_bug_overflow_diagnostic.ucas` / `.out` — BUG-A
- `mcp_sqrtmod_fields.jsonl` / `.out` — BUG-C (ids 1-2 buggy, ids 3-4 controls)
- `mcp_crt_fields.jsonl` / `.out` — BUG-B (id 1 buggy, id 2 control)
- `mcp_english_zerodivisors.jsonl` / `.out` — FIX-3 (NLP misroute, awaiting NLP-side fix)
- `FINDINGS.md`, `SUMMARY.md`

## Source changed
- `src/zint.c`: added `z_isqrt` (integer Newton sqrt), perfect-square fast path
  in `z_factor`, and a 5 s CPU rho deadline checked every 4096 iterations.
  The prior wave's bigint print cap (`Z_PRINT_MAX_DIGITS`) is untouched.
- `src/ntheory.c`: no change (audited by differential testing).

## Compliance
All new files are inside `tests/stress/areas/math/ntheory_army/`. No other
source, test, golden, or Makefile was modified by this wave; no commit was made.
Goldens were produced with `bmake stress-accept` under `UCAS_NO_TIMES=1
UCAS_SPIRV_CROSS=none`; CLI runs bounded by `timeout 15`.
