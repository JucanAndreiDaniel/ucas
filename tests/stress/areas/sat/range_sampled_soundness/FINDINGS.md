# Stress findings — `range_sampled_soundness`

_Original heading: `range_sampled_soundness` — findings_

# `range_sampled_soundness` — findings

Systematic follow-up on Master Findings **Top priority #4 (wrong `range`/`domain`)**.
Area: sampled/exhaustive `range` soundness on u16 / u32 / i16 / i32 / f32.

Method: 419 generated single-variable functions (arithmetic with wrap, isolated spikes,
step functions, interior extrema/quadratics, bitwise masks/shifts/rotates, abs, tables,
`match`, `where`, f32 conversions) plus ~170 hand-targeted probes (two-variable masks,
variable shifts, division, casts, composition, narrowed domains). An **independent**
Python oracle used full brute force for exhaustive domains (u8/u16/i16), a 30k–60k-point
edge-and-random grid for u32/i32, and a domain-restricted float grid for f32. For every
function the ucas headline min/max, `sound bound (intervals)`, `proved bound
(monotonicity, exact algebra)` and every `take x = …` witness were compared to the oracle.

Classification (from the 419 generated cases):
- **exhaustive-correct**: 207
- **sampled-but-sound** (no dense-grid counterexample): 123
- **sampled-unsound** (dense-grid counterexample to the headline, confirmed with `show`): 84
- **proved-but-wrong**: **0** (see Positive results)

All runs under `timeout 15`; all golden outputs run twice and byte-diffed (deterministic).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 5 | sampled headline excludes reachable values (84 confirmed instances) |

## Findings

### WRONG-1 — sampled headline excludes reachable values (84 confirmed instances)
**Severity:** WRONG
**Why it matters:** _not recorded_
The headline of a sampled `range` excludes values that a concrete input attains. The
separate `sound bound (intervals)` line is correct in **every** case, so the bug is the
headline being read as a bound (it is labelled "sampled … not exhaustive"). New instances
beyond `sat_ranges_where` / `fp_edge` include signed/unsigned wrap arithmetic, isolated
spikes, shifts, rotates, quadratics, two-variable masks, variable shifts and bit-casts.

**Reproducer:**
Reproducer (isolated spike, u32):
```sh
cd $ROOT/tests/stress/areas/sat/range_sampled_soundness
timeout 15 $ROOT/ucas 01_sampled_spike_u32.ucas
```
**Observed:**
```
range of spk -> int:
  0..0
  fits in u1
  sampled 65536 points (domain has 4294967296 points); not exhaustive
  sound bound (intervals): 0..1000000007
...
_() = 1000000007        <- show spk(3)
```
**Expected:** / why a bug:** `spk(3)=1000000007` is reachable, so the headline `0..0` is not a
bound. The sampler (65,536 points) never visits `x=3` (it does visit `x=0` and `x=1`).

Other confirmed instances (all deterministic, with `show` witnesses):
| function | headline | reachable value | witness |
|---|---|---|---|
| `x+2` on u32 | `1..4294942909` | `0`, `4294967295` | wrap corners |
| `x-2` on u32 | `10487..4294967295` | `0` | `x=2` |
| `x==3?1e9:0` on u32 | `0..0` | `1e9` | `x=3` |
| `x==3?1e9:0` on i32 | `0..0` | `1e9` | `x=3` |
| `x<<16` on i32 | `-2147418112..2147418112` | `-2147483648` | wrap corner |
| `(x<<8)\|(x>>24)` on i32 | headline misses `INT32_MIN` | `-2147483648` | rotate |
| `(x-1000)*(x+1000)` on i32 | min misses `INT32_MIN` | `-2147483648` | wrap |

### WRONG-2 — two-variable sampled ranges miss reachable corners (new pattern)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/range_sampled_soundness
timeout 15 $ROOT/ucas 02_multivar_mask.ucas
```
**Observed:**
```
range of bor -> u16:
  1..65535   (13903 distinct values)
  ...
  sound bound (intervals): 0..65535
...
_() = 0        <- show bor(0,0)
range of band -> u16:
  0..65408   (8581 distinct values)
  ...
  sound bound (intervals): 0..65535
