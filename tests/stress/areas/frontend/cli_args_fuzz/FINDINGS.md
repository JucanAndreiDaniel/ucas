# Stress findings — `cli_args_fuzz`

_Original heading: FINDINGS — `cli_args_fuzz`_

# FINDINGS — `cli_args_fuzz`

Area: the `ucas` command-line interface itself (argument parsing, flags,
stdin vs `-e`, file arguments, sub-mode flags). Binary:
`$ROOT/ucas`. 162 distinct invocations were run, all under
`timeout 15` (except a dedicated timing study for `--sat-selftest`, bounded at
`timeout 30`). Every would-be golden was executed twice and diffed; only
deterministic invocations were kept as `.out` goldens.

Golden format: each `cli_NN_*.py` is a self-contained reproducer that imports
`probe` from `_probe.py`. `probe LABEL 'command'` expands shell variables, runs
the command under `sh -c` with a 15-second subprocess timeout, then prints
`exit=N` and the merged stdout+stderr. `cli_NN_*.out` is the golden. Run all of
them with `python3 run_cli.py` (the `bmake stress-test` target only
discovers `.ucas` and `.jsonl` goldens, which cannot express flags/stdin/pipes).

No crashes, signals, or true hangs were found. The findings below are wrong
results, silently ignored flags, and non-deterministic runtime.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | REPL silently splits stdin lines longer than 8191 bytes |
| LIMIT | 4 | unrecognized `--files` mode silently defaults to `write` |
| DETERMINISM | 1 | `--sat-selftest` is slow with a variable runtime |

## Findings

### WRONG-1 — REPL silently splits stdin lines longer than 8191 bytes
**Severity:** WRONG
`repl()` uses a fixed `char line[8192]` and runs `run_text` on each `fgets`
chunk when bracket depth is 0. A single long statement with no brackets is
therefore executed as two (or more) separate statements, silently producing
wrong values with exit 0 and no diagnostic.

**Reproducer:**
Reproducer (copy-pasteable):

**Observed:**
```sh
python3 -c 'import sys; sys.stdout.write("1+"*5000+"1")' | $ROOT/ucas
```

**Expected:** a single value `5001`. Observed:

```
4096
905
```

Golden: `cli_08_stdin.out` ("stdin: 10001-char line (SPLIT bug)"). A
4001-term line (8001 chars, fits the buffer) correctly prints `4001`,
confirming the 8192-byte cutoff is the cause.

**Why it matters:** input is silently corrupted rather than rejected; the exit
status is 0 and there is no warning. A script piped to the CLI can compute the
wrong answer.

### WRONG-2 — `--json` with repeated `-e` serves only the last request
**Severity:** WRONG
**Expected:** _not recorded_
`json_main` stores the one-shot request in a single `one` variable that is
overwritten on every `-e`, so all but the final `-e` are silently discarded.

**Reproducer:**

```sh
$ROOT/ucas --json \
  -e '{"id":1,"cmd":"parse","args":{"expr":"1"}}' \
  -e '{"id":2,"cmd":"parse","args":{"expr":"9"}}' </dev/null
```

**Observed:** (only `id:2`, the first request produced no output at all):

```
{"id": 2, "ok": true, "cmd": "parse", "ucas": "parse 9", "structured": false, "result": {"text": "9\n"}, "notes": [], "conditions": [], "checks": [], "files": [], "text": "9\n"}
```

Golden: `cli_05_json.out` ("json: repeated -e (only last served)") and
`cli_09_misc.out` ("misc: --json triple -e (only last)").

**Why it matters:** a silently ignored flag/argument. A caller batching several
one-shot requests gets no response for the first N-1 and no error to signal
the loss.

### WRONG-3 — statement-level errors and failed requests all return exit 0
**Severity:** WRONG
Only file-open failures (exit 1) and flag/usage failures (exit 2) are
nonzero. A syntax error in a `-e`, a file, or stdin, and a `--json` request
that returns `ok:false`, all exit 0.

Reproducers and observed output (golden `cli_10_exit.out`):

**Observed:**
**Reproducer:**
```sh
$ROOT/ucas -e '1+' ; echo $?      # prints error, exit=0
# <arg>:1:3: error: expected an expression
#     1+
#       ^

$ROOT/ucas fixtures/bad.ucas ; echo $?   # exit=0
printf '1+\n' | $ROOT/ucas ; echo $?     # exit=0

$ROOT/ucas --json -e 'garbage' </dev/null ; echo $?  # exit=0
# {"id": null, "ok": false, "cmd": null, "error": {"code": "bad_json", "message": "unexpected character at byte 0"}}
```

**Expected:** a nonzero exit so shell pipelines/scripts can detect failed
evaluation.
**Why it matters:** automation cannot distinguish success from a
parse/request failure via exit status.

### WRONG-4 — a directory argument is silently accepted as empty input
**Severity:** WRONG
**Why it matters:** _not recorded_
`fopen(dir, "r")` succeeds on Linux; `fread` yields nothing, so `run_text`
gets an empty string and the command exits 0 with no output and no error.

