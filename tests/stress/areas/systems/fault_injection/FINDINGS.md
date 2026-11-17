# Stress findings — `fault_injection`

_Original heading: Findings — `fault_injection`_

# Findings — `fault_injection`

Area: graceful degradation when libc calls fail at awkward moments.

All reproducers use the prebuilt binary `$ROOT/ucas` and the
LD_PRELOAD shim in this folder (`shim.c` → `fi_shim.so`). The shim fails the Nth
call to a selected function and logs `[FI] <fn> call #<n> -> INJECTED FAILURE`
to stderr. Each process (including fork()ed MCP workers) has its own counters.

**Important invocation detail:** put `env` *inside* `timeout`, i.e.
`timeout 15 env FI_FAIL_X=N LD_PRELOAD=$PWD/fi_shim.so ucas ...`. If
`LD_PRELOAD` is set before `timeout`, the `timeout` process itself loads the
shim and logs a spurious extra `[FI]` line.

Coverage: 154 corpus commands (`corpus/c001..c154.ucas`) were run under all ten
shims for several N values each (5,236 executions; tallies in
`matrix_results.txt`). A 156-call MCP `--flat` corpus (`mcp_corpus_flat.jsonl`)
plus focused JSONL fixtures exercised the fork/pipe/waitpid and file-write paths.
Every would-be golden was run twice and diffed (both kept goldens are
deterministic). Crash / nondeterministic cases are documented here, not kept as
goldens.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 2 | 1 — malloc failure at some call indices → SIGSEGV (no OOM message) |
| WRONG | 2 | 1 — waitpid failure on MCP crash path reports a bogus, random signal number |
| LIMIT | 3 | 1 — fork / pipe failure silently disables `timeout_s` in MCP |

## Findings

### CRASH-1 — 1 — malloc failure at some call indices → SIGSEGV (no OOM message)
**Severity:** CRASH
**Reproducer:**
Reproducer** (from this folder; `show 1+2` in a one-line file):

```sh
cd $ROOT/tests/stress/areas/systems/fault_injection
printf 'show 1+2\n' > /tmp/fi_one.ucas
timeout 15 env FI_FAIL_MALLOC=150 LD_PRELOAD=$PWD/fi_shim.so \
  $ROOT/ucas /tmp/fi_one.ucas > /tmp/fi150.out 2>&1; echo $?
```

**Observed:** exit `139` (`SIGSEGV`), output:

```
[FI] malloc call #150 -> NULL (ENOMEM)
timeout: the monitored command dumped core
```

No echoed input, no answer, and crucially **no `ucas: out of memory`**. The same
happens at `FI_FAIL_MALLOC=5` (startup). At other indices the *same* OOM is
handled cleanly: `FI_FAIL_MALLOC=30` → exit `2`, output
`[FI] malloc call #30 -> NULL (ENOMEM)` + `ucas: out of memory`.

Across the 154-command corpus, `FI_FAIL_MALLOC=5` and `=150` produced SIGSEGV on
**all 154** commands, while `=30` and `=80` produced clean OOM on all 154.

**Why it matters:** `xmalloc`/`xcalloc`/`xrealloc` (`src/util.c:7-40`) implement a
clean OOM exit, but raw `malloc()` sites are dereferenced unchecked. A failed
allocation therefore randomly gets a clean `out of memory` or a segfault
depending on which call index is hit.
**Expected:** every allocation failure
produces the clean OOM message.

### CRASH-2 — 2 — strdup failure → SIGSEGV
**Severity:** CRASH
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/fault_injection
timeout 15 env FI_FAIL_STRDUP=1 LD_PRELOAD=$PWD/fi_shim.so \
  $ROOT/ucas /tmp/fi_one.ucas > /tmp/fi_strdup.out 2>&1; echo $?
```

**Observed:** exit `139` (`SIGSEGV`), output:

```
[FI] strdup call #1 -> NULL (ENOMEM)
timeout: the monitored command dumped core
```

Identical at `FI_FAIL_STRDUP=5`, `=12`, and `=24`; across the 154-command corpus
each of those four indices segfaulted on all commands that reached it
(`=24` fired on 135/154, the other 19 having fewer than 24 strdup calls).
At `=30` almost no command reaches the call (no effect).

**Why it matters:** strdup's return value is used unchecked throughout the
parser/symbol code; unlike malloc/calloc/realloc there is no OOM wrapper for it.
An OOM in strdup is a hard crash with no diagnostic.
**Expected:** clean OOM exit.

### WRONG-1 — 1 — waitpid failure on MCP crash path reports a bogus, random signal number
**Severity:** WRONG
_Original classification: `WRONG + DETERMINISM`._
**Reproducer:**
Reproducer** (fixture `mcp_crash_base.jsonl` contains a 2000-deep-paren
`show` with `timeout_s:3`, which crashes the forked worker with signal 11):

```sh
cd $ROOT/tests/stress/areas/systems/fault_injection
for i in 1 2 3; do
  timeout 15 env FI_FAIL_WAITPID=1 LD_PRELOAD=$PWD/fi_shim.so \
    $ROOT/ucas --mcp < mcp_crash_base.jsonl 2>&1 \
    | grep 'error (internal)'
