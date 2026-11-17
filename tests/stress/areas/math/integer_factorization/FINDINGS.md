# Stress findings — `integer_factorization`

_Original heading: Findings — `integer_factorization`_

# Findings — `integer_factorization`

All runs bounded with `timeout 15` unless stated otherwise (one deliberately long run uses 30 s).
Independent oracle: Python `sympy.factorint` / `sympy.isprime`.  All factorization requests used
`abstract_algebra.bigint_factor` (MCP), `rings.factorint` (MCP), CLI `bigint factor` and CLI `factorint`.

378 distinct queries were exercised (371 generated cases in the harness + 7 extra probes).
334 non-error results were verified by multiplying factors in Python and independently testing each
factor for primality; 115 CLI result headlines were likewise re-multiplied.  No wrong product, no
composite factor, and no missing factor was found among results that completed normally.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | factorization of a large prime square / large semiprime exceeds 15 s |
| WRONG | 1 | MCP returns `ok:true` with a composite listed under `factors[].prime` after its internal b… |
| LIMIT | 1 | sign is omitted from structured `factors` for negative integers |

## Findings

### HANG-1 — factorization of a large prime square / large semiprime exceeds 15 s
**Severity:** HANG
**Reproducer:**
Reproducer (CLI):
```sh
cd $ROOT
printf 'bigint factor 5316911983139663487003542222693990401\n' > /tmp/hang.ucas
timeout 15 ./ucas /tmp/hang.ucas; echo "RC=$?"
```

**Observed:** output:
```
> bigint factor 5316911983139663487003542222693990401
RC=124
```

**Reproducer:**
Reproducer (MCP):
```sh
cd $ROOT
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"abstract_algebra","arguments":{"op":"bigint_factor","args":{"n":"5316911983139663487003542222693990401"}}}}' \
 | timeout 15 ./ucas --mcp > /tmp/hang.out 2>&1; echo "RC=$?"
```
Only the `id:0` `initialize` line is emitted; the `id:1` response never arrives. `RC=124`.

**Other inputs with the same behaviour** (each individually isolated, `timeout 15`):
| input | value |
|---|---|
| `(2^61-1)^2` | `5316911983139663487003542222693990401` |
| `(2^64-59)^2` | `340282366920938461286658806734041124249` |
| `2^256-1` | `115792089237316195423570985008687907853269984665640564039457584007913129639935` |
| `2^400+1` (expression form) | — |

**Why it matters:** it is a bug / expected:** the claimed method is "trial division, then Pollard-Brent rho".
Pollard-Brent needs ~sqrt(p) iterations for a prime factor p, so a 61–64 bit squared prime
(or the 72-bit largest factor of `2^256-1`) is out of reach.  A perfect-square test (integer sqrt,
one comparison) would resolve the two square cases instantly, and a larger smooth/P-1 stage would
resolve `2^256-1`.
**Expected:** finish in well under 15 s or return a clean timeout error — not hang.

Note: supplying an explicit `timeout_s` (e.g. `{"n":"...","timeout_s":2}`) *does* return a clean
`error (timeout): timed out after 2 s; the state is unchanged`.  The problem is the default path.

### WRONG-1 — MCP returns `ok:true` with a composite listed under `factors[].prime` after its internal budget
**Severity:** WRONG
_Original classification: `WRONG (unsound structured output / silent truncation`._
**Reproducer:**
Reproducer (deliberately 30 s, MCP):
```sh
cd $ROOT
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"abstract_algebra","arguments":{"op":"bigint_factor","args":{"n":"5316911983139663487003542222693990401"}}}}' \
 | timeout 30 ./ucas --mcp 2>/dev/null
```
(Response arrives after ~24.6 s.)

