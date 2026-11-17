"""
oraclelib.py -- independent oracle helpers for external_oracle_diff.

No third-party CAS.  Exact arithmetic uses Python fractions.Fraction;
numeric evaluation uses float / math / decimal.  This module parses the
*output expressions* printed by the ucas CLI and provides an independent
semantic evaluator, plus a small exact polynomial/rational engine used to
construct ground truth for expand/factor/cancel checks.
"""
import re
import math
from fractions import Fraction

# ---------------------------------------------------------------------------
# Tokenizer / implicit-multiplication insertion
# ---------------------------------------------------------------------------

_FUNCS = {
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh",
    "tanh", "asinh", "acosh", "atanh", "sqrt", "cbrt", "exp", "log", "ln",
    "abs", "sign", "floor", "ceil", "round", "min", "max", "gcd", "re",
    "im", "conj", "mod", "isqrt",
}
_CONST = {"pi", "e", "C", "i", "tau", "phi", "inf", "nan"}


def _insert_implicit(s):
    """Insert '*' for implicit multiplication in ucas-style output."""
    toks = re.findall(r"\d+\.?\d*(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[()+\-*/^,]|\S", s)
    out = []
    n = len(toks)

    def starts_atom(t):
        return bool(re.match(r"^\d", t)) or bool(re.match(r"^[A-Za-z_(]", t))

    def ends_atom(t):
        return bool(re.match(r"^[\dA-Za-z_)]", t))

    for idx, t in enumerate(toks):
        if out:
            prev = out[-1]
            need = False
            # number/close-paren/ident  followed by  ident / open-paren
            if starts_atom(t) and ends_atom(prev):
                # identifier followed by '(' -> function call if known func
                if re.match(r"^[A-Za-z_]\w*$", prev) and t == "(":
                    if prev not in _FUNCS:
                        need = True
                elif re.match(r"^[A-Za-z_]\w*$", t) and re.match(r"^[A-Za-z_]\w*$", prev):
                    # two identifiers adjacent (rare); treat as multiply
                    need = True
                else:
                    need = True
            # ')' followed by number/ident/'('
            if prev == ")" and starts_atom(t):
                need = True
            if need:
                out.append("*")
        out.append(t)
    return " ".join(out)


class AST:
    __slots__ = ("k", "a", "b", "c")

    def __init__(self, k, a=None, b=None, c=None):
        self.k, self.a, self.b, self.c = k, a, b, c

    def __repr__(self):
        return f"AST({self.k},{self.a!r},{self.b!r},{self.c!r})"


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, s):
        s2 = _insert_implicit(s)
        self.toks = re.findall(r"\d+\.?\d*(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[()+\-*/^,]|\S", s2)
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def parse(self):
        e = self.expr()
        if self.peek() is not None:
            raise ParseError("trailing tokens: " + " ".join(self.toks[self.i:]))
        return e

    def expr(self):
        node = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.term()
            node = AST(op, node, rhs)
        return node

    def term(self):
        node = self.unary()
        while self.peek() in ("*", "/"):
            op = self.take()
            rhs = self.unary()
            node = AST(op, node, rhs)
        return node

    def unary(self):
        if self.peek() == "-":
            self.take()
            return AST("neg", self.unary())
        if self.peek() == "+":
            self.take()
            return self.unary()
        return self.power()

    def power(self):
        node = self.atom()
        if self.peek() == "^":
            self.take()
            node = AST("^", node, self.unary())  # right associative
        return node

    def atom(self):
        t = self.take()
        if t is None:
            raise ParseError("unexpected end")
        if t == "(":
            e = self.expr()
            if self.peek() != ")":
                raise ParseError("expected ')' got " + str(self.peek()))
            self.take()
            return e
        if re.match(r"^\d", t):
            if "." in t or "e" in t.lower():
                return AST("num", Fraction(t))
            return AST("num", Fraction(int(t)))
        if re.match(r"^[A-Za-z_]", t):
            if self.peek() == "(":
                self.take()
                args = []
                if self.peek() != ")":
                    args.append(self.expr())
                    while self.peek() == ",":
                        self.take()
                        args.append(self.expr())
                if self.peek() != ")":
                    raise ParseError("expected ')' in call " + t)
                self.take()
                return AST("call", t, args)
            return AST("var", t)
        raise ParseError("bad token " + t)


def parse(s):
    return Parser(s).parse()


# ---------------------------------------------------------------------------
# Numeric evaluation (float, with math functions)
# ---------------------------------------------------------------------------

