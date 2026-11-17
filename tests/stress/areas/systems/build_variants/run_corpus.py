#!/usr/bin/env python3
"""Run every corpus batch through every build variant.

Replaces ``run_corpus.sh``.  Captures stdout+stderr and exit codes, diffs each
variant against the reference (gcc_O2) byte-for-byte.  All runs use
UCAS_NO_TIMES=1 / UCAS_SPIRV_CROSS=none and a 30s timeout, as in the original.
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

import os
import subprocess

BD = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "build_variants"

BINS = [
    "bin_ucas_gcc_O0",
    "bin_ucas_gcc_O2",
    "bin_ucas_gcc_O3",
    "bin_ucas_clang_O2",
    "bin_ucas_gcc_O2_noalias",
    "bin_ucas_gcc_O2_fpmath",
    "bin_ucas_gcc_O3_fastmath",
    "bin_ucas_clang_O3_fastmath",
]
REF = "bin_ucas_gcc_O2"

RUN_ENV = dict(os.environ)
RUN_ENV["UCAS_NO_TIMES"] = "1"
RUN_ENV["UCAS_SPIRV_CROSS"] = "none"


def variant_name(b):
    return b[len("bin_ucas_"):] if b.startswith("bin_ucas_") else b


def run_binary(binary, corpus_file, out_path):
    """UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none timeout 30 ./bin corpus > out 2>&1

    Returns the exit code (124 on timeout) and leaves partial output in out.
    """
    with open(out_path, "wb") as out:
        try:
            p = subprocess.run(["./" + binary, corpus_file], cwd=str(BD),
                               env=RUN_ENV, stdout=out,
                               stderr=subprocess.STDOUT, timeout=30)
            return p.returncode
        except subprocess.TimeoutExpired:
            return 124


def count_lines(path):
    with open(path, "rb") as fh:
        return fh.read().count(b"\n")


def count_changed_lines(path):
    """grep -c '^[+-][^+-]' <path>"""
    n = 0
    with open(path, "rb") as fh:
        for line in fh:
            if len(line) >= 2 and line[0] in (ord("+"), ord("-")) \
                    and line[1] not in (ord("+"), ord("-")):
                n += 1
    return n


def main():
    results = BD / "results"
    diffs = BD / "diffs"
    results.mkdir(parents=True, exist_ok=True)
    diffs.mkdir(parents=True, exist_ok=True)

    print("variant-binaries: %d" % len(BINS))
    codes = results / "exit_codes.tsv"
    with open(codes, "w") as fh:
        fh.write("")

    for corpus in sorted(BD.glob("corpus_*.ucas")):
        f = corpus.name
        base = f[:-6] if f.endswith(".ucas") else f
        print("=== %s ===" % base)
        for b in BINS:
            v = variant_name(b)
            out_path = results / ("%s.%s.out" % (base, v))
            ec = run_binary(b, f, out_path)
            with open(codes, "a") as fh:
                fh.write("%s\t%s\t%s\n" % (base, v, ec))
            print("  %-18s exit=%-4s lines=%s" %
                  (v, str(ec), str(count_lines(out_path))))

        refo = results / ("%s.%s.out" % (base, variant_name(REF)))
        for b in BINS:
            if b == REF:
                continue
            v = variant_name(b)
            o = results / ("%s.%s.out" % (base, v))
            d = diffs / ("%s.vs_%s__%s.diff" %
                         (base, variant_name(REF), v))
            with open(d, "wb") as d_fh:
                subprocess.run(["diff", "-u", str(refo), str(o)],
                               stdout=d_fh, stderr=subprocess.STDOUT,
                               timeout=60)
            if d.stat().st_size > 0:
                print("    DIFF: %s (%d changed lines)" %
                      (v, count_changed_lines(d)))

    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
