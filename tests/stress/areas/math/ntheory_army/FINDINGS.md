# Stress findings — `ntheory_army`

Area: number theory and integer factorization, focused on the flags raised in
`math/number_theory_core/FINDINGS.md` and `math/integer_factorization/FINDINGS.md`
plus bugs mined while re-running those repros. All goldens were captured from the
fixed binary with the standard stress environment
(`UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`) and every CLI run was bounded with
`timeout 15`.

## Scope of source changes

Only `src/zint.c` was modified by this wave (plus this new test area). The prior
wave's bigint print cap (`Z_PRINT_MAX_DIGITS` in `z_print`) is preserved unchanged.
`src/ntheory.c` was audited by differential testing but needed no change.

## Fixed flags

### FIX-1 — `integer_factorization` HANG-1: large prime squares / hard cofactors hang
**Was:** `bigint factor 5316911983139663487003542222693990401` (`(2^61-1)^2`)
spun in Pollard-Brent rho for ~25 s on the stress host (15 s timeout), as did
`(2^64-59)^2`, `2^256-1` and `2^400+1`.

**Fix (`src/zint.c`):** `z_factor` now runs an integer-square test
(`z_isqrt`, integer Newton iteration) before rho on every bigint cofactor, so a
perfect square of a large prime is split in one comparison. A 5 s CPU deadline
is also imposed on the rho loop (sampled every 4096 iterations); a cofactor
whose smallest factor is out of reach now degrades to the existing honest
`not fully factored` / `not complete: a composite factor above 2^64 was not
split` output instead of running until the caller's wall-clock timeout.

**After:** the two square repros factor completely in <0.02 s; the non-square
repros return the honest partial factorization in ≤6 s here. Golden:
`01_fixed_factorization.out`, `02_budget_honesty.out`.

### FIX-2 — `integer_factorization` WRONG-1: composite listed under `factors[].prime`
**Was:** the MCP `abstract_algebra.bigint_factor` response for the same square
repro returned `ok:true` / `isError:false` with
`factors:[{"prime":"53169…0401","exponent":1}]` — a composite labelled `prime`,
with the only caveat in the headline and a `not_complete` string.

**After:** the repro now factors completely, so the structured `factors` entry
is `{"prime":"2305843009213693951","exponent":2}` (a genuine prime) and the
primality check is restored. Golden: `01_fixed_factorization.out` plus the
MCP-square response recorded in `mcp_bigint_factor` (existing area, unchanged).

**Residual structural issue (out of my ownership):** for inputs that still
cannot be fully split (e.g. `2^256-1`), the unsplit composite is still stored
in `p[]` by `z_factor` and printed under the field name `prime` by
`absalg_cmd.c:434`. The API has no separate `residual` field and I do not own
that file; a complete fix needs `absalg_cmd.c` to emit unfactored cofactors
under a distinct key and/or clear `ok`. `02_budget_honesty.out` captures the
current honest-text-but-`prime`-field behaviour so the fix can be verified.

### FIX-3 — `number_theory_core` WRONG-1: "zerodivisors mod 12" → sedenions (NOT fixed here)
**Status:** reproduced and recorded, but the bug is an English-front-end
misroute, not a number-theory routine. `nlp.c:sentence()` calls
`hy_sentence()` (`src/nlp_hyper.inc:211-215`) before the rings NLP; the
one-word `zerodivisors` is treated as a hyper-command and defaults the algebra
to `sedenion`. The correct CLI path `ring Z/12 zerodivisors` works.
Fixing it requires editing `src/nlp_hyper.inc` / `src/ring_nlp.c`, which are
outside this wave's source ownership; precise patch location is reported to
the parent. Golden `mcp_english_zerodivisors.out` captures the buggy answer so
it can be recaptured once the NLP-side fix lands.

## Mined bugs (new)

### BUG-A — nonsense diagnostic `0 is too large` for integer literals ≥ 2^128
**Severity:** WRONG (diagnostic)
**Repro:** `factorint 340282366920938463463374607431768211456` (and `phi`,
`carmichael`). `ring.c:iexpr_atom()` rejects a literal with bit 128 set but
formats the message with `u128s(rt[rti].v)` — the value truncated to 128 bits —
so the error names `0` instead of the huge literal. In range (`2^64`) the
proper `factorint n for 1 <= n < 2^64` message is produced; `jacobi` with the
same 2^128-minus-one value correctly prints the value.
**Golden:** `03_bug_overflow_diagnostic.out`.
**Fix owner:** `src/ring.c` (not owned by this wave). Note: `0 is too large`
also appears in existing goldens in `nlp_numbers`, `numeric_arg_overflow` and
`type_coercion`; changing the message requires recapturing those.

### BUG-B — MCP `crt` structured `x` field contains the input congruences, not the solution
**Severity:** WRONG (structured output)
**Repro:** MCP `rings.crt` with `{"congruences":["2 mod 4","4 mod 6"]}` returns
`solutions:["10"], modulus:"12"` (correct) but
`x:["2 (mod 4)","4 (mod 6)"]` — the inputs, not the solution. The single-
congruence form returns `x:"2 mod 3: x = 2"` while the solution sits in
`value:"2"`. A consumer reading `x` gets the question instead of the answer.
This is the generic headline splitter in `mcp.c`, not a math error.
**Golden:** `mcp_crt_fields.out`. **Fix owner:** `src/mcp.c` (not owned here).

### BUG-C — MCP `sqrtmod` `modulus` field absorbs the "no solution" suffix
**Severity:** WRONG (structured output)
**Repro:** MCP `rings.sqrtmod` with `{"a":2,"modulus":4}` returns
`modulus:"4: no solution"` plus `value:"2", value_int:2`; the structured
`modulus` is not the modulus. This is a second trigger of the class already
recorded as `number_theory_core` LIMIT-3 (there, the >256-solutions sentence
is absorbed), but on the common `no solution` path. Normal results
(`sqrtmod 2 7`, `sqrtmod 0 8`) have a clean `modulus` field.
**Golden:** `mcp_sqrtmod_fields.out`. **Fix owner:** `src/mcp.c` (not owned here).

## Controls that passed

`00_controls.ucas` records correct, unchanged behaviour for phi, Carmichael,
Legendre/Jacobi, modular square roots, inverse, order, CRT, `ring Z/12
zerodivisors` and `factorint`, so a regression in the number-theoretic core is
distinguishable from the intentional factorization-output changes above.

Independent differential checks (not goldens, run during mining against Python
`sympy` 1.14): 556 `phi`/`carmichael` cases, 413 `legendre`/`jacobi`/`inverse`/
`order` cases, 736 small and 400 large `sqrtmod` cases (root substitution and
brute-force root sets), and 400 bigint arithmetic cases — all matched the
oracle. `src/ntheory.c` required no change.
