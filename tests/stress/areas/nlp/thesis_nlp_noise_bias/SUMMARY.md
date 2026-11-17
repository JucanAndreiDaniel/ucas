# SUMMARY — `thesis_nlp_noise_bias`

## Counts
- Distinct expressions/queries tried: 455
- Goldens written: 7
- Files created: 16

### Scope
Thesis-derived NLP robustness (PHD_RESEARCH.md "NLP robustness" + items 6–7): graded noise injection,
adversarial paraphrase, bias/name probes, character-level attacks, prompt injection.  Frontends: CLI
plain-English files and MCP `english` (`ucas --mcp`).  All runs bounded by `timeout 30`.

### Counts
- **Distinct English queries tried:** ~455
  - 380 systematic study queries (15 clean queries × 4 noise levels × 4 edit types = 240 noise;
    30 paraphrase; ~70 bias/name; 27 character-level; 20 prompt-injection), each in a fresh MCP process.
  - 15 clean baselines + 8 targeted signedness-typo probes + 12 MCP-golden calls + 53 CLI-golden
    statements + reset/protocol probes.
- **Files created (16):**
  - CLI goldens: `01_noise_silent_misparse`, `02_noise_graceful`, `03_paraphrase`, `04_bias_names`,
    `05_char_attacks`, `06_injection` — each `.ucas` + `.out` (12 files).
  - MCP golden: `mcp_noise_bias.jsonl` + `mcp_noise_bias.out` (2 files).
  - `FINDINGS.md`, `SUMMARY.md` (2 files).
- **Issues by severity:**
  - `WRONG`: 3 (F1 silent function mutation under 1-char noise; F2 parity→show command substitution;
    F3 variable name `i` collides with imaginary unit and fails).
  - `NLP`: 2 (F4 MCP emits invalid-UTF-8 JSON for non-ASCII input; F5 paraphrase non-invariance —
    also tagged LIMIT).
  - `LIMIT`: 3 (F5 paraphrase gap, F6 graded-noise divergence profile, F8 `forget everything` does
    not clear definitions).
  - `CRASH` / `HANG` / `DETERMINISM`: 0.
  - Prompt injection (F7): verified inert / safe — no issue.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| NLP | 2 | — |
| LIMIT | 3 | — |

### Golden determinism
All 7 golden pairs generated twice and `cmp`-identical; every CLI run exited 0.


## Takeaway
The English frontend fails *gracefully* on heavy noise and prompt injection, but a single stray character can silently change the emitted `ucas` command or function (F1/F2), the name `i` is mis-handled (F3), and non-ASCII input breaks the MCP wire encoding (F4) — the "silently changing the parsed `ucas` string" failure mode is real even at 5% noise.

### Original takeaway (verbatim)
The English frontend fails *gracefully* on heavy noise and prompt injection, but a single stray
character can silently change the emitted `ucas` command or function (F1/F2), the name `i` is
mis-handled (F3), and non-ASCII input breaks the MCP wire encoding (F4) — the "silently changing the
parsed `ucas` string" failure mode is real even at 5% noise.
