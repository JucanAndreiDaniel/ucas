#!/usr/bin/env python3
"""
run_diff.py -- differential stress: ucas vs independent oracles.

Drives the ucas CLI with batches of statements and checks each answer against
an oracle computed purely in Python (fractions.Fraction, float, math, brute
force, hand-coded polynomial arithmetic).  No ucas mode is used as an oracle.

Usage:
    python3 run_diff.py            # run all campaigns, write diff_results.json
    python3 run_diff.py EXPAND     # run one campaign (name substring)
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
import re
import sys
import json
import math
import random
import subprocess
import tempfile
from collections import Counter

import oraclelib as O
from fractions import Fraction

UCAS = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, "_scratch")
os.makedirs(SCRATCH, exist_ok=True)

RNG = random.Random(0xC0FFEE)

RESULTS = []
COUNTS = Counter()

# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

def run_batch(tag, statements, timeout=30):
    """Write a .ucas batch, run it, return (blocks, full, exit_code)."""
    path = os.path.join(SCRATCH, tag + ".ucas")
    with open(path, "w") as fh:
        fh.write("\n".join(statements) + "\n")
    try:
        p = subprocess.run([UCAS, path], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        out = p.stdout.decode("utf-8", "replace")
        code = p.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        return [], out, "TIMEOUT"
    # split into blocks on lines beginning with '> '
    parts = re.split(r"(?m)^> ?", out)
    blocks = [p for p in parts if p.strip() != ""]
    if len(blocks) != len(statements):
        # fall back: one big block list unpadded
        blocks = blocks + ["<MISSING>"] * max(0, len(statements) - len(blocks))
    return blocks, out, code


def record(campaign, case_id, statement, ucas_out, verdict, expected=None,
           oracle=None, note=""):
    r = dict(campaign=campaign, id=case_id, statement=statement,
             ucas_out=ucas_out, verdict=verdict,
             expected=str(expected) if expected is not None else None,
             oracle=str(oracle) if oracle is not None else None,
             note=note)
    RESULTS.append(r)
    COUNTS[(campaign, verdict)] += 1
    if verdict in ("DISAGREE", "PARSE_FAIL", "ERROR", "TIMEOUT"):
        print(f"  [{verdict}] {campaign}:{case_id} :: {statement}")
        if note:
            print("        " + note)


def rhs(block):
    return O.extract_equals(block)


# ---------------------------------------------------------------------------
# helpers for generating random polynomials / expressions
# ---------------------------------------------------------------------------

def _factor_expr():
    """Return (expr_string, poly) for a random product of small factors in x."""
    k = RNG.randint(1, 4)
    exprs = []
    poly = {0: Fraction(1)}
    for _ in range(k):
        typ = RNG.choice(["lin", "lin", "quad", "scaled"])
        if typ == "lin":
            a = RNG.randint(-5, 5)
            if a == 0:
                a = 1
            es = f"(x + {a})" if a >= 0 else f"(x - {-a})"
            fp = {1: Fraction(1), 0: Fraction(a)}
        elif typ == "quad":
            a = RNG.randint(-4, 4)
            b = RNG.randint(-6, 6)
            es = f"(x^2 + {a}x + {b})".replace("+ -", "- ")
            if a < 0:
                es = f"(x^2 - {-a}x + {b})".replace("+ -", "- ")
            fp = {2: Fraction(1), 1: Fraction(a), 0: Fraction(b)}
        else:  # scaled linear
            a = RNG.randint(2, 5)
            b = RNG.randint(-5, 5)
            es = f"({a}x + {b})".replace("+ -", "- ")
            fp = {1: Fraction(a), 0: Fraction(b)}
        exprs.append(es)
        poly = O.pmul(poly, fp)
    return "*".join(exprs), poly


def _sample_points(lo=-4, hi=4, n=7):
    pts = []
    for _ in range(n):
        pts.append(Fraction(RNG.randint(lo, hi), RNG.choice([1, 1, 1, 2, 3])))
    return pts


# ---------------------------------------------------------------------------
# Campaign: expand
# ---------------------------------------------------------------------------

def campaign_expand(n=45):
    cases = []
    for i in range(n):
        es, poly = _factor_expr()
        cases.append((i, f"expand {es}", es, poly))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("expand", stmts)
    for (i, stmt, es, poly), b in zip(cases, blocks):
        if code != 0 and "MISSING" in b:
            record("expand", i, stmt, b, "ERROR", note=f"exit={code}")
            continue
        r = rhs(b)
        if r is None:
            record("expand", i, stmt, b, "PARSE_FAIL", note="no '=' line")
            continue
        try:
            got = O.ast_to_poly(O.parse(r))
        except Exception as ex:
            record("expand", i, stmt, b, "PARSE_FAIL", note=f"output={r!r} ({ex})")
            continue
        if got == poly:
            record("expand", i, stmt, b, "PASS", expected=O.poly_to_str(poly))
        else:
            record("expand", i, stmt, b, "DISAGREE", expected=O.poly_to_str(poly),
                   oracle=O.poly_to_str(got),
                   note=f"ucas={r!r}; expected coeffs={poly}; got coeffs={got}")


# ---------------------------------------------------------------------------
# Campaign: factor
# ---------------------------------------------------------------------------

def campaign_factor(n=35):
    cases = []
    for i in range(n):
        es, poly = _factor_expr()
        expanded = O.poly_to_str(poly)
        cases.append((i, f"factor {expanded}", expanded, poly))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("factor", stmts)
    for (i, stmt, expanded, poly), b in zip(cases, blocks):
        r = rhs(b)
        if r is None:
            record("factor", i, stmt, b, "PARSE_FAIL", note="no '=' line")
            continue
        try:
            got = O.ast_to_poly(O.parse(r))
        except Exception as ex:
            record("factor", i, stmt, b, "PARSE_FAIL", note=f"output={r!r} ({ex})")
            continue
        if got == poly:
            record("factor", i, stmt, b, "PASS", expected=expanded)
        else:
            record("factor", i, stmt, b, "DISAGREE", expected=expanded,
                   oracle=O.poly_to_str(got),
                   note=f"ucas={r!r}; factor product expanded to {got} != {poly}")


# ---------------------------------------------------------------------------
# Campaign: cancel / simplify / together (exact rational functions)
# ---------------------------------------------------------------------------

def _rand_poly(deg):
    p = {}
    for e in range(deg + 1):
        c = RNG.randint(-4, 4)
        if c:
            p[e] = Fraction(c)
    if not p:
        p[0] = Fraction(1)
    if 0 not in p:
        p[0] = Fraction(RNG.choice([-2, -1, 1, 2]))
    return p


def campaign_ratfunc(n=45):
    cases = []
    for i in range(n):
        A = _rand_poly(RNG.randint(1, 2))
        B = _rand_poly(RNG.randint(1, 2))
        C = _rand_poly(RNG.randint(1, 2))
        num = O.pmul(A, C)
        den = O.pmul(B, C)
        expr = f"({O.poly_to_str(num)})/({O.poly_to_str(den)})"
        # expected reduced via my own polynomial gcd
        exp_num, exp_den = O.rat_reduce(num, den)
        op = RNG.choice(["cancel", "simplify"])
        stmt = f"{op} {expr}"
        cases.append((i, stmt, "cancel", expr, exp_num, exp_den, num, den))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("ratfunc", stmts)
    for (i, stmt, op, expr, en, ed, num, den), b in zip(cases, blocks):
        r = rhs(b)
        if r is None:
            record("ratfunc", i, stmt, b, "PARSE_FAIL", note="no '=' line")
            continue
        try:
            gn, gd = O.rat_reduce(*O.ast_ratfun(O.parse(r)))
        except Exception as ex:
            record("ratfunc", i, stmt, b, "PARSE_FAIL", note=f"output={r!r} ({ex})")
            continue
        ok = (gn == en and gd == ed)
        # semantic fallback: compare at points away from poles
        if not ok:
            pts = _sample_points(-6, 6, 9)
            ok = True
            for x in pts:
                if O.peval(ed, x) == 0 or O.peval(gd, x) == 0:
                    continue
                a = O.peval(en, x) / O.peval(ed, x)
                c = O.peval(gn, x) / O.peval(gd, x)
                if a != c:
                    ok = False
                    break
        if ok:
            record("ratfunc", i, stmt, b, "PASS",
                   expected=f"{O.poly_to_str(en)}/{O.poly_to_str(ed)}")
        else:
            record("ratfunc", i, stmt, b, "DISAGREE",
                   expected=f"{O.poly_to_str(en)}/{O.poly_to_str(ed)}",
                   oracle=f"{O.poly_to_str(gn)}/{O.poly_to_str(gd)}",
                   note=f"ucas={r!r}")


def campaign_together(n=20):
    cases = []
    for i in range(n):
        a = RNG.randint(1, 6)
        b = RNG.randint(1, 6)
        while b == a:
            b = RNG.randint(1, 6)
        expr = f"1/(x + {a}) + 1/(x + {b})"
        # oracle: (2x+a+b)/((x+a)(x+b))
        exp = f"(2x + {a+b})/((x + {a})*(x + {b}))"
        cases.append((i, f"together {expr}", expr, exp))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("together", stmts)
    for (i, stmt, expr, exp), b in zip(cases, blocks):
        r = rhs(b)
        if r is None:
            record("together", i, stmt, b, "PARSE_FAIL", note="no '=' line")
            continue
        try:
            gn, gd = O.ast_ratfun(O.parse(r))
            en, ed = O.ast_ratfun(O.parse(exp))
        except Exception as ex:
            record("together", i, stmt, b, "PARSE_FAIL", note=f"output={r!r} ({ex})")
            continue
        pts = _sample_points(-5, 5, 9)
        ok = True
        for x in pts:
            if O.peval(gd, x) == 0 or O.peval(ed, x) == 0:
                continue
            if O.peval(gn, x) / O.peval(gd, x) != O.peval(en, x) / O.peval(ed, x):
                ok = False
                break
        record("together", i, stmt, b, "PASS" if ok else "DISAGREE",
               expected=exp, oracle=r,
               note="" if ok else f"ucas={r!r} differs from {exp}")


# ---------------------------------------------------------------------------
# Campaign: diff (symbolic derivative) vs independent symbolic derivative
# ---------------------------------------------------------------------------

def _rand_diff_expr():
    typ = RNG.choice(["poly", "poly", "trig", "exp", "sqrt"])
    if typ == "poly":
        _, poly = _factor_expr()
        return O.poly_to_str(poly)
    if typ == "trig":
        return f"sin({RNG.randint(1,3)}x) + cos({RNG.randint(1,3)}x)^2"
    if typ == "exp":
        return f"exp({RNG.randint(1,3)}x) + {RNG.randint(1,5)}x^2"
    return f"sqrt(x^2 + {RNG.randint(1,5)}) + {RNG.randint(1,3)}x"


def _evalf(node, x):
    return O.evals(node, {"x": float(x)})


def campaign_diff(n=45):
    cases = []
    for i in range(n):
        es = _rand_diff_expr()
        cases.append((i, f"diff {es}", es))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("diff", stmts)
    for (i, stmt, es), b in zip(cases, blocks):
        m = re.search(r"(?m)^d/dx .*? = (.*?)\s*$", b)
        if not m:
            m = re.search(r"(?m)^∂/∂x .*? = (.*?)\s*$", b)
        if not m:
            record("diff", i, stmt, b, "PARSE_FAIL", note="no derivative line")
            continue
        r = m.group(1)
        try:
            got = O.parse(r)
            src = O.parse(es)
            mine = O.ast_diff(src)
        except Exception as ex:
            record("diff", i, stmt, b, "PARSE_FAIL", note=f"parse/diff error {ex}; out={r!r}")
            continue
        pts = _sample_points(-3, 3, 7)
        ok = True
        worst = 0.0
        for x in pts:
            xv = float(x)
            try:
                a = _evalf(got, xv)
                c = _evalf(mine, xv)
            except Exception:
                ok = False
                break
            if isinstance(a, complex) or isinstance(c, complex):
                if abs(a - c) > 1e-6:
                    ok = False
                continue
            d = abs(a - c)
            scale = max(1.0, abs(a), abs(c))
            worst = max(worst, d / scale)
            if d / scale > 1e-8:
                ok = False
                break
        if ok:
            record("diff", i, stmt, b, "PASS", expected=O.poly_to_str(O.ast_to_poly(mine)) if _is_poly(mine) else "(symbolic)")
        else:
            record("diff", i, stmt, b, "DISAGREE", oracle=r,
                   note=f"ucas deriv={r!r} vs my ast_diff at points; worst rel={worst:.2e}")


def _is_poly(node):
    try:
        O.ast_to_poly(node)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Campaign: definite integral vs high-precision quadrature / exact antiderivative
# ---------------------------------------------------------------------------

def _quad(f, a, b, n=20000):
    """Composite Simpson's rule with n (even) subintervals."""
    if n % 2:
        n += 1
    h = (b - a) / n
    s = f(a) + f(b)
    for i in range(1, n):
        s += (4 if i % 2 else 2) * f(a + i * h)
    return s * h / 3.0


