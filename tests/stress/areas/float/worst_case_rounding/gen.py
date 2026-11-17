#!/usr/bin/env python3
"""
Generate 200+ adversarial worst-case-rounding inputs for ucas and compare
ucas's f16/f32/f64 evaluation against the 200+-bit mpmath oracle in oracle.py.

Outputs (all inside this folder):
  cases.json              machine-readable manifest with expected oracle bits
  NN_*.ucas               golden input files (<=18 `show asuint(...)` each)
  gen_report.txt          summary of each case: MATCH / MISMATCH + ulp info

Run:
  python3 gen.py            # regenerate cases + .ucas files + compare
  python3 gen.py --no-run   # only regenerate, do not run ucas
"""
# --- portability: derive the repo root from this file's own location -------
# Walk up until a directory containing both the `ucas` binary and `src/` is found.
from pathlib import Path as _ROOT_PATH
def _repo_root():
    here = _ROOT_PATH(__file__).resolve()
    for d in here.parents:
        if (d / 'ucas').is_file() and (d / 'src').is_dir():
            return d
    raise RuntimeError('ucas repo root not found above ' + str(here))
_REPO_ROOT = _repo_root()
ROOT = str(_REPO_ROOT)
import json
import math
import os
import random
import struct
import subprocess
import sys

import mpmath as mp

import oracle as O

HERE = os.path.dirname(os.path.abspath(__file__))
UCAS = str(_REPO_ROOT / "ucas")

FUNCS = ("exp", "log", "sqrt", "sin", "cos", "recip")


# ---------------------------------------------------------------------------
# expression construction
# ---------------------------------------------------------------------------
def input_expr(bits, fmt):
    return "asfloat(u%d(0x%0*x))" % (
        {"f16": 16, "f32": 32, "f64": 64}[fmt],
        {"f16": 4, "f32": 8, "f64": 16}[fmt], bits)


def func_expr(func, bits, in_fmt, out_fmt):
    x = input_expr(bits, in_fmt)
    if func == "recip":
        core = "%s(1)/%s" % (in_fmt, x)
    else:
        core = "%s(%s)" % (func, x)
    # ucas types a function result by its argument's float type; when the
    # requested output differs, add the explicit narrowing cast (this is the
    # f64 -> f32 / f64 -> f16 double-rounding path we want to test).
    if in_fmt != out_fmt:
        return "%s(%s)" % (out_fmt, core)
    return core


def show_expr(func, bits, in_fmt, out_fmt):
    return "show asuint(%s)" % func_expr(func, bits, in_fmt, out_fmt)


# ---------------------------------------------------------------------------
# random IEEE bit helpers
# ---------------------------------------------------------------------------
def rand_bits(fmt, rng, exp_lo=None, exp_hi=None, sign=None, nonzero=True):
    w, p, bias, emax = O.FMT[fmt]
    ewf = w - p
    emaxfield = (1 << ewf) - 1
    if exp_lo is None:
        exp_lo = 1
    if exp_hi is None:
        exp_hi = emaxfield - 1
    ef = rng.randint(exp_lo, exp_hi)
    frac = rng.getrandbits(p - 1)
    if sign is None:
        s = rng.randint(0, 1)
    else:
        s = sign
    b = (s << (w - 1)) | (ef << (p - 1)) | frac
    if nonzero and frac == 0:
        b |= 1
    return b


# ---------------------------------------------------------------------------
# inverse functions for midpoint root-finding
# ---------------------------------------------------------------------------
def inverse(func, t):
    if func == "exp":
        return mp.log(t)
    if func == "log":
        return mp.exp(t)
    if func == "sqrt":
        return t * t
    if func == "recip":
        return 1 / t
    if func == "sin":
        return mp.asin(t)
    if func == "cos":
        return mp.acos(t)
    raise ValueError(func)


def real_inverse(func, t):
    """inverse() with a guard for a tiny complex part (midpoint just outside
    the range of asin/acos).  Returns None if not a usable real value."""
    try:
        xs = inverse(func, t)
    except (ValueError, ZeroDivisionError):
        return None
    if isinstance(xs, mp.mpc):
        if abs(mp.im(xs)) > mp.mpf(10) ** -40:
            return None
        xs = mp.re(xs)
    return xs


