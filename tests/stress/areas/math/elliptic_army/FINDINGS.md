# Stress findings — `elliptic_army`

Scope: `src/ec*.c` / `src/ec*.h` (Q-side `ec`, F_p-side `ec*`), with reproducible
CLI cases captured in this folder. Every `.out` was captured from the **fixed**
binary with

```sh
cd tests/stress/areas/math/elliptic_army
env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none ucas NAME.ucas > NAME.out 2>&1
```

and re-run and diffed for determinism. All four goldens exit 0 and contain no
`error:`/`internal:` lines.

## Bugs fixed

| ID | Severity | One-line | Fix |
|----|----------|----------|-----|
| WRONG-1 (brief) | WRONG | Tate's algorithm at p=2,3 threw `internal: X is not divisible by 64/256/729/1024` on ~1% of nonsingular curves | `src/ecq.c`, I_m* loop: remove an extra factor of `p` from the `a6` divisor |
| WRONG-2 (brief) | WRONG | `ec_mul` with equation/coefficient curve + unparenthesised negative scalar read the scalar as a new modulus (`mod 97 -10` → `87`) | `src/ecff_cmd.c`: modulus parser stops at a whitespace-separated sign when a scalar token follows |
| BUG-1 (mined) | WRONG | `ecorder ... using schoof` failed on every valid curve over F_5 and F_7 | `src/eccount.c`: if the CRT modulus already exceeds the Hasse interval, return the single candidate instead of spinning in the BSGS finisher |
| BUG-2 (mined) | WRONG | `ecorder` failed to count valid tiny curves (e.g. `y^2 = x^3 + 1` over F_7, #E = 12) because the random-point certificate could not separate Hasse candidates | `src/ecff_cmd.c`: accept an exact naive/Schoof count with a trivial certificate when the cross-check is inconclusive |

### WRONG-1 — Tate's algorithm internal invariant on nonsingular curves

**Repro:** `ec y^2 = x^3 - 12*x local` gave
`internal: -32 is not divisible by 64` after printing the minimal model and
discriminant. Same class: `-108*x` (`/64`), `-115*x - 14` (`/256`),
`-120*x - 11` (`/729`), `[-266,386,-238,218,111]` (`/256`). An exhaustive scan
of `y^2 = x^3 + A x + B`, `|A|,|B| <= 40`, found 6,556 curves and no remaining
internal error after the fix (`A,B` up to 60, minimal-model-only: 14,587 curves
matched an independent Python port of Tate's algorithm, Kodaira / c_p / f).

**Root cause.** In `ecq_tate()`'s I_m* branch the second quadratic is

```
(a2/p) X^2 + (a4/(p*mx)) X + a6/(p*mx*my) mod p
```

with `mx = my = p^2` initially. The divisor for `a6` carried one extra `p`:
after the first y-translation `my` becomes `p^3`, so `p*mx*my = p^6`, but the
translation only guarantees `p^5 | a6`. The reference algorithm (Sage
`ell_local_data.py`, `_tate`, the `sw == 2` branch) divides by `mx*my`, not
`p*mx*my`. The failed `z_divexact` surfaced as an `internal:` invariant error.

**Fix.** `src/ecq.c` line ~615: `z_divexact(a6, z_mul(p, z_mul(mx, my)))`
→ `z_divexact(a6, z_mul(mx, my))`. One line, no other Tate step changed.

**Verification.** `y^2 = x^3 - 12*x` now prints conductor 288, p=2 `I3*`,
f=5, c_p=4; p=3 `III`, f=2, c_p=2; Tamagawa 8 — exactly LMFDB curve 288.a1.
`01_tate_nonsingular.ucas` / `.out` covers the five original failures plus five
valid control curves (good, multiplicative, II/III/IV and a general Weierstrass
model).

### WRONG-2 — negative scalar absorbed into the modulus

**Repro:** `ecmul y^2 = x^3 + 2x + 3 mod 97 -10 (73, 83)` gave
`87 is not prime`; the same for `over F_97`, `mod GF(97)` and `[2, 3] mod 97`.
Expected `-10 P = O` ((73, 83) has order 10).

**Root cause.** The MCP `ec_mul` frontend concatenates `curve`, `k`, `P` with
spaces. `parse_modulus()` used `getzz()` → `zz_parse()` → `pexpr()`, which
skips whitespace before a `+`/`-` and therefore read `97 -10` as one expression,
`87`. Parenthesising the scalar worked, and named curves were unaffected
(they have no modulus).

**Fix.** `src/ecff_cmd.c`: added `getzz_modulus()`, which for `ecmul` (flag
`scalar_follows`) copies the modulus text up to the first sign preceded by
whitespace, parses that prefix, and leaves the sign for the scalar parser.
Signs inside an expression (`2^255-19`), inside parentheses, and in the
`GF(...)`, `F_{...}` forms are untouched. Both the bare-modulus branch and the
`GF/F` branch of `parse_modulus()` use it. `cmd_ecmul()` sets/clears the flag
around `parse_curve()`.

**Verification.** `02_negative_scalar_fp.ucas` / `.out`: all four failing forms
now give `-10 P = O`; the parenthesised form, a positive scalar, a named curve
with a negative scalar and a spaced modulus expression (`2^61 - 1`) are
controls.

### BUG-1 — Schoof fails on small primes (CRT modulus wider than Hasse interval)

**Repro:** `ecorder [0,0,0,0,1] mod 5 using schoof` gave
`could not count (or certify) the points of y^2 = x^3 + 1 over F_5`; same for
`mod 7` and `y^2 = x^3 + 2x + 1 mod 5`. Naive counting on the same curves
worked and returned 6, 12 and 7.

**Root cause.** `ec_count_schoof()` collects primes until `M > 4 sqrt(p)`; for
p=5 it uses M = 42 and for p=7, M = 30. Both exceed the whole Hasse interval,
so there is exactly one candidate N in `[lo, hi]`. `ec_match_bsgs()` never
checked this: it computed `Q = M P`, which is `O` for **every** P (M is a
multiple of the group order), so `bsgs_all()` was never reached, all 20 random
points were discarded and the function returned 0.

**Fix.** `src/eccount.c`, `ec_match_bsgs()`: after computing
`k1 = (hi - c0) / M`, return `c0` immediately when `k1 == 0`. Also clear
`ecsch_last.bsgs` so the output does not claim a giant-step match that was not
performed.

**Verification.** `03_schoof_small_prime.ucas` / `.out`: the three failing
commands now agree with the naive counts and with `ecpoints`; Schoof on F_11
and F_97 and six naive counts are controls.

### BUG-2 — exact count rejected when the certificate cannot separate candidates

**Repro:** `ecorder [0,0,0,0,1] mod 7` (no method requested; p<=20 selects
naive counting) gave `could not count (or certify) the points ...`. It also
failed with `using naive` and `using schoof`. Independent enumeration gives
#E(F_7) = 12 for `y^2 = x^3 + 1` (LMFDB curve 49.a? order 12, group Z/2 x Z/6).

**Root cause.** `ec_certify()` only knows the *exponent* L of E and L2 of the
twist. Here L = 6, L2 = 2 and the Hasse interval [3, 13] contains two multiples
of 6, 6 and 12, both congruent to 16 mod 2. The twist is Z/2 x Z/2 (exponent
2) so no amount of additional random twist points helps. A scan of small
(p,a,b) found 15 such failures out of 516 valid curves (p=5,7,11,17).

**Fix.** `src/ecff_cmd.c`, `count()`: when `ec_certify()` fails but the count
came from an exact method (`CM_NAIVE` — every x enumerated — or `CM_SCHOOF`
after the CRT/BSGS finish), accept N with a trivial certificate
(`C->L = N`, `C->L2 = 1`, `C->ok = C->complete = 1`) instead of failing. When
certification succeeds the output is unchanged, so existing working goldens
are untouched.

**Verification.** `04_certify_small_group.ucas` / `.out`: six previously
failing curves now report counts matching an independent Python enumeration;
a p=97 order and the full `ec y^2 = x^3 + 1 mod 7` summary are controls.

## Goldens in other areas needing recapture (not edited here)

- `tests/stress/areas/math/elliptic_rank_generators/06_q_tate_internal_errors.out`
  — the five `internal:` errors are now successful local-data output.
- `tests/stress/areas/math/elliptic_rank_generators/mcp_errors.out` — ids 4, 5
  (Tate) and 7 (negative scalar) change from errors to successful results.

`bmake stress-test STRESS_AREA=elliptic_rank_generators` fails only on those two
goldens, as expected. All other goldens in that area still pass, including the
cosmetic LIMIT-3 case (`ec_mul` echoing the negated `P:`), which was left
unchanged deliberately.

## Notes on mining coverage

Beyond the four findings: ~7,000 random Q/F_p curve commands (Tate, order,
group law, heights, models, dlog, pairing, ECM, binary curves, CM, isogenies),
14,587 minimal-model local-data cross-checks against an independent Python
port of Sage's Tate algorithm, and hundreds of point-count cross-checks against
brute-force enumeration found no other reproducible wrong answer or crash.
