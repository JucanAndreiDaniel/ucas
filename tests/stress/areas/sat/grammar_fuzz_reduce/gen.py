#!/usr/bin/env python3
"""Type-directed well-typed ucas expression generator + differential sweep.

Deterministic: every random choice comes from ``random.Random(seed)``.

Usage:
    python3 gen.py --seed 0x5EED --count 240

Writes into this folder:
    corpus.jsonl       generated cases (AST + rendered ucas + mutant)
    sweep_cli.jsonl    per-case CLI equiv/range/wrap results under `timeout 15`
    sweep_mcp.jsonl    per-case MCP equiv/range/wrap results under `timeout 15`
    anomalies.jsonl    cases where CLI/MCP/independent Python oracle disagree

No other folder is touched.  All runs are bounded by `timeout`.
"""
import argparse
import copy
import json
import os
import re
import sys

from harness import (
    HERE, BIN, INT_TYPES, FLOAT_TYPES, is_int, is_signed, tw, tminmax,
    wrap, ev, UNDEF, corner_points, fingerprint, run_cli, run_mcp, mcp_call,
)

# ---------------------------------------------------------------------------
# AST constructors
# ---------------------------------------------------------------------------

def V(name, t):            return {"k": "var", "name": name, "t": t}
def C(v, t):               return {"k": "const", "v": v, "t": t}
def U(op, a, t):           return {"k": "un", "op": op, "a": a, "t": t}
def B(op, a, b, t):        return {"k": "bin", "op": op, "a": a, "b": b, "t": t}
def T(c, a, b):            return {"k": "tern", "c": c, "a": a, "b": b, "t": a["t"]}
def Cast(to, a):           return {"k": "cast", "to": to, "a": a, "t": to}
def BC(op, a):             return {"k": "bitcast", "op": op, "a": a,
                                   "t": "f32" if op == "asfloat" else ("u32" if op == "asuint" else "i32")}
def Match(var, arms, default, t):
    return {"k": "match", "var": var, "arms": arms, "default": default, "t": t}
def Table(vals, idx, t):   return {"k": "table", "vals": vals, "idx": idx, "t": t}


# ---------------------------------------------------------------------------
# generator
# ---------------------------------------------------------------------------

WIDE = [0x9E3779B9, 0x85EBCA6B, 0xC2B2AE35, 0x27D4EB2F, 0x7F4A7C15,
        0x2545F4914F6CDD1D, 0x9E3779B97F4A7C15, 0xD1B54A32D192ED03]

INT_BINS = (["+", "-", "*", "&", "|", "xor", "<<", ">>", "/", "%",
             "min", "max", "<", "<=", "==", "!="])
CMP_OPS = ("<", "<=", "==", "!=", ">", ">=")  # tuple: set order is hash-randomised


