# SUMMARY — `thesis_mr_mining`

## Counts
- Distinct expressions/queries tried: 1,250
- Goldens written: 331
- Files created: not recorded

### Scope
Mined implicit relations from the 250-file `tests/*.ucas` corpus (212 `equiv`
statements found), built meaning-preserving metamorphic relations from them, and
checked functional coupling across `equiv` / `range` / `domain` / `wrap` / `find` /
`gates`, plus LCF proof-kernel mutation through the `proofs` MCP tools.

### Counts
- Distinct expressions / queries tried: **~1,250**
  - 152 MR files × 4 `equiv` queries = 608
  - 80 coupling files × 2–5 commands ≈ 210
  - 14 domain/wrap/range consistency files × 4 commands = 56
  - 40 false/vacuous proof statements × (`theorem`,`prove`,`check`,`axioms`) = 160
  - 40 additional proof statements × 4 = 160
  - 4 dedicated finding reproducers + 9 MCP calls + probes ≈ 50
- Files created in this folder:
  - **330** `.ucas` reproducers + **330** matching CLI `.out` goldens
  - **1** `mcp_proof_mutation.jsonl` + its `.out` golden
  - `FINDINGS.md`, `SUMMARY.md`
- All 330 CLI files and the MCP golden were run twice and byte-compared: **0
  nondeterministic**, **0 timeouts**, **0 nonzero exits**, **0 slow (>5 s) cases**.

### Key reproducers
- `400_proof_axiom_mismatch.ucas` — `proof t_ab` prints empty `axioms used:` while
  `axioms t_ab` lists 4 axioms (see also `mcp_proof_mutation.out` ids 5–6).
- `401_domain_total_contradiction.ucas` — `domain` says "no conditions: total" yet
  "defined at 0 of 65536 points; C UB at 65536 points".
- `402_wrap_range_contradiction.ucas` — `range` "undefined everywhere" but `wrap`
  "equals the mathematical result everywhere" / dangling `e.g.`.
- `403_equiv_domain_asymmetry.ucas` — symmetry MR fails when domains differ.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | proof/axioms axiom-set contradiction; domain "total" vs 0 defined points; wrap contradicts range on UB/dangling e.g. |
| LIMIT | 2 | equiv asymmetry when domains differ; incomplete proof automation (no unsound acceptance) |

### Issues by severity
| Severity | Count | Short description |
|---|---|---|
| WRONG | 3 | `proof`/`axioms` axiom-set contradiction; `domain` "total" vs 0 defined points; `wrap` contradicts `range` on UB/dangling `e.g.` |
| CRASH | 0 | — |
| HANG | 0 | — |
| DETERMINISM | 0 | — |
| LIMIT | 2 | `equiv` asymmetry when domains differ; incomplete proof automation (no unsound acceptance) |


## Takeaway
Meaning-preserving rewrites and cross-command coupling checks are clean for ordinary functions, but the UB boundary is inconsistent: the `domain`, `range` and `wrap` commands disagree on functions that are undefined at some or all points, and the proof kernel's two axiom-reporting commands disagree on what a proof rests on.

### Original takeaway (verbatim)
Meaning-preserving rewrites and cross-command coupling checks are clean for ordinary
functions, but the UB boundary is inconsistent: the `domain`, `range` and `wrap`
commands disagree on functions that are undefined at some or all points, and the
proof kernel's two axiom-reporting commands disagree on what a proof rests on. No
unsound proof (false theorem accepted, or `prove` passing while `check` failed) and
no crash or hang was found.

### Folder confinement
All files were created only under `tests/stress/areas/sat/thesis_mr_mining/`. No existing
`tests/*.ucas` file, source file, Makefile or config was modified.
