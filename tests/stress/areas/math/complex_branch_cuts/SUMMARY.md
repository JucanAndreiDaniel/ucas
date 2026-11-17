# SUMMARY — `complex_branch_cuts`

## Counts
- Distinct expressions/queries tried: 250
- Goldens written: 14
- Files created: 14

### Counts

- **Distinct expressions / queries tried:** ~250+ distinct
  - 170 statements in CLI golden `.ucas` files
  - 40 MCP `tools/call` requests across 3 `.jsonl` sessions
  - ~80 further distinct exploratory probes (signed zeros, `(z,w,i)` one-sided limits,
    NLP phrasings, higher-order poles, `nthroots` edge cases; deduplicated)
- **Golden files created:** 14 (11 CLI + 3 MCP), each with its `.out`
  - CLI: `01_sqrt_log_cuts`, `02_powers_roots`, `03_parts_identities`, `04_inverse_trig`,
    `05_float_cuts`, `06_poles_residue`, `07_limits_multivalued`, `08_wrong_power_decomp`,
    `09_nlp_branch`, `10_misc_boundary`, `11_complex_side_limit_parse`
  - MCP: `mcp_complex_ops`, `mcp_wrong_decomp`, `mcp_props_calculus`
- **Documentation files:** `FINDINGS.md`, `SUMMARY.md`
- **Determinism:** all 14 goldens run twice and diffed — byte-identical; all exit 0.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | NLP-2 ("principal value of (-1)^(1/2)" → arg, FAILED/nan) |
| NLP | 2 | NLP-2 ("principal value of (-1)^(1/2)" → arg, FAILED/nan) |
| LIMIT | 3 | LIMIT-1 (one-sided complex-variable limits unparseable), LIMIT-2 (continuity ignores complex assumption), LIMIT-3 (atanh(1) unevaluated) |

### Issues by severity

| Severity | Count | IDs |
|----------|-------|-----|
| WRONG | 3 | WRONG-1 (`(-1)^(p/q)` Re/Im decomposition), WRONG-2 (`re`/`im` of powers fail own checks), WRONG-3 (`poles` misses order≥2) |
| NLP | 1 | NLP-1 ("principal value of log" → `arg`) |
| NLP/WRONG | 1 | NLP-2 ("principal value of (-1)^(1/2)" → `arg`, FAILED/nan) |
| LIMIT | 3 | LIMIT-1 (one-sided complex-variable limits unparseable), LIMIT-2 (`continuity` ignores complex assumption), LIMIT-3 (`atanh(1)` unevaluated) |
| CRASH / HANG / DETERMINISM | 0 | — |


## Takeaway
Branch-cut values themselves are mostly self-consistent (upper-lip convention, DLMF inverse trig), but negative-base rational powers get **wrong, self-contradictory Re/Im decompositions with vacuously passing checks**, `poles` **silently drops all higher-order poles**, "principal value of …" is **misrouted to `arg`** by the English frontend, and there is **no working way to take a one-sided limit toward a cut for a complex variable**.

### Original takeaway (verbatim)

Branch-cut values themselves are mostly self-consistent (upper-lip convention, DLMF inverse trig),
but negative-base rational powers get **wrong, self-contradictory Re/Im decompositions with vacuously
passing checks**, `poles` **silently drops all higher-order poles**, "principal value of …" is
**misrouted to `arg`** by the English frontend, and there is **no working way to take a one-sided
limit toward a cut for a complex variable**.