def campaign_integrate(n=35):
    cases = []
    for i in range(n):
        a = RNG.randint(-2, 1)
        b = RNG.randint(a + 1, 4)
        typ = RNG.choice(["poly", "poly", "sin", "exp", "sqrt"])
        if typ == "poly":
            deg = RNG.randint(1, 3)
            coeffs = [RNG.randint(-3, 3) for _ in range(deg + 1)]
            if coeffs[-1] == 0:
                coeffs[-1] = 1
            es = O.poly_to_str(O.poly_from_coeffs(coeffs))
            # exact oracle
            p = O.poly_from_coeffs(coeffs)
            anti = O.poly_antideriv(p)
            exact = float(O.peval(anti, Fraction(b)) - O.peval(anti, Fraction(a)))
            fn = lambda x, p=p: float(O.peval(p, Fraction(str(x)))) if False else sum(float(c) * x**e for e, c in p.items())
        elif typ == "sin":
            k = RNG.randint(1, 3)
            es = f"sin({k}x)"
            exact = (1 - math.cos(k * b)) / k - (1 - math.cos(k * a)) / k
            fn = lambda x, k=k: math.sin(k * x)
        elif typ == "exp":
            k = RNG.randint(1, 2)
            es = f"exp({k}x)"
            exact = (math.exp(k * b) - math.exp(k * a)) / k
            fn = lambda x, k=k: math.exp(k * x)
        else:
            c = RNG.randint(1, 5)
            es = f"sqrt(x^2 + {c})"
            F = lambda x, c=c: 0.5 * (x * math.sqrt(x*x + c) + c * math.asinh(x / math.sqrt(c)))
            exact = F(b) - F(a)
            fn = lambda x, c=c: math.sqrt(x*x + c)
        stmt = f"integrate {es} from {a} to {b}"
        cases.append((i, stmt, es, a, b, exact, fn))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("integrate", stmts)
    for (i, stmt, es, a, b, exact, fn), blk in zip(cases, blocks):
        m = re.search(r"(?m)^\s*from .*?: F\(.*?\) - F\(.*?\) = ([-\d.eE+]+)", blk)
        if not m:
            record("integrate", i, stmt, blk, "PARSE_FAIL", note="no 'from..F(b)-F(a)=' line")
            continue
        val = float(m.group(1))
        scale = max(1.0, abs(exact), abs(val))
        rel = abs(val - exact) / scale
        if rel < 1e-10:
            record("integrate", i, stmt, blk, "PASS", expected=f"{exact:.12g}", oracle=f"{val:.12g}")
        else:
            record("integrate", i, stmt, blk, "DISAGREE", expected=f"{exact:.12g}",
                   oracle=f"{val:.12g}",
                   note=f"ucas integral={val!r}, independent={exact!r}, rel={rel:.2e}")


