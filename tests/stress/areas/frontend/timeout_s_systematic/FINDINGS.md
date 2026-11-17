# Stress findings — `timeout_s_systematic`

_Original heading: Findings — `timeout_s_systematic`_

# Findings — `timeout_s_systematic`

Systematic follow-up on **MASTER_FINDINGS Top priority #2** (confirmed timeout-child
reply-stream desync). All work used the already-built `$ROOT/ucas`;
no source, Makefile, sibling folder or shared file was touched.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | string `timeout_s` silently disables limit across 3 interfaces / 8 families |
| LIMIT | 2 | zero/negative/huge timeouts disable limit; stray workers/children |
| DETERMINISM | 1 | timeout-child desync, ~85% at 0.0005 s timeout; all 3 interfaces |

## Findings

### DETERMINISM-1 — timeout-child desync confirmed in all three interfaces
**Severity:** DETERMINISM
and replies carry the wrong `id`). This independently re-confirms the orchestrator's finding and
extends it to MCP `--flat`.

The worker forked by `timeout_s` (`jsonmode.c:3206-3215`) writes its success reply to stdout
*before* signalling the waiter; when the deadline lands at the same instant the waiter also
writes a timeout reply with the **same id**. One request then yields two replies and every later
reply is shifted by one. The race window is widest when `timeout_s` ≈ the request's own runtime:
`english "factor (x+1)^20"` takes ~0.3 ms, so a **sub-millisecond** `timeout_s` (0.0005 s) desyncs
30-40 of 40 pairs.

**Reproducer:**
Reproducer (copy-pasteable):

**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/timeout_s_systematic
python3 repro_desync_systematic.py 40 all
```

**Exact observed output (one run):**

```
pairs=40  timeout_s=0.0005  op=english 'factor (x+1)^20'
  json : desync=33/40  extra_reply_lines=14  codes={'timeout': 25}
         first: cycle=7 timeout_req=16 timeout_reply=16 bigint_req=17 bigint_reply=16
  mcp  : desync=35/40  extra_reply_lines=10  codes={'timeout': 28}
         first: cycle=5 timeout_req=12 timeout_reply=12 bigint_req=13 bigint_reply=12
  flat : desync=35/40  extra_reply_lines=11  codes={'timeout': 26}
         first: cycle=5 timeout_req=12 timeout_reply=12 bigint_req=13 bigint_reply=12
