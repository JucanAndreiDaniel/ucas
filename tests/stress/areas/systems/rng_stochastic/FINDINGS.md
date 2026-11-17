# Stress findings — `rng_stochastic`

_Original heading: rng_stochastic — findings_

# rng_stochastic — findings

Area: statistical / reproducibility testing of ucas's stochastic commands
(`find`, `stoke`, `approx`, `fit`, `numsearch` internals, `pit`, `phash`,
`adamfit`, QMC sampling in `range`/`error`/`integrate`).

Binary: `$ROOT/ucas` (not rebuilt).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 2 | `approx ... search anneal|cmaes` exceeds the 30 s stress budget on moderate targets |
| DETERMINISM | 1 | `adamfit` emits a wall-clock timing line, so identical seeded runs differ |

## Findings

### DETERMINISM-1 — `adamfit` emits a wall-clock timing line, so identical seeded runs differ
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (golden-breaking`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
for i in 1 2 3; do
  printf 'adamfit cos(x) in 0..1 count 40 steps 20 seed 7 list 1\n' | ./ucas | tail -1
done
```

**Observed:** output (last line of three consecutive runs):

```
  0.50 s
  0.48 s
  0.51 s
```

A later (warm-cache) repeat gave `0.22 s / 0.20 s / 0.25 s`.  Every other
line of the output is byte-identical across runs with the same `seed`; only
the trailing `%.2f s` differs.  `md5sum` of the full output differs on every
run.

**Why it matters:** `src/stoch.h` states *"Every search is seeded: `seed K`,
else UCAS_SEED, else 1"* and `src/stoch.c` documents *"the same seed gives the
same run."*  `adamfit` violates that: its final line is nondeterministic, so
no golden `.out` can be kept for it and a seeded run cannot be byte-reproduced.
The runtime itself has an escape hatch — setting `UCAS_NO_TIMES=1` removes the
line and the output becomes fully reproducible (verified: 3 identical md5s) —
but the default CLI behaviour is nondeterministic and the variable is not
mentioned in `adamfit`'s help (`src/adamfit.c:2920-2921`).

**Note:** `adamfit` also does not echo the seed it used, unlike `stoke`, `pit`,
`phash`, `approx search ...` and QMC fallback, all of which print `seed K`.
A user cannot recover the seed from a reported fit.  (Low severity, included
here rather than as a separate finding.)

### LIMIT-1 — `approx ... search anneal|cmaes` exceeds the 30 s stress budget on moderate targets
**Severity:** LIMIT
_Original classification: `LIMIT (long-running; not an infinite loop`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf 'f(x: real) = exp(x)\napprox f in -1..1 degree 4 search anneal seed 7\n' \
  | timeout 60 ./ucas
# (same with `search cmaes`)
```

**Observed:** exit code **124** after 60 s, with only ~11 lines of partial
output; the process is killed mid-line (`piecewise (2 pieces split at 0,
max rel error): 1: 0.0616` with no trailing newline).  Because the kill point
depends on wall time, two `timeout 30` runs of this command produce *different
truncated outputs* (different md5s) — the apparent "nondeterminism" is purely
the timeout cutting at different points.

The search is seeded and terminating in principle (`numsearch.c` fixes the
budget at 2000 evaluations) but each evaluation is expensive; simpler targets
finish: `sin(x)` degree 1 in ~16 s, `x^2` degree 2 in ~6.5 s, `x` degree 1 in
~4.8 s, while `exp(x)` degree 4 does not finish in 60 s.

**Why it matters:** it is a bug / limitation:** the stress contract bounds runs at 30 s, and
this ordinary target (`exp`, degree 4) cannot be stress-tested within that
budget in its `search anneal`/`search cmaes` modes.  The default (walk) mode
of the same command finishes in <1 s.  No golden was kept for these modes.

### LIMIT-2 — `UCAS_SEED` silently accepts malformed values (`strtoull`, no validation)
**Severity:** LIMIT
_Original classification: `LIMIT (reproducibility foot-gun`._
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
for s in abc -3 18446744073709551616; do
  printf 'UCAS_SEED=%s -> ' "$s"
  UCAS_SEED=$s bash -c "printf 'f(x: u8) = x*x + 1\nstoke f steps 100\n' | ./ucas" \
    | grep -m1 'seed'
done
```

**Observed:** output:

```
UCAS_SEED=abc ->   4 chains of 100 proposals, seed 0; f as written costs 3
UCAS_SEED=-3 ->   4 chains of 100 proposals, seed 18446744073709551613; f as written costs 3
UCAS_SEED=18446744073709551616 ->   4 chains of 100 proposals, seed 18446744073709551615; f as written costs 3
```

**Why it matters:** `stoch_seed()` (`src/stoch.c:118-124`) uses bare
`strtoull(e, NULL, 10)` with no `errno`/end-pointer check.  A typo (`abc`) maps
silently to seed 0, a negative value wraps to `2^64-3`, and an overflow clamps
to `2^64-1`.  The command prints the resulting seed but emits no warning that
the requested seed was not used, so a batch reproducibility run can drift
without anyone noticing.  (`0007` correctly normalises to `7`.)

## Checks that passed

### Verified-correct behaviours (no finding)
These were checked and found sound; they are captured as goldens instead of
reported as bugs:

- **Seeded reproducibility / state independence.** `stoke`, `pit`, `phash`,
  `find f stoke`, `approx` (default) and QMC sampling all produce byte-identical
  output on repeated runs with the same `seed`.  Two stochastic commands in one
  session with the same explicit seed give the same result (no shared-RNG
  leakage): `stoke f steps 3000 seed 5` twice → identical `10035 accepted`.
- **`timeout_s` fork does not corrupt parent RNG.** MCP golden
  `mcp_stochastic.jsonl` runs seeded `stoke` (ids 2,3), a 1 s timed-out child
  (id 4, error `timed out after 1 s; the state is unchanged`), and seeded
  `stoke` again after both a killed child and a successful forked child
  (ids 5,6,7).  All five stoke results are identical: `12000 proposals, 10010
  accepted, 2250 at distance 0 ... 1 verified`.
- **Witness distribution is real, not a constant first hit.** `pit` on
  `x*x+1` vs `x*x+2` returns a different random point for each of seeds 1–6
  (e.g. `x = 1507915731792878937` for seed 1 vs `483963403690107284` for seed
  6).  `stoke` accepted counts vary across seeds 0..8 (9217–10105).  `phash`
  varies the number of hash functions tried (15–91 across seeds 1..99).
- **"Sampled" / probabilistic disclaimers are present.** `range` over u32/u64
  prints `sampled 65536 points (domain has ...) ; not exhaustive`; `error`
  prints `over 49080 points`; `approx` prints `measured on ... sampled floats`;
  `pit` prints `not a proof: a probabilistic answer` with a Schwartz–Zippel
  bound; QMC fallback prints `random digital shift ... seed 1 ... which
  nothing proves`; `stoke` prints `the search is stochastic: more steps,
  another seed`.
- **Per-rewrite validation.** `stoke` on `x*2` finds `x + x` at cost 1 with
  `every input enumerated`, and `equiv` independently confirms equality
  (`equal on the domain of f (exhaustive)`).
- **No crashes/hangs in the 842-run matrix** for `stoke`/`pit`/`phash`/`find`/
  `approx`(default)/`adamfit`/`range`/`error` with bounded parameters; seed
  validation on `stoke` rejects negatives, non-integers and >2^64−1.