# ---------------------------------------------------------------------------
# Machine-integer expression generator (returns string + python evaluator)
# ---------------------------------------------------------------------------

def _mkexpr(vars, bits, depth=0):
    """Build a random machine-int expression: (string, callable(**env))."""
    mask = (1 << bits) - 1
    if depth >= 3 or (depth > 0 and RNG.random() < 0.35):
        if RNG.random() < 0.6 and vars:
            v = RNG.choice(vars)
            return v, (lambda env, v=v: env[v])
        c = RNG.randint(0, min(mask, 15))
        return str(c), (lambda env, c=c: c)
    op = RNG.choice(["+", "-", "*", "&", "|", "xor", "<<", ">>", "~"])
    if op == "~":
        es, f = _mkexpr(vars, bits, depth + 1)
        return f"~({es})", (lambda env, f=f: (~f(env)) & mask)
    es1, f1 = _mkexpr(vars, bits, depth + 1)
    es2, f2 = _mkexpr(vars, bits, depth + 1)
    if op in ("<<", ">>"):
        # limit shift to avoid huge numbers
        es2 = str(RNG.randint(0, min(bits - 1, 4)))
        f2 = (lambda env, k=int(es2): k)
    if op == "+":
        return f"({es1} + {es2})", (lambda env, f1=f1, f2=f2: (f1(env) + f2(env)) & mask)
    if op == "-":
        return f"({es1} - {es2})", (lambda env, f1=f1, f2=f2: (f1(env) - f2(env)) & mask)
    if op == "*":
        return f"({es1} * {es2})", (lambda env, f1=f1, f2=f2: (f1(env) * f2(env)) & mask)
    if op == "&":
        return f"({es1} & {es2})", (lambda env, f1=f1, f2=f2: f1(env) & f2(env))
    if op == "|":
        return f"({es1} | {es2})", (lambda env, f1=f1, f2=f2: f1(env) | f2(env))
    if op == "xor":
        return f"({es1} xor {es2})", (lambda env, f1=f1, f2=f2: f1(env) ^ f2(env))
    if op == "<<":
        return f"({es1} << {es2})", (lambda env, f1=f1, f2=f2: (f1(env) << f2(env)) & mask)
    if op == ">>":
        return f"({es1} >> {es2})", (lambda env, f1=f1, f2=f2: f1(env) >> f2(env))
    raise AssertionError


