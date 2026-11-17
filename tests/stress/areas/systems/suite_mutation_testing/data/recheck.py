#!/usr/bin/env python3
"""Recheck selected mutants with a generous timeout; patch mutations.csv rows."""
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
import os, csv, subprocess, re
R=str(_REPO_ROOT / "tests"); D=os.path.dirname(os.path.abspath(__file__))
M=os.path.join(D,"..","mutations"); BIN=str(_REPO_ROOT / "ucas")
NOISE=re.compile(r"(max relative difference|max difference|residual |check:.*e[+-]\d+|elapsed|in \d+\.\d+ s)")
def sem(t):
    return "\n".join(l.rstrip() for l in t.splitlines()
                     if not l.startswith("> ") and not NOISE.search(l))
def run(n,to=60):
    try:
        p=subprocess.run([BIN,n+".ucas"],cwd=M,stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,timeout=to)
        return p.stdout.decode("utf-8","replace"),p.returncode,0
    except subprocess.TimeoutExpired as e:
        return (e.stdout or b"").decode("utf-8","replace"),124,1
rows=list(csv.DictReader(open(os.path.join(D,"mutations.csv"))))
idx={r["mutation"]:i for i,r in enumerate(rows)}
for n in ["m03","m13","m22","m15"]:
    base=rows[idx[n]]["base"]
    want=open(os.path.join(R,base+".out"),encoding="utf-8",errors="replace").read()
    g1,rc1,t1=run(n); g2,rc2,t2=run(n)
    det=(g1==g2)
    if not t1: open(os.path.join(M,n+".out"),"w",encoding="utf-8").write(g1)
    r=rows[idx[n]]
    r["deterministic"]=str(det); r["rc"]=str(rc1); r["timeout"]=str(t1)
    r["raw_detect"]=str(g1!=want); r["sem_detect"]=str(sem(g1)!=sem(want))
    print(n,"rc",rc1,"to",t1,"det",det,"raw",r["raw_detect"],"sem",r["sem_detect"])
with open(os.path.join(D,"mutations.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
