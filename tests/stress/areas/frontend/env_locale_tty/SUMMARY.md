# SUMMARY — `env_locale_tty`

## Counts
- Distinct expressions/queries tried: 110
- Goldens written: 5
- Files created: not recorded

### Coverage
- **Distinct expressions / English queries tried:** ≈110 (55 in durable goldens: 14 numeric,
  10 error/Unicode, 11 type/range, 8 algebra, 8 NLP, 4 MCP; ≈55 more in exploratory probes
  covering malformed UTF-8, NFC/NFD, Greek/math Unicode, locales, TTY modes, and file writes).
- **Bounded runs executed:** 171 durable matrix runs (`run_env_matrix.sh`) + ≈50 exploratory
  runs = **220+**, every one under `timeout`, all exit 0.
- **Environment matrix:** 28 configs × (5 CLI goldens + 1 MCP golden), covering
  `LANG`/`LC_ALL`/`LC_NUMERIC`/`LC_CTYPE`/`LANGUAGE` (C, C.UTF-8, en_US.UTF-8,
  ro_RO.UTF-8 comma-decimal, POSIX, invalid `xx_XX.INVALID`), `UCAS`, `UCAS_BIN`,
  `UCAS_SPIRV_CROSS`, `UCAS_CC`, `UCAS_SEED`, `UCAS_NO_TIMES`, `PATH`, `TMPDIR`, `HOME`
  (bogus and unset), and `TERM` (dumb, empty, xterm-256color, vt100, bogus, unset).

### Files created (in this folder only)
- `01_numbers.ucas` / `.out`, `02_errors.ucas` / `.out`, `03_types_ranges.ucas` / `.out`,
  `04_algebra.ucas` / `.out`, `05_nlp.ucas` / `.out`
- `mcp_env.jsonl` / `mcp_env.out`
- `run_env_matrix.sh` — the durable 171-run matrix + TTY/file-location/determinism probes
- `FINDINGS.md`, `SUMMARY.md`


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| NLP | 1 | F4 English-mode Unicode mapping inconsistent with expression mode / locale-invariant |
| LIMIT | 3 | F1 TTY-vs-pipe output differs; F2 stdin-tty/stdout-file half-interactive state; F3 non-ASCII rejected as '?', no normalization |

### Issues by severity
| severity | count | items |
|----------|-------|-------|
| CRASH    | 0 | — |
| HANG     | 0 | — |
| WRONG    | 0 | — |
| DETERMINISM | 0 | all goldens byte-identical across matrix and across repeat runs |
| LIMIT    | 3 | F1 TTY-vs-pipe output differs; F2 stdin-tty/stdout-file half-interactive state; F3 non-ASCII rejected as `'?'`, no normalization |
| NLP      | 1 | F4 English-mode Unicode mapping inconsistent with expression mode / locale-invariant |

No golden was added for a nondeterministic or hanging case; all 6 goldens pass the standard
runner (`ucas NAME.ucas` / `ucas --mcp < NAME.jsonl`) with 0 diffs.


## Takeaway
ucas is robust to environment/locale/terminal variation — no crashes, hangs, or wrong answers, and numeric output is byte-identical even in a comma-decimal locale because `setlocale` is never called — the only environment-dependent behaviour is the by-design TTY prompt/ambiguity dialogue (plus its half-interactive corner) and an inconsistent Unicode policy between the English and expression frontends.

### Original takeaway (verbatim)
ucas is robust to environment/locale/terminal variation — no crashes, hangs, or wrong
answers, and numeric output is byte-identical even in a comma-decimal locale because
`setlocale` is never called — the only environment-dependent behaviour is the by-design
TTY prompt/ambiguity dialogue (plus its half-interactive corner) and an inconsistent
Unicode policy between the English and expression frontends.
