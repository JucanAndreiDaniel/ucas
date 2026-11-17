#!/usr/bin/env python3
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
import os, subprocess, glob
BIN=str(_HERE / "ucas_san")
EVID=str(_HERE / "evidence")
ENV=dict(os.environ); ENV.update(UCAS_NO_TIMES="1",UCAS_SPIRV_CROSS="none",
  ASAN_OPTIONS="detect_leaks=0:abort_on_error=0:print_stacktrace=1",
  UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=0")
SIGS=("ERROR: AddressSanitizer","ERROR: LeakSanitizer","runtime error:","DEADLYSIGNAL","SEGV")
done={"absalg","calculus","catalogue","cfbridge_ic","cfbridge","csim","ev","exptable","findloophoist","glslview","glslview_absent","homal","idrw6"}
files=sorted(glob.glob(str(_REPO_ROOT / "tests/*.ucas")))
n=0
for p in files:
    name=os.path.basename(p)[:-6]
    if name in done: continue
    n+=1
    try:
        r=subprocess.run([BIN,os.path.basename(p)],text=True,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,env=ENV,timeout=12,cwd=str(_REPO_ROOT / "tests"))
        out,rc=r.stdout,r.returncode
    except subprocess.TimeoutExpired as e:
        out,rc=(e.stdout or b"").decode("utf-8","replace"),"TIMEOUT"
    hits=[s for s in SIGS if s in out]
    if hits:
        open(os.path.join(EVID,"CORPUS_"+name+".log"),"w").write("RC:%s\n"%rc+out)
        print("HIT",name,rc,hits,flush=True)
print("DONE remainder",n,flush=True)
