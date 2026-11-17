# SUMMARY — `self_reference_state`

## Counts
- Distinct expressions/queries tried: 299
- Goldens written: 19
- Files created: not recorded

### Coverage

- **Distinct cases tried:** 299
  - 159 CLI statements across 15 `.ucas` goldens (self-ref definitions typed/bare, mutual
    cycles, `show` of undefined names, auto-names `_`/`_0`/`it`/`that`, redefinitions,
    `where`-cycles, English builtin shadowing / junk / assumptions, reset/forget).
  - 140 MCP tool calls across 4 `.jsonl` goldens (adversarial `assume` values, English state
    mutation + `funcs`/`state` checks, structured `session define` cycles, auto-name state).
- **Goldens written:** 19 (`01`–`15` `.ucas` + 4 `mcp_*.jsonl`, each with a matching `.out`).
- **Docs:** `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | F1 (English shadows builtins; funcs/show vs evaluation disagree), F2 (show of undefined name installs a stray _ def hidden from introspectio |
| NLP | 2 | F1 (English as arbitrary-ucas emitter), F7 (junk phrases emit def-shaped artifacts; forget cannot undo English definitions) |
| LIMIT | 5 | F3 (undefined RHS becomes a function), F4 (self-ref redefinition drops signature), F5 (cyclic "assume means" unreachable in NLP), F6 (advers |

### Process / determinism

- Every case bounded with `timeout` (15 s CLI probes, 30 s golden generation).
- All 19 goldens run twice and diffed: **all deterministic**, all `rc=0`. No crash, hang, signal,
  or truncated JSON was observed, so no case was excluded from goldens for nondeterminism.

### Issues by severity

| Severity | Count | Ids |
|---|---|---|
| CRASH | 0 | — |
| HANG | 0 | — |
| WRONG | 2 | F1 (English shadows builtins; `funcs`/`show` vs evaluation disagree), F2 (`show` of undefined name installs a stray `_` def hidden from introspection) |
| NLP | 2 | F1 (English as arbitrary-ucas emitter), F7 (junk phrases emit def-shaped artifacts; `forget` cannot undo English definitions) |
| LIMIT | 5 | F3 (undefined RHS becomes a function), F4 (self-ref redefinition drops signature), F5 (cyclic "assume means" unreachable in NLP), F6 (adversarial assume values validated cleanly — non-bug), F7 (CLI `reset` is not a command) |
| DETERMINISM | 0 | — |


## Takeaway
The self-referential core is **resilient** — cycles are rejected at define time with no hang and no partial commit — but the **English/NLP boundary mutates state**: `define sin of x as 1000` shadows a builtin that `forget` cannot remove, and merely `show`ing an undefined name silently installs a hidden `_` definition that `funcs`/`state` do not report.

### Original takeaway (verbatim)

The self-referential core is **resilient** — cycles are rejected at define time with no hang and
no partial commit — but the **English/NLP boundary mutates state**: `define sin of x as 1000`
shadows a builtin that `forget` cannot remove, and merely `show`ing an undefined name silently
installs a hidden `_` definition that `funcs`/`state` do not report.
