# Stress findings — `resource_limits_extended`

_Original heading: FINDINGS — `resource_limits_extended`_

# FINDINGS — `resource_limits_extended`

Area: OS resource limits **beyond virtual memory** — `ulimit -n / -f / -t / -u / -s / -l / -v`,
combined with the CLI, `--json`, `--mcp`, `--dir`, plots and `timeout_s` searches.

Binary: `$ROOT/ucas` (prebuilt; nothing rebuilt/edited).
All probes ran with an outer `timeout 15` (12 s for the deliberately long searches), cwd
`/tmp/opencode/rlx` unless stated. Exit codes are from `$?`: `137`=SIGKILL, `139`=SIGSEGV,
`153`=SIGXFSZ, `127`=dynamic-loader failure, `124`=outer timeout, `2`=clean ucas error.

`ulimit -N` is applied **inside a `bash -c 'ulimit -N K; exec ucas …'`** so the limit reaches the
final process without an intervening fork; the outer `timeout` keeps its own (unlimited) limits.

Only deterministic, limit-independent cases were kept as goldens (`0N_*.ucas/.out`,
`mcp_limits_baseline.jsonl/.out`). Every limit-dependent case is documented here instead.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 3 | SIGXFSZ mid-GIF-write: truncated partial file, no clean error |
| HANG | 1 | `timeout_s` silently ignored when `fork()` fails under `RLIMIT_NPROC` |
| WRONG | 1 | CPU-limit SIGKILL in a forked child reported as `internal (signal 9)` |
| LIMIT | 4 | stack overflow threshold scales with `-s` (graceful → SIGSEGV) |

## Findings

### CRASH-1 — SIGXFSZ mid-GIF-write: truncated partial file, no clean error
**Severity:** CRASH
_Original classification: `CRASH (with silent data loss / protocol break`._
**Reproducer:**
Reproducer (CLI text mode):

```sh
cd /tmp/opencode/rlx
printf 'plot sin x\n' > p.ucas
rm -f plot.gif
timeout 15 bash -c 'ulimit -f 4; exec $ROOT/ucas /tmp/opencode/rlx/p.ucas' > A.out 2>&1; echo $?
```

**Observed:** `EXIT=153` (SIGXFSZ). Output stops right after the size line — no answer, no
`wrote plot.gif`, no diagnostic about the file-size limit:

```
> plot sin x
plot of sin(x)
  x in [-6.283 (-2pi), 6.283 (2pi)]: periodic with period 6.283 (2pi): two periods
  y in [-1.1, 1.1]: the values
  sin(x): 1201 samples, values in [-1, 1]
  image: 640x440, 8729 bytes
timeout: the monitored command dumped core
```

`plot.gif` is left as a **4096-byte truncated GIF** (`GIF image data, version 89a, 640 x 440`
header only — incomplete data). A partial, corrupt file is silently left on disk.

**Worse in `--json` (`--files write`) and `--mcp --dir`:** the process dies before emitting the
response line, so the client receives **no JSON-RPC/JSON response at all**:

```sh
cd /tmp/opencode/rlx
rm -f plot.gif
printf '%s\n' '{"id":1,"cmd":"plot","args":{"fs":"sin x"}}' |
  timeout 15 bash -c 'ulimit -f 4; exec $ROOT/ucas --json --files write' > B.out 2>&1; echo $?
```

**Observed:** `EXIT=153`, `B.out` contains **only** `timeout: the monitored command dumped core`
(zero bytes of protocol output), plus a 4096-byte partial `plot.gif`. In MCP the `initialize`
reply is sent, then the process dies before the `tools/call` reply.

**Threshold (`ulimit -f` in KiB; GIF must fit):**

| plot | GIF bytes | smallest `-f` that succeeds | fails at |
|------|-----------|------------------------------|----------|
| `plot sin x` | 8 729 | `-f 9` (9216) | `-f 1,2,4,8` |
| `plot x^2+y^2 heatmap` | 26 603 | `-f 26` (tested `-f 32` OK) | `-f 4,8,16` |

`plot … nofile` is immune at every `-f` (it prints a checksum, writes nothing): verified at
`-f 1,2,4,8` with exit 0.

**Why it matters:** `fwrite`/`fclose` failure on a size-limited file should be detected and
surfaced as a clean `ucas: error: cannot write plot.gif: File size limit exceeded` (exit 2),
with no corrupt file left behind. Instead the default SIGXFSZ action kills the process; in the
agent frontends this also breaks the one-request-per-line protocol.
**Expected:** install a SIGXFSZ
handler / check `ferror()` and report a proper error.

