#!/usr/bin/env python3
"""Run the clang static analyzer across ucas core sources, in parallel.

Replaces ``run_clang_analyze.sh``.  All output is confined to analysis/.
Does NOT rebuild the shipped binary.  Instead of emitting a ``_one.sh`` helper
via a quoted heredoc, this invokes the converted ``analysis/_one.py`` directly
(ROOT is derived there from __file__).
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

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "static_analysis"
OUT = HERE / "analysis"
HELPER = OUT / "_one.py"


def analyze_one(f):
    try:
        p = subprocess.run([sys.executable, str(HELPER), f], cwd=ROOT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=300)
        return p.stdout
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout or ""
        return out if isinstance(out, str) else out.decode("utf-8", "replace")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # find src -maxdepth 1 -name '*.c' | sort
    srcs = sorted("src/" + p.name for p in (_REPO_ROOT / "src").glob("*.c")
                  if p.is_file())
    (OUT / "src_list.txt").write_text("".join(s + "\n" for s in srcs))

    with ThreadPoolExecutor(max_workers=6) as pool:
        lines = list(pool.map(analyze_one, srcs))
    (OUT / "clang_status.tsv").write_text("".join(lines))
    print("DONE clang analyze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
