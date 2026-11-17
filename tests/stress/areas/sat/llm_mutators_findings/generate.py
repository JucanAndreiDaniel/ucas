#!/usr/bin/env python3
"""
llm_mutators_findings -- neighbourhood-mutation generator.

Turn the confirmed bug catalog (MASTER_FINDINGS.md + the per-area FINDINGS.md
files) into a generator.  Each "family" encodes one confirmed bug *shape*;
the generator applies that shape in a different command / type / frontend /
context, with a fixed seed so the whole corpus is reproducible.

You are an LLM in spirit only: the mutators are hand-distilled from the bug
catalog and then parameterised combinatorially.  The seed makes the sample
deterministic so two runs of `generate.py` are byte-identical.

Outputs (written next to this script):
  mutations.json   -- the full corpus of mutation specs
  MUTATIONS.md     -- a short human-readable family index

Run:
  python3 generate.py
  python3 run_corpus.py        # validates + executes every mutation
"""
import json
import os
import random

SEED = 20261116
HERE = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(SEED)

# width / bounds table used to build plausible domains
INT = {
    "u8": (0, 255), "u16": (0, 65535), "u32": (0, 2**32 - 1), "u64": (0, 2**64 - 1),
    "i8": (-128, 127), "i16": (-32768, 32767),
    "i32": (-2**31, 2**31 - 1), "i64": (-2**63, 2**63 - 1),
}
INTS = list(INT)
FLOATS = ["f32", "f64"]

mutations = []


def add(family, origin, shape, frontend, program, expect=""):
    """program is a str for 'cli' or a list of JSON-line strings for json/mcp."""
    mutations.append({
        "id": len(mutations) + 1,
        "family": family,
        "origin": origin,
        "shape": shape,
        "frontend": frontend,
        "program": program,
        "expect": expect,
    })


# ---------- JSON / MCP line builders ---------------------------------------

def jline(reqid, cmd, args):
    return json.dumps({"id": reqid, "cmd": cmd, "args": args}, separators=(",", ":"))


def mcp_lines(calls):
    """calls: list of (tool_name, arguments) pairs, already resolved for mode."""
    out = [
        json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "llm_mut", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
    ]
    for i, (name, args) in enumerate(calls, 1):
        out.append(json.dumps({"jsonrpc": "2.0", "id": i,
                               "method": "tools/call",
                               "params": {"name": name, "arguments": args}}))
    return out


OP_TOOL = {
    "equiv": "analyze", "error": "analyze", "range": "analyze",
    "domain": "analyze", "laplace_solve": "transforms",
    "english": "english", "ucas": "ucas",
}
DIRECT_TOOLS = {"english", "ucas"}


def mcp_call(op, args, flat):
    """Resolve one op into a (tool_name, arguments) pair for MCP / flat MCP."""
    if flat:
        return (op, args)                      # flat: tool name IS the op
    if op in DIRECT_TOOLS:
        return (op, args)
    return (OP_TOOL.get(op, "analyze"), {"op": op, "args": args})


def fobj(body, ty, where=None):
    o = {"body": body, "params": [{"name": "x", "type": ty}]}
    if where is not None:
        o["where"] = where          # NOTE: JSON equiv silently ignores this key
    return o


