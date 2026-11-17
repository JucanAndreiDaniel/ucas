# SUMMARY — `cost_cross_model`

## Counts
- Distinct expressions/queries tried: 1,700
- Goldens written: 10
- Files created: 26

### Counts

- **Distinct expressions / queries tried:** ~1,700.
  - Exploratory harnesses (scratch, not in this folder): 36 expressions × 16
    models = 576 `cost` queries; 17 algebra-equivalent form pairs × 2 × 16 = 544
    `cost` queries checking monotonicity; 17 functions × 9 x86 µarchs × 2
    (`cost` + `mca`) = 306 bound-consistency queries; 22 model-definition edge
    cases; 10 malformed cost-value cases; ~40 `find` calls under different
    `use` models; plus ad-hoc CLI/MCP probes.
  - Durable goldens: 10 CLI files (~280 statements) + 2 MCP files (13 + 10
    calls).
- **Files created (all inside `tests/stress/areas/gpu/cost_cross_model/`):** 26
  - 10 CLI golden pairs: `01_cost_integer_matrix` … `10_bad_model_values`
    (`.ucas` + `.out`).
  - 2 MCP golden pairs: `mcp_crossmodel_cost` (13 calls) and
    `mcp_crossmodel_mca` (10 calls) (`.jsonl` + `.out`).
  - `FINDINGS.md`, `SUMMARY.md`.
- **Determinism:** every golden generated twice and byte-diffed — identical.
  No crash, hang, signal or truncated output anywhere in this area.

### Reproducer quick reference

| Severity | One-line reproducer |
|---|---|
| WRONG | `cd tests/stress/areas/gpu/cost_cross_model && timeout 15 $ROOT/ucas 07_mca_divergence.ucas` → `bounds: critical path 12.00 … simulated: 18.00 cycles, limited by the critical path` |
| WRONG | `printf 'cost totally_undefined\n' \| $ROOT/ucas` → `cost of totally_undefined under gt1030: 0` |
| WRONG | `printf 'f(x:u32)=x*7+11\nmodel m:gt1030{imul:abc}\ncost f model m\n' > /tmp/v.ucas; $ROOT/ucas /tmp/v.ucas` → cost 0 |
| WRONG | `printf 'model p:nosuch{imul:5}\nmodels\n' \| $ROOT/ucas` → `model p { … }` appears despite `error: unknown model` |
| NLP | `printf 'cost tg model gt1030\n' \| $ROOT/ucas` → `'tg' read as t*g` |
| LIMIT | `model gt1030 { imul: 5 }` silently redefines the built-in model |

See `FINDINGS.md` for exact commands and pasted outputs.

### Scope confirmation:
all files were created only in
`tests/stress/areas/gpu/cost_cross_model/`; no source, Makefile, existing test,
`opencode.json`, or other subagent's folder was touched; no `make`, `git` or
commit was run.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | mca simulated cycles exceed its own critical-path bound for integer //%; cost of an undefined function = 0; abc/inf/nan costs silently becom |
| NLP | 1 | undefined two-letter name in cost is silently read as a product (tg → tg). |
| LIMIT | 2 | cost ordering is genuinely model-dependent (fusions invert it), and a built-in model can be silently redefined. |

### Issues by severity

| severity | count | one-line takeaway |
|---|---|---|
| CRASH | 0 | — |
| HANG | 0 | — |
| WRONG | 4 | `mca` simulated cycles exceed its own critical-path bound for integer `/`/`%`; `cost` of an undefined function = 0; `abc`/`inf`/`nan` costs silently become 0; a failed `model` definition leaves a phantom default-cost model usable. |
| NLP | 1 | undefined two-letter name in `cost` is silently read as a product (`tg` → `t*g`). |
| LIMIT | 2 | cost ordering is genuinely model-dependent (fusions invert it), and a built-in model can be silently redefined. |
| DETERMINISM | 0 | — |


## Takeaway
Cross-model pricing, overrides, inheritance, `use` switching, `find` and subset/instruction-set fallbacks are internally consistent and deterministic, but `mca` reports simulated cycles larger than the critical-path bound it prints for integer division, and the cost-model parser silently turns malformed prices and undefined functions into 0 (and keeps phantom models after failed definitions).

### Original takeaway (verbatim)

Cross-model pricing, overrides, inheritance, `use` switching, `find` and
subset/instruction-set fallbacks are internally consistent and deterministic,
but `mca` reports simulated cycles larger than the critical-path bound it prints
for integer division, and the cost-model parser silently turns malformed prices
and undefined functions into 0 (and keeps phantom models after failed
definitions).
