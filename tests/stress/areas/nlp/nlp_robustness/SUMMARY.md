# SUMMARY — `nlp_robustness`

## Counts
- Distinct expressions/queries tried: 354
- Goldens written: 7
- Files created: not recorded

### Coverage
- **Distinct queries tried: 354**
  - 229 curated English queries (heavy misspellings, broken grammar, word salad,
    unsupported requests, mixed ucas-in-English, empty/whitespace, single characters,
    long inputs, Unicode/emoji, punctuation-only, repeated words, nested questions,
    AI instructions, prompt injection), via CLI `-e`.
  - 125 fuzzed ASCII/punctuation garbage queries (random seed 1234, plus structured
    hostility: 500/2000 nested parens, 500-term sums, 30×46-digit numbers), via CLI `-e`.
  - Long-input probes: 2403-word / 1406-word word salad, 3000-letter single word,
    and 200–1000-word staircase to locate the sentence-length guard.
  - MCP `english` tool exercised for all the interesting categories, both normal MCP
    mode and `--flat` mode.
- All runs bounded by `timeout 15` (golden generation `timeout 30`). **Exit code 0 in
  every case — no crashes, hangs, signals, or truncated JSON observed.**

### Files created (in this folder only)
- `01_english_ok.ucas` + `.out` — well-formed English routing (CLI golden)
- `02_garbage_sorry.ucas` + `.out` — garbage that yields "sorry" (CLI golden)
- `03_injection.ucas` + `.out` — prompt-injection / imperative garbage (CLI golden)
- `04_edges.ucas` + `.out` — single chars, punctuation, Unicode/emoji, `{}`, long word (CLI golden)
- `05_long_input.ucas` + `.out` — 603-word word salad hitting the length guard (CLI golden)
- `mcp_english_robustness.jsonl` + `.out` — MCP `english` golden (includes misroute, silent injection, ambiguous error, bare `?`)
- `mcp_english_flat.jsonl` + `.out` + `.flags` (`--flat`) — flat-mode MCP `english` golden
- `FINDINGS.md`, `SUMMARY.md`

All 7 `.out` goldens were generated from their own directory and verified byte-identical
across 2 runs; several individual queries were md5-checked across 3 runs. No nondeterministic
output was found, so no noisy golden was kept.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| NLP | 6 | — |
| LIMIT | 2 | — |

### Issues by severity
- **CRASH: 0**
- **HANG: 0**
- **WRONG: 1** (F2 — "and" → bitwise `&` giving empty range, plus CLI/MCP type-inference disagreement)
- **NLP: 6** (F1 misrouted equality question → `equiv`; F2 conjunction misread; F3 `0/0`
  accepted silently; F4 injection/imp imperative garbage → junk math with no "sorry";
  F5 "anything" autocorrected to "nothing"; F6 bare `?`/comment-injection silent no-ops;
  F8 `{}` → bare `undefined`)
- **LIMIT: 2** (F7 sentence-length cap / 31-char word truncation; F3 division-by-zero no diagnostic)
- **DETERMINISM: 0** (all kept goldens stable)

Counting distinct findings: **8** (F1–F8), none of which are crashes or hangs.


## Takeaway
The English frontend is remarkably robust mechanically — 354 adversarial queries produced no crash, hang, or nondeterminism — but it fails *semantically* by silently turning unsupported/prompt-injection input into plausible junk math, misrouting "are x and y equal?" into an `equiv` check, and misreading conjunctions as bitwise operators; these silent defaults, not crashes, are the real robustness risk.

### Original takeaway (verbatim)
The English frontend is remarkably robust mechanically — 354 adversarial queries produced
no crash, hang, or nondeterminism — but it fails *semantically* by silently turning
unsupported/prompt-injection input into plausible junk math, misrouting "are x and y equal?"
into an `equiv` check, and misreading conjunctions as bitwise operators; these silent
defaults, not crashes, are the real robustness risk.