```

Rates vary with load (the harness's own focused probe saw `json 0/40, mcp 34/40, flat 0/40` in
one run), which is the point: the stream is timing-dependent and cannot be trusted after a
`timeout_s` call.

**Exact raw lines around the first desync (CLI `--json`):**

```
CYCLE 6: timeout REQ id=14, bigint REQ id=15
TIMEOUT REPLY: {"id": 14, "ok": true, "cmd": "english", ... "text": "factor (x + 1)^20\n  = ...
BIGINT  REPLY: {"id": 14, "ok": false, "cmd": "english", "error": {"code": "timeout",
                "message": "timed out after 0.0005 s; the state is unchanged"}}
```

The timeout request (id 14) got **two** replies — first the worker's `ok:true`, then the waiter's
`code:timeout`; the pure `bigint 2^200+1` request (id 15) got no reply of its own. A client reading
one line per request therefore sees a deterministic command "fail" with another request's id.

**Characterization (new):** the race needs `timeout_s` near the request runtime. In the 216-stream
matrix, every numeric timeout used `gates … nodes 100000000, timeout_s:0.02` — a request that
always runs far longer than the deadline — and produced **0 id mismatches / 216 streams** and a
clean `code:timeout` in 36/36. With a tiny timeout on a fast request the same environment desyncs
at ~85% (above). So the bug is reproducible but strongly parameter-dependent.

**Why it matters:** one request must yield exactly one reply with the matching `id`, and a pure
command must not flip `ok`.
**Expected:** the timeout produces one timeout reply, the worker is killed,
and the stream stays aligned.

### WRONG-1 — string `timeout_s` silently disables the limit (all 3 interfaces, 8 command families)
**Severity:** WRONG
**Expected:** _not recorded_
(reported there for CLI `--json` only) **extended to MCP grouped, MCP `--flat`, and to 8 command
families**.

`render_num()` accepts a JSON string as a constant expression, but `json_serve()` starts the timer
only when `timeout_s` is a JSON number, so `{"timeout_s":"0.05"}` runs the search with no wall-clock
limit. In the family sweep, **no** string-timeout request ever returned `code:timeout`.

**Reproducer:**
Reproducer (CLI `--json`, 3 s shell bound):

**Observed:**
```sh
cd $ROOT
printf '%s\n' \
 '{"id":1,"cmd":"define","args":{"name":"zz","params":[{"name":"x","type":"u6"}],"body":"x*x*x+47"}}' \
 '{"id":2,"cmd":"gates","args":{"f":"zz","max":45,"nodes":100000000,"timeout_s":"0.05"}}' \
 | timeout 3 ./ucas --json --files none > /tmp/opencode/strtimeout.out 2>&1
echo "rc=$? lines=$(wc -l < /tmp/opencode/strtimeout.out)"   # rc=124, only the define answered
```

With the numeric form of the same request (`"timeout_s":0.05`) it returns in ~50 ms with
`{"id":2,...,"error":{"code":"timeout",...}}` (`rc=0, lines=2`). The identical gap exists on MCP
grouped and MCP `--flat`; see `family_timeout_sweep.py` for 8 command families.

**Exact observed output of `family_timeout_sweep.py` (excerpt, identical for json/mcp/flat):**

```
  gates    numeric=timeout OK             string=HANG/ignored
  equiv    numeric=timeout OK             string=HANG/ignored
  approx   numeric=timeout OK             string=HANG/ignored
  parse    numeric=timeout OK             string=HANG/ignored
  find     numeric=timeout OK             string=fast/no-limit   (limit still ignored)
  fit      numeric=timeout OK             string=fast/no-limit
  prove    numeric=timeout OK             string=failed          (fails before limit matters)
```

**Why it matters:** the API accepts the string form (its own hint says a constant-expression
string is allowed) but gives no timeout protection. A caller who follows that hint gets unbounded
execution.

### LIMIT-1 — zero, negative and huge `timeout_s` do not limit the request (all 3 interfaces)
**Severity:** LIMIT
**Expected:** _not recorded_
the timer only for a positive finite JSON number. In the 216-stream matrix,

**Observed:**
**Reproducer:**
```sh
string  variant: hung=36/36, has_timeout_code=0/36
zero    variant: hung=36/36, has_timeout_code=0/36
negative variant: hung=36/36, has_timeout_code=0/36
huge (1e9) variant: hung=36/36, has_timeout_code=0/36
```

All 144 such streams left the reply stream truncated at the long-search request (no reply for
that request or any later one within the 1.2 s read deadline); the shell always had to kill the
process. Numeric positive timeouts, by contrast, produced `code:timeout` in **36/36** streams and
the following canaries were answered correctly.

**Why it matters:** it is a bug / expected:** a caller setting `0`, a negative value, or an enormous value
expects an immediate / bounded / effectively-unlimited-but-explicit limit; instead the documented
wall-clock limit is silently absent. Consistent with `timeout_isolation`, now confirmed across
MCP grouped and `--flat` too.

### LIMIT-2 — timed-out workers linger as stray children
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
contained live children:

**Observed:**
**Reproducer:**
```sh
children distribution over 216 streams: {0: 150, 1: 30, 2: 36}
```

One child is the chained server created by `chain_start()` (`jsonmode.c:3155-3182`); the second is a
worker that survived its deadline. This is the same non-reaped-worker leak reported by
`soak_nondeterminism`, reproduced here on the wire for `--json`, MCP grouped and `--flat`.

## Checks that passed

### Harness and coverage
- `systematic_harness.py` — generates and runs **216 request streams** = the full cross
  product `{no timeout, numeric, string, zero, negative, huge}` × `{CLI --json, MCP grouped,
  MCP --flat}` × `{single, N requests after timeout, timeout interleaved with define/English,
  two timeouts in a row, timeout then crash, timeout then reset}` × 2 repetitions.
  Per stream it measures one-response-per-request, id correctness, session-state equality,
  live stray children, `error.code == "timeout"`, and post-timeout canary behaviour.
  Raw measurements: `_scratch/results.json`.
- `repro_desync_systematic.py` — standalone, high-rate desync reproducer (all 3 interfaces).
- `family_timeout_sweep.py` — per-command-family check that a numeric `timeout_s` is honoured.
- `_scratch/hunt_desync.py` — timing sweep that located the reliable trigger.

Golden files (all deterministic; `gate` times out with a comfortable 0.05 s margin so no race):

| file | interface | verification |
|---|---|---|
| `json_numeric_timeout.jsonl/out` | CLI `--json` | 6/6 runs byte-identical |
| `mcp_numeric_timeout.jsonl/out` | MCP grouped | 6/6 runs byte-identical |
| `mcp_flat_numeric_timeout.jsonl/out` (+`.flags`) | MCP `--flat` | 6/6 runs byte-identical |

Each golden: define `zz`, capture `state`, a `gates … timeout_s:0.05` request (→ `code:timeout`),
capture `state` again (unchanged), `show zz` (still present).

### 5. Non-findings / verified correct
- Session state is **unchanged** by a numeric timeout: in every non-crash, non-reset numeric
  stream the `state` reply before and after the timeout was byte-identical (`state_same:True` in
  48 clean streams), and `show zz` still succeeded. A timed-out `gates` did not define or drop
  anything.
- `reset` after a timeout behaves normally; the state comparison correctly shows the intentional
  wipe (12 reset streams with `state_same:False`).
- A deep-nesting `parse` (2000 parens) sent **with** a numeric timeout is contained as
  `code:timeout` and the following call still works; **without** a timeout it crashes the whole
  server (known from `parser_json_fuzz`), after which no later reply arrives — handled safely by
  the harness.
- No crashes, malformed envelopes or wrong error codes were observed from the timeout mechanism
  itself; the only `code` values seen on numeric timeouts were `timeout`.

### Summary of severities
| severity | count | headline |
|---|---|---|
| DETERMINISM | 1 (critical) | timeout-child desync, ~85% at 0.0005 s timeout; all 3 interfaces |
| WRONG | 1 | string `timeout_s` silently disables limit across 3 interfaces / 8 families |
| LIMIT | 2 | zero/negative/huge timeouts disable limit; stray workers/children |