def evals(node, env):
    k = node.k
    if k == "num":
        return float(node.a)
    if k == "var":
        if node.a in env:
            return env[node.a]
        if node.a == "pi":
            return math.pi
        if node.a in ("e",):
            return math.e
        if node.a == "C":
            return 0.0
        if node.a == "i":
            return complex(0, 1)
        raise KeyError("unknown var " + node.a)
    if k == "neg":
        return -evals(node.a, env)
    if k in ("+", "-", "*", "/", "^"):
        a = evals(node.a, env)
        b = evals(node.b, env)
        if k == "+":
            return a + b
        if k == "-":
            return a - b
        if k == "*":
            return a * b
        if k == "/":
            return a / b
        if k == "^":
            return a ** b
    if k == "call":
        fname = node.a
        args = [evals(x, env) for x in node.b]
        fn = {
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "asin": math.asin, "acos": math.acos, "atan": math.atan,
            "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
            "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
            "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
            "exp": math.exp, "log": math.log, "ln": math.log,
            "abs": abs, "sign": lambda x: (x > 0) - (x < 0),
            "floor": math.floor, "ceil": math.ceil, "round": round,
            "atan2": math.atan2,
        }.get(fname)
        if fn is None:
            raise KeyError("unknown function " + fname)
        return fn(*args)
    raise KeyError("unknown node " + k)


# ---------------------------------------------------------------------------
# Exact polynomial engine (univariate in one named variable), Fraction coeffs.
# Poly = dict {exponent:int -> coeff:Fraction}
# ---------------------------------------------------------------------------

def _ptrim(p):
    return {e: c for e, c in p.items() if c != 0}


def padd(a, b):
    r = dict(a)
    for e, c in b.items():
        r[e] = r.get(e, 0) + c
    return _ptrim(r)


def pneg(a):
    return {e: -c for e, c in a.items()}


def pmul(a, b):
    r = {}
    for ea, ca in a.items():
        for eb, cb in b.items():
            e = ea + eb
            r[e] = r.get(e, 0) + ca * cb
    return _ptrim(r)


def ppow(a, n):
    if n < 0:
        raise ValueError("negative power in polynomial")
    r = {0: Fraction(1)}
    base = a
    while n:
        if n & 1:
            r = pmul(r, base)
        base = pmul(base, base)
        n >>= 1
    return r


def peval(p, x):
    s = Fraction(0)
    for e, c in p.items():
        s += c * (x ** e)
    return s


def ast_to_poly(node, var="x"):
    """Convert an AST to a polynomial (dict exp->Fraction) or raise if not poly."""
    k = node.k
    if k == "num":
        return {0: Fraction(node.a)}
    if k == "var":
        if node.a == var:
            return {1: Fraction(1)}
        if node.a in _CONST:
            raise ValueError("const atom in poly")
        # treat other variables as separate atom -> cannot do univariate
        raise ValueError("foreign var " + node.a)
    if k == "neg":
        return pneg(ast_to_poly(node.a, var))
    if k in ("+", "-"):
        a = ast_to_poly(node.a, var)
        b = ast_to_poly(node.b, var)
        return padd(a, b) if k == "+" else padd(a, pneg(b))
    if k == "*":
        return pmul(ast_to_poly(node.a, var), ast_to_poly(node.b, var))
    if k == "^":
        base = ast_to_poly(node.a, var)
        expn = ast_to_poly(node.b, var)
        if set(expn.keys()) != {0}:
            raise ValueError("non-const exponent")
        n = expn[0]
        if n.denominator != 1:
            raise ValueError("fractional exponent")
        return ppow(base, int(n))
    if k == "/":
        # allow division by an integer constant only
        den = ast_to_poly(node.b, var)
        if set(den.keys()) == {0} and den[0] != 0:
            inv = Fraction(1, 1) / den[0]
            return {e: c * inv for e, c in ast_to_poly(node.a, var).items()}
        raise ValueError("non-constant denominator")
    raise ValueError("node " + k)


def poly_to_str(p, var="x"):
    terms = []
    for e in sorted(p.keys(), reverse=True):
        c = p[e]
        if c == 0:
            continue
        sign = "-" if c < 0 else "+"
        ac = abs(c)
        if e == 0:
            body = str(ac)
        elif e == 1:
            body = ("" if ac == 1 else f"{ac}") + var
        else:
            body = ("" if ac == 1 else f"{ac}") + f"{var}^{e}"
        terms.append((sign, body))
    if not terms:
        return "0"
    s = ("-" if terms[0][0] == "-" else "") + terms[0][1]
    for sign, body in terms[1:]:
        s += f" {sign} {body}"
    return s


def poly_from_coeffs(coeffs):
    return {e: Fraction(c) for e, c in enumerate(coeffs) if c != 0}


# ---------------------------------------------------------------------------
# Output extraction helpers
# ---------------------------------------------------------------------------

def extract_equals(text):
    """Return the RHS expression of the first `  = EXPR` line."""
    for line in text.splitlines():
        m = re.match(r"\s*=\s*(.*?)\s*$", line)
        if m:
            return m.group(1)
    return None


def extract_after_colon(text, key):
    """For lines like 'from 0 to 3: F(3) - F(0) = 9' return '9'."""
    for line in text.splitlines():
        if key in line and "=" in line:
            return line.split("=", 1)[1].strip()
    return None


