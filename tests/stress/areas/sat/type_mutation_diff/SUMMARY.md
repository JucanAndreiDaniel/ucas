# SUMMARY — `type_mutation_diff`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 7
- Files created: not recorded

### Original preamble

Type-aware operator mutation + differential testing across ucas proof paths and frontends.

### Scale
- Seed functions: 61 well-typed seeds (arity 1–3) over 7 operator-mutation families
  (`+↔-`, `&↔|`, `xor↔+`, `<↔<=`, `*↔mod`, `>>↔<<`, `min↔max`), each mutated once.
- Widths exercised: `u4`, `u8`, `u32`, `i32` (plus `u64`/`i64` in the crash pass).
- Distinct `equiv` requests run: **~430** across campaigns, frontend replication,
  near-identity soundness, malformed inputs, crash pass, and goldens (~244 in the
  main width sweep alone: 61 seeds × 4 widths).
- Frontend evaluations: 48 logical requests × 4 frontends (CLI / `--json` /
  grouped MCP / `--flat` MCP) = 192, plus malformed cases × 3 structured frontends.
- No run exceeded its `timeout` (15–180 s); no nonzero exits or truncated JSON.

### Files written (in this folder only)
- 7 CLI goldens: `01_addsub_mut` … `07_minmax_mut` (`.ucas` + `.out`).
- 1 `--json` golden: `json_mutant_diff.jsonl` + `.out` (15 mutations).
- 2 MCP goldens: `mcp_grouped_mut.jsonl` + `.out`; `mcp_flat_mut.jsonl` + `.out`
  + `mcp_flat_mut.flags` (`--flat`).
- 2 bug reproducer inputs: `bug_zeroparam_fresh.jsonl`, `bug_zeroparam_stale.jsonl`
  (no `.out` — they capture an error and a wrong answer, documented in FINDINGS.md).
- `FINDINGS.md`, `SUMMARY.md`.
- Every golden verified deterministic by running twice and diffing (all identical).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| NLP | 1 | — |
| LIMIT | 2 | — |

### Issues by severity
- **WRONG: 1** — zero-param inline `equiv` in a multi-request JSON/MCP session reuses
  stale auto-names `it`/`that` and returns `equal:false` with a fabricated
  counterexample for a self-comparison (repro: `bug_zeroparam_stale.jsonl`).
- **NLP: 1** (with a DETERMINISM aspect) — the same zero-param request gives an
  `ambiguous` error in a fresh structured session, a `parse_error` with `defaults`,
  a different error in plain CLI, and succeeds after prior session state
  (repro: `bug_zeroparam_fresh.jsonl`).
- **LIMIT: 2** — vacuous `equal:true`/"exhaustive proof" on an empty domain
  (`x/(y-y)`); context-sensitive `^` reading visible only in `notes`.
- **CRASH / HANG: 0.**


## Takeaway
Proof paths and frontends agree on well-typed single-operator mutants; the real unsoundness is at the session/auto-naming boundary — zero-parameter inline functions injected by JSON/MCP can silently compare stale functions and return a fabricated refutation of a self-equivalence.

### Original takeaway (verbatim)
Proof paths and frontends agree on well-typed single-operator mutants; the real
unsoundness is at the session/auto-naming boundary — zero-parameter inline
functions injected by JSON/MCP can silently compare stale functions and return a
fabricated refutation of a self-equivalence.
