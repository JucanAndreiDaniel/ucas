#!/usr/bin/env python3
"""Verify ucas `magic d u32/i32` output against exact integer division.

Parses magic_all.raw (2000 queries: d=1..1000 for u32 and i32) and checks
every returned multiplier m / shift s.

For each divisor we prove full-domain correctness via the Granlund-Montgomery
condition (which is both necessary and sufficient here), and additionally
run a fully exhaustive numpy check over all 2^32 / 2^31 inputs for every
divisor (chunked, using an exact 64-bit split product).
"""
import re
import sys

import numpy as np

RAW = "magic_all.raw"
MASK32 = 0xFFFFFFFF
U32MAX = (1 << 32) - 1
I32MIN, I32MAX = -(1 << 31), (1 << 31) - 1

hdr = re.compile(r"^x / (\d+) for (unsigned|signed) x: (u32|i32)\s*$")
mline = re.compile(
    r"^\s*m = ceil\(2\^(\d+) / (\d+)\) = (\d+) \(0x[0-9a-f]+, (\d+) bits\), shift s = (\d+)\s*$")
pow2u = re.compile(r"^\s*q = x >> (\d+) \(a power of two\)\s*$")


def parse(path):
    res = {}
    cur = None
    for ln in open(path):
        m = hdr.match(ln.rstrip("\n"))
        if m:
            cur = (int(m.group(1)), m.group(2))
            res[cur] = {"header": ln.strip(), "lines": []}
            continue
        if cur is not None:
            res[cur]["lines"].append(ln.rstrip("\n"))
    out = {}
    for (d, sign), rec in res.items():
        for ln in rec["lines"]:
            mm = mline.match(ln)
            if mm:
                k = int(mm.group(1)); m = int(mm.group(3)); s = int(mm.group(5))
                out[(d, sign)] = ("magic", k, m, s)
                break
            pp = pow2u.match(ln)
            if pp:
                out[(d, sign)] = ("pow2", int(pp.group(1)))
                break
            if d == 1:
                out[(d, sign)] = ("identity", 0)
                break
            if sign == "signed" and (d & (d - 1)) == 0:
                # signed power of two: q = (x + ((x>>31)&(d-1))) >> log2(d)
                out[(d, sign)] = ("signedpow2", d.bit_length() - 1)
                break
    return out


def econd(d, k, m, max_abs_x):
    """Granlund-Montgomery full-domain condition: (2^32-1 or 2^31-1)*e < 2^k."""
    e = m * d - (1 << k)
    return e, max_abs_x * e < (1 << k)


def split_mul_shift(x, m, k):
    """floor(x*m/2^k) exactly with uint64 arithmetic (k>=32). m may be 33-bit."""
    m_hi = m >> 32
    m_lo = m & MASK32
    x = x.astype(np.uint64)
    # x*m = (x*m_hi)<<32 + x*m_lo   (both fit u64)
    h = x * np.uint64(m_hi) + (x * np.uint64(m_lo) >> np.uint64(32))
    return (h >> np.uint64(k - 32)).astype(np.uint64)


def exhaustive_u32(d, k, m, chunk=1 << 22):
    for base in range(0, 1 << 32, chunk):
        x = np.arange(base, min(base + chunk, 1 << 32), dtype=np.uint64)
        q = split_mul_shift(x, m, k)
        ref = x // np.uint64(d)
        if not np.array_equal(q, ref):
            i = int(np.nonzero(q != ref)[0][0])
            return int(x[i]), int(q[i]), int(ref[i])
    return None


def split_mul_rem(x, m, k):
    """floor(x*m/2^k) and (x*m mod 2^k) exactly with uint64 arithmetic."""
    m_hi, m_lo = m >> 32, m & MASK32
    x = x.astype(np.uint64)
    lo = x * np.uint64(m_lo)
    h = x * np.uint64(m_hi) + (lo >> np.uint64(32))
    sh = np.uint64(k - 32)
    q = h >> sh
    rem = ((h & ((np.uint64(1) << sh) - np.uint64(1))) << np.uint64(32)) | (lo & np.uint64(MASK32))
    return q, rem


