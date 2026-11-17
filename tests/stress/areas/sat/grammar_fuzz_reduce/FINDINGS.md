# Stress findings — `grammar_fuzz_reduce`

_Original heading: FINDINGS — `grammar_fuzz_reduce`_

# FINDINGS — `grammar_fuzz_reduce`

Area: type-directed grammar fuzzing + fingerprint differential + ddmin shrinking.
Binary: `$ROOT/ucas`.  All reproducers were run from this folder.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | `equiv` coerces the second function to the first function's result type |
| LIMIT | 3 | fingerprint-blind spot (no ucas bug, oracle limitation) |

## Findings

### WRONG-1 — `equiv` coerces the second function to the first function's result type
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/grammar_fuzz_reduce
timeout 30 $ROOT/ucas 01_equiv_cast_coercion.ucas
```

**Observed:** (`01_equiv_cast_coercion.out`)

```
> f(x: i8) = u8(x)
> g(x: i8) = i32(x)
> show f(-128)
_() = 128
  -> u8
> show g(-128)
_() = -128
  -> i32
...
> equiv f g
f and g are equal on the domain of f (exhaustive)
```

The same wrong `equal:true` comes back over MCP (`mcp_equiv_cast.jsonl` / `mcp_equiv_cast.out`):

```json
{"id":2,...,"result":{"structuredContent":{"cmd":"equiv","result":{"kind":"equiv","equal":true,"exhaustive":true,"mismatch_points":0,"method":"exhaustive"},"text":"f and g are equal on the domain of f (exhaustive)\n"}}}
```

Minimized by `reduce.py expr --id 96` from a 60-node generated i16 expression to
`minimized/min_equiv_cast.ucas` (3 statements, 2 steps):

```
f(x: i16) = (i16(0) != i16(0))
g(x: i16) = i16(32)
equiv f g
```
```
f and g are equal on the domain of f (exhaustive)
```

**Why it matters:** it is a bug.** `show` proves the two functions return different mathematical
values at the same input (128 vs −128; −1.5-type bool vs 32 in the minimized case).
`equiv` reports `equal:true` with `method:exhaustive`, i.e. a proof, not a sample.
The mechanism is a result-type coercion: g's value is truncated to f's result type
before comparison (32 → 0 in bool, −128 → 128 in u8).
**Expected:** either compare
results as mathematical integers (→ `differ`, with a counterexample) or refuse to
compare functions with incompatible result types.  The bug also fires with
`equiv g f`, with `f(x:u8)=i8(x)` vs `g(x:u8)=x`, and with an undefined second name
(see LIMIT 3).

### WRONG-2 — sampled `range` excludes reachable corner values
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/grammar_fuzz_reduce
timeout 30 $ROOT/ucas 02_range_excludes_reachable.ucas
```

**Observed:** (`02_range_excludes_reachable.out`, abridged)

```
range of a -> u16:
  0..65408   (8581 distinct values)
  sampled 65536 points ...; not exhaustive
  sound bound (intervals): 0..65535
> show a(65535, 65535)
_() = 65535
range of b -> u16:
  1..65535   (13903 distinct values)
  sound bound (intervals): 0..65535
> show b(0, 0)
_() = 0
range of c -> u16:
  0..65534   (37024 distinct values)
  sound bound (intervals): 0..65535
> show c(255, 257)
_() = 65535
```

**Why it matters:** it is a bug.** Every displayed `range` omits a value the tool itself returns
from `show` at a concrete input: 65535 ∉ [0, 65408], 0 ∉ [1, 65535], 65535 ∉
[0, 65534].  The same command prints a *sound* interval bound (0..65535) that does
include them, so the tool knows the true bound; the headline range is still printed
as a definite `lo..hi`.
**Expected:** label the headline numbers as sample extrema (or
union them with the sound bound) so a reachable value is never excluded.  Found by
the generator's independent Python oracle: 28 of 240 cases had a sampled range
that excluded a value from a corner/random valuation.

### WRONG-3 — float `equiv` reports "are equal" from an incomplete sample
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/grammar_fuzz_reduce
timeout 30 $ROOT/ucas 03_equiv_float_sampled.ucas
```

**Observed:** (`03_equiv_float_sampled.out`)

```
> equiv f g
f and g are equal on the domain of f (sampled, not proved; no SAT proof: a float division (by other than a constant power of two))
> show f(1.0, -0.5)
_() = -0.5
  -> f32
> show g(1.0, -0.5)
_() = -1.5
  -> f32
```

**Why it matters:** it is a bug.** The verdict sentence asserts equality, but the two functions
evaluate to different f32 values at an input inside the domain.  The parenthetical
that SAT had no proof is printed *after* the equality claim and does not change it.
**Expected:** say "not proved / inconclusive" (or return the found counterexample)
instead of "`are equal`".  This is the fingerprint-refutation direction: the
corner battery found (x=1, y=−0.5) as a disagreeing valuation, and ucas's own
`show` confirmed it.

### LIMIT-1 — fingerprint-blind spot (no ucas bug, oracle limitation)
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Corner valuations (`0, 1, −1, MIN, MAX`, boundaries, seeded random) for
`i8` make `f(y) = y % 14` and `g(y) = y % 21` collide: no battery point separates
them, so a cheap fingerprint would call them candidate identities.  ucas correctly
refutes the identity with a valid counterexample:

**Observed:**
**Reproducer:**
```sh
f(x: i8, y: i8) = y % i8(14)
g(x: i8, y: i8) = y % i8(21)
equiv f g
```
```
f and g differ at 43008 points, e.g. x=-128, y=-125
```
`y = −125`: `−125 % 14 = −13`, `−125 % 21 = −20`, so the refutation is sound
(fingerprint blind spot, not an unsound `equiv`).  Corpus case 140, recorded in
`anomalies.jsonl` as `FINGERPRINT_BLINDSPOT`.  Takeaway: fingerprint collisions are
only *candidates*; always confirm with the solver.

### LIMIT-2 — `equiv` with an undefined function name silently succeeds
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Observed:**
**Reproducer:**
```sh
f(x: i8) = u8(x)
equiv f g
```
```
f and g are equal on the domain of f (exhaustive)
```
`g` was never defined; it is silently read as a free variable, and the same
result-type coercion as finding 1 makes the query claim equality.
**Expected:** a
parse/domain error for an undefined function name.  Found while running the
line-level ddmin (the minimizer's predicate now rejects reductions that drop a
definition).

### LIMIT-3 — SAT budget exhausted but "equal" still reported
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Observed:**
**Reproducer:**
```sh
a(x: u32, y: u32) = x % y
b(x: u32, y: u32) = x - (x/y)*y
equiv a b
```
```
a and b are equal on the domain of a (sampled, not proved; SAT gave up on 21603 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```
This particular identity is true (so no WRONG verdict), but the headline again
says "are equal".  Took 6.25 s wall-clock — the longest single query in the sweep;
no hang or crash was observed anywhere (the slowest of 240 CLI cases stayed well
under `timeout 15`).

## Checks that passed

### Determinism
`gen.py --seed 0x5EED --count 240` produces byte-identical `corpus.jsonl` across
runs and across `PYTHONHASHSEED=1` vs `999` (a set-iteration nondeterminism in the
operator choice was found and fixed).  Every golden was generated twice and the
two outputs diffed: `01_*`, `02_*`, `03_*` and `mcp_equiv_cast.out` are all stable,
so they are safe as `.out` tests.  No nondeterministic case is kept as a golden.