def _mkexpr_with_var(bits):
    """Generate a machine-int expression that actually references x."""
    while True:
        es, fn = _mkexpr(["x"], bits)
        if re.search(r"\bx\b", es):
            return es, fn


def campaign_range(n=40):
    cases = []
    for i in range(n):
        bits = RNG.choice([4, 4, 8])
        es, fn = _mkexpr_with_var(bits)
        cases.append((i, bits, es, fn))
    stmts = []
    for i, bits, es, fn in cases:
        stmts.append(f"f{i}(x: u{bits}) = {es}")
        stmts.append(f"range f{i}")
        stmts.append(f"table f{i}")
    blocks, full, code = run_batch("range", stmts)
    if len(blocks) < len(stmts):
        record("range", -1, "(batch)", full[-500:], "ERROR", note=f"exit={code}, blocks<stmts")
        return
    bi = 0
    for i, bits, es, fn in cases:
        rblock = blocks[bi + 1]
        tblock = blocks[bi + 2]
        bi += 3
        mask = (1 << bits) - 1
        brute = {x: fn({"x": x}) & mask for x in range(1 << bits)}
        bmin, bmax = min(brute.values()), max(brute.values())
        bdistinct = len(set(brute.values()))
        r = O.parse_range(rblock)
        table = O.parse_table(tblock)
        ok = True
        detail = ""
        if r is None:
            ok = False
            detail = "could not parse range"
        elif (r[0], r[1]) != (bmin, bmax):
            ok = False
            detail = f"range {r} vs brute ({bmin},{bmax})"
        if ok and table:
            for x, v in brute.items():
                if x in table and table[x] != v:
                    ok = False
                    detail = f"table x={x}: ucas {table[x]} vs brute {v}"
                    break
        elif ok and not table:
            detail = "(no table parsed)"
        stmt = f"f(x: u{bits})={es}; range/table"
        if ok:
            record("range", i, stmt, rblock + "\n" + tblock, "PASS",
                   expected=f"{bmin}..{bmax} ({bdistinct} distinct)")
        else:
            record("range", i, stmt, rblock + "\n" + tblock, "DISAGREE",
                   expected=f"{bmin}..{bmax} ({bdistinct} distinct)",
                   note=detail)


