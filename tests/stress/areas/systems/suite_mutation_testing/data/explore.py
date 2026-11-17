#!/usr/bin/env python3
"""Exploratory scanner over tests/*.ucas + tests/*.out for bug signatures."""
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

ROOT = str(_REPO_ROOT / "tests")
cases = {}
for u in sorted(glob.glob(os.path.join(ROOT, "*.ucas"))):
    n = os.path.basename(u)[:-5]
    o = os.path.join(ROOT, n + ".out")
    if os.path.isfile(o):
        cases[n] = (open(u, encoding="utf-8", errors="replace").read(),
                    open(o, encoding="utf-8", errors="replace").read())
print("pairs:", len(cases))

# 1. equiv "differ at ... X vs X" identical printed witness values
ident = re.compile(r"differ at [^\n]*: ([^:\n]+?) vs ([^\n]+)")
print("\n=== equiv identical witness values ===")
for n,(s,o) in cases.items():
    for line in o.splitlines():
        m = ident.search(line)
        if m and m.group(1).strip() == m.group(2).strip():
            print(n, "|", line.strip()[:160])

# 2. domain says total but few points defined
print("\n=== 'total on its parameter types' tests ===")
for n,(s,o) in cases.items():
    if "total on its parameter types" in o:
        print(n, "|", [l.strip() for l in o.splitlines() if "total on" in l or "defined at" in l][:4])

# 3. wrap verdicts
print("\n=== wrap end-to-end verdicts ===")
cnt=0
for n,(s,o) in cases.items():
    for line in o.splitlines():
        if "end to end" in line or "end-to-end" in line:
            print(n, "|", line.strip()[:140]); cnt+=1
            if cnt>40: break
    if cnt>40: break

# 4. keywords per command frequency in .ucas
print("\n=== command coverage in .ucas sources ===")
cmds = ["equiv","range","domain","wrap","table","find","gates","prove","check","diff","integrate","limit","taylor","powerseries","laplace","fourier","solve","dsolve","groebner","pmsnf","primroot","abselftest","symmetry","crit","simplify","factor","expand","cancel","equiv real","real ","NaN","nanbits","ftz","snippets","fit","error","approx","proof","axioms","identify","residue","poles","fextrema","match"]
for c in cmds:
    k = sum(1 for s,o in cases.values() if c in s)
    print(f"  {c:16s} {k}")