# ---------------------------------------------------------------------------
# case generators
# ---------------------------------------------------------------------------
CASES = []


def add(cat, func, xbits, in_fmt, out_fmt, desc, oracle_override=None):
    if oracle_override is None:
        try:
            oracle_bits = O.oracle_bits(func, xbits, in_fmt, out_fmt)
            double_bits = O.double_round_bits(func, xbits, in_fmt, out_fmt)
        except (ValueError, ZeroDivisionError, AttributeError, OverflowError):
            return  # e.g. sqrt of a negative subnormal -> NaN; not comparable
    else:
        oracle_bits, double_bits = oracle_override
    CASES.append(dict(cat=cat, func=func, xbits=xbits, in_fmt=in_fmt,
                      out_fmt=out_fmt, desc=desc,
                      oracle=oracle_bits, double=double_bits,
                      expr=show_expr(func, xbits, in_fmt, out_fmt)))


def gen_published():
    """Published hardest-to-round constants (Lefevre/Muller) + classic cases."""
    # Hex constants from Lefevre 2013 / Muller worst-case tables.
    pub = [
        ("exp", "-0x1.12D31A20FB38Bp+5", "f64", "exp worst-case RN, whole domain (Lefevre 2013)"),
        ("exp", "0x1.FFFFFFFFFFFFP-53",  "f64", "exp directed-rounding worst case near 0"),
        ("log", "0x1.FD15DAA6CE332p+732", "f64", "log worst-case RN, whole domain (Lefevre 2013)"),
        ("log", "0x1.62A88613629B6p+678", "f64", "log directed-rounding worst case (Lefevre 2013)"),
        ("log", "0x1.0110001010101000100001100001001101100010100110110110p+678",
         "f64", "classic log worst case (Muller TMD)"),
    ]
    for func, h, fmt, desc in pub:
        try:
            b = O.f64_bits_from_hex(h)
        except (ValueError, OverflowError):
            continue
        add("01_published", func, b, fmt, fmt, desc + "  [" + h + "]")
    # classic hard-but-simple inputs
    classics = [
        ("exp", 0x3FF0000000000000, "exp(1)=e"),
        ("exp", 0xBFF0000000000000, "exp(-1)"),
        ("log", 0x3FF0000000000001, "log(1+2^-52)"),
        ("sqrt", 0x4000000000000000, "sqrt(2)"),
        ("sin", 0x3FE921FB54442D18, "sin(pi/4) as double"),
        ("cos", 0x3FE921FB54442D18, "cos(pi/4) as double"),
        ("recip", 0x3FEFFFFFFFFFFFFF, "1/(1-2^-53)"),
        ("recip", 0x3FF0000000000001, "1/(1+2^-52)"),
    ]
    for func, b, desc in classics:
        add("01_published", func, b, "f64", "f64", desc)


def gen_midpoint_hard(func, in_fmt, out_fmt, n, seed, exp_range, cat):
    """Solve f(x)=midpoint and test the two bracketing input floats."""
    rng = random.Random(seed)
    made = 0
    attempts = 0
    while made < n and attempts < n * 60:
        attempts += 1
        yb = rand_bits(out_fmt, rng, exp_range[0], exp_range[1],
                       sign=0 if func in ("exp", "sqrt") else None)
        m = O.midpoint_after(yb, out_fmt)
        if m <= 0:
            continue
        with mp.workprec(260 + max(0, mp.mag(m))):
            xs = real_inverse(func, m)
        if xs is None or xs <= 0 or not mp.isfinite(xs):
            continue
        # skip inputs outside the input format's normal range
        try:
            lo, hi = O.floor_and_ceil_float(xs, in_fmt)
        except Exception:
            continue
        for xb in (lo, hi):
            if made >= n:
                break
            if not (0 < xb < ((1 << O.FMT[in_fmt][0]) - 1)):
                continue
            xv = O.bits_to_mpf(xb, in_fmt)
            if xv <= 0 or not mp.isfinite(xv):
                continue
            add(cat, func, xb, in_fmt, out_fmt,
                "%s: exact image nearest f%g midpoint 0x%x" % (func, O.FMT[out_fmt][0], yb))
            made += 1


