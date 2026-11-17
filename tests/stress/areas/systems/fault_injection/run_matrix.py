#!/usr/bin/env python3
"""Run the 154-command corpus under every LD_PRELOAD shim and tally outcomes.

This is the reproducible evidence collector for FINDINGS.md / SUMMARY.md.
It never asserts success: it records what each injected fault actually did.
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
import glob
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = str(_REPO_ROOT / "ucas")
SHIM = os.path.join(HERE, "fi_shim.so")
CORPUS = sorted(glob.glob(os.path.join(HERE, "corpus", "c*.ucas")))

# (config env var, list of call indices to inject)
CONFIGS = [
    ("FI_FAIL_MALLOC",  [5, 30, 80, 150, 250, 400]),
    ("FI_FAIL_CALLOC",  [5, 30, 80, 150, 250]),
    ("FI_FAIL_REALLOC", [5, 50, 150, 250, 400]),
    ("FI_FAIL_STRDUP",  [1, 5, 12, 24, 30]),
    ("FI_FAIL_FOPEN",   [1, 2]),
    ("FI_FAIL_OPEN",    [1, 2]),
    ("FI_FAIL_FWRITE",  [1, 2]),
    ("FI_FAIL_PIPE",    [1, 2]),
    ("FI_FAIL_FORK",    [1, 2]),
    ("FI_FAIL_WAITPID", [1, 2]),
]

def run(env, args, stdin=None, timeout=8):
    e = dict(os.environ)
    e.update(env)
    e["LD_PRELOAD"] = SHIM
    try:
        p = subprocess.run([BIN] + args, input=stdin, env=e,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as ex:
        return 124, (ex.stdout or b"").decode("utf-8", "replace")

def classify(rc, out):
    if rc == 139 or "Segmentation fault" in out:
        return "SEGV"
    if rc == 124:
        return "TIMEOUT"
    if rc not in (0, 2):
        return "rc%d" % rc
    if "out of memory" in out:
        return "OOM(clean)"
    return "ok"

def main():
    lines = []
    print("corpus size:", len(CORPUS))
    for var, ns in CONFIGS:
        for n in ns:
            tally = Counter()
            fired = 0
            segv_cmds = []
            for f in CORPUS:
                rc, out = run({var: str(n)}, [f])
                cat = classify(rc, out)
                tally[cat] += 1
                if "[FI]" in out:
                    fired += 1
                if cat == "SEGV" and len(segv_cmds) < 4:
                    segv_cmds.append(os.path.basename(f))
            row = "%-16s N=%-4d fired=%-4d %s  segv_ex=%s" % (
                var, n, fired, " ".join("%s=%d" % (k, v) for k, v in sorted(tally.items())),
                ",".join(segv_cmds))
            print(row)
            lines.append(row)
    with open(os.path.join(HERE, "matrix_results.txt"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    sys.exit(main())
