# Stress findings — `repo_tooling`

_Original heading: FINDINGS — repository developer tooling (`tools/*`, `.claude/skills/ucas/*`)_

# FINDINGS — repository developer tooling (`tools/*`, `.claude/skills/ucas/*`)

Area folder: `tests/stress/areas/frontend/repo_tooling/`. 157 bounded invocations (see `harness_log.txt` /
`harness_log.json`). All runs used absolute paths and cwd = this folder; every run was
wrapped in `timeout`. Reproducers use `fake_mcp.py` / `fake_json.py`, which live in this
folder and emit canned (or malformed) JSON-RPC / JSON lines.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 2 | `mcp_client.py --flat` with no explicit binary path |
| HANG | 1 | `mcp_client.request()` never times out on a silent / wrong-id server |
| WRONG | 2 | `ucas.sh which` reports a directory as the chosen binary |
| LIMIT | 7 | structurally malformed (but parseable) MCP replies give confusing tracebacks |

## Findings

### CRASH-1 — `mcp_client.py --flat` with no explicit binary path
**Severity:** CRASH
_Original classification: `CRASH: mcp_client.py --flat with no explicit binary path`._
**Expected:** _not recorded_
**Reproduce** (from any cwd):
**Reproducer:**
```sh
python3 $ROOT/tools/mcp_client.py --flat
```

**Observed:** (rc 1):
```
Traceback (most recent call last):
  File "$ROOT/tools/mcp_client.py", line 128, in <module>
    main()
  ...
  File "$ROOT/tools/mcp_client.py", line 25, in __init__
    self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE,
  ...
FileNotFoundError: [Errno 2] No such file or directory: '--mcp'
```

**Why it matters:** it's a bug:** the module docstring documents `python3 tools/mcp_client.py
[path/to/ucas] [--flat]`, i.e. the path is optional and `--flat` alone should use the
default `../ucas`. In `main()`, `argv = sys.argv[1:] or [default]` is evaluated **before**
`--flat` is stripped; with only `--flat` the fallback is skipped, the filtered list is
empty, and `argv` becomes `['--mcp', '--flat']`. `Popen` then tries to execute the program
named `--mcp`. `--flat` after a real path (`mcp_client.py ./ucas --flat`) works, so this is
purely an argument-order/default bug.

### HANG-1 — `mcp_client.request()` never times out on a silent / wrong-id server
**Severity:** HANG
_Original classification: `HANG: mcp_client.request() never times out`._
**Expected:** _not recorded_
**Reproduce:**
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/repo_tooling
FAKE_SCENARIO=hang_wrongid timeout 3 \
  python3 $ROOT/tools/mcp_client.py ./fake_mcp.py
```
(`hang_wrongid` emits one reply with `id: 999` then blocks reading stdin; `hang_after_init`
is the same after a valid `initialize`.)

**Observed:** no output at all, `timeout` kills it, rc 124. Same for `hang_after_init`.

**Why it matters:** it's a bug:** `request()` loops `while True: line = self.proc.stdout.readline()` and
only stops on a matching `id` or EOF. A server that stays alive but never sends the matching
id (a hung or buggy MCP server) hangs the client forever — there is no deadline and no
`isError`/timeout handling. A diagnostic client should bound the wait.

### CRASH-2 — no graceful failure when the MCP server is missing/dies/emits bad JSON
**Severity:** CRASH
_Original classification: `CRASH: no graceful failure when the MCP server`._
**Expected:** _not recorded_
**Reproduce:**
**Reproducer:**
```sh
python3 $ROOT/tools/mcp_client.py /nonexistent/ucas      # bad path
python3 $ROOT/tools/mcp_client.py $ROOT # a directory
cd tests/stress/areas/frontend/repo_tooling
FAKE_SCENARIO=exit0    python3 $ROOT/tools/mcp_client.py ./fake_mcp.py
FAKE_SCENARIO=badjson  python3 $ROOT/tools/mcp_client.py ./fake_mcp.py
FAKE_SCENARIO=blankline python3 $ROOT/tools/mcp_client.py ./fake_mcp.py
```