class Gen:
    def __init__(self, seed):
        self.rng = __import__("random").Random(seed)

    def const(self, t, wide=False):
        if t in FLOAT_TYPES:
            v = self.rng.choice([0.0, 0.5, 1.0, 1.5, 2.0, 3.5, -1.0, -0.5, 7.25])
            return C(v, t)
        lo, hi = tminmax(t)
        if wide:
            w = tw(t)
            cand = self.rng.choice(WIDE)
            v = cand & ((1 << w) - 1)
            if is_signed(t) and v >= 1 << (w - 1):
                v -= 1 << w
            return C(v, t)
        pool = [0, 1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 255, 256, lo, hi]
        if lo < 0:
            pool += [-1, -2, lo + 1, hi - 1]
        return C(self.rng.choice(pool), t)

    def gen(self, t, depth, vars):
        r = self.rng
        if depth <= 0:
            return self.leaf(t, vars)
        p = r.random()
        if p < 0.18:
            return self.leaf(t, vars)
        if p < 0.60:
            return self.bin(t, depth, vars)
        if p < 0.69:
            a = self.gen(t, depth - 1, vars)
            op = r.choice(["-", "abs"] if t in FLOAT_TYPES else ["~", "-", "abs"])
            return U(op, a, t)
        if p < 0.78:
            c = B(r.choice(list(CMP_OPS)), self.gen(t, depth - 1, vars),
                  self.gen(t, depth - 1, vars), t)
            return T(c, self.gen(t, depth - 1, vars), self.gen(t, depth - 1, vars))
        if p < 0.85 and is_int(t):
            others = [x for x in INT_TYPES if x != t]
            return Cast(r.choice(others), self.gen(t, depth - 1, vars))
        if p < 0.90:
            if t == "u32":
                # full bit-cast round trip, stays u32
                return BC("asuint", BC("asfloat", self.gen("u32", depth - 1, vars)))
            if t == "f32":
                return BC("asfloat", BC("asuint", self.gen("f32", depth - 1, vars)))
            # other types: fall through to bin
            return self.bin(t, depth, vars)
        if p < 0.96 and is_int(t) and tw(t) <= 16:
            return self.memory(t, depth, vars)
        return self.bin(t, depth, vars)

    def leaf(self, t, vars):
        r = self.rng
        if vars and r.random() < 0.62:
            name = r.choice(vars)
            return V(name, t)
        return self.const(t, wide=(r.random() < 0.12))

    def bin(self, t, depth, vars):
        r = self.rng
        if t in FLOAT_TYPES:
            op = r.choice(["+", "-", "*", "/", "min", "max"])
            a = self.gen(t, depth - 1, vars)
            b = self.const(t) if r.random() < 0.45 else self.gen(t, depth - 1, vars)
            if op == "/" and r.random() < 0.7:
                b = B("+", b, C(1.0, t), t)  # avoid div by zero mostly
            return B(op, a, b, t)
        op = r.choice(INT_BINS)
        a = self.gen(t, depth - 1, vars)
        if op in ("<<", ">>"):
            w = tw(t)
            if r.random() < 0.85:
                sh = B("&", Cast("u32", self.gen(t, depth - 1, vars)), C(w - 1, "u32"), "u32")
            else:
                sh = Cast("u32", V(r.choice(vars), t)) if vars else C(r.randrange(w), "u32")
            return B(op, a, sh, t)
        if op in ("/", "%"):
            if r.random() < 0.55:
                b = C(r.randint(1, 15), t)
            else:
                b = B("|", self.gen(t, depth - 1, vars), C(1, t), t)
            return B(op, a, b, t)
        if op == "*":
            if r.random() < 0.55:
                b = self.const(t, wide=(r.random() < 0.7))
            else:
                b = self.gen(t, depth - 1, vars)
            return B(op, a, b, t)
        b = self.gen(t, depth - 1, vars) if r.random() < 0.85 else self.const(t, wide=(r.random() < 0.15))
        return B(op, a, b, t)

    def memory(self, t, depth, vars):
        r = self.rng
        key = r.choice(vars) if vars else self.const(t)
        lo, hi = tminmax(t)
        n = r.choice([4, 8, 16])
        if kind := r.random():
            vals = [int(wrap(r.randint(lo, hi), t)) for _ in range(n)]
            idx = B("&", Cast("u32", self.gen(t, depth - 1, vars)), C(n - 1, "u32"), "u32")
            return Table(vals, idx, t)
        arms = []
        used = set()
        for _ in range(r.randint(2, 4)):
            v = r.randint(0, min(hi, 9))
            if v in used:
                continue
            used.add(v)
            arms.append((v, int(wrap(r.randint(lo, hi), t))))
        default = int(wrap(r.randint(lo, hi), t))
        return Match(key, arms, default, t)

    def mutate(self, node, t):
        """Type-preserving one-point mutation (deep copy)."""
        r = self.rng
        n = copy.deepcopy(node)

        def pick(cur):
            cand = []
            def walk(x):
                if x is not node and isinstance(x, dict) and "k" in x:
                    cand.append(x)
                for key in ("a", "b", "c", "idx"):
                    if isinstance(x.get(key), dict):
                        walk(x[key])
            walk(n)
            return r.choice(cand) if cand else n

        target = pick(n)
        k = target["k"]
        nt = target.get("t", t)
        if k == "bin":
            op = target["op"]
            pool = ["+", "-", "*", "/", "min", "max"] if nt in FLOAT_TYPES else INT_BINS
            target["op"] = r.choice([o for o in pool if o != op])
        elif k == "un":
            target["op"] = r.choice(["-", "abs"] if nt in FLOAT_TYPES else ["~", "-", "abs"])
        elif k == "const":
            v = target["v"]
            if isinstance(v, float):
                target["v"] = v + r.choice([-1.0, 0.5, 1.0, 2.0])
            else:
                dv = r.choice([-2, -1, 1, 2, 3, 7])
                target["v"] = int(wrap(v + dv, target["t"]))
        elif k == "cast":
            target["to"] = r.choice([x for x in INT_TYPES if x != target["to"]])
            target["t"] = target["to"]
        elif k == "bitcast":
            # changing the cast op would break the child/result types; use a
            # type-preserving arithmetic mutation instead
            return B("+", n, self.const(t), t)
        elif k == "table":
            if target["vals"]:
                i = r.randrange(len(target["vals"]))
                target["vals"][i] = int(wrap(target["vals"][i] + r.choice([-1, 1, 2]), t))
        else:
            # wrap the whole thing in +const to guarantee a change
            return B("+", n, self.const(t), t)
        return n