def gen_double_round_targeted(func, in_fmt, out_fmt, n, seed, exp_range, cat):
    """Construct inputs where round_f64(f(x)) lands exactly on an out_fmt
    midpoint so ucas's double rounding differs from the direct rounding."""
    rng = random.Random(seed)
    made = 0
    attempts = 0
    while made < n and attempts < n * 120:
        attempts += 1
        yb = rand_bits(out_fmt, rng, exp_range[0], exp_range[1], sign=0)
        m = O.midpoint_after(yb, out_fmt)   # exact, representable in double
        u64 = O.round_mpf_bits(m, "f64")
        ulp64 = O.ulp_at_mpf(m)
        target = m - ulp64 / 4
        if target <= 0:
            continue
        with mp.workprec(260 + max(0, mp.mag(m))):
            xs = real_inverse(func, target)
        if xs is None or xs <= 0 or not mp.isfinite(xs):
            continue
        try:
            lo, hi = O.floor_and_ceil_float(xs, in_fmt)
        except Exception:
            continue
        for k in range(-2, 3):
            xb = lo + k
            if xb <= 0 or xb >= ((1 << O.FMT[in_fmt][0]) - 1):
                continue
            # does round-to-double of f(x) land exactly on the midpoint m?
            try:
                if O.oracle_bits(func, xb, in_fmt, "f64") != u64:
                    continue
                direct = O.oracle_bits(func, xb, in_fmt, out_fmt)
                dbl = O.double_round_bits(func, xb, in_fmt, out_fmt)
            except (ValueError, ZeroDivisionError):
                continue
            if dbl != direct:
                add(cat, func, xb, in_fmt, out_fmt,
                    "DOUBLE-ROUND %s to f%g via f64 (mid 0x%x)" % (
                        func, O.FMT[out_fmt][0], yb))
                made += 1
                break
        if made >= n:
            break


def gen_halfway_casts(cat, seed):
    """Exact midpoints (ties) and their +-1-double-ulp neighbours, cast to
    f16 / f32; tests round-to-nearest-ties-to-even."""
    rng = random.Random(seed)
    for out_fmt in ("f16", "f32"):
        for _ in range(24):
            yb = rand_bits(out_fmt, rng, sign=rng.randint(0, 1))
            m = O.midpoint_after(yb, out_fmt)
            mbits = O.round_mpf_bits(m, "f64")
            # direct cast of exact midpoint: ties-to-even
            expbits = O.round_mpf_bits(O.bits_to_mpf(mbits, "f64"), out_fmt)
            dblbits = expbits  # input is exact double -> single rounding
            CASES.append(dict(cat=cat, func="cast", xbits=mbits, in_fmt="f64",
                              out_fmt=out_fmt,
                              desc="tie midpoint between 0x%x and 0x%x -> f%g" % (
                                  yb, yb + 1, O.FMT[out_fmt][0]),
                              oracle=expbits, double=dblbits,
                              expr="show asuint(f%s(asfloat(u64(0x%016x))))" % (
                                  out_fmt[1:], mbits)))
            # neighbours just below / above the midpoint
            for delta in (-1, 1):
                nb = mbits + delta
                nb &= (1 << 64) - 1
                v = O.bits_to_mpf(nb, "f64")
                ebits = O.round_mpf_bits(v, out_fmt)
                CASES.append(dict(cat=cat, func="cast", xbits=nb, in_fmt="f64",
                                  out_fmt=out_fmt,
                                  desc="midpoint neighbour %+d of 0x%x -> f%g" % (
                                      delta, yb, O.FMT[out_fmt][0]),
                                  oracle=ebits, double=ebits,
                                  expr="show asuint(f%s(asfloat(u64(0x%016x))))" % (
                                      out_fmt[1:], nb)))


