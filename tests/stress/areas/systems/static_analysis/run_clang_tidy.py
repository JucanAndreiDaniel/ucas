#!/usr/bin/env python3
"""clang-tidy pass (selected checks) across core sources, parallel.

Replaces ``run_clang_tidy.sh``.  Uses the converted ``analysis/_tidyone.py``
helper instead of generating a ``_tidyone.sh`` heredoc.  Reads the source list
produced by run_clang_analyze.py.
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

OUT = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "static_analysis" / "analysis"
HELPER = OUT / "_tidyone.py"


def tidy_one(f):
    try:
        p = subprocess.run([sys.executable, str(HELPER), f], cwd=ROOT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=260)
        return p.stdout
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout or ""
        return out if isinstance(out, str) else out.decode("utf-8", "replace")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    srcs = (OUT / "src_list.txt").read_text().splitlines()
    with ThreadPoolExecutor(max_workers=6) as pool:
        lines = list(pool.map(tidy_one, srcs))
    (OUT / "tidy_status.tsv").write_text("".join(lines))
    print("DONE_TIDY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
