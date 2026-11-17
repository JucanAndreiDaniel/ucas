# SUMMARY — `thesis_fusion_enum`

## Counts
- Distinct expressions/queries tried: 1075
- Goldens written: 14
- Files created: not recorded

### Coverage

| item | count |
|---|---|
| Fusion pairs (generator tree + two equal emitters), CLI | 36 (commutativity 6, associativity 5, distributivity 4, identities 7, boolean/De Morgan 3, dependency-aware rename 6, fragment/regenerate 5 — see files 01–07) |
| Near-miss negative controls (`equiv` must say `differ`) | 8 (file 13) |
| Enumerated expressions in golden files (`range` / reflexive `equiv`) | 73 (files 08–11) |
| Full exhaustive sweep expressions (bulk, in `_scratch/`, oracle-checked) | 976 = 288 u4 depth-1 + 288 u8 depth-1 + 400 u4 depth-2 |
| PerfFuzz pathological equivalences | 6 (file 12, plus individual probes) |
| MCP tool calls in goldens | 16 `tools/call` (6 `session.define`, 3 `analyze.equiv`, 3 `analyze.error`, 4 `analyze.range`) + 2× init/initialized, across two jsonl files |
| **Distinct expressions / queries tried** | **≥ 1075** (36 pairs × 2 expressions + 976 enumerated + 8 near-miss × 2 + 6 perf × 2) |

### Files written

- `gen.py` — deterministic generator (`SEED=0xCA5`), regenerates every input; `python3 gen.py`.
- `_scratch/oracle.py`, `_scratch/perf_probe.py`, `_scratch/mkgoldens.py` — oracle, timing harness, golden builder.
- 14 CLI goldens: `01_fusion_commute_{1,2}`, `02_fusion_assoc`, `03_fusion_distribute`,
  `04_fusion_identity_{1,2}`, `05_fusion_boolean`, `06_fusion_mutate_swap`,
  `07_fusion_fragment_regen`, `08_enum_u4_depth1`, `09_enum_reflex_equiv`,
  `10_enum_u8_depth1`, `11_enum_u4_depth2`, `13_nearmiss_differ` (`.ucas` + `.out` each).
- 2 MCP goldens: `mcp_fusion_pairs.jsonl` + `.out`, `mcp_enum_range.jsonl` + `.out`.
- 1 documented non-golden reproducer: `12_perf_pathological.ucas` (exceeds the 30 s budget).
- `FINDINGS.md`, `SUMMARY.md`.

All 16 goldens were produced from this directory and **verified byte-identical across two
independent runs** (exit 0 both times) before their `.out` was written.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 1 | SAT give-up search on ((xy)z)^5 vs ((yx)z)^5 (u32) crossed the 29 s timeout in 1 of 3 identical runs |
| LIMIT | 2 | new give-up frontiers (44720 / 90933 / 148921 AIG nodes vs 35081 baseline); no standalone differ command |
| DETERMINISM | 1 | same input gave ~16.7 s / ~18.1 s / >29 s; answer text stable but runtime is not |

### Issues by severity

| severity | count | summary |
|---|---|---|
| `CRASH` | 0 | none |
| `WRONG` | 0 | 976 exhaustive range checks matched the independent oracle; no false `equal:true` in 8 near-miss controls |
| `NLP` | 0 | n/a for this area |
| `HANG` | 1 | SAT give-up search on `((x*y)*z)^5` vs `((y*x)*z)^5` (u32) crossed the 29 s timeout in 1 of 3 identical runs |
| `DETERMINISM` | 1 | same input gave ~16.7 s / ~18.1 s / >29 s; answer text stable but runtime is not |
| `LIMIT` | 2 | new give-up frontiers (44720 / 90933 / 148921 AIG nodes vs 35081 baseline); no standalone `differ` command |


## Takeaway
Fusion pairs and exhaustive u4/u8 enumeration are sound (0 wrong ranges, 0 unsound `equal`), but SAT give-up on product-under-xor chains is a real performance cliff with variable runtime that can cross the 30 s test budget — giving new AIG-node boundaries up to 148921, far past `satsteps.ucas`' 35081.

### Original takeaway (verbatim)

Fusion pairs and exhaustive u4/u8 enumeration are sound (0 wrong ranges, 0 unsound
`equal`), but SAT give-up on product-under-xor chains is a real performance cliff with
variable runtime that can cross the 30 s test budget — giving new AIG-node boundaries
up to 148921, far past `satsteps.ucas`' 35081.
