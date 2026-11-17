# SUMMARY — `spirv_glsl_simplify`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 6
- Files created: 13

### Counts

- **Distinct expressions / shaders / queries tried:** ≈ 260
  - 192 in five batched harness runs (`/tmp/cases{,2,3,4,5}.py`: 52 + 29 + 50 + 44 + 17),
    each run under `timeout`, with exit codes recorded.
  - ~70 more interactive probes: direct MCP tool calls, `ucas --json` range-overflow
    characterisation (boundaries around 2^63), 64-bit type-inference survey over 8
    opcodes, 64-bit unsoundness reproductions, `--mcp` replay of overflow inputs,
    `--flat` mode, and repeated CLI golden runs for determinism.
- **Determinism checks:** 192 cases run twice (52 + 29 + 50 + 44 + 17) and diffed;
  5 files were re-run twice for their goldens.
- **Golden / reproducer files created:** 13
  - `01_int_spv.ucas` + `.out` (integer SPIR-V peepholes, SAT proofs)
  - `02_glsl_fn.ucas` + `.out` (GLSL function-level: dead branch, unused mask, switch)
  - `03_float.ucas` + `.out` (Vulkan precision / bit-exact / ulp 0 / ulp 2 / ranges)
  - `04_c_ranges.ucas` + `.out` (C frontend + integer assumptions)
  - `mcp_simplify.jsonl` + `.out` (MCP golden, 12 tool calls: spv/glsl/c/float/ranges/errors/advice)
  - `mcp_flat.jsonl` + `.flags` (`--flat`) + `.out` (flat-mode MCP golden)
- **Docs:** `FINDINGS.md`, `SUMMARY.md`.

Coverage included: power-of-two mul/div, UMod, bitfield extract/insert, clamp/min/max,
select-of-constant, shift chains, algebra-mod-2^w hash chains, UB (div by zero,
shift ≥ width), 32/64/8/16-bit widths, huge constants, floats (FDiv/FAdd/FMul,
Sqrt/Pow/Mix/Step, NaN/inf/±0/subnormals, exact/ulp/approx/percomp/search/seed/sink),
ranges and float_ranges, function-level dead branches / unused masks / loops / repeated
and recursive calls / switches, subgroup / texture / derivative builtins, C inputs,
advice/overdraw/texture/files options, malformed GLSL and SPIR-V, oversized modules,
deep expression chains, null bytes and control characters, and missing tools.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | (1) 64-bit comparison operands inferred as 32-bit; (2) ranges bounds near 2^63 overflow to INT64_MIN and drive an unsound rewrite |
| NLP | 1 | GLSL compile failure surfaced as "SPIR-V: not an instruction" |
| LIMIT | 2 | spirv-cross missing (GLSL view skipped); transient Code-Mode MCP disconnect not reproducible via --mcp |
| DETERMINISM | 2 | (1) random /tmp/ucas-glsl-XXXXXX.glsl in compile-error text; (2) wall-clock "derived/proved in X.X s" in text |

### Issues by severity

| Severity | Count | Short description |
|---|---:|---|
| CRASH | 0 | no nonzero exits or signals in any bounded run |
| HANG | 0 | no run hit its `timeout` (all returned in ≤ a few seconds) |
| WRONG | 2 | (1) 64-bit comparison operands inferred as 32-bit; (2) `ranges` bounds near 2^63 overflow to INT64_MIN and drive an unsound rewrite |
| DETERMINISM | 2 | (1) random `/tmp/ucas-glsl-XXXXXX.glsl` in compile-error text; (2) wall-clock "derived/proved in X.X s" in text |
| NLP | 1 | GLSL compile failure surfaced as "SPIR-V: not an instruction" |
| LIMIT | 2 | spirv-cross missing (GLSL view skipped); transient Code-Mode MCP disconnect not reproducible via `--mcp` |

Plus a low-severity "accepted-invalid inputs" note (inverted ranges, negative `ulp`) in
FINDINGS.md.


## Takeaway
The simplifier is crash- and hang-free across ~260 adversarial queries and its normal integer, float and function-level proofs look sound, but two soundness bugs remain — 64-bit comparison operands are typed as 32-bit, and integer range bounds near 2^63 wrap to INT64_MIN and can produce a rewrite that is false on the requested domain; human-readable output also contains nondeterministic timing and temp-path text.

### Original takeaway (verbatim)

The simplifier is crash- and hang-free across ~260 adversarial queries and its normal
integer, float and function-level proofs look sound, but two soundness bugs remain —
64-bit comparison operands are typed as 32-bit, and integer range bounds near 2^63
wrap to INT64_MIN and can produce a rewrite that is false on the requested domain;
human-readable output also contains nondeterministic timing and temp-path text.

### Folder confirmation

All files listed above were created only in
`$ROOT/tests/stress/areas/gpu/spirv_glsl_simplify/`. No source file, Makefile,
existing test, `opencode.json`, or another subagent's folder was touched; no build or
git command was run.
