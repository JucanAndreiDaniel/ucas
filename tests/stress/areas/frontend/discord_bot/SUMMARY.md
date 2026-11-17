# SUMMARY — `discord_bot`

## Counts
- Distinct expressions/queries tried: 350
- Goldens written: 12
- Files created: not recorded

### Coverage

| Category | Count | Where |
|---|---:|---|
| `dc_command()` message-prefix / fence parsing cases | 197 (196 executed; 1 empty line skipped) | `cases/cmd_cases.txt` → `cmd_parse.out` |
| Full-message routing (mentions + greeting strip + parser) | 54 logical messages (62 physical lines) | `cases/route_cases.txt` → `route.out` |
| Follow-up answer-routing replies | 53 | `cases/answer_cases.txt` → `answer_route.out` |
| `english` MCP calls (text + follow-up answers) | 46 | `mcp_en_*.jsonl` → `mcp_en_*.out` |
| CLI defer/ask/follow-up engine scripts | 8 files (~27 statements) | `NN_*.ucas` → `NN_*.out` |
| Engine invocations fuzzed under `timeout 15` | 167 (re-used EVAL bodies) | `harness/fuzz_engine.py` (all exited 0) |

**Distinct message-style inputs tried: ~350** (well above the 150 minimum):
normal queries, ambiguous English, very long messages (20k identifier, 2500-term
expression, 500-deep parens, 400-line script), code blocks / fences (including
`c++`, `c#`, CRLF, unclosed/nested fences), Markdown, mentions (`<@id>`,
`<@!id>`, `@Name#NNNN`, typed names), Unicode/emoji, prompt-injection and
`\x1e` directive injection, rapid repeats (12 identical queries, 8 resets),
and malformed command prefixes.

### Files written

- Harnesses (compile the real `discord/text.c`; verbatim copies of the
  Concord-free helpers from `bot.c`): `harness/dc_harness.c`,
  `harness/answer_harness.c`, `harness/route_harness.c`.
- Generators / drivers: `harness/gen_cases.py`, `harness/gen_answers.py`,
  `harness/gen_route.py`, `harness/gen_cli.py`, `harness/gen_mcp.py`,
  `harness/fuzz_engine.py`, `harness/run.sh` (one-command rebuild+regen).
- Case fixtures: `cases/cmd_cases.txt`, `cases/answer_cases.txt`,
  `cases/route_cases.txt`.
- Unit goldens: `cmd_parse.out`, `answer_route.out`, `route.out`.
- CLI goldens: `01_defer_normal` … `08_reset_like` (`.ucas` + `.out`).
- MCP goldens: `mcp_en_normal`, `mcp_en_ambiguous`, `mcp_en_injection`,
  `mcp_en_long` (`.jsonl` + `.out`).
- `FINDINGS.md`, `SUMMARY.md`, plus `scratch/` exploratory scripts.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | leading - stripped → negative inputs become positive (Finding 1) |
| NLP | 3 | follow-up routing swallows new commands (2); c# tag leak (3); nested fence (4) |
| LIMIT | 2 | cannot build/run ucas-discord (5); per-channel state shared across users (6) |

### Issues by severity

| Severity | Count | Headline |
|---|---:|---|
| CRASH | 0 | — |
| HANG | 0 | — |
| WRONG | 1 | leading `-` stripped → negative inputs become positive (Finding 1) |
| NLP | 3 | follow-up routing swallows new commands (2); `c#` tag leak (3); nested fence (4) |
| LIMIT | 2 | cannot build/run `ucas-discord` (5); per-channel state shared across users (6) |
| DETERMINISM | 0 | all goldens byte-identical across two runs |


## Takeaway
The engine invocation path itself is robust (0 crashes, 0 hangs, deterministic, injection directives inert), but the bot's own text preprocessing silently deletes leading minus signs and its follow-up classifier swallows several new commands (including `reset`) as answers — both are easy to trigger with an ordinary addressed message.

### Original takeaway (verbatim)

The engine invocation path itself is robust (0 crashes, 0 hangs, deterministic,
injection directives inert), but the bot's own text preprocessing silently
deletes leading minus signs and its follow-up classifier swallows several new
commands (including `reset`) as answers — both are easy to trigger with an
ordinary addressed message.
