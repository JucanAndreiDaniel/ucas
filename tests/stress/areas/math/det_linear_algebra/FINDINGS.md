# Stress findings — `det_linear_algebra`

_Original heading: FINDINGS — `det_linear_algebra`_

# FINDINGS — `det_linear_algebra`

Area: linear algebra via determinant/matrix identities inspired by the Mathematica `Det` bug.
Domains exercised: `Z` (`zmatrix`), `Q` (`qmatrix`), `Z/n` and `GF(2^8)` (`rings.matrix`),
characteristic/minimal polynomial (`fxmodule`), Smith/Hermite (`snf`/`hnf`), plus `algebra.factor`.
All findings below are reproduced with `$ROOT/ucas` from this folder.

No WRONG determinant, no crash and no unsound certificate was found: ~1500 cases were checked
against independent oracles (`sympy` exact rationals, a hand-written GF(2^8) field implementation,
and identity cross-checks). Everything below is a `HANG` (runtime limit) or a `LIMIT`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | `fxmodule` characteristic polynomial of an 11×11 integer matrix exceeds 30 s |
| LIMIT | 3 | large matrix arguments through MCP are silently truncated → confusing `parse_error` |

## Findings

### HANG-1 — `fxmodule` characteristic polynomial of an 11×11 integer matrix exceeds 30 s
**Severity:** HANG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- **Reproducer:**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/det_linear_algebra
  timeout 30 $ROOT/ucas --mcp < repro_hang_charpoly.jsonl > /tmp/hang.out 2>&1
  echo $?      # 124
  ```
  (`repro_hang_charpoly.jsonl` holds one `abstract_algebra`/`fxmodule` call on a fixed
  11×11 matrix of 64-bit integer entries; generated with `random.seed(20261116)`.)
- **Observed output:** exit code **124** (timeout). The file contains only the single
  `initialize` JSON-RPC response; there is **no response for `id:1`** after 30 s:
  ```
  {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": "2025-06-18", ... }}
  ```
- **Why it is a bug / expected:** `fxmodule` computes the characteristic polynomial via the Smith
  form of `xI - M` over `Q[x]`; the runtime grows dramatically with dimension/entry size.
  Measured on the same machine: n≤9 with small entries < 2 s; n=10 small entries 2–14 s;
  n=11 small entries > 30 s; n=7 with 64-bit entries 25–30 s; n=11 with 64-bit entries > 30 s
  (twice, reproducibly). A user asking for a routine 11×11 characteristic polynomial gets no
  answer within the standard bound. Not added as a golden because it would time out a test runner.

### LIMIT-1 — large matrix arguments through MCP are silently truncated → confusing `parse_error`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- **Reproducer (MCP path — fails):**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/det_linear_algebra
  python3 repro_mcp_large_det.py > /tmp/mlarge.jsonl
  timeout 30 $ROOT/ucas --mcp < /tmp/mlarge.jsonl 2>&1 | tail -c 400
  ```
- **Observed output (MCP):**
  ```
  ... "error": {"code": "parse_error",
                "message": "bigint: unexpected \"\"", "pos": {"line": 1, "col": 6}},
      "isError": true
  ... <json>:1:6: error: bigint: unexpected ""
      [... 70693 bytes of output omitted ...]
  ```
  For a 150×150 matrix the message was even `zmat: expected an integer matrix like [[1, 2], [3, 4]], got "[[2, 19, ...` with the matrix text cut off.
- **Same matrix through the CLI succeeds:**
  ```sh
  python3 repro_large_det.py > /tmp/large.ucas
  timeout 30 $ROOT/ucas /tmp/large.ucas 2>&1 | tail -n 3
  # det = 0
  #   how: Bareiss fraction-free elimination
  #   check: Gaussian elimination over Q gives 0
  ```
- **Why it is a bug / expected:** the MCP argument→ucas-statement serializer has an internal
  length ceiling (the generated statement works up to ~52 KB and breaks at ~56 KB). It silently
  emits a truncated statement, so the parser reports a nonsensical `bigint: unexpected ""`.
  By contrast `rings.matrix` detects the size and returns the clean
  `{"code":"unsupported","message":"that is too long for me"}`. `zmatrix`/`qmatrix`/`fxmodule`
  should do the same instead of garbling the request.

### LIMIT-2 — GF(2^8) determinant with an explicit integer modulus prints no determinant
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- **Reproducer:**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/det_linear_algebra
  timeout 15 $ROOT/ucas repro_gf_modulus_omission.ucas
  ```
- **Observed output:**
  ```
  > det [[83, 202], [127, 1]] in GF(2^8, 305)
    note: integers are elements in integer notation (the coefficients as base-2 digits): 0x53 = x^6 + x^4 + x + 1
  the 2x2 matrix over GF(2)[x]/(x^8 + x^5 + x^4 + 1)
    [0x53 0xca]
    [0x7f 0x01]
    how: row reduction by Euclid's algorithm on each column (only swaps and row subtractions, which keep the determinant up to sign)
  ```
  No `det = ...` line. JSON form: `ok:true`, `result.kind:"det"`, `result.method` and
  `result.headline` present, but **no `result.det` field**.
- **Why it is a bug / expected:** with a named/default GF(2^8) modulus the same command prints
  `det = 0xb5` (default `0x11d`) or `det = 0x75` (`modulus:"aes"` = `0x11b`). Supplying an explicit
  polynomial modulus switches to `GF(2)[x]/(m)` but the command then claims to run Euclid
  row reduction and returns success without ever reporting the determinant. It should either
  emit the value or return a clear "determinant over a general quotient ring is not supported"
  response. (Both irreducible and reducible integer moduli behave this way; 34 of the 256
  degree-8 moduli are irreducible in GF(2)[x].)

### LIMIT-3 — rational / finite-field determinants carry no verification certificate
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- **Reproducer (MCP, results copied from the golden `mcp_det_identities.out` / `mcp_gf_det.out`):**
**Observed:**
**Reproducer:**
  ```sh
  cd $ROOT/tests/stress/areas/math/det_linear_algebra
  grep -o '"checks":\[[^]]*\]' mcp_det_identities.out mcp_gf_det.out
  ```
- **Observed output:**
  - `zmatrix det [[1,2],[3,4]]` →
    `"checks":[{"kind":"check","passed":true,"text":"Gaussian elimination over Q gives -2"}]`
  - `qmatrix det` → `"checks":[]`
  - `rings.matrix det mod 7` / `in GF(2^8)` → `"checks":[]`
- **Why it is a bug / expected:** README ("An exact framework … every claimed fact computed with
  a certificate that is checked before it is printed") suggests each determinant should carry a
  checked certificate. Only the integer `zmat det` does; the Q and modular determinants are
  asserted with none. Independent oracle checks (sympy / GF(2^8) field arithmetic) found no
  wrong value, so this is an observability/documentation gap rather than an unsound answer.

## Checks that passed

### Non-findings (positive results worth recording)
- `det(AB) = det(A)·det(B)` held over `Z`, `Q`, `Z/n` (prime **and** composite moduli up to 2^40)
  and `GF(2^8)` (default `0x11d` and `aes`), including 1000-bit entries.
- `det(Aᵀ) = det(A)`, row-swap sign flip, triangular = diagonal product, singular ⇒ 0
  (duplicate/zero rows and columns, bigint singular matrices), Vandermonde, Hilbert, Pascal,
  Cauchy, Toeplitz, Hankel, companion matrices — all matched `sympy`.
- `A·A⁻¹ = I` for unimodular `Z` inverses, `Q` inverses and modular inverses; singular inverse
  requests correctly report "no inverse"/"not invertible over Z"/"det is not a unit".
- `fxmodule` characteristic/minimal polynomials and invariant factors matched `sympy` for
  n ≤ 6; trace = −(coeff of x^(n−1)), det = (−1)^n·(constant term), `charpoly(AB)=charpoly(BA)`.
- SNF invariant-factor product = |det|, divisibility `d_i | d_{i+1}`, HNF and `U A V = D`
  certificates all verified on random matrices.
- Non-square, ragged, empty, `1/0`, `nan`, and `1e100` inputs return clean errors — no crashes.

All golden files in this folder were generated from their own directory under `timeout 30` and
verified byte-identical on a second run (deterministic).
