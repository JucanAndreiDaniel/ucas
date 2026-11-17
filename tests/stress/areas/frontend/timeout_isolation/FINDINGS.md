# Stress findings — `timeout_isolation`

_Original heading: Findings — `timeout_isolation`_

# Findings — `timeout_isolation`

Area: the long-search `timeout_s` mechanism itself (CLI `--json` + MCP).
All goldens were run twice and diffed; all four are deterministic.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | `timeout_s` given as a JSON string passes validation but silently disables the limit |
| LIMIT | 2 | non-positive, null-like and non-finite `timeout_s` do not limit the request |

## Findings

### WRONG-1 — `timeout_s` given as a JSON string passes validation but silently disables the limit
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`render_num()` (jsonmode.c:1378) accepts a JSON string as a "constant expression"
for `timeout_s`, so `{"timeout_s":"0.02"}` is accepted. But `json_serve()`
(jsonmode.c:3272) only starts the forked timer when `t->t == J_NUM`. A string
therefore runs the request **without any wall-clock limit**; the documented
"wall-clock limit" is not applied even though the request was accepted.

**Reproducer:**
Reproducer (CLI `--json`, 3 s shell bound):

```sh
cd $ROOT
printf '%s\n' \
 '{"id":1,"cmd":"define","args":{"name":"zz","params":[{"name":"x","type":"u6"}],"body":"x*x*x+47"}}' \
 '{"id":2,"cmd":"gates","args":{"f":"zz","max":45,"nodes":100000000,"timeout_s":"0.02"}}' \
 | timeout 3 ./ucas --json --files none > /tmp/opencode/strto3.out 2>&1
echo "rc=$? lines=$(wc -l < /tmp/opencode/strto3.out)"
```

**Observed:**

```
rc=124 lines=1        # only the define was answered; gates ran past 3 s
```

With the numeric form of the *same* request (`"timeout_s":0.02`) it returns in
~20 ms with `{"id":2,"ok":false,...,"error":{"code":"timeout","message":"timed out after 0.02 s; the state is unchanged"}}`
(`rc=0 lines=2`). A client that follows the API's own hint that strings are
allowed gets no timeout protection. Severity: **WRONG** (accepted value silently
ignored; leads to unbounded execution).

### LIMIT-1 — non-positive, null-like and non-finite `timeout_s` do not limit the request
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`json_serve()` requires `timeout_s` to be a positive JSON number to start the
timer. The following all run the search unbounded (shell `timeout 3` kills it,
`rc=124`, only the earlier `define` response is present):

| value | result |
|-------|--------|
| `0` | no timer, search runs unbounded |
| `-1`, `-0.5` | no timer, search runs unbounded |
| `1e400` (parsed as +Inf) | timer starts but `left = Inf - elapsed` never `<= 0` → never times out |
| `"0.02"` (string) | no timer (see WRONG above) |

**Reproducer:**

**Observed:**
```sh
cd $ROOT
printf '%s\n' \
 '{"id":1,"cmd":"define","args":{"name":"zz","params":[{"name":"x","type":"u6"}],"body":"x*x*x+47"}}' \
 '{"id":2,"cmd":"gates","args":{"f":"zz","max":45,"nodes":100000000,"timeout_s":0}}' \
 | timeout 3 ./ucas --json --files none >/dev/null 2>&1
echo "rc=$?"   # 124 — no 'code: timeout' response
```

`{"timeout_s":null}` and `{"timeout_s":true}` are *rejected* with
`bad_request: timeout_s: a number (or a constant expression as a string)`,
which is correct. This finding is about values that are accepted but do not
protect the caller. Severity: **LIMIT** (documented behaviour is ambiguous; a
caller setting `0` expecting an immediate/implicit timeout gets none).

### LIMIT-2 — 32-bit overflow in the poll wait
**Severity:** LIMIT
_Original classification: `LIMIT (latent, not observed`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`run_with_timeout()` (jsonmode.c:3240) computes the poll wait as
`(int)(left * 1000) + 1`. For large `secs` (e.g. `4294967.3`) the double-to-int
conversion overflows and the wait can become negative (poll = infinite) or a
few milliseconds. The deadline itself is still checked with the un-truncated
`double` `left` on every loop iteration, so the SIGKILL still happens at the
requested time; a `poll` timeout cannot cause an early kill. With successful
requests the child writes its "k" byte and poll returns on POLLIN, so no wrong
result was observed. Recorded here because a future change that relies on the
poll wait for deadline enforcement would break. Severity: **LIMIT** (latent;
no observable misbehaviour in the tested range).

## Checks that passed

### Verified-correct behaviour (no golden risk)
- A timed-out request returns an error with `error.code == "timeout"` and message
  `timed out after <secs> s; the state is unchanged`. In MCP the response has
  `isError: true` and `structuredContent.error.code == "timeout"`.
- Session state is untouched by a timeout: define a function, time out 1–20
  searches, then `show`/`state` still see the function and the active model /
  assumptions. A timed-out `approx … name MADE1` did **not** define `MADE1`.
- Subsequent calls in the same process work (both before and after timeouts).
- `reset` with `timeout_s` works and the following call sees empty state.
- No child-process leak: with a live stdin, after 20 timeouts there was exactly
  **one** direct child (the chained server); workers are SIGKILLed and reaped.
  After EOF no process from my tree remained.
- No crashes and no wrong error codes from any of the 156 long searches.

### Notes / non-issues
- `gates` only accepts ≤ 6 input bits; `find` on a float result needs one
  float parameter. These are normal validation errors from the search itself,
  not timeout bugs. The corpus was adjusted to use valid 6-bit functions.
- `table F max 4194304` and `range` on ordinary functions complete too quickly
  to time out; the corpus uses `gates … nodes 4194304` (the 2^22 synthesis cap
  in `cf_bridge.c`) and an expensive real function for `range` instead.
- No forked child was observed to outlive its session, and no request returned
  `error.code == "internal"` (the crash path) in this area.
