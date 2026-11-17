# SUMMARY — `rng_stochastic`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 9
- Files created: not recorded

### Counts

- **Distinct scripted scenarios:** 340 (stoke 156, pit 72, phash 16, approx 33,
  adamfit 15, find 6, find-stoke 3, range 10, error 3, edge cases 17, env-seed 9).
- **Total executions in the scripted matrix:** 842 (each stochastic scenario
  repeated 2–3× to measure reproducibility), all bounded by `timeout 15..30`.
- **Additional targeted probes:** ~80 (UCAS_SEED edge values, timeout_s forks,
  seed/variable sweep for pit & phash witness distribution, stoke verification
  via `equiv`, approx search modes, qmc fallback, singular integrals).
- **Goldens written:** 9 files total — 8 CLI `.ucas`+`.out` pairs
  (`01_stoke_seeds`, `02_pit`, `03_phash`, `04_find`, `05_range_sample`,
  `06_error_sample`, `07_approx`, `08_env_seed`) and 1 MCP
  `mcp_stochastic.jsonl`+`.out` pair.  Each was run twice and diffed before
  being kept.  No `adamfit` or `approx search anneal/cmaes` golden was kept.
- **Issues by severity:** DETERMINISM 1 (F1: adamfit timing line), LIMIT 2
  (F2: approx search anneal/cmaes > 60 s; F3: UCAS_SEED silent malformed-value
  coercion).  CRASH 0, HANG 0 (in the 842-run matrix), WRONG 0, NLP 0.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 2 | — |
| DETERMINISM | 1 | — |

## Takeaway
Seeding and reproducibility are otherwise solid — `stoke`, `pit`, `phash`, `find`, `approx`, and `range`/`error` sampling are byte-stable under a fixed seed, witnesses genuinely vary with the seed, and a `timeout_s`-forked child does not disturb the parent's RNG — but `adamfit` prints a variable elapsed time that defeats seeded reproducibility (use `UCAS_NO_TIMES=1`), and its `approx search anneal/cmaes` modes blow past the stress time budget on ordinary targets.

### Original takeaway (verbatim)

Seeding and reproducibility are otherwise solid — `stoke`, `pit`, `phash`,
`find`, `approx`, and `range`/`error` sampling are byte-stable under a fixed
seed, witnesses genuinely vary with the seed, and a `timeout_s`-forked child
does not disturb the parent's RNG — but `adamfit` prints a variable elapsed
time that defeats seeded reproducibility (use `UCAS_NO_TIMES=1`), and its
`approx search anneal/cmaes` modes blow past the stress time budget on ordinary
targets.
