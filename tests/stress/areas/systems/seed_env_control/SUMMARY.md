# SUMMARY — `seed_env_control`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 1
- Files created: not recorded

### Coverage

- **Distinct queries / invocations tried: 334** — 231 matrix cases executed by
  `harness.py` plus 103 pinned statements/calls in the goldens
  (5 CLI `.ucas` files = 83 statements, 1 JSON golden = 9 calls, 1 MCP golden
  = 11 calls; small overlap with the matrix cases).
- **Bounded runs:** 231 harness runs + 33 env-matrix checks + 7 golden
  double-run/diff verifications + repeat `find ... stoke` checks = **275+**,
  every one under `timeout` (15 s, 30 s for approx/stoke), all with exit codes
  recorded in `results.json`.
- **Input classes:** 39 `UCAS_SEED` values (valid, invalid strings, negative,
  overflow, whitespace/sign/junk lexical variants, empty); 33 explicit `pit`
  seeds; 8 `stoke` and 10 `approx` explicit seeds; 14 `qmc` seeds; 25 JSON
  `seed` args + 19 MCP `seed` args; 54 equal / different / false-equal
  polynomial-pair verdict checks across seeds 0/1/2; 18 fixed-seed repeat
  runs; 9 cross-interface (CLI vs JSON vs MCP) seed comparisons.

### Files created (this folder only)

- `harness.py` — the full runnable matrix + golden generator + `results.json`
- `results.json` — per-case rc / elapsed / verdict / echoed seed / SHA, with an
  `anomalies` section (29 expected parse/validation rejects, no crashes)
- `01_pit_explicit_seed.ucas` / `.out` — 20 explicit seed tokens on `pit`
- `02_pit_equal_vs_differ.ucas` / `.out` — 6 equal + 6 genuinely different
  polynomial pairs at fixed seed 1
- `03_pit_p_multiple_false_equal.ucas` / `.out` — 5 false-equal reproducers (F1)
- `04_qmc_explicit_seed.ucas` / `.out` — 6 QMC seeds
- `05_approx_seed.ucas` / `.out` — annealing seed 5
- `json_seed_args.jsonl` / `.out` — JSON `seed` arg matrix
- `mcp_seed_args.jsonl` / `.out` — MCP `analyze` `seed` arg matrix
- `run_seed_matrix.sh` — durable 33-run `UCAS_SEED` environment matrix
- `FINDINGS.md`, `SUMMARY.md`

All 7 goldens were written only after two byte-identical runs and pass the
standard `tests/stress/run.sh` conventions with 0 diffs.  `run_seed_matrix.sh`
passes 33/33.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | F1 false equal from pit for PIT_P-multiple differences; F2 unchecked strtoull env coercion; F4 CLI accepts uint64 seeds that JSON/MCP reject |
| LIMIT | 1 | F3 explicit negative seed K rejected at parse time in all three frontends |

### Issues by severity

| severity | count | items |
|----------|-------|-------|
| CRASH    | 0 | — (no signal / no nonzero exit from any seed value) |
| HANG     | 0 | — (no `rc=124`; huge/negative seeds did not stall any command) |
| WRONG    | 4 | F1 false `equal` from `pit` for `PIT_P`-multiple differences; F2 unchecked `strtoull` env coercion; F4 CLI accepts uint64 seeds that JSON/MCP reject above 1e15; F5 `approx` seed parser diverges from `pit`/`stoke`/`qmc` |
| DETERMINISM | 0 | three runs per fixed-seed command byte-identical; verdicts stable across seeds 0/1/2; no clock-deadline nondeterminism exposed on these seed-bearing paths |
| LIMIT    | 1 | F3 explicit negative `seed K` rejected at parse time in all three frontends |
| NLP      | 0 | — |


## Takeaway
Seeds are honoured and fixed-seed runs are reproducible, but the seed *surface* is unsound and fragmented: `pit` can prove a false equality when the difference is a multiple of 2^61−1, `UCAS_SEED` silently coerces junk/negative/overflow via unchecked `strtoull`, and the CLI / JSON / MCP / `approx` seed parsers each accept a different numeric domain.

### Original takeaway (verbatim)

Seeds are honoured and fixed-seed runs are reproducible, but the seed *surface*
is unsound and fragmented: `pit` can prove a false equality when the difference
is a multiple of 2^61−1, `UCAS_SEED` silently coerces junk/negative/overflow via
unchecked `strtoull`, and the CLI / JSON / MCP / `approx` seed parsers each
accept a different numeric domain.
