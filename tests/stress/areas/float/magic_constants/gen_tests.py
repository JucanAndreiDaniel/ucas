#!/usr/bin/env python3
"""Generate all stress-test .ucas / .jsonl inputs for the magic_constants area."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def w(name, text):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(text.strip() + "\n")
    print("wrote", name, len(text.strip().splitlines()), "lines")


# ---------------- CLI: fit ----------------
lines = [
    "g(x: f32, K: u32) = asfloat(K - (asuint(x) >> 1))",
    "fit g ~ 1/sqrt(x)",
    "fit g ~ 1/sqrt(x) metric maxrel",
    "fit g ~ 1/sqrt(x) metric maxabs",
    "fit g ~ 1/sqrt(x) metric rms",
    "gA(x: f32, K: u32 in 0x5f375000..0x5f376000) = asfloat(K - (asuint(x) >> 1))",
    "fit gA ~ 1/sqrt(x)",
    "gB(x: f32, K: u32 in 0x5f376000..0x5f377000) = asfloat(K - (asuint(x) >> 1))",
    "fit gB ~ 1/sqrt(x)",
]
w("01_fit_default.ucas", "\n".join(lines))

lines = [
    "g(x: f32, K: u32) = asfloat(K - (asuint(x) >> 1))",
    "fit g ~ 1/sqrt(real(x))",
    "g2(x: f64, K: u64) = asfloat(K - (asuint(x) >> 1))",
    "fit g2 ~ 1/sqrt(x: f64)",
    "gh(x: f16, K: u16) = asfloat(K - (asuint(x) >> 1))",
    "fit gh ~ 1/sqrt(x: f16)",
    "gm(x: f32, K: u32 in 0x5f370000..0x5f380000) = asfloat(K - (asuint(x) >> 1))",
    "fit gm ~ 1/sqrt(x) metric maxrel",
    "gn(x: f32, K: u32) = asfloat(K - (asuint(x) >> 1)) - 1.5",
    "fit gn ~ 1/sqrt(x)",
]
w("02_fit_variants.ucas", "\n".join(lines))

# ---------------- CLI: error sweep ----------------
Ks = [0x5F3759DF, 0x5F375A86, 0x5F375B00, 0x5F375C33, 0x5F375DDD,
      0x5F375DDF, 0x5F375E00, 0x5F375F00, 0x5F376000, 0x5F376010,
      0x5F376020, 0x5F376030, 0x5F376033, 0x5F376040, 0x5F376100,
      0x5F376200, 0x5F376300, 0x5F376400, 0x5F37642F, 0x5F376433]
for part, chunk in enumerate([Ks[:10], Ks[10:]], start=1):
    lines = []
    for i, K in enumerate(chunk):
        j = (part - 1) * 10 + i
        lines.append(f"e{j}(x: f32) = asfloat(0x{K:08x} - (asuint(x) >> 1))")
        lines.append(f"error e{j} ~ 1/sqrt(x)")
    w(f"03_error_K_fine{part}.ucas", "\n".join(lines))

Ks2 = [0x5F3759DF, 0x5F37642F, 0x5F376033, 0x5F375A86, 0x5F37A000,
       0x5F374000, 0x5F375000, 0x5F377000, 0x5F378000, 0x5F370000]
lines = []
for i, K in enumerate(Ks2):
    lines.append(f"q{i}(x: f32) = asfloat(0x{K:08x} - (asuint(x) >> 1))")
    lines.append(f"error q{i} ~ 1/sqrt(x)")
w("04_error_K_named.ucas", "\n".join(lines))

# ---------------- CLI: bit hacks ----------------
w("10_abs_mask.ucas", "\n".join([
    "ab(x: f32) = asfloat(asuint(x) & 0x7fffffff)",
    "rf(x: f32) = abs(x)",
    "equiv ab ~ rf",
    "equiv ab ~ rf nanbits",
    "equiv ab ~ rf ftz",
    "equiv ab ~ rf noftz",
    "idb(x: f32) = asfloat(asuint(x))",
    "idf(x: f32) = x",
    "equiv idb ~ idf",
    "equiv idb ~ idf nanbits",
]))

w("11_minmax_mask.ucas", "\n".join([
    "mn(x: f32, y: f32) = asfloat(asuint(y) ^ ((asuint(x) ^ asuint(y)) & -(u32(asuint(x) < asuint(y)))))",
    "mx(x: f32, y: f32) = asfloat(asuint(x) ^ ((asuint(x) ^ asuint(y)) & -(u32(asuint(x) > asuint(y)))))",
    "rmin(x: f32, y: f32) = min(x, y)",
    "rmax(x: f32, y: f32) = max(x, y)",
    "equiv mn ~ rmin",
    "equiv mx ~ rmax",
    "mnp(x: f32 in 0..1e30, y: f32 in 0..1e30) = asfloat(asuint(y) ^ ((asuint(x) ^ asuint(y)) & -(u32(asuint(x) < asuint(y)))))",
    "rminp(x: f32 in 0..1e30, y: f32 in 0..1e30) = min(x, y)",
    "equiv mnp ~ rminp",
]))

w("12_floor_ceil.ucas", "\n".join([
    "trunc(x: f32) = asfloat(asuint(x) & 0xffc00000)",
    "equiv trunc ~ floor(x: f32)",
    "flp(x: f32 in 0..1e30) = asfloat(asuint(x) & 0xffc00000)",
    "rfp(x: f32 in 0..1e30) = floor(x)",
    "equiv flp ~ rfp",
    "ceilbit(x: f32 in 0..1e30) = asfloat((asuint(x) + 0x007fffff) & 0xffc00000)",
    "rceilp(x: f32 in 0..1e30) = ceil(x)",
    "equiv ceilbit ~ rceilp",
    "idem(a: u32, b: u32) = (a & b) + (a ^ b)",
    "idem2(a: u32, b: u32) = a | b",
    "equiv idem ~ idem2",
]))

w("13_exp_mant.ucas", "\n".join([
    "eb(x: f32) = (asuint(x) >> 23) & 0xff",
    "mb(x: f32) = asuint(x) & 0x7fffff",
    "sb(x: f32) = asuint(x) >> 31",
    "range eb",
    "range mb",
    "range sb",
    "table eb",
    "table mb",
    "recon(x: f32) = asfloat((asuint(x) & 0x807fffff) | 0x3f800000)",
    "range recon",
    "equiv recon ~ recon",
]))

w("14_order_tricks.ucas", "\n".join([
    "ou(x: f32 in 0..1e30, y: f32 in 0..1e30) = asuint(x) < asuint(y)",
    "of(x: f32 in 0..1e30, y: f32 in 0..1e30) = x < y",
    "equiv ou ~ of",
    "ou2(x: f32 in 0..1e30, y: f32 in 0..1e30) = asuint(x) <= asuint(y)",
    "of2(x: f32 in 0..1e30, y: f32 in 0..1e30) = x <= y",
    "equiv ou2 ~ of2",
    "negbit(x: f32) = asfloat(asuint(x) ^ 0x80000000)",
    "negref(x: f32) = -x",
    "equiv negbit ~ negref",
]))

w("16_error_domain.ucas", "\n".join([
    "nw(x: f32) = asfloat(0x5f3759df - (asuint(x) >> 1)) where x >= 1 && x <= 2",
    "nr(x: f32 in 1..2) = asfloat(0x5f3759df - (asuint(x) >> 1))",
    "tw(x: f32) = 1/sqrt(x) where x >= 1 && x <= 2",
    "domain nw",
    "domain nr",
    "error nw ~ 1/sqrt(x)",
    "error nr ~ 1/sqrt(x)",
    "error nw ~ tw",
]))

w("15_special_values.ucas", "\n".join([
    "show asfloat(0x7f800000)",
    "show asfloat(0xff800000)",
    "show asfloat(0x7f800001)",
    "show asfloat(0xff800001)",
    "show asfloat(0x00000001)",
    "show asfloat(0x80000001)",
    "show asfloat(0x00000000)",
    "show asfloat(0x80000000)",
    "show abs(asfloat(0xff800001))",
    "show asfloat(asuint(asfloat(0x7fc00001)))",
]))

# ---------------- CLI: magic ----------------
def magic_block(ds, typ):
    return "\n".join(f"magic {d} {typ}" for d in ds)

w("20_magic_u32_small.ucas", magic_block(range(1, 19), "u32"))
w("21_magic_i32_small.ucas", magic_block(range(1, 19), "i32"))
w("22_magic_tricky.ucas", magic_block(
    [7, 9, 11, 13, 25, 33, 49, 64, 65, 127, 128, 129, 255, 256,
     511, 512, 513, 641, 642, 997, 998, 999, 1000], "u32"))
w("23_magic_tricky_i32.ucas", magic_block(
    [7, 9, 11, 13, 25, 33, 49, 64, 65, 127, 128, 129, 255, 256,
     511, 512, 513, 641, 642, 997, 998, 999, 1000], "i32"))

# ---------------- MCP JSONL ----------------
def jsonl(name, calls):
    out = [
        '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}',
        '{"jsonrpc":"2.0","method":"notifications/initialized"}',
    ]
    for i, (tool, args) in enumerate(calls, start=1):
        import json
        obj = {"jsonrpc": "2.0", "id": i, "method": "tools/call",
               "params": {"name": tool, "arguments": args}}
        out.append(json.dumps(obj))
    w(name, "\n".join(out))

# MCP fit: define g then vary target/metric
fitdef = ('g(x: f32, K: u32) = asfloat(K - (asuint(x) >> 1))\n'
          'g0(x: f32) = asfloat(0x5f3759df - (asuint(x) >> 1))\n'
          'gA(x: f32, K: u32 in 0x5f375000..0x5f376000) = asfloat(K - (asuint(x) >> 1))\n'
          'gB(x: f32, K: u32 in 0x5f376000..0x5f377000) = asfloat(K - (asuint(x) >> 1))')
calls = [("ucas", {"source": fitdef})]
for tgt in ["1/sqrt(x)", "1/sqrt(real(x))"]:
    for metric in ["maxrel", "maxabs", "rms"]:
        calls.append(("analyze", {"op": "fit", "args": {"g": "g", "f": tgt, "metric": metric}}))
for gname in ["gA", "gB"]:
    calls.append(("analyze", {"op": "fit", "args": {"g": gname, "f": "1/sqrt(x)"}}))
jsonl("mcp_fit.jsonl", calls)

# MCP error sweep
errdefs = []
for i, K in enumerate([0x5F3759DF, 0x5F37642F, 0x5F376033, 0x5F375A86,
                       0x5F376000, 0x5F376433, 0x5F375C33, 0x5F375DDF]):
    errdefs.append(f"e{i}(x: f32) = asfloat(0x{K:08x} - (asuint(x) >> 1))")
calls = [("ucas", {"source": "\n".join(errdefs)})]
for i in range(8):
    calls.append(("analyze", {"op": "error", "args": {"g": f"e{i}", "f": "1/sqrt(x)"}}))
jsonl("mcp_error.jsonl", calls)

# MCP magic
calls = []
for d in list(range(1, 41)) + [49, 64, 65, 127, 128, 129, 512, 513, 641, 642, 997, 998, 999, 1000]:
    calls.append(("rings", {"op": "magic", "args": {"divisor": d, "type": "u32"}}))
for d in [3, 7, 9, 10, 1000]:
    calls.append(("rings", {"op": "magic", "args": {"divisor": d, "type": "i32"}}))
jsonl("mcp_magic.jsonl", calls)

# MCP bithacks
bitdefs = [
    "ab(x: f32) = asfloat(asuint(x) & 0x7fffffff)",
    "rf(x: f32) = abs(x)",
    "idb(x: f32) = asfloat(asuint(x))",
    "minb(x: f32, y: f32) = asfloat(asuint(y) xor ((asuint(x) xor asuint(y)) & -(u32(asuint(x) < asuint(y)))))",
    "rmin(x: f32, y: f32) = min(x, y)",
    "trunc(x: f32) = asfloat(asuint(x) & 0xffc00000)",
    "flref(x: f32) = floor(x)",
    "negbit(x: f32) = asfloat(asuint(x) xor 0x80000000)",
    "negref(x: f32) = -x",
]
calls = [("ucas", {"source": "\n".join(bitdefs), "assume": {"caret": "xor"}})]
for a, b, extra in [
    ("ab", "rf", {"ftz": False, "nanbits": False}),
    ("ab", "rf", {"ftz": False, "nanbits": True}),
    ("ab", "rf", {"ftz": True, "nanbits": False}),
    ("ab", "rf", {"ftz": True, "nanbits": True}),
    ("idb", "x", {"ftz": False, "nanbits": False}),
    ("idb", "x", {"ftz": False, "nanbits": True}),
    ("minb", "rmin", {"ftz": False, "nanbits": False}),
    ("trunc", "flref", {"ftz": False, "nanbits": False}),
    ("negbit", "negref", {"ftz": False, "nanbits": False}),
]:
    args = {"f": a, "g": b}
    args.update(extra)
    calls.append(("analyze", {"op": "equiv", "args": args}))
for a in ["ab", "minb", "negbit"]:
    calls.append(("analyze", {"op": "range", "args": {"f": a}}))
jsonl("mcp_bithacks.jsonl", calls)
