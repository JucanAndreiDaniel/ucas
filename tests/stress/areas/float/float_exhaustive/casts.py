#!/usr/bin/env python3
"""Exhaustive f16<->f32 conversion checks against the exact oracle in exhaustive.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exhaustive as E


def oracle_cast(bits, src, dst, quiet_nan=True):
    kind, sign, v = E.decode(bits, src)
    f = E.FMTS[dst]
    sbit = sign << (f["expbits"] + f["fracbits"])
    if kind == "nan":
        return ("nan", None)  # payload/sign unspecified across formats; check NaN-ness
    if kind == "inf":
        return ("bits", sbit | (((1 << f["expbits"]) - 1) << f["fracbits"]))
    if kind == "zero":
        return ("bits", sbit)
    return ("bits", E.round_to_bits(-v if sign else v, dst))


def sweep_f16_to_f32():
    got = E.query_table_func("F", ["F(x: u16) = asuint(f32(asfloat(x)))"], 65536)
    wrong = pays = 0
    examples = []
    for b in range(65536):
        exp = oracle_cast(b, "f16", "f32")
        g = got.get(b, "SYMBOLIC")
        c = E.classify(exp, g, "f32")
        if c == "WRONG":
            wrong += 1
            if len(examples) < 12:
                examples.append((b, exp, g))
        elif c == "NANPAYLOAD":
            pays += 1
    print("=== f16 -> f32 exhaustive (65536) ===")
    print(f"  wrong={wrong} nanpayload={pays}")
    for b, exp, g in examples:
        print(f"    f16 bits=0x{b:04X} ({E.decode(b,'f16')[0]}) expected={exp} got={g}")
    return wrong, pays


def sweep_f32_to_f16(patterns):
    got = E.query_calls_func("F", ["F(x: u32) = asuint(f16(asfloat(x)))"], patterns)
    wrong = pays = 0
    examples = []
    for b in patterns:
        exp = oracle_cast(b, "f32", "f16")
        g = got.get(b, "SYMBOLIC")
        c = E.classify(exp, g, "f16")
        if c == "WRONG":
            wrong += 1
            if len(examples) < 12:
                examples.append((b, exp, g))
        elif c == "NANPAYLOAD":
            pays += 1
    print(f"=== f32 -> f16 sampled ({len(patterns)}) ===")
    print(f"  wrong={wrong} nanpayload={pays}")
    for b, exp, g in examples:
        print(f"    f32 bits=0x{b:08X} ({E.decode(b,'f32')[0]}) expected={exp} got={g}")
    return wrong, pays


if __name__ == "__main__":
    sweep_f16_to_f32()
    sweep_f32_to_f16(E.f32_patterns(quick="--quick" in sys.argv))
