#!/usr/bin/env python3
"""Same-result-type differential hunt for unsound `equiv`.

Grammar-mutates a small typed expression into a nearby pair f,g, asks ucas
`equiv f g`, then evaluates both at boundary literals with `show`.  Because f
and g always share a result type, the known result-type-coercion unsoundness
cannot explain an "are equal" verdict that disagrees with `show`; such a case
would be a NEW deep semantic bug.  Deterministic for a fixed seed.

    python3 semantic_hunt.py --count 160 --seed 0x5EED
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
import random
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, "_scratch")
HUNTDIR = os.path.join(SCRATCH, "hunt")
BIN = str(_REPO_ROOT / "ucas")
os.makedirs(HUNTDIR, exist_ok=True)

INT_TYPES = ["u8", "u16", "u32", "i8", "i16", "i32"]
BOUNDS = {
    "u8": [0, 1, 2, 127, 128, 255], "u16": [0, 1, 255, 256, 32767, 65535],
    "u32": [0, 1, 255, 65535, 2147483647, 4294967295],
    "i8": [-128, -1, 0, 1, 127], "i16": [-32768, -1, 0, 1, 32767],
    "i32": [-2147483648, -1, 0, 1, 2147483647],
}
# boundary literals from the dictionary
LITS = ["0", "1", "2", "3", "7", "0x7f", "0x80", "0xff", "255", "256",
        "0x7fffffff", "0x80000000", "2^63", "2^64"]
IOPS = ["+", "-", "*", "&", "|", "xor", "<<", ">>", "%"]
VALUE_RE = re.compile(r"_\(\) = (-?\d+)")


def expr(rng, depth, t, vars_):
    if depth <= 0 or rng.random() < 0.35:
        return rng.choice(vars_ + [rng.choice(LITS)])
    op = rng.choice(IOPS)
    a = expr(rng, depth - 1, t, vars_)
    b = expr(rng, depth - 1, t, vars_)
    return "(%s %s %s)" % (a, op, b)


def subnodes(s):
    """Crude parenthesised subexpression spans (balanced)."""
    spans = []
    stack = []
    for i, ch in enumerate(s):
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            st = stack.pop()
            spans.append((st, i + 1))
    return spans


def mutate_expr(s, rng):
    spans = subnodes(s)
    if not spans:
        return s + " + " + rng.choice(LITS)
    a, b = rng.choice(spans)
    inner = s[a + 1:b - 1]
    replacement = rng.choice([inner.split()[0] if inner.split() else "x",
                              rng.choice(LITS), rng.choice(["x", "x + 1", "x xor 3"])])
    return s[:a + 1] + replacement + s[b - 1:]


def run_one(src, name, timeout=8):
    path = os.path.join(HUNTDIR, name + ".ucas")
    with open(path, "w") as fh:
        fh.write(src)
    try:
        p = subprocess.run(["timeout", str(timeout), BIN, name + ".ucas"],
                           cwd=HUNTDIR, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout + 3)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or b"").decode("utf-8", "replace")


def analyze(out, n_show):
    equal = "are equal on the domain" in out
    vals = [int(x) for x in VALUE_RE.findall(out)]
    shows = [v for v in vals]
    return equal, shows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=160)
    ap.add_argument("--seed", type=lambda x: int(x, 0), default=0x5EED)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    findings = []
    stats = {"pairs": 0, "equal": 0, "differ": 0, "errors": 0, "timeouts": 0}
    for i in range(args.count):
        t = rng.choice(INT_TYPES)
        f = expr(rng, 2, t, ["x"])
        g = mutate_expr(f, rng) if rng.random() < 0.8 else expr(rng, 2, t, ["x"])
        pts = BOUNDS[t]
        src = "f(x: %s) = %s\ng(x: %s) = %s\nequiv f g\n" % (t, f, t, g)
        for p in pts:
            src += "show f(%d)\nshow g(%d)\n" % (p, p)
        rc, out = run_one(src, "h%04d" % i)
        stats["pairs"] += 1
        if rc in (None, 124, 137):
            stats["timeouts"] += 1
            continue
        if "error:" in out:
            stats["errors"] += 1
        eq, shows = analyze(out, len(pts))
        if eq:
            stats["equal"] += 1
        else:
            stats["differ"] += 1
        # compare pairwise show values f(pi) vs g(pi)
        if eq and len(shows) >= 2 * len(pts):
            mismatches = []
            for j, p in enumerate(pts):
                a, b = shows[2 * j], shows[2 * j + 1]
                mask = (1 << 32) - 1
                if (a & mask) != (b & mask):
                    mismatches.append((p, a, b))
            if mismatches:
                findings.append({"id": i, "type": t, "f": f, "g": g,
                                 "mismatches": mismatches, "source": src, "out": out})
    with open(os.path.join(SCRATCH, "semantic_findings.jsonl"), "w") as fh:
        for f in findings:
            fh.write(json.dumps(f) + "\n")
    print("stats:", stats)
    print("NEW unsound-equal candidates:", len(findings))
    for f in findings[:12]:
        print("  h%04d %s f=%s g=%s first-mismatch=%s" % (
            f["id"], f["type"], f["f"][:60], f["g"][:60], f["mismatches"][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
