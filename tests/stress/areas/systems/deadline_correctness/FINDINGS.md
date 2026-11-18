# FINDINGS — `deadline_correctness`

Area: time budgets in the C frontend bridge (`cf_bridge.c`), the MMA search
(`mma.c`) and the JSON/MCP timeout worker (`jsonmode.c`).  Goldens were
captured from the fixed binary with `UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`
and checked byte-identical on repeated runs.

## Summary

| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 0 | no wrong proof or answer introduced |
| CRASH | 0 | no signal exit in any repro |
| HANG | 0 | both searches now have a deadline; every reply is prompt |
| LIMIT | 2 | honest "budget exhausted" / "timed out" results are reported |

## Findings

### 1. `c optimize budget 2`: find's deadline was floored at 60 s (fixed)

`cf_bridge.c` passed `secs > 60 ? secs : 60` to `find_cands()`.  `eng_left()`
hands the engine its share of the CPU budget (with all engines on, budget 2
gives find about 0.43 s), but the floor turned that into 60 s, so the 14-19 s
runs reported in `FUZZ_C` were possible.  The bridge now passes the real
share through with a 0.5 s minimum.  `find.c`'s own level/deadline checks
were left alone — they already honour the `seconds` argument.

The golden records the stable result, not a timing.  On this host the whole
`c optimize` command still spends about 4 s in *candidate proof* after find
returns (see Remaining below); find's own enumeration is cut to its share.

### 2. `mma` with no budget ran 13-17 s (fixed)

`mma.c` had no internal deadline.  It runs two full searches (the main one,
and a second "what if wide shared accesses were cheaper" comparison); each
took ~6 s.  A caller with a 5 s client timeout saw no reply at all.

Both searches now share one absolute `CLOCK_MONOTONIC` deadline, default
3.5 s (`mma ... seconds N`, `N = 0` asks for the full search).  The check is
in `keep()` and in the expensive reduction paths (`red_plan`, the blocked
search loops) so a long inner loop cannot overshoot.  When a search is cut
the header says "search budget exhausted after 3.5 s", an explicit line says
the best dataflow found so far is shown and that a cheaper one may exist,
and structured output carries `"search": "budget exhausted"` instead of a
`tried` count.  That is an honest LIMIT, not a false "no dataflow" result.

Measured (fixed binary, this host): CLI `mma nofile` 3.51 s, `--json` mma
3.51 s, both with the budget message.  With `seconds 0` the original 10 s
search and its `8488 dataflows tried` header return unchanged.

### 3. `timeout_s` and a stalled reply body (fixed, not reproducible as a golden)

`jsonmode.c`'s `run_with_timeout()` used blocking `read()` for the u64
length header and the reply body after `poll()`.  A worker that wrote the
header and then stalled could hold the parent well past `secs`.

The parent now carries one absolute deadline through the whole exchange.
`rd_all_until()` polls with the remaining time before every read and returns
a distinct `-2` for a deadline, which takes the same honest "timed out after
N s; the state is unchanged" path as the poll-loop expiry.  EOF/partial
replies still take the `corrupt` path; the probe-byte distinction from
JSONMODE_RACE_FIX.md is preserved.

`json_timeout_slow.jsonl` exercises `timeout_s:0.5` on `mma` (a slow command)
and checks that the next request gets the right id and an unchanged state.
A mid-body stall needs the worker to be paused between two `write()` calls;
the canonical runner captures a worker's whole reply into a memstream first,
so there is no input that produces that schedule.  No golden can cover it;
the fix is in the read helper itself.

## Checks that passed

- `bmake` build, repeated (with unrelated agents editing other sources).
- 4 goldens in this area, byte-identical over 3 consecutive stress runs.
- `mma nofile` and `--json` mma reply in ~3.5 s with an honest budget message.
- `c optimize budget 2` no longer gives find a 60 s deadline.
- `bmake stress-test STRESS_AREA=timeout_isolation` — 4 goldens pass.
- `bmake stress-test STRESS_AREA=timeout_s_systematic` — 3 goldens pass.
- `bmake stress-test STRESS_AREA=cfront_fuzz` — 30 goldens pass.

## Existing goldens needing recapture (not edited here)

The new mma default changes the output of every golden that runs mma without
`seconds 0`.  Empirically these 5 differ and need `make accept` / `stress-accept`
by their owner:

- `tests/mma.out`
- `tests/mma_validate.out`
- `tests/json/mma.out`
- `tests/stress/areas/gpu/mma_army/01_mma_basic.out`
- `tests/stress/areas/gpu/mma_army/02_mma_variants.out`

No other golden changed in the areas checked.  The area index `AREAS.md`
also needs a `deadline_correctness — 4 goldens` line added under `systems`.

## Remaining, out of scope

- Candidate *proof* time in `cf_opt.c`/`cf_check.c` is not bounded by
  find's share: on this host `c optimize budget 2` still takes ~4 s wall
  after find returns (and ends with an honest "0 rewrites proved").  That
  is a different deadline from the one this task fixed.
- A wall-clock budget makes the partial mma result depend on host speed: a
  machine several times faster could finish the search inside 3.5 s and
  print the full-search golden instead.  Captured goldens are from this host.