**Observed:** (rc 1 for all):** raw Python tracebacks — `FileNotFoundError: ... '/nonexistent/ucas'`,
`PermissionError: ... '$ROOT'`, `McpError: the server exited`,
`json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`,
`json.decoder.JSONDecodeError: Expecting value: line 2 column 1 (char 1)`.

**Why it matters:** it's a bug:** the documented "fails gracefully when prerequisites are missing" is
not met: there is no `try/except`, so users get a 12-line traceback instead of a one-line
"server failed to start" message. Exit code 1 is at least consistent.

### LIMIT-1 — structurally malformed (but parseable) MCP replies give confusing tracebacks
**Severity:** LIMIT
_Original classification: `LIMIT: structurally malformed (but parseable) MCP replies give confusi`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Reproduce:** with `FAKE_SCENARIO=<name> python3 .../mcp_client.py ./fake_mcp.py`. Final
exception line observed for each scenario (all rc 1), from `harness_log.txt`:

| scenario | malformed reply | final exception |
| --- | --- | --- |
| `id_noresult` | reply with `id` but no `result`/`error` | `TypeError: 'NoneType' object is not subscriptable` |
| `init_error` | `initialize` returns JSON-RPC error | `McpError: -32000: init refused` |
| `init_noserverinfo` | init result lacks `serverInfo` | `KeyError: 'serverInfo'` |
| `init_noprotoversion` | init result lacks `protocolVersion` | `KeyError: 'protocolVersion'` |
| `tools_no_tools` | `tools/list` result lacks `tools` | `KeyError: 'tools'` |
| `tools_bad_entry` | a tool entry lacks `name` | `KeyError: 'name'` |
| `call_no_content` | `tools/call` result lacks `content` | `KeyError: 'content'` |
| `call_content_empty` | `content: []` | `IndexError: list index out of range` |
| `call_text_missing` | `content[0]` lacks `text` | `KeyError: 'text'` |
| `ambig_no_readings` | `ambiguous` error lacks `readings` | `KeyError: 'readings'` |
| `plot_image_nodata` | image item lacks `data` | `KeyError: 'data'` |
| `plot_image_nomime` | image item lacks `mimeType` | `KeyError: 'mimeType'` |
| `plot_badb64` | image `data` is invalid base64 | `binascii.Error: Invalid base64-encoded string ...` |
| `string_id` | reply `id` is a string, not a number | `McpError: the server exited` |

**Why it matters:** it's a bug:** every one of these is an unchecked dictionary/list access in `main()`,
`show()` or `Mcp.call()`. There is no schema validation and no `try/except`; a server that
is merely sloppy (rather than dead) produces a traceback whose `KeyError` rarely tells the
user which MCP field was wrong. `Mcp.call()` also assumes the ambiguity error always has
`readings`. Non-issue controls: `dup_id`, `crlf`, `unicode`, `empty_tools`,
`iserror_with_error`, `huge_line` all complete successfully (rc 0).

### WRONG-1 — `ucas.sh which` reports a directory as the chosen binary
**Severity:** WRONG
_Original classification: `WRONG: ucas.sh which reports a directory as the chosen binary`._
**Expected:** _not recorded_
**Reproduce:**
**Reproducer:**
```sh
UCAS=$ROOT PATH=/usr/bin:/bin \
  /bin/sh $ROOT/.claude/skills/ucas/ucas.sh which
UCAS=$ROOT PATH=/usr/bin:/bin \
  /bin/sh $ROOT/.claude/skills/ucas/ucas.sh -e '1+1'
```

**Observed:**
```
$ROOT                       # `which`: rc 0, prints the DIRECTORY
...
.claude/skills/ucas/ucas.sh: line 42: $ROOT: Is a directory   # exec: rc 126
```

