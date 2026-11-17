# Stress findings — `nan_subnormal_modes`

_Original heading: FINDINGS — `nan_subnormal_modes` (idea 5: mode-sensitive float equivalence)_

# FINDINGS — `nan_subnormal_modes` (idea 5: mode-sensitive float equivalence)

Area owner folder only: `tests/stress/areas/float/nan_subnormal_modes/`.
Binary: `$ROOT/ucas`.
All reproducers are deterministic (each golden was run twice and `diff`ed; see SUMMARY).

-------------------------------------------------------------------------------

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | algebraic identities defeat FTZ operand flushing |
| LIMIT | 4 | no rounding-direction mode for `equiv` |

## Findings

### WRONG-1 — algebraic identities defeat FTZ operand flushing
**Severity:** WRONG
_Original classification: `WRONG (unsound equal:true, equivalently an ignored mode effect`._
**Expected:** _not recorded_
**README contract:** *"`equiv F G ftz` flushes subnormals: every float operation (a bit cast aside)
reads a subnormal operand as the zero of its sign and gives one for a subnormal result,
in the evaluator and in the circuit alike".*

**What happens:** `x * 1` and `x - 0` are folded into a bare bitcast identity before the
FTZ circuit is built.  No float operation remains, so the subnormal operand is never
flushed.  ucas then reports `x*1 == x` under `ftz`, whereas a non-folded multiply does
flush and behaves differently.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/float/nan_subnormal_modes
$ROOT/ucas 05_ftz_identity_unsound.ucas
```

**Observed:** output (exact lines from `05_ftz_identity_unsound.out`):
```
> equiv mul1 passthru ftz
mul1 and passthru are equal on the domain of mul1 (proved by SAT: 1105 AIG nodes, 0 conflicts)
  every float operation flushed subnormals to zero (ftz)
> equiv mul1 fl ftz
mul1 and fl differ at 259 points of the sample, e.g. x=1: 1.40129846e-45 vs 0
  every float operation flushed subnormals to zero (ftz)
...
> equiv mul3 fl3 ftz
mul3 and fl3 are equal on the domain of mul3 (proved by SAT: 8418 AIG nodes, 4211 conflicts)
  every float operation flushed subnormals to zero (ftz)
