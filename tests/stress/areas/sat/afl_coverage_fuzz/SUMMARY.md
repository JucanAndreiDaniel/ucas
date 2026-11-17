# SUMMARY — `afl_coverage_fuzz`

## Counts
- Distinct expressions/queries tried: 2,000
- Goldens written: 3
- Files created: not recorded

### Method

AFL++ / honggfuzz are unavailable on this host; **`clang` libFuzzer** (real
coverage-guided fuzzing, 172,252 inline-8-bit coverage counters) was used
instead. Two ucas fuzz targets were built from `src/*.c` entirely inside this
folder (`fuzz_ucas` = libFuzzer+ASan, `fuzz_ucas_fast` = libFuzzer+UBSan), with
a `run_text()` harness, a 200+ token dictionary, and a corpus seeded from all
250 `tests/*.ucas` plus 24 hand-written grammar seeds.

### Counts

- **Distinct inputs tried:** ~2,000 retained corpus entries (43 initial fast
  seeds → 2,029 after coverage-guided growth), plus 250 original seeds timed,
  4 depth-crash reproducers and 3 golden inputs — well over the 100–300 target.
- **Fuzzer executions:** ~35,900 total (45 s validation: 909; ASan campaign:
  10,997; fast campaign: 14,521; second ASan campaign: 9,450). ~2,500 new
  coverage-increasing inputs discovered. Throughput 26–86 exec/s/worker.
- **Crash artifacts collected:** 3 stack-overflow crashes, 8 timeouts (all
  triaged as slow-but-terminating), 1 leak artifact.
- **Deduped issues:** 1 crash class (stack overflow), 1 determinism note,
  2 NLP issues, 3 limits → see `FINDINGS.md`.

### Files written (all inside this folder)

- `build.sh`, `build_fast.sh`, `fuzz_ucas.c`, `fuzz_ucas_echo.c`,
  `fuzz_ucas_noredir.c`, `fuzz_ucas`, `fuzz_ucas_fast`, `fuzz_ucas_echo`,
  `fuzz_ucas_noredir`, `build/`, `build_fast/` — instrumented builds + harnesses.
- `dict/ucas.dict` — token dictionary.
- `seeds/` (250 copies), `fastseeds/` (368), `corpus/` (2,029),
  `corpus_fast/` (1,824) — corpora; `snippets/`, `nlp_words.h`,
  `thy_absalg.inc` — read-only copies of build prerequisites so all writes
  stay in this folder.
- `crashes/`, `leaks/`, `run/` — artifacts and campaign logs.
- `01_deep_unary_crash.ucas` … `04_deep_sqrt_crash.ucas` — deterministic
  SIGSEGV reproducers (no `.out`, per `SPEC.md`: crashes are not goldens).
- `05_nlp_checklim.ucas/.out`, `06_nlp_solve_olv.ucas/.out`,
  `07_unicode_or.ucas/.out` — stable golden tests (determinism verified twice).
- `makeseeds.sh`, `seed_times.tsv` — corpus-construction helpers.
- `FINDINGS.md`, `SUMMARY.md` — this report.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| NLP | 2 | unknown commands taken as variables; solve-variable guessed |
| LIMIT | 3 | AFL++ absent; leaks; false-positive timeouts / harness fidelity |
| DETERMINISM | 1 | fuzzer stack overflow needs accumulated global state |

### Issues by severity

| Severity | Count | Headline |
|---|---|---|
| CRASH | 1 (4 reproducers) | ~1,600-deep expression → SIGSEGV in `pr()` recursion |
| HANG | 0 | all fuzzer timeouts were ~18 s mma searches, not hangs |
| WRONG | 0 | not exercised by a crash-only oracle |
| NLP | 2 | unknown commands taken as variables; solve-variable guessed |
| DETERMINISM | 1 | fuzzer stack overflow needs accumulated global state |
| LIMIT | 3 | AFL++ absent; leaks; false-positive timeouts / harness fidelity |


## Takeaway
Coverage-guided fuzzing with clang libFuzzer (~36k executions, 172k counters) found a deterministic, user-reachable stack-overflow crash in ucas's expression printer (`pr()`, node.c:1920) at only ~1,500 nesting depth, plus two NLP silent-default misparses; all reproducers and artifacts are confined to this folder.

### Original takeaway (verbatim)

Coverage-guided fuzzing with clang libFuzzer (~36k executions, 172k counters)
found a deterministic, user-reachable stack-overflow crash in ucas's expression
printer (`pr()`, node.c:1920) at only ~1,500 nesting depth, plus two NLP
silent-default misparses; all reproducers and artifacts are confined to this
folder.
