# SUMMARY — `aig_growth_patterns`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 11
- Files created: 11

### Counts
- **Distinct family×width cases tried: 330** (33 family shapes × 10 widths
  `u12,u16,u20,u24,u28,u32,u40,u48,u56,u64`), plus a 2-shape × 5-length
  associativity-chain probe (10 cases) and a mask-width probe attempt.
- Family shapes: products of increasing width, nested xor chains (3 and 5 deep),
  nested add chains, multiplier associativity and 3-operand permutations, bit-sliced
  adders, barrel shifters/rotates, mask decoders, bit-extract/parity/sign tricks,
  power forms, distributivity/De Morgan/select identities.
- Verdicts: **240 SAT-proved**, **60 SAT-gave-up (`sampled`)**, **30 exhaustive**,
  0 crashes, 0 genuine hangs, 0 wrong answers.
- Files created: 11 CLI goldens (`NN_*.ucas` + `NN_*.out`), 1 MCP golden
  (`mcp_aig_nodes.jsonl` + `mcp_aig_nodes.out`), `FINDINGS.md`, `SUMMARY.md`, and
  `_scratch/` (harness `sweep.py`, `analyze.py`, `determinism.py`, `make_goldens.py`,
  `chain_probe.py`, `results.json`, `sweep.log`).
- All 12 goldens regenerated with the canonical command and diffed byte-identically;
  9 additional cases verified deterministic across two runs.

### Invariants checked
- Monotonicity: 0 non-monotonic node sequences across 33 families × 10 widths.
- Plausibility: node counts 25…148857, none negative or above `MAXAIG` (4194304);
  proved conflicts 0…49313 (budget 100000), none negative/over budget.
- Give-up node counts as low as 1200 (`mul_maskff` u12) — size alone does not predict
  provability.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 5 | verdict decoupled from AIG size; new associativity give-up boundary; conflicts/steps/time not exposed for give-ups; give-up wall time scales |

### Issues by severity
| Severity | Count | Summary |
|---|---|---|
| CRASH | 0 | none |
| HANG | 0 | two 20 s timeouts under load were proven not hangs (standalone 12–13 s, rc 0) |
| WRONG / unsound | 0 | none found |
| NLP | 0 | 1 parsing footgun documented (`^`=power; single-letter MCP names) |
| LIMIT | 5 | verdict decoupled from AIG size; new associativity give-up boundary; conflicts/steps/time not exposed for give-ups; give-up wall time scales with load; `^` vs `xor` |
| DETERMINISM | 0 | all AIG counts/conflicts stable; 12 goldens stable |


## Takeaway
AIG node counts grow smoothly and deterministically with width and never misbehave; the real surprise is that the prove/give-up verdict is decoupled from node count (23 extra nodes flip it) and that conflicts/steps/time are largely unobservable for give-ups — so any "give-up at low node count" heuristic is unsafe.

### Original takeaway (verbatim)
AIG node counts grow smoothly and deterministically with width and never misbehave;
the real surprise is that the prove/give-up verdict is decoupled from node count
(23 extra nodes flip it) and that conflicts/steps/time are largely unobservable for
give-ups — so any "give-up at low node count" heuristic is unsafe.
