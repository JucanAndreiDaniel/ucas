# Stress findings — `number_theory_core`

_Original heading: FINDINGS — `number_theory_core`_

# FINDINGS — `number_theory_core`

Scope: elementary number theory through MCP `rings` and the CLI, cross-checked against
sympy 1.14 and brute force. All runs bounded with `timeout 15` (harness batches with larger
bounds only for multi-thousand-call sweeps). The mathematical core is solid: 6256 exhaustive
sqrt/Legendre/QR cases, 1582 general ops, 496 ring/primality cases, 228 magic-number cases
(709 evaluator substitutions), and 175 large-u64 cases all agreed with sympy. Everything below
is an **English-front-end (NLP) misroute/misparse** or a **structured-output LIMIT**; no wrong
verdicts, crashes, hangs, or nondeterminism were found in the rings number-theory commands.

Repro helper (copy-paste) for the MCP `english` findings:

```sh
cd $ROOT
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"english","arguments":{"text":"REPLACE_ME"}}}' \
 | timeout 15 ./ucas --mcp
```

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | `WRONG`/`NLP` — “zerodivisors mod 12” returns a sentence about sedenions |
| NLP | 6 | `NLP` — “cube roots mod 7” is routed to complex `nthroots`, then fails its own checks |
| LIMIT | 3 | `LIMIT` — no Möbius / divisor-sum support; English words unknown |

## Findings

### WRONG-1 — `WRONG`/`NLP` — “zerodivisors mod 12” returns a sentence about sedenions
**Severity:** WRONG
_Original classification: `WRONG/NLP`._
**Why it matters:** _not recorded_
**Reproducer:**
Repro: run the helper above with `text` = `zerodivisors mod 12`.

**Observed:** (`ok: true`):

```
zero divisors in the sedenions:
  (e1 - e10)(e4 + e15) = 0, although |e1 - e10| = |e4 + e15| = sqrt(2)
  so |ab| = |a||b| fails and the sedenions are not a division algebra (from dimension 16 on, every Cayley-Dickson algebra has them)
```

**Expected:** the zero divisors of Z/12 (nonzero non-units) `2, 3, 4, 6, 8, 9, 10` — the CLI
`ring Z/12 zerodivisors` prints exactly that. The English front-end silently answers a
completely different domain question. Compare `ring Z/12 zerodivisors` (correct) with the
English phrase (wrong).

### NLP-1 — `NLP` — “cube roots mod 7” is routed to complex `nthroots`, then fails its own checks
**Severity:** NLP
**Why it matters:** _not recorded_
**Reproducer:**
Repro: helper with `text` = `cube roots mod 7`.

**Observed:** (`ok: true`):

```
  ucas: nthroots 3 mod 7
  note: mod is taken as real
the 3 cube roots of mod 7: w^3 = z
  w_k = r^(1/3) e^(i (theta + 2 pi k)/3),  k = 0..2
  r = |z| = 7abs(mod),  theta = arg z = atan2(0, 7mod)
<english>:1:39: error: unexpected ')'
    ((7abs(mod))^(1/3)*e^(i*(atan2(0, 7mod) + 2pi*0)/3))^3
                                          ^
  k = 0: check: the result does not parse
...
```

**Expected:** modular cube roots of x³ ≡ a (mod 7), or a clear “not supported” message. Here
`mod` is read as a real variable and the generated “checks” do not even parse, yet the response
is returned as `ok: true`.

### NLP-2 — `NLP` — “solve the congruence 3x = 1 mod 11” duplicates the keyword and fails to parse
**Severity:** NLP
**Why it matters:** _not recorded_
**Reproducer:**
Repro: helper with `text` = `solve the congruence 3x = 1 mod 11`.

**Observed:**

```
  ucas: congruence congruence 3x = 1 mod 11
<english>:1:12: error: expected a polynomial in x, found congruence
    congruence congruence 3x = 1 mod 11
               ^
error code: parse_error
```

**Expected:** translate to `congruence 3*x = 1 mod 11` (or `solve 3x = 1 mod 11`) → `x = 4 (mod 11)`.
The word “congruence” is emitted twice.

### NLP-3 — `NLP` — “x squared = 2 mod 7” drops the variable `x`
**Severity:** NLP
**Why it matters:** _not recorded_
**Reproducer:**
Repro: helper with `text` = `x squared = 2 mod 7`.

**Observed:**

```
  ucas: congruence squared = 2 mod 7
<english>:1:12: error: expected a polynomial in x, found squared
    congruence squared = 2 mod 7
               ^
```

**Expected:** `congruence x^2 = 2 mod 7` → `x = 3, 4 (mod 7)`. A phrasing that works is
`find x such that x^2 = 1 mod 8` (translates correctly), so the `x squared` form is a
specific misparse.