# ===========================================================================
# F1. equiv ignores G's where-clause / declared range / value set
#     origin: sat_ranges_where/07, type_mutation_diff, grammar_fuzz_reduce/01
# ===========================================================================
def fam_equiv_domain():
    names = [("f", "g"), ("a", "b"), ("fa", "ga"), ("p", "q"), ("F", "G"),
             ("lo", "hi"), ("u", "v"), ("id1", "id2")]
    for i in range(30):
        ty = rng.choice(["u8", "u16", "u32", "i8", "i16", "i32"])
        lo, hi = INT[ty]
        k = lo + max(1, (hi - lo) // rng.choice([2, 4, 8]))
        f, g = names[i % len(names)]
        body = rng.choice([
            "x", "x + 0", "x * 1", "x - 0", "x & x", "x | x", "x ^ x",
            "x + 1 - 1", "0 + x",
        ])
        style = i % 3
        if style == 0:
            gty, restr, note = ty, " where x < %d" % k, "where x<%d" % k
        elif style == 1:
            gty, restr, note = "%s in %d..%d" % (ty, lo, k), "", "in %d..%d" % (lo, k)
        else:
            vals = [lo, lo + 1, lo + 2, min(hi, lo + 3)]
            gty, restr, note = ty, " where x in {%s}" % (
                ",".join(str(v) for v in vals)), "in set"
        fdecl = "%s(x: %s) = %s" % (f, ty, body)
        gdecl = "%s(x: %s) = %s%s" % (g, gty, body, restr)
        op = "~" if i % 2 else ""
        prog = "%s\n%s\nequiv %s %s%s\n" % (fdecl, gdecl, f, op, g)
        add("equiv_domain", "sat_ranges_where/07;type_mutation_diff",
            "F full / G %s, equiv(F,G)" % note, "cli", prog,
            "equal")
    # frontend variants: the 'where' object key is silently ignored in JSON equiv
    for i in range(8):
        ty = rng.choice(["u8", "u16", "i8", "i32"])
        lo, hi = INT[ty]
        k = lo + max(1, (hi - lo) // 4)
        f = fobj("x", ty)
        g = fobj("x", ty, where="x < %d" % k)
        prog = [jline(1, "equiv", {"f": f, "g": g})]
        fe = ["json", "mcp", "mcp_flat", "mcp"][i % 4]
        if fe != "json":
            prog = mcp_lines([mcp_call("equiv", {"f": f, "g": g},
                                       flat=(fe == "mcp_flat"))])
        add("equiv_domain", "sat_ranges_where/07", "JSON equiv ignores object 'where'",
            fe, prog, "equal")


# ===========================================================================
# F2. true real/float identity rejected with identical-printing counterexample
#     origin: prove_symbolic/08
# ===========================================================================
def fam_real_identity():
    identities = [
        ("(x+y)^2", "x^2 + 2*x*y + y^2"),
        ("(x-y)^2", "x^2 - 2*x*y + y^2"),
        ("x^2 - 1", "(x-1)*(x+1)"),
        ("(x+y)^3", "x^3 + 3*x^2*y + 3*x*y^2 + y^3"),
        ("(a+b)*(a-b)", "a^2 - b^2"),
        ("sin(x)^2 + cos(x)^2", "1"),
        ("(x+1)^2", "x^2 + 2*x + 1"),
        ("2*x + 3*x", "5*x"),
    ]
    for i in range(24):
        l, r = identities[i % len(identities)]
        ty = rng.choice(["real", "real", "f32", "f64"])
        vn = "a, b" if "a" in l and "b" in l else "x, y"
        f = "fn(i: %s, j: %s) = " % (ty, ty)
        # rebuild with explicit typed params x,y / a,b
        p1, p2 = (["a", "b"] if vn == "a, b" else ["x", "y"])
        l2 = l.replace("a", p1).replace("b", p2)
        r2 = r.replace("a", p1).replace("b", p2)
        decl = "fn(%s: %s, %s: %s) = %s\ngn(%s: %s, %s: %s) = %s\n" % (
            p1, ty, p2, ty, l2, p1, ty, p2, ty, r2)
        prog = decl + "equiv fn ~ gn\n"
        fe = "cli"
        if i % 6 == 5:
            objs = [jline(1, "equiv", {"f": {"body": l2, "params": [
                {"name": p1, "type": ty}, {"name": p2, "type": ty}]},
                "g": {"body": r2, "params": [
                    {"name": p1, "type": ty}, {"name": p2, "type": ty}]}})]
            prog = objs[0]
            fe = "json"
        add("real_identity", "prove_symbolic/08",
            "identity %s == %s over %s" % (l, r, ty), fe, prog, "equal (identity)")


# ===========================================================================
# F3. cast coercion: equiv proves uN(x)==iM(x) on signed input (always-UB-ish)
#     origin: grammar_fuzz_reduce/01, type_coercion/06
# ===========================================================================
def fam_cast_coercion():
    pairs = [
        ("i8", "u8", "i32"), ("i8", "u16", "i64"), ("i8", "i16", "i32"),
        ("i16", "u16", "i32"), ("i16", "u8", "i32"), ("i32", "u32", "i64"),
        ("i8", "u8", "u16"), ("i16", "i32", "u32"), ("i8", "i8", "u8"),
    ]
    for i in range(18):
        src, t1, t2 = pairs[i % len(pairs)]
        body1 = rng.choice(["%s(x)" % t1, "%s(x) + 0" % t1])
        body2 = rng.choice(["%s(x)" % t2, "0 + %s(x)" % t2])
        prog = "a(x: %s) = %s\nb(x: %s) = %s\nequiv a ~ b\n" % (
            src, body1, src, body2)
        fe = "cli"
        if i % 6 == 4:
            fe = "json"
            prog = jline(1, "equiv", {"f": {"body": body1, "params": [{"name": "x", "type": src}]},
                                      "g": {"body": body2, "params": [{"name": "x", "type": src}]}})
        add("cast_coercion", "grammar_fuzz_reduce/01;type_coercion/06",
            "equiv %s(x) vs %s(x) on %s" % (t1, t2, src), fe, prog, "differ")


# ===========================================================================
# F4. domain says "total" while reporting 0 defined points
#     origin: type_coercion/domain, sat_crypto_circuits/sh(x)=x<<32
# ===========================================================================
def fam_domain_total():
    specs = [
        ("u16", "x << 16"), ("u16", "x << 20"), ("u32", "x << 32"),
        ("u32", "x >> 32"), ("u64", "x << 64"), ("u16", "x / (x - x)"),
        ("u8", "x / (x - x)"), ("i8", "x / (x - x)"), ("u32", "x % (x - x)"),
    ]
    for i in range(14):
        ty, body = specs[i % len(specs)]
        prog = "sh(x: %s) = %s\ndomain sh\n" % (ty, body)
        add("domain_total", "type_coercion;sat_crypto_circuits",
            "domain of %s on %s" % (body, ty), "cli", prog, "total-while-0-defined")


# ===========================================================================
# F5. range excludes a reachable point (point spike / sampled corner)
#     origin: fp_edge, grammar_fuzz_reduce, sat_ranges_where
# ===========================================================================
def fam_range_spike():
    spikes = ["1e30", "1e10", "12345", "f32(3.14)", "-1e20"]
    for i in range(18):
        ty = rng.choice(FLOATS)
        val = spikes[i % len(spikes)]
        cmp = rng.choice(["f32(0.1)", "f32(0.5)", "f64(0.25)", "f32(1.0)"])
        body = "x == %s ? %s : 0" % (cmp, val)
        prog = "sp(x: %s in 0..1) = %s\nrange sp\n" % (ty, body)
        if i % 6 == 5:
            # bitwise corner on a narrow integer type
            ity = rng.choice(["i16", "u16"])
            body2 = "x & y"
            prog = "c(x: %s, y: %s) = %s\nrange c\n" % (ity, ity, body2)
        add("range_spike", "fp_edge;grammar_fuzz_reduce",
            "range of spike/corner %s" % body, "cli", prog, "reachable point")


# ===========================================================================
# F6. mixed signed/unsigned reinterpretation / narrowing
#     origin: type_coercion/mixed
# ===========================================================================
def fam_mixed_sign():
    pairs = [("u8", "i8"), ("i8", "u8"), ("i64", "u64"), ("u16", "i16"),
             ("i32", "u32"), ("u32", "i32")]
    ops = ["+", "-", "*", "<", ">", "==", "<="]
    for i in range(14):
        t1, t2 = pairs[i % len(pairs)]
        op = ops[i % len(ops)]
        a, b = "1", "2"
        if t1.startswith("i"):
            a = "-1"
        if t2.startswith("i"):
            b = "-2"
        prog = "show %s(%s) %s %s(%s)\n" % (t1, a, op, t2, b)
        add("mixed_sign", "type_coercion",
            "%s(%s) %s %s(%s)" % (t1, a, op, t2, b), "cli", prog, "note: mixing")


# ===========================================================================
# F7. symmetry claims both symmetric and antisymmetric
#     origin: fp_edge/symmetry
# ===========================================================================
def fam_symmetry():
    funcs = ["1e-20*(x + y)", "1e-30*(x - y)", "1e-25*x*y",
             "1e-20*(x^2 + y^2)", "1e-20*x", "1e-15*(x + y)"]
    for i in range(12):
        f = funcs[i % len(funcs)]
        ty = rng.choice(["real", "f32"])
        prog = "sy(x: %s, y: %s) = %s\nsymmetry sy\n" % (ty, ty, f)
        if i % 4 == 3:
            prog = "identify %s\n" % f
        add("symmetry_both", "fp_edge",
            "symmetry/identify of %s" % f, "cli", prog, "both yes")


# ===========================================================================
# F8. powerseries multiplies the series by the variable
#     origin: transforms_ode_series/powerseries
# ===========================================================================
def fam_powerseries():
    funcs = ["exp(x)", "sin(x)", "cos(x)", "log(1 + x)", "1/(1 - x)",
             "exp(-x)", "1/(1 + x)"]
    for i in range(12):
        f = funcs[i % len(funcs)]
        order = rng.choice([6, 8, 10])
        prog = "powerseries %s x\ntaylor %s x order %d\n" % (f, f, order)
        add("powerseries_var", "transforms_ode_series",
            "powerseries %s" % f, "cli", prog, "e^x*x shape")


# ===========================================================================
# F9. laplace_solve / zsolve drops ';'-separated initial conditions
#     origin: transforms_ode_series
# ===========================================================================
def fam_laplace():
    cases = [
        ("y' = y", "y(0) = 1"), ("y' = 2*y", "y(0) = 3"),
        ("y' = -y", "y(0) = 5"), ("y'' = y", "y(0) = 1, y'(0) = 0"),
        ("y' = y + 1", "y(0) = 0"),
    ]
    for i in range(10):
        eq, ic = cases[i % len(cases)]
        s = "%s; %s" % (eq, ic)
        args = {"equations": s}
        fe = "mcp_flat" if i % 2 else "mcp"
        prog = mcp_lines([mcp_call("laplace_solve", args, flat=(i % 2 == 1))])
        add("laplace_ic", "transforms_ode_series",
            "laplace_solve '%s'" % s, fe, prog, "IC dropped")


# ===========================================================================
# F10. stale it/that auto-names across a multi-request session
#     origin: type_mutation_diff/bug_zeroparam_stale, nlp_session_state
# ===========================================================================
def fam_stale_autoname():
    bodies = ["3 ^ 5 & 1", "x << y", "x + 1", "a*b + c", "(x+y)^2", "x^y"]
    for i in range(12):
        b1 = bodies[i % len(bodies)]
        b2 = b1                       # genuine self-comparison (the bug shape)
        ty = rng.choice(["u8", "i8", "u16"])
        reqs = [
            ("equiv", {"f": {"body": "x << y", "params": [
                {"name": "x", "type": ty}, {"name": "y", "type": ty}]},
                "g": {"body": "x >> y", "params": [
                    {"name": "x", "type": ty}, {"name": "y", "type": ty}]}}),
            ("equiv", {"f": {"body": b1, "params": []},
                       "g": {"body": b2, "params": []}}),
        ]
        fe = ["json", "mcp", "mcp_flat"][i % 3]
        if fe == "json":
            prog = [jline(1, reqs[0][0], reqs[0][1]),
                    jline(2, reqs[1][0], reqs[1][1])]
        else:
            prog = mcp_lines([mcp_call(op, args, flat=(fe == "mcp_flat"))
                              for op, args in reqs])
        add("stale_autoname", "type_mutation_diff",
            "zero-param equiv after prior equiv (%s / %s)" % (b1, b2),
            fe, prog, "equal:false self-comparison")


# ===========================================================================
# F11. English sorts 'from A to B' ascending -> integral bound flip
#     origin: nlp_calculus
# ===========================================================================
def fam_english_boundflip():
    funcs = ["x", "x squared", "x cubed", "sin x", "exp x", "x + 1"]
    intervals = [("pi", "0"), ("1", "-1"), ("2", "0"), ("5", "1"),
                 ("10", "3"), ("0.5", "-0.5")]
    for i in range(18):
        f = funcs[i % len(funcs)]
        a, b = intervals[i % len(intervals)]
        q = "the integral of %s from %s to %s" % (f, a, b)
        if i % 5 == 4:
            q = "integrate %s from %s to %s" % (f, a, b)
        fe = "cli"
        if i % 6 == 5:
            fe = "mcp"
            prog = mcp_lines([("english", {"text": q})])
        else:
            prog = q + "\n"
        add("english_boundflip", "nlp_calculus",
            "English integral %s to %s" % (a, b), fe, prog, "ascending flip")


# ===========================================================================
# F12. vacuous 'equal' proof on a domain with zero defined points
#     origin: type_mutation_diff, sat_crypto_circuits
# ===========================================================================
def fam_vacuous():
    bads = ["x / (y - y)", "x / (x - x)", "x % (y - y)", "x / 0",
            "1 / (y*y - y*y)"]
    for i in range(10):
        ty = rng.choice(["u8", "u16", "i8"])
        bad = bads[i % len(bads)]
        prog = "d(x: %s, y: %s) = %s\ne(x: %s, y: %s) = x\ndomain d\nequiv d e\n" % (
            ty, ty, bad, ty, ty)
        add("vacuous", "type_mutation_diff;sat_crypto_circuits",
            "equiv on empty domain (%s)" % bad, "cli", prog, "vacuous equal")


# ===========================================================================
# F13. deep nesting -> parser stack overflow (only reaches parse errors/crash)
#     origin: parser_json_fuzz, resource_limits, fp_edge
# ===========================================================================
def fam_deep_nesting():
    kinds = ["paren", "minus", "sqrt", "abs"]
    for i in range(10):
        kind = kinds[i % len(kinds)]
        n = rng.choice([1100, 1400, 1600])
        if kind == "paren":
            src = "show " + "(" * n + "1+2" + ")" * n
        elif kind == "minus":
            src = "show " + "-" * n + "1"
        elif kind == "sqrt":
            src = "show " + "sqrt(" * n + "1" + ")" * n
        else:
            src = "show " + "abs(" * n + "1" + ")" * n
        fe = "cli" if i % 2 else "mcp"
        if fe == "mcp":
            prog = mcp_lines([("ucas", {"source": src})])
        else:
            prog = src + "\n"
        add("deep_nesting", "parser_json_fuzz;resource_limits;fp_edge",
            "%s nesting depth %d" % (kind, n), fe, prog, "parse-error/crash")


# ===========================================================================
# F14. NLP number / comparison misparse
#     origin: nlp_numbers, nlp_arith, nlp_ambiguity
# ===========================================================================
def fam_nlp_number():
    queries = [
        "is 1 < 2 < 3?", "is 3 > 2 > 1?", "is 1 < 2 < 3 < 4?",
        "what is one trillion?", "what is one billion billion?",
        "7/8 of 64", "what is 2 and 1/2?", "is x always greater than 0 for u8 x?",
        "is x always less than 100 for u8 x?", "wrap of 5", "make it faster",
        "what is one thousand?", "what is ten trillion?",
    ]
    for i in range(14):
        q = queries[i % len(queries)]
        fe = "cli"
        prog = q + "\n"
        if i % 5 == 4:
            fe = "mcp"
            prog = mcp_lines([("english", {"text": q})])
        add("nlp_number", "nlp_numbers;nlp_arith;nlp_ambiguity",
            "English '%s'" % q, fe, prog, "NLP misparse")


for fn in (fam_equiv_domain, fam_real_identity, fam_cast_coercion,
           fam_domain_total, fam_range_spike, fam_mixed_sign, fam_symmetry,
           fam_powerseries, fam_laplace, fam_stale_autoname,
           fam_english_boundflip, fam_vacuous, fam_deep_nesting, fam_nlp_number):
    fn()

with open(os.path.join(HERE, "mutations.json"), "w") as fh:
    json.dump(mutations, fh, indent=1)

# human-readable family index
from collections import Counter
c = Counter(m["family"] for m in mutations)
lines = ["# Mutation corpus index", "",
         "Deterministic seed `%d`. %d mutations total." % (SEED, len(mutations)),
         "", "| family | count | origin |", "|---|---:|---|"]
origins = {}
for m in mutations:
    origins[m["family"]] = m["origin"]
for fam in sorted(c):
    lines.append("| %s | %d | %s |" % (fam, c[fam], origins[fam]))
lines.append("")
with open(os.path.join(HERE, "MUTATIONS.md"), "w") as fh:
    fh.write("\n".join(lines))

print("generated %d mutations across %d families (seed %d)" % (
    len(mutations), len(c), SEED))
