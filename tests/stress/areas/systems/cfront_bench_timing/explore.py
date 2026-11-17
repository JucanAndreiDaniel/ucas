#!/usr/bin/env python3
"""Exploration helper (not a golden).  Run a .ucas file under timeout 20.

Replaces ``explore.sh``.  Usage: explore.py FILE LABEL [clang|gcc]
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
    if len(argv) < 2:
        print("usage: explore.py FILE LABEL [clang|gcc]", file=sys.stderr)
        return 2
    f, label = argv[0], argv[1]
    mode = argv[2] if len(argv) > 2 else "gcc"

    env = dict(os.environ)
    if mode == "clang":
        env["PATH"] = str(HERE / "bin") + os.pathsep + env.get("PATH", "")
    try:
        p = subprocess.run([BIN, f], env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=20)
        out, rc = p.stdout, p.returncode
    except subprocess.TimeoutExpired as ex:
        out, rc = ex.stdout or b"", 124
    if isinstance(out, str):
        out = out.encode("utf-8", "replace")
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.write(
        ("[EXIT=%d LABEL=%s MODE=%s]\n" % (rc, label, mode)).encode())
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
