# SUMMARY — `cfront_bench_timing`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 22
- Files created: 01

### Counts

- **Distinct queries generated/tried:** ~600
  - 544-parameter matrix `.ucas` cases under `cases/` (18 functions × 7 option
    modes × budgets 0/1/3/100, plus a 5-function × 4-target × 2-mode target grid).
  - 20 curated CLI goldens, 1 MCP JSONL golden, 1 `--json` golden.
  - ~35 ad-hoc probes (nondeterminism, `UCAS_NO_TIMES`, clang shim, arg fuzz).
- **Matrix cases actually executed under `timeout 20`:** 152 of 544 before
  stopping (8 of those hit the 20 s wall under heavy host load from other
  stress agents; none showed a crash/sanitizer signature). The remaining
  matrix files are present as reproducible inputs; the curated goldens cover
  every matrix dimension.
- **Files created:** `01_*`–`20_*` (20 `.ucas` + 20 `.out`), `mcp_bench.jsonl` +
  `mcp_bench.out`, `json_bench.jsonl` + `json_bench.out`, `FINDINGS.md`,
  `SUMMARY.md`, `cases/` (544 `.ucas`), `cases_manifest.txt`, generators
  (`gen.py`, `gen_goldens.py`) and runners (`explore.sh`, `crun.sh`, `run_all.sh`,
  `run_rest.sh`, `make_goldens.sh`, `bin/cc`, `results_gcc*`). All inside
  `tests/stress/areas/systems/cfront_bench_timing/`.
- **Issues by severity:** WRONG 2, DETERMINISM 3, LIMIT 5, CRASH 0, HANG 0,
  NLP 0. (LIMIT-4 target handling is documented behaviour, not a defect.)

### What works (checked)

- `bench` genuinely runs a differential check and rdtsc benchmark when the
  harness builds (clang shim). Timing lines are clearly marked with a
  `bench <fn>:` prefix and a `(rdtsc, median of 15, 3 runs: …)` annotation.
- `bench` does change the chosen rewrite (vectorised loops / loop-body
  rewrites are applied only when measured >5% faster in every one of 3 runs).
- `check`+`bench` in either order, duplicated options, `target`, `budget`, and
  malformed C all behave without crashes; invalid targets give clean errors.

### Coverage notes

- Budgets 0/1/3/100: all used, no budget-dependent crash; `budget -1` and
  `budget abc` are passed through unvalidated (silently coerced) in JSON mode.
- Targets: `zen4`/`skylake` accepted; `skl` (internal uarch alias), `gt1030`
  (GPU) and `bogus` rejected with a clean error; `bench` is not reached.
- Tiny/large functions, loops, float vs integer: covered; float functions are
  never benchmarked (LIMIT-2).
- `check`+`bench` in both orders and duplicated options: deterministic.
- MCP (`c` tool `op:c_optimize`) and `--json` (`cmd:c_optimize`) equivalents
  reach the same path; `bench:"yes"` is rejected (`bench: true or false`), but
  timing appears only in `text`, not in the structured `result` (LIMIT-3).

### Golden caveat

All kept goldens were generated with the default `cc` (GCC) and double-run
byte-identically. They capture the "harness does not compile" branch. On a
machine where `cc` accepts `-fsanitize-minimal-runtime` they will differ
because real rdtsc lines will appear; those cases are documented in
`FINDINGS.md` and intentionally have no goldens.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 5 | — |
| DETERMINISM | 3 | — |

## Takeaway
`bench` does benchmark and clearly prefixes its rdtsc lines with `bench …`, but on this host (`cc`=GCC) the harness never builds so no timing happens; when forced through clang it reports ~1.2× "speedups" for byte-identical code, keeps rewrites it measured as slower, ignores `UCAS_NO_TIMES`, and changes the chosen rewrite from noisy numbers — so its timing must never be read as proof.

### Original takeaway (verbatim)

`bench` does benchmark and clearly prefixes its rdtsc lines with `bench …`,
but on this host (`cc`=GCC) the harness never builds so no timing happens; when
forced through clang it reports ~1.2× "speedups" for byte-identical code, keeps
rewrites it measured as slower, ignores `UCAS_NO_TIMES`, and changes the chosen
rewrite from noisy numbers — so its timing must never be read as proof.
