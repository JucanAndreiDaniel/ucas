"""Bit-accurate Python evaluator for the small ucas expression subset used by
the witness-verification stress tests.

Supported syntax (ucas):
  numbers, variables, parentheses
  unary:  - ~ +
  binary: * / %   + -   << >>   &   xor   |   < <= > >= == !=
  ternary: c ? a : b

Type model: unsigned uN wraps mod 2**N; signed iN wraps two's complement
into [-2**(N-1), 2**(N-1)-1].  Division truncates toward zero (C style),
modulo has the sign of the dividend, right shift is logical for unsigned and
arithmetic for signed.  Division/modulo by zero raises Undefined.
"""

import re


class Undefined(Exception):
    pass


TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<num>\d+)"
    r"|(?P<var>[A-Za-z_][A-Za-z_0-9]*)"
    r"|(?P<op><<|>>|<=|>=|==|!=|[-+*/%&|~<>()?:])"
    r")"
)


def tokenize(s):
    toks = []
    i = 0
    while i < len(s):
        m = TOKEN_RE.match(s, i)
        if not m:
            # skip whitespace only
            if s[i:].strip() == "":
                break
            raise ValueError("cannot tokenize %r at %d" % (s, i))
        i = m.end()
        g = m.group(m.lastgroup)
        if m.lastgroup == "num":
            toks.append(("num", int(g)))
        elif m.lastgroup == "var":
            toks.append(("op", "xor") if g == "xor" else ("var", g))
        else:
            toks.append(("op", g))
    toks.append(("eof", None))
    return toks


# Recursive descent, C-like precedence (lowest first).
class Parser:
    def __init__(self, s):
        self.toks = tokenize(s)
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, val):
        if self.peek()[1] == val:
            self.i += 1
            return True
        return False

    def parse(self):
        e = self.ternary()
        if self.peek()[0] != "eof":
            raise ValueError("trailing tokens near %r" % (self.peek(),))
        return e

    def ternary(self):
        c = self.or_(...)
        if self.accept("?"):
            a = self.ternary()
            if not self.accept(":"):
                raise ValueError("expected : in ternary")
            b = self.ternary()
            return ("?", c, a, b)
        return c

    def or_(self, _=None):
        e = self.xor_(...)
        while self.accept("|"):
            e = ("|", e, self.xor_(...))
        return e

    def xor_(self, _=None):
        e = self.and_(...)
        while self.peek()[1] == "xor":
            self.take()
            e = ("xor", e, self.and_(...))
        return e

    def and_(self, _=None):
        e = self.eq(...)
        while self.accept("&"):
            e = ("&", e, self.eq(...))
        return e

    def eq(self, _=None):
        e = self.rel(...)
        while self.peek()[1] in ("==", "!="):
            op = self.take()[1]
            e = (op, e, self.rel(...))
        return e

    def rel(self, _=None):
        e = self.shift(...)
        while self.peek()[1] in ("<", "<=", ">", ">="):
            op = self.take()[1]
            e = (op, e, self.shift(...))
        return e

    def shift(self, _=None):
        e = self.add(...)
        while self.peek()[1] in ("<<", ">>"):
            op = self.take()[1]
            e = (op, e, self.add(...))
        return e

    def add(self, _=None):
        e = self.mul(...)
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            e = (op, e, self.mul(...))
        return e

    def mul(self, _=None):
        e = self.unary(...)
        while self.peek()[1] in ("*", "/", "%"):
            op = self.take()[1]
            e = (op, e, self.unary(...))
        return e

    def unary(self, _=None):
        if self.peek()[1] in ("-", "~", "+"):
            op = self.take()[1]
            return (("neg" if op == "-" else op), self.unary(...))
        return self.primary(...)

    def primary(self, _=None):
        k, v = self.peek()
        if k == "num":
            self.take()
            return ("num", v)
        if k == "var":
            self.take()
            return ("var", v)
        if v == "(":
            self.take()
            e = self.ternary()
            if not self.accept(")"):
                raise ValueError("expected )")
            return e
        raise ValueError("unexpected token %r" % (self.peek(),))


def parse(s):
    return Parser(s).parse()


class Ty:
    def __init__(self, spec):
        m = re.fullmatch(r"([ui])(\d+)", spec)
        if not m:
            raise ValueError("bad type %r" % spec)
        self.signed = m.group(1) == "i"
        self.n = int(m.group(2))
        self.mod = 1 << self.n
        self.slo = -(1 << (self.n - 1))
        self.shi = (1 << (self.n - 1)) - 1
        if self.signed:
            self.lo = self.slo
            self.hi = self.shi
        else:
            self.lo = 0
            self.hi = self.mod - 1
        self.spec = spec

    def wrap(self, v):
        v &= self.mod - 1
        if self.signed and v >= (1 << (self.n - 1)):
            v -= self.mod
        return v

    def bits(self, v):
        return v & (self.mod - 1)

    def contains(self, v):
        return self.lo <= v <= self.hi

    def domain(self):
        return range(self.lo, self.hi + 1)


