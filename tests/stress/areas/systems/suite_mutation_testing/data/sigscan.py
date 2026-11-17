#!/usr/bin/env python3
"""Scan golden outputs for specific buggy signatures from MASTER_FINDINGS.md."""
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
import os, re, glob
R=str(_REPO_ROOT / "tests")
cases={}
for u in sorted(glob.glob(os.path.join(R,"*.ucas"))):
    n=os.path.basename(u)[:-5]; o=os.path.join(R,n+".out")
    if os.path.isfile(o):
        cases[n]=(open(u,errors="replace").read(),open(o,errors="replace").read())

sigs = {
 "wrap_diff0": (r"differs from the mathematical result at 0 points", "out"),
 "wrap_nsw_fail": (r"nsw fails", "out"),
 "vacuous_sat": (r"equal[^\n]*proved by SAT", "out"),
 "equal_exhaustive": (r"are equal on the domain[^\n]*\(exhaustive\)", "out"),
 "equal_sampled": (r"are equal[^\n]*sampled", "out"),
 "NaN_payload": (r"NaN 0x[0-9a-f]+ vs NaN 0x[0-9a-f]+", "out"),
 "total_but_sparse": (r"total on its parameter types", "out"),
 "sampled_not_exhaustive": (r"not exhaustive", "out"),
 "sound_bound": (r"sound bound", "out"),
 "no_value": (r"no value: none of", "out"),
 "identical_witness": (r"differ at [^\n]*: (.*) vs \1", "out"),
 "symmetry": (r"symmetr", "out"),
 "taylor": (r"taylor", "src"),
 "powerseries": (r"powerseries", "out"),
 "laplace": (r"laplace", "out"),
 "fourier": (r"fourier", "out"),
 "groebner": (r"groebner", "src"),
 "pmsnf": (r"pmsnf", "src"),
 "primroot": (r"primroot", "src"),
 "abselftest": (r"abselftest", "src"),
 "1e400": (r"1e400", "out"),
 "trillion": (r"trillion", "out"),
 "billion_billion": (r"billion", "out"),
 "is_less": (r"is 1 < 2 < 3", "out"),
 "sec_limit": (r"limit[^\n]*sec", "out"),
}
for name,(pat,which) in sigs.items():
    rx=re.compile(pat)
    hits=[]
    for n,(s,o) in cases.items():
        txt=o if which=="out" else s
        if rx.search(txt): hits.append(n)
    print(f"{name:24s} {len(hits):3d}  {hits[:14]}")
