#!/usr/bin/env python3
"""Split the two slow/ungoldened ops into one-call-per-file reproducers.

- mma: each call is ~9s and deterministic; one call per file fits `timeout 15`
  and each gets a golden .out.
- adamfit: each call embeds a wall-clock timing in the MCP text response, so it
  is nondeterministic. One-call files are kept as reproducers but get NO .out.
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
import json, os, subprocess, sys
HERE=os.path.dirname(os.path.abspath(__file__))
BIN=str(_REPO_ROOT / "ucas")
sys.path.insert(0,HERE)
from opdefs import OPS

INIT={"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}
NOTIF={"jsonrpc":"2.0","method":"notifications/initialized"}

def one_call_file(path, tool, op, args):
    lines=[INIT,NOTIF,{"jsonrpc":"2.0","id":1,"method":"tools/call",
           "params":{"name":tool,"arguments":{"op":op,"args":args}}}]
    with open(path,"w") as f:
        for l in lines: f.write(json.dumps(l,separators=(",",":"))+"\n")

def run(path, t=15):
    with open(path,"rb") as f:
        p=subprocess.run(["timeout",str(t),BIN,"--mcp"],stdin=f,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return p.returncode,p.stdout,p.stderr

def main():
    for old in ("34_mma.jsonl","34_mma.out","35_adamfit.jsonl","35_adamfit.out"):
        p=os.path.join(HERE,old)
        if os.path.exists(p): os.remove(p)
    report={}
    for prefix,op in (("34","mma"),("35","adamfit")):
        tool,valids,mal=OPS[op]
        entries=[("valid%d"%i,a) for i,a in enumerate(valids)]+[("malformed",mal)]
        statuses=[]
        for j,(tag,args) in enumerate(entries):
            name="%s%s_%s"%(prefix,chr(ord('a')+j),tag)
            jp=os.path.join(HERE,name+".jsonl")
            one_call_file(jp,tool,op,args)
            rc1,o1,e1=run(jp); rc2,o2,e2=run(jp)
            det=(rc1==rc2 and o1==o2 and e1==e2)
            keep=op=="mma" and det and rc1==0
            if keep:
                open(os.path.join(HERE,name+".out"),"wb").write(o1)
            statuses.append((name,rc1,rc2,det,keep))
            print("%-24s rc=%s/%s det=%s %s"%(name,rc1,rc2,det,"KEEP" if keep else "no-golden"))
        report[op]=statuses
    json.dump(report,open(os.path.join(HERE,"_slow_report.json"),"w"),indent=2)

if __name__=="__main__": main()
