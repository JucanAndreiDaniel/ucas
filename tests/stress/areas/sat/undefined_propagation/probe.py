#!/usr/bin/env python3
"""Exploratory probe for undefined-propagation stress tests (not a golden)."""
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
import subprocess, sys, re, json

BIN = str(_REPO_ROOT / "ucas")
WD  = str(_HERE)

def run(stmts, timeout=12):
    args = [BIN]
    for s in stmts:
        args += ["-e", s]
    try:
        p = subprocess.run(args, cwd=WD, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""

# Each entry: (name, definition). Analysis commands appended per expression.
EXPRS = []
def add(name, body):
    EXPRS.append((name, body))

# 1. constant undefined sources embedded in arithmetic
add("c_sqrtm1",        "f(x: real) = sqrt(-1) + x")
add("c_sqrtm1_mul0",   "f(x: real) = sqrt(-1) * 0 * x")
add("c_sqrtm1_x0",     "f(x: real) = sqrt(-1) * x * 0")
add("c_log0",          "f(x: real) = log(0) + x")
add("c_log0_mul0",     "f(x: real) = log(0) * 0 * x")
add("c_div0",          "f(x: real) = 1/0 + x")
add("c_div0_mul0",     "f(x: real) = (1/0) * 0 * x")
add("c_0div0",         "f(x: real) = 0/0 + x")
add("c_logneg",        "f(x: real) = log(-1) + x")
add("c_sqrtneg2",      "f(x: real) = sqrt(-2) * x")
add("c_powhalf",       "f(x: real) = (-1)^(1/2) + x")
add("c_asin2",         "f(x: real) = asin(2) + x")
add("c_acos2",         "f(x: real) = acos(2) + x")

# 2. real partial functions with operators
add("r_sqrt",         "f(x: real) = sqrt(x) + 1")
add("r_sqrt_mul",     "f(x: real) = sqrt(x) * x")
add("r_sqrt_div",     "f(x: real) = sqrt(x) / x")
add("r_sqrt_sub",     "f(x: real) = sqrt(x-1)")
add("r_log",          "f(x: real) = log(x) + 1")
add("r_log_mul",      "f(x: real) = log(x) * x")
add("r_log_div",      "f(x: real) = log(x) / x")
add("r_inv",          "f(x: real) = 1/x + 1")
add("r_inv_x",        "f(x: real) = x/x")
add("r_inv_x2",       "f(x: real) = (x^2 - 1)/(x - 1)")
add("r_inv_abs",      "f(x: real) = 1/|x|")
add("r_combo",        "f(x: real) = sqrt(x) + log(x) + 1/x")
add("r_nested",       "f(x: real) = sqrt(log(x))")
add("r_nested2",      "f(x: real) = log(sqrt(x))")
add("r_nested3",      "f(x: real) = sqrt(1 - x^2)")
add("r_nested4",      "f(x: real) = 1/sqrt(x)")
add("r_absneg",       "f(x: real) = sqrt(|x|)")
add("r_twosqrt",      "f(x: real) = sqrt(x) + sqrt(-x)")

# 3. dead branches with ?: and logical ops
add("d_true_dead",    "f(x: real) = 1 < 2 ? x : sqrt(-1)")
add("d_false_dead",   "f(x: real) = 1 > 2 ? sqrt(-1) : x")
add("d_cond_t",       "f(x: real) = x > 0 ? x : sqrt(-1)")
add("d_cond_f",       "f(x: real) = x > 0 ? sqrt(-1) : x")
add("d_and_short",    "f(x: real) = x > 0 && x < 5 ? x : sqrt(-1)")
add("d_or_short",     "f(x: real) = x > 0 || 1/x > 2 ? x : 0")
add("d_nested",       "f(x: real) = x > 0 ? (x>1 ? sqrt(x) : log(x)) : 1/x")
add("d_and_lazy",     "f(x: real) = (x > 0) && (sqrt(x) > 1)")
add("d_or_lazy",      "f(x: real) = (x > 0) || (log(x) > 1)")
add("d_bool_undef",   "f(x: real) = (sqrt(-1) > 0) ? x : 0")
add("d_bool_undef2",  "f(x: real) = (1/0 > 0) ? x : 0")
add("d_cmp_undef",    "f(x: real) = sqrt(-1) > x")

# 4. min / max with undefined
add("m_min_undef",    "f(x: real) = min(sqrt(-1), x)")
add("m_max_undef",    "f(x: real) = max(sqrt(-1), x)")
add("m_min_sqrt",     "f(x: real) = min(sqrt(x), 2)")
add("m_max_log",      "f(x: real) = max(log(x), 0)")
add("m_min_both",     "f(x: real) = min(sqrt(x), log(x))")
add("m_max_both",     "f(x: real) = max(sqrt(x), log(x))")
add("m_clamp",        "f(x: real) = max(0, min(1, sqrt(x)))")
add("m_min_dead",     "f(x: real) = x > 0 ? min(sqrt(x),2) : max(log(-x),0)")
add("m_min_nan",      "f(x: f32) = min(x, asfloat(0x7fc00000))")
add("m_max_snan",     "f(x: f32) = max(x, asfloat(0x7f800001))")

# 5. tables & shifts (enumerable int domains)
add("t_oob",          "f(x: u8) = [10,20,30][x]")
add("t_partial_ok",   "f(x: u8 in 0..2) = [10,20,30][x]")
add("t_oob_plus",     "f(x: u8) = [10,20,30][x] + 1")
add("t_oob_mul0",     "f(x: u8) = [10,20,30][x] * 0")
add("t_oob_cond",     "f(x: u8) = x < 3 ? [10,20,30][x] : 99")
add("t_oob_dead",     "f(x: u8) = x < 3 ? 99 : [10,20,30][x]")
add("t_nested",       "f(x: u8) = [[1,2],[3,4]][x & 1][x >> 1]")
add("s_shift",        "f(x: u8) = 1 << x")
add("s_shift_ok",     "f(x: u8 in 0..7) = 1 << x")
add("s_shift_r",      "f(x: u8) = x >> x")
add("s_shift_cond",   "f(x: u8) = x < 8 ? (1 << x) : 0")
add("s_shift_dead",   "f(x: u8) = x < 8 ? 0 : (1 << x)")
add("s_shift32",      "f(x: u32 in 0..40) = 1 << x")
add("s_shiftr32",     "f(x: u32 in 0..40) = x >> x")
add("s_shift_mul0",   "f(x: u8) = (1 << x) * 0")
add("s_shift_min",    "f(x: u8) = min(1 << x, 200)")

# 6. asfloat signalling NaN
add("n_snan",         "f(x: u32) = asfloat(x | 0x7f800001)")
add("n_snan_const",   "f(x: u32) = asfloat(0x7f800001)")
add("n_snan_add",     "f(x: u32) = asfloat(x | 0x7f800001) + 1")
add("n_snan_cmp",     "f(x: u32) = asfloat(x | 0x7f800001) > 0")
add("n_qnan",         "f(x: u32) = asfloat(x | 0x7fc00000)")
add("n_snan_min",     "f(x: u32) = min(asfloat(x | 0x7f800001), 1.0)")
add("n_snan_max",     "f(x: u32) = max(asfloat(x | 0x7f800001), 1.0)")
add("n_snan_cond",    "f(x: u32) = (asfloat(x | 0x7f800001) > 0) ? 1 : 2")
add("n_snan_abs",     "f(x: u32) = abs(asfloat(x | 0x7f800001))")
add("n_snan_neg",     "f(x: u32) = -asfloat(x | 0x7f800001)")

# 7. where out-of-domain
add("w_gt",           "f(x: real) = x where x > 5")
add("w_lt",           "f(x: real) = x where x < -3")
add("w_and",          "f(x: real) = x where x > 2 && x < 7")
add("w_partial",      "f(x: real) = sqrt(x) where x >= 0")
add("w_partial2",     "f(x: real) = sqrt(x) where x >= 4")
add("w_disjoint",     "f(x: real) = x where x < -2 || x > 2")
add("w_false",        "f(x: real) = x where x > x")
add("w_true",         "f(x: real) = x where x >= x")
add("w_int",          "f(x: u8) = x where x in 3..9")
add("w_int_partial",  "f(x: u8) = [1,2,3][x] where x < 3")
add("w_shift",        "f(x: u8) = 1 << x where x < 4")

# 8. match / piecewise partial
add("p_match",        "f(x: u8) = match x { 0 => 1, 1 => 2 }")
add("p_piece",        "f(x: real) = { x if x >= 0, -x otherwise }")
add("p_piece_partial","f(x: real) = { x if x > 0 }")
add("p_match_default","f(x: u8) = match x { 0 => 1, _ => 9 }")

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    total = 0
    for name, body in EXPRS:
        if which != "all" and not name.startswith(which):
            continue
        total += 1
        name_f = "f"
        cmds = [body]
        for cmd in ["domain", "range", "wrap", "crit"]:
            cmds.append(f"{cmd} {name_f}")
        rc, out = run(cmds)
        # summarise
        dom = re.findall(r"requires .*|where .*|defined at \d+ of \d+ points|defined on .*|nowhere|no conditions.*", out)
        rng = re.findall(r"undefined at \d+ of \d+ grid points|undefined at \d+ points|empty \(undefined everywhere\)", out)
        print(f"### {name}: rc={rc}")
        print(body)
        for line in out.splitlines():
            if (line.startswith("domain of") or line.startswith("range of") or
                line.startswith("wrap analysis") or line.startswith("critical points") or
                line.startswith("  requires") or line.startswith("  where") or
                "undefined" in line or "C undefined" in line or "empty" in line or
                "error" in line.lower() or "note:" in line or "defined at" in line or
                "not differentiable" in line or "end to end" in line):
                print("   " + line)
        print()
    print("TOTAL", total)
