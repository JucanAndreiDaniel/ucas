#!/usr/bin/env python3
"""Generate goldens: run each twice under timeout 20; keep byte-identical output.

Replaces ``make_goldens.sh``.  This is a GENERATOR (``make_*``), never invoked
by ``manual-only generator`` and never run as part of verification.  Writing to ``.out``
goldens is intentional here, exactly as in the original script.
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
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
BIN = str(_REPO_ROOT / "ucas")


def run_to(argv, out_path, stdin_path=None):
    """timeout 20 BIN ... < stdin > out 2>&1 ; returns exit code."""
    with open(out_path, "wb") as out:
        kw = dict(stdout=out, stderr=subprocess.STDOUT, timeout=20)
        if stdin_path is not None:
            kw["stdin"] = open(stdin_path, "rb")
        try:
            p = subprocess.run(argv, **kw)
            return p.returncode
        except subprocess.TimeoutExpired:
            return 124
        finally:
            if "stdin" in kw:
                kw["stdin"].close()


def same_bytes(a, b):
    return a.read_bytes() == b.read_bytes()


def main():
    nd_path = HERE / "nondeterministic.txt"
    nd_path.write_bytes(b"")

    for corpus in sorted(HERE.glob("*.ucas")):
        n = corpus.name[:-6] if corpus.name.endswith(".ucas") else corpus.name
        r1, r2 = HERE / (n + ".r1"), HERE / (n + ".r2")
        rc1 = run_to([BIN, corpus.name], r1)
        rc2 = run_to([BIN, corpus.name], r2)

        if rc1 != rc2:
            with open(nd_path, "a") as fh:
                fh.write("%s rc1=%s rc2=%s (exit differs)\n" % (n, rc1, rc2))
            r1.unlink(missing_ok=True)
            r2.unlink(missing_ok=True)
            continue
        if rc1 != 0:
            with open(nd_path, "a") as fh:
                fh.write("%s rc=%s (nonzero, skip golden)\n" % (n, rc1))
            r1.unlink(missing_ok=True)
            r2.unlink(missing_ok=True)
            continue
        if not same_bytes(r1, r2):
            with open(nd_path, "a") as fh:
                fh.write("%s (output differs between runs, skip golden)\n" % n)
            shutil.copyfile(r1, HERE / (n + ".diff1"))
            shutil.copyfile(r2, HERE / (n + ".diff2"))
            r1.unlink(missing_ok=True)
            r2.unlink(missing_ok=True)
            continue

        os.replace(r1, HERE / (n + ".out"))
        r2.unlink(missing_ok=True)
        print("OK %s" % n)

    for kind in ("mcp_bench", "json_bench"):
        jsonl = HERE / (kind + ".jsonl")
        r1, r2 = HERE / (kind + ".r1"), HERE / (kind + ".r2")
        rc1 = run_to([BIN, "--mcp"], r1, stdin_path=jsonl)
        rc2 = run_to([BIN, "--mcp"], r2, stdin_path=jsonl)
        if kind == "json_bench":
            rc1 = run_to([BIN, "--json", "--files", "none"], r1,
                         stdin_path=jsonl)
            rc2 = run_to([BIN, "--json", "--files", "none"], r2,
                         stdin_path=jsonl)
        if rc1 == 0 and rc2 == 0 and same_bytes(r1, r2):
            os.replace(r1, HERE / (kind + ".out"))
            r2.unlink(missing_ok=True)
            print("OK %s" % kind)
        else:
            with open(nd_path, "a") as fh:
                fh.write("%s rc1=%s rc2=%s (skip golden)\n" %
                         (kind, rc1, rc2))
            r1.unlink(missing_ok=True)
            r2.unlink(missing_ok=True)

    print("=== nondeterministic.txt ===")
    if nd_path.exists():
        with open(nd_path, "rb") as fh:
            os.write(1, fh.read())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
