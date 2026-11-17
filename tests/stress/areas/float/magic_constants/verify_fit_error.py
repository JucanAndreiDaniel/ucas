#!/usr/bin/env python3
"""Consolidated exact check of fit/error claims for the inverse-sqrt guess.

Reproduces the numbers cited in FINDINGS.md from first principles.
Run:  python3 verify_fit_error.py
"""
import numpy as np
import search_K as s
import verify_guess as v

CONSTS = [0x5F3759DF, 0x5F37642F, 0x5F376033, 0x5F375A86]
FIT_ANSWER = 0x5F376033

print("=== exact max relative error over ALL normal f32 mantissas ===")
for K in CONSTS:
    o, w = s.obj(K, "real", s.FULL)
    print(f"  K=0x{K:08x}  maxrel={o:.9f}  at exponent={w[0]} mantissa={w[1]}")

print("=== exact max relative error over full f32 domain (incl. subnormals) ===")
for K in CONSTS:
    o, at = v.max_relerr(K)
    print(f"  K=0x{K:08x}  maxrel={o:.7f}  at exp={at[0]} mant={at[1]}")

print("=== dense exact search over +-1024 of fit's answer (mantissa stride 16) ===")
D16 = s.build(16)
lo, hi = FIT_ANSWER - 1024, FIT_ANSWER + 1024
best = min((s.obj(K, "real", D16)[0], K) for K in range(lo, hi + 1))
o, K = best
ofull, w = s.obj(K, "real", s.FULL)
print(f"  true minimax K=0x{K:08x}  maxrel(full mantissas)={ofull:.9f}")
ofit, wfit = s.obj(FIT_ANSWER, "real", s.FULL)
print(f"  fit's K        =0x{FIT_ANSWER:08x}  maxrel(full mantissas)={ofit:.9f}")
print(f"  fit is optimal? {K == FIT_ANSWER}   (false => fit returned a non-optimal constant)")
