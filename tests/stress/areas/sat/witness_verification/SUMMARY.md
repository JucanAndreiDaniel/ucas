# SUMMARY — `witness_verification`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 8
- Files created: not recorded

### Coverage
- **Distinct queries/cases tried:** 222 per seed × 2 seeds (seeds `0xC0FFEE` and
  `0xBADF00D`) = **444 case-runs**, each with many brute-forced domain points.
  Breakdown per seed: 22 `equiv` true identities, 24 random `equiv` pairs,
  8 wrap-failing `equiv`, 48 `wrap` (36 random + 12 guaranteed overflow),
  30 `domain`, 34 `crit` (28 random + 6 curated), 32 `range` (26 random +
  6 curated), 16 `error`, 8 `fit`.
- Types: u4, u8, i8 (plus i16 in the evaluator validation set).
- Witnesses verified: differ counterexamples (with both values), wrap
  end-to-end / nuw / nsw witnesses, domain undefined points, crit local extrema,
  range min/max and reachable-value sets, error/fit worst points.
- Global soundness checks: brute-force confirmation of `equal`, differ counts,
  wrap counts, undefined counts, distinct-value counts and min/max.

### Result of independent verification
- **0 wrong/fabricated witnesses, 0 false `equal`, 0 missing extrema** in the
  CLI witness machinery across all 444 case-runs. Reports:
  `verify_report.txt` (default seed) and `verify_report_seed2.txt`.

### Files created
- `expr_eval.py` — bit-accurate ucas expression parser/evaluator (0 mismatches
  vs `table` over 10,336 points).
- `verify_witnesses.py` — 222-case generator + independent verifier.
- `make_goldens.py` — golden generator with determinism checks.
- `verify_report.txt`, `verify_report_seed2.txt` — full per-case evidence.
- CLI goldens: `01_equiv_counter` … `08_fit_worst` (`.ucas` + `.out`).
- MCP golden: `mcp_witnesses.jsonl` + `mcp_witnesses.out` (6 tool calls, all ok).
- `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 1 | — |

### Issues found (see FINDINGS.md)
- `LIMIT` ×1 — MCP `analyze/equiv` with expression strings, including the example
  call, returns a low-level parse error.
- `WRONG` ×1 — MCP `session/define` calls without a JSON-RPC `id` silently fail
  to register a definition (subsequent `funcs` empty, `equiv` fails).
- `WRONG` ×1 — constant-folded values are not reduced to the declared machine
  type when added to a comparison operand: `f(x: u4) = ((13*14) xor (4*15)) +
  (x==4)` has `table`/`range` values 138..139 (outside u4).

### Determinism
All 8 CLI goldens and the MCP golden were each run twice and `diff`-identical.
No nondeterministic golden was kept.


## Takeaway
The CLI witness machinery is sound on small machine types under independent brute-force verification; the real problems are in MCP session/argument handling and in constant-folding of large constants combined with boolean operands.

### Original takeaway (verbatim)
The CLI witness machinery is sound on small machine types under independent
brute-force verification; the real problems are in MCP session/argument handling
and in constant-folding of large constants combined with boolean operands.

Confirmed: all work stayed inside `tests/stress/areas/sat/witness_verification/`.
