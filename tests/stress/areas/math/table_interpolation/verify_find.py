#!/usr/bin/env python3
"""Differential test: for random small tables, ask `find` for the packed
one-constant form, define a function from it, and check `equiv` against the
original table function.  Any counterexample is a bug in either find or the
table evaluator.
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
_HERE = _ROOT_PATH(__file__).resolve().parent
import subprocess, random, re, sys

BIN = str(_REPO_ROOT / "ucas")
CWD = str(_HERE)

def run(src, timeout=25):
    p = subprocess.run([BIN], input=src, text=True, capture_output=True,
                       timeout=timeout, cwd=CWD)
    return p.stdout + p.stderr

def extract_packed(out):
    for line in out.splitlines():
        if "packed table in one constant" in line and line.strip().startswith("cost"):
            # format: '  cost 3   EXPR    packed table in one constant'
            m = re.match(r"\s*cost\s+\S+\s+(.*?)\s{2,}packed table in one constant", line)
            if m:
                return m.group(1).strip()
    return None

def main():
    random.seed(12345)
    bad = []
    tested = 0
    for t in range(40):
        n = random.choice([4, 8, 10, 12, 16])
        bits = random.choice([1, 2])
        maxv = (1 << bits) - 1
        vals = [random.randint(0, maxv) for _ in range(n)]
        # range 1..n so find's baseline index is x-1 (exercises coercion)
        tab = "[" + ",".join(map(str, vals)) + "]"
        ty = "u4" if n <= 16 else "u8"
        # build source: define table function, run find, then define packed and equiv
        src = (f"tabf(x: {ty} in 1..{n}) = {tab}[x-1]\n"
               f"find tabf\n")
        out = run(src)
        packed = extract_packed(out)
        if not packed:
            continue
        # packed expr refers to x; build a second function and equiv
        src2 = (f"tabf(x: {ty} in 1..{n}) = {tab}[x-1]\n"
                f"pkf(x: {ty} in 1..{n}) = {packed}\n"
                f"equiv tabf pkf\n")
        out2 = run(src2)
        tested += 1
        eqline = [l for l in out2.splitlines() if "equal on the domain" in l or "differ" in l or "differ at" in l]
        ok = any("equal on the domain" in l for l in eqline)
        if not ok:
            bad.append((n, vals, packed, out2))
    print("tested", tested, "bad", len(bad))
    for n, vals, packed, out2 in bad[:10]:
        print("=== n", n, "vals", vals, "packed", packed)
        print(out2)
    return bad

if __name__ == "__main__":
    sys.exit(0 if not main() else 1)
