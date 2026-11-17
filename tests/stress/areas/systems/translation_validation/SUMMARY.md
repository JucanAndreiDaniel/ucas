# SUMMARY — `translation_validation`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 6
- Files created: not recorded

### What was exercised

Every form emitted by the five ucas rewriters was collected as structured MCP
output and re-validated with oracles that share no code with ucas.

| rewriter | source cases | emitted forms collected | independently checked |
|---|---|---|---|
| `find` | 60 | 86 | 61 exhaustive (u4/u5/u6/u8/i4/i8/u32); 4 unbounded-int/float; 7 parse-skipped; 14 unsupported opcode/float |
| `gates` | 24 | 20 programs + 161 gate-step expressions | 20 programs simulated on every care input; all 161 step expressions parsed and evaluated |
| `simplify` | 20 | 20 | 20 exact-rational (sympy) |
| `c optimize` | 31 | 30 rewrites | 30 compiled with gcc -O0 and diffed against the original function |
| `spirv_simplify` | 21 | 16 rewrites | 9 whole-module interpreted before/after; 1 derivation skipped; 6 `to` forms are ucas expressions (not SPIR-V) |
| float `find` | 2 | 2 | bit-exact f32 pattern scan (NaN, ±0, subnormal, inf, 4000 random) |

Totals: **156 distinct source queries**, **≈330 emitted forms**, **301 forms
independently validated**, **0 emitted form found to compute a different
function**.  The two gcc diffs that initially differed were traced to samples
outside the asserted `range` of an assumed-range rewrite (finding 5), not to
unsoundness.

### Files created

- `FINDINGS.md`, `SUMMARY.md`
- Golden CLI tests (each run twice and `diff`-identical):
  - `01_find_machine.ucas` / `.out`
  - `02_gates_net.ucas` / `.out`
  - `03_simplify.ucas` / `.out`
- Golden MCP tests (each run twice and `diff`-identical):
  - `mcp_rewriters.jsonl` / `.out`
  - `mcp_spv_assume.jsonl` / `.out`
  - `mcp_c_range.jsonl` / `.out`
- Harness (all in `harness/`): `corpora.py`, `collect.py`, `expr_eval.py`,
  `validate.py`, `validate_c.py`, `validate_spv.py`, `validate_float.py`
- Raw collected data and reports under `_scratch/` (`collected.json`,
  `report*.json`) — not goldens.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| WRONG | 1 | — |
| LIMIT | 5 | — |

### Issues by severity

- **WRONG: 1** — `spirv_simplify` response-level proof claims SAT equality for
  *every input* while the emitted rewrite is a derivation valid only on an
  assumed range (`mcp_spv_assume.jsonl`).
- **CRASH: 1** — `find z(x: u8) = x & 15` segfaults (CLI and MCP, exit 139,
  stable partial output).
- **LIMIT: 5** — non-minimal `gates` networks with no `proof` field; an
  unbounded-int `find` rewrite marked `verified` while its proof is `sampled`;
  `c optimize` emitting unconditional C for an assumed-range proof; float
  min/max rewrites conditional on NaN/signed-zero (caveat accurate); MCP
  session-length output degradation worked around in the harness.
- **HANG: 0**, **NLP: 0**, **DETERMINISM: 0** in the goldens.


## Takeaway
The rewrites themselves were equivalence-correct on every domain we could independently enumerate or compile, but proof *metadata* can overstate its domain (`spirv_simplify` SAT claim over an assumed-range derivation) and a malformed `find` argument segfaults instead of being diagnosed.

### Original takeaway (verbatim)

The rewrites themselves were equivalence-correct on every domain we could
independently enumerate or compile, but proof *metadata* can overstate its
domain (`spirv_simplify` SAT claim over an assumed-range derivation) and a
malformed `find` argument segfaults instead of being diagnosed.

### How to re-run

```sh
cd $ROOT/tests/stress/areas/systems/translation_validation/harness
python3 collect.py            # rebuilds ../_scratch/collected.json
python3 validate.py           # find/gates/simplify
python3 validate_c.py         # gcc differential for c optimize
python3 validate_spv.py       # SPIR-V whole-module interpreter
python3 validate_float.py     # f32 bit-exact scan
```

All runs are bounded by `timeout`; the collect pass batches MCP calls in chunks
of 40 to avoid a session-length output-degradation issue (see FINDINGS.md).
