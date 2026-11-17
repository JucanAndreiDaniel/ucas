#!/usr/bin/env python3
"""
Thesis-derived stress-case generator for ucas.

Area: thesis_fusion_enum
Based on PHD_RESEARCH.md sections "Solver / SAT / SMT testing" and distilled
ideas 1-3:

  1. Fusion pairs (Winterer Semantic Fusion / YinYang): one generator tree,
     two provably-equal emitters.  `equiv f g` must prove equal, and
     `error g ~ f` must be exactly 0 (the "differ finds nothing" oracle).
     Dependency-aware mutations (Mansur/STORM) apply the SAME rename to both
     sides, or fragment a seed tree and regenerate it.
  2. Exhaustive small-expression enumeration: every depth-1 expression over
     + - * & | xor << >> with terminals {x,y,0,1,2,3} on u4/u8, plus a
     bounded depth-2 family; run `range` and reflexive `equiv` on each.
  3. PerfFuzz-style pathological generation: products-under-xor chains that
     are known to drive the SAT step budget (cf. tests/satsteps.ucas); probe
     for NEW give-up boundaries on u32/u64.

The script is deterministic (fixed seed) and only writes files inside its own
folder.  It never rebuilds ucas.

Usage:
    python3 gen.py            # regenerate all .ucas / .jsonl inputs
    python3 gen.py --list     # print the number of generated queries
"""

from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 0xCA5
OPS_BINARY = ["+", "-", "*", "&", "|", "xor", "<<", ">>"]
COMMUTATIVE = {"+", "*", "&", "|", "xor"}
ASSOCIATIVE = {"+", "*", "&", "|", "xor"}
TERMS = ["x", "y", "0", "1", "2", "3"]


# ---------------------------------------------------------------------------
# A tiny expression-tree model with two provably-equal emitters.
# ---------------------------------------------------------------------------
class Node:
    __slots__ = ("op", "args", "tag")

    def __init__(self, op, *args, tag=None):
        self.op = op
        self.args = args
        self.tag = tag

    def __repr__(self):
        if not self.args:
            return self.op
        return "(%s %s)" % (self.op, " ".join(map(repr, self.args)))


def v(name):
    return Node(name)


def c(k):
    return Node(str(k))


def b(op, a, t):
    return Node(op, a, t)


def emit(node):
    """Canonical emitter: fully parenthesised prefix-free infix, left order."""
    if not node.args:
        return node.op
    parts = [emit(a) for a in node.args]
    if node.op in ("~", "-u"):
        return "(~%s)" % parts[0] if node.op == "~" else "(-%s)" % parts[0]
    if len(parts) == 1:
        return "(%s %s)" % (node.op, parts[0])
    return "(" + (" %s " % node.op).join(parts) + ")"


def emit_fused(node, transform):
    """Second emitter: apply ONE semantics-preserving rewrite at the root.

    Every transform below is an identity on uN/iN machine integers (wrapping
    arithmetic), so emit_fused(t) == emit(t) for all inputs by construction.
    """
    op, args = node.op, node.args
    if transform == "commute":
        assert op in COMMUTATIVE and len(args) == 2
        return emit(b(op, args[1], args[0]))
    if transform == "assoc_right":
        assert op in ASSOCIATIVE and len(args) == 2 and args[0].op == op
        a, bb, cc = args[0].args[0], args[0].args[1], args[1]
        return emit(b(op, a, b(op, bb, cc)))
    if transform == "identity_add":
        return emit(b("+", node, c(0)))
    if transform == "identity_xor":
        return emit(b("xor", node, c(0)))
    if transform == "identity_or":
        return emit(b("|", node, c(0)))
    if transform == "identity_mul":
        return emit(b("*", node, c(1)))
    if transform == "xor_cancel":
        k = 3
        return emit(b("xor", b("xor", node, c(k)), c(k)))
    if transform == "double_neg":
        return emit(Node("-u", Node("-u", node)))
    if transform == "demorgan":
        # ~(a & b) == (~a) | (~b)   and   ~(a | b) == (~a) & (~b)
        assert op == "~" and len(args) == 1 and args[0].op in ("&", "|")
        inner = args[0]
        flip = "|" if inner.op == "&" else "&"
        return emit(b(flip, Node("~", inner.args[0]), Node("~", inner.args[1])))
    if transform == "distribute":
        # a*(b+c) == a*b + a*c   (holds mod 2^n)
        assert op == "*" and len(args) == 2 and args[1].op == "+"
        a, bb, cc = args[0], args[1].args[0], args[1].args[1]
        return emit(b("+", b("*", a, bb), b("*", a, cc)))
    if transform == "absorb":
        # x & (x | y) == x
        assert op == "&"
        return emit(args[0])
    raise ValueError(transform)


