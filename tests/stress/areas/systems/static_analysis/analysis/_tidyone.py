#!/usr/bin/env python3
"""Run clang-tidy (selected checks) on one C source (helper for run_clang_tidy.py).

Replaces ``analysis/_tidyone.sh``.  Usage: _tidyone.py SRC.c
"""
# --- portability: derive the repo root from this file's own location -------
# Walk up until a directory containing both the `ucas` binary and `src/` is found.
from pathlib import Path as _ROOT_PATH
from pathlib import Path
def _repo_root():
    here = _ROOT_PATH(__file__).resolve()
    for d in here.parents:
        if (d / 'ucas').is_file() and (d / 'src').is_dir():
            return d
    raise RuntimeError('ucas repo root not found above ' + str(here))
_REPO_ROOT = _repo_root()
ROOT = str(_REPO_ROOT)

import subprocess
import sys

OUT = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "static_analysis" / "analysis"

CHECKS = ("-*,clang-analyzer-*,bugprone-*,misc-*,-misc-no-recursion,"
          "-bugprone-easily-swappable-parameters,-bugprone-narrowing-conversions")
EXTRA = ["--", "-Isrc", "-I.", "-DCF_HAVE_X86",
         '-DUCAS_SNIPDIR="%s/snippets"' % ROOT,
         "-std=gnu99", "-D_GNU_SOURCE"]


def main(argv):
    if len(argv) != 1:
        return 2
    f = argv[0]
    name = Path(f).name
    base = name[:-2] if name.endswith(".c") else name
    out_path = OUT / ("tidy_" + base + ".txt")
    argv_cmd = ["clang-tidy", f, "--quiet", "-checks=" + CHECKS] + EXTRA
    with open(out_path, "wb") as out:
        try:
            p = subprocess.run(argv_cmd, cwd=ROOT, stdout=out,
                               stderr=subprocess.STDOUT, timeout=200)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    with open(out_path, "r", errors="replace") as fh:
        w = sum(1 for line in fh if "warning:" in line)
    print("%s\t%s\t%s" % (base, rc, w))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
