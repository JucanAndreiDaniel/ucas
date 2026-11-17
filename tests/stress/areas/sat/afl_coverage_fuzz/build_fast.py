#!/usr/bin/env python3
"""Second build: libFuzzer coverage instrumentation WITHOUT ASan, for higher
throughput.  Everything is still compiled locally into this folder.

Python port of build_fast.sh.
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
from concurrent.futures import ThreadPoolExecutor

SRC = os.path.join(ROOT, "src")
B = os.path.join(HERE, "build_fast")
os.makedirs(B, exist_ok=True)

CFLAGS = [
    "-O1", "-g", "-fno-omit-frame-pointer", "-std=gnu11", "-D_GNU_SOURCE", "-w",
    "-DCF_HAVE_X86",
    '-DUCAS_SNIPDIR=\\"%s\\"' % os.path.join(HERE, "snippets"),
    "-I%s" % HERE, "-I%s" % SRC, "-I%s" % ROOT,
    "-fsanitize=fuzzer-no-link",
]

# Shell glob `"$SRC"/*.c`, sorted as the shell would expand it.
SRCS = sorted(
    os.path.join(SRC, f) for f in os.listdir(SRC)
    if f.endswith(".c") and f != "main.c"
)


def _obj(src):
    return os.path.join(B, os.path.splitext(os.path.basename(src))[0] + ".o")


def _compile_one(src):
    """Mirror: clang CFLAGS -c "$f" -o "$o" 2>/dev/null || { echo COMPILE FAILED >&2; clang ... >&2; exit 1; }"""
    cmd = ["clang"] + CFLAGS + ["-c", src, "-o", _obj(src)]
    # First attempt: `2>/dev/null` (stderr suppressed, stdout inherited).
    p = subprocess.run(cmd, stdout=None, stderr=subprocess.DEVNULL)
    if p.returncode == 0:
        return True
    sys.stderr.write("COMPILE FAILED: %s\n" % src)
    sys.stderr.flush()
    # Second attempt: `>&2` (clang stdout and stderr both go to our stderr).
    p = subprocess.run(cmd, stdout=2, stderr=None)
    return p.returncode == 0


def main():
    # xargs -0 -n2 -P 8: compile in parallel, stop with exit 1 if any fails.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_compile_one, SRCS))
    if not all(results):
        return 1

    objs = [_obj(src) for src in SRCS]

    print("linking fuzz_ucas_fast ...")
    sys.stdout.flush()
    link = ["clang", "-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=fuzzer",
            os.path.join(HERE, "fuzz_ucas.c")]
    link += objs
    link += [os.path.join(ROOT, "libsnxglslc.a"), "-lm",
             "-o", os.path.join(HERE, "fuzz_ucas_fast")]
    r = subprocess.run(link)
    if r.returncode != 0:
        return r.returncode

    print("built %s" % os.path.join(HERE, "fuzz_ucas_fast"))
    subprocess.run(["ls", "-la", os.path.join(HERE, "fuzz_ucas_fast")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
