"""
Task catalog for second_cas_oracle.

Each task is a dict.  Fields:
  id    : short unique id
  cmd   : the exact ucas CLI command line (no leading '>')
  kind  : extraction/comparison kind (see run_oracle.py)
  src   : SymPy-parsable operand expression (for expr/diff/integrate/modes)
  fn    : for 'special' kind -- name of a sympy function to call on src
  args  : extra positional args for fn
  a,b   : limit/integrate bounds
  roots : for 'solve' kind -- list of SymPy-parsable real roots
  n     : for 'factorint' -- integer to factor
  matrix: for 'det' -- nested list
  tol   : optional numeric comparison tolerance
  note  : optional comment

Oracles are computed with SymPy 1.14 at run time; no ucas mode checks another
ucas mode.  ucas's printed answer is parsed into a SymPy expression and compared
semantically (simplify / expand / numeric fallback), not by string equality.
"""

TASKS = []


def add(**kw):
    TASKS.append(kw)


# ---------------------------------------------------------------------------
# expand  (mode: result must be equivalent to src)
# ---------------------------------------------------------------------------
_EXPANDS = [
    "(x+1)^3", "(x+1)^5", "(x-2)^4", "(2x+3)^3", "(3x-1)^4",
    "(x+y)^3", "(x+y+z)^3", "(x-y)^4", "(x+2)^6", "(x^2+1)^3",
    "(x^2+2x+1)*(x^2-2x+1)", "(x+1)*(x+2)*(x+3)*(x+4)",
    "(2x-3)*(x+4)", "(x-4)*(3x-1)", "(5x+5)*(x^2-2x+6)",
    "(a*x+b)*(c*x+d)", "(x^2+x+1)^2", "(2x^2-3x+1)*(x^2+2)",
    "(x-1)*(x-2)*(x-3)*(x-4)*(x-5)", "(1+x)^10",
    "((x+1)^2 - (x-1)^2)", "(x+y)^2*(x-y)^2", "(3x^2+2x-1)^2",
]
for i, s in enumerate(_EXPANDS):
    add(id=f"E{i:02d}", kind="equiv_src", cmd=f"expand {s}", src=s)

# ---------------------------------------------------------------------------
# factor  (mode: result must be equivalent to src; also check irreducibility)
# ---------------------------------------------------------------------------
_FACTORS = [
    "x^4 - 1", "x^6 - 1", "x^5 + x + 1", "x^4 + 1", "x^3 + y^3",
    "6x^2 - 5x - 6", "4x^2 - 9y^2", "x^2 y + x y^2", "2x^3 + 4x^2 + 2x",
    "x^5 - x", "x^4 - 5x^2 + 4", "x^3 - 3x^2 + 3x - 1",
    "x^7 - x", "2x^4 + x^3 - 8x^2 - x + 6", "x^6 + x^3 + 1",
    "x^2 - 2", "x^4 + 4", "x^9 - 1", "a^2 - b^2",
    "x^5 - 32", "12x^2 + 7x - 10", "x^4 + x^2 + 1",
]
for i, s in enumerate(_FACTORS):
    add(id=f"F{i:02d}", kind="equiv_src", cmd=f"factor {s}", src=s)

