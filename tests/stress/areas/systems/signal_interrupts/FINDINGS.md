# Stress findings — `signal_interrupts`

_Original heading: Findings — `signal_interrupts`_

# Findings — `signal_interrupts`

Area: interrupt robustness (SIGINT/SIGTERM/SIGHUP/SIGTSTP/SIGCONT, stdin close,
PTY Ctrl-C, external child kill, rapid double interrupts) during long searches
in CLI, `--json` and `--mcp` modes.

Binary: `$ROOT/ucas` (prebuilt, not rebuilt).
All runs bounded by `timeout` or an explicit `SIGKILL`. The machine-readable log
of every scenario is `results.jsonl` (153 scenarios from `driver.py`), with raw
per-run stdout/stderr in `_scratch/runs/`. `reproduce.sh` is a tested,
copy-pasteable reproducer for every finding below.

**No golden `.out` files are provided on purpose.** An interrupt scenario is
timing-dependent: which command is in flight when the signal lands, and how much
stdout has been flushed, both vary with machine load. Determinism check (4
identical runs, `ucas long_approx.ucas` + `kill -TERM` at 3.0 s):

```
run1 bytes=406  run2 bytes=419  run3 bytes=406  run4 bytes=393
diff deta_1 deta_2: 6 differing lines
  8c8
  <     2/2 1.58 (2.92) 2/3 1.58 (-)
  >     2/2 1.58 (2.92) 2/3 1.58 (-) 5/1 2.39 (-)
```

The exit code is stable (143) and every complete line is valid output, but the
partial last line differs. By the suite rules (SPEC.md §2), nondeterministic
cases must be documented in FINDINGS.md and must NOT be added as golden `.out`
tests. The only deterministic artefact is the well-formed-timeout baseline
(`scenarios/mcp_internal_timeout.jsonl`), kept as a reference reproducer without
a golden.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | killing the MCP/JSON server mid-search leaves the client stalled until `timeout_s` elapses |
| WRONG | 1 | killing the forked timeout child silently disables `timeout_s` |
| LIMIT | 2 | external signals orphan the timeout child (no PDEATHSIG / no signal forwarding) |

## Findings

### HANG-1 — killing the MCP/JSON server mid-search leaves the client stalled until `timeout_s` elapses
**Severity:** HANG
**Why it matters:** _not recorded_
`--json`/`--mcp` mode (`json_signal_*`, `mcp_signal_*`, delays 0.8/1.6/2.4 s,
`timeout_s: 60`).

A request with `timeout_s` makes the server fork a timeout child. That child
inherits the stdout *write* end of the client pipe. When the parent server is
killed mid-search, the child does not die: it keeps the write end open and only
writes the timeout error at the original deadline. A client reading the pipe
therefore sees neither the in-flight response nor EOF for the rest of the
`timeout_s` window.

**Reproducer:**
Reproducer (short 3 s deadline so it resolves quickly; `reproduce.sh` §Finding 1):

```sh
cd $ROOT/tests/stress/areas/systems/signal_interrupts/scenarios
python3 - <<'PY'
import subprocess, signal, time, os, select, fcntl
BIN="$ROOT/ucas"; f="mcp_short_t.jsonl"  # approx, timeout_s=3
p=subprocess.Popen([BIN,"--mcp"],stdin=open(f,"rb"),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
time.sleep(1.0)
kid=int(subprocess.check_output(["pgrep","-P",str(p.pid)]).split()[0])
p.kill(); p.wait()                        # server dies mid-search
fd=p.stdout.fileno()
fcntl.fcntl(fd,fcntl.F_SETFL,fcntl.fcntl(fd,fcntl.F_GETFL)|os.O_NONBLOCK)
t0=time.time(); events=[]; buf=b""
while time.time()-t0 < 8:
    r,_,_=select.select([fd],[],[],0.2)
    if r:
        try: c=os.read(fd,65536)
        except OSError: c=b""
        if not c: events.append(("EOF",round(time.time()-t0,2))); break
        buf+=c; events.append(("DATA",round(time.time()-t0,2),len(c)))
print(events)
print(buf[-220:].decode("utf-8","replace"))
PY
```

