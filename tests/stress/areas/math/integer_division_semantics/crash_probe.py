#!/usr/bin/env python3
"""Adversarial division/modulo probe: run each snippet twice under timeout,
flag nonzero exit, timeout, empty output, or differing output (nondeterminism)."""
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
import subprocess, hashlib, sys

BIN = str(_REPO_ROOT / "ucas")
TIMEOUT = 12

def run(src, extra=()):
    try:
        p = subprocess.run([BIN, *extra], input=src, text=True,
                           capture_output=True, timeout=TIMEOUT)
        return (p.returncode, p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return ("TIMEOUT", "")

def cases():
    C = []
    def add(tag, src, extra=()):
        C.append((tag, src, extra))
    # huge / out-of-range divisors
    for d in ["18446744073709551616", "9223372036854775808", "-9223372036854775809",
              "0x10000000000000000", "1e30", "999999999999999999999999999999"]:
        add(f"huge_{d}", f"f(x: u64) = x / {d}\nshow f\n")
        add(f"huge_i_{d}", f"f(x: i64) = x / {d}\nshow f\n")
    # divisor that wraps to zero
    add("wrapzero_u8", "f(x: u8) = x / (x + 256 - x)\nrange f\n")
    add("wrapzero_i8", "f(x: i8) = x / (x - x)\ndomain f\n")
    add("wrapzero_const", "f(x: u8 in 0..3) = x / 256\ntable f\n")
    # extremes
    add("imin_m1_i8", "f(x: i8) = x / -1\nrange f\nwrap f\n")
    add("imin_m1_i16", "f(x: i16) = x / -1\nrange f\n")
    add("imin_m1_i32", "f(x: i32) = x / -1\nrange f\n")
    add("imin_m1_i64", "f(x: i64) = x / -1\nrange f\n")
    add("imaxmod_i8", "f(x: i8) = x % -1\nrange f\n")
    # nested division chains
    for k in (2,3,5,10,30):
        expr = "x"
        for _ in range(k): expr += "/3"
        add(f"chain{k}", f"f(x: u16) = {expr}\nrange f\n")
    # modulo of modulo, division by modulo
    add("modmod", "f(x: u16) = (x % 7) % 3\nrange f\n")
    add("divmoddiv", "f(x: u16 in 0..1000) = x / (x % 7 + 1)\nrange f\n")
    add("div_of_mod", "f(x: i16) = (x % 13) / (x % 3)\ndomain f\n")
    # division in where clause / conditions
    add("where_div", "f(x: u8, y: u8) = x / y where y != 0\nrange f\n")
    add("where_div2", "f(x: i8) = x / (x - 1) where x != 1\nrange f\n")
    add("where_mod", "f(x: i8) = x % (x+1) where x != -1\nrange f\n")
    # bool / narrow types
    add("bool_div", "f(x: bool) = x / 1\nshow f\n")
    add("bool_mod", "f(x: bool) = x % 1\nshow f\n")
    # symbolic / real (should work)
    add("real_div", "f(x: real) = x / 3\nshow f\n")
    add("int_divmod", "f(x: int) = x % 3\ndomain f\n")
    # magic edge divisors
    for d in ["-1","1","2","-2","0","256","-128","128","65536","-32768",
              "4294967296","-2147483648","-9223372036854775808","18446744073709551615"]:
        add(f"magic_{d}_i8", f"magic {d} i8\n")
        add(f"magic_{d}_u8", f"magic {d} u8\n")
    # find on division by zero / variable
    add("find_divzero", "f(x: u8) = x / 0\nfind f 2\n")
    add("find_vardiv", "f(x: u8, y: u8 in 1..3) = x / y\nfind f 2\n")
    add("find_mod", "f(x: u16) = x % 7\nfind f 2\n")
    # mixed large
    add("mix_i64u64", "f(x: i64 in -100..100, y: u64 in 1..3) = x / y\nrange f\n")
    add("mix_u64i64", "f(x: u64 in 0..100, y: i64 in -3..-1) = x % y\nrange f\n")
    # domain of variable divisor at zero
    add("domain_vardiv", "f(x: u8, y: u8 in 0..3) = x / y\ndomain f\nrange f\n")
    add("wrap_vardiv", "f(x: i8, y: i8 in 0..3) = x / y\nwrap f\n")
    # equiv with division by zero on one side
    add("equiv_divzero", "f(x: u8 in 0..3) = x / x\nequiv f 1\n")
    add("equiv_divzero_rev", "f(x: u8 in 0..3) = 1\nequiv f (x/x)\n")
    # negative divisor in unsigned type
    add("u8_negdiv", "f(x: u8 in 0..8) = x / -3\nshow f\ntable f\n")
    add("u8_negmod", "f(x: u8 in 0..8) = x % -3\nshow f\ntable f\n")
    return C

def main():
    bad = []
    total = 0
    for tag, src, extra in cases():
        total += 1
        r1 = run(src, extra)
        r2 = run(src, extra)
        h1 = hashlib.md5(r1[1].encode()).hexdigest()
        h2 = hashlib.md5(r2[1].encode()).hexdigest()
        if r1[0]=="TIMEOUT" or r2[0]=="TIMEOUT":
            bad.append((tag,"HANG",r1[0],r2[0],r1[1][:200]))
        elif r1[0]!=0 or r2[0]!=0:
            bad.append((tag,"RC",r1[0],r2[0],(r1[1]+r2[1])[:300]))
        elif h1!=h2:
            bad.append((tag,"NONDET",h1,h2,(r1[1]+"\n---\n"+r2[1])[:400]))
        elif not r1[1].strip():
            bad.append((tag,"EMPTY",0,0,""))
    print(f"total={total} flagged={len(bad)}")
    for b in bad:
        print("FLAG", b)

if __name__=="__main__":
    main()
