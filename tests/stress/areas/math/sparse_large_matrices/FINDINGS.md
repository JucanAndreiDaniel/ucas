# Stress findings — `sparse_large_matrices`

_Original heading: FINDINGS — `sparse_large_matrices`_

# FINDINGS — `sparse_large_matrices`

Area: sparse and large matrix operations (up to 100×100), via CLI (`zmat`, `qmat`,
`snf`, `hnf`, `det/rank/nullspace/inverse … mod p`, `in GF(2^8)`, `pmsnf`) and MCP
(`abstract_algebra.zmatrix/qmatrix/snf/hnf/pmsnf`, `rings.matrix`).

All reproducers use the absolute binary `$ROOT/ucas` and were run
from this folder.  Deterministic reproducers also have `.ucas`+`.out` or
`.jsonl`+`.out` goldens, generated from this folder under `timeout 30` and verified
byte-identical on a second run.

Baseline: 157 generated matrices, 1 971 differential queries against Python
`fractions` / hand-written field oracles, 1 496 certificate/substitution checks —
**no wrong determinant, rank, SNF, HNF, inverse, solve, modular result, broken
certificate, crash, hang or nondeterminism in the core matrix operations.**  The
issues below are a silent truncation in the polynomial-matrix Smith form, a large-
matrix MCP serialization limit, and two low-severity capability gaps.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | `pmsnf` silently drops rows and columns past the 64th |
| LIMIT | 3 | MCP argument serializer truncates large matrices (>~52 KB) |

## Findings

### WRONG-1 — `pmsnf` silently drops rows and columns past the 64th
**Severity:** WRONG
_Original classification: `WRONG (silent truncation; wrong answer with a self-reported`._
  passing certificate).
- **Reproducer (CLI, rows):**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/sparse_large_matrices
  timeout 30 $ROOT/ucas repro_pmsnf_65rows.ucas > /tmp/r65.out 2>&1
  head -2 /tmp/r65.out
  timeout 30 $ROOT/ucas repro_pmsnf_65rows_control.ucas > /tmp/r64.out 2>&1
  head -2 /tmp/r64.out
  ```
  `repro_pmsnf_65rows.ucas` = 64 rows `[x]` followed by one row `[1]`
  (65 rows, 1 column).  The control has 63 rows `[x]` + one row `[1]` (64 rows).
- **Observed output:**
  ```
  > pmsnf [[x],...,[x],[1]]         # 65 rows
  Smith form over Q[x]: diag(x), rank 1
  ...
  > pmsnf [[x],...,[x],[1]]         # 64 rows (control)
  Smith form over Q[x]: diag(1), rank 1
  ...
  ```
  The 65th row `[1]` is never read, so the Smith form stays `diag(x)` instead of
  becoming `diag(1)`.  The same happens with columns: `repro_pmsnf_65cols.ucas`
  (one row with 64 `x` entries and a trailing `1`) also prints `diag(x)`; with only
  64 columns the trailing `1` would give `diag(1)`.  Both capped cases still print
  `check: U A V = D; … verified` for the *truncated* matrix, so the interface gives
  no hint that input was lost.
- **MCP is affected too** (the `abstract_algebra.pmsnf` op with a matrix string):
  a 65-row `[[x],…,[1]]` also returns `diag(x)`.
- **
**Why it matters:** `src/absalg_cmd.c:2278` uses `split_commas(body+1, rows, 64)`
  and line 2285 uses `split_commas(r+1, cells, 64)`.  `split_commas` caps `n` at the
  array size and returns 64, so entries 65 and beyond are silently discarded before
  `pm_init`/the parse loop.  There is no warning.
**Expected:** either read all rows
  (dynamic array, as `need_matrix` does for `snf`/`zmat`) or return `"too many
  rows/columns"` explicitly.  This is exactly the "silent row/column truncation"
  failure mode under test.
- **Files:** `repro_pmsnf_64rows.ucas/.out`, `repro_pmsnf_65rows.ucas/.out`,
  `repro_pmsnf_65rows_control.ucas/.out`, `repro_pmsnf_65cols.ucas/.out`.