# ---------------------------------------------------------------------------
# simplify / together / cancel / apart  (mode: equivalent to src)
# ---------------------------------------------------------------------------
_RAT = [
    ("simplify", "(x^2-1)/(x-1)"),
    ("simplify", "sqrt(x^2)"),
    ("simplify", "sqrt(4x^2+4x+1)"),
    ("simplify", "exp(log(x))"),
    ("simplify", "exp(x)*exp(2x)"),
    ("simplify", "x^2/x^3"),
    ("simplify", "sin(x)^2 + cos(x)^2"),
    ("simplify", "log(x^y)"),
    ("simplify", "(x^3+1)/(x+1)"),
    ("simplify", "abs(x)^2"),
    ("together", "1/x + 1/(x+1)"),
    ("together", "a/b + c/d"),
    ("together", "1/(x-1) + 2/(x+2)"),
    ("together", "x/(x+1) + 1/(x^2-1)"),
    ("cancel", "(x^2 - y^2)/(x - y)"),
    ("cancel", "(2x)/(4x^2)"),
    ("cancel", "(-4x^3 - 2x^2 - 2x + 2)/(6x - 3)"),
    ("cancel", "(x^4-1)/(x^2-1)"),
    ("apart", "1/(x^2-1)"),
    ("apart", "(2x+3)/(x^3-x)"),
    ("apart", "(x^3+1)/(x^2+1)^2"),
    ("apart", "1/(x*(x+1)*(x+2))"),
]
for i, (op, s) in enumerate(_RAT):
    add(id=f"R{i:02d}", kind="equiv_src", cmd=f"{op} {s}", src=s)

# ---------------------------------------------------------------------------
# diff  (oracle = sympy.diff)
# ---------------------------------------------------------------------------
_DIFFS = [
    "x^3 + 2x", "sin(x)*exp(x)", "(x^2+1)^5", "sqrt(x^2+3)",
    "sin(2x) + cos(3x)^2", "log(x)", "exp(x^2)", "x^5 - 3x^2 + 7",
    "tan(x)", "asin(x)", "atan(x)", "x*log(x)", "sin(x)/x",
    "(x^2+1)/(x-1)", "exp(sin(x))", "sqrt(x)", "x^x", "cos(x^3)",
]
for i, s in enumerate(_DIFFS):
    add(id=f"D{i:02d}", kind="diff", cmd=f"diff {s}", src=s)

# ---------------------------------------------------------------------------
# integrate (indefinite; oracle = sympy.integrate)
# ---------------------------------------------------------------------------
_INTS = [
    "x^2", "2x + 1", "sin(x)", "exp(x)", "x^3 - 2x", "cos(x)",
    "1/x", "x*exp(x)", "x*sin(x)", "1/(x^2+1)", "sqrt(x)",
    "x^4 + x^2 + 1", "sin(x)*cos(x)", "1/(1+x)", "x^2*log(x)",
]
for i, s in enumerate(_INTS):
    add(id=f"I{i:02d}", kind="integrate", cmd=f"integrate {s}", src=s)

# ---------------------------------------------------------------------------
# limit  (oracle = sympy.limit)
# ---------------------------------------------------------------------------
_LIMITS = [
    ("sin(x)/x", "0", "both"),
    ("(1-cos(x))/x^2", "0", "both"),
    ("(exp(x)-1)/x", "0", "both"),
    ("log(1+x)/x", "0", "both"),
    ("x^x", "0", "right"),
    ("1/x", "0", "right"),
    ("1/x", "0", "left"),
    ("x^2*log(x)", "0", "right"),
    ("(x^2-1)/(x-1)", "1", "both"),
    ("sin(1/x)", "0", "both"),
    ("(1+1/x)^x", "0", "right"),
    ("(x^3-8)/(x-2)", "2", "both"),
]
for i, (s, a, side) in enumerate(_LIMITS):
    dirarg = {"both": "", "right": "+", "left": "-"}[side]
    add(id=f"L{i:02d}", kind="limit", cmd=f"limit {s} x -> {a}{dirarg}",
        src=s, a=a, side=side)

# ---------------------------------------------------------------------------
# taylor  (oracle = sympy series)
# ---------------------------------------------------------------------------
_TAYLORS = [
    ("sin(x)", 0, 7), ("cos(x)", 0, 6), ("exp(x)", 0, 5),
    ("log(1+x)", 0, 5), ("1/(1-x)", 0, 5), ("(1+x)^5", 0, 5),
    ("atan(x)", 0, 7), ("sqrt(1+x)", 0, 4), ("exp(x)", 1, 3),
]
for i, (s, a, n) in enumerate(_TAYLORS):
    loc = f" at {a}" if a else ""
    add(id=f"T{i:02d}", kind="taylor", cmd=f"taylor {s}{loc} order {n}",
        src=s, a=a, n=n)

