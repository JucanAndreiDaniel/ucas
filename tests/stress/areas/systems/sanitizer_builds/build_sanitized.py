#!/usr/bin/env python3
"""Build a SEPARATE ASan+UBSan-instrumented ucas binary here.

Replaces ``build_sanitized.sh``.  Does NOT run ``make`` and does NOT overwrite
$ROOT/ucas.  Flags/includes/defines are reconstructed from the Makefile.
Parallel compilation uses a thread pool with bounded subprocesses instead of
``xargs -P 8 sh -c ...``.
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

HERE = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "sanitizer_builds"
SRC = _REPO_ROOT / "src"
SNX = SRC / "snxglslc"
OBJ = HERE / "obj"

SAN = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
# SNIPDIR define as received by cc after `sh -c` re-parses CFLAGS.
CFLAGS = ["-O1", "-g", "-std=gnu99", "-fno-omit-frame-pointer"] + SAN + [
    "-I" + str(SRC),
    "-I" + str(HERE),
    "-DCF_HAVE_X86",
    '-DUCAS_SNIPDIR="%s/snippets"' % ROOT,
]
SNX_NAMES = ["lexer", "parser", "emit", "builtins", "glslc"]


def compile_one(src, obj):
    err_path = obj.with_suffix(".err")
    with open(err_path, "wb") as err:
        try:
            p = subprocess.run(["cc"] + CFLAGS + ["-w", "-c", str(src),
                                "-o", str(obj)], stdout=subprocess.DEVNULL,
                               stderr=err, timeout=600)
            return src, p.returncode, err_path
        except subprocess.TimeoutExpired:
            return src, 124, err_path


def report_failure(src, err_path):
    sys.stderr.write("FAILED: %s\n" % src)
    if err_path.exists():
        sys.stderr.buffer.write(err_path.read_bytes())


def main():
    OBJ.mkdir(parents=True, exist_ok=True)
    for old in OBJ.glob("*.o"):
        old.unlink()
    san_bin = HERE / "ucas_san"
    if san_bin.exists():
        san_bin.unlink()

    # find "$SRC" -maxdepth 1 -name '*.c' -print  (no sort in the original)
    srclist = [p for p in SRC.glob("*.c") if p.is_file()]
    (HERE / "srclist.txt").write_text(
        "".join(str(p) + "\n" for p in srclist))
    snxlist = [SNX / (n + ".c") for n in SNX_NAMES]
    (HERE / "snxlist.txt").write_text(
        "".join(str(p) + "\n" for p in snxlist))

    jobs = [(p, OBJ / (p.name[:-2] + ".o")) for p in srclist]
    jobs += [(p, OBJ / ("snx_" + p.name[:-2] + ".o")) for p in snxlist]

    failed = False
    with ThreadPoolExecutor(max_workers=8) as pool:
        for src, rc, err_path in pool.map(lambda t: compile_one(*t), jobs):
            if rc != 0:
                failed = True
                report_failure(src, err_path)
    if failed:
        return 1

    nobj = len(list(OBJ.glob("*.o")))
    print("Compiled %d objects; linking..." % nobj)
    objfiles = sorted(OBJ.glob("*.o"))
    p = subprocess.run(["cc"] + SAN + ["-g"] + [str(o) for o in objfiles] +
                       ["-lm", "-o", str(san_bin)], timeout=900)
    if p.returncode != 0:
        return 1
    print("Built %s" % san_bin)
    subprocess.run(["ls", "-la", str(san_bin)], timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
