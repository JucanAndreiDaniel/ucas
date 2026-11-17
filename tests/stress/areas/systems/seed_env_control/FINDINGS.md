# Stress findings — `seed_env_control`

_Original heading: FINDINGS — `seed_env_control`_

# FINDINGS — `seed_env_control`

Area: seed handling and reproducibility of the stochastic verifiers
(`pit`, `stoke`, `find`, `approx`, `numsearch`/`qmc`) across CLI, JSON and MCP.

All commands below were run with
`timeout 15` (longer only where noted) against
`$ROOT/ucas`.  The full 231-case matrix is in `harness.py` /
`results.json`; fixed-seed deterministic cases are pinned as goldens; the
environment matrix is pinned by `run_seed_matrix.sh`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | `pit` returns a false `equal` verdict for polynomials that differ by a multiple of 2^61−1 |
| LIMIT | 1 | explicit negative `seed K` is rejected at parse time (idea #6 does not reach `rseed`) |

## Findings

### WRONG-1 — `pit` returns a false `equal` verdict for polynomials that differ by a multiple of 2^61−1
**Severity:** WRONG
_Original classification: `WRONG (unsound verdict, seed-independent`._
**Expected:** _not recorded_
Exact reproducer:

**Observed:**
**Reproducer:**
```sh
cd $ROOT
./ucas -e $'f(x:i64)=x\ng(x:i64)=x+2305843009213693951\npit f g trials 8'
```

Exact observed output:

```
pit f g: polynomial identity testing (Schwartz-Zippel), seed 1
  f has total degree at most 1, g at most 1
  polynomials of total degree at most 1, equal at 8 random points mod 2^61 - 1: two that differ agree at one with probability at most 1/(2^61 - 1) = 4.34e-19 (Schwartz-Zippel), at all 8 with at most 1.25e-147
  -> equal as polynomials over the integers, except with probability at most 1.25e-147 (not a proof: a probabilistic answer)
     in i64 they are then equal for every input: reduction mod 2^64 is a ring homomorphism
```

The same two functions are correctly reported as different by the exhaustive
checker:

```sh
./ucas -e $'f(x:i64)=x\ng(x:i64)=x+2305843009213693951\nequiv f g'
# f and g differ at 65536 points of the sample, e.g. x=-9223372036854775808:
#   -9223372036854775808 vs -6917529027641081857
```

**Why it matters:** this is a bug.** `pit_check` (src/stoch.c:317-365) evaluates both
polynomials modulo PIT_P = 2^61−1 and concludes "equal as polynomials over the
integers" when the sampled values agree.  A difference polynomial whose
coefficients are all divisible by P vanishes modulo P at *every* point, so the
Schwartz–Zippel bound (which assumes a nonzero polynomial of degree d over a
field has ≤ d roots) does not apply.  Here `g − f = P` exactly, so `pit` returns
a false `equal` with a bogus `1.25e-147` error bound and the flatly wrong claim
"in i64 they are then equal for every input".  The result is the same for seeds
0/1/2 and for all 5 members of the family (constant, linear, quadratic, cubic,
two-variable) pinned in `03_pit_p_multiple_false_equal.ucas`.

### WRONG-2 — `UCAS_SEED` is parsed by unchecked `strtoull` with silent coercion
**Severity:** WRONG
**Expected:** _not recorded_
result) + LIMIT (no validation).**

Reproducers (all deterministic; see `run_seed_matrix.sh`, 33 checks):

**Observed:**
**Reproducer:**
```sh
cd $ROOT
UCAS_SEED=abc    ./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4'   # seed 0
UCAS_SEED=-1     ./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4'   # seed 18446744073709551615
UCAS_SEED=18446744073709551616  ./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4'  # saturates to ULLONG_MAX
UCAS_SEED=12junk ./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4'   # seed 12 (junk ignored)
UCAS_SEED=' 5x'  ./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4'   # seed 5 (whitespace/'+' accepted)
UCAS_SEED=''     ./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4'   # seed 1 (default)
UCAS_SEED='   '  ./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4'   # seed 0 (skipped ws, no digits)
```

Exact observed first lines (from `results.json`, group `A_env_seed`):

```
UCAS_SEED='abc'                       -> pit ... seed 0
UCAS_SEED='-1'                        -> pit ... seed 18446744073709551615
UCAS_SEED='-00000000000000000001'     -> pit ... seed 18446744073709551615
UCAS_SEED='-9223372036854775809'      -> pit ... seed 9223372036854775807
UCAS_SEED='18446744073709551616'      -> pit ... seed 18446744073709551615
UCAS_SEED='9999999999999999999999999' -> pit ... seed 18446744073709551615
UCAS_SEED='12junk'                    -> pit ... seed 12
UCAS_SEED=' 5x'                       -> pit ... seed 5
UCAS_SEED='+7abc'                     -> pit ... seed 7
UCAS_SEED=''                          -> pit ... seed 1
UCAS_SEED='   '                       -> pit ... seed 0
```

**Why it matters:** this is a bug.** `stoch_seed()` at src/stoch.c:117-125 does
`strtoull(e, NULL, 10)` with no end-pointer, sign or `errno` check.  A typo in
an environment variable (`UCAS_SEED=abx`) silently selects seed 0 instead of
the documented default 1; a negative number selects `ULLONG_MAX`; a value one
past `ULLONG_MAX` saturates; trailing junk is silently accepted.  Because the
seed controls all stochastic verifiers, the ambient environment can change a
probabilistic verdict without any diagnostic.  (Ideas #2 / #29 from
`IDEAS_SOURCE.md`.)