def gen_subnormal_boundary(cat):
    """Subnormal / normal boundaries and flush-to-zero boundaries."""
    cases = []
    # f16 boundaries, fed to sqrt / recip and casts
    f16_special = [0x0001, 0x0002, 0x03FF, 0x0400, 0x0401, 0x7BFF, 0x7C00]
    for b in f16_special:
        for func in ("sqrt", "recip"):
            cases.append((func, b, "f16", "f16"))
        # cast f16 -> f64 and back through f32
    # f32 boundaries
    f32_special = [0x00000001, 0x00000002, 0x007FFFFF, 0x00800000, 0x00800001,
                   0x7F7FFFFF, 0x7F800000, 0x80000001, 0x807FFFFF, 0x80800000]
    for b in f32_special:
        for func in ("sqrt", "recip"):
            cases.append((func, b, "f32", "f32"))
    # f64 boundaries -> f32/f16 (rounding across subnormal/normal)
    f64_special = [
        0x0000000000000001, 0x0000000000000002, 0x000FFFFFFFFFFFFF,
        0x0010000000000000, 0x0010000000000001, 0x7FEFFFFFFFFFFFFF,
        0x8000000000000001, 0x800FFFFFFFFFFFFF, 0x8010000000000000,
    ]
    for b in f64_special:
        cases.append(("cast", b, "f64", "f32"))
        cases.append(("cast", b, "f64", "f16"))
    for func, b, infmt, outfmt in cases:
        if func == "cast":
            v = O.bits_to_mpf(b, infmt)
            eb = O.round_mpf_bits(v, outfmt)
            CASES.append(dict(cat=cat, func="cast", xbits=b, in_fmt=infmt,
                              out_fmt=outfmt,
                              desc="subnormal/normal boundary 0x%x f%g->f%g" % (
                                  b, O.FMT[infmt][0], O.FMT[outfmt][0]),
                              oracle=eb, double=eb,
                              expr="show asuint(f%s(asfloat(u%d(0x%0*x))))" % (
                                  outfmt[1:], O.FMT[infmt][0],
                                  O.FMT[infmt][0] // 4, b)))
        else:
            add(cat, func, b, infmt, outfmt,
                "subnormal/normal boundary 0x%x f%g" % (b, O.FMT[infmt][0]))


def gen_random_large_sin_cos(cat, seed, n=30):
    """Random large-magnitude doubles: argument reduction stress for sin/cos."""
    rng = random.Random(seed)
    # the confirmed 1-ulp glibc sin error found during exploration
    add(cat, "sin", 0x4a77814ea6142e5b, "f64", "f64",
        "confirmed 1-ulp libm sin error at large argument 0x4a77814ea6142e5b")
    for func in ("sin", "cos"):
        for _ in range(n):
            # exponents 2^112 .. 2^192; oracle uses 200+mag bits for reduction
            b = rand_bits("f64", rng, 0x46f, 0x4c0)
            add(cat, func, b, "f64", "f64",
                "large-argument %s(0x%x)" % (func, b))


# ---------------------------------------------------------------------------
# build all cases
# ---------------------------------------------------------------------------
def build_cases():
    CASES.clear()
    gen_published()

    # f64 midpoint-hard cases, all six functions
    f64_exp = (0x3F0, 0x402)   # ~2^-15 .. 2^2 outputs
    f64_log = (0x3C0, 0x402)   # outputs across ~2^-60..2^2
    f64_sincos = (0x3F0, 0x3FF)  # outputs in (0,1)
    for i, f in enumerate(FUNCS):
        rng = (f64_sincos if f in ("sin", "cos") else f64_log if f == "log" else f64_exp)
        gen_midpoint_hard(f, "f64", "f64", 8, 1000 + i, rng,
                          "02_f64_midpoint")

    # f32 midpoint-hard cases (double rounding possible)
    for i, f in enumerate(FUNCS):
        rng32 = (0x70, 0x81) if f in ("sin", "cos") else (0x70, 0x84)
        f32_logrng = (0x40, 0x84)
        rr = f32_logrng if f == "log" else rng32
        gen_midpoint_hard(f, "f32", "f32", 6, 2000 + i, rr,
                          "03_f32_midpoint")

    # f16 midpoint-hard cases
    for i, f in enumerate(FUNCS):
        rr = (0x04, 0x0F) if f in ("sin", "cos") else (0x04, 0x0E)
        gen_midpoint_hard(f, "f16", "f16", 3, 3000 + i, rr,
                          "04_f16_midpoint")

    # targeted double rounding via f64 -> f32 and f64 -> f16
    for i, f in enumerate(FUNCS):
        gen_double_round_targeted(f, "f64", "f32", 4, 4000 + i,
                                  (0x70, 0x82), "05_f64_to_f32_dr")
    for i, f in enumerate(("exp", "log", "sqrt")):
        gen_double_round_targeted(f, "f64", "f16", 3, 4200 + i,
                                  (0x08, 0x0E), "06_f64_to_f16_dr")

    gen_halfway_casts("07_halfway", 5000)
    gen_subnormal_boundary("08_subnormal")
    gen_random_large_sin_cos("09_large_sincos", 6000, 35)
    return CASES


# ---------------------------------------------------------------------------
# emit .ucas golden files (<=18 statements each)
# ---------------------------------------------------------------------------
def write_files(cases):
    # group by category, then chunk
    groups = {}
    for c in cases:
        groups.setdefault(c["cat"], []).append(c)
    filemap = {}
    for cat in sorted(groups):
        chunk = groups[cat]
        for ci in range(0, len(chunk), 18):
            part = chunk[ci:ci + 18]
            idx = ci // 18 + 1
            name = "%s_%02d.ucas" % (cat, idx)
            with open(os.path.join(HERE, name), "w") as fh:
                for c in part:
                    fh.write(c["expr"] + "\n")
            for c in part:
                c["file"] = name
            filemap[name] = part
    return filemap


def parse_output(text):
    """Extract integer result values from ucas `show asuint(...)` output."""
    vals = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("_() = "):
            try:
                vals.append(int(line[6:].split()[0]))
            except ValueError:
                vals.append(None)
    return vals


def run_and_compare(filemap):
    total = mism = uneval = 0
    report = []
    for name in sorted(filemap):
        part = filemap[name]
        path = os.path.join(HERE, name)
        try:
            p = subprocess.run([UCAS, path], capture_output=True, text=True,
                               timeout=20, cwd=HERE)
        except subprocess.TimeoutExpired:
            report.append("%s: TIMEOUT" % name)
            for c in part:
                c["ucas"] = None
            continue
        vals = parse_output(p.stdout)
        for i, c in enumerate(part):
            total += 1
            got = vals[i] if i < len(vals) else None
            c["ucas"] = got
            if got is None:
                # ucas returned an unevaluated expression (e.g. asuint on a
                # division that overflowed to inf); not a numeric comparison
                uneval += 1
                mm = "UNEVAL"
            else:
                mm = "MATCH" if got == c["oracle"] else "MISMATCH"
                if got != c["oracle"]:
                    mism += 1
            ulp = ""
            if got is not None and c["oracle"] is not None:
                d = got - c["oracle"]
                if d:
                    ulp = " (delta=%d)" % d
            report.append("%-14s %-6s %-6s %-4s got=%s oracle=%s%s :: %s" % (
                name, mm, c["func"], c["out_fmt"],
                hex(got) if got is not None else "--",
                hex(c["oracle"]), ulp, c["desc"]))
    return total, mism, uneval, report


def main():
    cases = build_cases()
    with open(os.path.join(HERE, "cases.json"), "w") as fh:
        json.dump(cases, fh, indent=1)
    filemap = write_files(cases)
    print("generated %d cases in %d .ucas files" % (len(cases), len(filemap)))
    if "--no-run" in sys.argv:
        return
    total, mism, uneval, report = run_and_compare(filemap)
    with open(os.path.join(HERE, "cases.json"), "w") as fh:
        json.dump(cases, fh, indent=1)
    with open(os.path.join(HERE, "gen_report.txt"), "w") as fh:
        fh.write("\n".join(report) + "\n")
    print("compared %d cases: %d MATCH, %d MISMATCH, %d UNEVAL" % (
        total, total - mism - uneval, mism, uneval))
    # breakdown by category
    bycat = {}
    for c in cases:
        if c.get("ucas") != c.get("oracle"):
            bycat.setdefault(c["cat"], []).append(c)
    for cat in sorted(bycat):
        print("  %s: %d mismatches" % (cat, len(bycat[cat])))
        for c in bycat[cat][:6]:
            print("     %s(%s->%s) got=%s oracle=%s : %s" % (
                c["func"], c["in_fmt"], c["out_fmt"],
                hex(c["ucas"]) if c["ucas"] is not None else "--",
                hex(c["oracle"]), c["desc"]))


if __name__ == "__main__":
    main()