**Reproducer:**

```sh
$ROOT/ucas fixtures/a_directory ; echo $?
```

**Observed:** `exit=0`, no stdout/stderr. Golden: `cli_04_files.out` ("file:
directory is silently empty", and "file: two directories").

**Expected:** an error such as `a_directory: Is a directory` and a nonzero exit,
matching the behavior for a nonexistent/unreadable file.

### DETERMINISM-1 — `--sat-selftest` is slow with a variable runtime
**Severity:** DETERMINISM
_Original classification: `DETERMINISM / LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The output text is stable (`sat selftest: ok`, exit 0), but the wall-clock
time varied from 7.8 s to 14.1 s across 10 consecutive runs:

**Observed:**
```
run 1: exit=0  14.12s   run 6: exit=0  9.57s
run 2: exit=0  13.42s   run 7: exit=0  9.21s
run 3: exit=0  12.29s   run 8: exit=0  8.90s
run 4: exit=0  8.47s    run 9: exit=0  9.39s
run 5: exit=0  7.83s    run 10: exit=0 14.05s
```

Consequently `timeout 8 ... --sat-selftest` returns 124 (killed), and even
the standard `timeout 15` is occasionally flaky. It also short-
circuits any following flags (`--sat-selftest --json` never reaches `--json`).

**Reproducer:**

```sh
timeout 8 $ROOT/ucas --sat-selftest ; echo $?   # 124
```

No golden `.out` is kept for `--sat-selftest` because of the variable runtime
and timeout flakiness; it is documented here only.

### LIMIT-1 — unrecognized `--files` mode silently defaults to `write`
**Severity:** LIMIT
**Why it matters:** _not recorded_
`json_main` maps any unrecognized `--files` value to `REP_FILES_WRITE`
instead of reporting a usage error.

**Reproducer:**

```sh
$ROOT/ucas --json --files bogus \
  -e '{"id":1,"cmd":"parse","args":{"expr":"1+2*3"}}' </dev/null
```

**Observed:** a normal successful response (no warning), exit 0. Golden:
`cli_05_json.out` ("json: --files bogus -e (default write)") and
`cli_09_misc.out` ("misc: --files none w/ newline value", where the value
`none\nfoo` is likewise accepted as `write`).

**Expected:** reject an invalid enum value like an unknown flag does (exit 2).

### LIMIT-2 — no getopt: `--` separator, abbreviations, combined flags, `=` forms
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
There is no getopt layer. Anything not exactly one of the known flag strings
is treated as a file name. In particular `--`, `--js`, `--sat`, `-qe`, `-eq`,
`-e=1+1`, `--json=1`, `--files=none`, `--flat=1`, a lone `-` and `---` all
become `fopen` targets and fail with exit 1; `-e` at the end of argv (no
value) is likewise opened as a file named `-e`. Conversely, a flag-looking
value immediately after `-e` is consumed as expression text (`-e -q` prints
`_(q: real) = -q`).

Goldens: `cli_02_flags.out`, `cli_03_e_edges.out` ("e-edge: missing value"),
`cli_09_misc.out` ("--files=none equals form", "--mcp --flat=1 equals form").

**Why it matters:** a caller expecting conventional CLI behavior gets
file-not-found errors rather than "unknown option" diagnostics, and typos in
flag names are not distinguished from file paths.

### LIMIT-3 — early-return flags discard all following arguments
**Severity:** LIMIT
**Expected:** _not recorded_
`--json`, `--json-schema`, `--mcp`, `--sat-selftest`, `-h` and `--help`
`return` from `main` as soon as they are seen. Any later argv is ignored,
including otherwise valid work:

**Reproducer:**
```sh
$ROOT/ucas -e '1+1' -h -e '2+2' | head -2
```

**Observed:** prints `2` then help, and the second `-e '2+2'` never runs (golden
`cli_07_order.out`, "order: -e then -h then -e"). Mixed modes likewise do not
compose: `--json --mcp` fails with the `--json` usage message because `--mcp`
is seen as an invalid json-sub flag; `--mcp --json` fails with the `--mcp`
usage message.

**Why it matters:** order-dependent silent dropping of requested work.

### LIMIT-4 — `UCAS_MCP_PROTO` env var is effectively ignored at initialize
**Severity:** LIMIT
**Expected:** _not recorded_
`mcp_main` reads `UCAS_MCP_PROTO` at startup, but the `initialize` handler
immediately overwrites the negotiated version from the client's
`protocolVersion`. So setting it has no effect on a normal session:

**Reproducer:**
```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
  | UCAS_MCP_PROTO=2024-11-05 $ROOT/ucas --mcp
```

**Observed:** `protocolVersion` in the reply is still `2025-06-18` (golden
`cli_06_mcp.out`, "mcp: UCAS_MCP_PROTO override").

**Why it matters:** an environment knob that appears to pin the protocol does
not do so, which is surprising for callers trying to force an older protocol.

## Checks that passed

_No separate passed checks were recorded in the original document._