**Why it matters:** it's a bug:** the only validation is `[ ! -x "$bin" ]`, and `-x` is true for a
searchable directory. `which` therefore lies (claims a usable binary) and `exec` later
fails with "Is a directory". A `-f`/`-d` check would fix it. The same holds for any path
that is a directory named like a binary.

### WRONG-2 — `HOME` unset + `~/` in `skills.env` emits a shell error then silently falls back
**Severity:** WRONG
_Original classification: `WRONG (minor): HOME unset + ~/`._
**Expected:** _not recorded_
**Reproduce** (with a `.claude/skills.env` containing `UCAS_BIN=~/Code/ucas/ucas` in a
parent of cwd):
**Reproducer:**
```sh
cd tests/stress/areas/frontend/repo_tooling/envtree
env -u UCAS -u HOME PATH=/usr/bin:/bin \
  /bin/sh $ROOT/.claude/skills/ucas/ucas.sh which
```

**Observed:** (rc 0):
```
$ROOT/.claude/skills/ucas/ucas.sh: line 14: HOME: unbound variable
$ROOT/ucas
```

**Why it matters:** it's a bug:** `set -u` plus the unguarded `$HOME/` expansion on line 14 makes the
`from_env` subshell die with "unbound variable"; the caller treats the empty result as
"no setting" and quietly falls through to the repository binary — a different binary than
the one the skills.env asked for. (With HOME set the `~/` expansion works: `homeA/myucas`
case passes.)

### LIMIT-2 — `skills.env` values are not trimmed (CRLF / spaces break resolution)
**Severity:** LIMIT
_Original classification: `LIMIT: skills.env values are not trimmed (CRLF / spaces break resolu`._
**Expected:** _not recorded_
**Reproduce** (skills.env with the given line, cwd under it):
**Observed:**
**Reproducer:**
```sh
UCAS_BIN=$ROOT/ucas\r\n      -> "no ucas binary at .../ucas\r"   rc 2
UCAS_BIN=$ROOT/ucas   \n     -> "no ucas binary at .../ucas   "   rc 2
UCAS_BIN=  $ROOT/ucas\n      -> "no ucas binary at   .../ucas"    rc 2
UCAS_BIN = $ROOT/ucas\n      -> falls back to repo ./ucas          rc 0
```
(the last line uses spaces around `=`, so the `sed -n 's/^UCAS_BIN=//p'` pattern does not
match and the setting is silently ignored).

**Why it matters:** it's a bug/misleading:** a CRLF-edited or casually spaced skills.env is a common real
case; the error shows the raw CR/spaces in the path, which is confusing, and the
spaces-around-`=` form is silently ignored rather than warned about.

### LIMIT-3 — `ucas.sh` needs coreutils even for `which` with `UCAS` already set
**Severity:** LIMIT
_Original classification: `LIMIT: ucas.sh needs coreutils even`._
**Expected:** _not recorded_
**Reproduce:**
**Reproducer:**
```sh
env UCAS=$ROOT/ucas PATH= \
  /bin/sh $ROOT/.claude/skills/ucas/ucas.sh which
```

**Observed:** (rc 0 but noisy):
```
$ROOT/.claude/skills/ucas/ucas.sh: line 6: dirname: command not found
$ROOT/.claude/skills/ucas/ucas.sh: line 6: cd: null directory
$ROOT/ucas
```

**Why it matters:** it's a bug:** line 6 computes `here` with external `dirname` before any resolution;
with a minimal PATH (the script itself documents keeping system tools on PATH, but a
caller may not) `here` is empty and error text leaks to stderr even though the answer is
correct. Same noise with only a stub dir on PATH. Low severity.

