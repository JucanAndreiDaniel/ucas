#!/usr/bin/env python3
"""Second exploratory probe: equiv/wrap/direct-eval/consistency and crash hunting."""
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

def run(stmts, timeout=12):
    args = [BIN]
    for s in stmts:
        args += ["-e", s]
    try:
        p = subprocess.run(args, cwd=WD, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        return "TIMEOUT", (e.stdout or b"").decode(errors="replace") + (e.stderr or b"").decode(errors="replace")

CASES = []
def add(label, stmts):
    CASES.append((label, stmts))

# direct evaluation of undefined subexpressions (look for silent 0 / NaN)
for body in ["sqrt(-1)", "sqrt(-1)*0", "log(0)*0", "(1/0)*0", "asin(2)*0",
             "sqrt(-1)+log(0)", "sqrt(-1)-sqrt(-1)", "sqrt(-1)/sqrt(-1)",
             "min(sqrt(-1),1)", "max(sqrt(-1),1)", "sqrt(-1)==sqrt(-1)",
             "1 < 2 ? 5 : sqrt(-1)", "1 > 2 ? sqrt(-1) : 5",
             "(1 < 2) && (sqrt(-1) > 0)", "(1 > 2) || (sqrt(-1) > 0)",
             "asfloat(0x7f800001)", "asfloat(0x7f800001)*0",
             "asfloat(0x7f800001) == asfloat(0x7f800001)"]:
    add("eval:"+body, [body])

# defined function evaluated at a bad point
add("evalfn", ["h(x: real) = sqrt(x)*0", "h(-4)", "h(4)", "domain h", "range h"])

# equiv: undefined dead branches, division / table / shift
add("eq_div1", ["f(x: u32 in 0..3) = x != 0 ? 10/x : 0",
                "g(x: u32 in 0..3) = x != 0 ? 10/x : 5", "equiv f g"])
add("eq_div2", ["f(x: u32) = x != 0 ? 10/x : 0",
                "g(x: u32) = x != 0 ? 10/x : 5", "equiv f g"])
add("eq_tbl1", ["f(x: u8) = x < 3 ? [1,2,3][x] : 0",
                "g(x: u8) = x < 3 ? [1,2,3][x] : 9", "equiv f g"])
add("eq_shift1", ["f(x: u8) = x < 8 ? (1<<x) : 0",
                  "g(x: u8) = x < 8 ? (1<<x) : 7", "equiv f g"])
add("eq_lazy1", ["f(x: real) = (x>0) && (sqrt(x)>1)", "g(x: real) = x>1", "equiv f g"])
add("eq_lazy2", ["f(x: real) = (x>0) || (log(x)>1)", "g(x: real) = x>0 || x>2.718281828459045", "equiv f g"])
add("eq_real1", ["f(x: real) = sqrt(x)*0", "g(x: real) = 0", "equiv f g"])
add("eq_real2", ["f(x: real) = x/x", "g(x: real) = 1", "equiv f g"])
add("eq_real3", ["f(x: real) = (x^2-1)/(x-1)", "g(x: real) = x+1", "equiv f g"])
add("eq_nan1", ["f(x: u32) = asfloat(x|0x7f800001)", "g(x: u32) = asfloat(x|0x7f800001)+0", "equiv f g nanbits"])
add("eq_nan2", ["f(x: u32) = asfloat(x|0x7f800001)", "g(x: u32) = asfloat(x|0x7fc00001)", "equiv f g nanbits"])
add("eq_nan3", ["f(x: f32) = min(x, asfloat(0x7f800001))", "g(x: f32) = min(x, asfloat(0x7fc00000))", "equiv f g nanbits"])

# wrap at undefined points
add("wrap_div", ["f(x: u8) = x != 0 ? 100/x : 0", "wrap f", "domain f"])
add("wrap_tbl", ["f(x: u8) = x < 3 ? [1,2,3][x] : 0", "wrap f", "domain f"])
add("wrap_shift", ["f(x: u8) = x < 8 ? (1<<x) : 0", "wrap f", "domain f"])

# potential crashes / hangs: nested undefined, big domains, many ops
add("crash1", ["f(x: real) = sqrt(sqrt(sqrt(sqrt(sqrt(x)))))", "domain f", "range f", "crit f"])
add("crash2", ["f(x: real) = log(log(log(x)))", "domain f", "range f"])
add("crash3", ["f(x: u32 in 0..1000000) = 1 << x", "domain f", "range f"])
add("crash4", ["f(x: i8) = (1 << 7) / x", "domain f", "range f", "wrap f"])
add("crash5", ["f(x: real) = 0^0", "domain f", "range f", "crit f"])
add("crash6", ["f(x: real) = (-1)^x", "domain f", "range f", "crit f"])
add("crash7", ["f(x: real) = x^x", "domain f", "range f"])
add("crash8", ["f(x: u8) = [1,2,3][x][0]", "domain f", "range f"])

if __name__ == "__main__":
    import sys
    filt = sys.argv[1] if len(sys.argv)>1 else ""
    for label, stmts in CASES:
        if filt and not label.startswith(filt):
            continue
        rc, out = run(stmts)
        print("="*70)
        print("LABEL:", label, "RC:", rc)
        for s in stmts: print("   >", s)
        print(out.strip()[:2500])
        print()
