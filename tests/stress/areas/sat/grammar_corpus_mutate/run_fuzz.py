#!/usr/bin/env python3
"""Execute every generated mutant under ``timeout 10`` and classify results.

Findings are de-duplicated by (exit-code class, first significant output line).
Each anomaly records a member list of mutant ids that share the fingerprint;
``reduce.py`` can then ddmin any one of them.  Everything stays in this folder.

    python3 run_fuzz.py
    python3 run_fuzz.py --timeout 10 --limit 240
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
BIN = str(_REPO_ROOT / "ucas")

# Markers that indicate a real crash / internal failure even when the process
# happens to exit 0 (e.g. a caught signal printed as text).
MARKERS = [
    "Assertion", "assertion", "Segmentation", "segmentation", "SIGSEGV",
    "SIGABRT", "SIGBUS", "SIGFPE", "AddressSanitizer", "runtime error",
    "internal error", "Internal error", "panic", "Panic", "FATAL",
    "fatal error", "abort", "Abort", "core dumped", "stack overflow",
    "Stack overflow", "terminate called", "malloc()", "free():",
    "double free", "heap-use-after-free", "out of memory", "bad_alloc",
    "bus error", "Bus error",
]
# Semantic claims worth a second look (unsound-equivalence hunt).
EQUAL_MARKERS = ["are equal on the domain", "equal:true", '"equal":true']


def nonempty_lines(out):
    return [l.strip() for l in out.splitlines() if l.strip()]


def first_line(out):
    ls = nonempty_lines(out)
    return ls[0] if ls else "<empty>"


def significant_line(out):
    """First non-echo, non-comment output line."""
    for l in nonempty_lines(out):
        if l.startswith(">") or l.startswith("#"):
            continue
        return l
    return first_line(out)


def crash_line(out):
    """The most informative line: a crash marker if any, else the last line."""
    for l in nonempty_lines(out):
        if any(m in l for m in MARKERS):
            return l
    ls = nonempty_lines(out)
    return ls[-1] if ls else "<empty>"


def classify(res):
    # `timeout 10` exits 124 when it kills a child that overran the limit;
    # 137 is SIGKILL.  Both mean the program did not finish in time -> HANG.
    if res["timed_out"] or res["rc"] in (124, 137):
        return "HANG"
    if res["rc"] != 0:
        return "CRASH"
    if any(m in res["out"] for m in MARKERS):
        return "ODD"
    return "OK"


def run_one(name, timeout):
    path = os.path.join(MUTDIR, name)
    try:
        p = subprocess.run(
            ["timeout", str(timeout), BIN, name],
            cwd=MUTDIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout + 3,
        )
        rc, out, timed = p.returncode, p.stdout.decode("utf-8", "replace"), False
    except subprocess.TimeoutExpired as e:
        rc, timed = None, True
        out = (e.stdout or b"").decode("utf-8", "replace") if e.stdout else ""
    res = {"rc": rc, "timed_out": timed, "out": out}
    res["kind"] = classify(res)
    res["first_line"] = first_line(out)
    res["sig_line"] = significant_line(out)
    res["crash_line"] = crash_line(out)
    res["equal_claim"] = any(m in out for m in EQUAL_MARKERS)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    corpus = [json.loads(l) for l in open(os.path.join(SCRATCH, "corpus.jsonl"))]
    if args.limit:
        corpus = corpus[:args.limit]

    results = []
    groups = {}
    kinds = {}
    equal_claims = 0
    for c in corpus:
        res = run_one(os.path.basename(c["file"]), args.timeout)
        rec = {"id": c["id"], "seed": c["seed"], "ops": c["ops"], **res}
        results.append(rec)
        kinds[res["kind"]] = kinds.get(res["kind"], 0) + 1
        if res["equal_claim"]:
            equal_claims += 1
        if res["kind"] != "OK":
            # (exit-code class, first significant output line) de-dup key
            key = (res["kind"], res["crash_line"])
            if key not in groups:
                groups[key] = {
                    "kind": res["kind"],
                    "rc": res["rc"],
                    "fingerprint": res["crash_line"],
                    "first_line": res["first_line"],
                    "members": [],
                    "example_id": c["id"],
                    "example_seed": c["seed"],
                    "example_ops": c["ops"],
                    "example_out": res["out"],
                }
            groups[key]["members"].append(c["id"])
        sys.stdout.write(".")
        sys.stdout.flush()
    print()

    with open(os.path.join(SCRATCH, "results.jsonl"), "w") as fh:
        for r in results:
            shallow = dict(r)
            shallow["out"] = r["out"]  # keep full output for offline triage
            fh.write(json.dumps(shallow) + "\n")
    anomalies = sorted(groups.values(), key=lambda g: (-len(g["members"]), g["kind"], g["fingerprint"]))
    with open(os.path.join(SCRATCH, "anomalies.jsonl"), "w") as fh:
        for g in anomalies:
            fh.write(json.dumps(g) + "\n")

    print("mutants run:", len(results))
    print("by kind:", dict(sorted(kinds.items())))
    print("equal-claim outputs:", equal_claims)
    print("distinct finding fingerprints:", len(anomalies))
    for g in anomalies[:40]:
        print("  [%s] n=%d example=m%04d rc=%s :: %s" % (
            g["kind"], len(g["members"]), g["example_id"], g["rc"],
            g["fingerprint"][:110]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
