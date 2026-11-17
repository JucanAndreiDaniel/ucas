# Floating-point "magic" testing ideas

Sources:

- **"There are Only Four Billion Floats – So Test Them All!"** (Bruce Dawson, 2014):
  <https://randomascii.wordpress.com/2014/01/27/theres-only-four-billion-floatsso-test-them-all/> — all 2^32
  float bit patterns can be enumerated in ~90 s. f16 (2^16) is trivial; f32 unary ops are feasible with a tight
  loop. LLVM libc verifies unary ops exhaustively over all bit patterns:
  <https://codebrowser.dev/llvm/libc/test/src/math/exhaustive/exhaustive_test.h.html>.
- **Lefèvre & Muller — *Worst cases for correct rounding of the elementary functions in double precision***,
  ARITH-15 (2001): <http://www.acsel-lab.com/arithmetic/arith15/papers/ARITH15_Lefevre.pdf> and
  <https://perso.ens-lyon.fr/jean-michel.muller/Intro-to-TMD.htm> — the "Table Maker's Dilemma": inputs whose
  exact image is closest to a rounding breakpoint. These are the hardest cases for correct rounding and the
  ones random sampling never hits.
- **MPFR**: <https://www.mpfr.org/> — correct rounding for all operations and math functions; the reference
  oracle. Python `mpmath` is a convenient frontend.
- **"When Double Rounding is Correct"** (2026): <https://arxiv.org/pdf/2610.09005> — tests every IEEE-like
  format of ≤8 bits exhaustively against MPFR; double rounding is a real correctness trap.
- ** Andrysco et al. — *Towards Verified, Constant-time Floating Point Operations***, CCS 2018:
  <http://cseweb.ucsd.edu/~dstefan/pubs/andrysco:2018:towards.pdf> — FTZ/DAZ flags, subnormals, NaN payloads,
  sNaN quieting; all modes must be modelled.
- **Magic-number division**: Granlund & Montgomery (PLDI 1994) <https://gmplib.org/~tege/divcnst-pldi94.pdf>,
  Hacker's Delight (Warren), optimal bounds <https://pmc.ncbi.nlm.nih.gov/articles/PMC8258644>. ucas's `rings`
  tool has "division magic numbers".
- **Fast inverse square root** (0x5f3759df): <https://arxiv.org/html/1802.06302v1> — the magic constant is an
  approximation chosen for accuracy over a domain; check optimality, not just correctness.

## ucas recipes

1. **Exhaustive f16** — enumerate all 65536 bit patterns, run `range`/`equiv`/`wrap` and each unary function;
   compare to exact rational/mpmath results. f32 unary: stride the 2^32 space plus all special regions.
2. **Worst-case rounding** — construct inputs just below/above rounding breakpoints for `exp`, `log`, `sin`,
   `sqrt`, `1/x`; feed to `f16`/`f32`/`f64` evaluation with an mpmath oracle at 200-bit precision.
3. **Double rounding** — generate values that round one way at f64 and another directly at f32; check ucas's
   `f32(x)` and mixed `f64`→`f32` conversions.
4. **Magic constants** — for `guess(x,K)=asfloat(K-(asuint(x)>>1))` and friends, verify `fit`'s K is optimal by
   exhaustive search over a window around it; check `error`'s max-rel-error claim against exact evaluation at
   the worst point. Also verify `rings` division-magic numbers for all divisors in a range.
5. **Mode-sensitive equivalence** — `equiv base f1 nanbits`, `ftz`, `noftz`: build pairs that differ only under
   sNaN payload preservation, subnormal flushing, signed zero, or rounding direction; check `equiv` honours the
   mode flag and does not silently drop a counterexample.
6. **Bit-hack identities** — `(x & y) + (x ^ y) == x | y` style over f32 bit patterns via `asuint`/`asfloat`;
   min/max via masks, `abs` via bit clearing, `floor`/`ceil` tricks — verify for subnormals, signed zero and
   NaN payloads.
