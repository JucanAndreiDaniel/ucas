#!/usr/bin/env python3
"""Independent oracle for the WRONG finding on `fit guess ~ rsqrt`.

For x a f32 in [0.01, 100] and K a u32:

    rsqrt(x) = 1/sqrt(x)                       (exact real target)
    guess(x, K) = asfloat(K - (asuint(x) >> 1))  (f32 bit hack)

Max relative error = max_x |guess(x,K) - 1/sqrt(x)| / (1/sqrt(x)).
We enumerate *every* f32 bit pattern in the interval (111,421,686 values),
so the result is not a sample.  numpy floats are IEEE f32/f64 as required.

Usage: python3 verify_fit_oracle.py
"""
import numpy as np

def f32_bits(v): return np.asarray(v, dtype=np.float32).view(np.uint32)
def bits_f32(u): return np.asarray(u, dtype=np.uint32).view(np.float32)

LO = int(f32_bits(np.float32(0.01)))
HI = int(f32_bits(np.float32(100.0)))

def maxrel(K):
    best, bx = 0.0, None
    for start in range(LO, HI + 1, 1 << 20):
        u = np.arange(start, min(start + (1 << 20), HI + 1), dtype=np.uint32)
        x = bits_f32(u).astype(np.float64)
        g = bits_f32((np.uint32(K) - (u >> np.uint32(1))).astype(np.uint32)).astype(np.float64)
        e = 1.0 / np.sqrt(x)
        rel = np.abs(g - e) / e
        i = int(np.argmax(rel))
        if rel[i] > best:
            best, bx = float(rel[i]), float(x[i])
    return best, bx

if __name__ == "__main__":
    # What `fit guess ~ rsqrt` returns:
    kfit = 0x5f3763ed
    # A strictly better constant found by a window search around kfit:
    kbetter = 0x5f376423
    for K in (kfit, kbetter, 0x5f3759df):
        mx, bx = maxrel(K)
        print(f"K=0x{K:08x}: exhaustive max-rel = {mx:.10g} at x={bx:.9g}")