**Observed:** output (structuredContent, abbreviated):
```json
{
  "id": 1, "ok": true,
  "result": {
    "kind": "bigint",
    "value": "5316911983139663487003542222693990401",
    "factors": [ {"prime": "5316911983139663487003542222693990401", "exponent": 1} ],
    "method": "trial division, then Pollard-Brent rho; primality by Miller-Rabin (deterministic below 2^64, probable above)",
    "not_complete": "a composite factor above 2^64 was not split",
    "headline": "5316911983139663487003542222693990401 = 5316911983139663487003542222693990401 (not fully factored)"
  },
  "checks": [ {"kind":"check", "passed": true, "text": "the product is the number"} ],
  "isError": false
}
```

**Why it matters:** it is a bug / expected:** `factors[0].prime` is **not prime** — it is
`2305843009213693951^2` (confirmed composite by sympy).  Yet the field is named `prime`, the
request is reported `ok: true` / `isError: false`, and the headline is the only place the
`(not fully factored)` caveat appears.  The usual `each factor passes the primality test` check is
silently dropped.  Any caller consuming `structuredContent.factors` will treat a composite as a
prime and report a complete factorization.
**Expected:** put the unsplit composite in a distinct
field (e.g. `unfactored`/`residual`) and/or set `ok:false`, so structured consumers cannot mistake
it for a prime.  The CLI path does not get this graceful degradation: the same input still has no
output at `timeout 35`.

### LIMIT-1 — sign is omitted from structured `factors` for negative integers
**Severity:** LIMIT
**Reproducer:**
```sh
cd $ROOT
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"abstract_algebra","arguments":{"op":"bigint_factor","args":{"n":"-10403"}}}}' \
 | timeout 15 ./ucas --mcp 2>/dev/null
```

**Observed:** output (`structuredContent.result`):
```json
{"kind":"bigint","value":"-10403",
 "factors":[{"prime":"101","exponent":1},{"prime":"103","exponent":1}],
 "headline":"-10403 = -101 * 103"}
```
with `checks: [{"passed": true, "text": "the product is the number; each factor passes the primality test"}]`.

**Why it matters:** it is a bug / expected:** multiplying the returned factors gives `+10403`, not the requested
`value = -10403`.  The minus sign exists only in the human-readable `headline` (and the tool's
internal check evidently accounts for it).  A structured consumer has no way to reconstruct the
original negative integer from `factors` alone.
**Expected:** a `sign: -1` field, or a leading
`{"prime":"-1","exponent":1}` entry.  Same for `-1`, whose `factors` is the empty list.

## Checks that passed

### Non-findings / verified-correct behaviour (recorded to prevent false alarms)
- Strong pseudoprimes to the first 9–13 prime bases (`3215031751`, `341550071728321`,
  `3825123056546413051`, `318665857834031151167461`, `3317044064679887385961981`, …) are all
  correctly split; `isprime()` also returns 0 for them.  See `14_pseudoprimes.ucas`.
- Semiprimes with factors up to ~2^40 (`1099511627791 * 1099511637823`) factor correctly and
  quickly.  See `13_large_semiprimes.ucas`.
- Carmichael numbers, highly composite numbers, Fibonacci/Lucas numbers, factorials, binomials,
  prime powers, numbers near 2^63/2^64, and large primes (2^89-1, 2^107-1, 2^127-1, 2^521-1)
  all factor correctly.
- `0` returns a stable error (`0 has no factorization`); `1` and `-1` return empty factor lists.
- Malformed arguments (`3.5`, `1/2`, `2^-1`, `abc`, `NaN`, `2^^3`, wrong JSON types, missing `n`,
  …) all return stable `ok:false` / `isError:true` errors.  See `12_malformed.ucas`, `mcp_errors.jsonl`,
  `mcp_argtypes.jsonl`.
- `0x10`, `5%2`, `gcd(6,4)`, `1_000`, `007` are valid ucas expressions (16, 1, 2, 1000, 7) and are
  factorized correctly — they are **not** parse bugs.
- `bigint 2^2000` returns the full 2001-bit value: no output truncation in the `bigint` op.
- All golden `.out` files were regenerated twice and `diff`-clean (deterministic).