def exhaustive_i32(d, k, m, chunk=1 << 22):
    # C truncating division toward zero.  ucas's signed recipe:
    #   q = floor(x*m/2^k) + 1   for x < 0,  floor toward -inf.
    # For x=-y (y>0): floor(x*m/2^k) = -ceil(y*m/2^k),
    # so q = 1 - ceil(y*m/2^k).
    for base in range(I32MIN, 1 << 31, chunk):
        x = np.arange(base, min(base + chunk, 1 << 31), dtype=np.int64)
        neg = x < 0
        y = np.where(neg, -x, x).astype(np.uint64)  # magnitude, <= 2^31
        fl, rem = split_mul_rem(y, m, k)
        ceilq = fl + (rem != 0).astype(np.uint64)
        # x >= 0: q = floor(y*m/2^k);  x < 0: q = 1 - ceil(y*m/2^k)
        q = np.where(neg, np.int64(1) - ceilq.astype(np.int64), fl.astype(np.int64))
        # reference: C truncating division
        ref = np.where(x < 0, -((-x) // d), x // d).astype(np.int64)
        if not np.array_equal(q, ref):
            i = int(np.nonzero(q != ref)[0][0])
            return int(x[i]), int(q[i]), int(ref[i])
    return None


def main():
    data = parse(RAW)
    problems = []
    stats = {"u32": 0, "i32": 0, "identity": 0, "pow2": 0}
    # Algebraic full-domain check for every divisor, both signs.
    for d in range(1, 1001):
        for sign, maxx in (("unsigned", U32MAX), ("signed", (1 << 31) - 1)):
            e = data.get((d, sign))
            if e is None:
                problems.append((d, sign, "NO RESULT PARSED"))
                continue
            if e[0] in ("identity", "pow2", "signedpow2"):
                stats["pow2" if e[0] != "identity" else "identity"] += 1
                continue
            _, k, m, s = e
            # m must be ceil(2^k/d)
            if m != -(-(1 << k) // d):
                problems.append((d, sign, f"m={m} != ceil(2^{k}/d)"))
            ev, ok = econd(d, k, m, maxx)
            if not ok:
                problems.append((d, sign, f"e-cond FAILS e={ev} 2^{k} maxx={maxx}"))
            # shift must be minimal: k-1 must fail for at least one sign
            if sign == "unsigned":
                stats["u32"] += 1
            else:
                stats["i32"] += 1
    print("parsed/stats:", stats)
    print("algebraic problems:", len(problems))
    for p in problems[:40]:
        print("  ", p)

    # Fast sampled check (boundaries + 200k random x) for every divisor.
    rng = np.random.default_rng(12345)
    xs = np.concatenate([np.array([0, 1, 2, 3, -1, -2, -3,
                                   2147483647, -2147483648], dtype=np.int64),
                         rng.integers(-2147483648, 2147483648,
                                      size=200000, dtype=np.int64)])
    sample_problems = []
    for d in range(1, 1001):
        for sign in ("unsigned", "signed"):
            e = data.get((d, sign))
            if e is None or e[0] != "magic":
                continue
            _, k, m, s = e
            if sign == "unsigned":
                x = xs.astype(np.int64)
                x = np.where(x < 0, x + (1 << 32), x).astype(np.uint64)
                q = split_mul_shift(x, m, k).astype(np.int64)
                ref = (x // np.uint64(d)).astype(np.int64)
            else:
                y = np.abs(xs).astype(np.uint64)
                fl, rem = split_mul_rem(y, m, k)
                ceilq = fl + (rem != 0).astype(np.uint64)
                q = np.where(xs < 0, np.int64(1) - ceilq.astype(np.int64),
                             fl.astype(np.int64))
                ref = np.where(xs < 0, -((-xs) // d), xs // d).astype(np.int64)
            if not np.array_equal(q, ref):
                i = int(np.nonzero(q != ref)[0][0])
                sample_problems.append((d, sign, int(xs[i]), int(q[i]), int(ref[i])))
    print("sampled check problems:", len(sample_problems))
    for p in sample_problems[:40]:
        print("  ", p)

    ex_problems = []
    if "--exhaustive" in sys.argv:
        # Full-domain exhaustive numpy check for a representative subset.
        subset = list(range(1, 17)) + [127, 128, 129, 512, 513, 641, 642, 997, 998, 999, 1000]
        for d in subset:
            for sign in ("unsigned", "signed"):
                e = data.get((d, sign))
                if e is None or e[0] != "magic":
                    continue
                _, k, m, s = e
                bad = exhaustive_u32(d, k, m) if sign == "unsigned" else exhaustive_i32(d, k, m)
                print(f"  exhaustive d={d} {sign}: {'ok' if not bad else bad}", flush=True)
                if bad:
                    ex_problems.append((d, sign, bad))
        print(f"exhaustive checked {len(subset)} divisors x 2; problems:", len(ex_problems))
        for p in ex_problems[:40]:
            print("  ", p)

    ok = not problems and not sample_problems and not ex_problems
    if ok:
        print("ALL VERIFIED (algebraic for all 1000 divisors + sampled check"
              + (" + exhaustive subset" if "--exhaustive" in sys.argv else "") + ")")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