# ---------------------------------------------------------------------------
# Campaign: equiv verdict vs brute force on small domains
# ---------------------------------------------------------------------------

def campaign_equiv(n=35):
    cases = []
    for i in range(n):
        bits = RNG.choice([4, 8])
        es1, f1 = _mkexpr_with_var(bits)
        eq = RNG.random() < 0.5
        if eq:
            # same function (sometimes syntactically different but equal)
            es2, f2 = es1, f1
        else:
            es2, f2 = _mkexpr_with_var(bits)
            mask = (1 << bits) - 1
            # ensure they actually differ somewhere
            if all((f1({"x": x}) & mask) == (f2({"x": x}) & mask) for x in range(1 << bits)):
                es2 = f"({es2} + 1)"
                base = f2
                f2 = (lambda env, base=base, mask=mask: (base(env) + 1) & mask)
        cases.append((i, bits, es1, es2, f1, f2))
    stmts = []
    for i, bits, es1, es2, f1, f2 in cases:
        stmts.append(f"a{i}(x: u{bits}) = {es1}")
        stmts.append(f"b{i}(x: u{bits}) = {es2}")
        stmts.append(f"equiv a{i} b{i}")
    blocks, full, code = run_batch("equiv", stmts)
    if len(blocks) < len(stmts):
        record("equiv", -1, "(batch)", full[-500:], "ERROR", note=f"exit={code}")
        return
    bi = 0
    for i, bits, es1, es2, f1, f2 in cases:
        eblock = blocks[bi + 2]
        bi += 3
        mask = (1 << bits) - 1
        brute_eq = all((f1({"x": x}) & mask) == (f2({"x": x}) & mask) for x in range(1 << bits))
        text = eblock.lower()
        if "are equal on the domain" in text:
            ucas_eq = True
        elif "differ at" in text or "are not equal" in text or "not equal" in text or "counterexample" in text:
            ucas_eq = False
            # cross-check the printed counterexample point/values against brute force
            m = re.search(r"e\.g\. x=(\d+): (-?\d+) vs (-?\d+)", eblock)
            if m:
                x0, v1, v2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
                bv1, bv2 = f1({"x": x0}) & mask, f2({"x": x0}) & mask
                if (bv1, bv2) != (v1, v2):
                    record("equiv", i, f"counterexample x={x0}", eblock, "DISAGREE",
                           expected=f"{bv1} vs {bv2}", oracle=f"{v1} vs {v2}",
                           note="ucas counterexample values disagree with brute force")
                    continue
        else:
            record("equiv", i, f"equiv a b / u{bits}", eblock, "PARSE_FAIL",
                   note="no clear verdict")
            continue
        if ucas_eq == brute_eq:
            record("equiv", i, f"a={es1}; b={es2}; u{bits}", eblock, "PASS",
                   expected="equal" if brute_eq else "not equal")
        else:
            record("equiv", i, f"a={es1}; b={es2}; u{bits}", eblock, "DISAGREE",
                   expected="equal" if brute_eq else "not equal",
                   oracle="equal" if ucas_eq else "not equal",
                   note=f"brute-force says {'equal' if brute_eq else 'NOT equal'}")


