#!/usr/bin/env python3
"""Compile one source file for a build variant.

Replaces ``worker.sh``.  Usage: worker.py NAME SRC OBJ
NAME selects CC/FLAGS from config.py (the former config_NAME.sh).
Every subprocess is bounded by a timeout.
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

import sys
import subprocess

# Ensure the sibling config.py is importable however this script is launched
# (``python3 worker.py`` already does this; importing as a module does not).
sys.path.insert(0, str(_ROOT_PATH(__file__).resolve().parent))
from config import VARIANTS

SRC = _REPO_ROOT / "src"

# bash: COMMON=(-std=c99 -D_GNU_SOURCE -w -DCF_HAVE_X86
#              -DUCAS_SNIPDIR="\"$ROOT/snippets\"" -I"$SRC" -I"$ROOT")
COMMON = [
    "-std=c99",
    "-D_GNU_SOURCE",
    "-w",
    "-DCF_HAVE_X86",
    '-DUCAS_SNIPDIR="%s/snippets"' % ROOT,
    "-I" + str(SRC),
    "-I" + ROOT,
]


def main(argv):
    if len(argv) != 3:
        print("usage: worker.py NAME SRC OBJ", file=sys.stderr)
        return 2
    name, src, obj = argv
    cfg = VARIANTS[name]                       # replaces: . config_NAME.sh
    cc = cfg["CC"]
    flags = cfg["FLAGS"].split()               # unquoted $FLAGS word splitting
    cmd = [cc] + COMMON + flags + ["-c", src, "-o", obj]
    # Original had no timeout; a generous bound is added for safety.
    p = subprocess.run(cmd, timeout=300)
    return p.returncode                        # set -e: propagate failure


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
