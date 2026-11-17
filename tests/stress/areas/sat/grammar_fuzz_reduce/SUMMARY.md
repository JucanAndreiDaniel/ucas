# SUMMARY — `grammar_fuzz_reduce`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 4
- Files created: not recorded

### What was built

- `gen.py` — deterministic, type-directed, bounded-depth generator of well-typed
  ucas functions over `u8/u16/u32/u64`, `i8/i16/i32/i64`, `f32`, `real`.  Operators
  are biased toward hard corners: wide (64-bit) multipliers, masked/variable shifts,
  division and remainder, `match`/table lookups, and `asuint`/`asfloat` bit casts.
  Each case emits a function `f` plus a type-preserving one-point mutant `g`.
- `harness.py` — bounded CLI/MCP runners and an independent Python evaluator of
  the generated AST (machine wrapping, casts, IEEE bit casts, partial ops), used
  as a differential oracle and for fingerprint batteries.
- `reduce.py` — ddmin in two modes: classic chunk-removal over `.ucas` lines, and
  structural AST shrinking (sub-expression replacement) with re-run under `timeout`.
- `corpus.jsonl` — 240 generated cases (480 expressions).  `sweep_cli.jsonl` —
  720 CLI `equiv`/`range`/`wrap` analyses (each under `timeout 15`).
  `sweep_mcp.jsonl` — 12 MCP sessions, 732 JSON-RPC tool calls.
  `anomalies.jsonl` — 31 cross-check hits.  Plus 14 hand-built adversarial
  wide-multiply / variable-shift / f32 cases (all under `timeout 15`).

### Counts

| item | count |
|------|-------|
| generated cases / expressions | 240 / 480 |
| CLI analyses (`equiv`+`range`+`wrap`) | 720 |
| MCP tool calls | 732 (0 errors; 0 CLI-vs-MCP equivalence disagreements) |
| targeted adversarial hard cases | 14 |
| **WRONG** | 3 |
| **CRASH** | 0 |
| **HANG** | 0 |
| **LIMIT** | 3 |
| **DETERMINISM** issues in kept goldens | 0 |

### Files written

`gen.py`, `harness.py`, `reduce.py`, `corpus.jsonl`, `sweep_cli.jsonl`,
`sweep_mcp.jsonl`, `anomalies.jsonl`, `sweep_cli_summary.txt`,
`01_equiv_cast_coercion.ucas/.out`, `02_range_excludes_reachable.ucas/.out`,
`03_equiv_float_sampled.ucas/.out`, `mcp_equiv_cast.jsonl/.out`,
`minimized/` (minimized reproducers + reduction traces),
`FINDINGS.md`, `SUMMARY.md`.  Helpers in `_scratch/` are scratch only.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| LIMIT | 3 | — |

### Issues by severity

1. **WRONG** — `equiv` coerces results to the first function's type, proving
   `u8(x) == i32(x)` on `i8` (`01_equiv_cast_coercion.ucas`, `mcp_equiv_cast.jsonl`).
   Reduced from a 60-node generated expression to 3 statements by `reduce.py`.
2. **WRONG** — sampled `range` excludes reachable corner values while printing a
   sound interval bound that includes them (`02_range_excludes_reachable.ucas`);
   28/240 generated cases hit this.
3. **WRONG** — float `equiv` says "are equal" on a sample where `show` returns
   different values (`03_equiv_float_sampled.ucas`).
4. **LIMIT** — one fingerprint collision (cases 140: `y%14` vs `y%21`) that ucas
   correctly refuted; three SAT-gave-up-but-still-"equal" statements; undefined
   function name silently treated as a free variable.


## Takeaway
The strongest bug is an unsound `equiv` that proves functions with different result types equal by coercing both to the first type; sampled `range` and sampled float `equiv` also report reachable-value-excluding / false "equal" answers, while no crash or hang appeared in 240 deterministic generated cases.

### Original takeaway (verbatim)

The strongest bug is an unsound `equiv` that proves functions with different result
types equal by coercing both to the first type; sampled `range` and sampled float
`equiv` also report reachable-value-excluding / false "equal" answers, while no
crash or hang appeared in 240 deterministic generated cases.

Stayed entirely inside `tests/stress/areas/sat/grammar_fuzz_reduce/`.
