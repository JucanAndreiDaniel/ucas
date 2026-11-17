# Stress findings — `tex_domain_modules`

_Original heading: FINDINGS — tex_domain_modules stress test_

# FINDINGS — tex_domain_modules stress test

Area: domain-specific MCP tools `texalu`, `texenc`, `lperm`, `winograd`, `tcdot`,
`ozaki`, `solids`, `plot`, `hypercomplex`. All reproducers use the MCP wire
(`ucas --mcp`) with `files:"none"` / `nofile:true` so nothing is written to disk.

Severity legend: `CRASH | HANG | WRONG | NLP | LIMIT | DETERMINISM`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 8 | `winograd` reports a finite error bound that overflow ignores |
| LIMIT | 1 | `tcdot` with the documented maximum sample count takes ~20 s |

## Findings

### WRONG-1 — `winograd` reports a finite error bound that overflow ignores
**Severity:** WRONG
**Reproducer:**
Reproducer (copy-paste):
```sh
cd $ROOT/tests/stress/areas/gpu/tex_domain_modules
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":"dbig(a0: f32 in -1e30..1e30, a1: f32 in -1e30..1e30, b0: f32 in -1e30..1e30, b1: f32 in -1e30..1e30) = a0*b0 + a1*b1"}}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"winograd","arguments":{"function":"dbig","rows":8,"cols":8,"files":"none"}}}' \
 | timeout 15 $ROOT/ucas --mcp
```
(Also recorded deterministically as `mcp_winograd_bounds.jsonl`, id 14.)

**Observed:**
```
floats: the same algebra, not the same roundings; |computed - exact| <= gamma_4 (sum |x_2j + y_2j+1| |x_2j+1 + y_2j| + sum |x x| + sum |y y|) <= 1.43051e+54 over the parameters' ranges
```

**Why it matters:** for f32 operands in ±1e30 the intermediate `(a0+b1)*(a1+b0)`
reaches ~4e60 and `a0*a1 + b0*b1` reaches ~2e60, both far past f32's 3.4e38
maximum. Evaluating the Winograd expression with f32 arithmetic gives
`inf - inf = NaN`, so `|computed - exact|` is not `<= 1.43e54` — the bound is
false over the declared parameter ranges. (Verified with IEEE f32: `(2e30)*(2e30)`
overflows to `inf`, the difference is `NaN`.) The derived bound is computed from
the real-valued ranges only, with no account of overflow in the intermediates.
**Expected:** the tool should either cap the ranges / detect overflow and decline to
state a finite bound, or return an infinite/NaN bound.

### WRONG-2 — `solids arclength` of `ln(x)` on [0,1] returns a finite value for a divergent integral
**Severity:** WRONG
**Reproducer:**
Reproducer: `mcp_solids_singular.jsonl`, id 5; equivalently
```sh
cd $ROOT/tests/stress/areas/gpu/tex_domain_modules
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"solids","arguments":{"op":"arclength","args":{"f":"ln(x)","from":"0","to":"1","nofile":true}}}}' \
 | timeout 15 $ROOT/ucas --mcp
```

**Observed:**
```
numeric (adaptive Gauss-Kronrod 7-15, 2985 evaluations): 68.8475580313482, estimated error 7.6e-13
arc length: 68.85
```

**Why it matters:** the arc length is `∫_0^1 sqrt(1 + 1/x^2) dx = ∫_0^1 sqrt(x^2+1)/x dx`,
which behaves like `∫ 1/x dx` near 0 and **diverges to +∞**. The tool reports a
precise finite 68.85 with a tiny error estimate. Note also the internal
inconsistency: it hit the 2985-evaluation cap yet claims `estimated error 7.6e-13`.
The `area` op correctly detects the analogous divergence for `1/x` on [0,1], so
`arclength` should report divergence too.
**Expected:** "diverges / no finite arc length".

### WRONG-3 — `solids arclength` of `1/sqrt(x)` on [0,1] returns a huge finite number for a divergent integral
**Severity:** WRONG
**Reproducer:**
```sh
# `mcp_solids_singular.jsonl`, id 6 (same pattern as #2 with `"f":"1/sqrt(x)"`).
cd $ROOT/tests/stress/areas/gpu/tex_domain_modules
timeout 15 $ROOT/ucas --mcp < mcp_solids_singular.jsonl
```

**Observed:**
```
numeric (adaptive Gauss-Kronrod 7-15, 2985 evaluations): 796131459065721, estimated error 8.8
arc length: 7.961e+14
```

**Why it matters:** `f' = -1/(2 x^(3/2))`, so the arc integrand behaves like
`1/(2 x^(3/2))` near 0 and the integral diverges. 7.96e14 is just where the
adaptive quadrature gave up, not a length; no divergence warning is emitted.
**Expected:** report the integral as divergent.

### WRONG-4 — `solids arclength` of `x^(2/3)` on [-1,1] returns a value below the chord (true ≈ 2.879)
**Severity:** WRONG
**Reproducer:**
```sh
# `mcp_solids_singular.jsonl`, id 1 (`"f":"x^(2/3)"`, from -1 to 1).
cd $ROOT/tests/stress/areas/gpu/tex_domain_modules
timeout 15 $ROOT/ucas --mcp < mcp_solids_singular.jsonl
```

**Observed:**
```
numeric: the integrand is undefined or infinite inside the interval (singular or divergent)
arc length: 1.186
```

