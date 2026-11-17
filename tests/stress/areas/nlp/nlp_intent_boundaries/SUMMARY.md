# SUMMARY — `nlp_intent_boundaries`

## Counts
- Distinct expressions/queries tried: 247
- Goldens written: 11
- Files created: 24

### Counts
- Distinct English queries tried: **247** (labeled 221-query corpus + probe batches + 10 adversarial
  chained-intent probes + the golden subsets). Every request was bounded by `timeout`; all returned
  (no crash/hang/malformed JSON).
- Files created in this folder: **24**
  - 11 MCP goldens (`mcp_*.jsonl` + `mcp_*.out`): `eq_neq`, `range_domain_wrap`, `find_gates`,
    `crit_maxmin_zeros`, `integral_area_anti`, `sum_closed_genfunc`, `diff_slope_rate`,
    `solve_ode_eq`, `define_let_assume`, `mixed_dual` (10 pairs = 20 files) plus
    `01_eq_neq_cli.ucas` + `01_eq_neq_cli.out` (1 pair) = 22 golden files, plus `FINDINGS.md` and
    `SUMMARY.md` = 24 total files (22 golden files + 2 docs).
  - All 11 golden `.out` files verified deterministic (each run twice, byte-identical).
- Issues by severity:
  - **WRONG**: 1 (F1 — "unequal" read as "equal", inverted answer)
  - **NLP**: 7 (F2 equivalence→find, F3 inequality side unsupported, F4 extrema routing split,
    F5 leading-"find" hijack, F6 `ok:true`+empty statements, F7 single-letter "of f" misparse,
    F8 compare→error)
  - **LIMIT**: 2 (F9 equality-phrasing inconsistency, F10 no two-intent composition)
  - **CRASH / HANG / DETERMINISM**: 0


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| NLP | 7 | — |
| LIMIT | 2 | — |

## Takeaway
The equal/different boundary is the sharpest: "unequal" is silently rewritten to "equal" and answers with the opposite polarity (F1), while every other "different/not-equal" phrasing fails (F3); the single most dramatic misroute is "equivalence of f and g" → `find it 10` on `f & g` (F2).

### Original takeaway (verbatim)
The equal/different boundary is the sharpest: "unequal" is silently rewritten to "equal" and
answers with the opposite polarity (F1), while every other "different/not-equal" phrasing fails
(F3); the single most dramatic misroute is "equivalence of f and g" → `find it 10` on `f & g` (F2).
Near-synonym boundaries (max/min vs maxima/minima vs extrema, range vs crit, of-f vs of-expression)
flip the emitted command on small lexical changes, and many correctly-executed requests report
`ok:true` with `statements:[]`/`understood:false`. No crashes or hangs were observed.

### Folder-confirmation
All files were written only under `$ROOT/tests/stress/areas/nlp/nlp_intent_boundaries/`.
No source, Makefile, existing test, `opencode.json`, or other agent's folder was touched; no `make`
or `git` command was run. Helper scripts lived in `/tmp` only.