### HANG-1 — `timeout_s` silently ignored when `fork()` fails under `RLIMIT_NPROC`
**Severity:** HANG
_Original classification: `HANG (unbounded execution`._
**Reproducer:**

```sh
cd /tmp/opencode/rlx
python3 -c "
import json
src='f(x: u16) = ((x*5+3)>>2) xor (x>>4)\nstoke f steps 2000000 restarts 8 seed 1'
print(json.dumps({'id':1,'cmd':'ucas','args':{'source':src,'timeout_s':2}}))" > reqC.jsonl
# RLIMIT_NPROC=8 is below the ~460 processes the user already owns, so fork() returns EAGAIN
timeout 12 bash -c 'ulimit -u 8; exec $ROOT/ucas --json' < reqC.jsonl > C.out 2>&1; echo $?
```

**Observed:** `EXIT=124` — the **outer** 12 s timeout had to kill it; `C.out` is **0 bytes
(no JSON response). The 2-second `timeout_s` was never enforced. With a normal `-u`, the same
request returns immediately:

```json
{"id": 1, "ok": false, "cmd": "ucas", "error": {"code": "timeout", "message": "timed out after 2 s; the state is unchanged"}}
```

With a shorter search (200k steps, ~1.7 s) that finishes under `-u 8`, the full result is
returned with `"ok": true`, `"notes": []`, `"error": null` — **no indication that `timeout_s`
was dropped**:

```json
{"id": 1, "ok": true, "cmd": "ucas", ..., "notes": [], ...}
```

Confirmed the limit is real and enforced in this container (`bash: fork: retry: Resource
temporarily unavailable` when -u 8 is set). MCP behaves identically (also silently ignores
`timeout_s` when fork fails).

**Why it matters:** `timeout_s` is the documented mechanism that runs a request in a forked
child and guarantees a wall-clock cap and state isolation. When `fork()` fails, ucas silently
falls back to running the request **in-process, with no timeout** — turning a bounded request
into an unbounded hang and stripping the state-rollback guarantee, with no note or error.
**Expected:** return an `internal`/`failed` error ("cannot fork: Resource temporarily unavailable")
or refuse the request, never silently disable the timeout.

### CRASH-2 — MCP has no crash isolation without `timeout_s`
**Severity:** CRASH
_Original classification: `CRASH (whole server dies; all subsequent calls unanswered`._
**Reproducer:**
Reproducer** (200 nested parens under a 512 KB stack; no `timeout_s`):

```sh
cd /tmp/opencode/rlx
python3 -c "
import json
src='show '+'('*200+'1+2'+')'*200
print('{\"jsonrpc\":\"2.0\",\"id\":0,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"s\",\"version\":\"1\"}}}')
print('{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}')
print(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'ucas','arguments':{'source':src}}}))
print(json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'ucas','arguments':{'source':'show 1+2'}}}))" > reqD.jsonl
timeout 12 bash -c 'ulimit -s 512; exec $ROOT/ucas --mcp' < reqD.jsonl > D.out 2>&1; echo $?
```

**Observed:** `EXIT=139` (SIGSEGV). Only **one** response line (`id:0` initialize) is produced;
the `id:1` tool call and the follow-up `id:2` call both get **no reply**. The process dumps core.

Adding `"timeout_s":5` to the `id:1` call fully isolates the same crash:

```json
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"error (internal): the evaluation crashed (signal 11); the state is unchanged"}], ..., "isError":true}}
{"jsonrpc":"2.0","id":2,"result":{ ... "_() = 3\n  -> int\n" ... }, "isError":false}
```

**Why it matters:** a long-lived MCP server should not be killable by a single client request.
Crash isolation currently depends entirely on the *client* setting `timeout_s`; the common
path (no `timeout_s`) evaluates in-process, so any parser/evaluator crash takes down the server
and leaves every in-flight/queued call unanswered.
**Expected:** fork every tool call by default (or
install signal handlers) so a bad request yields `internal` and the session survives.

### CRASH-3 — long search under `RLIMIT_CPU` is SIGKILLed with no result
**Severity:** CRASH
_Original classification: `CRASH (unclean termination; no diagnostic`._
**Reproducer:**

```sh
cd /tmp/opencode/rlx
# stoke2.ucas: f(x:u16)=((x*5+3)>>2) xor (x>>4); stoke f steps 2000000 restarts 8 seed 1
timeout 15 bash -c 'ulimit -t 1; exec $ROOT/ucas /tmp/opencode/rlx/stoke2.ucas' > E.out 2>&1; echo $?
```

