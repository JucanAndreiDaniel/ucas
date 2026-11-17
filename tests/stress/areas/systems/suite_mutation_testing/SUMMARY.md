# SUMMARY — `suite_mutation_testing`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 30
- Files created: 1

### Counts

| Item | Count |
|---|---:|
| Confirmed bug classes analysed (from `MASTER_FINDINGS.md`) | 32 |
| Individual coverage checks (bug class × relevant golden test) | 188 |
| Bug classes with a covering golden (fix would change a `.out`) | 1 |
| Bug classes with NO covering golden (GAP) | 31 |
| Top-level regression pairs indexed (`tests/*.ucas` + `.out`) | 250 |
| Existing `tests/*.ucas` read but not modified | 250 |
| Existing `tests/*.out` read but not modified | 250 |
| Mutants generated and run (copies, never originals) | 30 |
| Mutations applied (single operator/bound/type/constant change) | 30/30 |
| Mutants deterministic across two runs | 30/30 |
| Mutants detected by raw output diff | 30/30 |
| Mutants detected by semantic diff (noise-normalised) | 29/30 |
| Mutation blind spots | 1 (`m15`, `counter.ucas`) |
| New findings documented | 4 (2 WRONG, 1 DETERMINISM/LIMIT, 1 LIMIT) |
| Files created in this folder | 1 matrix + 1 findings + 1 summary + 1 mutation report + 30 `.ucas` + 30 `.out` + 12 data/script files |

### Artifacts (all in `tests/stress/areas/systems/suite_mutation_testing/`)

- `COVERAGE_MATRIX.md` — bug class → covered? → covering test or GAP (32 rows, 188 checks).
- `MUTATION_RESULTS.md` — 30 mutations, raw vs semantic detection, blind-spot analysis.
- `FINDINGS.md` — 4 findings with severity, exact repro, observed output, rationale.
- `SUMMARY.md` — this file.
- `mutations/m01..m30.ucas` + `.out` — mutated copies and their captured outputs.
- `data/build_matrix.py`, `checks.csv`, `matrix.json` — coverage analysis and per-check evidence.
- `data/mutate.py`, `recheck.py`, `mutation_report.py`, `mutations.csv` — mutation pipeline.
- `data/baseline.py`, `baseline.log`, `baseline.csv` — 4 s-capped suite-health snapshot.
- `data/explore.py`, `sigscan.py` — exploratory signature scans.

### Reproduce everything

```sh
cd $ROOT
python3 tests/stress/areas/systems/suite_mutation_testing/data/build_matrix.py
python3 tests/stress/areas/systems/suite_mutation_testing/data/mutate.py
python3 tests/stress/areas/systems/suite_mutation_testing/data/recheck.py
python3 tests/stress/areas/systems/suite_mutation_testing/data/mutation_report.py
```


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 2 | — |
| DETERMINISM | 1 | — |

## Takeaway
The 500-file golden suite does **not** catch the bugs we found: only 1 of 32 confirmed bug classes has a golden whose output would change on a fix (31 GAPs over 188 checks), and one of 30 semantic mutations (`counter.ucas` coefficient) is invisible to its golden's semantic content — so a fix could land, or a bug return, with the suite still green.

### Original takeaway (verbatim)

The 500-file golden suite does **not** catch the bugs we found: only 1 of 32 confirmed bug
classes has a golden whose output would change on a fix (31 GAPs over 188 checks), and one
of 30 semantic mutations (`counter.ucas` coefficient) is invisible to its golden's
semantic content — so a fix could land, or a bug return, with the suite still green.

### Folder-confirmation

No source file, Makefile, `opencode.json`, or existing test (`tests/*.ucas`, `tests/*.out`)
was edited. No `make`, `git`, or commit command was run. Every run was bounded with
`timeout`. All writes are confined to `tests/stress/areas/systems/suite_mutation_testing/`.
