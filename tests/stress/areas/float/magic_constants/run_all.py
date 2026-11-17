#!/usr/bin/env python3
"""Run every reproducer twice, check determinism, write .out goldens.

Usage:
  python3 run_all.py --check   # run twice + diff, report only
  python3 run_all.py           # run twice + diff + save golden .out
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
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UCAS = str(_REPO_ROOT / "ucas")
SAVE = "--check" not in sys.argv


def run(args, stdin_data):
    try:
        p = subprocess.run([UCAS] + args, input=stdin_data, text=True,
                           capture_output=True, timeout=30, cwd=HERE)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""


def main():
    files = sorted(glob.glob(os.path.join(HERE, "*.ucas")) +
                   glob.glob(os.path.join(HERE, "*.jsonl")))
    files = [f for f in files if os.path.basename(f) != "magic_all.ucas"]
    nd = []
    for f in files:
        name = os.path.basename(f)
        data = open(f).read()
        args = ["--mcp"] if name.endswith(".jsonl") else []
        rc1, o1 = run(args, data)
        rc2, o2 = run(args, data)
        same = (rc1 == rc2 and o1 == o2)
        print(f"{name:28s} rc={rc1}/{rc2} determinism={'OK' if same else 'DIFFER'} bytes={len(o1)}")
        if not same:
            nd.append(name)
        if SAVE and same and rc1 == 0:
            out = os.path.splitext(f)[0] + ".out"
            with open(out, "w") as fh:
                fh.write(o1)
        # flag suspicious content
        low = o1.lower()
        for kw in ["error (", "parse_error", "exception", "assert", "abort", "segmentation"]:
            if kw in low and rc1 == 0:
                print(f"    NOTE: output contains {kw!r}")
                break
    print("nondeterministic:", nd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
