#!/usr/bin/env python3
"""Build SEPARATE ucas binaries from the Makefile's source list.

Replaces ``build.sh``.  Never writes to $ROOT/ucas, never runs make, never
edits source.  Only writes inside tests/stress/areas/systems/build_variants/.

Command lines written to the build logs use bash's ``printf %q`` quoting so
the log bytes match the original shell script exactly.
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

import string
import subprocess

BD = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "build_variants"
SRC = _REPO_ROOT / "src"
SRCLIST = BD / "srclist.txt"

# Mirrors Makefile CFLAGS.  The SNIPDIR define keeps the surrounding double
# quotes, exactly like bash's -DUCAS_SNIPDIR="\"$ROOT/snippets\"".
COMMON = [
    "-std=c99",
    "-D_GNU_SOURCE",
    "-w",
    "-DCF_HAVE_X86",
    '-DUCAS_SNIPDIR="%s/snippets"' % ROOT,
    "-I" + str(SRC),
    "-I" + ROOT,
]

_BASH_SAFE = set(string.ascii_letters + string.digits + "_@%+=:,./-")


def bash_quote(s):
    """Equivalent of bash ``printf %q`` for the (plain) arguments used here."""
    if s == "":
        return "''"
    return "".join(c if c in _BASH_SAFE else "\\" + c for c in s)


def cmdline(argv):
    """Render an argv the way ``printf '%q ' "$@" ; echo`` does."""
    return " ".join(bash_quote(a) for a in argv) + " "


def first_version_line(cc):
    """Equivalent of ``$($cc --version 2>&1 | head -1)``."""
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


def read_srclist():
    return [ln for ln in SRCLIST.read_text().splitlines()]


def build_variant(name, cc, flags):
    od = BD / ("obj_" + name)
    logd = BD / "build_logs"
    od.mkdir(parents=True, exist_ok=True)
    logd.mkdir(parents=True, exist_ok=True)
    log_path = logd / ("build_" + name + ".log")

    srclist = read_srclist()
    # cat "$SRCLIST" | tr '\n' ' '
    srclist_flat = "".join(ln + " " for ln in srclist) if srclist else ""

    with open(log_path, "w") as log:
        log.write("VARIANT=%s\n" % name)
        log.write("CC=%s\n" % first_version_line(cc))
        log.write("FLAGS=%s\n" % " ".join(flags))
        log.write("COMMON=%s\n" % " ".join(COMMON))
        log.write("SRCLIST=%s\n" % srclist_flat)
        log.write("---- commands and compiler output ----\n")

        # snxglslc sources -> static library
        snxobjs = []
        for f in ("lexer", "parser", "emit", "builtins", "glslc"):
            o = od / ("snx_" + f + ".o")
            snxobjs.append(str(o))
            argv = [cc] + COMMON + flags + ["-fPIE", "-c",
                    str(SRC / "snxglslc" / (f + ".c")), "-o", str(o)]
            log.write(cmdline(argv) + "\n")
            log.flush()
            p = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                               timeout=300)
            if p.returncode != 0:
                print("BUILD FAIL %s : snx_%s" % (name, f))
                return 1

        liba = od / "libsnxglslc.a"
        if liba.exists():
            liba.unlink()
        ar_argv = ["ar", "rcs", str(liba)] + snxobjs
        log.write("ar rcs %s %s\n" % (bash_quote(str(liba)), " ".join(snxobjs)))
        log.flush()
        p = subprocess.run(ar_argv, stdout=log, stderr=subprocess.STDOUT,
                           timeout=120)
        if p.returncode != 0:
            print("BUILD FAIL %s : ar" % name)
            return 1

        # All SRCS from the Makefile.
        objs = []
        for f in srclist:
            if not f:
                continue
            o = od / (f[:-2] + ".o") if f.endswith(".c") else od / (f + ".o")
            objs.append(str(o))
            argv = [cc] + COMMON + flags + ["-c", str(SRC / f), "-o", str(o)]
            log.write(cmdline(argv) + "\n")
            log.flush()
            p = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                               timeout=300)
            if p.returncode != 0:
                print("BUILD FAIL %s : %s" % (name, f))
                return 1

        binpath = BD / ("bin_ucas_" + name)
        argv = [cc] + flags + ["-o", str(binpath)] + objs + [str(liba), "-lm"]
        log.write(cmdline(argv) + "\n")
        log.flush()
        p = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                           timeout=300)
        if p.returncode != 0:
            print("BUILD FAIL %s : link" % name)
            return 1

    print("BUILD OK %s -> bin_ucas_%s" % (name, name))
    return 0


VARIANTS = [
    ("gcc_O0",              "gcc",   ["-O0"]),
    ("gcc_O2",              "gcc",   ["-O2"]),
    ("gcc_O3",              "gcc",   ["-O3"]),
    ("clang_O2",            "clang", ["-O2"]),
    ("gcc_O2_noalias",      "gcc",   ["-O2", "-fno-strict-aliasing"]),
    ("gcc_O2_fpmath",       "gcc",   ["-O2", "-mfpmath=sse", "-msse2"]),
    ("gcc_O3_fastmath",     "gcc",   ["-O3", "-ffast-math", "-mfpmath=sse"]),
    ("clang_O3_fastmath",   "clang", ["-O3", "-ffast-math"]),
]


def main():
    # The original uses `set -u` (not -e): a failed variant is reported but the
    # remaining variants are still attempted.  Return codes are not propagated.
    for name, cc, flags in VARIANTS:
        build_variant(name, cc, flags)
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