# ---------------------------------------------------------------------------
# special polynomial ops
# ---------------------------------------------------------------------------
_SPECIAL = [
    ("E_gcd1", "gcd x^2-1, x^2+2x+1", "gcd", ["x^2-1", "x^2+2*x+1"], {}),
    ("E_gcd2", "gcd x^3-1, x^2-1", "gcd", ["x^3-1", "x^2-1"], {}),
    ("E_gcd3", "gcd 12, 18", "gcd", ["12", "18"], {"compare": "const"}),
    ("E_lcm1", "lcm x^2-1, x^2+2x+1", "lcm", ["x^2-1", "x^2+2*x+1"], {}),
    ("E_lcm2", "lcm x^2-4, x^2-2x", "lcm", ["x^2-4", "x^2-2*x"], {}),
    ("E_res1", "resultant x^2-2, x^2-3x+2", "resultant", ["x^2-2", "x^2-3*x+2"], {}),
    ("E_res2", "resultant x^2+1, x^3-1", "resultant", ["x^2+1", "x^3-1"], {}),
    ("E_dis1", "discriminant a*x^2 + b*x + c", "discriminant", ["a*x**2+b*x+c"], {}),
    ("E_dis2", "discriminant x^3 - 3x + 1", "discriminant", ["x**3-3*x+1"], {}),
    ("E_quo1", "quo x^3 + 1, x + 2", "quo", ["x**3+1", "x+2"], {}),
    ("E_rem1", "rem x^3 + 1, x + 2", "rem", ["x**3+1", "x+2"], {}),
    ("E_quo2", "quo x^4-1, x^2-1", "quo", ["x**4-1", "x**2-1"], {}),
    ("E_rem2", "rem x^4-1, x^2-1", "rem", ["x**4-1", "x**2-1"], {}),
]
for id_, cmd, fn, args, extra in _SPECIAL:
    d = dict(id=id_, kind="special", cmd=cmd, fn=fn, args=args)
    d.update(extra)
    add(**d)

# ---------------------------------------------------------------------------
# solve (single variable, real roots only; complex roots reported by ucas as
# '(and N complex solutions)' and are intentionally not compared)
# ---------------------------------------------------------------------------
_SOLVES = [
    ("x^2 - 5x + 6 = 0", ["2", "3"]),
    ("(x-1)^2 = 0", ["1"]),
    ("x^2 - 4 = 0", ["-2", "2"]),
    ("x^3 - 2 = 0", ["2**(1/3)"]),
    ("x^4 - 10x^2 + 1 = 0", ["sqrt(3)-sqrt(2)", "sqrt(2)-sqrt(3)", "-sqrt(2)-sqrt(3)", "sqrt(2)+sqrt(3)"]),
    ("2^x = 8", ["3"]),
    ("exp(x) = 5", ["log(5)"]),
    ("log(x) = 2", ["exp(2)"]),
    ("sqrt(x+1) = x - 1", ["3"]),
    ("abs(x - 2) = 3", ["-1", "5"]),
    ("x^3 - 3x + 1 = 0", []),  # checked via residual instead
    ("x^4 - 1 = 0", ["-1", "1"]),
    ("sin(x) = 0", []),
]
for i, (eqn, roots) in enumerate(_SOLVES):
    d = dict(id=f"S{i:02d}", kind="solve", cmd=f"solve {eqn}", roots=roots)
    if not roots:
        d["residual_check"] = True
        d["eqn"] = eqn
    add(**d)

