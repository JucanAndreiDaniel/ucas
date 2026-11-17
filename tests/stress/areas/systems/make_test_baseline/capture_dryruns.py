#!/usr/bin/env python3
"""Capture non-mutating evidence that the official make targets would rebuild.

Replaces ``capture_dryruns.sh``.  Writes dryruns.log and build_context.log in
this folder.  ``bmake -n`` / ``make -n`` are dry runs; no golden is touched.
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

import shutil
import subprocess

REPO = str(_REPO_ROOT)
HERE = Path(__file__).resolve().parent


def run(argv, timeout=60):
    """Return combined stdout+stderr bytes of a bounded subprocess."""
    try:
        p = subprocess.run(argv, cwd=str(HERE), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.stdout
    except subprocess.TimeoutExpired as ex:
        return ex.stdout or b""


def combined(parts):
    if isinstance(parts, str):
        return parts.encode()
    return parts


def main():
    # ---- dryruns.log -------------------------------------------------------
    chunks = []
    for target in ("test", "json-test", "mcp-test", "libc-test"):
        chunks.append(("### bmake -n %s\n" % target).encode())
        chunks.append(run(["bmake", "-C", REPO, "-n", target]))
    with open(HERE / "dryruns.log", "wb") as fh:
        fh.write(b"".join(combined(c) for c in chunks))

    # ---- build_context.log -------------------------------------------------
    ctx = []
    ctx.append(b"### which make / bmake\n")
    ctx.append(run(["which", "make", "bmake"]))
    ctx.append(b"### GNU make -n test (cannot parse BSD Makefile)\n")
    ctx.append(run(["make", "-C", REPO, "-n", "test"]))
    ctx.append(b"### binary / source mtimes\n")
    ctx.append(run(["stat", "-c", "%y %s %n", REPO + "/ucas"]))
    # find "$REPO/src" -name '*.c' -newer "$REPO/ucas" -printf ... | sort
    find_out = run(["find", REPO + "/src", "-name", "*.c",
                    "-newer", REPO + "/ucas",
                    "-printf", "%TY-%Tm-%Td %TH:%TM:%TS %p\n"])
    lines = find_out.decode("utf-8", "replace").splitlines()
    ctx.append(("\n".join(sorted(lines)) + ("\n" if lines else "")).encode())
    ctx.append(b"### golden mtimes (sample)\n")
    ctx.append(run(["stat", "-c", "%y %n",
                    REPO + "/tests/absalg.out",
                    REPO + "/tests/calc.out",
                    REPO + "/tests/json/calculus.out",
                    REPO + "/tests/mcp/calls.out"]))
    ctx.append(b"### tool availability (test .needs)\n")
    for t in ("spirv-cross", "spirv-val", "glslangValidator",
              "spirv-as", "spirv-opt"):
        found = shutil.which(t) or "MISSING"
        ctx.append(("%-18s %s\n" % (t, found)).encode())
    ctx.append(b"### locales\n")
    locale_out = run(["locale", "-a"]).decode("utf-8", "replace").splitlines()
    ctx.append(("\n".join(locale_out[:20]) +
                ("\n" if locale_out[:20] else "")).encode())

    with open(HERE / "build_context.log", "wb") as fh:
        fh.write(b"".join(ctx))

    print("wrote dryruns.log build_context.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
