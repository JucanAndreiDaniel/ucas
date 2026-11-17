# Stress findings — `algebra_ring_ff`

_Original heading: FINDINGS — `algebra_ring_ff`_

# FINDINGS — `algebra_ring_ff`

Area: exact-algebra / number-theory / finite-field MCP tools (`algebra`, `rings`,
`abstract_algebra`, `elliptic`, `elliptic_ff`, `properties`, `number_theory`-style ops).
All commands use the absolute binary `$ROOT/ucas`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 2 | `permgroup S1000` / degree ≥ 50 never finishes |
| WRONG | 1 | MCP `primroot` swaps `a` (candidate) and `n` (modulus), returning wrong yes/no answers |

## Findings

### WRONG-1 — MCP `primroot` swaps `a` (candidate) and `n` (modulus), returning wrong yes/no answers
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (the golden `mcp_primroot_wrong.jsonl` is committed in this folder):

```sh
cd $ROOT/tests/stress/areas/math/algebra_ring_ff
$ROOT/ucas --mcp < mcp_primroot_wrong.jsonl
```

**Observed:** output** (verdict lines from the MCP responses, ids 1–4):

```
id 1  ucas="primroot 11"  -> the smallest primitive root mod 11 is 2
id 2  ucas="primroot 2 11" -> yes: 1 is a primitive root mod 2 (its order is 1, phi(2) = 1)
id 3  ucas="primroot 3 7"  -> no: 1 is not a primitive root mod 3 (its order is 1, phi(3) = 2)
id 4  ucas="primroot 2 7"  -> yes: 1 is a primitive root mod 2 (its order is 1, phi(2) = 1)
```

**Ground truth** (CLI, correct syntax `primroot N A` = "is A a primitive root mod N?"):

```sh
printf 'primroot 7 3\nprimroot 7 2\nprimroot 11\n' | $ROOT/ucas
# yes: 3 is a primitive root mod 7 (its order is 6, phi(7) = 6)
# no: 2 is not a primitive root mod 7 (its order is 3, phi(7) = 6)
# the smallest primitive root mod 11 is 2
```

* `primroot({a:3, n:7})` asks "is 3 a primitive root mod 7?" → truth **yes**, MCP answers **no**.
* `primroot({a:2, n:7})` asks "is 2 a primitive root mod 7?" → truth **no**, MCP answers **yes**.

**Why it matters:** the MCP tool's declared arguments are `primroot(a, n, ring, modulus)`
with `a` = candidate and `n` = modulus ("whether a is one" / "smallest primitive root mod n"),
but the generated CLI statement (see the `ucas` field above) is `primroot a n`. The CLI grammar
is `primroot N A` (modulus first, candidate second), so the MCP layer emits the two numbers in
the wrong order. It then tests "is (n mod a) a primitive root mod a" instead of
"is a a primitive root mod n". The self-reported `check` passes because it checks the *wrong*
question, so this is an unchecked-at-the-interface wrong answer. Fix: emit `primroot n a`.

### HANG-1 — `permgroup S1000` / degree ≥ 50 never finishes
**Severity:** HANG
_Original classification: `HANG (and the timeout kills the MCP server process, taking down the session`._
**Reproducer:**

**Observed:**
```sh
printf 'permgroup S1000\n' | timeout 12 $ROOT/ucas
# exit 124, no output
$ROOT/ucas --mcp < <(cat <<'EOF'
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"abstract_algebra","arguments":{"op":"permgroup","args":{"group":"S1000"}}}}
EOF
)   # hangs: exit 124, only the `initialize` response is emitted
```

Threshold sweep (each bounded by `timeout 8`):

```
S10  EXIT=0  (order 3628800)
S20  EXIT=0
S30  EXIT=0
S50  EXIT=124  (partial: "S50: a permutation group of degree 50, order 3041..." then hangs)
S100 EXIT=124  (no output)
S200 EXIT=124  (no output)
S500 EXIT=124  (no output)
S1000 EXIT=124 (no output)
```

