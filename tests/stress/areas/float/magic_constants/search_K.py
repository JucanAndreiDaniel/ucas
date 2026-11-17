#!/usr/bin/env python3
"""Find the K minimising the max relative error of
guess(x,K)=asfloat(K-(asuint(x)>>1)) over all normal f32 mantissas.

Relative error is parity-periodic in the exponent for the exact-real target,
so one even and one odd exponent suffice.  We also evaluate a variant where
the target is rounded to f32 (as ucas's `error` measures it).
"""
import numpy as np

M23 = 1 << 23
MASK32 = 0xFFFFFFFF

# representative normal exponents: one even, one odd
EVEN_E, ODD_E = 2, 3


def build(step=1):
    M = np.arange(0, M23, step, dtype=np.uint64)
    out = {"M": M}
    for name, E in [("even", EVEN_E), ("odd", ODD_E)]:
        bits = ((E << 23) | M).astype(np.uint32)
        x = bits.view(np.float32).astype(np.float64)
        t_real = 1.0 / np.sqrt(x)
        t_f32 = np.float32(1.0 / np.float32(np.sqrt(np.float32(x)))).astype(np.float64)
        out[name] = (bits, t_real, t_f32)
    return out


FULL = build(1)
COARSE = build(8)


def obj(K, target="real", D=FULL):
    worst = -1.0
    where = None
    for name in ("even", "odd"):
        bits, t_real, t_f32 = D[name]
        t = t_real if target == "real" else t_f32
        gbits = ((K - (bits.astype(np.uint64) >> 1)) & MASK32).astype(np.uint32)
        g = gbits.view(np.float32).astype(np.float64)
        valid = (gbits < 0x7F800000) & (bits < 0x7F800000)
        with np.errstate(all="ignore"):
            re = np.abs(g - t) / np.abs(t)
        re = np.where(valid, re, -1.0)
        i = int(np.argmax(re))
        if re[i] > worst:
            worst = float(re[i]); where = (name, int(D["M"][i]))
    return worst, where


if __name__ == "__main__":
    import sys
    lo = 0x5F3759DF - 1024
    hi = 0x5F3759DF + 1024
    if len(sys.argv) >= 3:
        lo, hi = int(sys.argv[1], 0), int(sys.argv[2], 0)
    target = "f32" if "--f32" in sys.argv else "real"
    best = (float("inf"), None)
    for K in range(lo, hi + 1, 4):
        o, _ = obj(K, target, COARSE)
        if o < best[0]:
            best = (o, K)
    c = best[1]
    print(f"coarse best K=0x{c:08x} obj={best[0]:.9g}")
    fine = (float("inf"), None)
    for K in range(c - 8, c + 9):
        o, w = obj(K, target, FULL)
        if o < fine[0]:
            fine = (o, K, w)
    print(f"fine   best K=0x{fine[1]:08x} obj={fine[0]:.9g} at {fine[2]}")
    for K in [0x5F3759DF, 0x5F37642F, 0x5F376033, 0x5F375A86, fine[1]]:
        o, w = obj(K, target, FULL)
        print(f"K=0x{K:08x} obj={o:.9g} at {w}")