# ---------------------------------------------------------------------------
# Campaign: modular arithmetic vs Python (C-style remainder)
# ---------------------------------------------------------------------------

def _int_expr():
    a = RNG.choice([RNG.randint(1, 40), 1000000007, 1000000009, RNG.randint(10**6, 10**9)])
    b = RNG.randint(1, 40)
    c = RNG.randint(1, 40)
    op = RNG.choice(["+", "-", "*"])
    if op == "+":
        return f"({a} + {b})", a + b
    if op == "-":
        return f"({a} - {b})", a - b
    return f"({a} * {b})", a * b


def campaign_mod(n=35):
    cases = []
    for i in range(n):
        es, val = _int_expr()
        mod = RNG.choice([7, 11, 13, 97, 1000, 2**31 - 1])
        stmt = f"({es}) mod {mod}"
        # C-style (truncated) remainder oracle
        r = abs(val) % mod
        if val < 0:
            r = -r
        cases.append((i, stmt, es, val, mod, r))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("mod", stmts)
    for (i, stmt, es, val, mod, r), b in zip(cases, blocks):
        num = re.search(r"(-?\d+)\s*$", b.strip())
        if not num:
            # sometimes printed as bare integer line
            record("mod", i, stmt, b, "PARSE_FAIL", note=f"output={b.strip()!r}")
            continue
        got = int(num.group(1))
        if got == r:
            record("mod", i, stmt, b, "PASS", expected=str(r))
        else:
            record("mod", i, stmt, b, "DISAGREE", expected=str(r), oracle=str(got),
                   note=f"{val} mod {mod}: ucas={got}, oracle={r}")


