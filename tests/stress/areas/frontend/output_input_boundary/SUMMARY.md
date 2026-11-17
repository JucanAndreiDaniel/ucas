# SUMMARY — `output_input_boundary`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 4
- Files created: not recorded

### Counts

- **Chained steps executed: 421** across 13 groups (`driver.py`, raw log
  `driver_results.json`). Breakdown:
  - `A_text_feedback`: 43 seeds × up to 5 generations = **211** steps
    (full CLI `text` field pasted back as new source).
  - `A_file_feedback`: 12 seeds × up to 4 generations = **48** steps
    (same, pasted back as a `.ucas` file).
  - `B_find_equiv`: 8 · `C_gates_equiv`: 5 · `D_c_roundtrip`: 8 ·
    `E_spirv_roundtrip`: 3 · `F_proofs`: 8 · `G_english`: 20 ·
    `H_files`: 1 · `I_witness`: 6 · `J_state_leak`: 9 ·
    `K_amplification`: 6 · `Z_determinism`: 4 (each run twice).
- **Distinct seed expressions / queries / code snippets:** 43 (A) + 12 (A-file,
  subset) + 8 (find) + 5 (gates) + 8 (C) + 8 (proofs) + 20 (English) + 3
  (SPIR-V/C) + 6 (witness pairs) + 3 (state feeds) ≈ **105 distinct inputs**,
  expanded into 421 chained invocations.
- **Files created:** `driver.py`, `driver_results.json`, `FINDINGS.md`,
  `SUMMARY.md`, and 4 deterministic goldens
  (`01_show_text_feedback`, `02_english_statements_roundtrip`,
  `03_find_expr_roundtrip`, `mcp_output_to_input` — each `.ucas`/`.jsonl` +
  `.out`).
- **Issues by severity:** `LIMIT` 2 · `WRONG` 2 (finding 2 has sub-parts 2a/2b/2c)
  · `NLP` 1. No `CRASH`, no `HANG`, no `DETERMINISM` issue found.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| NLP | 1 | — |
| LIMIT | 2 | — |

## Takeaway
ucas's machine-formatted `text` is **not** a re-ingestible source language: 42/43 answers fail when pasted back, ~1/3 of them *amplify* their own parse errors (29→10111 bytes in 5 generations), and the lines that do parse silently install definitions that `state`/`funcs` cannot see — while the structured `result.*`/`files` seams (find/gates/C/SPIR-V/proof text) round-trip cleanly except for an undocumented `files[]`↔`content[].data` mismatch for GIFs.

### Original takeaway (verbatim)

ucas's machine-formatted `text` is **not** a re-ingestible source language: 42/43
answers fail when pasted back, ~1/3 of them *amplify* their own parse errors
(29→10111 bytes in 5 generations), and the lines that do parse silently install
definitions that `state`/`funcs` cannot see — while the structured
`result.*`/`files` seams (find/gates/C/SPIR-V/proof text) round-trip cleanly
except for an undocumented `files[]`↔`content[].data` mismatch for GIFs.

### Confinement

All work stayed in `tests/stress/areas/frontend/output_input_boundary/`. No source file,
Makefile, existing test or `opencode.json` was edited; no build, git or commit
commands were run. Every subprocess was bounded by `timeout`.
