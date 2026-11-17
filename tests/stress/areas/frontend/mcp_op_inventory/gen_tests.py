#!/usr/bin/env python3
"""Generate per-op MCP golden tests for the 45 ops found without genuine stress coverage.

Reads the op/args catalog from opdefs.py (kept in /tmp during construction; inlined
here via import fallback) and writes NN_<op>.jsonl + NN_<op>.out goldens.
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
import json, os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = str(_REPO_ROOT / "ucas")

# Try to load the catalog; it is also embedded below as a fallback so the
# generator is self-contained and re-runnable.
sys.path.insert(0, HERE)
try:
    from opdefs import OPS
except Exception:
    OPS = {}

INIT = {"jsonrpc":"2.0","id":0,"method":"initialize",
        "params":{"protocolVersion":"2025-06-18","capabilities":{},
                  "clientInfo":{"name":"stress","version":"1"}}}
NOTIF = {"jsonrpc":"2.0","method":"notifications/initialized"}

def call(i, tool, op, args):
    return {"jsonrpc":"2.0","id":i,"method":"tools/call",
            "params":{"name":tool,"arguments":{"op":op,"args":args}}}

def build_lines(op):
    tool, valids, mal = OPS[op]
    lines = [INIT, NOTIF]
    n = 1
    # `more` needs a prior find in the same session (setup, not counted).
    if op == "more":
        lines.append(call(n, "analyze", "find", {"f":"x+1: u8", "n":3}))
        n += 1
    for a in valids:
        lines.append(call(n, tool, op, a)); n += 1
    lines.append(call(n, tool, op, mal)); n += 1
    return lines

def write_jsonl(path, lines):
    with open(path, "w") as f:
        for l in lines:
            f.write(json.dumps(l, separators=(",", ":")) + "\n")

def run(path):
    with open(path, "rb") as f:
        p = subprocess.run(["timeout","15",BIN,"--mcp"], stdin=f,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr

def parse(out_bytes):
    res=[]
    for l in out_bytes.decode("utf-8","replace").splitlines():
        try: o=json.loads(l)
        except Exception: res.append({"_nonjson":l[:200]}); continue
        res.append(o)
    return res

def envelope_check(op, responses):
    """Return list of anomalies in structuredContent envelopes."""
    an=[]
    for o in responses:
        if "_nonjson" in o:
            an.append("NONJSON response: "+o["_nonjson"][:80]); continue
        if "id" not in o: continue
        if o["id"]==0: continue
        if "error" in o:
            # tool-level JSON-RPC error: allowed for invalid op/args at top level
            an.append("RPC_ERROR id=%s %s"%(o["id"],str(o["error"].get("message",""))[:60]))
            continue
        r=o.get("result",{})
        if "structuredContent" not in r:
            an.append("NO_STRUCTURED id=%s content=%s"%(o["id"],str(r.get("content"))[:80])); continue
        sc=r["structuredContent"]
        if sc.get("ok") is True and r.get("isError") is True:
            an.append("CONTRADICTORY ok=true isError=true id=%s"%o["id"])
        if sc.get("ok") is False and r.get("isError") is False:
            an.append("CONTRADICTORY ok=false isError=false id=%s"%o["id"])
        if not isinstance(sc.get("cmd"),str):
            an.append("NO_CMD id=%s"%o["id"])
    return an

def main():
    if not OPS:
        print("ERROR: opdefs.py catalog not found at /tmp"); sys.exit(2)
    report={}
    for idx,op in enumerate(OPS,1):
        name = "%02d_%s"%(idx,op)
        jp = os.path.join(HERE,name+".jsonl")
        lines = build_lines(op)
        write_jsonl(jp, lines)
        rc1,out1,err1 = run(jp)
        rc2,out2,err2 = run(jp)
        det = (rc1==rc2 and out1==out2 and err1==err2)
        resp1 = parse(out1)
        anom = envelope_check(op, resp1)
        # Keep golden only if deterministic and no crash/hang and no envelope anomaly
        ok_to_keep = det and rc1==0 and not any(
            a.startswith(("NONJSON","NO_STRUCTURED","CONTRADICTORY")) for a in anom)
        if ok_to_keep:
            with open(os.path.join(HERE,name+".out"),"wb") as f: f.write(out1)
        report[op]={
            "file":name+".jsonl","ncalls":len(lines)-2,
            "rc1":rc1,"rc2":rc2,"deterministic":det,"kept_golden":ok_to_keep,
            "stderr1":err1.decode("utf-8","replace")[:200],
            "anomalies":anom,
            "per_call":[(o.get("id"), (o.get("result",{}).get("structuredContent",{}) or {}).get("ok"),
                         ((o.get("result",{}).get("structuredContent",{}) or {}).get("error",{}) or {}).get("code"),
                         o.get("error",{}).get("code") if isinstance(o.get("error"),dict) else None)
                        for o in resp1 if isinstance(o.get("id"),int) and o["id"]>0],
        }
        print("%-18s rc=%s det=%s calls=%d anom=%d %s"%(
            op,rc1,det,len(lines)-2,len(anom),"KEEP" if ok_to_keep else "NO-GOLDEN"))
    with open(os.path.join(HERE,"_run_report.json"),"w") as f:
        json.dump(report,f,indent=2)
    print("\nWrote _run_report.json")

if __name__=="__main__":
    main()
