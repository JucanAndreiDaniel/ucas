# SUMMARY — `english_redos`

## Counts
- Distinct expressions/queries tried: 202
- Goldens written: 9
- Files created: 27

### Scope
Pathological English input shapes against both frontends: CLI English (piped
`.ucas` / stdin) and the MCP `english` tool (`--mcp`), each bounded by
`timeout 15`.

### Counts
- **Distinct queries generated and tried: 202** (see `measurements.tsv`, 202
  CLI rows), covering: repeated `a of`/`of` phrases, repeated `not`, long
  `and`/`or` chains, nested `the range of`, repeated `what is`, alternating
  synonyms (odd/even, and/or, sign), number-word chains, repeated `where`/`for`
  clauses, repeated ambiguity words (odd/sign/range), near-cap and over-cap
  inputs.
- **MCP calls: 23** (subset of the same texts, plus word-cap and hang
  reproducers). Total measured invocations ≈ 225.
- Additional fine-grained scaling probes: 6 scripts / ~150 timed runs
  (nested-depth curves 1–30, cap threshold 312–321, CLI-vs-MCP comparisons).
- **Files created: 27**
  - 9 CLI goldens: `01_repeat_phrase` … `09_ambiguity_words` (`.ucas` + `.out`)
  - 3 MCP goldens: `mcp_redos_shapes`, `mcp_ambiguity_repeat`,
    `mcp_word_cap` (`.jsonl` + `.out`)
  - `measurements.tsv`, `FINDINGS.md`, `SUMMARY.md`
- Every golden was generated twice and `diff`-verified identical.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| NLP | 2 | MCP reports only the first ambiguity in a multi-trigger sentence; alternating odd/even demotes even to a stray variable |
| LIMIT | 1 | Hard 320-token sentence cap; flat repetition rejected fast, but does not cover the hang |

### Issues by severity
| Severity | Count | Headline |
|---|---|---|
| HANG | 1 (4 CLI reproducers + MCP) | Exponential NLP parse for nested "the sqrt of / log of / inverse of / square root of / sign of": 61-word input times out at 15 s (~2^n) |
| LIMIT | 1 | Hard 320-token sentence cap; flat repetition rejected fast, but does not cover the hang |
| NLP | 2 | MCP reports only the first ambiguity in a multi-trigger sentence; alternating odd/even demotes `even` to a stray variable |
| CRASH | 0 | — |
| WRONG | 0 (beyond the NLP misparses above) | — |
| DETERMINISM | 0 | — |


## Takeaway
Flat English repetition and the 320-word cap are harmless and linear, but repeated *compositional* phrases ("the sqrt of the sqrt of ...") trigger an exponential (~2^n) NLP parse that hangs at just 61 words in both CLI and MCP — a genuine ReDoS-class denial of service.

### Original takeaway (verbatim)
Flat English repetition and the 320-word cap are harmless and linear, but
repeated *compositional* phrases ("the sqrt of the sqrt of ...") trigger an
exponential (~2^n) NLP parse that hangs at just 61 words in both CLI and MCP —
a genuine ReDoS-class denial of service.

### Folder confinement
All files live only in `tests/stress/areas/nlp/english_redos/`; no source, build, shared
or other subagent file was touched. All runs were bounded with `timeout`.