# ---------------------------------------------------------------------------
# rendering (fully parenthesised, explicit result types)
# ---------------------------------------------------------------------------

def lit(v, t):
    if t in FLOAT_TYPES:
        return f"{v!r}f" if t == "f32" else repr(float(v))
    if t in INT_TYPES and is_signed(t) and v < 0:
        return f"{t}(-{abs(v)})"
    if isinstance(v, int) and t in INT_TYPES and v > (1 << 63) - 1:
        return f"{t}(0x{v:X})"
    return f"{t}({v})"


def render(n):
    k = n["k"]
    t = n["t"]
    if k == "var":
        return n["name"]
    if k == "const":
        return lit(n["v"], t)
    if k == "un":
        return f"({n['op']}({render(n['a'])}))" if n["op"] == "abs" else f"({n['op']}{render(n['a'])})"
    if k == "bin":
        if n["op"] in ("min", "max"):
            return f"{n['op']}({render(n['a'])}, {render(n['b'])})"
        return f"({render(n['a'])} {n['op']} {render(n['b'])})"
    if k == "tern":
        return f"({render(n['c'])} ? {render(n['a'])} : {render(n['b'])})"
    if k == "cast":
        return f"{n['to']}({render(n['a'])})"
    if k == "bitcast":
        return f"{n['op']}({render(n['a'])})"
    if k == "match":
        arms = ", ".join(f"{p} => {lit(v, t)}" for p, v in n["arms"])
        return f"{t}(match {n['var']} {{ {arms}, _ => {lit(n['default'], t)} }})"
    if k == "table":
        vals = ", ".join(str(v) for v in n["vals"])
        return f"{t}([{vals}][{render(n['idx'])}])"
    raise ValueError(k)


def func_src(name, params, node):
    ps = ", ".join(f"{v}: {t}" for v, t in params)
    return f"{name}({ps}) = {render(node)}"


# ---------------------------------------------------------------------------
# explicit verified identities (seed cases for SAT soundness)
# ---------------------------------------------------------------------------

