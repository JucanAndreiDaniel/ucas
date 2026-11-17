#!/usr/bin/env python3
"""Run every generated case with default cc (gcc), timeout 20.

Replaces ``run_all.sh``.  Records exit + key-line counts in
results_gcc_summary.txt.
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

import re
import subprocess

HERE = Path(__file__).resolve().parent
BIN = str(_REPO_ROOT / "ucas")
OUT = HERE / "results_gcc"
CASES = HERE / "cases"
SUMMARY = HERE / "results_gcc_summary.txt"

RE_BENCH = re.compile(r"^  bench ")
RE_COMPILE = re.compile(r"does not compile")
RE_CRASH = re.compile(r"Assertion|Segmentation|abort|core dumped|sanitizer")


def grep_count(path, pattern):
    try:
        with open(path, "r", errors="replace") as fh:
            return sum(1 for line in fh if pattern.search(line))
    except OSError:
        return 0


def run_case(f, out_path):
    with open(out_path, "wb") as out:
        try:
            p = subprocess.run([BIN, str(f)], stdout=out,
                               stderr=subprocess.STDOUT, timeout=20)
            return p.returncode
        except subprocess.TimeoutExpired:
            return 124


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text("")
    total = 0
    for f in sorted(CASES.glob("*.ucas")):
        n = f.name[:-6] if f.name.endswith(".ucas") else f.name
        out_path = OUT / (n + ".out")
        rc = run_case(f, out_path)
        timing = grep_count(out_path, RE_BENCH)
        compfail = grep_count(out_path, RE_COMPILE)
        crash = grep_count(out_path, RE_CRASH)
        with open(SUMMARY, "a") as fh:
            fh.write("%s rc=%s timing=%s compfail=%s crash=%s\n" %
                     (n, rc, timing, compfail, crash))
        total += 1
    print("done %d cases" % total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