### NLP-4 — `NLP` — “factor 561” is a silent no-op instead of integer factorization
**Severity:** NLP
**Why it matters:** _not recorded_
**Reproducer:**
Repro: `printf 'factor 561\n' | timeout 15 ./ucas`

**Observed:**

```
factor 561
  = 561
  check: exact (both sides have the same normal form)
```

**Expected:** `factorint 561` → `561 = 3 * 11 * 17 (not prime)`. With a bare integer argument,
`factor` should route to integer factorization (it already does for the synonym
`factorize 561`). The returned “check” is vacuously true, so the failure is silent.

### NLP-5 — `NLP` — “quadratic residues mod 7” becomes a product of two variables
**Severity:** NLP
**Why it matters:** _not recorded_
**Reproducer:**
Repro: helper with `text` = `quadratic residues mod 7`.

**Observed:** (`ok: true`):

```
_(quadratic: int, residues: int) = quadratic*residues % 7
  -> int
```

**Expected:** `qr 7` → “the squares mod 7: 4 of 7 residues: 0, 1, 2, 4”. Adding the article
makes it work — `the quadratic residues mod 7` correctly translates to `qr 7` — so the
two-word form is an inconsistent misparse.

### LIMIT-1 — `LIMIT` — no Möbius / divisor-sum support; English words unknown
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The focus area asks for Möbius and divisor sums, but `rings` exposes none, and the English
front-end does not know the words:

- `mobius of 12` → `not_understood: I don't know the word "mobius"`.
- `divisors of 12` → `I don't know the word "divisors"`.
- `sum of divisors of 12` → `I don't know the word "divisors"` (text also says `"+" needs two or more things`).
- `how many divisors does 12 have` → `I don't know how to answer that "how" question`.
- CLI bare `sigma 12`, `tau 12`, `divisors 12` become junk functions, e.g. `_(sigma: real) = 12sigma`.

`bigint isprime(...)` (24 bases) and `factorint` (12 bases) are available and agree on every
sampled u64. `phi`/`carmichael` cover totient/Carmichael only.

### NLP-6 — `NLP` — functional notation for symbols is rejected
**Severity:** NLP
**Why it matters:** _not recorded_
**Reproducer:**
Repro: helper with `text` = `jacobi(2, 15)` (or `legendre(2, 7)`).

**Observed:**

```
<english>:1:7: error: expected ')', found ,
    jacobi(2, 15)
          ^
```

**Expected:** accept function-call syntax, or translate to `jacobi 2 15` → `(2/15) = 1`.
The spaced form `jacobi symbol 2 over 15` does work.

### LIMIT-2 — `LIMIT` — structured `value_int` omitted for results above 2^53
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
For `inverse_mod`/`phi` with large n (e.g. `phi 18446744073709551615`), the MCP structured
`result` carries only the exact decimal string `value: "9208981628670443520"` and **no**
`value_int`; for small results both fields are present. Consumers that read `value_int`
silently get `undefined` for large values. Repro: MCP call `{"op":"phi","args":{"n":18446744073709551615}}`.

### LIMIT-3 — `LIMIT` — malformed structured fields when `sqrtmod` exceeds the root cap
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
MCP `{"op":"sqrtmod","args":{"a":1,"modulus":6469693230}}` returns `ok: true` with text
`x^2 = 1 mod 6469693230 has more than 256 solutions`, but the generic headline splitter
produces a polluted structured result:

**Observed:**
**Reproducer:**
```json
"result": {"kind":"sqrtmod","lhs":"x^2","modulus":"6469693230 has more than 256 solutions","value":"1","value_int":1,...}
```

The `modulus` field absorbs the error sentence and bogus `value`/`value_int` fields appear.
Compare a normal result (e.g. `sqrtmod 2 mod 7`) where `modulus` is `"7"` and `roots` is a list.

---

#### Non-findings (verified correct, recorded for completeness)

- Primality claim “Miller-Rabin with first 12 prime bases, deterministic below 2^64” is
  **correct**: ψ₁₂ = 318665857834031151167461 > 2⁶⁴ (OEIS A014233). The strong pseudoprimes
  2047, 1373653, …, 3825123056546413051 are all correctly reported composite.
- CRT overflow, >256 square roots, `phi 0`, even-Jacobi, and `magic 0` all produce clean,
  deterministic errors rather than crashes/hangs.
- All returned certificates that were checkable by substitution (extended-Euclid inverse
  coefficients, `a^order ≡ 1`, factorization products and primality of factors, CRT/sqrt
  solutions, emitted magic-number formulas) verified.
- No nondeterminism: every golden file was run twice and the two outputs were byte-identical.

## Checks that passed

_No separate passed checks were recorded in the original document._
