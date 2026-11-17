#!/usr/bin/env python3
"""Stress harness for integer division/modulo semantics.

Talks to `ucas --mcp` over stdio, asks analyze table/range/domain/wrap/equiv,
and compares each evaluated value against a Python oracle implementing
C/CUDA truncating division and two's-complement wrapping.

This is a tool, not a golden test.  Run: python3 verify.py
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
import json, subprocess, sys, re, itertools

BIN = str(_REPO_ROOT / "ucas")

class MCP:
    def __init__(self):
        self.p = subprocess.Popen([BIN, "--mcp"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, bufsize=1)
        self.n = 0
        self.req({"method": "initialize", "params": {"protocolVersion": "2025-06-18",
                  "capabilities": {}, "clientInfo": {"name": "divstress", "version": "1"}}},
                 notify=False)
        self.req({"method": "notifications/initialized"}, notify=True)

    def req(self, obj, notify=True):
        if not notify:
            self.n += 1
            obj["id"] = self.n
        line = json.dumps({"jsonrpc": "2.0", **obj}) + "\n"
        self.p.stdin.write(line); self.p.stdin.flush()
        if notify:
            return None
        while True:
            out = self.p.stdout.readline()
            if not out:
                return {"error": {"message": "EOF"}}
            try:
                r = json.loads(out)
            except Exception:
                continue
            if r.get("id") == self.n:
                return r

    def call(self, tool, args):
        self.n += 1
        req = {"jsonrpc": "2.0", "id": self.n, "method": "tools/call",
               "params": {"name": tool, "arguments": args}}
        self.p.stdin.write(json.dumps(req) + "\n"); self.p.stdin.flush()
        while True:
            out = self.p.stdout.readline()
            if not out:
                return {"ok": False, "error": {"message": "EOF"}}
            try:
                r = json.loads(out)
            except Exception:
                continue
            if r.get("id") == self.n:
                sc = r.get("result", {}).get("structuredContent")
                if sc is not None:
                    return sc
                return r.get("result", {"ok": False, "error": {"message": "no structuredContent"}})

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=3)
        except Exception:
            self.p.kill()

def fn(body, params):
    return {"body": body, "params": [{"name": n, "type": t} if rng is None else
            {"name": n, "type": t, "range": rng} for (n, t, rng) in params]}

# ---- Python oracle -------------------------------------------------------
def info(t):
    if t[0] == 'u':
        n = int(t[1:]); return (True, n, 0, (1 << n) - 1)
    if t[0] == 'i':
        n = int(t[1:]); return (False, n, -(1 << (n-1)), (1 << (n-1)) - 1)
    raise ValueError(t)

def wrap(v, t):
    unsigned, n, lo, hi = info(t)
    m = 1 << n
    v = v % m
    if not unsigned and v >= (1 << (n-1)):
        v -= m
    return v

def cdiv(a, b):
    # truncating division toward zero
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q

def crem(a, b):
    return a - cdiv(a, b) * b

def oracle_const(t, op, a, d):
    """F(x: t) = x op d, with constant d coerced to t (wrapping)."""
    dd = wrap(d, t)
    if dd == 0:
        return None
    a = wrap(a, t)
    if op == '/':
        return wrap(cdiv(a, dd), t)
    else:
        return wrap(crem(a, dd), t)

def parse_at(s):
    # 'x=-3' -> -3 ; 'x=-3, y=2' -> (-3,2)
    vals = [int(v) for k, v in re.findall(r'([A-Za-z_]\w*)=(-?\d+)', s)]
    return tuple(vals)

def fmt_ranges(t, pts):
    """Group sorted points into 'lo..hi' ranges."""
    pts = sorted(set(pts))
    if not pts: return ""
    out = []; s = p = pts[0]
    for v in pts[1:]:
        if v == p + 1:
            p = v
        else:
            out.append(f"{s}..{p}" if s != p else str(s))
            s = p = v
    out.append(f"{s}..{p}" if s != p else str(s))
    return ", ".join(out)

# ---- case categories -----------------------------------------------------
def const_cases():
    cases = []
    ucases = {
        'u8':  [1,2,3,4,5,7,8,10,16,17,31,32,64,85,100,127,128,254,255,256,300],
    }
    icases = {
        'i8':  [1,2,3,4,5,7,8,10,-1,-2,-3,-7,-127,-128,127,200,-200],
    }
    for t, ds in ucases.items():
        lo, hi = info(t)[2], info(t)[3]
        for d in ds:
            for op in ('/', '%'):
                body = f"x{op}{d}"
                cases.append((f"const_{t}_{op}_{d}", body, [("x", t, None)],
                              lambda a, t=t, op=op, d=d: oracle_const(t, op, a, d),
                              None, True))
    for t, ds in icases.items():
        for d in ds:
            for op in ('/', '%'):
                body = f"x{op}({d})" if d < 0 else f"x{op}{d}"
                cases.append((f"const_{t}_{op}_{d}", body, [("x", t, None)],
                              lambda a, t=t, op=op, d=d: oracle_const(t, op, a, d),
                              None, True))
    return cases

def sampled_const_cases():
    """Larger types with explicit interesting point sets."""
    cases = []
    sets = {
        'u16': [0,1,2,3,7,15,16,31,32,100,255,256,1000,32767,32768,65534,65535],
        'u32': [0,1,2,3,7,15,16,31,32,1000,65535,65536,0x7ffffffe,0x7fffffff,0x80000000,0xfffffffe,0xffffffff],
        'u64': [0,1,2,3,7,15,16,31,32,1000,65535,65536,(1<<31)-1,1<<31,(1<<63)-2,
                (1<<63)-1],
        'i16': [-32768,-32767,-100,-7,-3,-2,-1,0,1,2,3,7,100,32766,32767],
        'i32': [-(1<<31),-(1<<31)+1,-1000,-7,-3,-2,-1,0,1,2,3,7,1000,(1<<31)-2,(1<<31)-1],
        'i64': [-(1<<63),-(1<<63)+1,-1000,-7,-3,-2,-1,0,1,2,3,7,1000,(1<<63)-2,(1<<63)-1],
    }
    for t, pts in sets.items():
        lo, hi = min(pts), max(pts)
        rng = [lo, hi]
        for d in [2,3,7,10,-3,256]:
            for op in ('/', '%'):
                txt = f"x{op}({d})" if d < 0 else f"x{op}{d}"
                # oracle with explicit points only
                cases.append((f"samp_{t}_{op}_{d}", txt, [("x", t, rng)],
                              lambda a, t=t, op=op, d=d: oracle_const(t, op, a, d),
                              pts, False))
    return cases

def identity_cases():
    """equiv identities; expected truth computed by brute force on small domain."""
    cases = []
    T = 'i8'
    dom = list(range(-128,128))
    def ev(expr, a):
        # evaluate simple ucas expression on a single i8 value with C semantics
        # handled per-case below via lambdas
        raise NotImplementedError
    identities = [
        ("divmod_ident", "x/3*3 + x%3", "x", lambda a: wrap(wrap(cdiv(wrap(a,T),3),T)*3 + wrap(crem(wrap(a,T),3),T),T) == wrap(a,T)),
        ("divmod_ident7", "x*0 + (x/7)*7 + x%7", "x", lambda a: wrap(wrap(cdiv(wrap(a,T),7),T)*7 + wrap(crem(wrap(a,T),7),T),T) == wrap(a,T)),
        ("div_floor", "x/3", "floor(x/3)", lambda a: wrap(cdiv(a,3),T) == wrap(cdiv(a,3),T)),
        ("mod_nonneg", "x%3 >= 0", "1", lambda a: (1 if crem(a,3)>=0 else 0) == 1),
        ("neg_div", "(-x)/3", "-(x/3)", lambda a: wrap(cdiv(wrap(-a,T),3),T) == wrap(-wrap(cdiv(a,3),T),T)),
        ("neg_mod", "(-x)%3", "-(x%3)", lambda a: wrap(crem(wrap(-a,T),3),T) == wrap(-wrap(crem(a,3),T),T)),
        ("div2_shift", "x/2", "x>>1", lambda a: cdiv(a,2) == (a>>1)),
        ("div_pow2_mask", "x%8", "x&7", lambda a: crem(a,8) == (a & 7)),
        ("div_self", "x/x", "1", lambda a: None if a==0 else (1 if cdiv(a,a)==1 else 0)),
        ("mod_self", "x%x", "0", lambda a: None if a==0 else (crem(a,a)==0)),
        ("div_one", "x/1", "x", lambda a: cdiv(a,1)==a),
        ("mod_one", "x%1", "0", lambda a: crem(a,1)==0),
        ("div_minus1", "x/-1", "-x", lambda a: wrap(cdiv(a,-1),T) == wrap(-a,T)),
        ("mod_minus1", "x%-1", "0", lambda a: crem(a,-1)==0),
        ("div_assoc", "x/3/5", "x/15", lambda a: cdiv(cdiv(a,3),5) == cdiv(a,15)),
        ("div_mul_cancel", "(x*3)/3", "x", lambda a: wrap(cdiv(wrap(a*3,T),3),T)==a),
        ("add_mul_div", "(x+3*5)/3", "x/3+5", lambda a: wrap(cdiv(wrap(a+15,T),3),T)==wrap(wrap(cdiv(a,3),T)+5,T)),
        ("mod_add", "(x+3)%3", "x%3", lambda a: crem(a+3,3)==crem(a,3)),
        ("mod_sub", "(x-3)%3", "x%3", lambda a: crem(a-3,3)==crem(a,3)),
        ("div_neg_den", "x/-3", "-(x/3)", lambda a: wrap(cdiv(a,-3),T)==wrap(-wrap(cdiv(a,3),T),T)),
        ("mod_neg_den", "x%-3", "x%3", lambda a: crem(a,-3)==crem(a,3)),
        ("euclid_vs_c", "x%5", "(x%5+5)%5", lambda a: crem(a,5)==crem(crem(a,5)+5,5)),
    ]
    for name, g, h, pred in identities:
        f1 = fn(g, [("x", T, None)])
        # h may be a bare expression; give it the same param type
        f2 = {"body": h, "params": [{"name": "x", "type": T}]}
        # expected: pred over all a except undefined points (div by zero if a==0)
        exp = True
        for a in dom:
            r = pred(a)
            if r is None:   # undefined -> skip
                continue
            if not r:
                exp = False; break
        cases.append((name, (f1, f2), None, exp, None, True))
    return cases

def mixed_cases():
    """Mixed signed/unsigned operands: ucas computes them as the unsigned type."""
    cases = []
    for t1, t2 in [('i8','u8'), ('u8','i8'), ('i16','u16'), ('u16','i16')]:
        u = 'u' + t1[1:]  # common type
        xs = list(range(-4,5)) if t1[0]=='i' else list(range(0,9))
        ys = list(range(-3,4)) if t2[0]=='i' else list(range(0,7))
        ys = [y for y in ys if y != 0]
        xs = [x for x in xs if True]
        for op in ('/','%'):
            body = f"x{op}y"
            prm = [("x",t1,None),("y",t2,[min(ys),max(ys)])]
            def oracle(v, u=u, op=op):
                x,y = v
                x = wrap(x,u); y = wrap(y,u)
                if y==0: return None
                return wrap(x//y,u) if op=='/' else wrap(x%y,u)
            cases.append((f"mix_{t1}_{t2}_{op}", body, prm, oracle, None, True))
    return cases

def pow2_cases():
    """Power-of-two divisors and shift/mask equivalences."""
    cases = []
    for t in ('u8','i8','u16','i16'):
        lo, hi = info(t)[2], info(t)[3]
        xs = list(range(lo,min(lo+40,hi+1))) + list(range(max(hi-40,lo),hi+1))
        xs = sorted(set(xs))
        for k in (1,2,3,4,7):
            d = 1<<k
            for op in ('/','%'):
                body = f"x{op}{d}"
                def oracle(v, t=t, op=op, d=d):
                    a = wrap(v,t); dw = wrap(d,t)
                    if dw==0: return None
                    return wrap(cdiv(a,dw),t) if op=='/' else wrap(crem(a,dw),t)
                cases.append((f"pow2_{t}_{op}_{d}", body, [("x",t,None)], oracle,
                              xs, True))
    return cases

def zero_cases():
    """Division/remainder by literal zero and zero-valued expressions."""
    cases = []
    for t in ('u8','i8','u16','i16'):
        for op in ('/','%'):
            for d in ('0', '(x-x)'):
                body = f"x{op}{d}"
                def oracle(v, t=t, op=op):
                    return None  # always undefined
                cases.append((f"zero_{t}_{op}_{d}", body, [("x",t,[0,4])], oracle,
                              None, True))
    return cases

def variable_divisor_cases():
    cases = []
    # x / y with y including zero; verify defined rows only
    for t in ('u8','i8'):
        ys = [0,1,2,3,-1,-2] if t=='i8' else [0,1,2,3,4]
        xs = list(range(-4,5)) if t=='i8' else list(range(0,9))
        for op in ('/','%'):
            cases.append((f"var_{t}_{op}", (f"x{op}y",
                          [("x",t,[min(xs),max(xs)]),("y",t,[min(ys),max(ys)])]),
                          (xs,ys), None, None, True))
    # where-clause excluding zero (use explicit conditions via body masking)
    return cases

def run():
    m = MCP()
    results = {"const":[], "samp":[], "equiv":[], "var":[],
               "mixed":[], "pow2":[], "zero":[]}
    allcases = []
    for c in const_cases(): allcases.append(("const",)+c)
    for c in sampled_const_cases(): allcases.append(("samp",)+c)
    for c in identity_cases(): allcases.append(("equiv",)+c)
    for c in variable_divisor_cases(): allcases.append(("var",)+c)
    for c in mixed_cases(): allcases.append(("mixed",)+c)
    for c in pow2_cases(): allcases.append(("pow2",)+c)
    for c in zero_cases(): allcases.append(("zero",)+c)

    for cat, name, expr, params, oracle, pts, full in allcases:
        if cat == 'equiv':
            ex = [expr[0]["body"], expr[1]["body"]]
        elif cat == 'var':
            ex = expr[0]
        else:
            ex = expr
        entry = {"name": name, "expr": ex}
        if cat == 'equiv':
            f1, f2 = expr
            r = m.call("analyze", {"op":"equiv","args":{"f":f1,"g":f2}})
            sc = r
            entry["ok"] = sc.get("ok")
            if sc.get("ok"):
                res = sc.get("result",{})
                entry["equal"] = res.get("equal")
                entry["expected"] = oracle
                entry["mismatch"] = (res.get("equal") != oracle)
                if "counterexample" in res: entry["counterexample"]=res["counterexample"]
            else:
                entry["error"] = sc.get("error")
            results['equiv'].append(entry)
        elif cat == 'var':
            body, prm = expr
            f = fn(body, prm)
            r = m.call("analyze", {"op":"table","args":{"f":f}})
            entry["ok"] = r.get("ok")
            if r.get("ok"):
                rows = r.get("result",{}).get("rows",[])
                entry["nrows"] = len(rows)
                bad = []
                xs, ys = params
                for row in rows:
                    v = parse_at(row["at"])
                    if not row.get("defined",True):
                        continue
                    a,b = v
                    t = prm[0][1]
                    op = expr[0][1]
                    if b == 0:
                        bad.append((row["at"],"defined-with-zero-divisor")); continue
                    if t[0]=='u':
                        exp = a//b if op=='/' else a%b
                    else:
                        exp = wrap(cdiv(a,b),t) if op=='/' else wrap(crem(a,b),t)
                    if int(row["value"])!=exp:
                        bad.append((row["at"],row["value"],exp))
                entry["bad"] = bad[:10]; entry["nbad"]=len(bad)
            else:
                entry["error"]=r.get("error")
            results['var'].append(entry)
        else:
            f = fn(expr, params)
            r = m.call("analyze", {"op":"table","args":{"f":f}})
            entry["ok"] = r.get("ok")
            if r.get("ok"):
                rows = r.get("result",{}).get("rows",[])
                entry["nrows"] = len(rows)
                bad = []
                for row in rows:
                    vals = parse_at(row["at"])
                    a = vals[0] if len(vals)==1 else vals
                    exp = oracle(a)
                    if exp is None:
                        if row.get("defined",True):
                            bad.append((a,row["value"],"should be undefined"))
                    elif not row.get("defined",True):
                        bad.append((a,"undefined","expected "+str(exp)))
                    elif int(row["value"])!=exp:
                        bad.append((a,row["value"],exp))
                entry["bad"] = bad[:12]; entry["nbad"]=len(bad)
            else:
                entry["error"]=r.get("error")
            results[cat].append(entry)
        sys.stderr.write(f"\r{sum(len(v) for v in results.values())}/{len(allcases)}")
    sys.stderr.write("\n")
    m.close()
    return results

if __name__ == "__main__":
    res = run()
    with open("verify_report.json","w") as f:
        json.dump(res,f,indent=1)
    for cat in res:
        bads = [e for e in res[cat] if e.get("nbad") or e.get("mismatch") or not e.get("ok")]
        print(f"[{cat}] cases={len(res[cat])} problems={len(bads)}")
        for e in bads[:30]:
            print("  ",e.get("name"), "nbad=",e.get("nbad"), "mismatch=",e.get("mismatch"),
                  "err=",e.get("error"), "bad=",e.get("bad"))
