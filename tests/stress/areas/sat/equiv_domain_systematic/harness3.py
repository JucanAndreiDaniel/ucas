#!/usr/bin/env python3
"""Part C: SAT-path / extra restriction shapes, CLI + 3 wire frontends."""
import json, subprocess, os
from harness import BIN, HERE
SCRATCH=os.path.join(HERE,"_scratch"); os.makedirs(SCRATCH,exist_ok=True)

SC = [
 ("c1_sat_u32","f(x: u32 in 0..10000000) = x where x < 1000000\ng(x: u32 in 0..10000000) = x where x < 500000","differ"),
 ("c2_u16_where","f(x: u16) = x\ng(x: u16) = x where x < 1000","differ"),
 ("c3_sparse_set","f(x: u32) = x\ng(x: u32 in {0, 4000000000}) = x","differ"),
 ("c4_where_arith","f(x: u8) = x\ng(x: u8) = x where x*2 < 10","differ"),
 ("c5_two_param_both","f(x: u8, y: u8) = x + y\ng(x: u8, y: u8) = x + y where x < 4 && y < 4","differ"),
 ("c6_i16_range","f(x: i16) = x\ng(x: i16 in -100..100) = x","differ"),
 ("c7_where_on_F","f(x: u8) = x where x < 5\ng(x: u8) = x","equal"),
 ("c8_match_default_where","f(x: u8) = x\ng(x: u8) = match x { 0 => 0, _ => x } where x < 5","differ"),
]

def run(argv,inp=None,timeout=40):
    try:
        p=subprocess.run(argv,input=inp,text=True,capture_output=True,timeout=timeout)
        return p.returncode,p.stdout
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or ""

def out_of_domain_witness(text, fmax):
    """Check any 'x=N vs' witness lies within f's printed domain (heuristic)."""
    import re
    m=re.search(r"e\.g\. x=(-?\d+)",text)
    if m:
        n=int(m.group(1))
        return n, (0<=n<=fmax)
    return None,True

rows=[]
for sid,src,oracle in SC:
    full=src+"\nequiv f ~ g\ndomain g\nerror g ~ f\n"
    # CLI
    path=os.path.join(SCRATCH,"C.ucas"); open(path,"w").write(full)
    rc,out=run([BIN,path]); rows.append((sid,"CLI","equiv",oracle,rc,out))
    for fe in ["json","mcp","mcp_flat"]:
        if fe=="json":
            req={"id":1,"cmd":"ucas","args":{"source":full}}
            inp=json.dumps(req)+"\n"
        else:
            pre='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
            req={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":full}}}
            inp=pre+json.dumps(req)+"\n"
        argv=[BIN,"--json","--files","none"] if fe=="json" else ([BIN,"--mcp"] if fe=="mcp" else [BIN,"--mcp","--flat"])
        rc,out=run(argv,inp); rows.append((sid,fe,"equiv",oracle,rc,out))

with open(os.path.join(HERE,"results_partC.jsonl"),"w") as fh:
    for sid,fe,cmd,orc,rc,out in rows:
        fh.write(json.dumps(dict(scenario=sid,frontend=fe,cmd=cmd,oracle=orc,rc=rc,raw=out))+"\n")

def verdict(fe,raw):
    if fe=="CLI":
        low=raw.lower()
        return ('equal' if 'are equal on the domain' in low else 'differ' if 'differ at' in low else 'unknown'), None
    for l in raw.splitlines():
        if not l.strip().startswith("{"): continue
        d=json.loads(l)
        if fe=="json":
            if d.get("cmd")=="ucas":
                t=d.get("text","") or ""; rr=None
                # source mode: text contains all commands; find equiv line
                low=t.lower()
        else:
            r=d.get("result",{})
            t=r.get("structuredContent",{}).get("text","") if isinstance(r,dict) and "structuredContent" in r else ""
        if fe=="json":
            low=t.lower()
        else:
            low=t.lower()
        if 'are equal on the domain' in low: return 'equal',t
        if 'differ at' in low: return 'differ',t
    return 'unknown',raw[:80]

print("### Part C equiv verdict vs oracle ###")
nwrong=0
for sid,fe,cmd,orc,rc,out in rows:
    v,t=verdict(fe,out)
    if v!=orc:
        nwrong+=1
        print(f"  WRONG {sid:22s} {fe:9s} oracle={orc:6s} got={v}")
print("total wrong:",nwrong,"/",len(rows))