# ---------------------------------------------------------------------------
# det (integer matrices)
# ---------------------------------------------------------------------------
_DETS = [
    ("[[1,2],[3,4]]", "-2"),
    ("[[1,2,3],[4,5,6],[7,8,10]]", "-3"),
    ("[[2,0],[0,3]]", "6"),
    ("[[1,0,0],[0,1,0],[0,0,1]]", "1"),
    ("[[5,1,1],[1,5,1],[1,1,5]]", "112"),
    ("[[2,1],[1,2]]", "3"),
    ("[[0,1],[1,0]]", "-1"),
    ("[[3,8],[4,5]]", "-17"),
    ("[[1,2,3],[0,1,4],[5,6,0]]", "1"),
    ("[[6,1],[2,4]]", "22"),
]
for i, (m, v) in enumerate(_DETS):
    add(id=f"X{i:02d}", kind="det", cmd=f"zmat det {m}", matrix=m, det=int(v))

# ---------------------------------------------------------------------------
# factorint (big integers)
# ---------------------------------------------------------------------------
_FACTS = [
    123456789, 3607, 9973, 104729, 1000003, 2147483647,
    8051, 1000000007, 1234567, 999999937, 2**31 - 1,
    12345678901234567, 1000000000039, 561, 1105,
]
for i, n in enumerate(_FACTS):
    add(id=f"N{i:02d}", kind="factorint", cmd=f"factorint {n}", n=n)

# ---------------------------------------------------------------------------
# Batch 2: adversarial -- branch conventions, conditions, tricky limits,
# incomplete integration, bigint primality claims.
# ---------------------------------------------------------------------------
_ADV_SIMPLIFY = [
    "log(x^2)", "log(x*y)", "(x^a)^b", "sqrt(x^4)", "log(exp(x))",
    "log(x) + log(y)", "sqrt(x)*sqrt(x)", "(x^2)^(1/2)",
    "sin(asin(x))", "tan(atan(x))", "exp(log(x^2))", "(x*y)^2",
    "sqrt(x^2 + 2x + 1)", "cos(acos(x))", "asin(sin(x))",
]
for i, s in enumerate(_ADV_SIMPLIFY):
    add(id=f"A{i:02d}", kind="equiv_src", cmd=f"simplify {s}", src=s)

_ADV_LIMITS = [
    ("tan(x)", "pi/2", "right", "-oo"),
    ("tan(x)", "pi/2", "left", "oo"),
    ("atan(1/x)", "0", "right", "pi/2"),
    ("atan(1/x)", "0", "left", "-pi/2"),
    ("log(x)", "0", "right", "-oo"),
    ("(1+x)^(1/x)", "0", "both", "E"),
    ("x*sin(1/x)", "0", "both", "0"),
    ("(x-sin(x))/x^3", "0", "both", "Rational(1,6)"),
    ("(1-cos(x))/x", "0", "both", "0"),
    ("exp(-1/x^2)", "0", "both", "0"),
    ("x^x", "0", "both", "1"),
    ("(x^2-1)/(x-1)", "1", "both", "2"),
    ("sqrt(x)/x", "0", "right", "oo"),
    ("log(1+x)/x", "0", "both", "1"),
]
for i, (s, a, side, val) in enumerate(_ADV_LIMITS):
    dirarg = {"both": "", "right": "+", "left": "-"}[side]
    add(id=f"AL{i:02d}", kind="limit", cmd=f"limit {s} x -> {a}{dirarg}",
        src=s, a=a, side=side, oracle_override=val)

# limits with special oracle override
_SPECIAL_LIMIT_ORACLE = {
    "AL00": "-oo", "AL01": "oo", "AL02": "pi/2", "AL03": "-pi/2",
    "AL04": "-oo", "AL05": "E", "AL06": "0", "AL07": "Rational(1,6)",
    "AL08": "0", "AL09": "0", "AL10": "1", "AL11": "2", "AL12": "oo",
    "AL13": "1",
}

_ADV_DIFF = [
    "sign(x)", "log(abs(x))", "x^(x)", "atan(x^2)", "log(log(x))",
    "(x+1)/(x-1)", "sin(x)^2", "exp(-x^2)", "x^(1/x)",
]
for i, s in enumerate(_ADV_DIFF):
    add(id=f"AD{i:02d}", kind="diff", cmd=f"diff {s}", src=s)