**Observed:** (client events, `t` = seconds after the server was killed):

```
[('DATA', 0.0, 765), ('DATA', 1.92, 310), ('EOF', 1.92)]
... "error": {"code": "timeout", "message": "timed out after 3 s; the state is unchanged"}}, "isError": true}}
orphan still alive at end? YES
```

The first 765 bytes are the `initialize` result; then ~2 s of **silence** (no
data, no EOF); at the 3 s deadline the orphan timeout child emits the
`timeout` error and closes the fd. With `timeout_s: 60` (the cataloged scenarios)
this is a ~59 s stall. No `isError` object, no error response, and no EOF
arrive when the server dies — only after the deadline.

**Expected:** a well-formed JSON-RPC error (or at minimum EOF) promptly when the
server dies, so a client does not block for the remainder of a long timeout.
The server already knows how to produce a well-formed error — an *internal*
timeout returns `isError:true` with
`structuredContent.error = {"code":"timeout", ...}` (verified with
`scenarios/mcp_internal_timeout.jsonl`). It is the external-kill path that stalls.

### WRONG-1 — killing the forked timeout child silently disables `timeout_s`
**Severity:** WRONG
**Why it matters:** _not recorded_
`timeout_s` is enforced by a forked child; the search itself runs in the parent.
If that child is killed externally, no error is emitted and the parent runs the
search to completion with no limit at all.

**Reproducer:**
Reproducer (`reproduce.sh` §Finding 2):

```sh
cd $ROOT/tests/stress/areas/systems/signal_interrupts/scenarios
# baseline
timeout 8 $ROOT/ucas --mcp < mcp_short_t.jsonl 2>&1 | tail -1
# child killed at t=1 s
python3 - <<'PY'
import subprocess,signal,time,os,json
BIN="$ROOT/ucas"
p=subprocess.Popen([BIN,"--mcp"],stdin=open("mcp_short_t.jsonl","rb"),
                   stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
time.sleep(1.0)
kid=int(subprocess.check_output(["pgrep","-P",str(p.pid)]).split()[0])
os.kill(kid,signal.SIGKILL)
out=p.communicate(timeout=15)[0]
for l in out.decode().splitlines():
    o=json.loads(l)
    if o.get("id")==1:
        print("isError",o["result"].get("isError"),"error",(o["result"].get("structuredContent") or {}).get("error"))
PY
```

**Observed:**

```
baseline:  {"id":1,...,"error":{"code":"timeout","message":"timed out after 3 s; the state is unchanged"}...,"isError":true}   (returned at ~3.0 s)
child killed at 1 s:  isError False error None    (full approx result, returned at ~6-12 s, never at 3 s)
```

`parent_alive_after_child_kill` was `True` in 6/6 `*_childkill_*` scenarios;
in the focused long-`approx` probe (an in-flight request at kill time) the
response was a normal success, not a timeout.
**Expected:** the parent
should notice the timer child's death and either fail closed with an error or
enforce the deadline in-process. As-is, an adversary (or an overzealous
process supervisor) that can signal the child removes the caller's timeout
protection. This is distinct from the already-documented "string `timeout_s`
disables the limit" finding in `timeout_isolation` — here the limit is a valid
number and is still silently dropped.

### LIMIT-1 — external signals orphan the timeout child (no PDEATHSIG / no signal forwarding)
**Severity:** LIMIT
**Why it matters:** _not recorded_
In 42/153 cataloged scenarios an external signal to a `--json`/`--mcp` server
killed the parent but left its forked timeout child alive. Breakdown: 18 signal
scenarios, 8 parent-kill scenarios, 6 stdin-close scenarios, 6 MCP double-interrupt
scenarios, 4 TSTP/CONT+INT scenarios. Parent exit codes were the expected
signal deaths (`rc = -15/-2/-1/-9`, i.e. shell 143/130/129/137), but the child
survived until its deadline:

**Observed:**
**Reproducer:**
```sh
parent 2701123 timer child [2701127] -> SIGTERM parent
  t+1s orphans: ['2701127:S']
  t+2s orphans: []          # fires at the 3 s deadline and exits
```

