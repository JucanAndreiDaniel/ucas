#!/usr/bin/env python3
"""Run every top-level tests/*.ucas against the shipped binary; record match status."""
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
import glob, os, subprocess, csv, json, time
R=str(_REPO_ROOT / "tests")
BIN=str(_REPO_ROOT / "ucas")
OUT=os.path.dirname(os.path.abspath(__file__))
rows=[]
files=sorted(glob.glob(os.path.join(R,"*.ucas")))
for u in files:
    n=os.path.basename(u)[:-5]
    o=os.path.join(R,n+".out")
    if not os.path.isfile(o): continue
    want=open(o,"rb").read()
    try:
        p=subprocess.run([BIN,n+".ucas"],cwd=R,stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,timeout=4)
        got=p.stdout; rc=p.returncode; to=0
    except subprocess.TimeoutExpired as e:
        got=e.stdout or b""; rc=124; to=1
    rows.append(dict(name=n,rc=rc,timeout=to,
                     match=(got==want),
                     bytes_got=len(got),bytes_want=len(want)))
with open(os.path.join(OUT,"baseline.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["name","rc","timeout","match","bytes_got","bytes_want"])
    w.writeheader(); w.writerows(rows)
from collections import Counter
c=Counter(("match" if r["match"] else "differ", "rc0" if r["rc"]==0 else ("to" if r["timeout"] else "rc"+str(r["rc"]))) for r in rows)
print("total",len(rows))
print("match",sum(r["match"] for r in rows),"differ",sum(not r["match"] for r in rows))
print("timeouts",sum(r["timeout"] for r in rows),"nonzero_rc",sum(r["rc"] not in (0,124) for r in rows))
print("differ names:", [r["name"] for r in rows if not r["match"]])
