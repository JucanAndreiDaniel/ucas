# SUMMARY — `nlp_multilingual`

## Counts
- Distinct expressions/queries tried: 207
- Goldens written: 3
- Files created: 8

### Counts

- **Distinct queries tried:** ~207 (Spanish, French, German, Chinese, Japanese, Russian,
  Hindi, Arabic/Hebrew RTL, code-switching, Latin abbreviations, archaic/formal, pidgin/simple,
  foreign number words, Greek letters, math symbols, emoji/malformed/edge inputs).
- **Modes used:** MCP `english` tool (via Code Mode and via `--mcp` JSONL), CLI interactive
  English (stdin and `.ucas` files), `defaults:true` vs default ambiguous-error path.
- **Files created (8):**
  - `01_graceful.ucas` + `01_graceful.out` — CLI golden, 14 statements, correctly-parsed and
    gracefully-refused multilingual inputs.
  - `02_silent_misparse.ucas` + `02_silent_misparse.out` — CLI golden, 10 statements, the
    silent-wrong-statement reproducers.
  - `mcp_multilingual.jsonl` + `mcp_multilingual.out` — MCP golden, 22 `english` calls across
    every required category (satisfies the "at least one `mcp_*.jsonl` golden" requirement).
  - `FINDINGS.md`, `SUMMARY.md`.
- **Determinism:** all three goldens verified byte-identical over 3 consecutive runs; the MCP
  golden additionally over 100 serial + 30 concurrent runs. The one divergent (empty-capture)
  run is documented in FINDINGS DETERMINISM-1 and deliberately NOT kept as a golden.

### Scope confirmation

All files were created only under `tests/stress/areas/nlp/nlp_multilingual/`. No source files, Makefile,
existing tests, or `opencode.json` were modified; no `make`, `git`, or unbound process was used.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | NLP-1, NLP-2, NLP-3 |
| NLP | 3 | NLP-1, NLP-2, NLP-3 |
| LIMIT | 4 | NLP-4, LIMIT-1, LIMIT-2, LIMIT-3 |
| DETERMINISM | 1 | DETERMINISM-1 |

### Issues by severity

| Severity | Count | IDs |
|---|---|---|
| WRONG / NLP | 3 | NLP-1, NLP-2, NLP-3 |
| LIMIT | 4 | NLP-4, LIMIT-1, LIMIT-2, LIMIT-3 |
| DETERMINISM | 1 | DETERMINISM-1 |
| CRASH | 0 | — |
| HANG | 0 | — |


## Takeaway
The frontend refuses most genuinely foreign input gracefully (not-understood / parse-error / ambiguous), but when a request's first token is not a known English keyword it silently degrades into a bare expression and emits a **wrong definition with `ok:true` and `understood:false`** — the core "never silently emit a wrong statement" failure — while a single rare MCP run was observed dropping every successful answer entirely.

### Original takeaway (verbatim)

The frontend refuses most genuinely foreign input gracefully (not-understood / parse-error /
ambiguous), but when a request's first token is not a known English keyword it silently degrades
into a bare expression and emits a **wrong definition with `ok:true` and `understood:false`** —
the core "never silently emit a wrong statement" failure — while a single rare MCP run was
observed dropping every successful answer entirely.