def identity_seeds():
    out = []

    def add(t, f, g):
        out.append({"t": t, "params": [("x", t), ("y", t)], "f": f, "g": g, "seed": True})

    for t in ("u8", "u16", "u32", "u64", "i8", "i32"):
        x, y = V("x", t), V("y", t)
        lo, hi = tminmax(t)
        w = tw(t)
        maxv = int(wrap(hi, t))
        add(t, B("+", x, x, t), B("<<", x, C(1, "u32"), t))
        add(t, B("-", x, x, t), C(0, t))
        add(t, B("xor", x, x, t), C(0, t))
        add(t, B("+", B("&", x, y, t), B("xor", x, y, t), t), B("|", x, y, t))
        add(t, B("xor", x, y, t), B("-", B("|", x, y, t), B("&", x, y, t), t))
        add(t, U("~", x, t), B("-", B("-", C(0, t), x, t), C(1, t), t))
        add(t, U("~", B("&", x, y, t), t), B("|", U("~", x, t), U("~", y, t), t))
        add(t, B("&", x, B("|", x, y, t), t), x)
        add(t, B("xor", B("xor", x, C(0x5A, t), t), C(0x5A, t), t), x)
        add(t, B("*", x, C(0, t), t), C(0, t))
        add(t, B("+", B("|", x, y, t), B("&", x, y, t), t), B("+", x, y, t))
        add(t, B("+", B("min", x, y, t), B("max", x, y, t), t), B("+", x, y, t))
        add(t, B("-", B("|", x, y, t), B("xor", x, y, t), t), B("&", x, y, t))
        if w > 1:
            k = min(w - 1, 4)
            add(t, B(">>", B("<<", x, C(k, "u32"), t), C(k, "u32"), t),
                B("&", x, C(int(wrap(hi >> k, t)), t), t))
    return out


# ---------------------------------------------------------------------------
# differential checking
# ---------------------------------------------------------------------------

def make_envs(t, rng, n_extra=10):
    pts = corner_points(t, rng)
    lo, hi = tminmax(t)
    extra = []
    for _ in range(n_extra):
        if t in FLOAT_TYPES:
            extra.append(float(rng.randint(-10000, 10000)) / 13.0)
        else:
            extra.append(rng.randint(lo, hi))
    pts += extra
    env1 = [{"x": p} for p in pts]
    env2 = [{"x": p, "y": q} for p in pts[:8] for q in pts[:8]]
    return env1, env2


def val_eq(a, b):
    """ucas equiv compares NaN==NaN as equal; Python does not."""
    if a is UNDEF or b is UNDEF:
        return a is b
    if isinstance(a, float) and isinstance(b, float):
        if a != a and b != b:
            return True
    return a == b


def python_expect(case, rng):
    """Independent expected equiv verdict + a Python counterexample env."""
    t = case["t"]
    params = case["params"]
    env1, env2 = make_envs(t, rng)
    envs = env2 if len(params) >= 2 else env1
    for env in envs:
        fv = ev(case["f"], env)
        gv = ev(case["g"], env)
        if fv is UNDEF:
            continue
        if gv is UNDEF or not val_eq(fv, gv):
            return False, env, fv, gv
    return True, None, None, None


def python_range_vals(case, rng):
    t = case["t"]
    params = case["params"]
    env1, env2 = make_envs(t, rng, n_extra=40)
    envs = env2 if len(params) >= 2 else env1
    vals = []
    for env in envs:
        v = ev(case["f"], env)
        if v is not UNDEF:
            vals.append(v)
    return vals


def parse_counterexample(s, params):
    """Parse 'x=1, y=2: 3 vs 4' into an env dict."""
    if not s:
        return None
    head = s.split(":", 1)[0]
    env = {}
    for part in head.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            env[k.strip()] = v.strip()
    if not env:
        return None
    return env


def env_from_strings(d, t):
    out = {}
    for k, v in d.items():
        try:
            out[k] = int(v, 0)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                return None
    return out


def classify_cli(case, result):
    out = result["out"]
    info = {"rc": result["rc"], "timed_out": result["timed_out"]}
    m = re.search(r"are equal on the domain", out)
    if m:
        info["equal"] = True
    m = re.search(r"differ at (\d+) points", out)
    if m:
        info["equal"] = False
        info["mismatch_points"] = int(m.group(1))
    m = re.search(r"e\.g\. ([^\n]+?): (\S+) vs (\S+)", out)
    if m:
        info["counterexample"] = m.group(1)
    m = re.search(r"range of \S+ -> (\w+):\s*\n\s*(-?\d+)\.\.(-?\d+)", out)
    if m:
        info["range"] = [int(m.group(2)), int(m.group(3))]
        info["range_type"] = m.group(1)
    m = re.search(r"end to end: equals the mathematical \(unbounded\) result everywhere", out)
    info["end_to_end_exact"] = bool(m)
    # Only real parse/engine errors, not innocuous text like "max abs error 0".
    info["has_error"] = bool(re.search(
        r"\.ucas:\d+:\d+: error:|^error(?: \(|$)|\bSegmentation\b|\bAborted\b|\bAssertion\b",
        out, re.M))
    info["crash"] = (result["rc"] not in (0, None)) or result["timed_out"] or info["has_error"]
    return info