def rename(node, a, b):
    """Dependency-aware mutation: swap variable names everywhere in a tree."""
    if node.op == a:
        return v(b)
    if node.op == b:
        return v(a)
    return Node(node.op, *[rename(x, a, b) for x in node.args], tag=node.tag)


def fragment(node):
    """STORM seed fragmentation: split a tree into its two children."""
    if len(node.args) == 2:
        return list(node.args)
    return [node]


# ---------------------------------------------------------------------------
# Fusion pair catalogue: (basename, type, tree, transform, params)
# ---------------------------------------------------------------------------
def fusion_catalogue():
    P = []

    # 1. commutativity
    for nm, ty, tree in [
        ("add", "u8", b("+", v("x"), v("y"))),
        ("mul", "u8", b("*", v("x"), v("y"))),
        ("and", "u8", b("&", v("x"), v("y"))),
        ("or", "u8", b("|", v("x"), v("y"))),
        ("xor", "u8", b("xor", v("x"), v("y"))),
        ("add16", "u16", b("+", v("x"), v("y"))),
    ]:
        P.append(("comm_" + nm, ty, tree, "commute"))

    # 2. associativity (chains of one associative op)
    for nm, ty, tree in [
        ("add", "u8", b("+", b("+", v("x"), v("y")), v("z"))),
        ("mul", "u8", b("*", b("*", v("x"), v("y")), v("z"))),
        ("xor", "u8", b("xor", b("xor", v("x"), v("y")), v("z"))),
        ("and", "u8", b("&", b("&", v("x"), v("y")), v("z"))),
        ("or", "u8", b("|", b("|", v("x"), v("y")), v("z"))),
    ]:
        P.append(("assoc_" + nm, ty, tree, "assoc_right"))

    # 3. distributivity / factoring
    for nm, ty, tree in [
        ("mul_add", "u8", b("*", v("x"), b("+", v("y"), v("z")))),
        ("and_or", "u8", b("&", v("x"), b("|", v("y"), v("z")))),
        ("or_and", "u8", b("|", v("x"), b("&", v("y"), v("z")))),
        ("sub_dist", "u8", b("*", b("-", v("x"), v("y")), v("z"))),
    ]:
        tr = "distribute"
        if nm == "and_or":
            tr = "distribute_and"
        if nm == "or_and":
            tr = "distribute_or"
        if nm == "sub_dist":
            tr = "distribute_right"
        P.append(("dist_" + nm, ty, tree, tr))

    # 4. identity insertion / cancellation
    for nm, ty, tree, tr in [
        ("add0", "u8", b("+", v("x"), v("y")), "identity_add"),
        ("xor0", "u8", b("xor", v("x"), v("y")), "identity_xor"),
        ("or0", "u8", b("|", v("x"), v("y")), "identity_or"),
        ("mul1", "u8", b("*", v("x"), v("y")), "identity_mul"),
        ("xorcancel", "u8", b("&", v("x"), v("y")), "xor_cancel"),
        ("dblneg", "u8", b("+", v("x"), v("y")), "double_neg"),
        ("dblneg_s", "i8", b("-", v("x"), v("y")), "double_neg"),
    ]:
        P.append(("ident_" + nm, ty, tree, tr))

    # 5. De Morgan and absorption
    for nm, ty, tree, tr in [
        ("demorgan_and", "u8", Node("~", b("&", v("x"), v("y"))), "demorgan"),
        ("demorgan_or", "u8", Node("~", b("|", v("x"), v("y"))), "demorgan"),
        ("absorb", "u8", b("&", v("x"), b("|", v("x"), v("y"))), "absorb"),
    ]:
        P.append(("bool_" + nm, ty, tree, tr))

    return P


def extra_transform(name, tree, tr):
    """Handle the boolean distributivity variants not covered generically."""
    op, args = tree.op, tree.args
    if tr == "distribute_and":
        a, bb, cc = args[0], args[1].args[0], args[1].args[1]
        return emit(b("|", b("&", a, bb), b("&", a, cc)))
    if tr == "distribute_or":
        a, bb, cc = args[0], args[1].args[0], args[1].args[1]
        return emit(b("&", b("|", a, bb), b("|", a, cc)))
    if tr == "distribute_right":
        a, bb, cc = args[0].args[0], args[0].args[1], args[1]
        return emit(b("-", b("*", a, cc), b("*", bb, cc)))
    return emit_fused(tree, tr)