**Observed:** `EXIT=137` (SIGKILL). Output is only the echo and the search header — no result,
no `cpu time limit exceeded` message:

```
> f(x: u16) = ((x*5+3)>>2) xor (x>>4)
> stoke f steps 2000000 restarts 8 seed 1
stoke f under gt1030: Metropolis-Hastings over programs of up to 8 instructions (add sub mul and or xor shl shr not neg),
  8 chains of 2000000 proposals, seed 1; f as written costs 8
```

**Threshold:** wall time to death ≈ `t + 0.8 s` (startup overhead): `-t 1` → 1.8 s, `-t 2` → 2.9 s,
`-t 3` → 3.4 s, `-t 5` → 6.1 s, `-t 8` → 10.1 s; all exit `137`. The kernel sends SIGXCPU at the
soft limit and SIGKILL at the hard limit; ucas installs no SIGXCPU handler, so it never gets a
chance to unwind. A short search (`find32`, `find`+`more`) finishes well under `-t 1` and is fine.

**Why it matters:** an OS CPU cap should produce a clean, actionable error (exit 2,
`ucas: cpu time limit exceeded`), at least in the frontends.
**Expected:** catch SIGXCPU, stop the
search and report gracefully. (Contrast the clean OOM message documented in the sibling
`resource_limits` folder, LIMIT-6.)

