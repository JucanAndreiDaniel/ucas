#!/usr/bin/env python3
"""Large combinatorial sweep of undefined-propagation expressions.

Runs every candidate under `timeout` and records exit codes.  Output to stdout;
intended as an audit tool, not a golden.  Usage: python3 sweep.py
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
_HERE = _ROOT_PATH(__file__).resolve().parent
import subprocess

BIN = str(_REPO_ROOT / "ucas")
WD  = str(_HERE)

def run(stmts, timeout=15):
    args = [BIN]
    for s in stmts:
        args += ["-e", s]
    try:
        p = subprocess.run(args, cwd=WD, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""

# Undefined-producing cores, parameterised by x.
REAL_CORES = [
    "sqrt(x)", "log(x)", "1/x", "x/x", "(x*x-1)/(x-1)",
    "sqrt(-1)", "log(0)", "1/0", "0/0", "asin(2)", "acos(3)",
    "(-1)^(1/2)", "x^x", "sqrt(x)*sqrt(-x)", "sqrt(log(x))",
    "log(sqrt(x))", "1/sqrt(x)", "sqrt(1-x*x)", "log(abs(x)-1)",
    "atanh(x)", "acosh(x-2)", "W(-1)",
]
INT_CORES = [
    "[1,2,3][x]", "1 << x", "x >> x", "100/x", "100%x",
    "(1 << 7)/x", "match x { 0 => 1, 1 => 2 }",
    "{ 3 if x < 2 }", "[1,2][x] + [5,6][x]",
]

# Wrappers that embed a core <C> in a larger expression.
WRAPPERS = [
    "<C> + 1", "<C> * 2", "-<C>", "<C> * 0", "0 * <C>",
    "min(<C>, 5)", "max(<C>, 5)", "abs(<C>)", "sqrt(<C>)",
    "log(<C>)", "1/(<C>)", "x > 0 ? <C> : 0", "x > 0 ? 0 : <C>",
    "x < 3 ? <C> : 9", "x < 3 ? 9 : <C>",
    "(x > 0) && (<C> > 0)", "(x > 0) || (<C> > 0)",
    "<C> where x > 2", "<C> where x < -2",
    "<C> == <C>", "<C> > 0", "f32(<C>)", "real(<C>)",
]

exprs = []
for core in REAL_CORES:
    for w in WRAPPERS:
        exprs.append(("real:" + w.replace("<C>", core), "f(x: real) = " + w.replace("<C>", core)))
for core in INT_CORES:
    for w in WRAPPERS:
        exprs.append(("int:" + w.replace("<C>", core), "f(x: u8) = " + w.replace("<C>", core)))

# Also test asfloat of signalling-NaN bit patterns and combinations.
for bits in ["0x7f800001", "0xff800001", "0x7fc00001", "0x7f800000", "0x7fbfffff"]:
    exprs.append(("nan:" + bits, "f(x: u32) = asfloat(x | %s) + 1" % bits))

print("TOTAL EXPRESSIONS:", len(exprs))
bad = []
counts = {}
for i, (label, body) in enumerate(exprs):
    rc, out = run([body, "domain f", "range f"])
    counts[rc] = counts.get(rc, 0) + 1
    marker = ""
    if rc != 0:
        marker = "  <-- NONZERO"
        bad.append((label, rc, out[-600:]))
    elif "error" in out.lower() and "note:" not in out.lower():
        # parse errors that still produce output are interesting but not crashes
        marker = "  <-- parse error?"
    if marker or i % 50 == 0:
        print(i, label, "rc=", rc, marker)
print("EXIT COUNTS:", counts)
print("BAD:", len(bad))
for label, rc, tail in bad:
    print("----", label, rc)
    print(tail)
