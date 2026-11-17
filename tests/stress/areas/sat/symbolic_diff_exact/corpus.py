"""Deterministic corpus of 200+ expression pairs (identities and near-misses)."""

from __future__ import annotations

import math
from fractions import Fraction

from exprlib import Expr, X, Undefined


def _binom_expand(a, b, n, x="x", y="y"):
    """Expansion of (a*x + b*y)^n as an exact Expr AST."""
    xx, yy = X(x), X(y)
    terms = []
    for k in range(n + 1):
        c = math.comb(n, k) * (a ** (n - k)) * (b ** k)
        pieces = []
        if c != 1:
            pieces.append(Expr.num(c))
        if n - k > 0:
            pieces.append(xx ** (n - k))
        if k > 0:
            pieces.append(yy ** k)
        if not pieces:
            term = Expr.num(1)
        else:
            term = pieces[0]
            for p in pieces[1:]:
                term = term * p
        terms.append(term)
    out = terms[0]
    for t in terms[1:]:
        out = out + t
    return out


def _poly_eval_mul(terms, xx):
    """Build c0 + c1*xx + ... from a coefficient list."""
    out = Expr.num(terms[0])
    for i, c in enumerate(terms[1:], 1):
        out = out + Expr.num(c) * (xx ** i)
    return out


def build_corpus():
    """Return a list of dicts: id, f, g, intended, family, shape, note."""
    pairs = []
    serial = [0]

    def add(f, g, intended, family, shape, note=""):
        serial[0] += 1
        pairs.append({
            "id": "p%03d" % serial[0],
            "f": f, "g": g,
            "intended": intended,     # True identity or near-miss (constructor hint)
            "family": family,
            "shape": shape,           # pairs sharing a shape are renamed variants
            "note": note,
        })

    x, y = X("x"), X("y")

    # ---- Family A: binomial squares/cubes with coefficient perturbations ----
    aidx = 0
    for a in (1, 2, 3):
        for b in (1, 2, 3):
            for n in (2, 3, 4):
                aidx += 1
                base = (a * x + b * y) ** n
                exact = _binom_expand(a, b, n)
                add(base, exact, True, "binom", "A%d" % aidx,
                    "(%d*x+%d*y)^%d full expansion" % (a, b, n))
                # near-miss: bump the constant term of the expansion by +1
                add(base, exact + 1, False, "binom", "A%d" % aidx,
                    "same but constant term +1")
                # near-miss: flip sign of the leading coefficient term
                perturbed = exact - 2 * (Expr.num(a ** n) * (x ** n))
                add(base, perturbed, False, "binom", "A%d" % aidx,
                    "leading x^n coefficient negated")

    # ---- Family B: difference of squares (with shifted sub-expressions) ----
    bidx = 0
    for a in (0, 1, 2, -1, -3):
        for b in (0, 1, 2, -2):
            bidx += 1
            u, v = x + a, y + b
            add(u ** 2 - v ** 2, (u - v) * (u + v), True, "diffsq", "B%d" % bidx,
                "(x+%d)^2-(y+%d)^2" % (a, b))
            add(u ** 2 - v ** 2, (u - v) * (u + v) + 1, False, "diffsq", "B%d" % bidx,
                "near-miss: +1")
            add(u ** 2 + v ** 2, (u - v) * (u + v), False, "diffsq", "B%d" % bidx,
                "near-miss: sum vs difference of squares")

    # ---- Family C: sum/difference of cubes ----
    cidx = 0
    for a in (1, 2, 3):
        cidx += 1
        u, v = x + a, y
        add(u ** 3 + v ** 3, (u + v) * (u * u - u * v + v * v), True,
            "sumcube", "C%d" % cidx, "(x+%d)^3+y^3" % a)
        add(u ** 3 - v ** 3, (u - v) * (u * u + u * v + v * v), True,
            "diffcube", "C%d" % cidx, "(x+%d)^3-y^3" % a)
        add(u ** 3 + v ** 3, (u + v) * (u * u - u * v + v * v) + 1, False,
            "sumcube", "C%d" % cidx, "near-miss +1")
        add(u ** 3 - v ** 3, (u - v) * (u * u + u * v - v * v), False,
            "diffcube", "C%d" % cidx, "near-miss: last sign flipped")

    # ---- Family D: rational identities ----
    didx = 0
    for a in (1, 2, 3, -1, -2):
        didx += 1
        add((x * x - a * a) / (x - a), x + a, True, "rational", "D%d" % didx,
            "(x^2-a^2)/(x-a)=x+a, a=%d" % a)
        add((x * x - a * a) / (x - a), x + a + 1, False, "rational", "D%d" % didx,
            "near-miss x+a+1")
    for a in (1, 2, -1):
        didx += 1
        add(1 / x + 1 / y, (x + y) / (x * y), True, "rational", "D%d" % didx,
            "1/x+1/y=(x+y)/(xy)")
        add(1 / x - 1 / y, (y - x) / (x * y), True, "rational", "D%d" % didx,
            "1/x-1/y=(y-x)/(xy)")
        add(1 / x + 1 / y, (x + y + 1) / (x * y), False, "rational", "D%d" % didx,
            "near-miss numerator+1")
        add(x / (x + a) + a / (x + a), Expr.num(1), True, "rational", "D%d" % didx,
            "x/(x+a)+a/(x+a)=1")

    # ---- Family E: complete-the-square quadratics ----
    eidx = 0
    for a in (1, 2, 3, 4, -1, -2):
        for b in (0, 1, -3):
            eidx += 1
            add(x * x + 2 * a * x + a * a, (x + a) ** 2, True, "quadratic", "E%d" % eidx,
                "x^2+2ax+a^2=(x+a)^2, a=%d" % a)
            add(x * x + 2 * a * x + a * a + b + 1, (x + a) ** 2, False,
                "quadratic", "E%d" % eidx, "near-miss")

    # ---- Family F: trivariate square (shape reduction playground) ----
    fidx = 0
    z = X("z")
    for a in (1, 2):
        fidx += 1
        add((x + y + z) ** 2,
            x * x + y * y + z * z + 2 * x * y + 2 * x * z + 2 * y * z,
            True, "trivar", "F%d" % fidx, "(x+y+z)^2 expansion")
        add((x + y + z) ** 2,
            x * x + y * y + z * z + 2 * x * y + 2 * x * z + 2 * y * z + a,
            False, "trivar", "F%d" % fidx, "near-miss +a")

    # ---- Family G: shifted-substitution variants of (x+y)^2 identity ----
    # These share shape with A-family binomial squares but are generated here as
    # explicit renamed/shifted copies to exercise shape reduction verification.
    gidx = 0
    base_f = (x + y) ** 2
    base_g = x * x + 2 * x * y + y * y
    renamings = [
        {"x": "x", "y": "y"},          # identity
        {"x": "y", "y": "x"},          # swap
        {"x": "a", "y": "b"},          # pure rename
        {"x": "u", "y": "v"},          # pure rename
    ]
    for m in renamings:
        gidx += 1
        add(base_f.rename(m), base_g.rename(m), True, "rename", "G%d" % gidx,
            "renamed (x+y)^2 identity: %s" % m)
        add(base_f.rename(m), (base_g + 1).rename(m), False, "rename", "G%d" % gidx,
            "renamed near-miss +1")
    # shift variants: x -> x+1, y -> y-2
    for sx, sy in ((1, 0), (0, 1), (1, 1), (2, -3), (-1, 2)):
        gidx += 1
        vf = base_f.subst("x", x + sx).subst("y", y + sy)
        vg = base_g.subst("x", x + sx).subst("y", y + sy)
        add(vf, vg, True, "shift", "G%d" % gidx, "shifted identity x+%d,y+%d" % (sx, sy))
        add(vf, vg + 1, False, "shift", "G%d" % gidx, "shifted near-miss")

    # ---- Family H: miscellaneous classic identities ----
    add((x + 1) * (y + 1), x * y + x + y + 1, True, "misc", "H1", "(x+1)(y+1)")
    add((x + 1) * (y + 1), x * y + x + y, False, "misc", "H1", "near-miss: missing +1")
    add((x - 1) * (x + 1) * (x * x + 1), x ** 4 - 1, True, "misc", "H2", "x^4-1 factorization")
    add((x ** 3 - 1) / (x - 1), x * x + x + 1, True, "misc", "H3", "(x^3-1)/(x-1)")
    add((x ** 3 - 1) / (x - 1), x * x + x + 2, False, "misc", "H3", "near-miss")
    add((x + y) ** 5, _binom_expand(1, 1, 5), True, "misc", "H4", "(x+y)^5")
    add((x + y) ** 5, _binom_expand(1, 1, 5) - 2 * x * y ** 4, False, "misc", "H4",
        "near-miss: coefficient of x*y^4 off by 2")
    add(x ** 2 - 2 * x + 1, (x - 1) ** 2, True, "misc", "H5", "(x-1)^2")
    add(x ** 2 - 2 * x + 1, (x - 1) ** 2 + 1, False, "misc", "H5", "near-miss")

    return pairs


