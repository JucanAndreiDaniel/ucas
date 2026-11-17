#!/usr/bin/env python3
"""Independent near-exact evaluation of guess(x,K)=asfloat(K-(asuint(x)>>1)).

The relative error of the classic inverse-sqrt guess depends (in exact
arithmetic) only on the parity of x's exponent and on its mantissa, so we
enumerate all 2^23 mantissas for both parities plus the subnormal region.
float64 has 53 bits: plenty to measure a ~3% relative error to ~1e-15.
"""
import numpy as np

M23 = 1 << 23
MASK32 = 0xFFFFFFFF

# representative *normal* exponents (one even, one odd is enough, but we
# sample several to make sure no exponent-dependent effect is missed)
NORMAL_EXPS = [1, 2, 100, 101, 126, 127, 128, 129, 200, 201, 253, 254]


def f32_from_bits(bits):
    b = np.asarray(bits, dtype=np.uint32)
    return b.view(np.float32).astype(np.float64)


def relerr_for_normal(K, E):
    """max relative error over all mantissas for normal exponent E."""
    M = np.arange(M23, dtype=np.uint64)
    bits = ((E << 23) | M).astype(np.uint32)
    x = f32_from_bits(bits)
    gbits = ((K - (bits.astype(np.uint64) >> 1)) & MASK32).astype(np.uint32)
    g = f32_from_bits(gbits)
    # valid only when g is a finite positive float
    gf = gbits.view(np.float32).astype(np.float64)
    valid = (g >= 0) & (gbits < 0x7F800000) & (x > 0)
    t = 1.0 / np.sqrt(x)
    with np.errstate(all="ignore"):
        re = np.abs(gf - t) / np.abs(t)
    re = np.where(valid, re, 0.0)
    i = int(np.argmax(re))
    return float(re[i]), int(M[i]), E


def relerr_for_subnormal(K):
    """max relative error over all subnormal x (E=0, mantissa>0)."""
    M = np.arange(1, M23, dtype=np.uint64)
    bits = M.astype(np.uint32)
    x = f32_from_bits(bits)
    gbits = ((K - (bits.astype(np.uint64) >> 1)) & MASK32).astype(np.uint32)
    gf = gbits.view(np.float32).astype(np.float64)
    valid = (gbits < 0x7F800000) & (x > 0)
    t = 1.0 / np.sqrt(x)
    with np.errstate(all="ignore"):
        re = np.abs(gf - t) / np.abs(t)
    re = np.where(valid, re, 0.0)
    i = int(np.argmax(re))
    return float(re[i]), int(M[i]), 0


def max_relerr(K):
    """Return (maxrel, description) over the representative domain."""
    best = (0.0, None)
    for E in NORMAL_EXPS:
        r, m, e = relerr_for_normal(K, E)
        if r > best[0]:
            best = (r, (e, m))
    r, m, e = relerr_for_subnormal(K)
    if r > best[0]:
        best = (r, (e, m))
    return best


if __name__ == "__main__":
    import sys
    Ks = [int(k, 0) for k in sys.argv[1:]] or [
        0x5F3759DF, 0x5F37642F, 0x5F376033, 0x5F375A86]
    for K in Ks:
        r, at = max_relerr(K)
        print(f"K=0x{K:08x} maxrel={r:.7g} at exp={at[0]} mant={at[1]}")
