#!/usr/bin/env python3
"""Extra tiny, fast seeds covering diverse command families (read-only grammar
probes; all writes stay in this folder).

Python port of makeseeds.sh.
"""
# --- portability: derive the repo root from this file's own location -------
# Walk up until a directory containing both the `ucas` binary and `src/` is found.
from pathlib import Path as _ROOT_PATH


def _repo_root():
    here = _ROOT_PATH(__file__).resolve()
    for d in here.parents:
        if (d / "ucas").is_file() and (d / "src").is_dir():
            return d
    raise RuntimeError("ucas repo root not found above " + str(here))


_REPO_ROOT = _repo_root()
ROOT = str(_REPO_ROOT)
HERE = str(_ROOT_PATH(__file__).resolve().parent)

import os
import sys

SEEDS = [
    "simplify x^2/x",
    "factor x^4 - 1",
    "expand (x+1)^5",
    "range x^3 - 3x",
    "equiv x+y y+x",
    "f(x: u8) = x + 1\nwrap f\ndomain f",
    "diff sin(x)*x",
    "integrate x^2 from 0 to 1",
    "lim x->0 sin(x)/x",
    "solve x^2 = 4",
    "identify 1,4,9,16,25",
    "what is the derivative of x squared",
    "u8 x = 255 + 1",
    "bigint 2^100",
    "find f in {x+y, y+x, x-y} under zen4",
    "cost (a+b)*c",
    "ring z/5: (2+3)*4",
    "approx x^2 on -1..1",
    "simplify sqrt(x^2)",
    "SAT x^2 + 1 = 0",
    "show x + y",
    "crit x^3 - 3x",
    "together 1/x + 1/(x+1)",
    "check equiv x*x x^2",
]


def main():
    d = os.path.join(HERE, "fastseeds")
    if not os.path.isdir(d):
        sys.exit(1)          # shell: cd "$(dirname "$0")/fastseeds" || exit 1
    os.chdir(d)
    for i, seed in enumerate(SEEDS, 1):
        with open("g%d.ucas" % i, "wb") as fh:
            fh.write((seed + "\n").encode())   # shell: printf '%s\n' "$1" > "g$i.ucas"
    print("extra grammar seeds: %d" % len(SEEDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
