#!/usr/bin/env python3
"""Regenerate the independent-oracle differential report (writes to _scratch/).

Golden .out files are NOT regenerated here: generate them with the commands in
SUMMARY.md and verify determinism by running each twice and diffing.

Python port of run.sh (which was simply `cd` + `exec python3 harness.py`).
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
import subprocess
import sys

ENV = dict(os.environ)
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def main():
    try:
        # A generous safety timeout; the original `exec` had none, so this is
        # only a runaway-process guard and never fires for a normal harness run.
        p = subprocess.run(["python3", "harness.py"], cwd=HERE, env=ENV,
                           timeout=3600)
        return p.returncode
    except subprocess.TimeoutExpired:
        sys.stderr.write("TIMEOUT: harness.py exceeded 3600s\n")
        return 124


if __name__ == "__main__":
    sys.exit(main())
