#!/usr/bin/env python3
"""ddmin-style minimizer for ucas reproducers.

Two modes:

* ``lines``  — classic delta debugging over the statements of a .ucas file
  (or the requests of a .jsonl file): repeatedly remove chunks and re-run the
  reproducer under ``timeout`` until no smaller set still triggers the bug.

* ``expr``   — structural shrinking of the generated f/g AST of a corpus case:
  replace sub-expressions by smaller ones of the same result type, re-render,
  re-run `equiv`, and keep the change only while the unsoundness remains
  (ucas claims equal, the independent Python oracle finds a differing point).

Everything stays in this folder; every run is bounded by ``timeout``.

Usage:
    python3 reduce.py expr --id 96
    python3 reduce.py lines --file _scratch/rc96.ucas --expect 'are equal on the domain'
"""
import argparse
import copy
import json
import os
import sys

from harness import (HERE, ev, UNDEF, corner_points, tminmax, is_int,
                     run_cli, run_mcp, mcp_call)
from gen import render, func_src, C, B


# ---------------------------------------------------------------------------
# line-level ddmin
# ---------------------------------------------------------------------------

def ddmin(test, units, max_rounds=25):
    """Zeller's ddmin: minimize `units` while test(units) stays true."""
    assert test(units), "initial input does not trigger the bug"
    n = 2
    while len(units) >= 2 and max_rounds > 0:
        max_rounds -= 1
        chunk = max(1, len(units) // n)
        subsets = [units[i:i + chunk] for i in range(0, len(units), chunk)]
        reduced = False
        for i in range(len(subsets)):
            complement = subsets[:i] + subsets[i + 1:]
            cand = [u for s in complement for u in s]
            if cand and test(cand):
                units, n, reduced = cand, max(2, n - 1), True
                break
            subset = subsets[i]
            if test(subset):
                units, n, reduced = subset, 2, True
                break
        if not reduced:
            if n >= len(units):
                break
            n = min(len(units), n * 2)
    return units


def line_test(units, expect, timeout, require_defs=True):
    def t(cand):
        if require_defs:
            eq = [ln for ln in cand if ln.strip().startswith("equiv ")]
            if eq:
                names = eq[0].split()[1:3]
                for nm in names:
                    if not any(ln.lstrip().startswith(nm + "(") for ln in cand):
                        return False
        res = run_cli(cand, timeout, name="red_lines")
        return (not res["timed_out"]) and expect in res["out"] and "error:" not in res["out"]
    return t


# ---------------------------------------------------------------------------
# expression-level shrinking
# ---------------------------------------------------------------------------

def subnodes(node, path=()):
    """Yield (path, node) for every node in the tree."""
    yield path, node
    for key in ("a", "b", "c", "idx"):
        ch = node.get(key) if isinstance(node, dict) else None
        if isinstance(ch, dict):
            yield from subnodes(ch, path + (key,))


def get_node(root, path):
    for k in path:
        root = root[k]
    return root


def set_node(root, path, new):
    if not path:
        return new
    cur = root
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = new
    return root


def alternatives(node):
    """Smaller well-typed replacements for a node (same result type)."""
    t = node["t"]
    k = node["k"]
    out = []
    if k == "bin":
        out = [node["a"], node["b"], C(0, t), C(1, t)]
        if node["op"] in ("<", "<=", "==", "!=", ">", ">="):
            # keep a bool-typed result (ucas compares on the first type)
            out += [B("==", C(0, t), C(0, t), t), B("!=", C(0, t), C(0, t), t)]
    elif k == "un":
        out = [node["a"], C(0, t), C(1, t)]
    elif k == "tern":
        out = [node["a"], node["b"], C(0, t)]
    elif k == "cast":
        out = [C(0, t), C(1, t)]
    elif k == "table":
        out = [C(node["vals"][0] if node["vals"] else 0, t), C(0, t)]
    elif k == "match":
        out = [C(node["default"], t), C(0, t)]
    elif k == "bitcast":
        out = [C(0, t)]
    # de-dup by rendering
    seen, uniq = set(), []
    seen.add(render(node))  # never accept an identical replacement
    for x in out:
        s = render(x)
        if s not in seen:
            seen.add(s)
            uniq.append(x)
    return uniq


def py_diff(f, g, params, t):
    """Return a valuation where f,g differ according to the Python oracle."""
    pts = corner_points(t, __import__("random").Random(1234))
    if len(params) >= 2:
        envs = [{"x": a, "y": b} for a in pts[:10] for b in pts[:10]]
    else:
        envs = [{"x": a} for a in pts]
    for env in envs:
        a, b = ev(f, env), ev(g, env)
        if a is UNDEF:
            continue
        if b is UNDEF:
            return env
        if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
            continue  # ucas compares NaN==NaN as equal
        if a != b:
            return env
    return None


def unsound_equal(f, g, params, t, timeout=15):
    ps = ", ".join(f"{v}: {tt}" for v, tt in params)
    src = (func_src("rf", params, f) + "\n" + func_src("rg", params, g) +
           "\n" + "equiv rf rg\n")
    res = run_cli(src, timeout, name="red_expr")
    if res["timed_out"] or "are equal on the domain" not in res["out"]:
        return None
    cex = py_diff(f, g, params, t)
    if cex is None:
        return None
    return {"source": src, "out": res["out"], "py_cex": cex}


def shrink_expr(case, timeout=15, max_passes=80):
    f, g = copy.deepcopy(case["f_ast"]), copy.deepcopy(case["g_ast"])
    params, t = case["params"], case["t"]
    proof = unsound_equal(f, g, params, t, timeout)
    if proof is None:
        return None
    history = [{"step": 0, "f": render(f), "g": render(g),
                "py_cex": proof["py_cex"]}]
    for step in range(1, max_passes + 1):
        changed = False
        # Prefer shrinking the larger tree; try all paths, smallest-first.
        for which in ("g", "f"):
            root = g if which == "g" else f
            # largest subexpressions first (biggest structural wins)
            cands = sorted(list(subnodes(root)), key=lambda p: _size(p[1]), reverse=True)
            for path, old in cands:
                for alt in alternatives(old):
                    trial = set_node(copy.deepcopy(root), path, alt)
                    nf, ng = (trial, g) if which == "f" else (f, trial)
                    got = unsound_equal(nf, ng, params, t, timeout)
                    if got is not None:
                        if which == "f":
                            f = nf
                        else:
                            g = ng
                        history.append({"step": step, "f": render(f), "g": render(g),
                                        "py_cex": got["py_cex"], "changed": which + ":" + "/".join(path)})
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
        if not changed:
            break
    final = unsound_equal(f, g, params, t, timeout)
    return {"f": f, "g": g, "f_src": render(f), "g_src": render(g),
            "params": params, "t": t, "history": history,
            "py_cex": final["py_cex"] if final else None,
            "steps": len(history) - 1}


def _size(n):
    return sum(1 for _ in subnodes(n))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("expr", "lines"))
    ap.add_argument("--id", type=int, help="corpus case id (expr mode)")
    ap.add_argument("--file", help="file to minimize (lines mode)")
    ap.add_argument("--expect", default="are equal on the domain")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args()

    if args.mode == "expr":
        cases = [json.loads(l) for l in open(os.path.join(HERE, "corpus.jsonl"))]
        case = cases[args.id]
        res = shrink_expr(case, args.timeout)
        if res is None:
            print("case does not trigger the unsound-equivalence predicate")
            return 1
        ps = ", ".join(f"{v}: {tt}" for v, tt in res["params"])
        src = (f"f({ps}) = {res['f_src']}\n"
               f"g({ps}) = {res['g_src']}\n"
               f"equiv f g\n")
        out = os.path.join(HERE, "_scratch", f"min_{args.id:04d}.ucas")
        with open(out, "w") as fh:
            fh.write(src)
        with open(os.path.join(HERE, f"reduce_expr_{args.id:04d}.json"), "w") as fh:
            json.dump(res, fh, indent=2, default=str)
        print("=== minimized reproducer ===")
        print(src)
        print("python counterexample:", res["py_cex"])
        print("steps:", res["steps"], "saved:", out)
        return 0

    # lines mode
    units = open(args.file).read().splitlines()
    test = line_test(units, args.expect, args.timeout)
    mini = ddmin(test, units)
    out = os.path.join(HERE, "_scratch", "min_lines.ucas")
    with open(out, "w") as fh:
        fh.write("\n".join(mini) + "\n")
    print("=== minimized statements ===")
    print("\n".join(mini))
    print("saved:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
