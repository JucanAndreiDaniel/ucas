#!/usr/bin/env python3
"""Parallel build of one variant: build_parallel.py NAME

Replaces ``build_parallel.sh``.  Reads the variant's CC/FLAGS from config.py
(formerly config_NAME.sh), writes obj_NAME/, build_logs/build_NAME.log,
libsnxglslc.a and bin_ucas_NAME.  Compilation is farmed out to worker.py via
``xargs -P 12`` exactly as before.
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

# Ensure the sibling config.py is importable however this script is launched.
sys.path.insert(0, str(_ROOT_PATH(__file__).resolve().parent))
from config import VARIANTS

BD = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "build_variants"
SRC = _REPO_ROOT / "src"
SRCLIST = BD / "srclist.txt"
WORKER = BD / "worker.py"


def first_version_line(cc):
    try:
        p = subprocess.run([cc, "--version"], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=30)
        out = p.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as ex:
        out = ""
        if isinstance(ex, subprocess.TimeoutExpired):
            out = (ex.stdout or b"").decode("utf-8", "replace")
    lines = out.splitlines()
    return lines[0] if lines else ""


def main(argv):
    if len(argv) != 1:
        print("usage: build_parallel.py NAME", file=sys.stderr)
        return 2
    name = argv[0]
    cfg = VARIANTS[name]                        # . config_NAME.sh
    cc = cfg["CC"]
    flags = cfg["FLAGS"].split()                # unquoted $FLAGS

    od = BD / ("obj_" + name)
    (BD / "build_logs").mkdir(parents=True, exist_ok=True)
    od.mkdir(parents=True, exist_ok=True)
    log_path = BD / "build_logs" / ("build_" + name + ".log")

    srclist = SRCLIST.read_text().splitlines()
    srclist_flat = "".join(ln + " " for ln in srclist) if srclist else ""

    # New common line in the log has NO literal quotes around SNIPDIR - same
    # as the original `echo "COMMON=... -DUCAS_SNIPDIR=$ROOT/snippets ..."`.
    common_log = (
        "-std=c99 -D_GNU_SOURCE -w -DCF_HAVE_X86 "
        "-DUCAS_SNIPDIR=%s/snippets -I%s -I%s" % (ROOT, SRC, ROOT)
    )

    with open(log_path, "w") as log:
        log.write("VARIANT=%s\n" % name)
        log.write("CC=%s\n" % first_version_line(cc))
        log.write("FLAGS=%s\n" % cfg["FLAGS"])
        log.write("COMMON=%s\n" % common_log)
        log.write("SRCLIST=%s\n" % srclist_flat)
        log.write("---- compile jobs (parallel, xargs -P 12) ----\n")

    # pairs_NAME.txt
    pairs_path = BD / ("pairs_" + name + ".txt")
    pairs = []
    for f in ("lexer", "parser", "emit", "builtins", "glslc"):
        pairs.append("%s/snxglslc/%s.c %s/snx_%s.o" % (SRC, f, od, f))
    for f in srclist:
        if not f:
            continue
        base = f[:-2] if f.endswith(".c") else f
        pairs.append("%s/%s %s/%s.o" % (SRC, f, od, base))
    pairs_path.write_text("\n".join(pairs) + "\n")
    print("compile jobs: %d" % len(pairs))

    # cat pairs | xargs -P 12 -n 2 worker.sh NAME >> log 2>&1
    with open(log_path, "a") as log:
        p = subprocess.run(["xargs", "-P", "12", "-n", "2",
                            sys.executable, str(WORKER), name],
                           input="\n".join(pairs) + "\n", text=True,
                           stdout=log, stderr=subprocess.STDOUT, timeout=1800)
    if p.returncode != 0:
        print("BUILD FAIL %s (compile)" % name)
        return 1

    # snxglslc archive
    snxobjs = [str(od / ("snx_" + f + ".o"))
               for f in ("lexer", "parser", "emit", "builtins", "glslc")]
    liba = od / "libsnxglslc.a"
    if liba.exists():
        liba.unlink()
    p = subprocess.run(["ar", "rcs", str(liba)] + snxobjs, timeout=120)
    if p.returncode != 0:
        return 1

    objs = []
    for f in srclist:
        if not f:
            continue
        base = f[:-2] if f.endswith(".c") else f
        objs.append(str(od / (base + ".o")))

    binpath = BD / ("bin_ucas_" + name)
    with open(log_path, "a") as log:
        log.write("link %s\n" % binpath)
        p = subprocess.run([cc] + flags + ["-o", str(binpath)] + objs +
                           [str(liba), "-lm"], stdout=log,
                           stderr=subprocess.STDOUT, timeout=600)
    if p.returncode != 0:
        print("BUILD FAIL %s (link)" % name)
        return 1

    print("BUILD OK %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
