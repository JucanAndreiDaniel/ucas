#!/usr/bin/env python3
"""Regenerate CLI golden outputs and verify determinism.

Python port of gen_goldens.sh.  NOTE: this script OVERWRITES the .out goldens in
this folder (that is its purpose); do not run it when auditing goldens.

Deterministic environment (UCAS_NO_TIMES / UCAS_SPIRV_CROSS) is set explicitly
to match how the goldens are produced by `make test`.
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

import glob
import os
import subprocess
import sys

B = str(_REPO_ROOT / "ucas")

ENV = dict(os.environ)
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def _run(args, stdin=None, timeout=30):
    """Run the ucas binary; return (rc, stdout+stderr combined bytes).

    Exit 124 on timeout matches the GNU `timeout` utility used by the shell
    original.
    """
    try:
        p = subprocess.run([B] + list(args), input=stdin, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, env=ENV)
        return p.returncode, (p.stdout or b"")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"")


def main():
    os.chdir(HERE)
    fail = 0

    for f in sorted(glob.glob("*.ucas")):
        name = os.path.splitext(f)[0]
        rc, first = _run([f])
        with open(name + ".out", "wb") as fh:
            fh.write(first)
        rc2, second = _run([f])
        with open(name + ".out.2", "wb") as fh:
            fh.write(second)
        if rc != 0 or rc2 != 0:
            print("NONZERO %s rc=%d/%d" % (name, rc, rc2))
            fail = 1
        if first != second:
            print("NONDETERMINISTIC %s" % name)
            fail = 1
        os.remove(name + ".out.2")

    for f in sorted(glob.glob("*.jsonl")):
        name = os.path.splitext(f)[0]
        flags = []
        flag_file = name + ".flags"
        if os.path.isfile(flag_file):
            with open(flag_file, "r") as fh:
                flags = fh.read().split()   # shell: flags=$(cat "$name.flags"); --mcp $flags
        with open(f, "rb") as fh:
            payload = fh.read()
        rc, first = _run(["--mcp"] + flags, stdin=payload)
        with open(name + ".out", "wb") as fh:
            fh.write(first)
        rc2, second = _run(["--mcp"] + flags, stdin=payload)
        with open(name + ".out.2", "wb") as fh:
            fh.write(second)
        if rc != 0 or rc2 != 0:
            print("NONZERO %s rc=%d/%d" % (name, rc, rc2))
            fail = 1
        if first != second:
            print("NONDETERMINISTIC %s" % name)
            fail = 1
        os.remove(name + ".out.2")

    if fail == 0:
        print("ALL GOLDENS DETERMINISTIC")
    return fail


if __name__ == "__main__":
    sys.exit(main())
