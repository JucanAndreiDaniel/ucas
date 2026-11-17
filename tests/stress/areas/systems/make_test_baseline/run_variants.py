#!/usr/bin/env python3
"""Run the fast suites (json + mcp) under each altered environment.

Replaces ``run_variants.sh``.  Usage: run_variants.py [json|mcp|both]
Each replay is bounded by timeout 300 (per-suite 300s, per-test 45s).
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
REPLAY = HERE / "replay.py"
DB = "UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none"


def run(label, extra, base, sec):
    for s in ("json", "mcp"):
        if sec not in ("both", s):
            continue
        print("### %s / %s" % (label, s))
        sys.stdout.flush()
        subprocess.run([sys.executable, str(REPLAY), "%s-%s" % (label, s),
                        extra, base, "45", "300", s],
                       cwd=str(HERE), stderr=subprocess.STDOUT, timeout=300)


def main(argv):
    sec = argv[0] if argv else "both"
    run("seed0", "UCAS_SEED=0", DB, sec)
    run("seed1", "UCAS_SEED=1", DB, sec)
    run("lcC", "LC_ALL=C", DB, sec)
    run("lcRO", "LC_ALL=ro_RO.utf8", DB, sec)
    run("notimes_off", "", "UCAS_SPIRV_CROSS=none", sec)
    run("spv_bogus", "",
        "UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=/nonexistent/spirv-cross", sec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
