# SUMMARY — `cli_args_fuzz`

## Counts
- Distinct expressions/queries tried: 162
- Goldens written: 10
- Files created: 10

### Scope
The command-line interface of `$ROOT/ucas`: flag parsing and
ordering, repeated/unknown/abbreviated/combined flags, `--` separator, stdin
vs `-e`, file-argument errors (missing / directory / unreadable / multiple /
Unicode / spaces), huge and control-character `-e` values, and the `--json`,
`--mcp`, `--flat`, `--dir`, `--files`, `--json-schema` and `--sat-selftest`
sub-modes.

### Counts
- Distinct invocations tried: **162** (10 golden scripts, `cli_01`..`cli_10`).
- Runs: every candidate run under `timeout 15`; every golden executed twice
  and diffed (all 10 goldens deterministic). `--sat-selftest` additionally
  timed over 10 runs under `timeout 30` to characterise its runtime.
- Files written: 10 `cli_NN_*.py` reproducers, 10 `cli_NN_*.out` goldens,
  `_probe.py` helper, `run_cli.py` runner, fixtures in `fixtures/`,
  `longline.txt`, `midlongline.txt`, `FINDINGS.md` and `SUMMARY.md`.

### Format note
Suite goldens are `.ucas`/`.jsonl` inputs with a matching `.out`, and `areas/`
helpers are Python only (see `SPEC.md`). The `bmake stress-test` target
auto-discovers only `.ucas` and `.jsonl` goldens, which cannot express CLI
invocations (flags, pipes, multiple argv). This folder therefore keeps those
invocations as Python reproducers: each `cli_NN_*.py` uses `_probe.py` to print
a stable `exit=N` + merged stdout/stderr report, driven by `run_cli.py`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | — |
| LIMIT | 4 | — |
| DETERMINISM | 1 | — |

### Issues by severity
- CRASH: 0
- HANG: 0 (one apparent hang was `--sat-selftest`'s slow, variable runtime)
- WRONG: 4 — (1) stdin lines >8191 bytes silently split into multiple
  statements; (2) `--json` repeated `-e` serves only the last request;
  (3) statement/request failures all exit 0; (4) a directory argument is
  silently treated as empty input.
- NLP: 0 (non-ASCII identifiers produce a parser error but that is outside
  this area's scope)
- LIMIT: 4 — unknown `--files` mode silently becomes `write`; no getopt so
  `--`/abbreviations/combined flags/`=` forms are file names; early-return
  flags discard later argv; `UCAS_MCP_PROTO` overridden at initialize.
- DETERMINISM: 1 — `--sat-selftest` takes 7.8–14.1 s (flaky under
  `timeout 15`); no golden kept, documented in FINDINGS.md only.


## Takeaway
The CLI parses argv with a hand-rolled sequential loop and a fixed 8192-byte REPL line buffer: it never crashes, but it silently splits long stdin input, drops repeated `--json -e` requests and post-early-return flags, accepts directories and bad `--files` values without complaint, and reports success (exit 0) even when evaluation or a request fails.

### Original takeaway (verbatim)
The CLI parses argv with a hand-rolled sequential loop and a fixed 8192-byte
REPL line buffer: it never crashes, but it silently splits long stdin input,
drops repeated `--json -e` requests and post-early-return flags, accepts
directories and bad `--files` values without complaint, and reports success
(exit 0) even when evaluation or a request fails.
