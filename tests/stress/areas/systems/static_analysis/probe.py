#!/usr/bin/env python3
"""Probe helper: run a single .ucas statement under timeout 10.

Replaces ``probe.sh``.  Usage: probe.py 'statement text'
Prints ``rc=N | <first 400 bytes, newlines as ~>``.
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

HERE = Path(__file__).resolve().parent
BIN = str(_REPO_ROOT / "ucas")
P = HERE / "_probe.ucas"
OUT = HERE / "_probe.out"


def main(argv):
    if len(argv) != 1:
        print("usage: probe.py 'statement text'", file=sys.stderr)
        return 2
    P.write_text(argv[0] + "\n")
    with open(OUT, "wb") as out:
        try:
            p = subprocess.run([BIN, "_probe.ucas"], cwd=str(HERE),
                               stdout=out, stderr=subprocess.STDOUT,
                               timeout=10)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    with open(OUT, "rb") as fh:
        head = fh.read(400)
    sys.stdout.buffer.write(b"rc=" + str(rc).encode() + b" | " +
                            head.replace(b"\n", b"~") + b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
