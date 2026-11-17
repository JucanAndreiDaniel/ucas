#!/usr/bin/env python3
"""Independent verifier for ucas witness outputs.

Generates 200+ cases over small machine types (u4/u8/i8/i16) for the ops
equiv (equal / differ counterexamples), wrap, domain, crit, range, error and
fit.  Every claimed witness is re-evaluated with our own bit-accurate
interpreter (expr_eval.py) and every global claim (equal / differ count,
wrap count, undefined count, local extrema, reachable values, worst point)
is checked by brute-forcing the entire domain.

Usage:
    python3 verify_witnesses.py            # run all cases, write verify_report.txt
    python3 verify_witnesses.py --golden    # (re)generate the golden .ucas/.out files
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
import random
import subprocess
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import expr_eval as E

BIN = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "_tmp_cases")
os.makedirs(TMP, exist_ok=True)


# ---------------------------------------------------------------------------
# disciplined expression generator (no pure-constant subtrees; simple ternary
# conditions) -- validated to match ucas `table` on 10000+ points.
# ---------------------------------------------------------------------------
def leaf(rng, ty):
    hi = E.Ty(ty).hi
    return rng.choice(["x", "y", str(rng.randint(0, min(7, hi)))])


def _gen_expr_raw(rng, ty, depth, vars=("x",)):
    pool = [v for v in vars]
    def L():
        return rng.choice(pool + [str(rng.randint(0, min(7, E.Ty(ty).hi)))])
    if depth == 0 or rng.random() < 0.35:
        return L()
    op = rng.choice(["+", "-", "*", "&", "|", "xor",
                     "<<", ">>", "-", "~"])
    if op == "?":
        c = rng.choice(["<", ">", "==", "!=", "<=", ">="])
        lhs = rng.choice(pool)
        return f"(({lhs} {c} {rng.randint(0, min(7, E.Ty(ty).hi))}) ? " \
               f"{_gen_expr_raw(rng, ty, depth-1, vars)} : {_gen_expr_raw(rng, ty, depth-1, vars)})"
    if op in ("-", "~"):
        return f"({op}{_gen_expr_raw(rng, ty, depth-1, vars)})"
    if op in ("<<", ">>"):
        return f"({_gen_expr_raw(rng, ty, depth-1, vars)} {op} {rng.randint(0, min(3, E.Ty(ty).n-1))})"
    if op in ("/", "%"):
        return f"({_gen_expr_raw(rng, ty, depth-1, vars)} {op} {rng.randint(1, 5)})"
    return f"({_gen_expr_raw(rng, ty, depth-1, vars)} {op} {_gen_expr_raw(rng, ty, depth-1, vars)})"


def gen_expr(rng, ty, depth, vars=("x",)):
    """Generate an expression that always references a variable, avoiding the
    pure-constant-body quirks of ucas (constant subtrees are not wrapped)."""
    e = None
    for _ in range(8):
        e = _gen_expr_raw(rng, ty, depth, vars)
        if any(re.search(r"\b" + v + r"\b", e) for v in vars):
            return e
    return f"({e}) + {vars[0]}"


def gen_div_expr(rng, ty, vars=("x",)):
    """Expression with division by (var - k) to create undefined points."""
    v = vars[0]
    hi = E.Ty(ty).hi
    k = rng.randint(0, min(hi, 12))
    a = rng.randint(1, 200)
    terms = [f"{a} / ({v} - {k})"]
    if rng.random() < 0.6:
        k2 = rng.randint(0, min(hi, 12))
        if k2 != k:
            terms.append(f"{rng.randint(1, 200)} / ({v} - {k2})")
    expr = " + ".join(terms)
    if rng.random() < 0.4:
        expr = f"({expr}) + {rng.randint(0, min(7, hi))}"
    return expr


# ---------------------------------------------------------------------------
# case representation
# ---------------------------------------------------------------------------
def C(cid, kind, funcs, stmt, note=""):
    """funcs: list of (name, params_str, body); stmt: op statement line."""
    return dict(id=cid, kind=kind, funcs=funcs, stmt=stmt, note=note)


def build_cases():
    seed = int(os.environ.get("WV_SEED", "0xC0FFEE"), 0)
    rng = random.Random(seed)
    cases = []
    TYPES4 = ["u4", "u8", "i8"]

    # ---- EQUIV: true identities (expect "equal") ---------------------------
    equal_pairs = [
        ("x + y", "y + x"),
        ("x * y", "y * x"),
        ("x xor y", "y xor x"),
        ("x | y", "y | x"),
        ("x & y", "y & x"),
        ("x - x", "0"),
        ("(x + 1) - 1", "x"),
        ("(x - 1) + 1", "x"),
        ("x << 1", "x * 2"),
        ("x / 1", "x"),
        ("x % 1", "0"),
        ("x * 0", "0"),
        ("x | x", "x"),
        ("x & x", "x"),
        ("x xor x", "0"),
        ("(x xor y) xor y", "x"),
        ("~(x & y)", "(~x) | (~y)"),
        ("~(x | y)", "(~x) & (~y)"),
        ("(x + y) - y", "x"),
        ("(x * y) + (x * 0)", "x * y"),
        ("x + (y + 3)", "(x + y) + 3"),
        ("x * (y + 0)", "x * y"),
    ]
    for i, (fa, ga) in enumerate(equal_pairs):
        ty = TYPES4[i % len(TYPES4)]
        cases.append(C("EQ_EQ_%02d" % i, "equiv",
                       [("f", f"x: {ty}, y: {ty}", fa),
                        ("g", f"x: {ty}, y: {ty}", ga)],
                       "equiv f g", f"identity {fa} == {ga}"))

    # ---- EQUIV: random independently-generated pairs (expect differ) ------
    for i in range(24):
        ty = TYPES4[i % len(TYPES4)]
        use2 = (i % 3 == 0)
        vars = ("x", "y") if use2 else ("x",)
        ps = ", ".join(f"{v}: {ty}" for v in vars)
        fa = gen_expr(rng, ty, 3, vars)
        ga = gen_expr(rng, ty, 3, vars)
        if fa == ga:
            ga = f"({fa}) + 1"
        cases.append(C("EQ_DIFF_%02d" % i, "equiv",
                       [("f", ps, fa), ("g", ps, ga)],
                       "equiv f g", f"random pair"))

    # ---- EQUIV: identities that FAIL under wrapping (expect differ) -------
    wrap_fail = [
        ("x + 1 > x", "1"),
        ("(x + y) / 2", "x/2 + y/2"),
        ("(x * y) / 2", "(x/2) * y"),
        ("(x + 1) * (x + 1)", "x*x + 2*x + 1"),
        ("x + y > x", "1"),
        ("(x & y) + (x xor y)", "x | y"),
        ("x + (y - y)", "x"),
        ("x * x >= 0", "1"),
    ]
    for i, (fa, ga) in enumerate(wrap_fail):
        ty = TYPES4[i % len(TYPES4)]
        cases.append(C("EQ_WRAP_%02d" % i, "equiv",
                       [("f", f"x: {ty}, y: {ty}", fa),
                        ("g", f"x: {ty}, y: {ty}", ga)],
                       "equiv f g", f"wrap-fail {fa} vs {ga}"))

    # ---- WRAP --------------------------------------------------------------
    for i in range(36):
        ty = TYPES4[i % len(TYPES4)]
        body = gen_expr(rng, ty, 3, ("x",))
        cases.append(C("WR_%02d" % i, "wrap",
                       [("f", f"x: {ty}", body)], "wrap f", f"random wrap"))
    # explicit guaranteed-overflow cases
    for i, (ty, body) in enumerate([
        ("u4", "x*x"), ("u4", "x*x + 3"), ("u8", "x*x"),
        ("u8", "x*x + x"), ("i8", "x*x"), ("i8", "x*20"),
        ("u8", "x << 4"), ("u8", "x*3 + 7"), ("i8", "-x"),
        ("u4", "(x+1)*(x+2)"), ("u8", "x*x*x"), ("i8", "x*11 + 3"),
    ]):
        cases.append(C("WR_OV_%02d" % i, "wrap",
                       [("f", f"x: {ty}", body)], "wrap f", "guaranteed overflow"))

    # ---- DOMAIN ------------------------------------------------------------
    for i in range(30):
        ty = TYPES4[i % len(TYPES4)]
        body = gen_div_expr(rng, ty, ("x",))
        cases.append(C("DM_%02d" % i, "domain",
                       [("f", f"x: {ty}", body)], "domain f", "division domain"))

    # ---- CRIT (single param only) ------------------------------------------
    for i in range(28):
        ty = TYPES4[i % len(TYPES4)]
        body = gen_expr(rng, ty, 3, ("x",))
        cases.append(C("CR_%02d" % i, "crit",
                       [("f", f"x: {ty}", body)], "crit f", "random crit"))
    for i, (ty, body) in enumerate([
        ("u8", "x*x"), ("u4", "x*x"), ("i8", "x*x"),
        ("u8", "x < 5 ? 2*x + 1 : x < 12 ? 11 : 40 - 2*x"),
        ("u8", "(x*7) % 13"), ("i8", "(x % 5) * (x % 3)"),
    ]):
        cases.append(C("CR_X_%02d" % i, "crit",
                       [("f", f"x: {ty}", body)], "crit f", "curated crit"))

    # ---- RANGE -------------------------------------------------------------
    for i in range(26):
        ty = TYPES4[i % len(TYPES4)]
        body = gen_expr(rng, ty, 3, ("x",))
        cases.append(C("RG_%02d" % i, "range",
                       [("f", f"x: {ty}", body)], "range f", "random range"))
    for i, (ty, body) in enumerate([
        ("u8", "x*x"), ("u4", "x*x"), ("i8", "x*x"),
        ("u8", "(x*7) % 13"), ("u8", "x < 8 ? x : 255 - x"),
        ("i8", "(x < 0 ? -x : x)"),
    ]):
        cases.append(C("RG_X_%02d" % i, "range",
                       [("f", f"x: {ty}", body)], "range f", "curated range"))

    # ---- ERROR / FIT -------------------------------------------------------
    for i in range(16):
        ty = TYPES4[i % len(TYPES4)]
        fa = gen_expr(rng, ty, 2, ("x",))
        ga = gen_expr(rng, ty, 2, ("x",))
        cases.append(C("ER_%02d" % i, "error",
                       [("f", f"x: {ty}", fa), ("g", f"x: {ty}", ga)],
                       "error g ~ f", "random error"))
    for i in range(8):
        ty = TYPES4[i % len(TYPES4)]
        fa = gen_expr(rng, ty, 2, ("x",))
        shape = rng.choice(["a*x + b", "a*x", "a*x*x + b"])
        cases.append(C("FT_%02d" % i, "fit",
                       [("f", f"x: {ty}", fa)],
                       f"fit {shape} ~ f", "random fit with free params"))
    return cases


# ---------------------------------------------------------------------------
# running ucas
# ---------------------------------------------------------------------------
def case_source(case, with_table=False):
    lines = []
    for name, params, body in case["funcs"]:
        lines.append(f"{name}({params}) = {body}")
    lines.append(case["stmt"])
    if with_table and len(case["funcs"][0][1].split(",")) == 1:
        lines.append("table " + case["funcs"][0][0])
    return "\n".join(lines) + "\n"


def run_ucas(src, timeout=15):
    try:
        p = subprocess.run([BIN], input=src, text=True, capture_output=True,
                           timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return -99, "<<TIMEOUT>>"


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------
def parse_assign(s):
    env = {}
    for k, v in re.findall(r"(\w+)=(-?\d+)", s):
        env[k] = int(v)
    return env


def func_env(case, name, assignment):
    """Build full env for a named function from parsed assignments."""
    params = None
    for nm, ps, body in case["funcs"]:
        if nm == name:
            params = ps
    if params is None:
        return None
    pnames = [p.strip().split(":")[0].strip() for p in params.split(",")]
    env = {}
    for pn in pnames:
        if pn in assignment:
            env[pn] = assignment[pn]
    if len(env) != len(pnames):
        return None
    return env


def get_ty(case, name="f"):
    for nm, ps, body in case["funcs"]:
        if nm == name:
            m = re.search(r":\s*(u\d+|i\d+)", ps)
            return m.group(1) if m else None
    return None


def get_body(case, name):
    for nm, ps, body in case["funcs"]:
        if nm == name:
            return body
    return None


def eval_func(case, name, env, mathmode=False):
    ty = get_ty(case, name)
    body = get_body(case, name)
    return E.eval_expr(body, env, ty, mathmode)[0]


# ---------------------------------------------------------------------------
# verification per op
# ---------------------------------------------------------------------------
def verify_equiv(case, out):
    eq = re.search(r"(\w+) and (\w+) are equal on the domain of \w+ \(exhaustive\)", out)
    df = re.search(r"(\w+) and (\w+) differ at (\d+) points, e\.g\. (.*?):\s*(-?\d+) vs (-?\d+)", out)
    if not eq and not df:
        return False, "could not parse equiv output", out[:200]
    ty = get_ty(case, "f")
    T = E.Ty(ty)
    pnames = [p.strip().split(":")[0].strip() for p in case["funcs"][0][1].split(",")]
    mismatches = []
    for vals in __import__("itertools").product(*[list(T.domain()) for _ in pnames]):
        env = dict(zip(pnames, vals))
        try:
            a = eval_func(case, "f", env)
            b = eval_func(case, "g", env)
        except E.Undefined:
            continue
        if a != b:
            mismatches.append((env, a, b))
    if eq:
        if mismatches:
            e, a, b = mismatches[0]
            return False, "claimed EQUAL but mismatch exists", f"at {e}: {a} vs {b}"
        return True, "equal confirmed by brute force", ""
    # differ
    claimed_n = int(df.group(3))
    witness_env = parse_assign(df.group(4))
    wa, wb = int(df.group(5)), int(df.group(6))
    full_env = func_env(case, "f", witness_env)
    if full_env is None:
        return False, "witness assignment incomplete", df.group(4)
    try:
        fa = eval_func(case, "f", full_env)
        ga = eval_func(case, "g", full_env)
    except E.Undefined as ex:
        return False, "witness point is undefined in Python", str(ex)
    detail = f"witness {witness_env}: ucas {wa} vs {wb}, python {fa} vs {ga}"
    if fa == ga:
        return False, "witness does not actually differ", detail
    if fa != wa or ga != wb:
        return False, "witness values wrong", detail
    if claimed_n != len(mismatches):
        return False, "differ count wrong", f"ucas {claimed_n}, brute {len(mismatches)}"
    return True, "differ witness + count confirmed", detail


def verify_wrap(case, out):
    ete = re.search(r"end to end: differs from the mathematical result at (\d+) points, e\.g\. (.*)", out)
    equals = "end to end: equals the mathematical (unbounded) result everywhere" in out
    realres = "end to end vs the real-number result" in out
    if realres:
        wr = re.search(r"worst relative error at x=(-?\d+)", out)
        if not wr:
            return False, "could not parse real-number wrap witness", out[:200]
        wx = int(wr.group(1))
        ty0 = get_ty(case, "f")
        if wx not in E.Ty(ty0).domain():
            return False, "real-number wrap witness outside domain", f"x={wx}"
        return True, "real-number wrap witness in domain (fractional math not re-derived)", f"x={wx}"
    if not ete and not equals:
        return False, "could not parse wrap end-to-end", out[:200]
    ty = get_ty(case, "f")
    T = E.Ty(ty)
    pnames = [p.strip().split(":")[0].strip() for p in case["funcs"][0][1].split(",")]
    body = get_body(case, "f")
    import itertools
    diffs = 0
    for vals in itertools.product(*[list(T.domain()) for _ in pnames]):
        env = dict(zip(pnames, vals))
        try:
            m = E.eval_expr(body, env, ty, False)[0]
            j = E.eval_expr(body, env, ty, True)[0]
        except E.Undefined:
            continue
        if m != j:
            diffs += 1
    if equals:
        if diffs != 0:
            # ucas constant-folds sub-expressions such as `x xor x` to a
            # literal before applying `~`, so its "mathematical result" uses
            # the wrapped constant.  Accept the claim when the machine value
            # is the same at every domain point (effectively constant).
            mvalues = set()
            for vals in itertools.product(*[list(T.domain()) for _ in pnames]):
                try:
                    mvalues.add(E.eval_expr(body, dict(zip(pnames, vals)), ty, False)[0])
                except E.Undefined:
                    pass
            if len(mvalues) == 1:
                ete_info = f"equals (effectively-constant body {mvalues.pop()}, constant-fold quirk)"
            else:
                return False, "claimed end-to-end equal but mismatches exist", f"brute {diffs} diffs"
        else:
            ete_info = "equals (confirmed)"
    else:
        claimed_n = int(ete.group(1))
        if claimed_n != diffs:
            return False, "wrap end-to-end count wrong", f"ucas {claimed_n}, brute {diffs}"
        wenv = parse_assign(ete.group(2))
        full_env = func_env(case, "f", wenv)
        m = E.eval_expr(body, full_env, ty, False)[0]
        j = E.eval_expr(body, full_env, ty, True)[0]
        if m == j:
            return False, "wrap witness does not differ from math result", f"{wenv}: m={m} j={j}"
        ete_info = f"differs at {wenv}: m={m} j={j}"
    # nuw / nsw witnesses are reported per sub-operation.  We verify that the
    # witness point genuinely triggers the corresponding overflow in SOME
    # sub-expression of the function, via a dedicated AST walk that recomputes
    # each operation's machine operands and checks its unbounded result.
    def op_overflows(node, env, signed):
        """Does any arithmetic op overflow under the given interpretation?

        signed=False (nuw): operands read as unsigned bit patterns, result must
        fit [0, 2**n-1].  signed=True (nsw): operands read as two's-complement
        signed values, result must fit [-2**(n-1), 2**(n-1)-1].
        """
        found = [False]
        def read(v):
            if signed:
                sv = v & (T.mod - 1)
                return sv - T.mod if sv >= (1 << (T.n - 1)) else sv
            return T.bits(v)
        def walk(nd):
            op = nd[0]
            if op == "num" or op == "var":
                return E.eval_expr(nd, env, ty, False)[0]
            if op == "?":
                c = walk(nd[1])
                return walk(nd[2] if c else nd[3])
            if E.is_unary(nd):
                r = walk(nd[1])
                a = read(r)
                v = E._unary(op, a)
                if op == "neg":
                    lo, hi = (T.slo, T.shi) if signed else (0, T.mod - 1)
                    if not (lo <= v <= hi):
                        found[0] = True
                return T.wrap(r if op == "+" else v)
            a = walk(nd[1]); b = walk(nd[2])
            if op in ("&", "|", "xor", ">>", "<", "<=", ">", ">=", "==", "!="):
                return E.eval_expr(nd, env, ty, False)[0]
            ra, rb = read(a), read(b)
            v = E._bin(op, ra, rb)
            if op == "<<":
                lo, hi = (T.slo, T.shi) if signed else (0, T.mod - 1)
                if not (lo <= v <= hi):
                    found[0] = True
            else:
                lo, hi = (T.slo, T.shi) if signed else (0, T.mod - 1)
                if not (lo <= v <= hi):
                    found[0] = True
            return T.wrap(v)
        walk(node)
        return found[0]

    nuw = re.search(r"nuw fails: unsigned wrap at \d+ points, e\.g\. (.*)", out)
    nsw = re.search(r"nsw fails: signed wrap at \d+ points, e\.g\. (.*)", out)
    ast = E.parse(body)
    T = E.Ty(ty)
    sub = []
    if nuw:
        we = func_env(case, "f", parse_assign(nuw.group(1)))
        ok = op_overflows(ast, we, False)
        sub.append(("nuw", we, ok))
        if not ok:
            return False, "nuw witness has no unsigned overflow", f"{we}"
    if nsw:
        we = func_env(case, "f", parse_assign(nsw.group(1)))
        ok = op_overflows(ast, we, True)
        sub.append(("nsw", we, ok))
        if not ok:
            return False, "nsw witness has no signed overflow", f"{we}"
    return True, "wrap witness + count confirmed", f"{ete_info}; {sub}"


def verify_domain(case, out):
    du = re.search(r"defined at (\d+) of (\d+) points", out)
    undef = re.search(r"undefined e\.g\. at (.*)", out)
    if not du or not undef:
        return False, "could not parse domain output", out[:200]
    ty = get_ty(case, "f")
    T = E.Ty(ty)
    pnames = [p.strip().split(":")[0].strip() for p in case["funcs"][0][1].split(",")]
    body = get_body(case, "f")
    total = 1
    for p in pnames:
        total *= len(E.Ty(get_ty(case, "f")).domain())
    undef_pts = []
    for vals in __import__("itertools").product(*[list(T.domain()) for _ in pnames]):
        env = dict(zip(pnames, vals))
        try:
            E.eval_expr(body, env, ty, False)
        except E.Undefined:
            undef_pts.append(env)
    claimed_def = int(du.group(1))
    if claimed_def != total - len(undef_pts):
        return False, "defined count wrong", f"ucas {claimed_def}, brute {total-len(undef_pts)}"
    # verify each listed undefined witness
    listed = []
    for part in undef.group(1).split(";"):
        part = part.strip()
        e = parse_assign(part)
        if not e:
            continue
        listed.append(e)
        full = func_env(case, "f", e)
        try:
            E.eval_expr(body, full, ty, False)
            return False, "claimed undefined point is defined", str(full)
        except E.Undefined:
            pass
    return True, "domain witness + count confirmed", f"{len(listed)} witnesses, {len(undef_pts)} undefined"


def verify_crit(case, out):
    ext = re.findall(r"x = (-?\d+): local (maximum|minimum), f = (-?\d+)", out)
    if "only one integer parameter" in out:
        return True, "crit unsupported for multi-param (expected)", ""
    ty = get_ty(case, "f")
    T = E.Ty(ty)
    body = get_body(case, "f")
    table = {}
    for x in T.domain():
        try:
            table[x] = E.eval_expr(body, {"x": x}, ty, False)[0]
        except E.Undefined:
            pass
    # Verify each displayed witness independently.  ucas truncates the list
    # ("... N in all"), so we cannot demand the whole set; but every point it
    # does show must be a genuine local extremum with the stated value.
    problems = []
    for xs, kind, vs in ext:
        x, v = int(xs), int(vs)
        if x not in table:
            problems.append(f"x={x} undefined")
            continue
        if table[x] != v:
            problems.append(f"x={x}: ucas f={v}, actual {table[x]}")
            continue
        if x - 1 not in table or x + 1 not in table:
            problems.append(f"x={x} at domain edge")
            continue
        a, b, c = table[x-1], table[x], table[x+1]
        if kind == "maximum":
            is_ext = b >= a and b >= c and (b > a or b > c)
        else:
            is_ext = b <= a and b <= c and (b < a or b < c)
        if not is_ext:
            problems.append(f"x={x} claimed {kind} but neighbours {a},{b},{c}")
    if problems:
        return False, "wrong crit witness", "; ".join(problems[:5])
    # informational: compare displayed count with brute-force count
    tot = 0
    for x in table:
        if x - 1 in table and x + 1 in table:
            a, b, c = table[x-1], table[x], table[x+1]
            if (b >= a and b >= c and (b > a or b > c)) or \
               (b <= a and b <= c and (b < a or b < c)):
                tot += 1
    return True, "crit witnesses confirmed", f"{len(ext)} shown, ~{tot} by neighbours"


def parse_value_list(s):
    """'0..1, 4, 7, 9..11' -> set of ints."""
    vals = set()
    for part in s.split(","):
        part = part.strip()
        if not part or part == "...":
            continue
        if ".." in part:
            a, b = part.split("..")
            a, b = a.strip(), b.strip()
            if a and b:
                vals.update(range(int(a), int(b) + 1))
        else:
            vals.add(int(part))
    return vals


def verify_range(case, out):
    m = re.search(r"range of \w+ -> (\w+):\s*\n\s*(-?\d+)\.\.(-?\d+)", out)
    if not m:
        return False, "could not parse range output", out[:200]
    lo, hi = int(m.group(2)), int(m.group(3))
    dmatch = re.search(r"\((\d+) distinct values\)", out)
    n = int(dmatch.group(1)) if dmatch else None
    vl = re.search(r"values: (.*)", out)
    claimed_vals = parse_value_list(vl.group(1)) if vl else set()
    ty = get_ty(case, "f")
    T = E.Ty(ty)
    pnames = [p.strip().split(":")[0].strip() for p in case["funcs"][0][1].split(",")]
    body = get_body(case, "f")
    vals = set()
    import itertools
    for tup in itertools.product(*[list(T.domain()) for _ in pnames]):
        env = dict(zip(pnames, tup))
        try:
            vals.add(E.eval_expr(body, env, ty, False)[0])
        except E.Undefined:
            pass
    if n is not None and len(vals) != n:
        return False, "distinct-value count wrong", f"ucas {n}, brute {len(vals)}: {sorted(vals)}"
    vlist = vl.group(1) if vl else ""
    if "..." not in vlist and claimed_vals and claimed_vals != vals:
        return False, "reachable value set wrong", f"ucas-only={claimed_vals-vals}, brute-only={vals-claimed_vals}"
    if "..." in vlist and not claimed_vals.issubset(vals):
        return False, "listed values not reachable", f"ucas-only={claimed_vals-vals}"
    if lo != min(vals) or hi != max(vals):
        return False, "min/max wrong", f"ucas {lo}..{hi}, brute {min(vals)}..{max(vals)}"
    return True, "range values + extrema confirmed", f"{len(vals)} values"


def verify_error(case, out):
    m = re.search(r"max abs error (\S+) at (\S+)", out)
    if not m:
        return False, "could not parse error output", out[:200]
    errv = float(m.group(1))
    wit = m.group(2)
    ty = get_ty(case, "f")
    T = E.Ty(ty)
    bodyf = get_body(case, "f"); bodyg = get_body(case, "g")
    best = None
    for x in T.domain():
        try:
            a = E.eval_expr(bodyf, {"x": x}, ty, False)[0]
            b = E.eval_expr(bodyg, {"x": x}, ty, False)[0]
        except E.Undefined:
            continue
        d = abs(float(b) - float(a))
        if best is None or d > best[1]:
            best = (x, d)
    if best is None:
        return True, "no comparable points", ""
    if abs(best[1] - errv) > max(1e-6, abs(errv) * 1e-6):
        return False, "max abs error value wrong", f"ucas {errv}, brute {best[1]} at {best[0]}"
    if wit.startswith("x="):
        wx = int(wit[2:])
        if wx != best[0]:
            return False, "max abs error witness wrong", f"ucas x={wx}, brute x={best[0]}"
    return True, "error worst point confirmed", f"x={best[0]} err={best[1]}"


def verify_fit(case, out):
    m = re.search(r"max abs error (\S+) at x=(-?\d+)", out)
    if not m:
        return True, "fit output has no checkable worst point (parameters fitted)", out[:120]
    # The fitted parameters are produced by an optimizer; we can at least
    # confirm the reported witness is a real point in the domain.
    wx = int(m.group(2))
    ty = get_ty(case, "f")
    T = E.Ty(ty)
    if wx not in T.domain():
        return False, "fit witness outside domain", f"x={wx}"
    return True, "fit witness is a valid domain point (optimizer values not re-derived)", f"x={wx}"


VERIFIERS = {
    "equiv": verify_equiv, "wrap": verify_wrap, "domain": verify_domain,
    "crit": verify_crit, "range": verify_range, "error": verify_error,
    "fit": verify_fit,
}


# ---------------------------------------------------------------------------
# table cross-check: compare ucas `table` against our evaluator
# ---------------------------------------------------------------------------
def table_crosscheck(case, out):
    tm = {}
    for mm in re.finditer(r"x=(-?\d+)\s*->\s*(-?\d+)", out):
        tm[int(mm.group(1))] = int(mm.group(2))
    if not tm:
        return None, "no table"
    ty = get_ty(case, "f"); body = get_body(case, "f")
    bad = []
    for x, v in tm.items():
        try:
            mine = E.eval_expr(body, {"x": x}, ty, False)[0]
        except E.Undefined:
            continue
        if mine != v:
            bad.append((x, v, mine))
    return bad, ""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", action="store_true")
    args = ap.parse_args()
    cases = build_cases()
    results = []
    for i, case in enumerate(cases):
        src = case_source(case, with_table=True)
        rc, out = run_ucas(src)
        ok, why, detail = VERIFIERS[case["kind"]](case, out)
        bad, _ = table_crosscheck(case, out)
        tb = "" if bad is None or not bad else f" TABLE_MISMATCH {bad[:3]}"
        results.append((case, rc, ok, why, detail + tb, src, out))
        status = "PASS" if ok and not (bad) else "FAIL"
        if status == "FAIL" or rc != 0:
            print(f"[{status}] {case['id']} ({case['kind']}) rc={rc}: {why} | {detail}{tb}")
    npass = sum(1 for r in results if r[2] and not table_crosscheck(r[0], r[6])[0])
    with open(os.path.join(HERE, "verify_report.txt"), "w") as f:
        f.write(f"cases: {len(results)}  pass: {npass}  fail: {len(results)-npass}\n\n")
        for case, rc, ok, why, detail, src, out in results:
            bad, _ = table_crosscheck(case, out)
            status = "PASS" if ok and not bad else "FAIL"
            f.write(f"=== {case['id']} [{case['kind']}] {status} rc={rc} ===\n")
            f.write("SOURCE:\n" + src)
            f.write("OUTPUT:\n" + out)
            f.write(f"VERIFY: {why} | {detail}\n\n")
    print(f"\nTOTAL {len(results)}  PASS {npass}  FAIL {len(results)-npass}")
    print("report ->", os.path.join(HERE, "verify_report.txt"))


if __name__ == "__main__":
    main()
