# SUMMARY — `equiv_domain_systematic`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 9
- Files created: 6

### Original preamble

Systematic cross-product follow-up on the "equiv ignores G's domain" root cause
(binary `$ROOT/ucas`, not rebuilt).

### Counts

| item | count |
|---|---:|
| distinct restriction scenarios | 23 (8 families: where / typed range / typed set / where-set / partial match / table index / div-by-zero / shift≥width — plus sqrt-negative control) |
| comparison commands | 7 (`equiv`, `error`, `fit`, `domain`, `range`, `wrap`, `differ`-via-analyze) |
| frontends | 4 (CLI, `--json`, `--mcp` grouped, `--mcp --flat`) |
| arg modes | 3 (full source, raw-string name, function object) |
| bounded case-runs | ≈800 (165 Part-A source cross-product + 543 Part-B structured requests + 32 Part-C SAT/extra + 60 fuzz + ad-hoc probes) |
| WRONG findings | 3 (§1 equiv domain — extended; §2 error domain — new; §3 wrap exact/mismatch contradiction — new) |
| NLP findings | 2 (§4 function-object `where` dropped by domain/range/wrap — extended; §7 overflowed where bound) |
| LIMIT findings | 3 (§5 `differ` not an op; §6 `fit` inapplicable; plus §3/§7 overlap) |
| CRASH / HANG | 0 |
| DETERMINISM issues | 0 (all 9 goldens byte-stable across double runs) |
| text-vs-structured contradictions in equiv/error | 0 / 60 fuzz + all goldens |
| files created | 6 CLI goldens (`.ucas`+`.out`), 3 MCP goldens (`.jsonl`+`.out`+1 `.flags`), 3 harness scripts, 5 `results_*.jsonl`, FINDINGS.md, SUMMARY.md |


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| NLP | 2 | — |
| LIMIT | 3 | — |

### Goldens (deterministic, verified twice)

`01_equiv_declaration_restrictions`, `02_equiv_body_undefinedness` (controls),
`03_equiv_sat_i8_twoparam`, `04_error_drops_where`,
`05_where_literal_overflow`, `06_wrap_exact_vs_zero_points`,
`mcp_equiv_domain`, `mcp_flat_equiv_domain` (`.flags`: `--flat`),
`mcp_funcobj_where_drop`.


## Takeaway
The declaration-level domain of G is silently discarded by `equiv` and `error` on **every** frontend and in **both** arg modes (only body-level undefinedness is honored); the function-object surface additionally drops `where` entirely, so `domain`/`range`/`wrap` disagree with the equivalent raw-string path, and `wrap` reports `exact:false` alongside `mismatch_points:0`.

### Original takeaway (verbatim)

The declaration-level domain of G is silently discarded by `equiv` and `error`
on **every** frontend and in **both** arg modes (only body-level undefinedness
is honored); the function-object surface additionally drops `where` entirely,
so `domain`/`range`/`wrap` disagree with the equivalent raw-string path, and
`wrap` reports `exact:false` alongside `mismatch_points:0`. No crashes, hangs,
or nondeterminism found.
