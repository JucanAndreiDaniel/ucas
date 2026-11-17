# SUMMARY — `range_sampled_soundness`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 6
- Files created: 6

### Counts
- **Functions/queries tried:** ~590 (419 generated single-variable specs from `harness.py`
  + ~170 hand-targeted probes across 13 scratch files).
- **Oracle coverage:** full brute force for every exhaustive domain (u8/u16/i16);
  30k–60k-point edge-and-random grids for u32/i32; domain-restricted float grid for f32.
- **Classification of the 419 generated specs:** 207 exhaustive-correct,
  123 sampled-but-sound (no dense-grid counterexample), **84 sampled-unsound**,
  **0 proved-but-wrong**.
- **Sound-bound violations:** 0. **Bad proved-bound witnesses:** 0.
- **Files created:** 6 CLI golden pairs (`*.ucas` + `*.out`), 1 MCP golden pair
  (`mcp_range_structured.jsonl` + `.out`), `harness.py`, `FINDINGS.md`, `SUMMARY.md`,
  plus `gen/` scratch (generated `.ucas`/`.out` batches and `results.json`).
- **Issues by severity:** 5 WRONG (systematic sampled-headline unsoundness, split into
  spike/wrap arithmetic, two-variable masks, variable shift, `asfloat` IEEE count, f32),
  0 CRASH / HANG / DETERMINISM.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 5 | — |

### Goldens (all deterministic, byte-diffed over two runs)
- `01_sampled_spike_u32.ucas/out` — isolated spike headline `0..0` vs `spk(3)=1000000007`.
- `02_multivar_mask.ucas/out` — `x|y` min miss (0 vs 1), `x&y` max miss (65535 vs 65408).
- `03_varshift_asfloat.ucas/out` — `x>>s` min miss; `asfloat` "±inf at 0 points" vs `inf`.
- `04_f32_sampled.ucas/out` — f32 spike `[0,1]` vs `1e30`; `abs` min `1.13e-41` vs `0`.
- `05_proved_sound_controls.ucas/out` — correct proved bounds + witnesses (control).
- `06_exhaustive_controls.ucas/out` — exact exhaustive ranges (control).
- `mcp_range_structured.jsonl/out` — structured `min`/`max`/`sound_bound`/`proved_bound`/
  `proof` fields for a sampled spike, a proved-bound function and a bit-cast.

Confirmed: stayed entirely within `tests/stress/areas/sat/range_sampled_soundness/`; all runs bounded
with `timeout 15`; no source files, Makefiles, other folders or shared files touched.


## Takeaway
Exhaustive ranges, the `sound bound (intervals)` line, proved-bound monotonicity and its `take x = …` witnesses are all sound on u16/u32/i16/i32/f32; the **sampled headline** is routinely not a bound (84 confirmed counterexamples with `show`), f32 ranges have no sound fallback at all, and sampled IEEE side-counts can be flat false — so only the sound-bound line, never the headline, should be trusted for a sampled `range`.

### Original takeaway (verbatim)
Exhaustive ranges, the `sound bound (intervals)` line, proved-bound monotonicity and its
`take x = …` witnesses are all sound on u16/u32/i16/i32/f32; the **sampled headline** is
routinely not a bound (84 confirmed counterexamples with `show`), f32 ranges have no sound
fallback at all, and sampled IEEE side-counts can be flat false — so only the sound-bound
line, never the headline, should be trusted for a sampled `range`.
