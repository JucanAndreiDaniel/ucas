#!/usr/bin/env python3
"""Run the repo's own golden corpus through the sanitized binary, hunting for reports."""
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
_HERE = _ROOT_PATH(__file__).resolve().parent
import os, subprocess, glob, re
BIN=str(_HERE / "ucas_san")
EVID=str(_HERE / "evidence")
os.makedirs(EVID,exist_ok=True)
ENV=dict(os.environ)
ENV.update(UCAS_NO_TIMES="1", UCAS_SPIRV_CROSS="none",
           ASAN_OPTIONS="detect_leaks=0:abort_on_error=0:print_stacktrace=1",
           UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=0")
SIGS=("ERROR: AddressSanitizer","ERROR: LeakSanitizer","runtime error:",
      "DEADLYSIGNAL","SEGV")
def run(cmd, inp, name, cwd, t=15):
    try:
        r=subprocess.run(cmd,input=inp,text=True,stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,env=ENV,timeout=t,cwd=cwd)
        out,rc=r.stdout,r.returncode
    except subprocess.TimeoutExpired as e:
        out,rc=(e.stdout or b"").decode("utf-8","replace"),"TIMEOUT"
    hits=[s for s in SIGS if s in out]
    if hits:
        with open(os.path.join(EVID,name+".log"),"w") as f: f.write("RC:%s\n"%rc+out)
    return rc,hits

hitsall=[]; n=0
for p in sorted(glob.glob(str(_REPO_ROOT / "tests/*.ucas"))):
    n+=1; rc,h=run([BIN,os.path.basename(p)],None,"CORPUS_"+os.path.basename(p)[:-6],str(_REPO_ROOT / "tests"))
    if h: hitsall.append((os.path.basename(p),rc,h))
for p in sorted(glob.glob(str(_REPO_ROOT / "tests/json/*.jsonl"))):
    n+=1; inp=open(p).read(); rc,h=run([BIN,"--json","--files","none"],inp,"JSON_"+os.path.basename(p)[:-7],str(_REPO_ROOT / "tests/json"))
    if h: hitsall.append(("json/"+os.path.basename(p),rc,h))
for p in sorted(glob.glob(str(_REPO_ROOT / "tests/mcp/*.jsonl"))):
    n+=1; inp=open(p).read(); rc,h=run([BIN,"--mcp"],inp,"MCP_"+os.path.basename(p)[:-7],str(_REPO_ROOT / "tests/mcp"))
    if h: hitsall.append(("mcp/"+os.path.basename(p),rc,h))
print("Ran",n,"corpus files under sanitizer")
print("Sanitizer hits:",len(hitsall))
for name,rc,h in hitsall: print("  ",name,rc,h)
