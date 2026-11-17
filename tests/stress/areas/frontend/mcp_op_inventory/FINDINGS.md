# Stress findings — `mcp_op_inventory`

_Original heading: FINDINGS — `mcp_op_inventory`_

# FINDINGS — `mcp_op_inventory`

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 3 | LIMIT (mma is ~9 s per call; a batch of 6 exceeds even `timeout 30`) |
| DETERMINISM | 1 | DETERMINISM (adamfit embeds wall-clock time in the MCP response) |

## Findings

### DETERMINISM-1 — DETERMINISM (adamfit embeds wall-clock time in the MCP response)
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (no golden kept`._
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_op_inventory
timeout 15 $ROOT/ucas --mcp < 35a_valid0.jsonl > /tmp/a.out 2>/dev/null
timeout 15 $ROOT/ucas --mcp < 35a_valid0.jsonl > /tmp/b.out 2>/dev/null
diff /tmp/a.out /tmp/b.out
```

**Observed:** output (the only differing line):
```
< ... "  best candidates ... af6(x) = fma(x, x - (-5.31804838e-18), 1.0)\n  5.07 s\n"}
---
> ... "  best candidates ... af6(x) = fma(x, x - (-5.31804838e-18), 1.0)\n  5.04 s\n"}
```
All of `structuredContent.result` (candidates, bounds, scores, proof) is byte-identical; only
the trailing `X.XX s` wall-clock timing in `content[0].text` / `structuredContent.text` moves.

**Why it matters:** an MCP response is not reproducible: a test runner diffing two runs sees a
failure that has nothing to do with the mathematical result. A golden `.out` cannot be kept for
`adamfit` (same applies to any op that prints elapsed time).
**Expected:** either omit the timing
from the structured/text response or move it to a separate diagnostic field.

### LIMIT-1 — LIMIT (mma is ~9 s per call; a batch of 6 exceeds even `timeout 30`)
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_op_inventory
# original combined file (removed) with 6 mma calls:
timeout 30 $ROOT/ucas --mcp < 34_mma.jsonl > /tmp/m.out   # EXIT=124 (timeout)
```
Measured per call (`34a`..`34e`): 9.01 s, 9.11 s, 6.64 s, 9.04 s, 9.32 s. Each individual call
completes in <15 s and is deterministic; only the cumulative batch timed out.

**Resolution /
**Why it matters:** the coverage catalog split `mma` into one-call files
(`34a_valid0.jsonl` … `34f_malformed.jsonl`) so each golden fits `timeout 15`. Not an
unsoundness, but a real cost/UX limit for an op that a test suite may batch.

### LIMIT-2 — LIMIT (ec_pairing: setting the documented optional `kind` without P/Q/n fails)
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/mcp_op_inventory
grep -n '"id": [345]' 16_ec_pairing.out
```
`16_ec_pairing.jsonl` ids 3–5 set `kind: "weil"` / `"tate"` (the exact enum values from
`session schema`, which documents `kind` as optional, "default weil") without points:

**Observed:** output:
```
id 3 ok False :: <json>:1:11: error: expected a point: (x, y), G, O or random
id 4 ok False :: <json>:1:11: error: expected a point: (x, y), G, O or random
id 5 ok False :: <json>:1:11: error: expected a point: (x, y), G, O or random
```
Supplying `P,Q` then demands `n`, and `n` then demands valid points — the positional grammar
behaves as `curve, P, Q, n, kind`, so `kind` cannot be used alone despite being documented as an
optional enum. `{"curve":"bn254"}` alone returns the pairing fine.
**Expected:** accept `kind`
with the default points (as the no-`kind` form does), or document that P/Q/n are mandatory with
`kind`.

### LIMIT-3 — GAP (45 ops previously had only empty-args schema coverage)
**Severity:** LIMIT
_Original classification: `LIMIT (coverage`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
45 ops were exercised only with `args:{}` in schema-enumeration tests, so no real argument type,
math path, or error path was ever tested for them. They are listed in the table below with an
example valid call's observed result. All are now covered by goldens in this folder.

## Checks that passed

### Scope
Enumerated all **248** callable MCP operations from `tools/list` (239 grouped `op` values
across 18 tool schemas + 9 standalone tools = 27 tools) and cross-checked `session schema`
(`session/op=schema` reports exactly 248 `commands`). Then searched all 11,928 files under
`tests/stress/*/` for genuine coverage.

**Coverage result:** 203 ops have at least one genuine stress test (valid args in a non-meta
`.jsonl` or a tool-name call). **45 ops had NO genuine coverage** — they occurred only in
`mcp_codemode_schemas/mcp_all_ops.jsonl` and friends, always with empty `args:{}` (schema
enumeration / missing-arg envelope checks), never with real arguments. Those 45 are the
subject of this folder.

For each of the 45 GAP ops: 5 valid calls + 1 malformed call were generated (258 calls total),
using exact arg names/types from `session schema`. Every call was run under `timeout 15`,
twice, and diffed. Deterministic calls were kept as golden `NN_<op>.out`.

Note on scope: "coverage" here is specifically MCP-side (`tools/call` with real `args`). A
parallel CLI-focused area (`tests/stress/areas/frontend/command_inventory/`) added `.ucas` probes for many of
the same commands after this scan; this area supplies the MCP valid-args/arg-type coverage,
which `.ucas` statements do not exercise (JSON-RPC envelopes, `structuredContent`, typed args).

### Negative results (things checked, not found)
- **No CRASH**: all 258 calls returned JSON-RPC responses; no signal/nonzero exit/truncated JSON.
- **No HANG**: every single call finished well under 15 s (max ~9 s for `mma`).
- **No WRONG envelope**: `structuredContent.ok` and `isError` were consistent everywhere;
  every response had a `cmd` field.
- **No accepted-malformed**: all 45 malformed calls were rejected (35 `bad_request`,
  5 `parse_error`, 2 `failed`, 1 `unsupported`, 1 JSON-RPC `-32602` for non-object `args`).

### Coverage + result table (op -> covered? / GAP / example valid args -> observed result)
Every row: covered="no (empty-args only)" before this work; GAP="NEW"; result column =
`N ok / M semantic-error / K rejected` plus the first success headline.

| op | covered? | GAP | example valid args -> observed result |
|---|---|---|---|
| `abexact` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: Z -> Z/4 -> Z/2: exact at Z/4 |
| `absub` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: the subgroup generated in Z/2 + Z/12: Z/2 + Z/2 |
| `pmsnf` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: Smith form over F_p[x]: diag(x, x^2), rank 2 |
| `space` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: S^2: cell complex of dimension 2 |
| `homology` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: H_*(S^2; Z) |
| `cohomology` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: H^*(S^2; Z) |
| `les` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: long exact sequence of 0 -> C^*(S^2) -2-> C^*(S^2) -> C |
| `bockstein` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: Bockstein spectral sequence of RP^2 at p = 2 |
| `bockstein_trace` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: Bockstein spectral sequence of RP^2 at p = 2: tracing H |
| `prop01` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: Proposition 0.1 on RP^2 at p = 2: if a in H^n(X; Z) gen |
| `ec_binary` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: y^2 + x y = x^3 + 0x1 x^2 + 0x1 over GF(2^163) |
| `ec_cm` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: y^2 = x^3 + 32 over F_4274828413 |
| `ec_decompress` | no (empty-args only) | NEW | 3 ok / 1 semantic / 0 rejected; first: (0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2 |
| `ec_dlog` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: k = 1 |
| `ec_isogeny` | no (empty-args only) | NEW | 4 ok / 1 semantic / 0 rejected; first: 3 rational 2-isogenies from j = 36 |
| `ec_pairing` | no (empty-args only) | NEW | 2 ok / 4 semantic / 0 rejected; first: e(G1, G2) on BN254: reduced Tate pairing in F_p^12 |
| `ec_volcano` | no (empty-args only) | NEW | 4 ok / 1 semantic / 0 rejected; first: the 2-isogeny graph of j = 36 (breadth first, at most 6 |
| `ec_weak` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: y^2 = x^3 + 2592469188103234411x + 12679997811118790130 |
| `ecdh` | no (empty-args only) | NEW | 4 ok / 1 semantic / 0 rejected; first: shared secret: x = 0xd7924d4f7d43ea965a465ae3095ff41131 |
| `ecdsa_sign` | no (empty-args only) | NEW | 4 ok / 1 semantic / 0 rejected; first: signature (r, s) on secp256k1 with SHA-256 |
| `ecdsa_verify` | no (empty-args only) | NEW | 3 ok / 1 semantic / 0 rejected; first: invalid signature |
| `ecm` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: 8051 = 83 * 97 |
| `ecpp` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: 104729 is prime |
| `ed25519_sign` | no (empty-args only) | NEW | 4 ok / 1 semantic / 0 rejected; first: 1b79abc415a34efe5915b4c1b53d2435e731b3c92d0ba440de29cab |
| `ed25519_verify` | no (empty-args only) | NEW | 2 ok / 1 semantic / 0 rejected; first: invalid signature |
| `hilbert` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: H_-3(x) = x |
| `modpoly` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: Phi_2(X, Y) = (X^3 + Y^3) - X^2*Y^2 + 1488*(X^2*Y^1 + X |
| `x25519` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: 439e9f4dd07aa75e39c222d17c226ea1b68b95442380b5720c7879c |
| `x448` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: 556fe623c1426ac3c4c4580fc442ade41191b9df1efab047813f356 |
| `banks` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: banks under gt1030: 32 banks of 4 bytes, a warp of 32 l |
| `dword` | no (empty-args only) | NEW | 2 ok / 4 semantic / 0 rejected; first: dword: x has no f64 arithmetic whose result is its valu |
| `foldproof` | no (empty-args only) | NEW | 2 ok / 4 semantic / 0 rejected; first: foldproof x: no float conversion round trip (T -> a nar |
| `intatomic` | no (empty-args only) | NEW | 3 ok / 3 semantic / 0 rejected; first: intatomic x under gt1030: a shared float atomic add of  |
| `mma` | no (empty-args only) | NEW | 5 ok + 1 rejected (split goldens 34a–34f); first: mma m16n8k16: D = A B + C on a warp's fragments, 32 lanes |
| `adamfit` | no (empty-args only) | NEW | 5 ok + 1 rejected (reproducers 35a–35f; NO golden — nondet timing); first: adamfit x^2+1 in 0..1 -> f32, 2000 shapes |
| `more` | no (empty-args only) | NEW | 5 ok + 1 rejected (after a `find` setup); first: more for u8(x >= 0 && x <= 15) == x + 2 |
| `rop` | no (empty-args only) | NEW | 2 ok / 4 semantic / 0 rejected; first: rop F: the update = x, applied once per fragment (x the |
| `help` | no (empty-args only) | NEW | 5 ok / 0 semantic / 1 rejected; first: definitions |
| `scheme` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: evaluation schemes for x^2 under gt1030 |
| `continuous` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: x^2 has no loops |
| `trig` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: note: x is taken as real |
| `injective` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: injective x^3: |
| `surjective` | no (empty-args only) | NEW | 4 ok / 2 semantic / 0 rejected; first: surjective x^3: |
| `bijective` | no (empty-args only) | NEW | 5 ok / 1 semantic / 0 rejected; first: bijective x^3: |
| `dtft` | no (empty-args only) | NEW | 4 ok / 2 semantic / 0 rejected; first: DTFT of 4 values: X(w) = sum_n x[n] e^(-iwn) |
