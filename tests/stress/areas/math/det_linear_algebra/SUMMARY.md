# SUMMARY — `det_linear_algebra`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 6
- Files created: not recorded

### Coverage
- **Distinct matrix cases / queries tried: ~1,500.** Breakdown:
  - 579 identity cases (`gen.py`): Z/Q determinants, `det(AB)=det(A)det(B)`, transpose,
    row-swap sign, triangular, singular families, Vandermonde, big entries, Hilbert/Cauchy/rational
    over Q, Z/n and GF(2^8) determinants, charpoly/trace, inverses, `algebra.factor`.
  - 354 differential-fuzz cases (`fuzz.py`): dense/sparse/Hankel/Toeplitz/Vandermonde/Pascal/
    companion/bigint Z matrices; Hilbert/Cauchy/rational Q matrices; 17 moduli (prime and
    composite); GF(2^8) default and aes — all compared with `sympy` / a GF(2^8) oracle.
  - ~600 targeted probes: composite moduli, entries ≥ modulus, modulus edge values, singular
    inverses, SNF/HNF/inverse certificate reconstruction, GF(2^8) modulus handling, irreducible/
    reducible polynomial moduli, crash/hang and matrix-size limits.
- **Oracles:** Python `fractions`/`sympy` (exact rationals), a hand-written GF(2^8) field with both
  `0x11d` (ucas default) and `0x11b` (aes) moduli, plus metamorphic identity cross-checks.
- **Interfaces:** CLI (`--json -e`, file mode) and MCP JSON-RPC wire mode (`--mcp`) driving
  `abstract_algebra` (`zmatrix`, `qmatrix`, `fxmodule`, `snf`, `hnf`), `rings`
  (`matrix`, `gf2matrix` schema probe), and `algebra` (`factor`, `expand`).

### Files created (this folder only)
- Goldens (deterministic, verified by double-run diff):
  - `01_zdet_identities.ucas` + `.out`
  - `02_qdet_hilbert.ucas` + `.out`
  - `03_mod_gf_det.ucas` + `.out`
  - `04_snf_hnf.ucas` + `.out`
  - `mcp_det_identities.jsonl` + `.out`
  - `mcp_gf_det.jsonl` + `.out`
- Reproducers (documented in FINDINGS; intentionally NOT goldens):
  - `repro_hang_charpoly.jsonl`
  - `repro_gf_modulus_omission.ucas`
  - `repro_large_det.py`, `repro_mcp_large_det.py`
- Reports: `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 1 | — |
| LIMIT | 3 | — |

### Issues by severity
- `CRASH`: 0
- `WRONG`: 0 (no wrong determinant, rank, inverse, characteristic polynomial or SNF found)
- `HANG`: 1 — `fxmodule` charpoly on an 11×11 integer matrix > 30 s (exponential growth)
- `NLP`: 0
- `DETERMINISM`: 0 (all goldens byte-identical across two runs)
- `LIMIT`: 3 — MCP large matrix arguments silently truncated → `parse_error`; GF(2^8) with
  explicit integer modulus omits the determinant value; Q/modular determinants carry no
  `checks` certificate (low).


## Takeaway
Determinant and linear-algebra identities are sound across Z, Q, Z/n and GF(2^8) on ~1,500 oracle-checked cases; the only real defects are a slow `fxmodule` charpoly path and two result-reporting/MCP-argument limits — no wrong determinants.

### Original takeaway (verbatim)
Determinant and linear-algebra identities are sound across Z, Q, Z/n and GF(2^8) on ~1,500
oracle-checked cases; the only real defects are a slow `fxmodule` charpoly path and two
result-reporting/MCP-argument limits — no wrong determinants.

Confirmed: all work stayed inside `tests/stress/areas/math/det_linear_algebra/`.
