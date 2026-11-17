"""
High-precision oracle + IEEE-754 rounding helpers for the worst_case_rounding
stress area.

The oracle computes the exact image of an elementary function at an *exact*
floating-point input using mpmath (200+ bits), then rounds that image to the
target IEEE binary16/32/64 format with round-to-nearest, ties-to-even,
including subnormals.  It returns the exact bit pattern of the rounded result
so it can be compared byte-for-byte with ucas's `show asuint(EXPR)` output.

ucas's evaluator (src/eval.c scalar_float) computes:
  f64: the host libm double function directly, no re-rounding
  f32: fround(32, libm_double_result) == (float)(double result) -> DOUBLE ROUNDING
  f16: fround(16, libm_double_result)                         -> DOUBLE ROUNDING
so any mismatch against this oracle is a genuine correctness gap (libm not
correctly rounded, a double-rounding error, or a bad tie-to-even).
"""

import mpmath as mp

mp.mp.prec = 200

# (total width w, significand bits p including implicit, exponent bias, emax)
FMT = {
    "f16": (16, 11, 15, 15),
    "f32": (32, 24, 127, 127),
    "f64": (64, 53, 1023, 1023),
}


def bits_to_mpf(bits, fmt):
    """Exact value of an IEEE bit pattern (finite values only)."""
    w, p, bias, emax = FMT[fmt]
    sign = -1 if (bits >> (w - 1)) & 1 else 1
    expf = (bits >> (p - 1)) & ((1 << (w - p)) - 1)
    frac = bits & ((1 << (p - 1)) - 1)
    if expf == (1 << (w - p)) - 1:      # inf or nan
        return sign * mp.inf if frac == 0 else mp.nan
    if expf == 0:                       # subnormal or zero
        val = mp.mpf(frac) * mp.mpf(2) ** (1 - bias - (p - 1))
    else:                               # normal
        val = mp.mpf((1 << (p - 1)) | frac) * mp.mpf(2) ** (expf - bias - (p - 1))
    return sign * val


def mpf_to_manexp(x):
    """Return (sign, man, exp) with x = (-1)^sign * man * 2^exp, man integer>0."""
    sign, man, exp, bc = x._mpf_
    return sign, man, exp


def round_bits_from_manexp(sign, man, exp, fmt):
    """Round (-1)^sign * man * 2^exp to an IEEE format, return bit pattern.

    Round-to-nearest, ties-to-even, with subnormals and overflow to inf.
    """
    if man == 0:
        return (sign << (FMT[fmt][0] - 1))
    w, p, bias, emax = FMT[fmt]
    emin = 1 - bias
    E = exp + man.bit_length() - 1        # floor(log2 value)
    maxexpfield = (1 << (w - p)) - 1
    if E > emax:                          # overflow to infinity
        return (sign << (w - 1)) | (maxexpfield << (p - 1))
    if E < emin - p:                      # far below half the min subnormal -> 0
        return (sign << (w - 1))
    ulp_exp = (E - (p - 1)) if E >= emin else (emin - (p - 1))
    shift = exp - ulp_exp
    if shift >= 0:
        q = man << shift
    else:
        sh = -shift
        q = man >> sh
        rem = man - (q << sh)
        half = 1 << (sh - 1)
        if rem > half or (rem == half and (q & 1)):
            q += 1
    if E >= emin:
        if q >= (1 << p):
            q >>= 1
            E += 1
        biased = E + bias
        if biased >= maxexpfield:         # exponent field all ones -> inf
            return (sign << (w - 1)) | (maxexpfield << (p - 1))
        frac = q - (1 << (p - 1))
        return (sign << (w - 1)) | (biased << (p - 1)) | frac
    else:
        frac = q & ((1 << (p - 1)) - 1)
        if q >= (1 << (p - 1)):           # carried into smallest normal
            return (sign << (w - 1)) | (1 << (p - 1))
        return (sign << (w - 1)) | frac


def round_mpf_bits(x, fmt):
    s, m, e = mpf_to_manexp(x)
    return round_bits_from_manexp(s, m, e, fmt)


def _exact_image(func, x):
    if func == "exp":
        return mp.exp(x)
    if func == "log":
        return mp.log(x)
    if func == "sqrt":
        return mp.sqrt(x)
    if func == "sin":
        return mp.sin(x)
    if func == "cos":
        return mp.cos(x)
    if func == "recip":
        return 1 / x
    raise ValueError(func)


def _with_prec_for(x, func):
    """Context manager giving enough bits for argument reduction of sin/cos."""
    mag = mp.mag(x) if x != 0 else 0
    extra = max(0, mag) if func in ("sin", "cos") else 0
    return mp.workprec(mp.mp.prec + extra)