### LIMIT-4 — `mcp_client.py` always writes `mcp_plot.gif` into the current directory, even on failure
**Severity:** LIMIT
_Original classification: `LIMIT: mcp_client.py always writes mcp_plot.gif into the current d`._
**Expected:** _not recorded_
**Reproduce:**
**Reproducer:**
```sh
cd tests/stress/areas/frontend/repo_tooling
python3 $ROOT/tools/mcp_client.py $ROOT/ucas
# -> mcp_plot.gif appears in $PWD; running from the repo root would write it there
FAKE_SCENARIO=plot_badb64 python3 $ROOT/tools/mcp_client.py ./fake_mcp.py
# -> open("mcp_plot.gif","wb") runs before b64decode(); a 0-byte file is left behind
```

**Observed:** the first command prints `-- plot: wrote mcp_plot.gif (image/gif)` and creates
the file; the malformed case leaves a `-rw-r--r-- ... 0 ... mcp_plot.gif` and then raises
`binascii.Error`. Also confirmed with a nested cwd: the GIF lands in that nested folder.

**Why it matters:** it's a bug:** there is no `--dir`/output-path option, so the client always dirties the
caller's cwd (the SKILL.md warns to use `--dir` for ucas itself, but the client has no such
option). Writing the file before validating the payload leaves a broken artifact after a
crash.

### LIMIT-5 — `mcp_sdk_check.mjs` has no friendly prerequisite/binary errors
**Severity:** LIMIT
_Original classification: `LIMIT: mcp_sdk_check.mjs has no friendly prerequisite/binary errors`._
**Expected:** _not recorded_
**Reproduce / observed:**
**Observed:**
**Reproducer:**
```sh
node $ROOT/tools/mcp_sdk_check.mjs ./ucas
# rc 1: Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@modelcontextprotocol/sdk' ...
node $ROOT/tools/mcp_sdk_check.mjs /nonexistent/ucas
# rc 1: raw node:internal/child_process ... Error: spawn /nonexistent/ucas ENOENT
node $ROOT/tools/mcp_sdk_check.mjs            # no bin arg -> raw traceback
```

**Why it matters:** it's a bug:** the file's own header says "npm install @modelcontextprotocol/sdk",
but with the SDK absent it prints a 15-line Node module-resolution traceback rather than
that hint. With SDK 1.20.2 made resolvable (local symlinks in this folder; copy
`sdk_check_copy.mjs`) the script passes end to end: 27 tools, `range`, ambiguity, plot,
session-preserved-after-timeout, resources, prompts and `unknown tool error: -32602` all
behave. An extra unrecognised argv (`--mcp-extra`) makes ucas print `usage: ucas --mcp
[--flat] [--dir DIR]` and the SDK report `MCP error -32000: Connection closed`.

### LIMIT-6 — `ucas_client.py` also fails with raw tracebacks on bad prerequisites/replies
**Severity:** LIMIT
_Original classification: `LIMIT: ucas_client.py also fails with raw tracebacks`._
**Reproduce:**
**Reproducer:**
```sh
python3 $ROOT/tools/ucas_client.py /nonexistent/ucas   # FileNotFoundError
cd tests/stress/areas/frontend/repo_tooling
FAKE_JSON_SCENARIO=exit0    python3 $ROOT/tools/ucas_client.py ./fake_json.py
FAKE_JSON_SCENARIO=badjson  python3 $ROOT/tools/ucas_client.py ./fake_json.py
FAKE_JSON_SCENARIO=wrongid  python3 $ROOT/tools/ucas_client.py ./fake_json.py
```
**Observed:** (rc 1):** `FileNotFoundError: ... '/nonexistent/ucas'`,
`RuntimeError: ucas exited`, `JSONDecodeError: Expecting value: line 1 column 1`,
`AssertionError: responses come back in order`. (`error`/`ambig`/`nook` fake replies also
raise `KeyError` from `schema()`/`show()`.) With the real binary the demo passes and is
deterministic (`tool_ucas_client.out` golden).