done
```

**Observed:** (three consecutive runs):

```
error (internal): the evaluation crashed (signal 41); the state is unchanged
error (internal): the evaluation crashed (signal 28); the state is unchanged
error (internal): the evaluation crashed (signal 125); the state is unchanged
```

With no fault the correct message is `... crashed (signal 11) ...` (the input
really does segfault). The injected `waitpid` failure is logged as
`[FI] waitpid call #1 -> -1 (ECHILD)`.

**Why it matters:** `run_with_timeout()` (`src/jsonmode.c:3245-3252`) calls
`waitpid(pid, &st, 0)` and then reads `st` to build the error message. `st` is
uninitialized; when waitpid fails (ECHILD) the code reports whatever stack
garbage is in `st`. The reported signal is fabricated and changes run to run,
which can mislead a client debugging a real crash.
**Expected:** check waitpid's
return value and report a generic "crashed" message if the status is unknown.

### LIMIT-1 — 1 — fork / pipe failure silently disables `timeout_s` in MCP
**Severity:** LIMIT
_Original classification: `LIMIT (silent degradation; unbounded execution`._
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/fault_injection
# baseline: id 2 is a 6-bit 'gates' search with timeout_s 0.02
timeout 20 $ROOT/ucas --mcp < mcp_timeout_base.jsonl > /tmp/base.out 2>&1
grep '"id": 2,' /tmp/base.out | grep -o 'error (timeout[^"]*'

# inject a failure of the worker fork:
timeout 20 env FI_FAIL_FORK=2 LD_PRELOAD=$PWD/fi_shim.so \
  $ROOT/ucas --mcp < mcp_timeout_base.jsonl > /tmp/fork2.out 2>&1
grep '"id": 2,' /tmp/fork2.out | grep -o '"ok": [a-z]*'
```

**Observed:** baseline id 2 →
`error (timeout): timed out after 0.02 s; the state is unchanged`.
With `FI_FAIL_FORK=2` (or equivalently `FI_FAIL_PIPE=2`) id 2 →
`"ok": true` with the **full** gates result (68-step program, truth-table check
passed) and no `error` field. The only hint is the stderr line
`[FI] fork call #2 -> -1 (EAGAIN)`. Exit code stays 0 and later calls work.

**Why it matters:** `run_with_timeout()` returns -1 on pipe/fork failure and
`json_serve()` (`src/jsonmode.c:3273-3277`) falls back to running the request
inline. That keeps the server alive, but the caller's `timeout_s: 0.02` is
silently ignored: a request that should be bounded to 20 ms runs to completion.
A client relying on `timeout_s` for wall-clock protection gets none, with no
note in the JSON response. (Same class as the "string timeout_s" finding in
`timeout_isolation`.)
**Expected:** report that the limit could not be applied, or
return a resource error instead of silently dropping it. `FI_FAIL_FORK=1` /
`FI_FAIL_PIPE=1` hit `chain_start()`'s fallback and are harmless (timeout still
enforced).

### LIMIT-2 — 2 — partial (zero-byte) file left behind on fwrite failure (CLI plot/GIF)
**Severity:** LIMIT
_Original classification: `LIMIT (silent artifact / partial file`._
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/fault_injection
rm -f fw_plot1.gif
timeout 15 env FI_FAIL_FWRITE=1 LD_PRELOAD=$PWD/fi_shim.so \
  $ROOT/ucas filewrite.ucas > /tmp/fw.out 2>&1; echo $?
ls -l fw_plot1.gif
```

**Observed:** exit `0`; the error message is clear:

```
[FI] fwrite call #1 -> 0 (EIO)
filewrite.ucas:1:6: error: cannot write fw_plot1.gif
    plot sin(x) x in -3..3 to fw_plot1
         ^