def cdiv(a, b):
    """Truncate toward zero."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def cmod(a, b):
    return a - cdiv(a, b) * b


def is_unary(node):
    return node[0] in ("neg", "~") or (node[0] == "+" and len(node) == 2)


def is_const(node):
    op = node[0]
    if op == "num":
        return True
    if op == "var":
        return False
    if op == "?":
        return is_const(node[1]) and is_const(node[2]) and is_const(node[3])
    if is_unary(node):
        return is_const(node[1])
    return is_const(node[1]) and is_const(node[2])


def _bin(op, a, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise Undefined("division by zero")
        return cdiv(a, b)
    if op == "%":
        if b == 0:
            raise Undefined("mod by zero")
        return cmod(a, b)
    if op == "<<":
        if b < 0:
            raise Undefined("negative shift")
        return a << b
    if op == ">>":
        if b < 0:
            raise Undefined("negative shift")
        return a >> b
    if op == "&":
        return a & b
    if op == "|":
        return a | b
    if op == "xor":
        return a ^ b
    if op in ("<", "<=", ">", ">=", "==", "!="):
        return int({"<": a < b, "<=": a <= b, ">": a > b,
                    ">=": a >= b, "==": a == b, "!=": a != b}[op])
    raise ValueError("unknown binary op %r" % op)


def _unary(op, a):
    if op == "neg":
        return -a
    if op == "~":
        return ~a
    return a  # '+'


def math_eval(node):
    """Unbounded mathematical evaluation (constant folding, no wrapping)."""
    op = node[0]
    if op == "num":
        return node[1]
    if op == "var":
        raise ValueError("math_eval needs a constant tree")
    if op == "?":
        return math_eval(node[2] if math_eval(node[1]) else node[3])
    if is_unary(node):
        return _unary(op, math_eval(node[1]))
    return _bin(op, math_eval(node[1]), math_eval(node[2]))


def _eval(node, env, ty, mathmode=False):
    """Evaluate AST node under ucas machine semantics.

    Returns (value, unsigned_overflow, signed_overflow).
      mathmode=True: unbounded mathematical result (for wrap / end-to-end).
      mathmode=False: machine value with per-operation wrapping; pure-constant
                      subtrees are folded unbounded and wrapped when used as an
                      operand of a typed (non-constant) operation.
    """
    op = node[0]
    if mathmode and is_const(node):
        # ucas coerces literal / constant subtrees into the type even for the
        # mathematical end-to-end result (e.g. ~1 becomes 254 in u8).
        return ty.wrap(math_eval(node)), False, False
    if op == "num":
        return node[1], False, False
    if op == "var":
        return env[node[1]], False, False

    if mathmode:
        if op == "?":
            c = math_eval(node[1]) if is_const(node[1]) else _eval(node[1], env, ty, True)[0]
            return _eval(node[2] if c else node[3], env, ty, True)
        if is_unary(node):
            a = _eval(node[1], env, ty, True)[0]
            return _unary(op, a), False, False
        a = _eval(node[1], env, ty, True)[0]
        b = _eval(node[2], env, ty, True)[0]
        v = _bin(op, a, b)
        if op in ("<", "<=", ">", ">=", "==", "!="):
            return v, False, False
        uov = not (0 <= v <= ty.mod - 1)
        sov = not (ty.slo <= v <= ty.shi)
        return v, uov, sov

    # non-mathmode (machine value)
    if is_const(node):
        # ucas folds constant subtrees in unbounded arithmetic; the final
        # value is NOT wrapped until it is used as a typed operand.
        return math_eval(node), False, False

    if op == "?":
        c = _eval(node[1], env, ty, False)[0]
        chosen = node[2] if c else node[3]
        v = _eval(chosen, env, ty, False)[0]
        return ty.wrap(v), False, False

    if is_unary(node):
        a = _eval(node[1], env, ty, False)[0]
        if is_const(node[1]):
            a = ty.wrap(a)
        v = _unary(op, a)
        res = ty.wrap(v)
        uov = not (0 <= v <= ty.mod - 1)
        sov = not (ty.slo <= v <= ty.shi)
        return res, uov, sov

    a = _eval(node[1], env, ty, False)[0]
    b = _eval(node[2], env, ty, False)[0]
    if is_const(node[1]):
        a = ty.wrap(a)
    if is_const(node[2]):
        b = ty.wrap(b)
    v = _bin(op, a, b)
    if op in ("<", "<=", ">", ">=", "==", "!="):
        return int(bool(v)), False, False
    res = ty.wrap(v)
    if op in ("&", "|", "xor", "<<", ">>"):
        return res, False, False
    uov = not (0 <= v <= ty.mod - 1)
    sov = not (ty.slo <= v <= ty.shi)
    return res, uov, sov


def eval_expr(s, env, ty_spec, mathmode=False):
    """Return (value, unsigned_overflow_flag, signed_overflow_flag)."""
    ty = Ty(ty_spec)
    node = parse(s) if isinstance(s, str) else s
    return _eval(node, env, ty, mathmode)


def value(s, env, ty_spec, mathmode=False):
    return eval_expr(s, env, ty_spec, mathmode)[0]


def eval_all(s, ty_spec):
    """Return dict domainvalue->(result, uov, sov) and mathresult dict."""
    ty = Ty(ty_spec)
    node = parse(s)
    out = {}
    for x in ty.domain():
        out[x] = _eval(node, {"x": x}, ty, False)
    return out