### LIMIT-1 — MCP argument serializer truncates large matrices (>~52 KB)
**Severity:** LIMIT
_Original classification: `LIMIT (large-matrix path only; the CLI path is correct`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- **Reproducer:**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/sparse_large_matrices
  python3 repro_mcp_large_sparse.py > /tmp/mlarge.jsonl
  timeout 30 $ROOT/ucas --mcp < /tmp/mlarge.jsonl > /tmp/mlarge.out 2>&1
  tail -c 300 /tmp/mlarge.out
  ```
- **Observed output** (150×150 identity, one `abstract_algebra.zmatrix rank` call):
  ```
  ... "error": {"code": "parse_error",
                "message": "bigint: unexpected \"\"",
                "pos": {"line": 1, "col": 6}}, "isError": true}
  ```
  The same matrix sent through the CLI works:
  `zmat rank <150×150 identity>` → `rank = 150` in well under a second.  The 100×100
  identity (≈30 KB JSONL) still works over MCP (`rank = 100`); the break happens
  between ≈52 KB and ≈56 KB of generated statement, where the serializer silently
  cuts the matrix text.
- **Why it is a bug / expected:** a user asking for a routine large sparse-matrix
  rank gets a confusing parse error instead of an answer.  `rings.matrix` already
  guards this with a clean `{"code":"unsupported","message":"that is too long for
  me"}`; `zmatrix`/`qmatrix`/`fxmodule` should do the same, or stream the matrix
  without a length ceiling.  (Also observed independently in the sibling
  `det_linear_algebra` area; reproduced here on a 150×150 sparse identity.)

### LIMIT-2 — mod-p matrix path rejects entries at/above 2^64 (clean error)
**Severity:** LIMIT
_Original classification: `LIMIT (documented behaviour, not an unsound answer`._
**Expected:** _not recorded_
- **Reproducer:**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/sparse_large_matrices
  printf '%s\n' 'det [[1267650600228229401496703205376,0],[0,3]] mod 7' > /tmp/b.ucas
  timeout 15 $ROOT/ucas /tmp/b.ucas 2>&1
  ```
- **Observed output:**
  ```
  /tmp/b.ucas:1:6: error: 1267650600228229401496703205376 is too large
      det [[1267650600228229401496703205376,0],[0,3]] mod 7
  ```
- **
**Why it matters:** the `zmat`/`snf` bigint path accepts arbitrary-size entries
  (`zmat det [[2^100,0],[0,3]]` works and reduces correctly), but the `mod p` and
  `GF(2^8)` entry parser is machine-word based.  Entries at 2^63, 2^64−1 are
  accepted and reduced correctly; ≥2^64 is rejected.  Worth knowing when mixing
  bigint structure with modular reduction; no wrong value is produced.

### LIMIT-3 — lenient matrix grammar accepts trailing commas and flat rows
**Severity:** LIMIT
_Original classification: `LIMIT / observation (not a wrong answer`._
**Expected:** _not recorded_
- **Reproducer:**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/sparse_large_matrices
  printf '%s\n' 'zmat det [[1,2,],[3,4]]' 'zmat rank [1,2,3,4]' > /tmp/len.ucas
  timeout 15 $ROOT/ucas /tmp/len.ucas 2>&1
  ```
- **Observed output:**
  ```
  > zmat det [[1,2,],[3,4]]
  det = -2
  > zmat rank [1,2,3,4]
  rank = 1
  ```
- **
**Why it matters:** these are accepted by design (`need_matrix`'s flat-row
  branch and permissive comma handling), but a trailing comma inside a row and a
  single un-nested row are common malformed-input markers in other CAS frontends.
  No wrong result: `[[1,2,],[3,4]]` is parsed as `[[1,2],[3,4]]` and `[1,2,3,4]`
  as a 1×4 matrix.  Recorded so the leniency is explicit; genuinely ragged rows
  (`[[1,2],[3]]`) ARE rejected cleanly with `the rows have different lengths`.

## Checks that passed

### Non-findings / positive results worth recording
- Oracle-checked (0 mismatches): `zmat det/rank` and `qmat det/rank` on zero,
  identity, diagonal with 2^63/2^64/10^30/2^100 entries, banded (widths 1–10),
  upper/lower triangular, permutation, rank-1 outer products, duplicate/zero-row,
  duplicate/zero-column and linear-combination rank-deficient matrices, rectangular
  (incl. 100×5, 5×100, 75×40), sparse random (density 0.002–0.5), Pascal,
  Vandermonde, Hilbert, Cauchy, companion, Toeplitz, Hankel and nilpotent forms.
- `snf`: diagonals satisfy `d_i ≥ 0`, `d_i | d_{i+1}`, `rank = #nonzero`, and
  `∏ d_i = |det|` for square matrices — including singular and 2^70-entry cases.
  MCP `snf` certificates re-checked by substitution: `U A V = D`, `U U⁻¹ = I`,
  `V V⁻¹ = I`, `check.passed = true`.
- `hnf`: `U A = H` verified by substitution; rank matches the oracle.
- `zmat inverse` invertible iff `|det| = 1`; `zmat solve` solutions satisfy `A x =
  b`, unsolvable systems report `no integer solution` (with the over-Q witness),
  and the general-solution basis is emitted only for singular `A`.
- `qmat inverse` verified by `A A⁻¹ = I`; rational singular matrices correctly
  report `singular: no inverse`.
- mod-p `det`/`rank`/`inverse`/`nullspace` matched a hand-written field oracle for
  p = 2, 7, 1 000 003 on sparse and rank-deficient matrices: inverse products are
  `I`, nullspace dimension is `n − rank`, and every basis vector satisfies `M v = 0`.
- GF(2^8) determinants matched a hand-written field implementation (default
  modulus 0x11d and `aes`); negative integer entries are embedded as their
  char-2 reductions (e.g. `−4 → 0x04`), which is consistent with the documented
  integer notation.
- Malformed inputs (ragged rows in `zmat`/`snf`/`qmat`/`det … mod p`, empty rows,
  double commas, unclosed brackets, non-numeric cells) return clean errors with no
  crash or hang, through both CLI and MCP.
- Determinism: 40 representative matrices × 4 operations (`zmat det/rank`,
  `snf`, `hnf`) produced byte-identical output on two runs; all golden files were
  also verified byte-identical on a second run.