def parse_range(text):
    """Parse `range of f ... :\\n  min..max (N distinct values)`."""
    m = re.search(r"(-?\d+)\.\.(-?\d+)\s*\((\d+)\s+distinct", text)
    if not m:
        m = re.search(r"^\s*(-?\d+)\.\.(-?\d+)", text, re.M)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_table(text):
    """Parse `  x=0  ->  1` lines into dict."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*([A-Za-z_]\w*)=(-?\d+)\s*->\s*(-?\d+)\s*$", line)
        if m:
            out[int(m.group(2))] = int(m.group(3))
    return out


# ---------------------------------------------------------------------------
# Polynomial gcd, rational-function reduction, symbolic differentiation
# ---------------------------------------------------------------------------

def pdegree(p):
    return max(p.keys()) if p else -1


def pdivmod(a, b):
    """Polynomial division a = q*b + r over Q."""
    a = dict(a)
    b = _ptrim(b)
    if not b:
        raise ZeroDivisionError
    q = {}
    db = pdegree(b)
    lb = b[db]
    while a and pdegree(a) >= db:
        da = pdegree(a)
        la = a[da]
        e = da - db
        coeff = la / lb
        q[e] = q.get(e, 0) + coeff
        for eb, cb in b.items():
            a[e + eb] = a.get(e + eb, 0) - coeff * cb
            if a[e + eb] == 0:
                del a[e + eb]
    return _ptrim(q), _ptrim(a)


def pgcd(a, b):
    a, b = dict(a), dict(b)
    while b:
        _, r = pdivmod(a, b)
        a, b = b, r
    if not a:
        return {}
    # make monic
    lc = a[pdegree(a)]
    return {e: c / lc for e, c in a.items()}


def rat_reduce(num, den):
    """Return reduced (num, den) polynomials, monic denom."""
    num, den = dict(num), dict(den)
    if not den:
        raise ZeroDivisionError
    g = pgcd(num, den)
    n, _ = pdivmod(num, g)
    d, _ = pdivmod(den, g)
    lc = d[pdegree(d)]
    return {e: c / lc for e, c in n.items()}, {e: c / lc for e, c in d.items()}


def ast_ratfun(node, var="x"):
    """Convert AST to (num, den) polynomials (no functions)."""
    k = node.k
    if k in ("num", "var", "neg", "+", "-", "*", "^"):
        return ast_to_poly(node, var), {0: Fraction(1)}
    if k == "/":
        n, d = ast_ratfun(node.a, var)
        dn, dd = ast_ratfun(node.b, var)
        return pmul(n, dd), pmul(d, dn)
    raise ValueError("ast_ratfun cannot handle " + k)


def ast_diff(node, var="x"):
    """Symbolic derivative of an AST w.r.t. var (subset of calculus)."""
    k = node.k
    if k == "num":
        return AST("num", Fraction(0))
    if k == "var":
        return AST("num", Fraction(1 if node.a == var else 0))
    if k == "neg":
        return AST("neg", ast_diff(node.a, var))
    if k == "+":
        return AST("+", ast_diff(node.a, var), ast_diff(node.b, var))
    if k == "-":
        return AST("-", ast_diff(node.a, var), ast_diff(node.b, var))
    if k == "*":
        u, v = node.a, node.b
        # product rule
        return AST("+", AST("*", ast_diff(u, var), v), AST("*", u, ast_diff(v, var)))
    if k == "/":
        u, v = node.a, node.b
        num = AST("-", AST("*", ast_diff(u, var), v), AST("*", u, ast_diff(v, var)))
        return AST("/", num, AST("^", v, AST("num", Fraction(2))))
    if k == "^":
        u, v = node.a, node.b
        # generic: u^v * (v' ln u + v u'/u); handle constant exponent simply
        try:
            p = ast_to_poly(v, var)
            if set(p.keys()) == {0}:
                n = int(p[0])
                return AST("*", AST("*", AST("num", Fraction(n)), AST("^", u, AST("num", Fraction(n - 1)))), ast_diff(u, var))
        except Exception:
            pass
        raise ValueError("ast_diff generic power unsupported")
    if k == "call":
        f, args = node.a, node.b
        x = args[0]
        dx = ast_diff(x, var)
        table = {
            "sin": "cos", "cos": lambda: AST("neg", AST("call", "sin", [x])),
            "exp": "exp", "sqrt": None, "log": None,
        }
        if f == "sin":
            return AST("*", AST("call", "cos", [x]), dx)
        if f == "cos":
            return AST("*", AST("neg", AST("call", "sin", [x])), dx)
        if f == "exp":
            return AST("*", AST("call", "exp", [x]), dx)
        if f == "log":
            return AST("/", dx, x)
        if f == "sqrt":
            return AST("/", dx, AST("*", AST("num", Fraction(2)), AST("call", "sqrt", [x])))
        raise ValueError("ast_diff function " + f)
    raise ValueError("ast_diff node " + k)


def poly_antideriv(p, var="x"):
    """Exact antiderivative polynomial (no constant)."""
    r = {}
    for e, c in p.items():
        r[e + 1] = c / Fraction(e + 1)
    return _ptrim(r)
