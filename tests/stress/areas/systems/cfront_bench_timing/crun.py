#!/usr/bin/env python3
"""Run one .ucas with the cc->clang wrapper, timeout 20.

Replaces ``crun.sh``.  Usage: crun.py UCARGS...
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

import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BIN = str(_REPO_ROOT / "ucas")


def main(argv):
    env = dict(os.environ)
    env["PATH"] = str(HERE / "bin") + os.pathsep + env.get("PATH", "")
    try:
        p = subprocess.run([BIN] + argv, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=20)
        out, rc = p.stdout, p.returncode
    except subprocess.TimeoutExpired as ex:
        out, rc = ex.stdout or b"", 124
    if isinstance(out, str):
        out = out.encode("utf-8", "replace")
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.write(("[EXIT=%d]\n" % rc).encode())
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
