#!/usr/bin/env python3
"""Generate the deterministic CLI golden catalog for float_exhaustive.

Each .ucas file is small (<=20 statements), self-contained, and is run twice to
confirm byte-identical output before the .out golden is written.  The statements
are drawn from the exhaustive sweeps plus the individual counterexamples found
by exhaustive.py / casts.py.
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
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
UCAS = str(_REPO_ROOT / "ucas")


def hx(v, w):
    return f"0x{v:0{w}x}"


F16_SPECIAL = [0x0000, 0x0001, 0x0002, 0x03FF, 0x0400, 0x0401, 0x07FF, 0x0800,
               0x3800, 0x3BFF, 0x3C00, 0x3C01, 0x3D00, 0x3E00, 0x4000, 0x7BFE,
               0x7BFF, 0x7C00, 0x7C01, 0x7DFF, 0x7E00, 0x7FFF,
               0x8000, 0x8001, 0x83FF, 0xBC00, 0xC000, 0xFC00, 0xFC01, 0xFE00, 0xFFFF]

F16_SUB = [0x0001, 0x0002, 0x0004, 0x0008, 0x0010, 0x0020, 0x0040, 0x0080,
           0x0100, 0x0200, 0x03FE, 0x03FF]

F16_CORE = [0x0000, 0x0001, 0x03FF, 0x0400, 0x3800, 0x3BFF, 0x3C00, 0x3C01,
            0x4000, 0x4400, 0x4800, 0x5000, 0x7000, 0x7BFF, 0x7C00, 0x7E00]

F32_SPECIAL = [0x00000000, 0x00000001, 0x00000002, 0x007FFFFE, 0x007FFFFF,
               0x00800000, 0x00800001, 0x3F7FFFFF, 0x3F800000, 0x3F800001,
               0x40000000, 0x7F7FFFFE, 0x7F7FFFFF, 0x7F800000, 0x7F800001,
               0x7FC00000, 0x7FFFFFFF, 0x80000000, 0x80000001, 0x807FFFFF,
               0x80800000, 0xBF800000, 0xFF7FFFFF, 0xFF800000, 0xFFC00000, 0xFFFFFFFF]

F32_CORE = [0x00000000, 0x00000001, 0x00800000, 0x3F800000, 0x3F000000,
            0x40000000, 0x40240000, 0x42B00000, 0x7F7FFFFF, 0x7F800000,
            0x7FC00000, 0x80000000, 0xBF800000, 0xFF800000, 0xFFC00000, 0xFFFFFFFF]


def header(*defs):
    return list(defs)


def calls(fn, pats, width, per_line=2):
    out = []
    for i in range(0, len(pats), per_line):
        out.append("; ".join(f"{fn}({hx(b, width)})" for b in pats[i:i + per_line]))
    return out


FILES = {}


def add(name, lines):
    FILES[name] = lines


# 1. asuint(asfloat(bits)) roundtrip over f16 specials
add("01_f16_roundtrip", header("R(x: u16) = asuint(asfloat(x))") + calls("R", F16_SPECIAL, 4))

# 2-7: f16 unary ops over specials (individual counterexamples / sweep summaries)
for num, (op, fn) in enumerate([("sqrt", "SQ"), ("log", "LG"), ("exp", "EX"),
                                ("sin", "SN"), ("abs", "AB"), ("floor", "FL"),
                                ("ceil", "CE"), ("roundeven", "RE")], start=2):
    label = {2: "sqrt", 3: "log", 4: "exp", 5: "sin", 6: "abs", 7: "floor", 8: "ceil", 9: "roundeven"}[num]
    lines = header(f"p(x: u16) = asfloat(x)", f"{fn}(x: u16) = asuint({op}(p(x)))")
    lines += calls(fn, F16_SPECIAL if num in (2, 3, 4, 5) else F16_CORE, 4)
    add(f"{num:02d}_f16_{label}", lines)

# 10. f16 signed-zero behaviour of unary ops
lines = header("p(x: u16) = asfloat(x)",
               "AB(x:u16)=asuint(abs(p(x)))", "SQ(x:u16)=asuint(sqrt(p(x)))",
               "SN(x:u16)=asuint(sin(p(x)))", "FL(x:u16)=asuint(floor(p(x)))",
               "CE(x:u16)=asuint(ceil(p(x)))", "RE(x:u16)=asuint(roundeven(p(x)))")
for b in (0x0000, 0x8000):
    lines.append("; ".join(f"{f}({hx(b,4)})" for f in ("AB", "SQ", "SN", "FL", "CE", "RE")))
add("10_f16_signed_zero", lines)

# 11. f16 -> f32 casts
lines = header("C(x: u16) = asuint(f32(asfloat(x)))") + calls("C", F16_SPECIAL, 4)
add("11_f16_to_f32", lines)

# 12. f32 -> f16 casts
lines = header("C(x: u32) = asuint(f16(asfloat(x)))") + calls("C", F32_CORE, 8)
add("12_f32_to_f16", lines)

# 13. direct-call domain errors stay symbolic for f16
add("13_f16_domain_symbolic", header("p(x:u16)=asfloat(x)",
    "LG(x:u16)=asuint(log(p(x)))", "SQ(x:u16)=asuint(sqrt(p(x)))",
    "EX(x:u16)=asuint(exp(p(x)))") + [
    "LG(0x0000)", "LG(0x8000)", "LG(0xbc00)", "LG(0xfc00)",
    "SQ(0xbc00)", "SQ(0xfc00)", "EX(0x7bff)",
])

# 14. direct-call domain errors stay symbolic for f32
add("14_f32_domain_symbolic", header("p(x:u32)=asfloat(x)",
    "LG(x:u32)=asuint(log(p(x)))", "SQ(x:u32)=asuint(sqrt(p(x)))",
    "EX(x:u32)=asuint(exp(p(x)))") + [
    "LG(0x00000000)", "LG(0x80000000)", "LG(0xbf800000)", "LG(0xff800000)",
    "SQ(0xbf800000)", "SQ(0xff800000)", "EX(0x42c00000)",
])

# 15. table-forced numeric evaluation of the very same domain errors
add("15_forced_domain_numeric", [
    "lgz(x:u16)=asuint(log(asfloat(0x0)))", "table lgz max 1",
    "sqn(x:u16)=asuint(sqrt(asfloat(0xbc00)))", "table sqn max 1",
    "exo(x:u16)=asuint(exp(asfloat(0x42c00000)))", "table exo max 1",
    "lgn(x:u16)=asuint(log(asfloat(0xbf800000)))", "table lgn max 1",
])

# 16. NaN payload / sNaN quieting: f16 vs f32 vs f64 abs
add("16_nan_abs_inconsistent", [
    "a16(x:u16)=asuint(abs(asfloat(x)))", "a32(x:u32)=asuint(abs(asfloat(x)))",
    "a64(x:u64)=asuint(abs(asfloat(x)))",
    "a16(0x7c01)", "a16(0xfc01)", "a16(0x7e01)",
    "a32(0x7f800001)", "a32(0xff800001)", "a32(0x7fc00001)",
    "a64(0x7ff0000000000001)", "a64(0xfff0000000000001)",
])

# 17. non-abs ops quiet sNaN consistently (f16)
lines = header("p(x:u16)=asfloat(x)",
    "SQ(x:u16)=asuint(sqrt(p(x)))", "SN(x:u16)=asuint(sin(p(x)))",
    "FL(x:u16)=asuint(floor(p(x)))", "RE(x:u16)=asuint(roundeven(p(x)))")
for b in (0x7c01, 0xfc01, 0x7dff):
    lines.append("; ".join(f"{f}({hx(b,4)})" for f in ("SQ", "SN", "FL", "RE")))
add("17_f16_snAN_quiet", lines)

# 18. UNSOUND equiv: x vs x+0 differ at -0 but equiv says equal (all formats)
add("18_equiv_signed_zero", [
    "f16a(x:f16)=x", "f16b(x:f16)=x+0",
    "f32a(x:f32)=x", "f32b(x:f32)=x+0",
    "f64a(x:f64)=x", "f64b(x:f64)=x+0",
    "equiv f16a ~ f16b", "equiv f16a ~ f16b nanbits",
    "equiv f32a ~ f32b", "equiv f64a ~ f64b",
])

# 19. the actual -0 counterexample values
add("19_signed_zero_counterexample", [
    "p16(x:u16)=asfloat(x)", "I16(x:u16)=asuint(p16(x))", "A16(x:u16)=asuint(p16(x)+0.0)",
    "p32(x:u32)=asfloat(x)", "I32(x:u32)=asuint(p32(x))", "A32(x:u32)=asuint(p32(x)+0.0)",
    "I16(0x8000)", "A16(0x8000)", "I16(0x0000)", "A16(0x0000)",
    "I32(0x80000000)", "A32(0x80000000)",
])

# 20. domain counts off by one (-0 excluded)
add("20_domain_counts", [
    "id16(x:f16)=x", "id32(x:f32)=x", "id64(x:f64)=x",
    "domain id16", "range id16", "domain id32", "domain id64", "range id64",
])

# 21. range of f16 unary functions (exhaustive, deterministic)
add("21_range_f16", [
    "s16(x:f16)=sqrt(x)", "l16(x:f16)=log(x)", "n16(x:f16)=sin(x)",
    "a16(x:f16)=abs(x)", "f16(x:f16)=floor(x)", "c16(x:f16)=ceil(x)",
    "range s16", "range l16", "range n16", "range a16", "range f16", "range c16",
])

# 22. f32 special-region unary evaluations
lines = header("p(x:u32)=asfloat(x)",
    "SQ(x:u32)=asuint(sqrt(p(x)))", "LG(x:u32)=asuint(log(p(x)))",
    "EX(x:u32)=asuint(exp(p(x)))", "SN(x:u32)=asuint(sin(p(x)))")
for b in (0x3F800000, 0x7F800000, 0xFF800000, 0x7FC00000, 0x00000001, 0x80000000):
    lines.append("; ".join(f"{f}({hx(b,8)})" for f in ("SQ", "LG", "EX", "SN")))
add("22_f32_specials", lines)

# 23. f16 subnormal sweep via table (summary of sweep)
add("23_f16_subnormal_sweep", [
    "p(x:u16)=asfloat(x)",
    "SQ(x:u16)=asuint(sqrt(p(x)))", "table SQ max 16",
    "LG(x:u16)=asuint(log(p(x)))", "table LG max 16",
    "EX(x:u16)=asuint(exp(p(x)))", "table EX max 16",
])

# 24. equiv sanity (differing functions ARE caught)
add("24_equiv_sanity", [
    "id16(x:f16)=x", "ab16(x:f16)=abs(x)", "fl16(x:f16)=floor(x)",
    "equ16(x:f16)=x*1", "sq16(x:f16)=sqrt(x*x)",
    "equiv id16 ~ ab16", "equiv id16 ~ fl16", "equiv id16 ~ equ16", "equiv id16 ~ sq16",
])

# 25. f32 roundtrip and casts round-trip summary
add("25_f32_roundtrip", header("R(x: u32) = asuint(asfloat(x))") + calls("R", F32_SPECIAL[:12], 8))


def gen(name, lines):
    ucas = os.path.join(HERE, name + ".ucas")
    with open(ucas, "w") as f:
        f.write("\n".join(lines) + "\n")
    cmd = [UCAS, ucas]
    r1 = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=HERE)
    out1 = r1.stdout + ("\n[STDERR]\n" + r1.stderr if r1.stderr else "")
    r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=HERE)
    out2 = r2.stdout + ("\n[STDERR]\n" + r2.stderr if r2.stderr else "")
    if out1 != out2:
        print(f"!! NONDETERMINISTIC: {name} -- not writing .out")
        return False, out1
    with open(os.path.join(HERE, name + ".out"), "w") as f:
        f.write(out1)
    nstmt = sum(1 for ln in lines if ln.strip() and " = " not in ln)
    return True, nstmt


if __name__ == "__main__":
    total = 0
    for name in sorted(FILES):
        ok, info = gen(name, FILES[name])
        if not ok:
            continue
        total += info
        print(f"{name}: {info} statements, deterministic")
    print(f"\napprox total statements: {total}")