...
_() = 65535    <- show band(65535,65535)
```
**Why it matters:** a bug:** `x|y` reaches 0 at `(0,0)` (headline min 1 is wrong) and `x&y` reaches
65535 at `(65535,65535)` (headline max 65408 is wrong). The 2-D sampler misses both
corners. (The `band` max is the same instance reported in `grammar_fuzz_reduce`; the
`bor` **min** miss is a new direction.)

### WRONG-3 — variable-shift range misses the `s=0` corner (new pattern)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/range_sampled_soundness
timeout 15 $ROOT/ucas 03_varshift_asfloat.ucas
```
**Observed:**
```
range of vshr -> i32:
  -2106916413..2147483647
  fits in i32
  undefined at 57322 points
  sampled 65536 points (domain has 1099511627776 points); not exhaustive
  sound bound (intervals): -2147483648..2147483647
...
_() = -2147483648    <- show vshr(-2147483648, 0)
```
**Why it matters:** a bug:** `vshr(INT32_MIN, 0) = INT32_MIN` is reachable and below the headline min.
The sound bound is correct.

### WRONG-4 — `asfloat(u32)` IEEE side-count "±inf at 0 points" is unsound (new pattern)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer:** same file `03_varshift_asfloat.ucas`.
**Observed:**
```
range of asf -> f32:
  [-3.40002206e+38, 3.37868943e+38]
  IEEE: NaN at 258 points, ±inf at 0 points
  sampled 65536 points (domain has 4294967296 points); not exhaustive
...
_() = inf    <- show asf(2139095040)   (0x7f800000)
```
**Why it matters:** a bug:** ±inf is reachable (bit patterns `0x7f800000` / `0xff800000`), so reporting
"±inf at 0 points" is false; the headline also misses both f32 infinities and the exact
finite extremes. This is a sampled *count* being stated as an absolute, not just a bound.

### WRONG-5 — f32 sampled headline excludes a reachable spike and the true minimum
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/range_sampled_soundness
timeout 15 $ROOT/ucas 04_f32_sampled.ucas
```
**Observed:**
```
range of f_spk05 -> f32:
  [0, 1]
  sampled 65536 points (domain has 1065353217 points); not exhaustive
...
_() = 1.00000002e+30    <- show f_spk05(0.5)
range of f_abs -> f32:
  [1.13084786e-41, 1]
  sampled 65536 points (domain has 2130706433 points); not exhaustive
...
_() = 0                <- show f_abs(0)
```
**Why it matters:** a bug:** `f_spk05(0.5)=1e30` is reachable (same class as `fp_edge`). New: the `abs`
headline min is `1.13e-41` although `f_abs(0)=0` — the sampler skipped the zero input for
this expression, so even a plain non-spike function gets an unsound f32 lower bound.
f32 sampled ranges print **no** `sound bound` line at all, so there is no sound fallback.

## Checks that passed

### Positive results (no issue) — sound/proved bounds and witnesses
Across all 419 generated cases and the targeted probes there were **0** violations of the
`sound bound (intervals)` line and **0** proved-bound witnesses that failed to attain the
claimed extremum. In particular:
- exhaustive u8/u16/i16 ranges (identity, `-x`, `x*x`, isolated spikes, tables, `match`)
  are exact, including distinct-value lists;
- proved-bound functions (`identity`, `x>>k`, `x|0`, `~x`, `x/2+x/4`, `4294967295-x`)
  give correct monotonicity direction and correct `take x = …` witnesses;
- `where` / `in a..b` narrowings are honoured (range is exhaustive over the narrowed
  range, e.g. `x where x<10` → `0..9`, `over all 10 points`).

Reproducer for the clean controls:
```sh
cd $ROOT/tests/stress/areas/sat/range_sampled_soundness
timeout 15 $ROOT/ucas 05_proved_sound_controls.ucas
timeout 15 $ROOT/ucas 06_exhaustive_controls.ucas
```
The structured MCP view (`mcp_range_structured.jsonl`) confirms the fields: the sampled
spike has `proof.kind:"numeric"`, `sound_bound:[0,1000000007]`, `proved_bound:null`;
`x>>16` has `proof.kind:"symbolic"` with `proved_bound.max_steps` ending in `take x =
4294967295` / `65535` (both verified to attain). All MCP output byte-stable across runs.

**Scope note:** the known "proved bound (monotonicity) claims unreachable max for
i56–i63" bug (`type_coercion`) was **not** reproduced for u16/u32/i16/i32: every integer
endpoint here is exactly representable as a double, so the double-rounded interval
endpoints that break wide types do not arise in this area.
