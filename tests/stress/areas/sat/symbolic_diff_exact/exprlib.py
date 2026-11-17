"""Independent exact-arithmetic expression library for the symbolic-diff oracle.

No dependency on ucas.  Expressions are rational functions over Q in a handful
of named variables.  They can be:

  * evaluated exactly at rational points with fractions.Fraction (the oracle),
  * rendered to ucas syntax,
  * structurally renamed / shifted (verified shape reduction).

This is deliberately a *different* oracle from ucas's `equiv` (which uses SAT on
machine types or numeric sampling on `real`).
"""

from __future__ import annotations

from fractions import Fraction


class Undefined(Exception):
    """Raised when an expression has no value at a rational point (e.g. /0)."""


class Expr:
    __slots__ = ("op", "a", "b", "val")

    def __init__(self, op, a=None, b=None, val=None):
        self.op = op      # 'num','var','+','-','*','/','neg','^'
        self.a = a
        self.b = b
        self.val = val

    # ---- constructors -------------------------------------------------
    @staticmethod
    def num(v):
        return Expr("num", val=Fraction(v))

    @staticmethod
    def var(name):
        return Expr("var", val=name)

    # ---- operator overloading ----------------------------------------
    def __add__(self, other):
        return Expr("+", self, _coerce(other))

    def __radd__(self, other):
        return Expr("+", _coerce(other), self)

    def __sub__(self, other):
        return Expr("-", self, _coerce(other))

    def __rsub__(self, other):
        return Expr("-", _coerce(other), self)

    def __mul__(self, other):
        return Expr("*", self, _coerce(other))

    def __rmul__(self, other):
        return Expr("*", _coerce(other), self)

    def __truediv__(self, other):
        return Expr("/", self, _coerce(other))

    def __rtruediv__(self, other):
        return Expr("/", _coerce(other), self)

    def __pow__(self, other):
        e = _coerce(other)
        if e.op != "num" or e.val.denominator != 1:
            raise ValueError("only integer exponents supported")
        return Expr("^", self, e)

    def __neg__(self):
        return Expr("neg", self)

    # ---- exact evaluation --------------------------------------------
    def eval(self, env):
        op = self.op
        if op == "num":
            return self.val
        if op == "var":
            if self.val not in env:
                raise KeyError(self.val)
            return env[self.val]
        a = self.a.eval(env)
        if op == "neg":
            return -a
        b = self.b.eval(env)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise Undefined("division by zero")
            return a / b
        if op == "^":
            n = int(self.b.val)
            if n == 0:
                return Fraction(1)
            if n < 0:
                if a == 0:
                    raise Undefined("zero to a negative power")
                return Fraction(1) / (a ** (-n))
            return a ** n
        raise ValueError("bad op " + op)

    # ---- structural transforms ---------------------------------------
    def vars(self):
        out = set()

        def walk(e):
            if e.op == "var":
                out.add(e.val)
            elif e.op not in ("num",):
                walk(e.a)
                if e.b is not None:
                    walk(e.b)
        walk(self)
        return out

    def rename(self, mapping):
        """Return a copy with variable names replaced per `mapping`."""
        if self.op == "var":
            return Expr.var(mapping.get(self.val, self.val))
        if self.op == "num":
            return Expr.num(self.val)
        if self.op == "neg":
            return Expr("neg", self.a.rename(mapping))
        return Expr(self.op, self.a.rename(mapping), self.b.rename(mapping))

    def subst(self, var, replacement):
        """Return a copy with `var` replaced by `replacement` (an Expr)."""
        if self.op == "var":
            return replacement if self.val == var else self
        if self.op == "num":
            return self
        if self.op == "neg":
            return Expr("neg", self.a.subst(var, replacement))
        return Expr(self.op, self.a.subst(var, replacement),
                    self.b.subst(var, replacement))

    # ---- rendering ----------------------------------------------------
    def render(self, pow_as_mul=False):
        return self._render(pow_as_mul)

    def _render(self, pam, parent_prec=0):
        op = self.op
        if op == "num":
            f = self.val
            if f.denominator == 1:
                return str(f.numerator)
            return "(%d/%d)" % (f.numerator, f.denominator)
        if op == "var":
            return self.val
        if op == "neg":
            s = "-" + self.a._render(pam, 3)
            return "(" + s + ")" if parent_prec > 3 else s
        prec = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 4}[op]
        if op == "^" and self.b.val.denominator == 1:
            n = int(self.b.val)
            if n == 0:
                return "1"
            if n == 1:
                return self.a._render(pam, parent_prec)
            if pam and 2 <= n <= 12:
                atom = "(" + self.a._render(pam, 4) + ")"
                s = "*".join([atom] * n)
                return "(" + s + ")" if parent_prec > 2 else s
        # Drop trivial multiplicative identities in rendering only.
        if op in ("*", "/") and self.b.op == "num":
            if op == "*" and self.b.val == 1:
                return self.a._render(pam, parent_prec)
            if op == "*" and self.b.val == 0:
                return "0"
            if op == "/" and self.b.val == 1:
                return self.a._render(pam, parent_prec)
        if op == "*" and self.a.op == "num" and self.a.val == 1:
            return self.b._render(pam, parent_prec)
        if op == "*" and self.a.op == "num" and self.a.val == -1:
            inner = self.b._render(pam, 3)
            s = "-" + inner
            return "(" + s + ")" if parent_prec > 3 else s
        left = self.a._render(pam, prec)
        right = self.b._render(pam, prec + 1)
        s = left + " " + op + " " + right
        return "(" + s + ")" if parent_prec > prec else s

    def __repr__(self):
        return "Expr(%s)" % self.render()


def _coerce(v):
    if isinstance(v, Expr):
        return v
    return Expr.num(v)


def X(name="x"):
    return Expr.var(name)


def diff(a, b):
    """Symbolic difference as an AST (not evaluated)."""
    return a - b