### WRONG-1 — CPU-limit SIGKILL in a forked child reported as `internal (signal 9)`
**Severity:** WRONG
_Original classification: `WRONG (misleading error classification`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd /tmp/opencode/rlx
python3 -c "
import json
src='f(x: u16) = ((x*5+3)>>2) xor (x>>4)\nstoke f steps 2000000 restarts 8 seed 1'
print(json.dumps({'id':1,'cmd':'ucas','args':{'source':src,'timeout_s':3}}))" > reqF.jsonl
timeout 12 bash -c 'ulimit -t 2; exec $ROOT/ucas --json' < reqF.jsonl > F.out 2>&1; echo $?
```

**Observed:** `EXIT=0`, the server stays up and replies:

```json
{"id": 1, "ok": false, "cmd": "ucas", "error": {"code": "internal", "message": "the evaluation crashed (signal 9); the state is unchanged"}}
```

With no `-t`, the identical request (2 s CPU limit absent, 3 s wall `timeout_s`) correctly
reports `{"code":"timeout","message":"timed out after 3 s; the state is unchanged"}`.

**Why it matters:** the cause is the external `RLIMIT_CPU` SIGKILL, not an internal evaluation
crash. Classifying it as `internal` suggests a ucas bug and gives the caller no way to
distinguish "host resource limit hit" from "evaluator fault". MCP shows the same
`error (internal): the evaluation crashed (signal 9)`. Low severity because the isolation
itself works and the session survives.

### LIMIT-1 — stack overflow threshold scales with `-s` (graceful → SIGSEGV)
**Severity:** LIMIT
_Original classification: `LIMIT (documented threshold; graceful path exists only below it`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`show (((…1+2…)))` nested-parenthesis depth vs `-s` (KiB), each run under `timeout 15`:

| `-s` (KiB) | deepest depth that succeeds | first depth that SIGSEGVs |
|-----------|-----------------------------|---------------------------|
| 8192 (default) | 1200 (and sibling: 1500) | ~1600–2000 |
| 2048 | 200 | 400 |
| 1024 | 100 | 200 |
| 512 | 50 | 100 |
| 256 | *(none — even depth 50 / plain startup dies)* | 50 |

At/over the threshold: `EXIT=139`, output is just the echoed `> show (((…` line, no result,
no `expression nested too deeply` error. This is the same recursive-parser depth bug as sibling
`resource_limits` CRASH-1, but here the graceful-to-crash boundary is shown to move with the
stack rlimit (≈1 KB of stack per nesting level). See also finding 3 (MCP kill radius) and the
isolation note there. Safe, limit-independent depths (50 at default stack) are kept in
`01_baseline_ops.ucas` / `mcp_limits_baseline.jsonl`.

### LIMIT-2 — FD threshold (`-n`): graceful down to 4, clean loader failure at 3
**Severity:** LIMIT
_Original classification: `LIMIT (positive result — no crash; threshold documented`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
| `-n` | CLI `show` | CLI `plot sin x` (writes plot.gif) | `--json`, `--mcp` |
|------|-----------|------------------------------------|-------------------|
| 32, 16, 8, 4 | exit 0 | exit 0, full 8729-byte GIF written | exit 0 |
| 3 | exit 127 | exit 127 | (exits in loader) |

At `-n 3` the failure is a **clean dynamic-loader error**, not a ucas crash:

**Observed:**
**Reproducer:**
```sh
$ROOT/ucas: error while loading shared libraries: libm.so.6: cannot open shared object file: Error 24
```

(`Error 24` = EMFILE.) So ucas needs only 4 FDs (stdin/stdout/stderr + one) and degrades
gracefully — a reference case showing no SIGSEGV despite an extreme FD squeeze.

### LIMIT-3 — locked-memory limit `-l` is a no-op
**Severity:** LIMIT
_Original classification: `LIMIT (informational`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`ulimit -l 0`, `-l 8`, `-l 64` all produce byte-identical, exit-0 results for CLI `show` and
CLI `plot sin x` (including the full GIF write). ucas does not call `mlock`/`mlockall`, so
`RLIMIT_MEMLOCK` never affects it. (`-l 4294967295` only fails because it exceeds the hard
limit 8192 — a shell/ulimit artefact, not a ucas issue.) Useful negative result: no lock-related
crash surface in this area.

### LIMIT-4 — tight virtual memory (`-v`): SIGSEGV / loader-error / clean-OOM bands
**Severity:** LIMIT
_Original classification: `LIMIT (extends sibling resource_limits CRASH-7 to --json and --mcp`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Same trivial input (`show 1+2`) tested in CLI, `--json` and `--mcp`:

| `-v` (KiB) | CLI | `--json` | `--mcp` |
|-----------|-----|----------|---------|
| 16000, 20000 | SIGSEGV, **0 bytes output** | SIGSEGV, 0 bytes | SIGSEGV, 0 bytes |
| 22000, 24000 | exit 127, `libc.so.6: failed to map segment from shared object` | same | same |
| 26000 | exit 0 | exit 0 | exit 0 |
| 30000, 40000, 60000 | exit 0 | exit 0 | exit 0 |

So the ≈20–23 MB band where the binary starts but dies in an unchecked early allocation
(SIGSEGV, no diagnostic) is present **identically in all three frontends**. A heavier request
(`--json --files write` with `plot sin x`, 8.7 KB GIF) at `-v 26000` exits **2** with the clean
`ucas: out of memory` (expected OOM handling), and succeeds at `-v 30000`. This confirms the
startup SIGSEGV is specific to the tiny-memory band and that the graceful OOM path exists once
the process is up — the gap is the unhandled pre-handler allocation failure.

## Checks that passed

### Summary table
| # | Severity | Title | Limit |
|---|----------|-------|-------|
| 1 | CRASH | SIGXFSZ mid-GIF-write: truncated partial file, no clean error; JSON/MCP lose the whole response | `-f` |
| 2 | HANG / WRONG | `timeout_s` silently ignored when `fork()` fails under `RLIMIT_NPROC` | `-u` |
| 3 | CRASH | MCP server has **no** crash isolation without `timeout_s` — one deep expression kills it | `-s` |
| 4 | CRASH | Long search under `RLIMIT_CPU` is SIGKILLed, no result, no diagnostic | `-t` |
| 5 | WRONG (low) | CPU-limit SIGKILL in a forked child is reported as `internal (signal 9)`, never `timeout` | `-t`+`timeout_s` |
| 6 | LIMIT | Stack overflow threshold scales with `-s`; 1 MB stack tolerates only ~100 nesting levels | `-s` |
| 7 | LIMIT | FD threshold: `-n 4` works (even with plot writes); `-n 3` fails cleanly in the loader | `-n` |
| 8 | LIMIT | Locked-memory limit `-l` is a no-op for this binary | `-l` |
| 9 | LIMIT | Tight virtual memory: SIGSEGV / loader-error / clean-OOM bands, same in CLI, JSON and MCP | `-v` |

No orphaned children were observed: a `timeout_s:2` search that timed out left the in-flight
process count unchanged (14 before, 14 after); the killed child is reaped.

### Reproducers that are *goldens* (limit-independent, deterministic)
The following were each run twice and were byte-identical; they are kept as `.out` tests and
document the normal behaviour that the limit-dependent cases above deviate from:

- `01_baseline_ops.ucas` — show / u8 wrap / isqrt range / parse / diff / exhaustive `equiv`.
- `02_plot_nofile.ucas` — plots with `nofile` (checksums, no disk write; immune to `-f`).
- `03_searches_seeded.ucas` — `find` + seeded `stoke` (deterministic under repeated runs).
- `mcp_limits_baseline.jsonl` — handshake, show, plot `nofile`, define, range, state; all `isError:false`.