When this op is issued through the OpenCode MCP client, the harness wall-clock timeout kills the
`ucas` child: the tool returns `MCP server "ucas" failed: Connection closed: MCP server process
exited`, and **every subsequent call in the session** fails with `MCP server "ucas" is not
connected`. One bad call therefore destroys the whole MCP session.

**Why it matters:** Schreier–Sims on S_n should either complete or hit a declared resource limit.
For degree ≥ 50 it stalls with no output and no `timeout`/`failed` response, and it takes the MCP
server down.
**Expected:** a bounded computation or a clean `timeout`/`failed` JSON-RPC error.

### HANG-2 — `ring Z/1000000007` enumerates a billion units
**Severity:** HANG
_Original classification: `HANG (and the timeout kills the MCP server process, taking down the session`._
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'ring Z/1000000007\n' | timeout 12 $ROOT/ucas
# exit 124
```

**Observed:** output (partial, 486 bytes before the timeout):

```
Z/1000000007: the integers mod 1000000007
  1000000007 elements, characteristic 1000000007
  a field: yes (1000000007 is prime: every nonzero a has an inverse, a^(1000000007-2)); so also an integral domain
  units: phi(1000000007) = 1000000006: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, ... (1000000006 in all)
  unit group: C1000000006 (order 1000000006, exponent lambda(1000000007) = 1000000006); cyclic, generated by the primitive root 5
```

Via the OpenCode MCP client, `rings.ring({ring:"Z/1000000007"})` returned
`MCP tool "rings" on server "ucas" failed: Connection closed: MCP server process exited`, and all
following calls failed with `MCP server "ucas" is not connected`.

**Why it matters:** `ring` eagerly materialises/prints the full unit list even when the ring has
~10^9 elements. A summary operation should not enumerate a billion elements; it should print the
count and stop, or refuse with a clean error. As with finding 2, one such call kills the MCP
session. (By contrast `qr 1000000007` correctly refuses with `qr: n up to 2^24`, so the designer
was aware of the general problem but `ring` has no such guard.)

## Checks that passed

### Notes / non-bugs worth recording
* **Flat mode argument shape.** With `--flat`, the tool name is the op and the arguments are the
  op's own args directly (`{"name":"factor","arguments":{"f":"x^2-1"}}`). Passing the usual
  wrapped `{"op":"factor","args":{...}}` shape gives `bad_request: factor has no argument "op"`.
  This is correct behavior, documented here so it is not mistaken for a bug (see
  `mcp_flat.jsonl` / `mcp_flat.out`).
* Edge cases that behaved **correctly** and were stress-tested: `n=1` (`phi 1`, `carmichael 1`,
  `ring Z/1`, `sqrtmod ... mod 1`, `primroot 1`), `n=0` rejected cleanly (`phi 0`, `carmichael 0`,
  `factorint 0`, `ring Z/0`, `magic 0`), non-fields (`ring Z/12`, `ring_roots ... over Z/8`,
  `matrix ... mod 8`), characteristic 2 (`GF(2^8)`, `GF(4)`, `irreducible`/`primitive` over
  `GF(2)`, `groebner ... modulus 2`), huge primes (`phi 1000000007`, `factorint 9999999967`,
  `ec_info secp256k1`), singular elliptic curve rejected (`ec [0,0,0,0,0]`), and ambiguous /
  malformed arguments (ragged SNF/HNF matrices, `abgroup garbage`, `ring garbage`, `sqrtmod` with
  no solution, etc.) — all produced `ok:false` errors rather than bogus `ok:true` answers.
* All committed goldens were run twice and byte-for-byte diffed: **no DETERMINISM issues** found
  (including `ec_order` bsgs/schoof, `factorint` with Pollard-rho, `ec_info` certificates,
  `groebner`, and `magic`).
* No wrong polynomial factorization or failing self-check certificate was found: every `factor`,
  `gcd`, `resultant`, `snf`, `hnf`, `groebner`, `idealmember`, and `ec_*` result carried a `check`
  that passed and matched the mathematical fact.