**Why it matters:** the cusp at x=0 is integrable. With `x=t^3`,
`2∫_0^1 sqrt(1+(4/9)x^(-2/3)) dx = 2∫_0^1 3t sqrt(t^2+4/9) dt ≈ 2.8794`.
The reported 1.186 is not even the length of the polyline through
(-1,1),(0,0),(1,1), which is `2√2 ≈ 2.828` — an arc can never be shorter than
its chord. The tool abandons the integrable interior singularity and returns a
too-small number.
**Expected:** ≈ 2.879 with a note that the cusp is integrable.

### WRONG-5 — `solids surfacearea` of `x^(2/3)` on [-1,1] falsely declares divergence
**Severity:** WRONG
**Reproducer:**
```sh
# `mcp_solids_singular.jsonl`, id 15 (`"op":"surfacearea"`, `"f":"x^(2/3)"`, about x).
cd $ROOT/tests/stress/areas/gpu/tex_domain_modules
timeout 15 $ROOT/ucas --mcp < mcp_solids_singular.jsonl
```

**Observed:**
```
    x^(2/3): S = 2pi ∫ |x^(2/3)| sqrt(1 + (0.6666666667x^(-0.3333333333))^2) dx
      numeric: singular or divergent
```

**Why it matters:** the integrand near 0 behaves as `x^(2/3)·(2/3)x^(-1/3) = (2/3)x^(1/3)`,
which is finite and integrable; the surface area exists and is ≈ 9.873
(`2·2π∫_0^1 3t^3 sqrt(t^2+4/9) dt`). The tool reports no value and claims
"singular or divergent".
**Expected:** ≈ 9.87.

### WRONG-6 — `hypercomplex zerodivisors` silently defaults an unknown algebra to sedenion
**Severity:** WRONG
_Original classification: `WRONG/NLP`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer: `mcp_hypercomplex_zero.jsonl`, id 7 (`"op":"zerodivisors","args":{"algebra":"bogus"}`).

**Observed:**
```
zero divisors in the sedenions:
  (e1 - e10)(e4 + e15) = 0, although |e1 - e10| = |e4 + e15| = sqrt(2)
```

**Why it matters:** `"bogus"` is not a valid algebra. The sibling `algebra` op
correctly errors with `algebra complex|quaternion|octonion|sedenion|cd N`, and
`cd(1)` / `cd(64)` are rejected. `zerodivisors` silently returns the sedenion
answer for any unrecognised name — a bogus answer accepted from a malformed argument.

### WRONG-7 — `hypercomplex multiplication_table` treats an unknown algebra name as a variable
**Severity:** WRONG
_Original classification: `WRONG/NLP`._
**Reproducer:**
```sh
# `mcp_hypercomplex_zero.jsonl`, id 11 (`"op":"multiplication_table","args":{"algebra":"bogus"}`).
cd $ROOT/tests/stress/areas/gpu/tex_domain_modules
timeout 15 $ROOT/ucas --mcp < mcp_hypercomplex_zero.jsonl
```

**Observed:**
```
  bogus=-10  ->  -10
  bogus=-9  ->  -9
  ...
  bogus=10  ->  10
```

**Why it matters:** instead of rejecting the unknown algebra, the op falls through
to the generic table builder and emits a nonsense "table" of the token `bogus`.
**Expected:** the same `algebra ...` usage error that op `algebra` gives.

### WRONG-8 — `texenc` silently accepts a 3-D ASTC footprint as its 2-D prefix
**Severity:** WRONG
_Original classification: `WRONG/NLP`._
**Reproducer:**
```sh
# `mcp_texenc_astc_etc.jsonl`, id 8 (`"astc":"4x4x4"`).
cd $ROOT/tests/stress/areas/gpu/tex_domain_modules
timeout 15 $ROOT/ucas --mcp < mcp_texenc_astc_etc.jsonl
```

**Observed:**
```
texenc the table astc 4x4: 16 entries as ASTC 4x4, rows of 4 (4 x 4 texels): 1 block, 16 bytes ...
```

**Why it matters:** `astc` is documented as a 2-D footprint `BWxBH` (4x4 to 12x12);
the tool's own error message says "ASTC's 2D blocks are 4x4, 5x4, ...". A 3-D
footprint `4x4x4` should be rejected, but the third component is silently
dropped and a 4x4 block is produced. Same for `6x6x6`, etc.
**Expected:** a domain
error naming the invalid footprint.

### LIMIT-1 — `tcdot` with the documented maximum sample count takes ~20 s
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (`samples=100000` is the tool's stated upper bound: "samples from 1 to 100000"):
```sh
printf '%s\n' \
 '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"tcdot","arguments":{"n":16,"samples":100000,"seed":1,"files":"none"}}}' \
 | timeout 30 $ROOT/ucas --mcp
```

**Observed:** exit 0, valid output, but wall-clock ~20 s (timed out at the 15 s
bound). This is not kept as a golden.
**Expected:** an accepted option should
complete in reasonable time, or the documented bound should be smaller.

## Checks that passed

### Notes on areas that behaved correctly
- `lperm` cleanly rejects non-power-of-two lane counts (`lanes N, a power of two from 2 to 64`)
  and out-of-range lane maps; no crashes.
- `texalu` handled border reads / neighbour stencils under several models;
  rewrites were deterministic, `files:"none"` honoured.
- `plot` / `plot3d` / `neighbourhood` with degenerate bounds (`x in 0..0`,
  `nan..nan`, poles, constant functions) either produce a stable GIF checksum with
  `nofile` or a clean error; no stray image files were left behind. A degenerate
  window `[1e10, 1e10+1]` collapses to `[1e10, 1e10]` due to float precision (minor).
- `tcdot` and all other tools were deterministic run-to-run (the random sampler
  is seeded deterministically by default), so goldens are safe.

All above WRONG/LIMIT findings are captured in stable, deterministic golden
`.out` files (except #9, per the contract).
