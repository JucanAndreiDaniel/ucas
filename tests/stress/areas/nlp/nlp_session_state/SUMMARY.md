# SUMMARY — `nlp_session_state`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 13
- Files created: 29

### What was tried

Multi-turn English state: definitions, `let`/`call it X` aliases, redefinition,
`assume`/`forget`/`forget everything`, pronouns ("its range", "what is f when x
is 3"), context carry-over of the `it` function, variables and byte/int type
assumptions, mixed raw-`ucas` + English lines, session `define`/`assume`/`reset`/
`state`/`schema` via MCP (including `--flat`), and repeated `initialize`.

Counts:
- Distinct query/statement/JSON-RPC-call instances: **172**
  - CLI `.ucas`: **119** across 8 files
  - MCP calls (excluding `initialize`/`notifications/initialized`): **53** across 5 JSONL sessions
- Files created: **29**
  - 8 `.ucas` + 8 `.out` (CLI goldens)
  - 5 `.jsonl` + 5 `.out` (MCP goldens; one uses a `.flags` with `--flat`)
  - 1 `.flags`, `FINDINGS.md`, `SUMMARY.md`
- All runners bounded with `timeout` (15 s CLI, 20–30 s MCP); every exit code 0.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 5 | two separate assumption stores (English vs session assume): invisible to state, assume clear and forget everything fail to clear, stale Engl |
| NLP | 2 | pronoun its resolves to last-defined function instead of the one just named; misleading "I didn't follow 'of 3'" after reset |
| LIMIT | 1 | reserved words (square, it, range) cannot be user-defined; malformed assume values / invalid op strings weakly validated |

### Issues by severity

| Severity | Count | Summary |
|---|---|---|
| `CRASH` | 0 | none |
| `HANG` | 0 | none |
| `DETERMINISM` | 0 | all 13 goldens bit-identical on rerun |
| `WRONG` | 5 | two separate assumption stores (English vs `session assume`): invisible to `state`, `assume clear` and `forget everything` fail to clear, stale English meaning overrides a newer JSON assumption; second `initialize` leaks state across sessions |
| `NLP` | 2 | pronoun `its` resolves to last-defined function instead of the one just named; misleading "I didn't follow 'of 3'" after `reset` |
| `LIMIT` | 1 | reserved words (`square`, `it`, `range`) cannot be user-defined; malformed `assume` values / invalid op strings weakly validated |

See `FINDINGS.md` for exact repro commands and observed output for each.


## Takeaway
The English and JSON session-state paths maintain two independent assumption stores whose `clear`/`forget`/`state`/precedence disagree, pronouns bind to the most recent *definition* rather than the most recent *referent*, and a second `initialize` does not reset a process — so multi-turn English state is silently wrong well before it ever crashes.

### Original takeaway (verbatim)

The English and JSON session-state paths maintain two independent assumption
stores whose `clear`/`forget`/`state`/precedence disagree, pronouns bind to the
most recent *definition* rather than the most recent *referent*, and a second
`initialize` does not reset a process — so multi-turn English state is
silently wrong well before it ever crashes.
