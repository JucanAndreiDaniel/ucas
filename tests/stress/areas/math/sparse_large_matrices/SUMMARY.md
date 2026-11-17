# SUMMARY — `sparse_large_matrices`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 7
- Files created: not recorded

### Counts

- **Distinct matrices generated:** 157 (seeded, deterministic; sizes 1×1 … 100×100,
  plus a few 150×150 MCP probes).
- **Distinct differential queries:** 1 971
  - 1 298 in `_harness.py` (CLI `zmat`/`qmat`/`snf`/`hnf`, mod-p `det`/`rank`,
    MCP `snf`/`hnf`/`zmatrix inverse` certificate checks),
  - 673 in `_harness2.py` (integer/rational solve, modular inverse,
    modular nullspace, GF(2^8) determinant, malformed inputs, determinism).
- **Certificate / substitution checks:** 1 496
  (SNF `U A V = D` + `U U⁻¹ = I` + `V V⁻¹ = I`; HNF `U A = H`; solve `A x = b`;
  inverse `A A⁻¹ = I`; modular `M M⁻¹ = I`; nullspace `M v = 0`).
- **Oracle mismatches in core matrix operations:** 0.
- **Issues found:** 4
  - `WRONG`: 1 (`pmsnf` silently drops rows/columns past index 64 → wrong Smith form)
  - `LIMIT`: 3 (MCP large-matrix serialization truncation; mod-p path rejects
    ≥2^64 entries; lenient trailing-comma/flat-row grammar)

### Files created

- Goldens (deterministic, generated from this folder, verified twice):
  - `01_sparse_structured.ucas` + `.out`
  - `02_mod_gf_sparse.ucas` + `.out`
  - `mcp_sparse_matrices.jsonl` + `.out`
  - `repro_pmsnf_64rows.ucas` + `.out`
  - `repro_pmsnf_65rows.ucas` + `.out`
  - `repro_pmsnf_65rows_control.ucas` + `.out`
  - `repro_pmsnf_65cols.ucas` + `.out`
- Reproducer script: `repro_mcp_large_sparse.py`
- Harnesses (differential oracles, not goldens): `_harness.py`, `_harness2.py`
- Run logs / raw results: `_run*.log`, `_mismatches*.json`, `_counts2.json`,
  `_toolslist.json`, `_batch.ucas` (scratch, overwritten by each batch)
- Reports: `FINDINGS.md`, this `SUMMARY.md`


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| LIMIT | 3 | — |

## Takeaway
Core sparse/large integer-rational-modular matrix arithmetic is oracle-correct with verified certificates across 157 matrices and ~2 000 queries; the one real defect is `pmsnf` silently ignoring rows and columns after the 64th, which yields a wrong Smith normal form while still reporting a passing self-check.

### Original takeaway (verbatim)

Core sparse/large integer-rational-modular matrix arithmetic is oracle-correct with
verified certificates across 157 matrices and ~2 000 queries; the one real defect
is `pmsnf` silently ignoring rows and columns after the 64th, which yields a wrong
Smith normal form while still reporting a passing self-check.