### LIMIT-1 — explicit negative `seed K` is rejected at parse time (idea #6 does not reach `rseed`)
**Severity:** LIMIT
_Original classification: `LIMIT (documented expectation from source audit does not hold`._
**Expected:** _not recorded_
Exact reproducer:

**Observed:**
**Reproducer:**
```sh
cd $ROOT
printf 'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 8 seed -1\n' | ./ucas
```

Exact observed output:

```
<stdin>:3:23: error: pit: seed K
    pit f g trials 8 seed -1
                          ^
```

Same for `stoke ... seed -1` (`stoke: seed K`) and `qmc ... seed -1`
(`qmc: seed K`).  CLI, JSON and MCP all reject a negative explicit seed.

**Why it matters:** this is a finding.** Idea #6 predicted that a negative explicit seed
would reach `rseed()` unchecked (as `UCAS_SEED=-1` does).  In fact `cmdp_int`
requires a `T_NUM` token and `-1` is a unary-minus expression, so the parser
rejects it before `stoch_command` can cast it to `uint64_t`.  The env path and
the explicit path therefore have different accepted domains (see F5).

### WRONG-3 — WRONG / DIVERGENCE: CLI accepts full 64-bit seeds; JSON and MCP silently cap them at 1e15
**Severity:** WRONG
**Expected:** _not recorded_
Reproducers:

**Observed:**
**Reproducer:**
```sh
cd $ROOT
# CLI: accepted, seed echoed verbatim
./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 2 seed 18446744073709551615' | head -1
printf '%s\n' '{"id":1,"cmd":"pit","args":{"f":"x^2","g":"x*x","trials":2,"seed":18446744073709551615}}' \
  | ./ucas --json --files none
```

Exact observed output:

```
# CLI
pit f g: polynomial identity testing (Schwartz-Zippel), seed 18446744073709551615
# --json
{"id": 1, "ok": false, "cmd": "pit", "error": {"code": "bad_request", "message": "seed: an integer"}}
```

The same JSON rejection happens for `seed: 9223372036854775807` (INT64_MAX),
`seed: 1000000000000001` (1e15+1), `seed: 1.5`, `seed: true`, `seed: null`,
`seed: "5"`, and for the MCP tool `analyze` with the same `args.seed`.
`seed: 1e3` is accepted and rendered as `1000`.

**Why it matters:** this is a bug.** `P_INT` arguments in src/jsonmode.c:1572-1577 require a
`J_NUM` with `fabs(v->num) <= 1e15`, whereas the CLI's `cmdp_int` accepts the
whole `int64_t` bit pattern and reinterprets it as `uint64_t`.  The same
logical request is therefore valid on the CLI and a `bad_request` on JSON/MCP,
with no documentation of the lower cap.  Pinned in `json_seed_args` and
`mcp_seed_args` goldens.

### WRONG-4 — WRONG / DIVERGENCE: `approx` uses a different seed parser than `pit`/`stoke`/`qmc`
**Severity:** WRONG
**Expected:** _not recorded_
Reproducers:

**Observed:**
**Reproducer:**
```sh
cd $ROOT
# pit accepts the full uint64 value:
./ucas -e $'f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 2 seed 18446744073709551615' | head -1
# approx rejects the same value:
./ucas -e 'approx sin(x) in 0..0.7853981 degree 3 as f32 list 1 search anneal seed 18446744073709551615 budget 50'
```

Exact observed output:

```
pit f g: polynomial identity testing (Schwartz-Zippel), seed 18446744073709551615
<arg>:1:94: error: seed: a whole number, not -1
    approx sin(x) in 0..0.7853981 degree 3 as f32 list 1 search anneal seed 18446744073709551615 budget 50
                                                                                                 ^
```

`approx ... seed 9223372036854775807` is rejected as
`seed: a whole number, not 9.22337e+18`; `approx ... seed -1` as `not -1`.
`stoke ... seed 18446744073709551615` and
`integrate ... qmc ... seed 18446744073709551615` are both accepted.

**Why it matters:** this is a bug.** `approx` parses `seed` with `cmdp_number` into a
`double` and bounds it to `[0, 9e15]` (src/approx.c:3784-3788); `pit`/`stoke`
use `cmdp_int` (src/stoch.c:3102-3105, 3121-3124) and `qmc` uses `cmdp_int`
(src/qmc.c:149-151).  There is no single documented seed domain: the same
numeric token is accepted by one stochastic command and rejected by another.
Note also the misleading diagnostic `not -1` — the overflowing decimal is
parsed through a signed 64-bit constant that wraps to −1 before the check.

## Checks that passed

### Clean checks (no issue found — recorded so they are not re-run)
* **No crashes and no hangs.** All 231 matrix runs exited 0 or were the
  expected parse/validation errors; no signal, no `rc=124`.  Huge and negative
  seeds did not crash `pit`, `stoke`, `approx` or `qmc`.
* **Fixed-seed determinism holds.** For each of
  `pit` (equal and different), `stoke`, `approx search anneal` and
  `integrate ... qmc`, three runs with an identical seed were byte-identical
  (group `I_repeat`; also `find ... stoke` checked manually with `UCAS_SEED=5`).
  The idea-#9 clock-deadline paths (`snippets grow`, `rules infer`,
  `find_cands`) are not exposed as a `seed`-bearing stochastic command on this
  CLI path, so no fixed-seed nondeterminism was observed in this area.
* **Verdicts do not flip with seeds 0/1/2** on genuinely equal (6 pairs) or
  genuinely different (6 pairs) polynomials — all gave the correct verdict for
  every seed (group `H_verdict`).  The only verdict anomaly is F1, which is
  seed-independent.
* **Explicit `seed K` overrides `UCAS_SEED`** in CLI, JSON and MCP (verified in
  `run_seed_matrix.sh` and harness group `B`/`F`/`G`).
