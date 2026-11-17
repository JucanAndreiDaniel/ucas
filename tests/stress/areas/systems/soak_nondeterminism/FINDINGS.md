# Stress findings — `soak_nondeterminism`

_Original heading: FINDINGS — soak_nondeterminism_

# FINDINGS — soak_nondeterminism

Harness: `soak.py` (phases `calibrate`, `golden`, `live`, `report`).
Standalone reproducers: `repro_fd_leak.py`, `repro_timeout_desync.py`.
Raw logs: `soak_golden.jsonl` (8,800 records), `soak_live.jsonl` (8,000 records),
`soak_findings.json`, `work/calibration.json`, `work/golden_run.log`, `work/live_run.log`.

Everything below was produced with the already-built `$ROOT/ucas`.
No sibling folder, source file, Makefile or `opencode.json` was modified.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 3 | Repeated `reset` leaks one file descriptor per call in both long-lived frontends |
| DETERMINISM | 1 | `timeout_s` corrupts the long-lived response stream (ok flapping / wrong ids / call-order … |

## Findings

### DETERMINISM-1 — `timeout_s` corrupts the long-lived response stream (ok flapping / wrong ids / call-order dependence)
**Severity:** DETERMINISM
A `--json` or `--mcp` process answers one line per request. After requests that
carry the `timeout_s` option ("the request runs in a forked child"), the reply
stream **desynchronises**: replies arrive with the wrong `id`, and a subsequent
completely deterministic request (`bigint 2^200 + 1`, which always succeeds) is
answered with an error (`ok:false`). The fork's child is not killed and its
eventual output is emitted onto the same stdout, so answers come to depend on
request order and on timing. This is exactly the rare, order-dependent drift the
soak was built to catch: the 4,000-iteration live run produced **113 canary-drift
and 190 stateful-drift events**, and `j_bigint` (a pure command) was observed
`ok:false` 87 times and `ok:true` 142 times.

**Reproducer:**
Reproducer (copy-pasteable):

**Observed:**
```sh
cd $ROOT/tests/stress/areas/systems/soak_nondeterminism
python3 repro_timeout_desync.py 60
```

The script sends 60 `[ english "factor (x+1)^20" with timeout_s=0.001 , bigint 2^200+1 ]`
pairs to one long-lived `--json` process and checks that each reply's `id`
matches its request's `id`.

**Exact observed output:**

```
pairs=60  desynced_pairs=58
first desync (cycle, timeout_req_id, timeout_resp_id, timeout_ok, bigint_req_id, bigint_resp_id, bigint_ok):
   (2, 5, 5, True, 6, 5, False)
lingering child processes after 60 timeouts: 1
```

That is: request id 5 (the timeout request) got reply id 5 with `ok:true`; the
**next** request, id 6 (`bigint 2^200 + 1`), got reply id 5 with `ok:false`.
Request 6 never received its own reply before request 7 was read.

The same happens on the MCP wire. Driving `--mcp` with 60
`{"name":"english","arguments":{"text":"factor (x+1)^20","timeout_s":0.001}}`
calls interleaved with `{"name":"ucas","arguments":{"source":"bigint 2^200 + 1"}}`:

```
MCP pairs=60 desync= 51 first= (9, 19, 19, True, 20, 19, False)
```

Under the main live workload the desynchronised stream is what produced the
`ok` flapping and stateful-script drift, e.g.:

```
LIVE_OK_FLAPPING  iface=json tag=j_bigint  counts={"false": 87, "true": 142}
LIVE_STATEFUL_DRIFT iface=json i=2200 step=assume \
  base={"cmd":"reset",...} now={"cmd":"assume","result":{"assumptions":{"log":"base 2"},...},...}
```

**Why it matters:** it is a bug / expected:** one request must yield exactly one response,
with the matching `id`, and a pure command must not flip `ok`. A client that
pipelines requests over a single long-lived process (the documented use of
`--json`/`--mcp`) gets wrong answers and cannot trust the stream after any
`timeout_s` call.
**Expected:** the timeout produces a single timeout reply, the
forked child is killed, and no later reply is corrupted.

### LIMIT-1 — Repeated `reset` leaks one file descriptor per call in both long-lived frontends
**Severity:** LIMIT
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/systems/soak_nondeterminism
python3 repro_fd_leak.py 200
```

**Exact observed output:**

```
json: FDs start=3 end=203 peak=203 delta=+200 after 200 resets
mcp : FDs start=4 end=203 peak=203 delta=+199 after 200 resets
```

A controlled trace confirms linear growth and that it is specific to `reset`:

```
JSON reset x100:        fd 3 -> 104 (delta 101), first=[3,4,5,6,7,8,9,10]
MCP session-reset x100: fd 4 -> 103 (delta 99),  first=[4,4,5,6,7,8,9,10]
JSON define-unique x60: fd 3 -> 4  (delta 1)   # plateaus
MCP define-unique x60:  fd 4 -> 4  (delta 0)   # plateaus
```

Other commands (`bigint`, `english`, `state`, `assume`, defining functions) all
plateau at a fixed FD count; only the reset path grows without bound.

**Why it matters:** it is a bug / expected:** a long-lived session that resets between tasks
(`session reset` is the documented way to drop definitions) leaks a descriptor
each time. With the common `ulimit -n 1024` this reaches `EMFILE` after ~1,000
resets and the process can no longer open files/pipes.
**Expected:** FD count stays
flat across resets. (This machine's limit is 1,048,576, so exhaustion was not
reached here, but the growth is strictly linear and unbounded.)

### LIMIT-2 — Timed-out `timeout_s` forked child is not killed (process leak)
**Severity:** LIMIT
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/systems/soak_nondeterminism
python3 - <<'PY'
import json,subprocess,select,time,os
p=subprocess.Popen(["$ROOT/ucas","--json","--files","none"],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
p.stdin.write(json.dumps({"id":100,"cmd":"english",
  "args":{"text":"factor (x+1)^20","timeout_s":0.001}})+"\n");p.stdin.flush()
select.select([p.stdout],[],[],8); p.stdout.readline()
time.sleep(1)
print(subprocess.run(["ps","--ppid",str(p.pid),"-o","pid,stat,etime,cmd"],
      capture_output=True,text=True).stdout)
p.kill();p.wait()
PY
```

**Exact observed output** (the parent replies "timed out after 0.001 s" but the
child is still running 20 s later):

```
    PID STAT     ELAPSED CMD
2573782 S          00:20 $ROOT/ucas --json --files none
```

**Why it matters:** it is a bug / expected:** the timeout contract says "the request runs in a
forked child and the state is unchanged on a timeout"; the worker should be
terminated when the deadline fires. Here it keeps consuming CPU and, because it
inherits stdout, is the source of the stale/duplicate reply lines that cause
finding 1.
**Expected:** the child is reaped/killed on timeout.

### LIMIT-3 — Heavy SAT goldens occasionally exceed `timeout 15` (timing variance; not content drift)
**Severity:** LIMIT
Two randomness/budget-driven SAT goldens completed in well under 15 s on most
runs but exceeded 15 s on some runs of the same input. The siblings generated
these goldens under `timeout 30`, so this is borderline runtime, not a wrong
answer: **every run that completed produced byte-identical output** — the
"drift" reported by the probe was only truncation at the timeout boundary.

**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/sat_crypto_circuits
for i in $(seq 1 10); do
  timeout 15 $ROOT/ucas --mcp < mcp_sat_crypto.jsonl > /tmp/o 2>&1
  echo "rc=$? lines=$(wc -l < /tmp/o)"
done
cd ../sat_ranges_where
for i in $(seq 1 10); do
  timeout 15 $ROOT/ucas --mcp < mcp_sat_ranges_where.jsonl > /tmp/o 2>&1
  echo "rc=$? lines=$(wc -l < /tmp/o)"
done
```

**Exact observed output (excerpt):**

```
sat_crypto_circuits/mcp_sat_crypto: reps=10 distinct=2 drift_runs=2
  ANOMALY rep=1 rc=-99 timeout=True   (complete runs: 1 distinct sha)
sat_ranges_where/mcp_sat_ranges_where: reps=10 distinct=2 drift_runs=8
  ANOMALY rep=0 rc=-99 timeout=True
  ANOMALY rep=4 rc=-99 timeout=True
```

**Why it matters:** it is a bug / expected:** a reproducible single input has strongly varying
wall-clock time near the 15 s mark (SAT budget/heuristic), so a stricter runner
can see a "hang" on one run and success on the next.
**Expected:** either bounded
runtime or a documented fixed seed/budget. No unsound or differing answer was
observed in completed runs, so this is recorded as LIMIT, not DETERMINISM.

## Checks that passed

### Negative results (searched, nothing found)
* **8,800 golden repetitions** — 110 distinct sibling goldens × 80 runs each,
  every run under `timeout 15`, compared both to the stored `.out` and to the
  first run of the same case: **0 run-to-run drift, 0 `.out` mismatches, 0
  crashes, 0 timeouts** (`work/golden_run.log`, `soak_golden.jsonl`).
* **9 randomness-prone goldens** (`find`, `stoke`, `gates`, `approx`, `phash`,
  SAT budgets) × 10 runs each: completed runs byte-identical (see finding 4 for
  the timeout-only cases).
* **Memory** — RSS of both long-lived processes stayed in ~5–18 MB with no
  upward trend across 4,000 calls (`LIVE_RESOURCE_SUMMARY`: json rss first
  11452 / last 5320 KB, mcp rss first 9668 / last 5576 KB).
* **Process death / hangs** — 0 `LIVE_PROC_DIED`, 0 read timeouts, 0 `ok`
  changes attributable to the binary itself in the live run (all drift traced
  to finding 1).
