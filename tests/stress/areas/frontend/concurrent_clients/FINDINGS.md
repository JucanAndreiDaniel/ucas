# Stress findings — `concurrent_clients`

_Original heading: FINDINGS — concurrent_clients (interleaving & state isolation)_

# FINDINGS — concurrent_clients (interleaving & state isolation)

Scope: multiple clients of one long-lived `ucas --mcp` process, plus concurrent
`--json` CLI runs. All runs bounded by `timeout 15`. Harness: `harness.py`.

**Bottom line:** with a correct client-side demultiplexer (route replies by the
echoed `id`) I found **no crossed answer, no wrong `id`, no deadlock, no crash,
and no unsound result** across 2–4 interleaved clients and a few dozen requests,
including >PIPE_BUF concurrent writes. Every issue below is a **LIMIT** — a
documented isolation/serialization characteristic of the single-process stdio
transport, not a correctness bug in the algebra engine.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 4 | 1 — State is process-global: no isolation between clients of one process |

## Findings

### LIMIT-1 — 1 — State is process-global: no isolation between clients of one process
**Severity:** LIMIT
_Original classification: `LIMIT (design; state leak between logical clients`._
**Expected:** _not recorded_
A single `ucas --mcp` process owns **one** session. Definitions, session-wide
`assume` answers, the active cost model, and `session reset` are shared by every
client talking to that process. A function defined by client A is immediately
visible to client B, and an assumption set by A silently changes how B's
ambiguous expressions are parsed. Conversely, a `reset` by A drops B's state.

**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/concurrent_clients
timeout 15 python3 harness.py state_share
# deterministic single-stream version:
timeout 30 $ROOT/ucas --mcp < mcp_state_share.jsonl
```

**Exact observed output (harness):**
```
B sees A's function: 'shared_a(x: u8) = x + 1\n  -> u8\n'
B ambiguous after A's assume: True '{"text": ""}' notes: [{'kind': 'assumed', 'text': '"^" between integers, next to bitwise operators: power (args.assume.caret)'}]
B after A's reset: '_(shared_a: real) = shared_a\n  -> real\n'
B caret expr after reset: False 'error (ambiguous): "^" between integers, next to bitwise operators\n...'
```
`mcp_state_share.out` confirms the same: id 2 shows `shared_a` after A defined it;
id 4 succeeds under A's `caret=power` assumption (note `assumed`); id 6 shows the
definition gone after A's reset; id 7 is again `ambiguous`.

**Why it matters:** it matters / expected:** expected for a single session (definitions
persist across calls), but there is **no per-client namespace**. Multi-tenant
use of one process cannot isolate state; `reset` from one client is global.
Clients must coordinate or use separate processes.

### LIMIT-2 — 2 — Single-threaded serialization: a long request blocks all other clients
**Severity:** LIMIT
_Original classification: `LIMIT (head-of-line blocking`._
**Expected:** _not recorded_
The process handles requests strictly one at a time. A long request from client A
(with an internal `timeout_s`) blocks short requests from client B for the whole
duration of A's request, even though B's request is trivial.

**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/concurrent_clients
timeout 15 python3 harness.py longshort
```

**Exact observed output:**
```
A long reply after 3.02s: 'error (timeout): timed out after 3 s; the state is unchanged'
B latencies: ['2.82s', '0.00s', '0.00s']
eof=False rc=None
```
Client A's `stoke` (timeout_s=3) occupies the process; B's first `expand` waits
~2.82 s and only returns after A's request completes. The next two B requests
are instant. `reset_inflight` shows the same serialization and that the reset is
applied only after the long request finishes (A timed out cleanly, "state is
unchanged"; server stayed healthy).

**Why it matters:** it matters / expected:** expected for a single stdio server with one
worker, but it is a real limitation for interactive multi-client use — one
client's long search freezes every other client. `timeout_s` (when placed inside
`args`, e.g. `args:{"steps":8e6,"timeout_s":2}`) caps the offending request at
~2 s so the block is bounded; note that putting `timeout_s` at the wrong level
(next to `args`, not inside it) is silently ignored and the request runs to
completion (a 5M-step `stoke` ran >12 s). That parameter-placement trap is worth
knowing.

### LIMIT-3 — 3 — No per-client channel: duplicate ids collide; replies arrive in request order
**Severity:** LIMIT
_Original classification: `LIMIT (answer-routing hazard; not a server bug`._
**Expected:** _not recorded_
The server echoes each request's `id` verbatim and emits replies in **request
arrival order**. There is no connection/session id in the protocol. Two
independent clients that each start their id counter at 1 produce two replies
that both carry `id:1`. A client that demultiplexes only by `id` cannot attribute
a reply to itself, and a naive client that reads "the first reply after I sent"
can be handed the other client's answer.

**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/concurrent_clients
timeout 15 python3 harness.py dup_id
```

**Exact observed output:**
```
replies received for id=1: 2
  reply[0]: id=1 text='error (timeout): timed out after 2 s; the state is unchanged'
  reply[1]: id=1 text='expand (x + 770001)^2\n  = x^2 + 1540002x + ...'
```
Both replies have `id=1`; the slow request sent first is answered first, so a
client keying only on id sees an ambiguous bucket. In an earlier direct-read
variant, one naive client actually received the *other* client's `expand`
answer (marker `770001`) — a real crossed answer from the client's point of view.

**Why it matters:** it matters / expected:** the engine is correct — it echoes the right id.
The hazard is transport-level: multi-client use requires a multiplexing layer
that (a) assigns globally unique ids and (b) demultiplexes by id. `id_echo`
demonstrates that with distinct id ranges (1000+/2000+/3000+) and a demux layer,
0/24 replies are crossed and 0/24 ids are wrong.

### LIMIT-4 — 4 (informational) — Large interleaved writes are tolerated
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Two clients writing JSON lines far larger than `PIPE_BUF` (120 000-byte `pad`
field) concurrently, without a client-side write lock, produced **no** malformed
JSON, no crash, and no crossed answers.

**Reproducer:**
Reproducer / output:
**Observed:**
```sh
timeout 15 python3 harness.py large_interleave
# requests=12 missing=0 wrong_marker=0 badjson_lines=0 ; eof=False rc=None
```
Deterministic golden `mcp_id_echo.jsonl` (8 distinct ids/markers) and
`mcp_state_share.jsonl` both diff clean across two runs.

## Checks that passed

### Checks that PASSED (no finding)
- **id echo / no crossed answers** — `id_echo` 3×: 24/24 correct each time; a
  4-client × 8-request run (32 reqs): 0 missing, 0 crossed, 0 wrong ids.
- **Two processes at once, grouped + flat** — `twoproc_flat`: both serve
  concurrently; `only_g` is invisible in the flat server and `only_f` is
  invisible in the grouped server (full process isolation). A second
  `initialize` on a live process does not reset state.
- **Rapid connect/disconnect** — `reconnect` (8 cycles): all initialize replies
  received, all processes exit rc=0, harness leaves no stray processes
  (count unchanged 108→108).
- **Client disconnect mid-flight** — `disconnect_midflight`: closing stdin
  during a 3 s request lets the server finish and exit cleanly (rc=0) in ~2.8 s.
- **Concurrent CLI runs sharing `--dir`** — `concurrent_dir` (6 read-only
  `--json` runs): 0 failures. `concurrent_dir_files` (4 CLI runs plotting to
  the *same* filename in one shared dir): all rc=0, output file intact
  (`GIF89a`, 8944 bytes). No file-write race observed.
