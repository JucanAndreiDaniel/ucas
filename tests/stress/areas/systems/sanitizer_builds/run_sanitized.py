#!/usr/bin/env python3
"""
Driver for the sanitizer_builds stress area.

Generates a broad set of harsh reproducers (drawn from the sibling stress
areas' FINDINGS.md files), runs each through the SEPARATE sanitizer-instrumented
binary in this folder, and records every ASan/UBSan report with its stack trace.

Raw per-case output is saved under evidence/ (NOT kept as golden .out files,
because crash/hang cases would break a test runner).
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
import os, subprocess, sys, textwrap

HERE = str(_HERE)
BIN = os.path.join(HERE, "ucas_san")
EVID = os.path.join(HERE, "evidence")
os.makedirs(EVID, exist_ok=True)

ENV = dict(os.environ)
ENV["ASAN_OPTIONS"] = "detect_leaks=1:abort_on_error=0:print_stacktrace=1:symbolize=1"
ENV["UBSAN_OPTIONS"] = "print_stacktrace=1:halt_on_error=0"
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"

# Sanitizer signatures we hunt for.
SIGS = (
    "ERROR: AddressSanitizer",
    "ERROR: LeakSanitizer",
    "runtime error:",
    "SUMMARY: AddressSanitizer",
    "SUMMARY: UndefinedBehaviorSanitizer",
)

cases = []  # (name, mode, payload, timeout)

def ucas(name, text, t=15):
    cases.append((name, "cli", text, t))

def jsonl(name, text, t=15):
    cases.append((name, "json", text, t))

def mcp(name, text, t=15):
    cases.append((name, "mcp", text, t))

def args(name, text, t=15):
    cases.append((name, "args", text, t))

# ---------------------------------------------------------------------------
# A. parser_json_fuzz deep nesting (CLI) -- known stack-overflow crashes
# ---------------------------------------------------------------------------
ucas("A01_deep_parens_2000", "show " + "("*2000 + "x" + ")"*2000 + "\n")
ucas("A02_deep_parens_5000", "show " + "("*5000 + "x" + ")"*5000 + "\n")
ucas("A03_unary_minus_2000", "show " + "-"*2000 + "x\n")
ucas("A04_nested_sqrt_3000", "show " + "sqrt("*3000 + "x" + ")"*3000 + "\n")
ucas("A05_unmatched_open_paren_20000", "show " + "("*20000 + "\n")
ucas("A06_unmatched_open_bracket_20000", "show " + "["*20000 + "\n")
ucas("A07_deep_where_1500", "show (x where " + "x<"*1500 + "x)\n")
ucas("A08_long_ident_50000", "show " + "a"*50000 + "\n", 20)
ucas("A09_deep_unary_in_fn", "f(x: u8) = " + "-"*2000 + "x\nshow f\n")
ucas("A10_nested_abs_3000", "show " + "abs("*3000 + "x" + ")"*3000 + "\n")

# ---------------------------------------------------------------------------
# B. JSON / MCP deep nesting (server-wide crashes)
# ---------------------------------------------------------------------------
import json
deep_src = "show " + "("*3000 + "x" + ")"*3000
jsonl("B01_json_deep_3000",
      json.dumps({"id":1,"cmd":"ucas","args":{"source":deep_src}}) + "\n" +
      json.dumps({"id":2,"cmd":"bigint","args":{"expr":"2^10"}}) + "\n", 30)
mcp("B02_mcp_deep_3000",
    '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}\n'
    '{"jsonrpc":"2.0","method":"notifications/initialized"}\n' +
    json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":deep_src}}}) + "\n" +
    json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"show","args":{"f":"x+1"}}}}) + "\n", 30)
# deeply nested JSON arrays (parser's own depth limit ~62)
jsonl("B03_json_nested_arrays",
      json.dumps({"id":1,"cmd":"show","args":{"f":"["*40 + "]"*40}}) + "\n")
jsonl("B04_json_timeout_s_bad",
      '{"id":1,"cmd":"show","args":{"f":"x","timeout_s":-5}}\n'
      '{"id":2,"cmd":"show","args":{"f":"x","timeout_s":"abc"}}\n'
      '{"id":3,"cmd":"show","args":{"f":"x","timeout_s":1e9}}\n')

# ---------------------------------------------------------------------------
# C. resource_limits-style huge tables / big values
# ---------------------------------------------------------------------------
ucas("C01_table_1024", "b(x: u16 in 0..1024) = [" + ",".join("0" for _ in range(1024)) + "][x]\nrange b\n", 25)
ucas("C02_table_1025", "b(x: u16 in 0..1025) = [" + ",".join("0" for _ in range(1025)) + "][x]\n", 25)
ucas("C03_bigint_2pow1m", "bigint 2^1000000\n", 25)
ucas("C04_shift_u64_huge", "show 1u64 << 100000\nshow 1u64 >> 100000\n")
ucas("C05_huge_literal", "bigint " + "9"*10000 + "\n", 20)
ucas("C06_many_statements", "\n".join("show %d+1" % i for i in range(300)) + "\n", 25)
ucas("C07_deep_list_literal", "show [" + ",".join("[" * 1 + "1" + "]" * 1 for _ in range(500)) + "]\n", 25)
ucas("C08_huge_table_index", "t(x: u8) = [10,20,30][x]\nshow t(255)\nshow t(256)\n")
ucas("C09_big_fact", "bigint 10000!\n", 25)

# ---------------------------------------------------------------------------
# D. fp_edge NaNs / special float values
# ---------------------------------------------------------------------------
nan_cases = [
    "show asfloat(u16(0x7c00))", "show asfloat(u16(0x7e00))",
    "show asfloat(u16(0x0001))", "show asfloat(u16(0x7bff))",
    "show asfloat(u32(0x7f800000))", "show asfloat(u32(0xff800000))",
    "show asfloat(u32(0x7fc00000))", "show asfloat(u32(0x00000001))",
    "show asfloat(u32(0x007fffff))", "show asfloat(u32(0x7f7fffff))",
    "show asfloat(u64(0x7ff0000000000000))", "show asfloat(u64(0x0000000000000001))",
    "show asfloat(u64(0x7fefffffffffffff))", "show asuint(asfloat(u32(0x7fc00001)))",
    "show asint(asfloat(u32(0xffffffff)))", "show asuint(asfloat(u64(0x7ff8000000000001)))",
    "show asint(asfloat(u64(0x8000000000000000)))", "show asuint(f16(-0.0))",
    "show asuint(f32(-0.0))", "show asuint(f64(-0.0))",
    "show asfloat(u32(0x7fc00000)) + asfloat(u32(0x7fc00001))",
    "show asfloat(u32(0x7fc00000)) < 1.0", "show asfloat(u32(0x7fc00000)) == asfloat(u32(0x7fc00000))",
    "show min(asfloat(u32(0x7fc00000)), 1.0)", "show max(asfloat(u32(0x7fc00000)), 1.0)",
    "show sqrt(asfloat(u32(0xff800000)))", "show 1.0 / asfloat(u32(0x00000000))",
    "show asfloat(u32(0x7f800000)) - asfloat(u32(0x7f800000))",
    "show 0.0 * asfloat(u32(0x7f800000))",
]
ucas("D01_nan_battery", "\n".join(nan_cases) + "\n", 25)
ucas("D02_nan_in_sat", "f(x: f32) = x < 1.0\nequiv f f\n", 25)
ucas("D03_nan_range", "g(x: f32 in 0.0..1.0) = x\nrange g\n")

# ---------------------------------------------------------------------------
# E. type coercion / casts
# ---------------------------------------------------------------------------
casts = []
for t in ["u8","i8","u16","i16","u32","i32","u64","i64","f16","f32","f64","int","real","bool"]:
    casts.append("show u8(%s(255))" % t if t not in ("u8",) else "show u8(255)")
for t in ["u8","i8","u16","i16","u32","i32","u64","i64"]:
    casts.append("show %s(-1)" % t)
    casts.append("show %s(1000000)" % t)
casts += [
    "show f32(16777217)", "show f16(70000)", "show i8(f32(200.9))",
    "show u8(f64(-1.5))", "show asuint(-1)", "show asint(0xffffffffu32)",
    "show bigint(1.5)", "show f64(bigint(2^200))", "show u32(f64(1e30))",
    "show i32(0x80000000u32)", "show u64(0xffffffffffffffffu64) + 1",
    "show asfloat(0x7fc00000u32)", "show f16(f64(1e10))",
]
ucas("E01_cast_battery", "\n".join(casts) + "\n", 25)
ucas("E02_wrap_u64_id", "id(x: u64) = x\nwrap id\n", 25)
ucas("E03_shift_width", "f(x: u32) = x << 32\ndomain f\nwrap f\n")
ucas("E04_div_zero", "f(x: u8, y: u8) = x / y\ndomain f\nrange f\n")

# ---------------------------------------------------------------------------
# F. sat_wide_bitops / sat_ranges_where harsh reproducers
# ---------------------------------------------------------------------------
ucas("F01_swar64",
     "pc(x: u64) = popcount(x)\n"
     "r(x: u64) = x - ((x >> 1) & 0x5555555555555555)\n"
     "s(x: u64) = (r(x) & 0x3333333333333333) + ((r(x) >> 2) & 0x3333333333333333)\n"
     "t(x: u64) = (s(x) + (s(x) >> 4)) & 0x0f0f0f0f0f0f0f0f\n"
     "q(x: u64) = (t(x) * 0x0101010101010101) >> 56\n"
     "swar(x: u64) = q(x)\n"
     "equiv pc swar\n", 30)
ucas("F02_equiv_where",
     "fw(x: u8) = x where x < 10\n"
     "gw(x: u8) = x where x < 5\n"
     "equiv fw ~ gw\n"
     "domain gw\n")
ucas("F03_range_big_domain", "g(x: u32 in 0..4194304) = x*x\nrange g\n", 25)
ucas("F04_shift_var", "g(x: u64, n: u64) = x >> n\ndomain g\nwrap g\n", 25)
ucas("F05_clz_ctz", "show clz(0u32)\nshow ctz(0u32)\nf(x: u8) = x >> 8\ndomain f\n")

# ---------------------------------------------------------------------------
# Run all cases
# ---------------------------------------------------------------------------
def run_one(name, mode, payload, timeout):
    path = os.path.join(EVID, name + ".in")
    with open(path, "w") as f:
        f.write(payload)
    if mode == "cli":
        cmd = [BIN, path]
    elif mode == "json":
        cmd = [BIN, "--json", "--files", "none"]
    elif mode == "mcp":
        cmd = [BIN, "--mcp"]
    else:
        cmd = [BIN] + payload.strip().split()
    try:
        p = subprocess.run(cmd, input=(None if mode in ("cli","args") else payload),
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=ENV, timeout=timeout, cwd=HERE)
        out, rc = p.stdout, p.returncode
    except subprocess.TimeoutExpired as e:
        out, rc = (e.stdout or b"").decode("utf-8", "replace"), "TIMEOUT"
    with open(os.path.join(EVID, name + ".log"), "w") as f:
        f.write("### CMD: %s\n### RC: %s\n\n" % (" ".join(cmd), rc))
        f.write(out)
    hits = [s for s in SIGS if s in out]
    return rc, hits, out

def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, mode, payload, t in cases:
        if only and only not in name:
            continue
        rc, hits, out = run_one(name, mode, payload, t)
        tag = ""
        if hits:
            tag = "  <<< " + ",".join(sorted(set(hits)))
        print("%-36s rc=%-8s%s" % (name, str(rc), tag))
        sys.stdout.flush()

if __name__ == "__main__":
    main()
