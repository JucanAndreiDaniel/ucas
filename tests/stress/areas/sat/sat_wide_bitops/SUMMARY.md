# SUMMARY — `sat_wide_bitops`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 14
- Files created: not recorded

### Coverage

| metric | count |
|---|---|
| Distinct CLI statements tried (12 `.ucas` files) | 135 |
| MCP `analyze` calls — `mcp_wide_bitops.jsonl` | 31 |
| MCP calls — `mcp_flat.jsonl` (`--flat` mode) | 9 |
| **Total distinct expressions / queries** | **175** |

Operations exercised: `equiv`, `range`, `wrap`, `domain`, `cost`, MCP `analyze`
(`parse`, `show`, `table`, plus all five above), CLI `table`, `model`, `find`-adjacent
bit identities.  Bit topics: u8/u16/u32/u64 variable shifts (narrow-range and
full-domain), rotate-by-shift-or, masks and `(x & mask)==0`, sign extension
(`i64(i32(x))`, xor-subtract), `popcount`, `clz`, `ctz`, manual SWAR popcount and
bit-SUM identities, de-Bruijn-style table constants, division/modulo by
constants and variables, `isqrt` (u8/u16/u32/u64), packed `[t0,...][i]` lookups
(in-bounds and out-of-bounds), comparison chains, and SAT-vs-algebra-vs-exhaustive
proofs.  Both narrow-range variants and full-domain variants are included.

### Files created

- CLI goldens (`.ucas` + `.out`): `01_shifts_wrap`, `02_rotates_masks`,
  `03_popcount_ctz`, `04_divmod`, `05_isqrt_tables`, `06_comparisons`,
  `07_equiv_sat`, `08_cost`, `09_wrap_narrow`, `10_domain_edges`,
  `11_signext_reverse`, `12_wide_ranges` — 24 files.
- MCP golden: `mcp_wide_bitops.jsonl` + `mcp_wide_bitops.out` (31 calls) — 2 files.
- MCP `--flat` golden: `mcp_flat.jsonl` + `mcp_flat.out` + `mcp_flat.flags` — 3 files.
- `FINDINGS.md`, `SUMMARY.md` — 2 files.
- All 14 golden outputs were generated with `timeout` from the owning directory
  and re-run + `diff`-checked byte-for-byte identical (no random witnesses,
  samples, or timing numbers).  `--flat` golden regenerated with
  `$ROOT/ucas --mcp --flat < mcp_flat.jsonl`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | (1) u64 wrap end-to-end verdict false whenever result has bit 63 set, incl. identity x; (2) inline function definitions silently misparse in |
| NLP | 1 | (6) 2-letter inline names silently read as juxtaposition on CLI but hard-error on MCP |
| LIMIT | 3 | (3) SAT gave up on 64-bit SWAR popcount equiv (graceful, sampled fallback); (4) MCP equiv rejects the documented plain-string expression for |

### Issues by severity

| severity | count | items |
|---|---:|---|
| CRASH | 0 | — |
| HANG | 0 | — |
| WRONG | 2 | (1) u64 `wrap` end-to-end verdict false whenever result has bit 63 set, incl. identity `x`; (2) inline function definitions silently misparse into bogus `name*x == body` answers |
| NLP | 1 | (6) 2-letter inline names silently read as juxtaposition on CLI but hard-error on MCP |
| LIMIT | 3 | (3) SAT gave up on 64-bit SWAR popcount `equiv` (graceful, sampled fallback); (4) MCP `equiv` rejects the documented plain-string expression form; (5) empty witness "differs at 0 points, e.g. " for always-undefined constant shift |
| DETERMINISM | 0 | — |

Total findings: 6 (see `FINDINGS.md` for exact reproducers and outputs).


## Takeaway
The SAT bit-blasting path itself is robust (no crashes, hangs, or wrong proofs in 175+ wide-bit queries, and shift-by-width/UB is diagnosed gracefully), but the **u64 `wrap` end-to-end checker is unsound for values above 2^63** and the analysis frontends silently accept malformed inline definitions and produce bogus answers instead of parse errors.

### Original takeaway (verbatim)

The SAT bit-blasting path itself is robust (no crashes, hangs, or wrong proofs
in 175+ wide-bit queries, and shift-by-width/UB is diagnosed gracefully), but
the **u64 `wrap` end-to-end checker is unsound for values above 2^63** and the
analysis frontends silently accept malformed inline definitions and produce
bogus answers instead of parse errors.
