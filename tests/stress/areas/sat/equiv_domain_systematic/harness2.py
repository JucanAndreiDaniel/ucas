#!/usr/bin/env python3
"""Part B: function-object vs raw-string args across --json / --mcp / --mcp --flat."""
import json, subprocess, os
from harness import S, BIN, HERE, oracle_equiv, PAIR_CMDS, UNARY_CMDS

SCRATCH = os.path.join(HERE, "_scratch")
os.makedirs(SCRATCH, exist_ok=True)

def define_args(sc):
    """Build `define`-style defs AND proper function objects for each f/g."""
    fname = sc["f"][0].split("(")[0]; gname = sc["g"][0].split("(")[0]
    fbody = sc["f"][0].split("=",1)[1].strip()
    gbody = sc["g"][0].split("=",1)[1].strip()
    if " where " in gbody: gbody = gbody.split(" where ",1)[0].strip()
    two = sc["id"].startswith("s13")
    fparams = ([{"name":"x","type":"u8"},{"name":"y","type":"u8"}] if two
               else [{"name":"x","type":"u8"}])
    gparams = ([{"name":"x","type":"u8"},{"name":"y","type":"u8"}] if two
               else [{"name":"x","type":"u8"}])
    gwhere = []
    if sc["kind"]=="range":
        rng = {"s02_decl_range":(0,7),"s07_i8_range":(-5,5)}.get(sc["id"])
        ty = "u8" if sc["id"].startswith("s02") else "i8"
        if rng: gparams=[{"name":"x","type":ty,"range":list(rng)}]
    if sc["kind"] in ("set","where-set"):
        gwhere=["x in {0,1,2,3}"]
    if sc["kind"]=="where" and sc["g"][1]:
        gwhere=[sc["g"][1]]
    # function-object forms (note: the object `where` key is silently dropped
    # by the generator; declared `range` in params IS emitted)
    fobj={"body":fbody,"params":fparams}
    gobj={"body":gbody,"params":gparams}
    if gwhere: gobj["where"]=gwhere
    return {
        "fname":fname,"gname":gname,"fbody":fbody,"gbody":gbody,
        "fparams":fparams,"gparams":gparams,"gwhere":gwhere,
        "fobj":fobj,"gobj":gobj,
    }

def frontend_config(fe):
    base = {"json":([BIN,"--json","--files","none"],"json"),
            "mcp":([BIN,"--mcp"],"mcp"),
            "mcp_flat":([BIN,"--mcp","--flat"],"flat")}[fe]
    return base

OPS = set(PAIR_CMDS)|set(UNARY_CMDS)|{"differ"}
def mkreq(fe, id, name, args):
    """Map a logical command to the right wire shape for the frontend."""
    if fe=="json":
        return {"id":id,"cmd":name,"args":args}
    if name=="define":
        if fe=="mcp_flat":
            return {"jsonrpc":"2.0","id":id,"method":"tools/call","params":{"name":"define","arguments":args}}
        return {"jsonrpc":"2.0","id":id,"method":"tools/call","params":{"name":"session","arguments":{"op":"define","args":args}}}
    if name in OPS:
        if fe=="mcp_flat":
            return {"jsonrpc":"2.0","id":id,"method":"tools/call","params":{"name":name,"arguments":args}}
        return {"jsonrpc":"2.0","id":id,"method":"tools/call","params":{"name":"analyze","arguments":{"op":name,"args":args}}}
    return {"jsonrpc":"2.0","id":id,"method":"tools/call","params":{"name":name,"arguments":args}}

def prelude(fe):
    if fe=="json": return []
    return [
      {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}},
      {"jsonrpc":"2.0","method":"notifications/initialized"},
    ]

def parse_resp(fe, line):
    d=json.loads(line)
    if fe=="json": return d
    r=d.get("result",{})
    sc=r.get("structuredContent") if isinstance(r,dict) else None
    return sc if sc else {"_content":r.get("content"),"_isError":r.get("isError"),"_id":d.get("id"),"_error":d.get("error")}

def run(fe, reqs):
    argv,_=frontend_config(fe)
    inp="\n".join(json.dumps(r) for r in prelude(fe)+reqs)+"\n"
    try:
        p=subprocess.run(argv,input=inp,text=True,capture_output=True,timeout=40)
        return p.returncode,p.stdout,p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", "TIMEOUT"

def main():
    allrows=[]
    for fe in ["json","mcp","mcp_flat"]:
        reqs=[]; meta=[]
        idc=1
        # define all functions first (for raw-string mode)
        for sc in S:
            d=define_args(sc)
            for nm,body,params,where in [
                (d["fname"],d["fbody"],d["fparams"],[]),
                (d["gname"],d["gbody"],d["gparams"],d["gwhere"]),
            ]:
                args={"name":nm,"body":body,"params":params}
                if where: args["where"]=where
                reqs.append(mkreq(fe,idc,"define",args))
                meta.append(("define",sc["id"],nm))
                idc+=1
        # pair commands: raw-string and function-object
        for sc in S:
            d=define_args(sc)
            oracle=oracle_equiv(sc)
            for cmd in PAIR_CMDS:
                # raw string
                reqs.append(mkreq(fe,idc,cmd,{"f":d["fname"],"g":d["gname"]}))
                meta.append((cmd+"_raw",sc["id"],oracle)); idc+=1
                # function object (if both available)
                if d["fobj"] and d["gobj"]:
                    fo={"f":d["fobj"],"g":d["gobj"]}
                    reqs.append(mkreq(fe,idc,cmd,fo))
                    meta.append((cmd+"_obj",sc["id"],oracle)); idc+=1
        # unary commands on G: raw-string and function-object
        for sc in S:
            d=define_args(sc)
            for cmd in UNARY_CMDS:
                reqs.append(mkreq(fe,idc,cmd,{"f":d["gname"]}))
                meta.append((cmd+"_raw",sc["id"],"report")); idc+=1
                if d["gobj"]:
                    reqs.append(mkreq(fe,idc,cmd,{"f":d["gobj"]}))
                    meta.append((cmd+"_obj",sc["id"],"report")); idc+=1
        # a couple of analyze/differ and unknown-op probes
        reqs.append(mkreq(fe,idc,"differ",{"f":S[0]["f"][0].split("(")[0],"g":S[0]["g"][0].split("(")[0]}))
        meta.append(("differ",S[0]["id"],"LIMIT")); idc+=1
        rc,out,err=run(fe,reqs)
        lines=[l for l in out.splitlines() if l.strip().startswith("{")]
        if fe!="json":  # drop the initialize(id 0) response line
            lines=[l for l in lines if json.loads(l).get("id")!=0]
        for i,(m,line) in enumerate(zip(meta,lines)):
            try: resp=parse_resp(fe,line)
            except Exception as e: resp={"_parse_error":str(e)}
            allrows.append(dict(frontend=fe,case=m[0],scenario=m[1],oracle=m[2],resp=resp,rc=rc))
        with open(os.path.join(HERE,f"results_partB_{fe}.jsonl"),"w") as fh:
            for r in allrows:
                if r["frontend"]==fe: fh.write(json.dumps(r)+"\n")
        print(fe,"reqs",len(reqs),"resp lines",len(lines),"rc",rc)
        if len(lines)!=len(reqs):
            print("  !!! MISMATCH: expected",len(reqs),"got",len(lines))
            # show last few raw lines
            for l in lines[-3:]: print("   LAST:",l[:300])

if __name__=="__main__":
    main()
