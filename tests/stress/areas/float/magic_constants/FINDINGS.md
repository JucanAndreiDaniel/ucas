# Stress findings — `magic_constants`

_Original heading: FINDINGS — magic_constants_

# FINDINGS — magic_constants

Binary: `$ROOT/ucas`. All repros run from this directory.
Independent oracles: `python3 verify_fit_error.py`, `python3 verify_magic.py`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | `fit` returns a non-optimal inverse-sqrt magic constant |
| LIMIT | 3 | bit hacks fail at special values (verified, not a ucas bug) |

## Findings

### WRONG-1 — `fit` returns a non-optimal inverse-sqrt magic constant
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/float/magic_constants
printf 'g(x: f32, K: u32) = asfloat(K - (asuint(x) >> 1))\nfit g ~ 1/sqrt(x)\n' | \
  timeout 15 $ROOT/ucas
```

**Observed:**

```
fit g to 1/sqrt(x) (max relative error, 257 sample points):
  K = 1597464627  (0x5f376033)
  objective 0.0341151
```

**Independent exact check** (`python3 verify_fit_error.py`, float64 oracle over all
2^23 mantissas for both exponent parities, dense search over ±1024 of fit's answer):

```
true minimax K=0x5f37642f  maxrel=0.034212838
fit's K        =0x5f376033  maxrel=0.034275781
fit is optimal? False
```

The classic Lomont constant `0x5f37642f` (inside the ±1024 window) has a strictly
smaller true max relative error. Under ucas's *own* `error` metric the ordering is
reversed (`0x5f376033`: 0.0341951, `0x5f37642f`: 0.0342123) — see finding 2.

**Why it matters:** it is a bug / what was expected** — `fit`'s stated goal is to choose the
constant minimising max relative error. It minimises a 257-point *sample* instead,
and the sample's minimiser is not the domain's minimiser. A ±1024 exhaustive search
finds a better constant. (The output does say "257 sample points", so this is a
sampling limitation with a real accuracy consequence, not a pure crash.)

### WRONG-2 — `error`'s max-relative-error claim is not a bound, and disagrees with `fit`
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/float/magic_constants
cat <<'EOF' | timeout 15 $ROOT/ucas
e(x: f32) = asfloat(0x5f376033 - (asuint(x) >> 1))
error e ~ 1/sqrt(x)
EOF
```

**Observed:** (same K as finding 1)

```
error of e against 1/sqrt(x):
  max abs error 0.170493 at x=0.04
  max rel error 0.0341951 (3.42%) at x=3.74
  mean rel error 0.0237068 over 500 points
```

Three different "max relative errors" for the *same* constant:

| source | value |
|---|---|
| `fit` objective (257 points) | 0.0341151 |
| `error` max rel (500 points) | 0.0341951 |
| exact, all normal f32 mantissas | 0.034275781 |
| exact, full f32 domain incl. subnormals | 0.9995054 |

**Why it matters:** it is a bug / what was expected** — the reported 3.42% understates the true
worst case even on normals (3.4276%), and is off by ~29x on the full domain:
every subnormal `x` (e.g. `x = 1.40129846e-45`, bits `0x00000001`) gives the guess
`1.321e19` against the true `2.671e22` — **99.95% relative error**. Random sampling
of 500 f32 bit patterns never lands on the very smallest subnormals, so `error`
never sees them. The `rounding ... worst case 0 u` block is correct (bit casts are
exact), but the headline max-rel number must not be read as an error bound.

### WRONG-3 — `error` ignores the approximation's `where` / range domain
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (golden `16_error_domain.ucas` / `.out`)

```sh
cd $ROOT/tests/stress/areas/float/magic_constants
cat <<'EOF' | timeout 15 $ROOT/ucas
nw(x: f32) = asfloat(0x5f3759df - (asuint(x) >> 1)) where x >= 1 && x <= 2
domain nw
error nw ~ 1/sqrt(x)
EOF
```

**Observed:**

