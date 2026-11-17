# SUMMARY — `make_test_baseline`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 0
- Files created: 3

### Scope / counts
- Official test cases exercised (distinct, default env): **250 CLI** (`.ucas`)
  + **54 JSON** (`.jsonl`) + **14 MCP** (`.jsonl`) = **318**, plus 1
  `--sat-selftest` and **144** C sources in the `libc-test` syntax check.
- Altered-environment re-runs: JSON+MCP × 7 variants (`UCAS_SEED=0`,
  `UCAS_SEED=1`, `LC_ALL=C`, `LC_ALL=C.utf8`, `LC_ALL=ro_RO.utf8`,
  `UCAS_NO_TIMES` removed, `UCAS_SPIRV_CROSS=/nonexistent/...`) = **476**, plus
  a full CLI re-run under `UCAS_SEED=0` (**250**).  Total test invocations ≈
  **1190**.
- Files created (all inside `tests/stress/areas/systems/make_test_baseline/`): 3 driver
  scripts (`replay.sh`, `run_variants.sh`, `capture_dryruns.sh`), this summary +
  `FINDINGS.md`, per-run `.log`/`.exit`/`.leftover`/`.selftest.out` files and
  preserved `.diff` directories, and the dry-run evidence logs.

### Official baseline (default Makefile env: `UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`)
| Suite | ok | FAIL | skip | exit |
|---|---|---|---|---|
| CLI (`make test` loop) | 211 | 37 | 2 | 37 |
| JSON (`make json-test`) | 42 | 11 | 1 | 11 |
| MCP (`make mcp-test`) | 11 | 2 | 1 | 2 |
| libc syntax (`make libc-test`) | 144 | 0 | 0 | 0 |
| `--sat-selftest` | ok | – | – | 0 |

The 300 s cap **cannot complete the CLI suite**: the unaltered replay stopped
after 23/250 tests because `cfbridge.ucas` hangs; even with a 45 s per-test
cap the suite needs ~12 min.  Skips are the 4 `spirv-cross`-dependent tests
(tool absent); `spirv-val`, `spirv-as`, `spirv-opt`, `glslangValidator` are present.

### Environment sensitivity
- `UCAS_SEED=1`: identical to baseline.  `UCAS_SEED=0`: +3 JSON failures
  (`adamfit`, `numsearch`, `stoke`) — goldens silently assume the default seed 1.
- `LC_ALL=C`, `LC_ALL=C.utf8`, `LC_ALL=ro_RO.utf8`: identical to baseline.
- Removing `UCAS_NO_TIMES`: +1 JSON failure (`adamfit`, timing line).
- `UCAS_SPIRV_CROSS=/nonexistent/...`: +7 JSON and +1 MCP failure
  ("spirv-cross not found" note); only the Makefile's `none` is silent.
- CLI full re-run under `UCAS_SEED=0`: **200 ok / 48 FAIL / 2 skip** — 11 extra
  failures (`approxcert`, `approxsearch`, `cfbridge_icl`, `fsimp`, `integ2`,
  `nlp_robust`, `phashtable`, `qmcmore`, `sparsemap`, `stoke`, `texenc`).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 5 | — |
| WRONG | 50 | — |
| LIMIT | 5 | — |
| DETERMINISM | 2 | — |

### Issues by severity
| Severity | Count | Summary |
|---|---|---|
| HANG | 5 | `cfbridge`, `cfbridge_zen4`, `cfront`, `mma`, `numsearch` (≥45 s, no progress) |
| WRONG | 50 | golden drift in default env: 37 CLI + 11 JSON + 2 MCP |
| DETERMINISM | 2 | seed-1-only goldens (14 cases: 3 JSON + 11 CLI), tie-order swap (1) |
| LIMIT | 5 | rebuild-required / GNU-make parse / 300 s cap / `NO_TIMES` / `SPIRV_CROSS` |
| LIMIT (artifacts) | 50 pairs | failing tests leave `.got`/`.diff` behind (baseline run alone) |


## Takeaway
The repo's own suite is **not green out of the box**: `bmake test` would first rebuild the binary, and even against the shipped binary 50 official cases fail (five hang), the goldens silently pin seed 1 / `NO_TIMES` / `SPIRV_CROSS=none`, and failures leave `.got`/`.diff` litter behind.

### Original takeaway (verbatim)
The repo's own suite is **not green out of the box**: `bmake test` would first
rebuild the binary, and even against the shipped binary 50 official cases fail
(five hang), the goldens silently pin seed 1 / `NO_TIMES` / `SPIRV_CROSS=none`,
and failures leave `.got`/`.diff` litter behind.

### Confinement
All files I created live in `tests/stress/areas/systems/make_test_baseline/`.  No source,
Makefile, existing test, `opencode.json`, or other subagent's folder was
edited.  The binary was never rebuilt (all runs used the absolute path
`$ROOT/ucas`); the official recipes' side-effect files were
redirected into my folder by running the replay from there.  The `snippets`
target (which regenerates files outside this folder) was deliberately not run
because the binary was already built and folder confinement is required;
`snippets.ucas` still passes against the existing database.