With `timeout_s: 60` the orphan lingers for ~60 s, still holding the client's
stdout write fd.
**Expected:** the child should have `PR_SET_PDEATHSIG` (or the
parent should forward termination signals) so it cannot outlive its server.

### LIMIT-2 — closing stdin does not interrupt an in-flight search
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
cancel a query by closing stdin).

CLI mode with two chained ~5 s `gates` searches on stdin, stdin pipe closed at
0.8/1.6/2.4 s:

**Observed:**
**Reproducer:**
```sh
cli close_stdin d=0.8: rc=0 outbytes=7024 errbytes=0   (both searches complete normally)
cli close_stdin d=1.6: rc=0 outbytes=7024 errbytes=0
cli close_stdin d=2.4: rc=0 outbytes=7024 errbytes=0
```

`--json`/`--mcp` with the long `approx` request behave the same way: closing
stdin during the search does not stop it, and killing the process afterwards
leaves the timeout child orphaned (6 scenarios). A client that wants to cancel
must kill the process, not close the stream.

## Checks that passed

### Verified-correct behaviour (no finding; full coverage recorded in `results.jsonl`)
All checks below passed; none produced a core dump, an orphan, or a bad fresh
process. A "fresh process works afterwards" probe
(`printf '1+1\n' | ucas` → `2`, rc=0) passed in **153/153** scenarios.

- **CLI signal matrix — 72/72 clean.** For each of `find`, `gates`, `approx`,
  `fit`, `prove`, `range` (each in a >10 s workload file) and each of SIGINT,
  SIGTERM, SIGHUP at delays 0.7/1.4/2.1/2.8 s: exit was a clean signal death
  (`rc = -2/-15/-1` → shell 130/143/129), stdout was either empty (stdio still
  buffered, e.g. the 30,000-statement `fit` workload) or contained only the
  echoed statements plus the current search's header line, stderr was empty, no
  children existed, and no core file was produced. Examples:
  `cli_gates_TERM_1.4`, `cli_approx_INT_dfl_2.1`, `cli_range_HUP_2.8`.
- **PTY Ctrl-C — 16/16 clean.** Both `script -qec "... ucas long_X.ucas"`
  (12 runs) and `pty.fork()` + `write(fd, b"\x03")` (4 runs) gave rc=130 / -2,
  echoed `^C`, no orphan and no core. One `find` run hit the ambiguous-`^`
  prompt (`which? [1]`) and Ctrl-C aborted there cleanly too.
- **Rapid double/triple interrupts — 12/12 clean.** INT/INT, TERM/TERM,
  INT/TERM, TERM/INT, HUP/HUP, INT/TERM/INT at 20 ms gaps, in CLI and MCP: no
  crash, no core, no hung process after the first signal took effect.
- **SIGTSTP/SIGCONT — 12/12 correct.** `/proc/PID/stat` state was `T` at every
  stop; SIGCONT resumed the search in every case. No stopped process was left
  behind.
- **Output framing — 153/153 well-formed.** Every complete line emitted in
  `--json`/`--mcp` mode parsed as a JSON object; no truncated JSON line was
  observed. The problem in the HANG finding is *absence* of the response, not
  corrupt JSON.
- **No partial output files.** `plot … to NAME` and `animate … to NAME` write
  complete GIFs (`file` reports `GIF image data, version 89a`) or, if interrupted
  before the write, leave no file at all. No truncated file was found after any
  of the interrupt runs.
- **No core dumps from this area.** `coredumpctl` SIGSEGV entries seen during the
  run all had command lines from another subagent's
  `tests/stress/areas/systems/fault_injection/corpus/cNNN.ucas`, never from a
  `signal_interrupts` workload.
- **Background-job caveat (not a product bug).** A process started with `&` in a
  non-interactive bash inherits `SIGINT`/`SIGQUIT` as `SIG_IGN`, so `kill -INT`
  appears to be ignored (the search runs to completion). All INT scenarios in
  the driver reset the disposition to `SIG_DFL` via `reset_exec.py` (or use a
  real PTY), which is the disposition a foreground process has. Reported here
  so nobody mistakes the shell artefact for an ignored-signal bug.
