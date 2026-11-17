#!/usr/bin/env python3
"""Exhaustive bit-pattern float testing of ucas unary ops vs an exact oracle.

- f16: ALL 65536 bit patterns enumerated via `table` (ucas evaluates the whole
  u16 domain in one process, ~0.13 s per op).
- f32: strided 2^32 space plus dense special regions (zero, subnormals,
  min/max normal, inf, NaNs, powers of two), evaluated via batched explicit
  calls with a robust multi-line parser.

Oracle: input bit patterns are decoded to exact rational values; transcendental
results are computed with mpmath at 200-bit precision; every result is rounded
to nearest IEEE (ties to even) with exact integer arithmetic.  This is an
independent reference, not ucas's own arithmetic.

Run:  python3 exhaustive.py            (full sweeps, prints report)
      python3 exhaustive.py --quick    (small f32 sample)
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
import argparse
import os
import re
import struct
import subprocess
import sys
from fractions import Fraction

import mpmath as mp

mp.mp.prec = 200

UCAS = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))

FMTS = {
    "f16": dict(sig=16, expbits=5, fracbits=10, bias=15, emin=-14, emax=15),
    "f32": dict(sig=32, expbits=8, fracbits=23, bias=127, emin=-126, emax=127),
}


# ---------------------------------------------------------------------------
# Exact IEEE decoding / rounding (independent oracle)
# ---------------------------------------------------------------------------
def decode(bits, fmt):
    """Return (kind, sign, value) where kind in {zero, sub, norm, inf, nan}."""
    f = FMTS[fmt]
    eb, fb = f["expbits"], f["fracbits"]
    sign = bits >> (eb + fb)
    e = (bits >> fb) & ((1 << eb) - 1)
    m = bits & ((1 << fb) - 1)
    if e == (1 << eb) - 1:
        return ("nan" if m else "inf", sign, m)
    if e == 0:
        if m == 0:
            return ("zero", sign, Fraction(0))
        v = Fraction(m) * Fraction(2) ** (f["emin"] - fb)
        return ("sub", sign, v)
    v = Fraction((1 << fb) + m) * Fraction(2) ** (e - f["bias"] - fb)
    return ("norm", sign, v)


def _round_half_even(q):
    """Nearest integer to Fraction q, ties to even."""
    n = q.numerator // q.denominator
    rem = q - n
    if rem > Fraction(1, 2):
        return n + 1
    if rem < Fraction(1, 2):
        return n
    return n if n % 2 == 0 else n + 1


def _round_shift(M, d):
    """Nearest integer to M * 2**d (M>=0, d int, small), ties to even."""
    if d >= 0:
        return M << d
    if d < -(M.bit_length() + 1):
        return 0  # far below half the quantum
    s = -d
    q = M >> s
    r = M - (q << s)
    half = 1 << (s - 1)
    if r > half or (r == half and (q & 1)):
        q += 1
    return q


def round_man_exp(sign, man, exp, fmt):
    """Round sign * man * 2**exp (man>=0 int) to nearest IEEE fmt bits, even ties.

    Works purely with integer mantissa/exponent, so it handles the enormous
    exponents of exp(large f32) without allocating giant Fractions.
    """
    f = FMTS[fmt]
    eb, fb, bias, emin, emax = f["expbits"], f["fracbits"], f["bias"], f["emin"], f["emax"]
    sbits = sign << (eb + fb)
    if man == 0:
        return sbits
    e = man.bit_length() - 1 + exp  # floor(log2 magnitude)
    if e < emin:
        n = _round_shift(man, exp - (emin - fb))
        if n == 0:
            return sbits
        if n < (1 << fb):
            return sbits | n
        return sbits | (1 << fb)  # carried into smallest normal
    n = _round_shift(man, exp - (e - fb))
    if n >= (1 << (fb + 1)):
        n >>= 1
        e += 1
    if e > emax:
        return sbits | (((1 << eb) - 1) << fb)
    return sbits | ((e + bias) << fb) | (n - (1 << fb))


def round_to_bits(v, fmt):
    """Round exact Fraction v (signed, dyadic) to nearest IEEE fmt bits."""
    if v == 0:
        return 0  # caller handles sign of zero
    sign = 1 if v < 0 else 0
    num, den = abs(v.numerator), v.denominator
    assert den & (den - 1) == 0, "non-dyadic Fraction"  # den is a power of two
    exp = -(den.bit_length() - 1)
    return round_man_exp(sign, num, exp, fmt)


def round_fraction(v, fmt):
    """Round arbitrary exact Fraction v to nearest IEEE fmt bits (ties even)."""
    f = FMTS[fmt]
    eb, fb, bias, emin, emax = f["expbits"], f["fracbits"], f["bias"], f["emin"], f["emax"]
    if v == 0:
        return 0
    sign = 1 if v < 0 else 0
    a = abs(v)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    while Fraction(2) ** (e + 1) <= a:
        e += 1
    k = max(e, emin) - fb
    n = _round_half_even(a / Fraction(2) ** k)
    if n == 0:
        return sign << (eb + fb)
    if n >= (1 << (fb + 1)):
        n >>= 1
        e += 1
    if e > emax:
        return (sign << (eb + fb)) | (((1 << eb) - 1) << fb)
    if e < emin:  # subnormal (n already in quantum units)
        return (sign << (eb + fb)) | n
    return (sign << (eb + fb)) | ((e + bias) << fb) | (n - (1 << fb))


def quiet_nan(fmt, sign=0):
    f = FMTS[fmt]
    return (sign << (f["expbits"] + f["fracbits"])) | (((1 << f["expbits"]) - 1) << f["fracbits"]) | (1 << (f["fracbits"] - 1))


def is_nan(bits, fmt):
    f = FMTS[fmt]
    e = (bits >> f["fracbits"]) & ((1 << f["expbits"]) - 1)
    m = bits & ((1 << f["fracbits"]) - 1)
    return e == (1 << f["expbits"]) - 1 and m != 0


def mp_of(bits, fmt):
    """Exact mpmath value of a finite input bit pattern."""
    kind, sign, v = decode(bits, fmt)
    assert kind in ("zero", "sub", "norm"), (bits, kind)
    x = mp.mpf(v.numerator) / mp.mpf(v.denominator)
    return -x if sign else x


def mp_to_bits(x, fmt):
    if not x:  # exact zero (signed zero handled by caller)
        return 0
    man, exp = mp.libmp.to_man_exp(x._mpf_)
    sign = 1 if x._mpf_[0] else 0
    return round_man_exp(sign, man, exp, fmt)


# ---------------------------------------------------------------------------
# Oracles: return ('bits', int) for a definite bit pattern, or ('nan', None)
# meaning "any quiet NaN is acceptable".
# ---------------------------------------------------------------------------
def _nan_for_input(bits, fmt):
    """Quiet a NaN input the IEEE way (set mantissa MSB, keep payload/sign)."""
    f = FMTS[fmt]
    return bits | (1 << (f["fracbits"] - 1))


def oracle(op, bits, fmt):
    kind, sign, v = decode(bits, fmt)
    sbit = sign << (FMTS[fmt]["expbits"] + FMTS[fmt]["fracbits"])

    if op == "abs":
        # abs clears the sign bit for every class, NaN included.
        f = FMTS[fmt]
        return ("bits", bits & ((1 << (f["expbits"] + f["fracbits"])) - 1))

    if op in ("floor", "ceil", "roundeven"):
        if kind in ("inf", "nan"):
            return ("nan", None) if kind == "nan" else ("bits", bits)
        if kind == "zero":
            return ("bits", bits)  # preserve signed zero
        x = -v if sign else v  # v is magnitude; apply sign
        if op == "floor":
            iv = x.numerator // x.denominator
        elif op == "ceil":
            iv = -((-x.numerator) // x.denominator)
        else:
            iv = _round_half_even(x)
        if iv == 0:
            return ("bits", sbit)  # signed zero with sign of x
        return ("bits", round_to_bits(Fraction(iv), fmt))

    if op == "sqrt":
        if kind == "zero":
            return ("bits", bits)  # sqrt(-0) = -0
        if kind == "nan":
            return ("bits", _nan_for_input(bits, fmt))
        if kind == "inf":
            return ("bits", bits) if sign == 0 else ("nan", None)
        if sign:
            return ("nan", None)
        return ("bits", mp_to_bits(mp.sqrt(mp_of(bits, fmt)), fmt))

    if op == "log":
        if kind == "nan":
            return ("bits", _nan_for_input(bits, fmt))
        if kind == "zero":
            # log(+-0) = -inf
            f = FMTS[fmt]
            return ("bits", (1 << (f["expbits"] + f["fracbits"])) | (((1 << f["expbits"]) - 1) << f["fracbits"]))
        if kind == "inf":
            return ("bits", bits) if sign == 0 else ("nan", None)
        if sign:
            return ("nan", None)
        return ("bits", mp_to_bits(mp.log(mp_of(bits, fmt)), fmt))

    if op == "exp":
        if kind == "nan":
            return ("bits", _nan_for_input(bits, fmt))
        if kind == "inf":
            return ("bits", bits) if sign == 0 else ("bits", 0)  # exp(-inf)=+0
        return ("bits", mp_to_bits(mp.exp(mp_of(bits, fmt)), fmt))

    if op == "sin":
        if kind == "nan" or kind == "inf":
            return ("nan", None)
        if kind == "zero":
            return ("bits", bits)  # sin(-0) = -0
        return ("bits", mp_to_bits(mp.sin(mp_of(bits, fmt)), fmt))

    raise ValueError(op)


# ---------------------------------------------------------------------------
# ucas querying
# ---------------------------------------------------------------------------
def run_ucas(source, timeout=120):
    p = subprocess.run([UCAS], input=source, capture_output=True, text=True, timeout=timeout, cwd=HERE)
    return p.stdout + ("\n[STDERR]\n" + p.stderr if p.stderr else "")


def query_table_func(funcname, defs, n):
    """Evaluate a defined function over bits 0..n-1 via ucas `table`."""
    lines = list(defs) + [f"table {funcname} max {n}"]
    out = run_ucas("\n".join(lines) + "\n", timeout=180)
    res = {}
    pat = re.compile(r"^\s*x=(\d+)\s*->\s*(\d+)\s*$")
    for line in out.splitlines():
        m = pat.match(line)
        if m:
            res[int(m.group(1))] = int(m.group(2))
    return res


def query_calls_func(funcname, defs, patterns, timeout=180):
    """Evaluate a defined function at explicit bit patterns -> bits|'SYMBOLIC'."""
    lines = list(defs)
    hexes = [hex(b) for b in patterns]
    for i in range(0, len(hexes), 8):
        lines.append("; ".join(f"{funcname}({h})" for h in hexes[i:i + 8]))
    out = run_ucas("\n".join(lines) + "\n", timeout=timeout)
    olines = out.splitlines()
    res = {}
    i = 0
    for b in patterns:
        if i >= len(olines):
            res[b] = "SYMBOLIC"
            continue
        line = olines[i].strip()
        if re.fullmatch(r"\d+", line):
            res[b] = int(line)
            i += 1
        elif line.startswith("_() ="):
            i += 1
            while i < len(olines) and not olines[i].strip().startswith("->"):
                i += 1
            i += 1
            res[b] = "SYMBOLIC"
        else:
            i += 1
            res[b] = "SYMBOLIC"
    return res


def query_table(op, fmt, n):
    ut = f"u{fmt[1:]}"
    return query_table_func("F", [f"pp(x: {ut}) = asfloat(x)",
                                  f"F(x: {ut}) = asuint({op}(pp(x)))"], n)


def query_calls(op, fmt, patterns, timeout=180):
    ut = f"u{fmt[1:]}"
    return query_calls_func("F", [f"pp(x: {ut}) = asfloat(x)",
                                  f"F(x: {ut}) = asuint({op}(pp(x)))"], patterns, timeout)


def classify(expected, got, fmt):
    """Return 'OK' | 'NANPAYLOAD' | 'WRONG'."""
    ekind, eval_ = expected
    if got == "SYMBOLIC":
        return "WRONG" if ekind == "bits" else "OK"
    if ekind == "nan":
        return "OK" if is_nan(got, fmt) else "WRONG"
    if eval_ == got:
        return "OK"
    if is_nan(eval_, fmt) and is_nan(got, fmt):
        return "NANPAYLOAD"
    return "WRONG"


# ---------------------------------------------------------------------------
# Pattern sets for f32
# ---------------------------------------------------------------------------
def f32_patterns(quick=False):
    p = set()
    # stride the whole 2^32 space
    step = 1 << 21 if quick else 1 << 17
    p.update(range(0, 1 << 32, step))
    # special regions, dense
    specials = [
        0, 1, 2, 3, 0x007FFFFF,                       # +zero, tiny subnormals, max subnormal
        0x00800000, 0x00800001, 0x00FFFFFF,           # min normal, min normal+1, 
        0x3F800000, 0x3F7FFFFF, 0x3F800001,           # 1.0, below/above 1
        0x7F7FFFFF, 0x7F800000, 0x7F800001, 0x7FC00000, 0x7FFFFFFF,  # max norm, inf, sNaN, qNaN, all-ones
        0x80000000, 0x80000001, 0x807FFFFF,           # -zero, -tiny, -max subnormal
        0x80800000, 0x80800001, 0x80FFFFFF,           # -min normal...
        0xBF800000, 0xBF7FFFFF, 0xBF800001,           # -1.0
        0xFF7FFFFF, 0xFF800000, 0xFF800001, 0xFFC00000, 0xFFFFFFFF,  # -max norm, -inf, NaNs
        0x40000000, 0x3F000000, 0x3F800001,           # 2.0, 0.5
        0x00000010, 0x00000100, 0x00010000,           # assorted subnormals
    ]
    p.update(specials)
    # neighbourhoods around key values
    for center in [0x3F800000, 0x00800000, 0x7F7FFFFF, 0x7F800000, 0x7FC00000,
                   0x00000000, 0x80000000, 0x40000000]:
        for d in range(-8, 9):
            v = (center + d) & 0xFFFFFFFF
            p.add(v)
    # powers of two across the whole exponent range
    for e in range(256):
        p.add((e << 23) & 0xFFFFFFFF)
        p.add(((e << 23) | 0x80000000) & 0xFFFFFFFF)
    return sorted(p)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
ALL_OPS = ["abs", "sqrt", "log", "exp", "sin", "floor", "ceil", "roundeven"]


def sweep_f16(ops):
    print("=== f16 exhaustive sweep (all 65536 bit patterns per op) ===")
    total = wrong = nanpay = ok = 0
    examples = {}
    for op in ops:
        got_map = query_table(op, "f16", 65536)
        wrongs, pays = [], []
        for b in range(65536):
            exp = oracle(op, b, "f16")
            got = got_map.get(b, "SYMBOLIC")
            c = classify(exp, got, "f16")
            if c == "WRONG":
                wrongs.append((b, exp, got))
            elif c == "NANPAYLOAD":
                pays.append((b, exp, got))
        examples[op] = (wrongs, pays)
        print(f"  {op:10s}: wrong={len(wrongs):5d}  nanpayload={len(pays):5d}  evaluated={len(got_map)}")
        wrong += len(wrongs); nanpay += len(pays); ok += 65536 - len(wrongs) - len(pays)
        total += 65536
    print(f"  TOTAL f16: {total} comparisons, wrong={wrong}, nanpayload={nanpay}\n")
    return examples


def report_examples(op, items, fmt, limit=6):
    ut = f"u{fmt[1:]}"
    f = FMTS[fmt]
    mask = (1 << (f["expbits"] + f["fracbits"])) - 1
    for b, exp, got in items[:limit]:
        kind, sign, v = decode(b, fmt)
        print(f"    bits=0x{b:0{f['sig']//4}X} ({kind}, sign={sign}) "
              f"expected={exp[0]}:" + (f"{exp[1]:#x}" if exp[1] is not None else "NaN") +
              f"  got=" + ("SYMBOLIC" if got == "SYMBOLIC" else f"{got:#x}"))


def sweep_f32(ops, patterns):
    print(f"=== f32 sampled sweep ({len(patterns)} bit patterns per op) ===")
    total = wrong = nanpay = ok = 0
    examples = {}
    for op in ops:
        got_map = query_calls(op, "f32", patterns)
        wrongs, pays = [], []
        for b in patterns:
            exp = oracle(op, b, "f32")
            got = got_map.get(b, "SYMBOLIC")
            c = classify(exp, got, "f32")
            if c == "WRONG":
                wrongs.append((b, exp, got))
            elif c == "NANPAYLOAD":
                pays.append((b, exp, got))
        examples[op] = (wrongs, pays)
        print(f"  {op:10s}: wrong={len(wrongs):5d}  nanpayload={len(pays):5d}")
        wrong += len(wrongs); nanpay += len(pays); ok += len(patterns) - len(wrongs) - len(pays)
        total += len(patterns)
    print(f"  TOTAL f32: {total} comparisons, wrong={wrong}, nanpayload={nanpay}\n")
    return examples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--ops", default=",".join(ALL_OPS))
    args = ap.parse_args()
    ops = [o for o in args.ops.split(",") if o]
    ex16 = sweep_f16(ops)
    ex32 = sweep_f32(ops, f32_patterns(quick=args.quick))
    print("=== First counterexamples (f16) ===")
    for op in ops:
        w, p = ex16[op]
        if w:
            print(f"  {op} WRONG ({len(w)}):")
            report_examples(op, w, "f16")
        if p:
            print(f"  {op} NANPAYLOAD ({len(p)}):")
            report_examples(op, p, "f16")
    print("\n=== First counterexamples (f32) ===")
    for op in ops:
        w, p = ex32[op]
        if w:
            print(f"  {op} WRONG ({len(w)}):")
            report_examples(op, w, "f32")
        if p:
            print(f"  {op} NANPAYLOAD ({len(p)}):")
            report_examples(op, p, "f32")


if __name__ == "__main__":
    main()