def special_image(func, x):
    """Result for non-finite inputs, or None if the ordinary path applies."""
    if mp.isnan(x):
        return mp.nan
    if mp.isinf(x):
        if func == "exp":
            return mp.inf if x > 0 else mp.mpf(0)
        if func in ("log", "sqrt"):
            return mp.inf if x > 0 else mp.nan
        if func in ("sin", "cos"):
            return mp.nan
        if func == "recip":
            return mp.mpf(0) * (1 if x > 0 else -1)
    return None


def inf_nan_bits(y, fmt):
    """Bit pattern for an infinite or NaN result, or None for finite values."""
    w, p, bias, emax = FMT[fmt]
    maxexp = (1 << (w - p)) - 1
    if mp.isnan(y):
        # canonical quiet NaN; payload is not compared meaningfully
        return (maxexp << (p - 1)) | (1 << (p - 2))
    if mp.isinf(y):
        return ((1 if y < 0 else 0) << (w - 1)) | (maxexp << (p - 1))
    return None


def oracle_bits(func, x_bits, in_fmt, out_fmt):
    """Directly round f(exact x) to out_fmt (the correctly-rounded answer)."""
    x = bits_to_mpf(x_bits, in_fmt)
    sp = special_image(func, x)
    if sp is not None:
        b = inf_nan_bits(sp, out_fmt)
        if b is not None:
            return b
        # finite result (e.g. exp(-inf)=0, recip(inf)=0)
        sp = mp.mpf(sp)
        return round_mpf_bits(sp, out_fmt) if sp != 0 else 0
    with _with_prec_for(x, func):
        y = _exact_image(func, x)
        if y == 0:
            s = 0
            if func in ("recip", "sin") and x < 0:
                s = 1
            return s << (FMT[out_fmt][0] - 1)
        return round_mpf_bits(y, out_fmt)


def double_round_bits(func, x_bits, in_fmt, out_fmt):
    """Model ucas: round the exact image to f64 first, then to out_fmt."""
    x = bits_to_mpf(x_bits, in_fmt)
    sp = special_image(func, x)
    if sp is not None:
        return oracle_bits(func, x_bits, in_fmt, out_fmt)
    with _with_prec_for(x, func):
        y = _exact_image(func, x)
        if y == 0:
            return 0
        d = round_mpf_bits(y, "f64")
        dy = bits_to_mpf(d, "f64")
        return round_mpf_bits(dy, out_fmt)


def image_mpf(func, x_bits, in_fmt):
    """The high-precision exact image, for analysis (nearest midpoint etc.)."""
    x = bits_to_mpf(x_bits, in_fmt)
    with _with_prec_for(x, func):
        return _exact_image(func, x)


# --------------------------------------------------------------------------
# helpers for building adversarial cases
# --------------------------------------------------------------------------
def midpoint_after(bits, fmt):
    """Exact midpoint between the float `bits` and the next float up."""
    v = bits_to_mpf(bits, fmt)
    vn = bits_to_mpf(bits + 1, fmt)
    return (v + vn) / 2


def ulp_at_mpf(y):
    """Spacing of doubles around |y| as an mpf."""
    ay = abs(y)
    if ay == 0:
        return mp.mpf(2) ** -1074
    s, m, e = mpf_to_manexp(ay)
    E = e + m.bit_length() - 1
    return mp.mpf(2) ** (E - 52)


def floor_and_ceil_float(xstar, fmt):
    """Nearest floats below / above xstar as bit patterns (xstar>0)."""
    rb = round_mpf_bits(xstar, fmt)
    v = bits_to_mpf(rb, fmt)
    if v < xstar:
        return rb, rb + 1
    elif v > xstar:
        return rb - 1, rb
    else:
        return rb - 1, rb + 1


def f64_bits_from_hex(h):
    import struct
    return struct.unpack("<Q", struct.pack("<d", float.fromhex(h)))[0]


# --------------------------------------------------------------------------
# self-test: rounding must agree with Python's correctly-rounded mpf->float
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import struct
    import random
    random.seed(1)
    for _ in range(4000):
        man = random.getrandbits(200) | 1
        exp = random.randint(-1100, 1000)
        x = mp.mpf(man) * mp.mpf(2) ** exp
        if x == 0:
            continue
        mine = round_mpf_bits(x, "f64")
        try:
            ref = struct.unpack("<Q", struct.pack("<d", float(x)))[0]
        except OverflowError:
            continue
        if mine != ref:
            print("ROUND MISMATCH", mp.nstr(x, 10), hex(mine), hex(ref))
            raise SystemExit(1)
    print("oracle self-test OK (IEEE rounding agrees with Python float() on 4000 values)")
