#!/usr/bin/env python3
"""Re-run the SymPy differential harness and verify all CLI goldens in this folder.

Python port of verify.sh.  Deterministic environment (UCAS_NO_TIMES / UCAS_SPIRV_CROSS)
is set explicitly so the results do not depend on the caller's shell.
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

UCAS = str(_REPO_ROOT / "ucas")

ENV = dict(os.environ)
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def _tail(data, n=5):
    """Byte-for-byte equivalent of `tail -n N` on a bytes blob."""
    if not data:
        return b""
    return b"".join(data.splitlines(keepends=True)[-n:])


def _run_ucas(src, timeout=30):
    """Run `ucas <src>` with stdout+stderr combined; return (rc, combined_bytes).

    A timeout is reported as exit 124, matching the GNU `timeout` utility the
    shell original used.
    """
    try:
        p = subprocess.run([UCAS, src], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, env=ENV)
        return p.returncode, (p.stdout or b"")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"")


def main():
    os.chdir(HERE)
    out = sys.stdout.buffer

    out.write(b"== differential oracle harness (ucas vs SymPy) ==\n")
    out.flush()
    try:
        p = subprocess.run(["python3", "run_oracle.py"], stdout=subprocess.PIPE,
                           stderr=None, timeout=400, env=ENV)
        oracle_out = p.stdout or b""
    except subprocess.TimeoutExpired as e:
        # `timeout 400 ... | tail -5` keeps whatever was produced before TERM.
        oracle_out = e.stdout or b""
    out.write(_tail(oracle_out, 5))
    out.flush()

    out.write(b"\n== golden determinism / reproducibility ==\n")
    out.flush()
    status = 0
    for f in ("01_rounded_cancel", "02_rounded_limit", "03_limit_check_disagree",
              "04_incomplete", "05_branch_ok", "06_oracle_agree"):
        chk = "/tmp/opencode/second_cas_oracle_%s.chk" % f
        os.makedirs(os.path.dirname(chk), exist_ok=True)
        rc, combined = _run_ucas(f + ".ucas")
        with open(chk, "wb") as fh:
            fh.write(combined)
        if rc != 0:
            out.write(("FAIL %s (exit %d)\n" % (f, rc)).encode())
            out.flush()
            status = 1
            continue
        with open(f + ".out", "rb") as fh:
            golden = fh.read()
        if golden == combined:
            out.write(("PASS %s\n" % f).encode())
        else:
            out.write(("FAIL %s (output differs from golden)\n" % f).encode())
            status = 1
        out.flush()
    return status


if __name__ == "__main__":
    sys.exit(main())