# ---------------------------------------------------------------------------
# Campaign: float evaluation at fixed rounding (show) vs Python IEEE double
# ---------------------------------------------------------------------------

def _float_expr():
    kind = RNG.choice(["arith", "sqrt", "trig", "exp", "log"])
    a = round(RNG.uniform(0.1, 8.0), 6)
    b = round(RNG.uniform(0.1, 5.0), 6)
    if kind == "arith":
        es = f"{a} * {b} + {round(RNG.uniform(0.1,3),6)}"
    elif kind == "sqrt":
        es = f"sqrt({a}^2 + {b})"
    elif kind == "trig":
        es = f"sin({a}) + cos({b})"
    elif kind == "exp":
        es = f"exp({a}/10) + {b}"
    else:
        es = f"log({a}) + {b}"
    return es


def campaign_float(n=35):
    cases = []
    for i in range(n):
        es = _float_expr()
        val = O.evals(O.parse(es), {})
        cases.append((i, f"show {es}", es, val))
    stmts = [c[1] for c in cases]
    blocks, full, code = run_batch("float", stmts)
    for (i, stmt, es, val), b in zip(cases, blocks):
        m = re.search(r"=\s*([-\d.eE+]+)\s*$", b.strip().splitlines()[-1] if b.strip() else "")
        if not m:
            m = re.search(r"=\s*([-\d.eE+]+)", b)
        if not m:
            record("float", i, stmt, b, "PARSE_FAIL", note=f"output={b.strip()!r}")
            continue
        got = float(m.group(1))
        scale = max(1.0, abs(val), abs(got))
        rel = abs(got - val) / scale
        # ucas prints ~10 significant digits
        if rel < 2e-9:
            record("float", i, stmt, b, "PASS", expected=f"{val:.12g}", oracle=f"{got:.12g}")
        else:
            record("float", i, stmt, b, "DISAGREE", expected=f"{val:.12g}",
                   oracle=f"{got:.12g}", note=f"rel={rel:.2e}")


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

CAMPAIGNS = {
    "expand": campaign_expand,
    "factor": campaign_factor,
    "ratfunc": campaign_ratfunc,
    "together": campaign_together,
    "diff": campaign_diff,
    "integrate": campaign_integrate,
    "range": campaign_range,
    "equiv": campaign_equiv,
    "mod": campaign_mod,
    "float": campaign_float,
}


def main():
    args = sys.argv[1:]
    names = [c for c in CAMPAIGNS if not args or any(a.lower() in c for a in args)]
    for name in names:
        print(f"== campaign {name} ==")
        try:
            CAMPAIGNS[name]()
        except Exception as ex:
            import traceback
            record(name, -1, "(harness exception)", "", "ERROR", note=traceback.format_exc()[-600:])
    with open(os.path.join(HERE, "diff_results.json"), "w") as fh:
        json.dump(RESULTS, fh, indent=1)
    print("\n=== SUMMARY ===")
    total = 0
    for (camp, verdict), cnt in sorted(COUNTS.items()):
        print(f"  {camp:10s} {verdict:12s} {cnt}")
        total += cnt
    print(f"  TOTAL cases: {total}")
    bad = sum(n for (c, v), n in COUNTS.items() if v != "PASS")
    print(f"  NON-PASS: {bad}")


if __name__ == "__main__":
    main()
