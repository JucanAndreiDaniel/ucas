#!/usr/bin/env python3
"""Folder-local golden runner for piped-stdin interactive scenarios.

The stress harness invokes this script and checks only our exit status, so we
do the per-scenario diffing ourselves.  Every binary run is bounded by a
30-second subprocess timeout, and only deterministic scenarios appear here.
"""

import os
import subprocess
import sys
from pathlib import Path


def _find_root(start):
    p = Path(start).resolve()
    while True:
        if (p / "ucas").is_file() and (p / "src").is_dir():
            return p
        parent = p.parent
        if parent == p:
            raise SystemExit("cannot find repo root")
        p = parent


HERE = Path(__file__).resolve().parent
ROOT = _find_root(HERE)
BIN = ROOT / "ucas"

ENV = os.environ.copy()
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"

PLAIN = ["sin_basic", "sin_partial", "sin_eof_mid", "sin_crlf", "sin_no_newline",
         "sin_blank", "sin_crlf_multiline", "sin_ambig", "sin_defs", "sin_long",
         "sin_many"]


def run(cmd, stdin_obj, got):
    with open(got, "wb") as g:
        try:
            return subprocess.run(cmd, stdin=stdin_obj, stdout=g,
                                  stderr=subprocess.STDOUT, timeout=30,
                                  cwd=str(HERE), env=ENV).returncode
        except subprocess.TimeoutExpired:
            return 124


def check(name):
    want = HERE / f"{name}.out"
    got = HERE / f"{name}.got"
    diff = HERE / f"{name}.diff"
    with open(diff, "wb") as df:
        d = subprocess.run(["diff", "-u", str(want), str(got)],
                           stdout=df, stderr=subprocess.STDOUT)
    ok = d.returncode == 0
    if ok:
        diff.unlink(missing_ok=True)
    got.unlink(missing_ok=True)
    return ok


def main():
    fail = 0

    # plain: ucas < NAME.txt
    for n in PLAIN:
        with open(HERE / f"{n}.txt", "rb") as f:
            run([str(BIN)], f, HERE / f"{n}.got")
        if not check(n):
            fail += 1

    # ucas -i < file : ambiguity question swallows the next statement (golden)
    with open(HERE / "sin_ambig_i.txt", "rb") as f:
        run([str(BIN), "-i"], f, HERE / "sin_ambig_i.got")
    if not check("sin_ambig_i"):
        fail += 1

    # mixing a file argument with piped stdin: stdin is ignored
    with open(HERE / "sin_basic.txt", "rb") as f:
        run([str(BIN), "sin_filearg.ucas"], f, HERE / "sin_mixed.got")
    if not check("sin_mixed"):
        fail += 1

    # stdin redirected from a directory: clean exit, no output
    fd = os.open(str(HERE), os.O_RDONLY)
    try:
        run([str(BIN)], fd, HERE / "sin_dir.got")
    finally:
        os.close(fd)
    if not check("sin_dir"):
        fail += 1

    if fail:
        print(f"stdin_interactive: {fail} mismatches")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