def params_for(tree):
    names = []
    def walk(n):
        if not n.args and n.op in ("x", "y", "z"):
            if n.op not in names:
                names.append(n.op)
        for a in n.args:
            walk(a)
    walk(tree)
    return names


def sig(names, ty):
    return ", ".join("%s: %s" % (n, ty) for n in names)


def write(path, text):
    with open(os.path.join(HERE, path), "w") as f:
        f.write(text)


def gen_fusion_files():
    P = fusion_catalogue()
    groups = {
        "01_fusion_commute": [p for p in P if p[0].startswith("comm_")],
        "02_fusion_assoc": [p for p in P if p[0].startswith("assoc_")],
        "03_fusion_distribute": [p for p in P if p[0].startswith("dist_")],
        "04_fusion_identity": [p for p in P if p[0].startswith("ident_")],
        "05_fusion_boolean": [p for p in P if p[0].startswith("bool_")],
    }
    for gname, items in groups.items():
        # split into chunks of <=5 pairs to keep files small
        for ci in range(0, len(items), 5):
            chunk = items[ci:ci + 5]
            lines = ["# Fusion pairs (Semantic Fusion / YinYang): one generator tree,"]
            lines.append("# two provably-equal emitters. equiv must prove equal; error ~0.")
            idx = ci // 5 + 1
            for name, ty, tree, tr in chunk:
                f = emit(tree)
                g = extra_transform(name, tree, tr)
                names = params_for(tree)
                s = sig(names, ty)
                lines.append("f_%s(%s) = %s" % (name, s, f))
                lines.append("g_%s(%s) = %s" % (name, s, g))
                lines.append("equiv f_%s g_%s" % (name, name))
                lines.append("error g_%s ~ f_%s" % (name, name))
            suffix = "" if len(items) <= 5 else "_%d" % idx
            write(gname + suffix + ".ucas", "\n".join(lines) + "\n")

    # 6/7. dependency-aware mutations: swap x<->y in BOTH sides; fragment+regen
    lines = ["# Dependency-aware mutation (Mansur/STORM): swap x<->y in BOTH f and g;"]
    lines.append("# the fusion relation must survive the coherent rename.")
    for name, ty, tree, tr in P[:6]:
        names = params_for(tree)
        if "x" not in names or "y" not in names:
            continue
        f = emit(tree)
        g = extra_transform(name, tree, tr)
        f2 = emit(rename(tree, "x", "y"))
        g2 = extra_transform(name, rename(tree, "x", "y"), tr)
        s = sig(names, ty)
        lines.append("mf_%s(%s) = %s" % (name, s, f2))
        lines.append("mg_%s(%s) = %s" % (name, s, g2))
        lines.append("equiv mf_%s mg_%s" % (name, name))
        lines.append("error mg_%s ~ mf_%s" % (name, name))
    write("06_fusion_mutate_swap.ucas", "\n".join(lines) + "\n")

    lines = ["# STORM seed fragmentation: split a seed tree, regenerate a fused body."]
    lines.append("# Each piece is re-emitted through the same provably-equal transform.")
    frag_seeds = P[0], P[1], P[6], P[11], P[18]
    for k, (name, ty, tree, tr) in enumerate(frag_seeds):
        pieces = fragment(tree)
        names = params_for(tree)
        s = sig(names, ty)
        # regenerate: f = a op b ; g = transform applied, then re-fragmented
        f = emit(tree)
        g = extra_transform(name, tree, tr)
        lines.append("sf_%d(%s) = %s" % (k, s, f))
        lines.append("sg_%d(%s) = %s" % (k, s, g))
        lines.append("equiv sf_%d sg_%d" % (k, k))
        lines.append("error sg_%d ~ sf_%d" % (k, k))
    write("07_fusion_fragment_regen.ucas", "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Exhaustive small-expression enumeration
# ---------------------------------------------------------------------------
def enumerate_depth1():
    out = []
    for op in OPS_BINARY:
        for a in TERMS:
            for t in TERMS:
                out.append("(%s %s %s)" % (a, op, t))
    return out


def enumerate_depth2(limit=30):
    rng = random.Random(SEED + 1)
    out = []
    for op in OPS_BINARY:
        for _ in range(limit // len(OPS_BINARY) + 1):
            a = rng.choice(TERMS)
            t = rng.choice(TERMS)
            inner = "(%s %s %s)" % (rng.choice(TERMS), rng.choice(OPS_BINARY), rng.choice(TERMS))
            if rng.random() < 0.5:
                out.append("(%s %s %s)" % (inner, op, t))
            else:
                out.append("(%s %s %s)" % (a, op, inner))
    return out[:limit]


def gen_enum_files():
    d1 = enumerate_depth1()  # 8*36 = 288 expressions
    # 08: u4 range of the first 20 depth-1 exprs
    for fname, subset, ty in [
        ("08_enum_u4_depth1", d1[:20], "u4"),
        ("10_enum_u8_depth1", d1[40:60], "u8"),
    ]:
        lines = ["# Exhaustive enumeration: depth-1 expressions over + - * & | xor << >>."]
        for i, e in enumerate(subset):
            name = "e%d" % i
            lines.append("%s(x: %s, y: %s) = %s" % (name, ty, ty, e))
            lines.append("range %s" % name)
        write(fname + ".ucas", "\n".join(lines) + "\n")

    # 09: reflexive equiv (f == f) on depth-1 exprs -- must always prove equal
    lines = ["# Enumeration reflexivity: equiv e e must prove equal for every expression."]
    for i, e in enumerate(d1[80:95]):
        name = "r%d" % i
        lines.append("%s(x: u4, y: u4) = %s" % (name, e))
        lines.append("equiv %s %s" % (name, name))
    write("09_enum_reflex_equiv.ucas", "\n".join(lines) + "\n")

    # 11: depth-2 families, u4, range
    d2 = enumerate_depth2(18)
    lines = ["# Bounded depth-2 enumeration: range over u4."]
    for i, e in enumerate(d2):
        name = "d2_%d" % i
        lines.append("%s(x: u4, y: u4) = %s" % (name, e))
        lines.append("range %s" % name)
    write("11_enum_u4_depth2.ucas", "\n".join(lines) + "\n")

    # 12: perfFuzz pathological -- products under xor, cf. tests/satsteps.ucas
    lines = ["# PerfFuzz-style: products-under-xor chains. Find new SAT give-up boundaries."]
    cands = [
        ("p1", "u32", "((x*y)*z) ^ 5", "((y*x)*z) ^ 5"),
        ("p2", "u32", "((x*y)^5)*z", "((y*x)^5)*z"),
        ("p3", "u32", "((x*y)*(y*z)) ^ 0x5a", "((y*x)*(z*y)) ^ 0x5a"),
        ("p4", "u64", "(x*y) ^ 5", "(y*x) ^ 5"),
        ("p5", "u16", "((x*y)*z)^5", "((z*y)*x)^5"),
        ("p6", "u32", "((x + (y*3)) * (z + 7)) ^ 0xff", "((z*3 + x) * (7 + y)) ^ 0xff"),
    ]
    for nm, ty, f, g in cands:
        lines.append("pf_%s(x: %s, y: %s, z: %s) = %s" % (nm, ty, ty, ty, f))
        lines.append("pg_%s(x: %s, y: %s, z: %s) = %s" % (nm, ty, ty, ty, g))
        lines.append("equiv pf_%s pg_%s" % (nm, nm))
    write("12_perf_pathological.ucas", "\n".join(lines) + "\n")

    # 13: near-miss negative controls.  These pairs are NOT equal; ucas must
    # report "differ" with a real witness.  A false "equal" here is unsound.
    nearmiss = [
        ("n1", "u8", "(x - y)", "(y - x)"),
        ("n2", "u8", "((x - y) - z)", "(x - (y - z))"),
        ("n3", "u8", "((x + y) & z)", "((x & z) + (y & z))"),
        ("n4", "u8", "(x + (y & z))", "((x + y) & (x + z))"),
        ("n5", "u8", "((x xor y) + z)", "((x + z) xor (y + z))"),
        ("n6", "u8", "(~(x + y))", "((~x) + (~y))"),
        ("n7", "u8", "(x * (y xor z))", "((x * y) xor (x * z))"),
        ("n8", "u8", "((x << y) | (x >> z))", "((x << z) | (x >> y))"),
    ]
    lines = ["# Near-miss negative controls: these pairs are NOT equal."]
    lines.append("# equiv must report differ with a witness; a false 'equal' is unsound.")
    for nm, ty, f, g in nearmiss:
        lines.append("nf_%s(x: %s, y: %s, z: %s) = %s" % (nm, ty, ty, ty, f))
        lines.append("ng_%s(x: %s, y: %s, z: %s) = %s" % (nm, ty, ty, ty, g))
        lines.append("equiv nf_%s ng_%s" % (nm, nm))
    write("13_nearmiss_differ.ucas", "\n".join(lines) + "\n")


def gen_bulk_enum():
    """Bulk files for the exhaustive sweep (in _scratch, never goldens)."""
    scratch = os.path.join(HERE, "_scratch")
    os.makedirs(scratch, exist_ok=True)
    d1 = enumerate_depth1()  # all 288 depth-1 expressions
    with open(os.path.join(scratch, "all_depth1_u4.ucas"), "w") as f:
        f.write("# ALL 288 depth-1 expressions over + - * & | xor << >> on u4\n")
        for i, e in enumerate(d1):
            f.write("q%d(x: u4, y: u4) = %s\nrange q%d\n" % (i, e, i))
    # deterministic larger depth-2 family (400 exprs) for oracle sweep
    rng = random.Random(SEED + 7)
    d2 = []
    for _ in range(400):
        inner = "(%s %s %s)" % (rng.choice(TERMS), rng.choice(OPS_BINARY), rng.choice(TERMS))
        op = rng.choice(OPS_BINARY)
        t = rng.choice(TERMS)
        d2.append("(%s %s %s)" % (inner, op, t) if rng.random() < 0.5
                  else "(%s %s %s)" % (t, op, inner))
    with open(os.path.join(scratch, "all_depth2_u4.ucas"), "w") as f:
        f.write("# 400 deterministic depth-2 expressions on u4\n")
        for i, e in enumerate(d2):
            f.write("s%d(x: u4, y: u4) = %s\nrange s%d\n" % (i, e, i))
    with open(os.path.join(scratch, "all_depth1_u8.ucas"), "w") as f:
        f.write("# ALL 288 depth-1 expressions over + - * & | xor << >> on u8\n")
        for i, e in enumerate(d1):
            f.write("q%d(x: u8, y: u8) = %s\nrange q%d\n" % (i, e, i))


def gen_mcp_files():
    # MCP golden: fusion pair via analyze.equiv + analyze.error + analyze.range
    calls = []
    i = 1
    def add(method, params):
        nonlocal i
        obj = {"jsonrpc": "2.0", "id": i, "method": method, "params": params}
        calls.append(obj)
        i += 1

    add("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "stress", "version": "1"}})
    calls.insert(1, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    # renumber ids so notifications has no id and tools/call ids are unique
    # (the inserted notification has no id, fine)
    for nm, ty, f, g in [
        ("fx", "u8", "(x*y)^5", "(y*x)^5"),
        ("fa", "u8", "(x+y)+z", "x+(y+z)"),
        ("fd", "u8", "x*(y+z)", "x*y + x*z"),
    ]:
        prm = [{"name": "x", "type": ty}, {"name": "y", "type": ty},
               {"name": "z", "type": ty}]
        add("tools/call", {"name": "session", "arguments": {
            "op": "define", "args": {"name": "f_" + nm,
            "params": prm, "body": f}}})
        add("tools/call", {"name": "session", "arguments": {
            "op": "define", "args": {"name": "g_" + nm,
            "params": prm, "body": g}}})
        add("tools/call", {"name": "analyze", "arguments": {
            "op": "equiv", "args": {"f": "f_" + nm, "g": "g_" + nm}}})
        add("tools/call", {"name": "analyze", "arguments": {
            "op": "error", "args": {"g": "g_" + nm, "f": "f_" + nm}}})
    write("mcp_fusion_pairs.jsonl", "\n".join(
        __import__("json").dumps(o) for o in calls) + "\n")

    # MCP golden: enumeration range
    calls = []
    i = 1
    add("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "stress", "version": "1"}})
    calls.insert(1, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    prm = [{"name": "x", "type": "u4"}, {"name": "y", "type": "u4"}]
    for k, e in enumerate(["x+y", "x xor y", "x<<2", "(x & y) | (x xor y)"]):
        add("tools/call", {"name": "analyze", "arguments": {
            "op": "range", "args": {"f": {"body": e, "params": prm}}}})
    write("mcp_enum_range.jsonl", "\n".join(
        __import__("json").dumps(o) for o in calls) + "\n")


def count_queries():
    n = 0
    for fn in sorted(os.listdir(HERE)):
        if fn.endswith(".ucas"):
            n += sum(1 for ln in open(os.path.join(HERE, fn))
                     if ln.strip() and not ln.lstrip().startswith("#")) / 2
        elif fn.endswith(".jsonl"):
            n += sum(1 for ln in open(os.path.join(HERE, fn))
                     if '"tools/call"' in ln)
    return int(n)


def main():
    gen_fusion_files()
    gen_enum_files()
    gen_bulk_enum()
    gen_mcp_files()
    if "--list" in sys.argv:
        print("generated statements/query pairs: %d" % count_queries())
    else:
        print("wrote generated inputs to %s" % HERE)


if __name__ == "__main__":
    main()
