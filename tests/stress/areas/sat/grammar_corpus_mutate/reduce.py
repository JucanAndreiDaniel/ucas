#!/usr/bin/env python3
"""ddmin minimizer for a mutant reproducer (delta debugging over lines).

Given a mutant id (and which campaign corpus it came from) plus an expected
classification (HANG / CRASH / a substring of the output), repeatedly remove
chunks of statements and re-run under `timeout` until no smaller set still
triggers the finding.  All work stays in this folder.

    python3 reduce.py --id 93 --corpus 0x5EED --expect HANG --timeout 5
    python3 reduce.py --file path/to.ucas --expect 'unexpected'
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
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, "_scratch")
MUTDIR = os.path.join(SCRATCH, "mutants")
REDDIR = os.path.join(SCRATCH, "minimized")
BIN = str(_REPO_ROOT / "ucas")
os.makedirs(REDDIR, exist_ok=True)


def run(lines, timeout, name="red"):
    path = os.path.join(REDDIR, name + ".ucas")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    try:
        p = subprocess.run(["timeout", str(timeout), BIN, name + ".ucas"],
                           cwd=REDDIR, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout + 3)
        rc, out, timed = p.returncode, p.stdout.decode("utf-8", "replace"), False
    except subprocess.TimeoutExpired as e:
        rc, timed = None, True
        out = (e.stdout or b"").decode("utf-8", "replace") if e.stdout else ""
    kind = "HANG" if (timed or rc in (124, 137)) else ("CRASH" if rc != 0 else "OK")
    return {"rc": rc, "timed_out": timed, "kind": kind, "out": out}


def make_test(expect, timeout):
    def t(cand):
        if not cand:
            return False
        r = run(cand, timeout)
        if expect in ("HANG", "CRASH"):
            return r["kind"] == expect
        return expect in r["out"]
    return t


def ddmin(test, units, max_rounds=30):
    assert test(units), "initial input does not satisfy the predicate"
    n = 2
    while len(units) >= 2 and max_rounds > 0:
        max_rounds -= 1
        chunk = max(1, len(units) // n)
        subsets = [units[i:i + chunk] for i in range(0, len(units), chunk)]
        reduced = False
        for i in range(len(subsets)):
            comp = subsets[:i] + subsets[i + 1:]
            cand = [u for s in comp for u in s]
            if cand and test(cand):
                units, n, reduced = cand, max(2, n - 1), True
                break
            sub = subsets[i]
            if test(sub):
                units, n, reduced = sub, 2, True
                break
        if not reduced:
            if n >= len(units):
                break
            n = min(len(units), n * 2)
    return units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int)
    ap.add_argument("--corpus", default="", help="corpus suffix (e.g. 0x5EED)")
    ap.add_argument("--file")
    ap.add_argument("--expect", default="HANG")
    ap.add_argument("--timeout", type=int, default=5)
    args = ap.parse_args()

    if args.file:
        src = open(args.file).read()
        label = os.path.basename(args.file).replace(".ucas", "")
    else:
        cf = "corpus.jsonl" if not args.corpus else "corpus_%s.jsonl" % args.corpus
        cases = [json.loads(l) for l in open(os.path.join(SCRATCH, cf))]
        src = cases[args.id]["source"]
        label = "m%04d" % args.id
    units = src.splitlines()
    test = make_test(args.expect, args.timeout)
    mini = ddmin(test, units)
    out = os.path.join(REDDIR, label + "_min.ucas")
    with open(out, "w") as fh:
        fh.write("\n".join(mini) + "\n")
    final = run(mini, args.timeout, label + "_min")
    print("=== minimized (%d -> %d lines) ===" % (len(units), len(mini)))
    print("\n".join(mini))
    print("--- final kind:", final["kind"], "rc:", final["rc"])
    print("saved:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