**Why it matters:** it's a bug:** same class as F3/F4 — no guard around `Popen`, `readline`, `json.loads`
or the id check.
**Expected:** a concise error naming the failing prerequisite.

### LIMIT-7 — `test.sh` cannot tell a wrong binary from a broken build
**Severity:** LIMIT
_Original classification: `LIMIT: test.sh cannot tell a wrong binary from a broken build`._
**Expected:** _not recorded_
**Reproduce:**
**Reproducer:**
```sh
# with a stub named `ucas` earlier on PATH
PATH=tests/stress/areas/frontend/repo_tooling/bin_with_ucas:/usr/bin:/bin \
  sh $ROOT/.claude/skills/ucas/test.sh
```
**Observed:** (rc 1):
```
ucas: $ROOT/tests/stress/areas/frontend/repo_tooling/bin_with_ucas/ucas
FAIL equiv: two forms of a mean proved equal by SAT
     | STUB-UCAS argv: -e avg(x: u32, y: u32) = ...
... 10 failed
```
Also: with the repo binary present (the normal case) the "no binary is refused" branch at
the end of `test.sh` is **never executed** — it is guarded by `if [ -x "$here/../../../ucas"
]`, which is always true here. Exercising that branch required copying `ucas.sh` into a
deeper folder (`copy/ucas.sh`); the refusal then works correctly (`rc 2`, exact documented
message — see `A7.no_binary_copy_direct`).

**Why it matters:** it's a bug:** a stub/wrong binary yields ten misleading recipe failures instead of a
single "the binary you found is not ucas" check. The key no-binary refusal is untestable
in-tree. Low severity.

## Checks that passed

### Cross-area observation (ucas CLI, not owned by this folder)
SKILL.md line 156 recommends `--dir DIR` to keep generated GIFs out of the working
folder, but in plain CLI mode the flag only works **after** the statements:
```sh
$ROOT/ucas --dir "$PWD" -e 'plot sin(x)'   # "--dir: No such file or directory" (rc 1)
$ROOT/ucas -e 'plot sin(x)' --dir "$PWD"   # works (writes plot.gif into DIR)
$ROOT/ucas --json --files none --dir "$PWD" -e '{...}'   # works
```
This is a ucas argument-parser issue (belongs to a CLI-focused area), noted here only
because it affects the tool-facing documentation. Not counted as a tooling finding.

### Non-findings / controls
- **Determinism:** all kept goldens (CLI via `ucas.sh`, MCP via `ucas.sh --mcp`,
  `mcp_client.py`, `ucas_client.py`) produced byte-identical output on two runs. No
  `DETERMINISM` issue found. (The SAT conflict count in the `equiv` golden was stable at
  `833` across runs; it differs from the number quoted in SKILL.md, which is a doc-vs-build
  drift, not nondeterminism.)
- **Exit codes:** `ucas.sh` returns 0 on success, 2 for "no binary" (documented), and passes
  through the child's code (verified 37 via a stub). `test.sh` returns 0/1 as documented.
  `mcp_client.py` / `ucas_client.py` / SDK check return 1 on failure (via traceback).
- **No stray files outside this folder:** every GIF/PNG/log generated by my runs lives in
  `tests/stress/areas/frontend/repo_tooling/` (verified). `tests/simplified.spvasm` was written at
  22:00:59 by another agent — before this harness started (~22:03) — and was not touched.
- **Ambiguity answering works:** the real `mcp_client.py` run answers `zeros(z^2+1)` by
  picking the `default` reading (`z` complex) and continues; the SDK check shows
  `ambiguous: true caret`. The fake `normal_ambig` scenario confirms the retry-with-
  `assume` loop advances the id correctly.
- **Plot image saving works:** `mcp_client.py` decodes and writes the returned GIF;
  `gifcheck.py` independently validates it (and the repo's `area.gif` / `revolve.gif`).
