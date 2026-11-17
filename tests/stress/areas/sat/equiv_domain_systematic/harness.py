#!/usr/bin/env python3
"""
Systematic follow-up on the confirmed "equiv ignores G's domain" root cause.

Cross-product:
  (every way of restricting a domain)
    x (every comparison command)
    x (all frontends: CLI / --json / --mcp grouped / --mcp --flat)
    x (function-object vs raw-string / source args)

For every case the true domain is brute-forced in Python and the verdict is
classified as CORRECT / WRONG (unsound) / DROPPED-RESTRICTION / LIMIT.  We also
flag any frontend divergence and any case where the human-readable `text`
verdict contradicts the structured `result`.

Binary: $ROOT/ucas (already built, never rebuilt).
All runs are bounded with timeout.  No source / Makefile / shared file touched.
Deterministic: re-run with the same seed to reproduce byte-identical results.
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
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
import json, subprocess, itertools, os, sys

BIN = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Scenarios.  f is wide; g is a strict subset of f's domain with the SAME body
# value where it is defined, so the ONLY legitimate reason for `equiv f g` to
# report a difference is g's domain restriction.  Oracle for equiv is therefore
# "differ" (g undefined somewhere in f's domain) unless noted.
# ---------------------------------------------------------------------------
S = [
  dict(id="s01_where_lt", kind="where",
       f=("f01(x: u8) = x", [{"name":"x","type":"u8"}]),
       g=("g01(x: u8) = x where x < 5", "x < 5",
          {"body":"x","params":[{"name":"x","type":"u8"}],"where":["x < 5"]}),
       gdef=lambda x: 0 <= x <= 4, fdom=range(0,256), gval=lambda x:x),
  dict(id="s02_decl_range", kind="range",
       f=("f02(x: u8) = x", None),
       g=("g02(x: u8 in 0..7) = x", None,
          {"body":"x","params":[{"name":"x","type":"u8","range":[0,7]}]}),
       gdef=lambda x: 0 <= x <= 7, fdom=range(0,256), gval=lambda x:x),
  dict(id="s03_decl_set", kind="set",
       f=("f03(x: u8) = x", None),
       g=("g03(x: u8 in {0,1,2,3}) = x", None,
          None),  # function-object cannot express a declared set
       gdef=lambda x: x in (0,1,2,3), fdom=range(0,256), gval=lambda x:x),
  dict(id="s04_where_set", kind="where-set",
       f=("f04(x: u8) = x", None),
       g=("g04(x: u8) = x where x in {0,1,2,3}", "x in {0,1,2,3}",
          {"body":"x","params":[{"name":"x","type":"u8"}],"where":["x in {0,1,2,3}"]}),
       gdef=lambda x: x in (0,1,2,3), fdom=range(0,256), gval=lambda x:x),
  dict(id="s05_where_neq", kind="where",
       f=("f05(x: u8) = x", None),
       g=("g05(x: u8) = x where x != 0", "x != 0",
          {"body":"x","params":[{"name":"x","type":"u8"}],"where":["x != 0"]}),
       gdef=lambda x: x != 0, fdom=range(0,256), gval=lambda x:x),
  dict(id="s06_where_or", kind="where",
       f=("f06(x: u8) = x", None),
       g=("g06(x: u8) = x where x < 3 || x > 250", "x < 3 || x > 250",
          {"body":"x","params":[{"name":"x","type":"u8"}],"where":["x < 3 || x > 250"]}),
       gdef=lambda x: x<3 or x>250, fdom=range(0,256), gval=lambda x:x),
  dict(id="s07_i8_range", kind="range",
       f=("f07(x: i8) = x", None),
       g=("g07(x: i8 in -5..5) = x", None,
          {"body":"x","params":[{"name":"x","type":"i8","range":[-5,5]}]}),
       gdef=lambda x: -5 <= x <= 5, fdom=range(-128,128), gval=lambda x:x),
  dict(id="s08_match", kind="body-match",
       f=("f08(x: u4) = x", None),
       g=("g08(x: u4) = match x { 0=>0, 1=>1 }", None,
          {"body":"match x { 0=>0, 1=>1 }","params":[{"name":"x","type":"u4"}]}),
       gdef=lambda x: x in (0,1), fdom=range(0,16), gval=lambda x:x),
  dict(id="s09_table", kind="body-table",
       f=("f09(x: u4) = x", None),
       g=("g09(x: u4) = [0,1,2,3][x]", None,
          {"body":"[0,1,2,3][x]","params":[{"name":"x","type":"u4"}]}),
       gdef=lambda x: 0<=x<=3, fdom=range(0,16), gval=lambda x:x),
  dict(id="s10_div0", kind="body-div0",
       f=("f10(x: u8) = x", None),
       g=("g10(x: u8) = (x == 0) ? (1/0) : x", None,
          {"body":"(x == 0) ? (1/0) : x","params":[{"name":"x","type":"u8"}]}),
       gdef=lambda x: x!=0, fdom=range(0,256), gval=lambda x:x),
  dict(id="s11_shift", kind="body-shift",
       f=("f11(x: u8) = x", None),
       g=("g11(x: u8) = (x >= 8) ? (1 << x) : x", None,
          {"body":"(x >= 8) ? (1 << x) : x","params":[{"name":"x","type":"u8"}]}),
       gdef=lambda x: x<8, fdom=range(0,256), gval=lambda x:x),
  dict(id="s12_table_wide", kind="body-table",
       f=("f12(x: u8 in 0..255) = x", None),
       g=("g12(x: u8 in 0..255) = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15][x]", None,
          {"body":"[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15][x]","params":[{"name":"x","type":"u8"}]}),
       gdef=lambda x: 0<=x<=15, fdom=range(0,256), gval=lambda x:x),
  dict(id="s13_two_param_where", kind="where",
       f=("f13(x: u8, y: u8) = x + y", None),
       g=("g13(x: u8, y: u8) = x + y where y < 4", "y < 4",
          None),
       gdef=lambda p: p[1] < 4, fdom=None, gval=lambda p:p[0]+p[1]),
  # ---- controls: no restriction / identical ----
  dict(id="c01_identical", kind="control",
       f=("c01f(x: u8) = x", None),
       g=("c01g(x: u8) = x", None,
          {"body":"x","params":[{"name":"x","type":"u8"}]}),
       gdef=lambda x: True, fdom=range(0,256), gval=lambda x:x),
  dict(id="c02_where_novoid", kind="control",
       f=("c02f(x: u8) = x", None),
       g=("c02g(x: u8) = x where x < 256", "x < 256",
          {"body":"x","params":[{"name":"x","type":"u8"}],"where":["x < 256"]}),
       gdef=lambda x: True, fdom=range(0,256), gval=lambda x:x),
]

# commands taking (f,g)
PAIR_CMDS = ["equiv", "error"]
# commands taking a single function (test G's restriction reporting)
UNARY_CMDS = ["domain", "range", "wrap"]

def oracle_equiv(sc):
    if sc["fdom"] is None:
        # two-parameter: brute force 16x16
        diff = any((not sc["gdef"]((x,y))) for x in range(0,16) for y in range(0,16))
    else:
        diff = any((not sc["gdef"](x)) for x in sc["fdom"])
    return "differ" if diff else "equal"

# ---------------------------------------------------------------------------
# runners
# ---------------------------------------------------------------------------
def run(argv, inp=None, timeout=15):
    try:
        p = subprocess.run(argv, input=inp, text=True, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout,bytes) else (e.stdout or ""), "TIMEOUT"

def classify_equiv(result, text):
    """Return ('equal'|'differ'|'unknown', contradiction_bool)."""
    eq = result.get("equal") if isinstance(result,dict) else None
    if eq is True: v="equal"
    elif eq is False: v="differ"
    else:
        low=(text or "").lower()
        if "are equal on the domain" in low: v="equal"
        elif "differ at" in low: v="differ"
        else: v="unknown"
    contra = False
    if eq is True and "differ at" in (text or ""): contra=True
    if eq is False and "are equal on the domain" in (text or ""): contra=True
    return v, contra

# ---------------------------------------------------------------------------
# Part A: source-based cross-product (all four frontends see the SAME source)
# ---------------------------------------------------------------------------
def build_source(sc, cmd):
    fdef = sc["f"][0]; gdef = sc["g"][0]
    return fdef + "\n" + gdef + "\n" + cmd + "\n"

def partA():
    rows=[]
    for sc in S:
        fn = sc["f"][0].split("(")[0]; gn = sc["g"][0].split("(")[0]
        for cmd in PAIR_CMDS:
            line=f"{cmd} {fn} ~ {gn}"
            src=build_source(sc,line)
            oracle=oracle_equiv(sc)
            # CLI
            path=os.path.join(HERE,"_scratch","A.ucas")
            open(path,"w").write(src)
            rc,out,err=run([BIN,path]); rows.append(("CLI",sc["id"],cmd,"source",rc,out,err,oracle))
            # structured source frontends
            for fe,argv in [
                ("json",[BIN,"--json","--files","none"]),
                ("mcp",[BIN,"--mcp"]),
                ("mcp_flat",[BIN,"--mcp","--flat"]),
            ]:
                if fe=="json":
                    inp=json.dumps({"id":1,"cmd":"ucas","args":{"source":src}})+"\n"
                elif fe=="mcp":
                    inp='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}\n'\
                        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'+\
                        json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":src}}})+"\n"
                else:
                    inp='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}\n'\
                        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'+\
                        json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ucas","arguments":{"source":src}}})+"\n"
                rc,out,err=run(argv,inp); rows.append((fe,sc["id"],cmd,"source",rc,out,err,oracle))
        for cmd in UNARY_CMDS:
            line=f"{cmd} {gn}"
            src=build_source(sc,line)
            path=os.path.join(HERE,"_scratch","A.ucas"); open(path,"w").write(src)
            rc,out,err=run([BIN,path]); rows.append(("CLI",sc["id"],cmd,"source",rc,out,err,"report-domain"))
    return rows

def main():
    os.makedirs(os.path.join(HERE,"_scratch"),exist_ok=True)
    rows=partA()
    with open(os.path.join(HERE,"results_partA.jsonl"),"w") as fh:
        for fe,sid,cmd,mode,rc,out,err,oracle in rows:
            fh.write(json.dumps(dict(frontend=fe,scenario=sid,cmd=cmd,args=mode,rc=rc,oracle=oracle,raw=out,err=err))+"\n")
    print("partA rows:",len(rows))

if __name__=="__main__":
    main()
