#!/usr/bin/env python3
"""Independent numerical oracle for critical-point finding/classification.

For each function we:
  * ask ucas (`analyze crit` over MCP wire) for its critical points
  * compute our OWN derivative roots by a dense scan + bisection + sign test
  * compare locations and classifications

This file is a helper/catalog, not a golden.  It is intentionally written
without using any ucas result in the oracle computation.
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
import json, math, subprocess, sys, re, os

UCAS = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------
# Python evaluation namespace (independent of ucas)
# ----------------------------------------------------------------------------
import math as _m
NS = {
    "sin": _m.sin, "cos": _m.cos, "tan": _m.tan, "asin": _m.asin,
    "acos": _m.acos, "atan": _m.atan, "sinh": _m.sinh, "cosh": _m.cosh,
    "tanh": _m.tanh, "exp": _m.exp, "log": _m.log, "ln": _m.log,
    "sqrt": _m.sqrt, "abs": _m.fabs, "sign": lambda x: (x>0)-(x<0),
    "pi": _m.pi, "e": _m.e, "floor": _m.floor,
    "ceil": _m.ceil, "round": round, "trunc": _m.trunc,
    "max": max, "min": min, "pow": _m.pow,
}

def translate(ucas_expr):
    """Translate a ucas expression into a Python-evaluable one."""
    s = ucas_expr
    s = s.replace('^', '**')
    # function renames
    s = re.sub(r'\bln\s*\(', 'log(', s)
    # implicit multiplication FIRST: '2x'->'2*x', '3 x'->'3*x', '2cos'->'2*cos'
    s = re.sub(r'(\d)\s+([a-zA-Z(])', r'\1*\2', s)
    s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)
    # function application without parens, e.g. 'sin x', 'exp x', '2*cos x'
    s = re.sub(r'\b(sin|cos|tan|exp|log|ln|sqrt|abs|sinh|cosh|tanh|asin|acos|atan)\s+(\w+)\b', r'\1(\2)', s)
    return s

def make_f(ucas_expr):
    py = translate(ucas_expr)
    code = compile(py, '<f>', 'eval')
    def f(x):
        return eval(code, {"__builtins__": {}}, {**NS, "x": x})
    return f, py

def deriv(f, x, h=1e-5):
    try: return (f(x+h)-f(x-h))/(2*h)
    except Exception: return float('nan')

def second(f, x, h=1e-4):
    try: return (f(x+h)-2*f(x)+f(x-h))/(h*h)
    except Exception: return float('nan')

# ----------------------------------------------------------------------------
# Oracle: scan [-10,10], find derivative sign-change roots, refine by bisection
# ----------------------------------------------------------------------------
def oracle_points(f, scan_lo=-10.0, scan_hi=10.0, n=20001):
    xs = [scan_lo + (scan_hi-scan_lo)*i/(n-1) for i in range(n)]
    ds = []
    for x in xs:
        try: ds.append(deriv(f, x))
        except Exception: ds.append(float('nan'))
    roots = []
    for i in range(n-1):
        a, b = ds[i], ds[i+1]
        if math.isnan(a) or math.isnan(b): continue
        if a == 0.0:
            roots.append((xs[i], 'min' if b>0 else 'max' if b<0 else 'inflection'))
            continue
        if (a < 0 < b) or (a > 0 > b):
            xlo, xhi = xs[i], xs[i+1]
            flo = a
            for _ in range(60):
                mid = (xlo+xhi)/2
                try: fm = deriv(f, mid)
                except Exception: fm = float('nan')
                if math.isnan(fm): break
                if (flo < 0 and fm < 0) or (flo > 0 and fm > 0):
                    xlo, flo = mid, fm
                else:
                    xhi = mid
            xr = (xlo+xhi)/2
            kind = 'min' if (a < 0 < b) else 'max'
            roots.append((xr, kind))
    # merge near-duplicate roots
    merged = []
    for r in roots:
        if merged and abs(r[0]-merged[-1][0]) < 1e-3:
            continue
        merged.append(r)
    return merged

def norm_kind(k):
    k = k.lower()
    if 'maximum' in k or k == 'max': return 'max'
    if 'minimum' in k or k == 'min': return 'min'
    if 'inflection' in k: return 'inflection'
    if 'saddle' in k: return 'saddle'
    return k

# ----------------------------------------------------------------------------
# Query ucas via MCP wire in ONE batch
# ----------------------------------------------------------------------------
def query_crit(exprs, timeout=120):
    lines = [
      json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize","params":{
        "protocolVersion":"2025-06-18","capabilities":{},
        "clientInfo":{"name":"stress","version":"1"}}}),
      json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}),
    ]
    for i, e in enumerate(exprs, 1):
        lines.append(json.dumps({"jsonrpc":"2.0","id":i,"method":"tools/call",
          "params":{"name":"analyze","arguments":{"op":"crit","args":{"f":e}}}}))
    inp = "\n".join(lines)+"\n"
    p = subprocess.run([UCAS,"--mcp"], input=inp, text=True,
                       capture_output=True, timeout=timeout)
    out = {}
    for line in p.stdout.splitlines():
        try: o = json.loads(line)
        except Exception: continue
        i = o.get('id')
        if not isinstance(i,int) or i==0: continue
        sc = o.get('result',{}).get('structuredContent')
        if sc is None:
            out[i] = {"error": o.get('result',{}).get('content') or o.get('error') or o}
        else:
            out[i] = sc
    return out, p.stderr

# ----------------------------------------------------------------------------
# Comparison
# ----------------------------------------------------------------------------
def _shortpts(pts, k=6):
    s = ', '.join(f"{x:.4f}:{u}" for x,u in pts[:k])
    if len(pts) > k: s += f", ... (+{len(pts)-k})"
    return '['+s+']'

def compare(exprs, verbose=True):
    res, err = query_crit(exprs)
    issues = []
    for i, e in enumerate(exprs, 1):
        f, py = make_f(e)
        o = res.get(i, {})
        if 'error' in o:
            issues.append((e,'CRASH/ERROR', str(o['error'])[:200]))
            continue
        r = o.get('result', {})
        pts = r.get('points', [])
        kind = r.get('kind','')
        if kind == 'crit_gradient' or 'gradient' in r:
            if verbose: print(f"[GRAD only] {e}")
            continue
        try:
            oracle = oracle_points(f)
        except Exception as ex:
            issues.append((e,'ORACLE_FAIL',str(ex)))
            continue
        ucas_pts = []
        for p in pts:
            try:
                ux = float(p.get('x'))
                uk = norm_kind(str(p.get('kind','')))
                ucas_pts.append((ux,uk))
            except Exception: pass
        # High-frequency / huge-count cases: oracle scan is unreliable; only count-check
        if len(oracle) > 40 or len(ucas_pts) > 40:
            if len(oracle) != len(ucas_pts):
                issues.append((e,'HIGH_FREQ_COUNT',
                    f"oracle roots={len(oracle)} ucas points={len(ucas_pts)} (unreliable counts)"))
            continue
        sp = _shortpts(ucas_pts)
        for ux, uk in ucas_pts:
            d = deriv(f, ux)
            if not math.isnan(d) and abs(d) > 0.02 and abs(ux) < 9.99:
                issues.append((e,'SPURIOUS', f"x={ux:.5f} {uk} f'={d:.5f} {sp}"))
        for ox, ok in oracle:
            match = [u for u in ucas_pts if abs(u[0]-ox) < 0.02]
            if not match:
                issues.append((e,'MISSED', f"oracle x={ox:.5f}({ok}) not in ucas {sp}"))
            elif match[0][1] != ok:
                issues.append((e,'WRONG_CLASS', f"x={ox:.5f}: oracle={ok} ucas={match[0][1]} {sp}"))
    if verbose:
        print(f"\nTried {len(exprs)} functions; {len(issues)} potential issues")
        for it in issues[:200]:
            print("  ", it[0], '|', it[1], '|', it[2])
        if len(issues) > 200: print(f"  ... and {len(issues)-200} more")
    return issues, res

if __name__ == '__main__':
    # load expressions from a plain text file (one per line) given as argv[1]
    path = sys.argv[1] if len(sys.argv)>1 else os.path.join(HERE,'exprs.txt')
    exprs = [l.strip() for l in open(path) if l.strip() and not l.startswith('#')]
    compare(exprs)