def classify_mcp(case, result):
    info = {"rc": result["rc"], "timed_out": result["timed_out"], "calls": []}
    for msg in result["parsed"]:
        if msg.get("id", 0) == 0 or "result" not in msg:
            continue
        sc = msg["result"].get("structuredContent", {})
        rr = sc.get("result") or {}

        def cell(x):
            return x.get("value") if isinstance(x, dict) else x

        info["calls"].append({
            "id": msg.get("id"),
            "ok": sc.get("ok"),
            "kind": rr.get("kind"),
            "equal": rr.get("equal"),
            "method": rr.get("method"),
            "counterexample": rr.get("counterexample"),
            "range": [cell(rr.get("min")), cell(rr.get("max"))],
            "result": rr,
            "error": (sc.get("error") or {}).get("code") if isinstance(sc.get("error"), dict) else sc.get("error"),
            "isError": msg["result"].get("isError", False),
        })
    info["crash"] = (result["rc"] not in (0, None)) or result["timed_out"]
    return info


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="0x5EED")
    ap.add_argument("--count", type=int, default=240)
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--skip-sweep", action="store_true")
    args = ap.parse_args()
    seed = int(args.seed, 0)
    g = Gen(seed)
    arng = __import__("random").Random(seed ^ 0xA5A5)

    # 1. build cases --------------------------------------------------------
    cases = []
    for i, s in enumerate(identity_seeds()):
        c = dict(s)
        c["id"] = i
        c["name"] = f"c{i:04d}"
        cases.append(c)
    while len(cases) < args.count:
        i = len(cases)
        t = g.rng.choice(list(INT_TYPES) + list(FLOAT_TYPES))
        params = [("x", t), ("y", t)] if g.rng.random() < 0.75 else [("x", t)]
        f = g.gen(t, g.rng.randint(2, 4), [p for p, _ in params])
        gm = g.mutate(f, t)
        cases.append({"id": i, "name": f"c{i:04d}", "t": t, "params": params,
                      "f": f, "g": gm, "seed": False})
    cases = cases[:args.count]

    # 2. write corpus -------------------------------------------------------
    corpus_path = os.path.join(HERE, "corpus.jsonl")
    with open(corpus_path, "w") as fh:
        for c in cases:
            rec = {"id": c["id"], "name": c["name"], "t": c["t"], "params": c["params"],
                   "seed": c["seed"], "f_ast": c["f"], "g_ast": c["g"],
                   "f_src": render(c["f"]), "g_src": render(c["g"]),
                   "f_def": func_src(c["name"] + "f", c["params"], c["f"]),
                   "g_def": func_src(c["name"] + "g", c["params"], c["g"])}
            fh.write(json.dumps(rec) + "\n")

    srcs = []
    for c in cases:
        ps = ", ".join(f"{v}: {t}" for v, t in c["params"])
        srcs.append(
            f"{c['name']}f({ps}) = {render(c['f'])}\n"
            f"{c['name']}g({ps}) = {render(c['g'])}\n"
            f"equiv {c['name']}f {c['name']}g\n"
            f"range {c['name']}f\n"
            f"wrap {c['name']}f\n"
        )

    if args.skip_sweep:
        print(f"wrote {len(cases)} cases to {corpus_path}")
        return

    # 3. CLI sweep ----------------------------------------------------------
    cli_path = os.path.join(HERE, "sweep_cli.jsonl")
    anomalies = []
    counts = {"crash": 0, "hang": 0, "unsound_equal": 0, "wrong_refute": 0, "range_wrong": 0}
    with open(cli_path, "w") as fh:
        for c, src in zip(cases, srcs):
            res = run_cli(src, args.timeout, name="sw_" + c["name"])
            info = classify_cli(c, res)
            exp_equal, cex, fv, gv = python_expect(c, arng)
            rec = {"id": c["id"], "t": c["t"], "params": c["params"],
                   "seed": c["seed"], "info": info,
                   "py_equal": exp_equal, "py_cex": cex,
                   "f_src": render(c["f"]), "g_src": render(c["g"])}
            # cross-check equiv
            if exp_equal is False and info.get("equal") is True:
                counts["unsound_equal"] += 1
                anomalies.append({**rec, "kind": "UNSOUND_EQUAL"})
            if exp_equal is True and info.get("equal") is False:
                # verify ucas's reported counterexample in Python
                env = env_from_strings(parse_counterexample(info.get("counterexample", ""), c["params"]), c["t"])
                valid = None
                if env is not None:
                    a, b = ev(c["f"], env), ev(c["g"], env)
                    valid = (a is not UNDEF and b is not UNDEF and a != b)
                if valid is True:
                    anomalies.append({**rec, "kind": "FINGERPRINT_BLINDSPOT", "uc_cex_valid": True})
                else:
                    counts["wrong_refute"] += 1
                    anomalies.append({**rec, "kind": "WRONG_REFUTE", "uc_cex_valid": valid})
            # cross-check range with sampled Python values for small domains
            if "range" in info:
                vals = python_range_vals(c, arng)
                lo, hi = info["range"]
                bad = [v for v in vals if v < lo or v > hi]
                if bad:
                    counts["range_wrong"] += 1
                    anomalies.append({**rec, "kind": "RANGE_WRONG", "bad": bad[:4], "range": info["range"]})
            if res["timed_out"]:
                counts["hang"] += 1
                anomalies.append({**rec, "kind": "HANG"})
            elif info["crash"]:
                counts["crash"] += 1
                anomalies.append({**rec, "kind": "CRASH", "out_tail": res["out"][-600:]})
            fh.write(json.dumps(rec) + "\n")
            if (c["id"] + 1) % 40 == 0:
                print(f"CLI: {c['id']+1}/{len(cases)}", file=sys.stderr, flush=True)

    # 4. MCP sweep (batches of 20 cases) ------------------------------------
    mcp_path = os.path.join(HERE, "sweep_mcp.jsonl")
    with open(mcp_path, "w") as fh:
        for start in range(0, len(cases), 20):
            batch = cases[start:start + 20]
            defs = "\n".join(srcs[c["id"]].split("\n")[0] + "\n" + srcs[c["id"]].split("\n")[1] for c in batch)
            reqs = [mcp_call(1, "ucas", {"source": defs})]
            idn = 2
            for c in batch:
                for op in ("equiv", "range", "wrap"):
                    a = {"f": c["name"] + "f"}
                    if op == "equiv":
                        a["g"] = c["name"] + "g"
                        a["ftz"] = False
                        a["nanbits"] = False
                    reqs.append(mcp_call(idn, "analyze", {"op": op, "args": a}))
                    idn += 1
            res = run_mcp(reqs, args.timeout)
            info = classify_mcp(batch[0], res)
            fh.write(json.dumps({"batch": start, "n": len(batch), "info": info,
                                 "raw_tail": res["out"][-800:] if info["crash"] else ""}) + "\n")
            if info["crash"]:
                anomalies.append({"kind": "MCP_CRASH", "batch": start, "out_tail": res["out"][-800:]})
            print(f"MCP: batch {start}", file=sys.stderr, flush=True)

    with open(os.path.join(HERE, "anomalies.jsonl"), "w") as fh:
        for a in anomalies:
            fh.write(json.dumps(a, default=str) + "\n")

    print(json.dumps({"cases": len(cases), "cli_counts": counts,
                      "anomalies": len(anomalies)}, indent=2))


if __name__ == "__main__":
    main()
