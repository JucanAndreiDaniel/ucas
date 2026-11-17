#!/usr/bin/env python3
"""Durable UCAS_SEED matrix (source: stoch.c:117-125).

Replaces ``run_seed_matrix.sh``.  strtoull(base 10) semantics: leading
whitespace skipped, optional sign, longest decimal prefix, ULLONG_MAX
saturation, '-' negation, empty -> 1.  Every run is bounded by timeout 15;
output is compared to the seed the binary echoes.
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

BIN = str(_REPO_ROOT / "ucas")
SCRIPT = "f(x:i64)=x+1\ng(x:i64)=1+x\npit f g trials 4"

fail = 0
n = 0


def run(script, seed=None, unset_seed=False):
    e = dict(os.environ)
    if unset_seed:
        e.pop("UCAS_SEED", None)
    elif seed is not None:
        e["UCAS_SEED"] = seed
    try:
        p = subprocess.run([BIN, "-e", script], env=e, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=15)
        out = p.stdout
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout or b""
    return out.decode("utf-8", "replace")


def head1(text):
    lines = text.splitlines()
    return lines[0] if lines else ""


def check(want, seed):
    global fail, n
    got = head1(run(SCRIPT, seed=seed))
    n += 1
    if "seed %s" % want not in got:
        print("FAIL UCAS_SEED=[%s] want seed %s got: %s" % (seed, want, got))
        fail += 1


CASES = [
    (0, "abc"), (0, "xyz"), (0, "nan"), (0, "inf"),
    (0, "+"), (0, "-"),
    (1, "1.5"), (1, "1e3"), (1, "1_000"),
    (12, "12junk"), (5, "5x"), (7, "+7abc"),
    (5, " 5x"), (5, "5 "), (0, "   "), (0, " "), (1, ""),
    (0, "-0"),
    (18446744073709551615, "-1"),
    (18446744073709551615, "-00000000000000000001"),
    (9223372036854775807, "-9223372036854775809"),
    (18446744073709551615, "18446744073709551616"),
    (18446744073709551615, "9999999999999999999999999"),
    (18446744073709551615, "18446744073709551615"),
    (18446744073709551614, "18446744073709551614"),
    (9223372036854775808, "9223372036854775808"),
    (0, "0"), (1, "1"), (2, "2"), (42, "42"), (1000000, "1000000"),
]


def main():
    global fail, n
    for want, seed in CASES:
        check(want, seed)

    # explicit `seed 0` override under UCAS_SEED=7
    got_lines = [ln for ln in run(SCRIPT + "\npit f g trials 4 seed 0",
                                  seed="7").splitlines()
                 if "Schwartz-Zippel), seed" in ln]
    got = got_lines[-1] if got_lines else ""
    n += 1
    if "seed 0" not in got:
        print("FAIL override got: %s" % got)
        fail += 1

    # default (UCAS_SEED unset)
    got = head1(run(SCRIPT, unset_seed=True))
    n += 1
    if "seed 1" not in got:
        print("FAIL default got: %s" % got)
        fail += 1

    print("seed matrix: %d runs, %d failures" % (n, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