```
domain of nw:
  x: f32 (every finite value)
  where x >= 1 && x <= 2
  no conditions: total on its parameter types
  defined at 122 of 122 points
  sampled 122 points (domain has 4278190079 points); not exhaustive
error of nw against 1/sqrt(x):
  max abs error 0.169721 at x=0.04
  max rel error 0.0342885 (3.43%) at x=3.74
  mean rel error 0.0236166 over 500 points
```

**Why it matters:** it is a bug / what was expected** — `domain nw` restricts x to [1,2] (122
points), but `error nw ~ 1/sqrt(x)` reports its worst points at `x=3.74` and
`x=0.04`, outside that domain, with exactly the same numbers as the unrestricted
case. `measure()` samples the *target's* domain and drops `g`'s restrictions.
`equiv` does not have this problem (`equiv a ~ b` with the same `where` proves
equality on the restricted domain), so the two commands are inconsistent. A user
asking "how good is my approximation on [1,2]?" gets a global answer.

### LIMIT-1 — bit hacks fail at special values (verified, not a ucas bug)
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
These are genuine limitations of the bit hacks, confirmed by `equiv` (files
`10_abs_mask` … `15_special_values`, `mcp_bithacks.jsonl`):

- `min` via unsigned-integer comparison hack
  `asfloat(y ^ ((x ^ y) & -(asuint(x) < asuint(y))))` is **wrong for negative
  floats**: `equiv mn ~ rmin` returns `differ at 49275 points, e.g. x=-6.01e+33,
  y=-1.94e-23`. Adding the positive range `in 0..1e30` makes it prove equal.
- `asfloat(asuint(x) & 0xffc00000)` is **truncation**, not `floor`, for negatives
  (`equiv trunc ~ floor(x)` differs at 65139 points); it proves equal on `0..1e30`.
- `asfloat(asuint(x) & 0x7fffffff)` matches `abs(x)` bitwise including NaN payloads
  (`equiv ... nanbits` proved), but **under `ftz` they differ at 255 points** because
  the bit cast preserves subnormals while `abs` flushes them — correct mode-sensitive
  behaviour, documented here so it is not mistaken for a regression.
- Subnormals, signed zero and NaN payloads: `asfloat(0x00000001)=1.4e-45`,
  `asfloat(0x80000000)=-0`, `asfloat(0x7f800001)`/abs of negative sNaN behave as
  expected (file `15_special_values`).

### LIMIT-2 — SAT fallback counterexample did not reproduce
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
printf 'idb(x: f32) = asfloat(asuint(x))\nidf(x: f32) = x\nequiv idb ~ idf\n' | \
  timeout 15 $ROOT/ucas
```

**Observed:**

```
idb and x are equal on the domain of idb (sampled, not proved; no SAT proof: its counterexample did not reproduce)
```

**Why it matters:** it matters** — `asfloat(asuint(x))` is exactly the identity on all f32 bit
patterns, so the SAT encoder's "counterexample" was spurious and the proof degraded
to sampling. Not unsound, but it shows the SAT path mishandles the asuint/asfloat
round-trip; worth tracking as a proof-coverage gap.

### LIMIT-3 — `rings` division magic: no defects found
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
All 1000 divisors 1..1000 for `u32` and `i32` (2000 `magic` queries, saved in
`magic_all.raw`) were checked with `python3 verify_magic.py`:

* algebraic Granlund–Montgomery full-domain condition for every returned `(m, s)`:
  `m = ceil(2^k/d)` and `e = m*d - 2^k` in range — **0 problems** (990 nontrivial +
  18 powers of two + 2 identities per sign category);
* exact integer-division check (split 64-bit multiply-shift) on boundaries plus
  200 000 random inputs per divisor: **0 problems**;
* fully exhaustive numpy comparison over all 2^32 / 2^31 inputs for a subset
  (d = 3, 7; see `exhaustive.log`): **0 problems**.

No non-optimal constants, wrong shifts or crashes were found. MCP strictness
(`magic` needs `divisor`/`type`; `equiv` over MCP needs explicit `ftz`/`nanbits`)
is documented API behaviour, not a defect.

## Checks that passed

_No separate passed checks were recorded in the original document._