_ADV_INT = [
    "1/sqrt(1-x^2)", "exp(-x^2)", "1/(x^2+4)", "x/(x^2+1)",
    "log(x)^2", "sec(x)^2", "sin(x)^3", "x^2*exp(x)",
]
for i, s in enumerate(_ADV_INT):
    add(id=f"AI{i:02d}", kind="integrate", cmd=f"integrate {s}", src=s)

_ADV_DETS = [
    ("[[2,1,3],[0,1,1],[1,3,0]]", "-4"),
    ("[[1,2,3,4],[2,1,0,0],[0,0,1,2],[1,1,1,1]]", "5"),
    ("[[1,1,1],[1,2,3],[1,4,9]]", "2"),
    ("[[0,0,1],[0,1,0],[1,0,0]]", "-1"),
    ("[[1,0,2],[0,1,0],[3,0,1]]", "-5"),
]
for i, (m, v) in enumerate(_ADV_DETS):
    add(id=f"AX{i:02d}", kind="det", cmd=f"zmat det {m}", matrix=m, det=int(v))

_BIGINTS = [561, 1105, 1729, 2465, 2821, 6601, 8911, 3215031751,
            1373653, 25326001, 2152302898747, 1000000007]
for i, n in enumerate(_BIGINTS):
    add(id=f"AN{i:02d}", kind="factorint", cmd=f"factorint {n}", n=n)

# ---------------------------------------------------------------------------
# Batch 3: definite integrals (numeric oracle), limits at infinity, big dets
# ---------------------------------------------------------------------------
_DEFINITE = [
    ("x^2", "0", "3"), ("sin(x)", "0", "pi"), ("1/x", "1", "2"),
    ("exp(-x^2)", "0", "1"), ("abs(x)", "-1", "1"),
    ("x^3 - 2x", "-1", "2"), ("cos(x)", "0", "pi/2"),
    ("sqrt(x)", "0", "4"), ("1/(1+x^2)", "0", "1"),
    ("x*exp(x)", "0", "1"), ("log(x)", "1", "e"),
    ("sin(x)^2", "0", "pi"), ("exp(x)", "0", "1"),
    ("x^4 + x", "0", "2"),
]
for i, (s, a, b) in enumerate(_DEFINITE):
    add(id=f"DI{i:02d}", kind="definite", cmd=f"integrate {s} from {a} to {b}",
        src=s, a=a, b=b)

_INF_LIMITS = [
    ("(x^2+1)/x", "inf", "oo"),
    ("exp(x)/x^2", "inf", "oo"),
    ("(1+1/x)^x", "inf", "E"),
    ("x^(1/x)", "inf", "1"),
    ("log(x)/x", "inf", "0"),
    ("x - sqrt(x^2+1)", "inf", "0"),
    ("(x+1)/x", "inf", "1"),
    ("sin(x)/x", "inf", "0"),
    ("1/x", "inf", "0"),
    ("x^2*exp(-x)", "inf", "0"),
]
for i, (s, a, val) in enumerate(_INF_LIMITS):
    add(id=f"IF{i:02d}", kind="limit", cmd=f"limit {s} x -> {a}",
        src=s, a=a, side="both", oracle_override=val)

_BIG_DETS = [
    ("[[2,1,3,0],[0,1,1,2],[1,3,0,1],[4,0,2,1]]", "-24"),
    ("[[1,2,3,4],[5,6,7,8],[9,10,11,12],[13,14,15,17]]", "-4"),
    ("[[3,1,4,1,5],[9,2,6,5,3],[5,8,9,7,9],[3,2,3,8,4],[6,2,6,4,3]]", "0"),
]
for i, (m, v) in enumerate(_BIG_DETS):
    add(id=f"BX{i:02d}", kind="det", cmd=f"zmat det {m}", matrix=m, det=int(v))
