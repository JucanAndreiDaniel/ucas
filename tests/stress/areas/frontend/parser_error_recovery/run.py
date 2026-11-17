#!/usr/bin/env python3
"""Run every .ucas twice; keep a .out golden only for deterministic, non-crashing runs."""
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
BIN = str(_REPO_ROOT / "ucas")
TIMEOUT = 15


def run(path):
    try:
        r = subprocess.run(
            ["timeout", str(TIMEOUT), BIN, os.path.basename(path)],
            cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=TIMEOUT + 5,
        )
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        return "HANG", b""


def main():
    files = sorted(glob.glob(os.path.join(HERE, "*.ucas")))
    kept, nondet, crash, hang = [], [], [], []
    for path in files:
        c1, o1 = run(path)
        c2, o2 = run(path)
        base = os.path.basename(path)
        golden = path[:-5] + ".out"
        if c1 == "HANG" or c2 == "HANG":
            hang.append((base, c1, c2))
            continue
        if c1 != 0 or c2 != 0:
            crash.append((base, c1, c2, o1[:300]))
            continue
        if o1 != o2:
            nondet.append((base, o1[:300], o2[:300]))
            continue
        with open(golden, "wb") as f:
            f.write(o1)
        kept.append(base)

    print(f"files={len(files)} goldens={len(kept)} nondet={len(nondet)} crash={len(crash)} hang={len(hang)}")
    for tag, rows in (("NONDET", nondet), ("CRASH", crash), ("HANG", hang)):
        for row in rows:
            print(tag, row)


if __name__ == "__main__":
    main()
