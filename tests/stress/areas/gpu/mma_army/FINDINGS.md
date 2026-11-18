# FINDINGS — `mma_army`

Area: the MMA/SWAR/dot/fusion/NPN/lane-permutation sources —
`src/mma.c`, `src/swar.c`, `src/dot.c`, `src/tcdot.c`, `src/fuse.c`,
`src/npn.c`, `src/lperm.c`.  All reproducers were run under
`UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`; every golden was regenerated from
the fixed (current HEAD) binary with the canonical CLI command and checked
byte-identical on two runs.

## Summary

| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 0 | no wrong proof, range, cost or emitted form found |
| CRASH | 0 | no signal exit under fuzzing or ASan/UBSan |
| HANG | 0 | no reproducer exceeded its time budget |
| LIMIT | 0 | search limits are reported when hit |

Fourteen CLI goldens cover all seven modules plus explicit controls.  No
source file needed a fix, so **no existing golden in the repository needs
recapture** from this work.

## Findings

No reproducible bug was found.  The mining effort and its negative results:

- **MMA lowering (`mma.c`).** Ran every shape in `mma.ucas`, f16 and f32
  accumulators, `chain 1..4`, tiles `2x1x1`, `1x2x1`, `2x2x1`, `1x1x2`,
  `1x1x4`, `2x1x2` and the built-in models rdna2/mali_g715/sm86/gt1030.
  Every run self-proves the dataflow over all 32 lanes and reports the
  sampled error `within the bound`; none printed `OVER THE BOUND` or an
  internal-proof failure.  The emitted GLSL of `mma m16n8k8 f32` was
  independently emulated in Python (unpacks, subgroup shuffles, xor and
  index shuffles, fma, output packing) on 50 random fragment sets and
  matched the exact `A*B+C` sum within the gamma bound (worst ratio
  `0.001` of the bound).
- **SWAR identities (`swar.c`).** Fuzzed ~120 random word-wide byte/half
  expressions with `find`; every rewrite that fired was `proved by SAT`.
- **Integer dot (`dot.c`).** 4000 random `show` cases across all 18
  forms (including 64-bit accumulator literals and negatives) matched an
  independent Python transcription exactly, after reading the accumulator
  in the result's type.  120 narrow-domain `range` cases were checked
  exhaustively and were sound and tight.
- **Fusion (`fuse.c`).** Checked LUT/IMAD/shift/float covers, custom
  models, inheritance, `nofuse`, modifier classes and proved-width XMAD
  forms; costs were consistent with the prices and the tallies.
- **NPN (`npn.c`).** `gates npn` reports the correct 222 classes with the
  expected `2 + 12 + 117 + 91` histogram and all 222 proved minimal; the
  LUT3 rewrite in `08_npn.out` is checked by SAT.
- **Lane permutations (`lperm.c`).** 180 random affine and non-affine maps
  over 32/64 lanes: the reported map, the affine columns and constant, and
  `rank(I xor A)` matched independent evaluation; the Benes maps in
  `10_lperm_benes.out` are composed on every lane by the tool.

## Checks that passed

- **Crash/hang fuzzing**: ~1100 CLI cases (lperm, tcdot, mma, dot, SWAR)
  in batches; no signal exit, no timeout beyond the normal ~8-35 s cost of
  a full MMA search.
- **Sanitizers**: gcc `-fsanitize=address` and `-fsanitize=undefined`
  builds run over the fuzz corpora; no ASan report, no UBSan runtime error.
- **Numeric edge options**: negative, zero and very large `n/samples/seed/
  chain/tile` values were rejected gracefully or handled; no crash.
- **Determinism**: repeated runs of MMA, tcdot, `gates npn` and lperm were
  byte-identical.
- **Controls** (`14_controls.out`): byte-difference symmetry, `tc_dot` of
  one product equals its f32 conversion, a signed byte field folded into
  a `sudot4x8` (SAT), and `udot4x8` equals its lane-wise sum (SAT) all
  pass, so the oracles above are exercised on working paths.

## Existing goldens needing recapture

None.  No source file was changed, so the repository's current goldens
remain valid.