```

but `fw_plot1.gif` **exists with size 0**. Same for the second and third
commands with `FI_FAIL_FWRITE=2` / `=3`. With `FI_FAIL_FOPEN=2` the error is
equally clear and **no** file is left behind (`fopen` never created it).

**Why it matters:** `deliver()` (`src/anim.c:1611-1617`) opens the output with
`fopen(path,"wb")`, and on `fwrite` failure only does `fclose(fp)` + `fail(...)`
— no `unlink`. A real ENOSPC mid-write would leave a truncated, apparently
valid `.gif`.
**Expected:** unlink the partially written output on failure.
(Positive controls in `run_fault_injection.sh` verify the clean error text.)

### WRONG-2 — 2 — JSON/MCP file-write failure still reports "wrote NAME.gif"
**Severity:** WRONG
_Original classification: `WRONG (misleading success text; silent data-integrity issue`._
**Reproducer:**
Reproducer** (fixture `fi_json_plot.jsonl` in `/tmp/opencode`, or inline):

```sh
cd /tmp/opencode
mkdir -p fi_outdir
printf '%s\n' '{"id":1,"cmd":"plot","args":{"fs":["sin(x)"],"options":"x in -3..3","to":"jp1"}}' \
  > fi_json_plot.jsonl
timeout 15 env FI_FAIL_FOPEN=1 LD_PRELOAD=$ROOT/tests/stress/areas/systems/fault_injection/fi_shim.so \
  $ROOT/ucas --json --files write --dir fi_outdir \
  < fi_json_plot.jsonl > /tmp/jp.out 2>&1
python3 -c 'import json;o=json.loads([l for l in open("/tmp/jp.out") if l.startswith("{")][0]);print(o["result"]["details"]);print(o["files"])'
```

**Observed:**

```
['x in [-3, 3]: given', 'y in [-1.1, 1.1]: the values', 'wrote jp1.gif']
[{'name': 'jp1.gif', 'mime': 'image/gif', 'bytes': 8059, 'error': 'Permission denied'}]
```

and `text` ends with `... wrote jp1.gif\n`. No file is created in `fi_outdir`.
With `FI_FAIL_FWRITE=1` the same happens with `error: 'Input/output error'` and a
zero-byte `jp1.gif` is left in the output dir.

**Why it matters:** `rep_file()` (`src/report.c:1148-1156`) correctly records
`files[].error` and omits `path`, but `rep_deliver()` (`src/report.c:1178-1181`)
then prints `wrote %s` unconditionally whenever `REP_FILES_WRITE` is set. A
client that renders only `result.details` / `text` believes the file was written
when it was not.
**Expected:** the "wrote" line must depend on the actual write
result.

### LIMIT-3 — 3 — non-timeout MCP requests have no crash isolation
**Severity:** LIMIT
_Original classification: `LIMIT (design limitation; whole session lost on OOM`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/fault_injection
timeout 15 env FI_FAIL_MALLOC=400 LD_PRELOAD=$PWD/fi_shim.so \
  $ROOT/ucas --mcp < mcp_inline_base.jsonl > /tmp/moom.out 2>&1; echo $?
```

**Observed:** exit `2`; responses for ids 1 and 2 are present, then:

```
[FI] malloc call #400 -> NULL (ENOMEM)
ucas: out of memory
```

— id 3 gets **no response**; the MCP server exited. `FI_FAIL_STRDUP=1` instead
kills the whole server with SIGSEGV (`139`) before any response. By contrast, a
request carrying `timeout_s` runs in a forked worker, so a crash there is
contained (`error (internal): the evaluation crashed (signal 11); the state is
unchanged`) and the session continues (verified with `mcp_crash_base.jsonl`).

**Why it matters:** fault containment in MCP is conditional on the caller
supplying `timeout_s`. Ordinary requests are handled inline, so any allocation
failure terminates the session and leaves the client with unanswered ids. This
matches the design (`json_serve` only forks for positive numeric `timeout_s`)
but is worth recording: clients wanting per-request isolation must set a
timeout on every call.

## Checks that passed

### Coverage note — `open()` faults never fire
`FI_FAIL_OPEN=N` and `FI_FAIL_OPEN64=N` (N = 1..8) never fired in the CLI
corpus, the MCP corpus, or JSON mode: the shim's exit dump reports `open=0`,
`open64=0`. The binary's own file writes go through `fopen`/`fwrite` and glibc
internal temp-file paths (whose `open` is not routed through the PLT), so there
is no simple reproducer for an `open`-failure failure mode. `fopen`/`fwrite`
faults (above) cover the reachable write paths.

### Verified-correct / graceful behaviour (no golden risk)
- **calloc / realloc OOM** → always clean `ucas: out of memory`, exit 2 (154/154
  corpus commands at the indices tested; see matrix).
- **malloc OOM at a handled index** (e.g. 30, 80) → clean exit 2.
- **fopen of the input file fails** → `perror` + exit 1, no crash.
- **fopen of an output file fails** → `error: cannot write ...`, no file created,
  remaining commands in the script still run.
- **read-only cwd** → `plot ... to NAME` gives `error: cannot write NAME.gif`,
  session continues (`show 1+2` still answered), no crash, no partial file.
- **unwritable / nonexistent TMPDIR** (adamfit with a C code block) → clean
  `adamfit: cannot make a temporary folder in <dir>`, exit 0, no crash.
- **MCP fork/pipe/waitpid faults** (indices 1 and 2) → session stays alive, all
  ids answered, no crash (asserted by `run_fault_injection.sh`).
- No stray child processes from my runs were left behind (`pgrep` clean after
  each batch); the live-session zombie check was inconclusive because other
  subagents were running many ucas processes concurrently, so no finding is
  claimed there.
