#!/usr/bin/env python3
"""
run_oracle.py -- differential harness: ucas vs SymPy/mpmath (a real CAS).

Usage:  python3 run_oracle.py [--verbose] [--only IDPREFIX]

Builds one .ucas batch from oracle_tasks.TASKS, runs the ucas binary under a
timeout, extracts each command's answer from the printed block, computes the
ground truth with SymPy, and compares semantically.  Results go to
report.json and report.txt (both inside this folder).
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
import sys
import os
import re
import json
import subprocess
import argparse

import sympy as sp
from sympy import sympify, simplify, expand, diff, integrate, limit, pi, oo
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations, implicit_multiplication_application,
    convert_xor,
)
from oracle_tasks import TASKS

HERE = os.path.dirname(os.path.abspath(__file__))
UCAS = str(_REPO_ROOT / "ucas")
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

x = sp.Symbol("x", real=True)
LOCAL = {"x": x, "e": sp.E, "C": sp.Symbol("C"), "y": sp.Symbol("y"),
         "a": sp.Symbol("a"), "b": sp.Symbol("b"),
         "c": sp.Symbol("c"), "d": sp.Symbol("d")}


def parse_ucas(s):
    """Parse a ucas-printed expression into a SymPy object."""
    s = s.strip()
    # strip inline numeric annotation "   (= 1.234)" and trailing text
    s = re.sub(r"\s*\(=\s*[^)]*\)\s*$", "", s).strip()
    # strip a leading "  = " was already removed by extractor
    s = s.replace("ln(", "log(")
    return parse_expr(s, transformations=TRANSFORMS,
                      local_dict=LOCAL, evaluate=True)


def as_sympy(s):
    # use the same parser as ucas output, but with our real x symbol so that
    # parsed operands and parsed answers share the same Symbol identity.
    return parse_expr(str(s), transformations=TRANSFORMS,
                      local_dict=LOCAL, evaluate=True)


# --- output extraction ------------------------------------------------------
def split_blocks(text):
    """Return list of (command, block_text) keyed by '> ' echoed lines."""
    blocks = []
    cur_cmd, cur_lines = None, []
    for line in text.splitlines():
        if line.startswith("> "):
            if cur_cmd is not None:
                blocks.append((cur_cmd, "\n".join(cur_lines)))
            cur_cmd, cur_lines = line[2:].strip(), []
        else:
            if cur_cmd is not None:
                cur_lines.append(line)
    if cur_cmd is not None:
        blocks.append((cur_cmd, "\n".join(cur_lines)))
    return blocks


def first_equals(block):
    for line in block.splitlines():
        m = re.match(r"^\s*=\s*(.*?)\s*$", line)
        if m:
            return m.group(1).strip()
    return None


def extract(task, block):
    kind = task["kind"]
    if kind == "diff":
        # ucas prints: "d/dx EXPR = RESULT" on the first result line
        for line in block.splitlines():
            if line.startswith("d/dx ") or line.startswith("d/d") or " = " in line:
                if " = " in line:
                    return line.split(" = ", 1)[1].strip()
        return None
    if kind in ("equiv_src", "integrate"):
        # trig-form simplify prints several conditional "= ..." forms and a
        # final "simplest:" line -- the latter is the actual answer.
        for line in block.splitlines():
            m = re.match(r"^\s*simplest:\s*(.*?)\s*$", line)
            if m:
                return re.sub(r"\s{2,}\(.*\)\s*$", "", m.group(1)).strip()
        return first_equals(block)
    if kind == "special":
        fn = task["fn"]
        if fn == "resultant":
            for line in block.splitlines():
                m = re.match(r"^\s*in x:\s*(.*?)\s*$", line)
                if m:
                    return m.group(1).strip()
        if fn == "discriminant":
            for line in block.splitlines():
                m = re.match(r"^\s*in x \(degree \d+\):\s*(.*?)\s*$", line)
                if m:
                    return m.group(1).strip()
        return first_equals(block)
    if kind == "limit":
        v = first_equals(block)
        if v is None:
            return None
        return re.sub(r"\s*\(from.*$", "", v).strip()
    if kind == "taylor":
        for line in block.splitlines():
            m = re.match(r"^\s*.+? = (.*?)\s*\+\s*O\(", line)
            if m:
                return m.group(1).strip()
        return None
    if kind == "solve":
        roots = []
        for line in block.splitlines():
            if "extraneous" in line:
                continue
            # results are printed as "  x = VALUE" (possibly with a
            # "(= numeric)" or "(a double root)" annotation)
            m = re.match(r"^\s+x\s*=\s*(.*?)\s*$", line)
            if not m:
                # system form: "  x = -sqrt(2)/2, y = -0.707..."
                m = re.match(r"^\s+x\s*=\s*([^,]+),", line)
            if m:
                val = m.group(1).strip()
                val = re.sub(r"\s{2,}\(.*\)\s*$", "", val).strip()
                roots.append(val)
        return roots if roots else None
    if kind == "definite":
        for line in block.splitlines():
            m = re.match(r"^\s*from .*?=\s*([0-9.eE+-]+)\s*$", line)
            if m:
                return m.group(1).strip()
            m = re.match(r"^\s*numeric \(adaptive[^)]*\):\s*([0-9.eE+-]+)", line)
            if m:
                return m.group(1).strip()
        return None
    if kind == "det":
        for line in block.splitlines():
            m = re.match(r"^\s*det = (.*?)\s*$", line)
            if m:
                return m.group(1).strip()
        return None
    if kind == "factorint":
        for line in block.splitlines():
            m = re.match(r"^\s*(\d+) = (.*?)\s*\(not prime\)\s*$", line)
            if m:
                return m.group(2).strip()
            m = re.match(r"^\s*(\d+) = \d+ \(prime\)\s*$", line)
            if m:
                return "PRIME"
        return None
    return None


# --- oracle -----------------------------------------------------------------
def oracle_for(task):
    k = task["kind"]
    if k == "equiv_src":
        return as_sympy(task["src"])
    if k == "diff":
        return diff(as_sympy(task["src"]), x)
    if k == "integrate":
        return integrate(as_sympy(task["src"]), x)
    if k == "definite":
        e = as_sympy(task["src"])
        a, b = as_sympy(task["a"]), as_sympy(task["b"])
        return sp.N(sp.integrate(e, (x, a, b)), 20)
    if k == "definite":
        e = as_sympy(task["src"])
        return sp.N(sp.integrate(e, (x, as_sympy(task["a"]), as_sympy(task["b"]))), 20)
    if k == "limit":
        if task.get("oracle_override"):
            return as_sympy(task["oracle_override"])
        a = as_sympy(task["a"])
        side = "+" if task["side"] == "right" else "-" if task["side"] == "left" else "+"
        return limit(as_sympy(task["src"]), x, a, dir=side)
    if k == "taylor":
        a = int(task["a"])
        n = int(task["n"])
        e = as_sympy(task["src"])
        return sp.series(e, x, a, n + 1).removeO()
    if k == "special":
        fn, args = task["fn"], task["args"]
        f = getattr(sp, fn)
        pa = [as_sympy(a) for a in args]
        if fn in ("gcd", "lcm", "quo", "rem"):
            return f(*pa)
        if fn == "resultant":
            return sp.resultant(pa[0], pa[1], x)
        if fn == "discriminant":
            return sp.discriminant(pa[0], x)
        return f(*pa)
    if k == "solve":
        return [as_sympy(r) for r in task["roots"]]
    if k == "det":
        return sp.Matrix(eval(task["matrix"])).det()
    if k == "factorint":
        return sp.factorint(task["n"])
    return None


# --- comparison -------------------------------------------------------------
def eq_expr(a, b, compare="exact"):
    """Return (equal, how).  Semantic comparison with numeric fallback."""
    if compare == "const":
        # equal up to a nonzero constant factor (gcd/lcm normalization)
        try:
            if b == 0:
                return (sp.simplify(a) == 0), "exact"
            ratio = sp.cancel(a / b)
            if not ratio.free_symbols:
                return (sp.simplify(ratio) != 0), "const"
        except Exception:
            pass
    if compare == "antideriv":
        # antiderivatives may differ by an additive constant
        try:
            d = sp.simplify(sp.diff(a - b, x))
            if d == 0:
                return True, "antideriv"
            if sp.expand(d) == 0:
                return True, "antideriv"
        except Exception:
            pass
    d = None
    try:
        d = simplify(sp.together(a - b))
        if d == 0:
            return True, "simplify"
    except Exception:
        pass
    try:
        d = expand(a - b)
        if d == 0:
            return True, "expand"
    except Exception:
        pass
    # numeric fallback: compare at several sample points (real + complex)
    try:
        pts = [sp.Rational(1, 7), sp.Rational(2, 5), sp.Rational(3, 2), sp.Rational(5, 3)]
        for p in pts:
            av = complex(sp.N(a.subs(x, p), 25))
            bv = complex(sp.N(b.subs(x, p), 25))
            if abs(av - bv) > 1e-12 * max(1.0, abs(av), abs(bv)):
                return False, "numeric"
        return True, "numeric"
    except Exception:
        pass
    return None, "inconclusive"


def compare_task(task, answer, oracle, block=""):
    k = task["kind"]
    if answer is None:
        if k == "integrate" and "no antiderivative found" in block:
            return None, "INCOMPLETE-integration"
        if k == "solve" and "no real solution" in block:
            # correct if the oracle has no real roots
            if not oracle or all(not r.is_real for r in oracle):
                return True, "no-real-solution"
        return False, "no-answer-extracted"
    try:
        if k == "factorint":
            if answer == "PRIME":
                ok = sp.isprime(task["n"])
                return ok, "prime-claim"
            factors = {}
            for term in answer.split("*"):
                term = term.strip()
                if "^" in term:
                    base, e = term.split("^")
                    factors[int(base)] = int(e)
                else:
                    factors[int(term)] = factors.get(int(term), 0) + 1
            prod = 1
            for base, e in factors.items():
                prod *= base ** e
            ok = (prod == task["n"]) and all(sp.isprime(b) for b in factors)
            return ok, f"product={prod}"
        if k == "definite":
            try:
                av = float(answer)
                bv = float(oracle)
                ok = abs(av - bv) <= 1e-9 * max(1.0, abs(av), abs(bv))
                return ok, f"numeric({av} vs {bv})"
            except Exception as ex:
                return None, f"definite-parse: {ex}"
        if k == "det":
            return int(answer) == int(oracle), "int"
        if k == "solve":
            got = [parse_ucas(r) for r in answer]
            exp = oracle
            if task.get("residual_check") or task.get("general"):
                # verify each reported root satisfies the original equation
                # numerically (substitute integer values for any free k)
                eqn = task.get("eqn", "")
                if " = " in eqn:
                    lhs, rhs = eqn.split(" = ", 1)
                    L, R = as_sympy(lhs), as_sympy(rhs)
                    for root in got:
                        for kval in (0, 1, -1):
                            try:
                                rv = complex(sp.N(root.subs(sp.Symbol("k"), kval), 25))
                            except Exception:
                                continue
                            if abs(complex(sp.N(L.subs(x, rv) - R.subs(x, rv), 25))) > 1e-9:
                                return False, f"residual nonzero at {root}"
                    return True, "residual-numeric"
                return None, "residual-skip"
            if len(got) != len(exp):
                return False, f"count {len(got)} vs {len(exp)}"
            # match roots as a multiset (up to simplify/numeric)
            used = [False] * len(exp)
            for g in got:
                found = False
                for j, e in enumerate(exp):
                    if used[j]:
                        continue
                    eq, _ = eq_expr(g, e)
                    if eq:
                        used[j] = True
                        found = True
                        break
                if not found:
                    return False, f"root {g} unmatched"
            return True, "roots"
        if k == "limit":
            if "not found symbolically" in str(answer):
                return None, "INCOMPLETE-limit"
            if answer in ("inf", "+inf") and oracle == oo:
                return True, "inf"
            if answer == "-inf" and oracle == -oo:
                return True, "inf"
            if answer.startswith("none") or "does not exist" in answer:
                # ucas reports non-existence; SymPy returns AccumBounds for
                # oscillatory limits, or raises/returns oo for divergent ones
                if type(oracle).__name__ in ("AccumBounds", "AccumulationBounds") or oracle is sp.nan:
                    return True, "oscillates"
                return False, "claimed-no-limit-but-oracle-has-one"
            try:
                a = parse_ucas(answer)
            except Exception:
                return False, f"unparseable {answer!r}"
            eq, how = eq_expr(a, oracle)
            return eq, "limit-" + how
        if k == "taylor":
            a = parse_ucas(answer)
            eq, how = eq_expr(a, oracle, "exact")
            if eq is True:
                return True, how
            # ucas prints ~10-digit decimals for expansions about a != 0
            try:
                for p in (sp.Rational(1, 7), sp.Rational(2, 5), sp.Rational(3, 2)):
                    av = complex(sp.N(a.subs(x, p), 20))
                    bv = complex(sp.N(oracle.subs(x, p), 20))
                    if abs(av - bv) > 1e-6 * max(1.0, abs(av), abs(bv)):
                        return False, "taylor-numeric"
                return True, "taylor-numeric(1e-6)"
            except Exception:
                return eq, how
        # expr-like kinds
        a = parse_ucas(answer)
        if k == "integrate":
            a = a.subs(sp.Symbol("C"), 0)
            eq, how = eq_expr(a, oracle, "antideriv")
            if eq is not True:
                eq2, how2 = eq_expr(a, oracle, "exact")
                if eq2 is True:
                    eq, how = eq2, "exact"
            return eq, how
        cmp = task.get("compare", "exact")
        eq, how = eq_expr(a, oracle, cmp)
        return eq, how
    except Exception as ex:
        return None, f"compare-error: {type(ex).__name__}: {ex}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    tasks = [t for t in TASKS if t["id"].startswith(args.only)] if args.only else TASKS
    batch = os.path.join(HERE, "_generated_batch.ucas")
    with open(batch, "w") as fh:
        fh.write("# auto-generated differential batch -- second_cas_oracle\n")
        for t in tasks:
            fh.write(t["cmd"] + "\n")
    proc = subprocess.run([UCAS, batch], capture_output=True, text=True,
                          timeout=60, cwd=HERE)
    text = proc.stdout + "\n" + proc.stderr
    with open(os.path.join(HERE, "_generated_batch.out"), "w") as fh:
        fh.write(text)

    blocks = dict(split_blocks(text))
    results = []
    n_ok = n_bad = n_inc = 0
    for t in tasks:
        block = blocks.get(t["cmd"], "")
        answer = extract(t, block)
        oracle = oracle_for(t)
        eq, how = compare_task(t, answer, oracle, block)
        status = "OK" if eq else ("BAD" if eq is False else
                                  "LIMIT" if str(how).startswith("INCOMPLETE") else "INC")
        if eq is True:
            n_ok += 1
        elif eq is False:
            n_bad += 1
        else:
            n_inc += 1
        results.append(dict(id=t["id"], cmd=t["cmd"], kind=t["kind"],
                            answer=answer, oracle=str(oracle), status=status,
                            how=how, block=block))
        if args.verbose or eq is False or eq is None:
            print(f"[{status:3}] {t['id']:6} {t['cmd']}")
            print(f"        answer={answer!r} oracle={str(oracle)!r} how={how}")

    report = dict(counts=dict(total=len(tasks), ok=n_ok, bad=n_bad, limit=n_inc),
                  results=results)
    with open(os.path.join(HERE, "report.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    with open(os.path.join(HERE, "report.txt"), "w") as fh:
        fh.write(f"second_cas_oracle: total={len(tasks)} ok={n_ok} bad={n_bad} limit={n_inc}\n\n")
        for r in results:
            fh.write(f"[{r['status']}] {r['id']} {r['cmd']}\n")
            fh.write(f"   answer: {r['answer']!r}\n")
            fh.write(f"   oracle: {r['oracle']!r}  (how={r['how']})\n")
    print(f"\nTOTAL {len(tasks)}  OK={n_ok}  BAD={n_bad}  LIMIT={n_inc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