```
where `mul1(x)=asfloat(x)*f32(1)`, `fl(x)` explicitly flushes subnormal `x`,
`mul3(x)=asfloat(x)*f32(3)`, `fl3(x)=fl(x)*f32(3)`.

**Why it matters:** under the documented FTZ semantics the subnormal operand of `x*1`
must be read as zero, so `mul1` should equal `fl` under `ftz`, and `mul1` should
**differ** from the unflushed `passthru` bitcast.  ucas instead proves `mul1 == passthru`
under `ftz` and still finds `mul1 != fl`.  The non-folded control (`mul3`/`fl3`) behaves
correctly, isolating the fault to algebraic folding removing the flushable operation.
The same holds for `x - f32(0)` (also folded to `x`, 1105 nodes).
Note `x + f32(0)` is *not* folded (because `-0 + +0 = +0`), so it flushes correctly —
see `01_ftz_modes.out`.

-------------------------------------------------------------------------------

### WRONG-2 — JSON/MCP `equiv` silently misparses expression-string args, wrong verdict + ignored ftz flag
**Severity:** WRONG
_Original classification: `WRONG (false equal:false, plus the ftz mode flag is swallowed`._
**Why it matters:** _not recorded_
`tools.ucas.analyze({op:"equiv", args:{f,g,ftz,nanbits}})` documents `f`/`g` as
"expressions are ucas syntax strings (x^2 sin(x))".  `jsonmode.c:render_func` copies a
J_STR argument verbatim into a space-separated `equiv F G [ftz] [nanbits]` command with
no quoting/parenthesising.  An expression containing spaces is therefore tokenised into
several names.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/float/nan_subnormal_modes
$ROOT/ucas --mcp < mcp_expr_misparse.jsonl
```

**Observed:** output (from `mcp_expr_misparse.out`, `id` 1 / 2 / 3):
```
id=1 ucas: equiv asfloat(x: u32) + f32(0) asfloat(x) noftz
     equal=False, mismatch_points=65533, method=sampled,
     counterexample="x=4294967295: -nan vs 4.2949673e+09"
id=2 ucas: equiv asfloat(x: u32) + f32(0) asfloat(x) ftz
     equal=False, ftz=FALSE (despite ftz:true in the request!), method=sampled
id=3 (correct object form {"body":...,"params":...}):
     equal=True (proved by SAT: 5170 AIG nodes, 1462 conflicts)
```
The garbled function name in the rendered text — `asfloat(x) + 0asfloat(x) and noftz` —
shows the mode token `noftz`/`ftz` was consumed as the *second function's name*, so the
requested `ftz` flag never reached `cmd_equiv` (reported `ftz:false`).

**Expected:** either the same answer as the object form (`equal:true`), or a clean
`bad_request` error.  Instead a wrong verdict is returned with `ok:true` and no warning.
Workaround: pass `{"body": expr, "params":[{name,type}]}` objects or define functions
first and pass their names (see `mcp_mode_matrix.jsonl`, which uses defined names).

-------------------------------------------------------------------------------

### LIMIT-1 — no rounding-direction mode for `equiv`
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The FOCUS mentions rounding direction, but `equiv` only accepts `ftz|noftz` and
`nanbits`; arithmetic is always round-to-nearest-even.  Rounding-direction tokens are
clean parse errors, not silent fallbacks.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/float/nan_subnormal_modes
$ROOT/ucas _scratch/edge_modes.ucas
```
**Observed:**
```
equiv r1 r2 rte
edge_modes.ucas:10:13: error: unexpected 'rte' after the statement
equiv r1 r2 rz     -> error: unexpected 'rz'
equiv r1 r2 rn     -> error: unexpected 'rn'
```
Flag order itself is fine: `equiv ... nanbits ftz` and `equiv ... ftz nanbits` produce
identical verdicts and both note lines.

-------------------------------------------------------------------------------

### LIMIT-2 — min/max NaN propagation is order-dependent when NaNs enter the domain
**Severity:** LIMIT
_Original classification: `LIMIT (documented as left open in README, but observable only with`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`u32 -> asfloat` inputs).

`min(x,y)` vs `min(y,x)` is proved equal (with and without `nanbits`) when the
parameters are `f32` — because an `f32` parameter's domain is the finite values and
NaNs are excluded.  When inputs are `u32` bit-cast with `asfloat`, *every* bit pattern
including NaNs is in the domain and the order matters for NaN payloads:

**Reproducer:**
Reproducer:** `03_zero_minmax.ucas`, command `equiv mnf mng nanbits`.
**Observed:** (`03_zero_minmax.out`):
```
mnf and mng differ at 1 point of the sample, e.g. a=4293458434, b=4286966646:
  NaN 0xffe8fa02 vs NaN 0xffc5eb76
```
Rationale: README states "what `min` of a signaling NaN gives" is left open; ucas
propagates a different NaN operand depending on argument order.  Not a soundness bug in
ucas, but a trap for anyone assuming min/max are bit-for-bit commutative under
`nanbits` — and a reminder that the `f32`-parameter domain excludes NaNs.

-------------------------------------------------------------------------------

### LIMIT-3 — `asuint(asfloat(x))` is not a bit identity for sNaN patterns
**Severity:** LIMIT
_Original classification: `LIMIT (documented behaviour, surprising in practice`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
CAST round-tripping a `u32` through `asfloat` quiets signaling NaNs, because the
evaluator holds f32 in a double ("an f32 NaN read quiet, as the evaluator holds f32 in
a double", README).  A hand-computed expectation of "bit identity" was wrong in 130 of
65536 sample points.

**Reproducer:**
Reproducer:** `03_zero_minmax.ucas`, `equiv zidf zerog`.
**Observed:** (`03_zero_minmax.out`):
```
zidf and zerog differ at 130 points of the sample, e.g. x=2139370684:
  2143564988 vs 2139370684
```
`0x7f9a2a5c` (sNaN) is read back as `0x7fc02a5c` (quiet bit set).  The earlier
`equiv ib1 ib2 nanbits` proof in `tests/fpsat.out` succeeds only because its input is
already forced quiet (`x | 0x7fc00000`).

-------------------------------------------------------------------------------

### LIMIT-4 — "counterexample did not reproduce" fallback under `nanbits`
**Severity:** LIMIT
_Original classification: `LIMIT (observation; no false verdict confirmed`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Several float results with free NaN payloads fall back to `equal:true, sampled, not
proved; no SAT proof: its counterexample did not reproduce` under `nanbits`:

- `02_nanbits_modes.out`: `equiv sqf sqg nanbits` (sNaN + 0 quieting).
- `tests/fpsat.out` already has the same pattern for `asfloat(x)+0` vs `asfloat(x)`.

This is defensible — the host libm leaves arithmetic-NaN payloads open — but it means
`nanbits` cannot decide those cases, and a "did not reproduce" message is emitted rather
than a warning that the verdict is only sampled.  I found no case where this fallback
flipped a provably false statement to `equal:true`.

-------------------------------------------------------------------------------

## Checks that passed

### Negative results (no bug found)
- **No mode-flag state leakage.** `cmd_equiv` resets `float_ftz`, `nsat_ftz`,
  `nsat_floats`, `equiv_nanbits`, `nsat_nanbits` after every call (`src/analyze.c:2340`).
  MCP session `mcp_state_leak.jsonl` alternates ftz/noftz and nanbits on/off 13 times:
  every verdict matches its mode (id 2/4 differ with ftz, id 3/14 equal without, etc.).
- **Aux ops unaffected by prior equiv modes.** `mcp_aux_leak.jsonl` interleaves `range`,
  `domain`, `wrap` with mode-flipped `equiv`s; repeated `range` (id 2 vs 4, id 11 vs 13)
  and `wrap` (id 8 vs 10) outputs are byte-identical.
- **Flag order-independent** (`equiv nanf nang nanbits ftz` ≡ `equiv nanf nang ftz nanbits`).
- **MCP refuses missing flags** with a clean `unsupported` error: omitting `ftz` for a
  float formula, or omitting `nanbits` for a float result (verified over `--mcp`).
- **Expectation sweep clean.** Across the 203-pair batch, 331 verdicts had a hand-computed
  expectation; the 13 mismatches were all traced to errors in *my* expectations
  (sNaN quieting on read, order-dependent NaN min, float-vs-integer select conditions,
  and `x-0` folding) after re-deriving from IEEE-754.  Zero unexplained wrong verdicts.