# ---- exact rational oracle -------------------------------------------

def oracle_points(vars_needed):
    """Deterministic rational sample points avoiding small denominators."""
    vals = [Fraction(v) for v in (-3, -2, -1, 0, 1, 2, 3)]
    vals += [Fraction(1, 2), Fraction(-1, 2), Fraction(2, 3), Fraction(-3, 4)]
    pts = []
    names = sorted(vars_needed)
    if len(names) == 1:
        pts = [{names[0]: v} for v in vals]
    elif len(names) == 2:
        # 8x8 grid = 64 points, deterministic
        for v1 in vals[:8]:
            for v2 in vals[:8]:
                pts.append({names[0]: v1, names[1]: v2})
    else:
        for i, v in enumerate(vals[:9]):
            pts.append({nm: Fraction((i + j) % 5 - 2) for j, nm in enumerate(names)})
    return pts


def oracle_verdict(f, g):
    """Exact rational-function identity test.

    Returns (is_identity, detail).  A nonzero value at ANY point where both
    sides are defined refutes the identity exactly.  If all sampled points give
    zero (and there are strictly more points than any polynomial degree here),
    the rational functions agree identically.
    """
    needed = f.vars() | g.vars()
    pts = oracle_points(needed)
    diffs = []
    defined = 0
    for env in pts:
        try:
            d = f.eval(env) - g.eval(env)
        except (Undefined, ZeroDivisionError):
            continue
        defined += 1
        if d != 0:
            diffs.append((env, d))
            return False, {"refuted_at": env, "difference": d,
                           "points_checked": defined}
    return True, {"points_checked": defined, "all_zero": True}
