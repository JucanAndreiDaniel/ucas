#!/usr/bin/env python3
"""Per-command-family check: is a numeric positive timeout_s honoured?

For every search family we use a genuinely expensive invocation (borrowed from
timeout_isolation/json_long_150.jsonl) and compare numeric 0.05 vs string "0.05".
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
import json, os, select, signal, subprocess, sys
BIN = str(_REPO_ROOT / "ucas")

def readline(p, t=2.0):
    r, _, _ = select.select([p.stdout], [], [], t)
    return p.stdout.readline() if r else None

def spawn(mode):
    flags = ["--json", "--files", "none"] if mode == "json" else (
            ["--mcp", "--flat"] if mode == "flat" else ["--mcp"])
    p = subprocess.Popen([BIN]+flags, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1,
                         start_new_session=True)
    if mode != "json":
        p.stdin.write(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize",
            "params":{"protocolVersion":"2025-06-18","capabilities":{},
                      "clientInfo":{"name":"sweep","version":"1"}}})+"\n")
        p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\n")
        p.stdin.flush(); readline(p); readline(p)
    return p

FAM = {"define":"session","state":"session","reset":"session",
       "gates":"analyze","find":"analyze","equiv":"analyze","range":"analyze",
       "approx":"analyze","fit":"analyze","parse":"analyze","show":"analyze",
       "prove":"proofs"}
def mk(mode, rid, op, args):
    if mode == "json": return {"id":rid,"cmd":op,"args":args}
    if mode == "flat": return {"jsonrpc":"2.0","id":rid,"method":"tools/call",
                               "params":{"name":op,"arguments":args}}
    if op == "bigint": return {"jsonrpc":"2.0","id":rid,"method":"tools/call",
                   "params":{"name":"ucas","arguments":{"source":"bigint 2^200+1"}}}
    fam = FAM.get(op)
    params = ({"name":fam,"arguments":{"op":op,"args":args}} if fam
              else {"name":op,"arguments":args})
    return {"jsonrpc":"2.0","id":rid,"method":"tools/call","params":params}

def extract(line):
    if not line: return (None,"no-reply")
    try: o=json.loads(line)
    except Exception: return (None,"bad-json")
    r=o.get("result"); sc=r.get("structuredContent") if isinstance(r,dict) else None
    env=sc if isinstance(sc,dict) else o
    return ((env.get("error") or {}).get("code"), "ok")

DEFS = [
 ("zz",{"name":"zz","params":[{"name":"x","type":"u6"}],"body":"x*x*x+47"}),
 ("h1",{"name":"h1","params":[{"name":"x","type":"u64"}],"body":"(x*0x9e3779b97f4a7c15)*0x9e3779b97f4a7c15"}),
 ("h2",{"name":"h2","params":[{"name":"x","type":"u64"}],"body":"x*(0x9e3779b97f4a7c15*0x9e3779b97f4a7c15)"}),
 ("ra1",{"name":"ra1","params":[{"name":"x","type":"real"}],"body":"sin(x)*exp(cos(x))"}),
 ("heavy2",{"name":"heavy2","params":[{"name":"x","type":"real"}],"body":"exp(sin(exp(x)))*cos(exp(cos(exp(x))))"}),
]
CASES = [
 ("gates", {"f":"zz","max":45,"nodes":100000000}),
 ("find",  {"f":"zz","n":300,"max":45}),
 ("equiv", {"f":"h1","g":"h2"}),
 ("range", {"f":"heavy2"}),
 ("approx",{"f":"ra1","in":[-10,10],"options":"degree 45 as f64"}),
 ("fit",   {"g":"a*x^4 + b*x^3 + c*x^2 + d*x + e","f":"sin(x)","metric":"maxrel"}),
 ("prove", {"name":"bockstein"}),
 ("parse", {"expr":"(" * 2000 + "x" + ")" * 2000}),
]

def run(mode, op, base, ts):
    p=spawn(mode)
    try:
        for i,(_,d) in enumerate(DEFS):
            p.stdin.write(json.dumps(mk(mode,10+i,"define",dict(d)))+"\n")
            p.stdin.flush(); readline(p)
        args=dict(base); args["timeout_s"]=ts
        p.stdin.write(json.dumps(mk(mode,50,op,args))+"\n"); p.stdin.flush()
        return extract(readline(p,2.0))
    finally:
        try: os.killpg(os.getpgid(p.pid),signal.SIGKILL)
        except Exception: pass
        p.wait(timeout=4)

def main():
    print("family | numeric(0.05) | string(\"0.05\") — verdict")
    for mode in ("json","mcp","flat"):
        print(f"\n=== {mode} ===")
        for op,base in CASES:
            nc,ns=run(mode,op,base,0.05)
            sc,ss=run(mode,op,base,"0.05")
            def v(c,s):
                if s=="no-reply": return "HANG/ignored"
                if c=="timeout": return "timeout OK"
                if c in (None,) and s=="ok": return f"fast/no-limit({c})"
                return f"{c}"
            print(f"  {op:8s} numeric={v(nc,ns):22s} string={v(sc,ss):22s} [raw n={nc}/{ns} s={sc}/{ss}]")

if __name__=="__main__": main()
