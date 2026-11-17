# SUMMARY — `plot_gif_resources`

## Counts
- Distinct expressions/queries tried: 325
- Goldens written: 11
- Files created: 31

### Counts

- **Distinct invocations tried: ≈325**
  - MCP `tools/call` plot/animate/solids calls: **183** in 7 JSONL batteries
    (`mcp_stress_1d/bounds/geometry/surface/animate/solids/gifbytes.jsonl`).
  - CLI plot/animate statements: **102** in two batteries (67 themed + 35
    extreme-options).
  - Targeted probes: ~40 (file modes, `--dir`, GIF byte validation, size cap,
    leak test, determinism, module writers, `--flat`).
- **Files created: 31** (all inside `tests/stress/areas/gpu/plot_gif_resources/`):
  - 8 CLI `.ucas` + 8 `.out` goldens
  - 3 MCP `.jsonl` + 3 `.out` goldens (one keeps the full base64 GIF)
  - 7 MCP stress `.jsonl` batteries
  - `FINDINGS.md`, `SUMMARY.md`
- **Issues by severity:**
  - CRASH: 0
  - HANG: 0
  - WRONG: 3 (oversized MCP GIF silently dropped; silent `--dir` write failure;
    NaN interval `[-nan, inf]`)
  - LIMIT / NLP: 2 (`animate exec` absorbs trailing `frames N` as a variable;
    sampling/range options ignored or clamped without a note)
  - DETERMINISM: 1 informational (unseeded `random` animation seed is
    time-derived; no golden kept — explicit-seed cases are deterministic)


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| NLP | 2 | — |
| DETERMINISM | 1 | — |

## Takeaway
Plot/GIF generation is remarkably robust — 325 invocations produced no crashes, hangs, invalid GIF bytes or files outside the folder, and all goldens are byte deterministic — but MCP silently discards GIFs larger than the 4 MiB base64 cap instead of re-rendering them, and a failed `--dir` write is reported as success.

### Original takeaway (verbatim)

Plot/GIF generation is remarkably robust — 325 invocations produced no crashes,
hangs, invalid GIF bytes or files outside the folder, and all goldens are byte
deterministic — but MCP silently discards GIFs larger than the 4 MiB base64 cap
instead of re-rendering them, and a failed `--dir` write is reported as success.
