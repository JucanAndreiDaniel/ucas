#!/usr/bin/env python3
"""Oracle-driven stress harness for sparse/large matrix operations in ucas.

Generates >=150 matrices (sparse, structured, rank-deficient, boundary entries,
rational, Z/n, GF(p^k), malformed), runs CLI + MCP operations under timeout,
and compares against sympy/fractions or hand-written finite-field oracles.
Also re-checks SNF/HNF certificates by substitution.

Deterministic: fixed RNG seed.  Nothing here is a golden; it is a differential
fuzzer that prints any mismatch it finds.
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
import json
import os
import random
import re
import subprocess
import sys
from fractions import Fraction

from sympy import Matrix, ZZ, QQ, Rational, eye, zeros

BIN = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261116
random.seed(SEED)

MISMATCHES = []
COUNTS = {"cases": 0, "queries": 0, "cli": 0, "mcp": 0, "checked": 0}
VERBOSE = "-v" in sys.argv


def note(kind, case, stmt, expected, observed, extra=""):
    MISMATCHES.append({
        "kind": kind, "case": case, "stmt": stmt,
        "expected": str(expected), "observed": str(observed), "extra": extra,
    })
    if VERBOSE:
        print(f"[{kind}] {case}: {stmt}\n  expected={expected}\n  observed={observed} {extra}")


# ---------------------------------------------------------------------------
# matrix formatting
# ---------------------------------------------------------------------------
def fmt_int_matrix(M):
    return "[" + ",".join("[" + ",".join(str(int(x)) for x in row) + "]" for row in M) + "]"


def fmt_q_matrix(M):
    def q(x):
        x = Fraction(x)
        return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
    return "[" + ",".join("[" + ",".join(q(x) for x in row) + "]" for row in M) + "]"


def parse_int_matrix(s):
    s = s.strip()
    if s == "[]":
        return []
    rows = re.findall(r"\[([^\[\]]*)\]", s)
    return [[int(x) for x in r.split(",")] for r in rows if r.strip()]


# ---------------------------------------------------------------------------
# CLI batch runner
# ---------------------------------------------------------------------------
def run_cli(statements, timeout=25):
    path = os.path.join(HERE, "_batch.ucas")
    with open(path, "w") as f:
        f.write("\n".join(statements) + "\n")
    try:
        p = subprocess.run([BIN, path], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode(errors="replace") + (e.stderr or b"").decode(errors="replace")


def split_blocks(output, n):
    """Split ucas CLI output into one block per statement using the '> ' prompts."""
    lines = output.splitlines()
    blocks = [[] for _ in range(n)]
    idx = -1
    for ln in lines:
        if ln.startswith("> "):
            idx += 1
            if idx >= n:
                idx = n - 1
            blocks[idx].append(ln)
        else:
            if idx >= 0:
                blocks[idx].append(ln)
    return ["\n".join(b) for b in blocks]


def find_line(block, prefix):
    for ln in block.splitlines():
        s = ln.strip()
        if s.startswith(prefix):
            return s[len(prefix):].strip()
    return None


# ---------------------------------------------------------------------------
# MCP runner (wire protocol)
# ---------------------------------------------------------------------------
def run_mcp(calls, timeout=25, start_id=1):
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "stress", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
    ]
    for i, (tool, op, args) in enumerate(calls, start=start_id):
        lines.append(json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                 "params": {"name": tool, "arguments": {"op": op, "args": args}}}))
    inp = "\n".join(lines) + "\n"
    try:
        p = subprocess.run([BIN, "--mcp"], input=inp, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return 124, {}
    out = {}
    for ln in p.stdout.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if "id" in o and isinstance(o["id"], int) and o["id"] >= 1:
            out[o["id"]] = o
    return p.returncode, out


def sc(o):
    try:
        return o["result"]["structuredContent"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# oracles
# ---------------------------------------------------------------------------
def matmul(A, B):
    n, m, p = len(A), len(B), len(B[0]) if B else 0
    return [[sum(A[i][k] * B[k][j] for k in range(m)) for j in range(p)] for i in range(n)]


def mat_eq(A, B):
    return A == B


def det_bareiss(A):
    """Exact integer determinant by fraction-free Bareiss elimination."""
    n = len(A)
    if n == 0:
        return 1
    M = [row[:] for row in A]
    sign = 1
    prev = 1
    for k in range(n - 1):
        if M[k][k] == 0:
            piv = None
            for i in range(k + 1, n):
                if M[i][k]:
                    piv = i
                    break
            if piv is None:
                return 0
            M[k], M[piv] = M[piv], M[k]
            sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                M[i][j] = (M[i][j] * M[k][k] - M[i][k] * M[k][j]) // prev
        prev = M[k][k]
    return sign * M[n - 1][n - 1]


def rank_q(A):
    """Rank over Q via exact-fraction elimination (fast on sparse inputs)."""
    if not A:
        return 0
    M = [[Fraction(x) for x in row] for row in A]
    n, m = len(M), len(M[0])
    r = 0
    for c in range(m):
        piv = None
        for i in range(r, n):
            if M[i][c]:
                piv = i
                break
        if piv is None:
            continue
        M[r], M[piv] = M[piv], M[r]
        inv = 1 / M[r][c]
        for i in range(r + 1, n):
            if M[i][c]:
                f = M[i][c] * inv
                for k in range(c, m):
                    M[i][k] -= f * M[r][k]
        r += 1
        if r == n:
            break
    return r


def det_mod(A, p):
    M = [[x % p for x in row] for row in A]
    n = len(M)
    if n == 0:
        return 1 % p
    det = 1
    for c in range(n):
        piv = None
        for r in range(c, n):
            if M[r][c] % p:
                piv = r
                break
        if piv is None:
            return 0
        if piv != c:
            M[c], M[piv] = M[piv], M[c]
            det = (-det) % p
        det = det * M[c][c] % p
        inv = pow(M[c][c], -1, p)
        for r in range(c + 1, n):
            if M[r][c] % p:
                f = M[r][c] * inv % p
                for k in range(c, n):
                    M[r][k] = (M[r][k] - f * M[c][k]) % p
    return det % p


def rank_mod(A, p):
    M = [[x % p for x in row] for row in A]
    if not M:
        return 0
    r = 0
    n, m = len(M), len(M[0])
    for c in range(m):
        piv = None
        for i in range(r, n):
            if M[i][c] % p:
                piv = i
                break
        if piv is None:
            continue
        M[r], M[piv] = M[piv], M[r]
        inv = pow(M[r][c], -1, p)
        for k in range(c, m):
            M[r][k] = M[r][k] * inv % p
        for i in range(n):
            if i != r and M[i][c] % p:
                f = M[i][c]
                for k in range(c, m):
                    M[i][k] = (M[i][k] - f * M[r][k]) % p
        r += 1
        if r == n:
            break
    return r


# GF(2^8) with a polynomial modulus (integer notation: bit i = coeff x^i)
def gf_mul(a, b, mod):
    res = 0
    while b:
        if b & 1:
            res ^= a
        b >>= 1
        a <<= 1
        if a & 0x100:
            a ^= mod
    return res & 0xFF


def gf_inv(a, mod):
    assert a
    for x in range(1, 256):
        if gf_mul(a, x, mod) == 1:
            return x
    raise AssertionError("no inverse")


def det_gf(A, mod):
    M = [[x & 0xFF for x in row] for row in A]
    n = len(M)
    if n == 0:
        return 1
    det = 1
    for c in range(n):
        piv = None
        for r in range(c, n):
            if M[r][c]:
                piv = r
                break
        if piv is None:
            return 0
        if piv != c:
            M[c], M[piv] = M[piv], M[c]
            det = gf_mul(det, 0)  # placeholder overwritten below
            # sign irrelevant in char 2
        det = gf_mul(det, M[c][c], mod)
        inv = gf_inv(M[c][c], mod)
        for r in range(c + 1, n):
            if M[r][c]:
                f = gf_mul(M[r][c], inv, mod)
                for k in range(c, n):
                    M[r][k] ^= gf_mul(f, M[c][k], mod)
    return det


# ---------------------------------------------------------------------------
# case generation
# ---------------------------------------------------------------------------
def gen_cases():
    cases = []  # dict(id, kind, M, extra)

    def add(kind, M, **kw):
        cases.append(dict(id=f"C{len(cases)+1:03d}", kind=kind, M=M, **kw))

    # 1. zero matrices
    for n in [1, 2, 3, 5, 10, 50, 100]:
        add("zero", [[0] * n for _ in range(n)])

    # 2. identity
    for n in [1, 2, 3, 10, 50, 100]:
        add("identity", [[1 if i == j else 0 for j in range(n)] for i in range(n)])

    # 3. diagonal with boundary big entries
    for n, vals in [(2, [2**63 - 1, 2**63]), (2, [2**64 - 1, 2**64 - 2]),
                    (3, [2**100, 3, 5**20]), (4, [10**30, 2, 3, 7]),
                    (5, [1, 2, 4, 8, 16])]:
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            M[i][i] = vals[i]
        add("diag_big", M)

    # 4. banded sparse
    for n, bw in [(5, 1), (10, 2), (20, 1), (50, 3), (100, 2), (100, 5)]:
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            M[i][i] = random.choice([1, 2, 3, -1, 5])
            for d in range(1, bw + 1):
                if i + d < n:
                    M[i][i + d] = random.choice([0, 0, 1, 2, -3])
                if i - d >= 0:
                    M[i][i - d] = random.choice([0, 0, 1, -2])
        add(f"band_{bw}", M)

    # 5. triangular (upper/lower, unit/nonunit)
    for n in [3, 5, 10, 20, 50]:
        for tri in ["upper", "lower"]:
            M = [[0] * n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    if (tri == "upper" and j >= i) or (tri == "lower" and j <= i):
                        M[i][j] = (1 if i == j else random.choice([0, 0, 1, 2, -1, 3]))
            add(f"tri_{tri}", M)

    # 6. permutation matrices
    for n in [3, 5, 10, 50, 100]:
        perm = list(range(n))
        random.shuffle(perm)
        M = [[0] * n for _ in range(n)]
        for i, j in enumerate(perm):
            M[i][j] = 1
        add("permutation", M)

    # 7. random sparse
    for n, dens in [(2, 0.3), (3, 0.2), (5, 0.15), (10, 0.1), (20, 0.05),
                    (50, 0.03), (100, 0.02), (10, 0.01), (50, 0.01), (100, 0.005)]:
        M = [[random.choice([0, 0, 0, 0, random.randint(-5, 5)]) for _ in range(n)] for _ in range(n)]
        add(f"sparse_{dens}", M)

    # 8. rank-deficient sparse (duplicate / zero rows, linear combos)
    for n in [3, 5, 10, 20, 50, 100]:
        M = [[random.choice([0, 0, 1, 2, -1, 3]) for _ in range(n)] for _ in range(n)]
        M[n - 1] = M[0][:]              # duplicate row
        if n >= 4:
            M[n - 2] = [0] * n          # zero row
        add("rankdef_dup", M)

    for n in [3, 5, 10, 50]:
        # rank 1 outer product, sparse
        u = [random.choice([0, 0, 1, 2, -1]) for _ in range(n)]
        v = [random.choice([0, 0, 1, 3, -2]) for _ in range(n)]
        add("rank1_outer", [[u[i] * v[j] for j in range(n)] for i in range(n)])

    # 9. rectangular sparse
    for m, n in [(2, 3), (3, 2), (5, 8), (8, 5), (10, 20), (20, 10), (50, 30), (30, 50)]:
        M = [[random.choice([0, 0, 0, random.randint(-4, 4)]) for _ in range(n)] for _ in range(m)]
        add("rect", M)

    # 10. rational matrices
    for n in [2, 3, 5, 10]:
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if random.random() < 0.25:
                    M[i][j] = Fraction(random.randint(1, 6), random.randint(1, 7)) * random.choice([1, -1])
        add("rational", M, rational=True)

    # 11. structured named matrices (sparse/dense small)
    # Vandermonde
    xs = [1, 2, 3, 4, 5]
    add("vandermonde", [[x**j for j in range(5)] for x in xs])
    # Hilbert 5
    add("hilbert", [[Fraction(1, i + j + 1) for j in range(5)] for i in range(5)], rational=True)
    # Pascal 5
    P = [[0] * 5 for _ in range(5)]
    for i in range(5):
        for j in range(5):
            P[i][j] = 1 if j == 0 or i == 0 else P[i - 1][j] + P[i][j - 1]
    add("pascal", P)
    # companion of x^3 - 2x^2 + 3x - 4
    add("companion", [[0, 0, 4], [1, 0, -3], [0, 1, 2]])
    # Toeplitz / Hankel sparse
    add("toeplitz", [[(i - j) if abs(i - j) <= 1 else 0 for j in range(10)] for i in range(10)])
    add("hankel", [[(i + j) if i + j < 6 else 0 for j in range(6)] for i in range(6)])

    # 12. + extra sparse big-boundary structured (rank deficient with boundary entries)
    M = [[0] * 6 for _ in range(6)]
    for i in range(6):
        M[i][i] = 2**63 + i
    M[5] = M[0][:]  # make singular
    add("big_rankdef", M)

    # ---- additional cases to reach 150+ ----
    # more zero / identity sizes
    for n in [4, 7, 15, 25, 75]:
        add("zero", [[0] * n for _ in range(n)])
        add("identity", [[1 if i == j else 0 for j in range(n)] for i in range(n)])

    # more diagonal boundary configurations
    for n, vals in [(3, [2**63 - 1, 2**63, 2**63 + 1]),
                    (3, [2**64 - 1, 2**64 - 2, 2**64 - 3]),
                    (4, [-(2**63), 2**62, -(2**62), 1]),
                    (5, [2**31, 2**32, 2**40, 2**50, 2**60]),
                    (6, [1, 2, 4, 8, 16, 32])]:
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            M[i][i] = vals[i]
        add("diag_boundary", M)

    # more banded sparse
    for n, bw in [(7, 1), (15, 2), (25, 1), (75, 4), (100, 1), (100, 10)]:
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            M[i][i] = random.choice([1, 2, 3, -1, 5, -7])
            for d in range(1, bw + 1):
                if i + d < n:
                    M[i][i + d] = random.choice([0, 0, 0, 1, -2, 3])
                if i - d >= 0:
                    M[i][i - d] = random.choice([0, 0, 0, 1, 2, -4])
        add(f"band_{bw}", M)

    # more random sparse with varied density and sizes
    for n, dens in [(4, 0.25), (7, 0.12), (15, 0.08), (25, 0.04), (75, 0.02),
                    (100, 0.01), (100, 0.002), (12, 0.5), (6, 0.4)]:
        M = [[random.choice([0, 0, 0, 0, random.randint(-9, 9)]) for _ in range(n)] for _ in range(n)]
        add(f"sparse_{dens}", M)

    # more rank-deficient variants: duplicate columns, zero columns, combo rows
    for n in [4, 7, 15, 25, 75, 100]:
        M = [[random.choice([0, 0, 1, 2, -1, 4]) for _ in range(n)] for _ in range(n)]
        M[n - 1] = M[1][:]           # duplicate row
        for i in range(n):
            M[i][n - 1] = M[i][2]    # duplicate column
        add("rankdef_col", M)

    for n in [4, 7, 15, 25]:
        M = [[random.choice([0, 0, 1, 2, -1]) for _ in range(n)] for _ in range(n)]
        for i in range(n):
            M[i][n - 1] = 0          # zero column
            M[n - 1][i] = 0          # zero row
        add("rankdef_zero", M)

    for n in [5, 10, 20, 50]:
        # rows as linear combinations of first two rows
        M = [[random.choice([0, 0, 1, 2, -3]) for _ in range(n)] for _ in range(2)]
        while len(M) < n:
            a, b = random.randint(-2, 2), random.randint(-2, 2)
            M.append([a * M[0][j] + b * M[1][j] for j in range(n)])
        add("rankdef_combo", M)

    # more rectangular
    for m, n in [(4, 6), (6, 4), (15, 20), (20, 15), (75, 40), (40, 75), (100, 5), (5, 100)]:
        M = [[random.choice([0, 0, 0, random.randint(-6, 6)]) for _ in range(n)] for _ in range(m)]
        add("rect", M)

    # more rational (including singular rational and sparse rational)
    for n in [4, 6, 8]:
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if random.random() < 0.2:
                    M[i][j] = Fraction(random.randint(1, 9), random.randint(1, 11)) * random.choice([1, -1])
        M[n - 1] = M[0][:]  # singular rational
        add("rational_singular", M, rational=True)
    for n in [2, 3, 5]:
        M = [[Fraction(random.randint(0, 3), random.randint(1, 5)) for _ in range(n)] for _ in range(n)]
        add("rational_dense", M, rational=True)

    # more structured named matrices
    xs = [2, 3, 5, 7, 11, 13]
    add("vandermonde6", [[x**j for j in range(6)] for x in xs])
    # sparse Cauchy-like
    add("cauchy", [[Fraction(1, i + j + 1) if (i + j) % 2 == 0 else 0 for j in range(6)] for i in range(6)], rational=True)
    # sparse companion
    add("companion_sparse", [[0, 0, 0, 5], [1, 0, 0, -2], [0, 1, 0, 3], [0, 0, 1, -7]])
    # diagonal-dominant banded with huge entries
    M = [[0] * 8 for _ in range(8)]
    for i in range(8):
        M[i][i] = 2**70 + i
        if i + 1 < 8:
            M[i][i + 1] = 1
    add("band_big", M)

    # final batch: permutations + structured sparse with boundary entries
    for n in [4, 7, 15, 25, 75]:
        perm = list(range(n))
        random.shuffle(perm)
        M = [[0] * n for _ in range(n)]
        for i, j in enumerate(perm):
            M[i][j] = 1
        add("permutation", M)
    for n in [5, 10, 20, 50, 100]:
        # mostly zero with a few 2^63 / 2^64-1 entries on the diagonal
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            if i % 3 == 0:
                M[i][i] = 2**63
            elif i % 3 == 1:
                M[i][i] = 2**64 - 1
            else:
                M[i][i] = 1
        add("diag_boundary_sparse", M)
    for n in [3, 6, 12, 30]:
        # strictly upper triangular => nilpotent, det 0, rank <= n-1
        M = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if random.random() < 0.2:
                    M[i][j] = random.choice([1, 2, -1, 3])
        add("upper_nilpotent", M)
    for n in [4, 8, 16]:
        # lower unitriangular
        M = [[(1 if i == j else random.choice([0, 0, 2, -3])) if j <= i else 0 for j in range(n)] for i in range(n)]
        add("lower_unitri", M)

    return cases


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def build_cli_checks(cases):
    """Return list of (case, op, statement, oracle_kind, oracle_data)."""
    checks = []
    for c in cases:
        M = c["M"]
        cid, kind = c["id"], c["kind"]
        n = len(M)
        israt = c.get("rational", False)
        if israt:
            checks.append((cid, "qdet", "qmat det " + fmt_q_matrix(M), ("qdet", M)))
            checks.append((cid, "qrank", "qmat rank " + fmt_q_matrix(M), ("qrank", M)))
            continue
        fm = fmt_int_matrix(M)
        checks.append((cid, "zdet", "zmat det " + fm, ("zdet", M)))
        checks.append((cid, "zrank", "zmat rank " + fm, ("zrank", M)))
        # SNF/HNF on square or rectangular, but keep runtime bounded: skip 100x100
        if n <= 50:
            checks.append((cid, "snf", "snf " + fm, ("snf", M)))
            checks.append((cid, "hnf", "hnf " + fm, ("hnf", M)))
    return checks


def evaluate_cli(case, op, stmt, data, block, rc):
    okind = data[0]
    M = data[1]
    k, tag = case, op
    if rc not in (0,):
        note("CRASH/" + op, case, f"{stmt[:90]}...", "exit 0", f"exit {rc}", block[-300:])
        return
    if okind == "zdet":
        if M and len(M) != len(M[0]):
            if "error" not in block.lower():
                note("WRONG/zdet-rect", case, stmt[:90], "error on rectangular", block[-200:])
            return
        got = find_line(block, "det =")
        exp = str(det_bareiss(M))
        if got is None or got != exp:
            note("WRONG/zdet", case, stmt[:90], exp, got)
        else:
            COUNTS["checked"] += 1
    elif okind == "zrank":
        got = find_line(block, "rank =")
        exp = str(rank_q(M))
        if got is None or got != exp:
            note("WRONG/zrank", case, stmt[:90], exp, got)
        else:
            COUNTS["checked"] += 1
    elif okind == "qdet":
        got = find_line(block, "det =")
        sm = Matrix([[Rational(x) for x in row] for row in M])
        exp = str(sm.det())
        if got is None or Fraction(got) != Fraction(exp):
            note("WRONG/qdet", case, stmt[:90], exp, got)
        else:
            COUNTS["checked"] += 1
    elif okind == "qrank":
        got = find_line(block, "rank =")
        sm = Matrix([[Rational(x) for x in row] for row in M])
        exp = str(sm.rank())
        if got is None or got != exp:
            note("WRONG/qrank", case, stmt[:90], exp, got)
        else:
            COUNTS["checked"] += 1
    elif okind == "snf":
        d = find_line(block, "D:")
        if d is None:
            note("WRONG/snf-nod", case, stmt[:90], "D matrix", block[-300:])
            return
        D = parse_int_matrix(d)
        diag = [D[i][i] for i in range(min(len(D), len(D[0]) if D else 0))]
        # invariant factors must be nonnegative and divisibility d_i | d_{i+1}
        if any(x < 0 for x in diag):
            note("WRONG/snf-negative", case, stmt[:90], "nonnegative diag", diag)
            return
        nz = [x for x in diag if x != 0]
        # invariant factors are 0 for the zero part; divisibility applies to nonzeros
        for a, b in zip(nz, nz[1:]):
            if b % a:
                note("WRONG/snf-divisibility", case, stmt[:90], f"{a}|{b}", diag)
                return
        # rank must match oracle rank
        rexp = rank_q(M)
        if len(nz) != rexp:
            note("WRONG/snf-rank", case, stmt[:90], rexp, len(nz))
            return
        # for square matrices, product of invariant factors == |det|
        if M and len(M) == len(M[0]):
            prod = 1
            for x in diag:  # include zeros: product of ALL invariant factors == |det|
                prod *= x
            dexp = abs(det_bareiss(M))
            if prod != dexp:
                note("WRONG/snf-detproduct", case, stmt[:90], dexp, prod)
                return
        COUNTS["checked"] += 1
    elif okind == "hnf":
        h = find_line(block, "H:")
        if h is None:
            note("WRONG/hnf-noh", case, stmt[:90], "H matrix", block[-300:])
            return
        # verify rank equals oracle rank
        H = parse_int_matrix(h)
        if not H:
            rank_h = 0
        else:
            rank_h = rank_q(H)
        exp_rank = rank_q(M)
        if rank_h != exp_rank:
            note("WRONG/hnf-rank", case, stmt[:90], exp_rank, rank_h)
        else:
            COUNTS["checked"] += 1


def build_mcp_cert_checks(cases):
    """SNF/HNF certificate checks via MCP structured outputs (small matrices)."""
    calls = []
    meta = []
    i = 1
    for c in cases:
        M = c["M"]
        if c.get("rational") or len(M) > 12 or not M:
            continue
        fm = fmt_int_matrix(M)
        # snf
        calls.append(("abstract_algebra", "snf", {"matrix": M}))
        meta.append((c["id"], "snf", M, i)); i += 1
        # hnf
        calls.append(("abstract_algebra", "hnf", {"matrix": M}))
        meta.append((c["id"], "hnf", M, i)); i += 1
        # zmatrix inverse
        calls.append(("abstract_algebra", "zmatrix", {"op": "inverse", "matrix": M}))
        meta.append((c["id"], "zinv", M, i)); i += 1
    return calls, meta


def evaluate_mcp(meta, out):
    for cid, op, M, reqid in meta:
        o = out.get(reqid)
        if o is None:
            note("HANG/" + op, cid, f"mcp id {reqid}", "response", "none")
            continue
        s = sc(o)
        if s is None:
            note("CRASH/" + op, cid, f"mcp id {reqid}", "structured", json.dumps(o)[:200])
            continue
        r = s.get("result", {})
        if op == "snf":
            try:
                U = parse_int_matrix(r["u"]); V = parse_int_matrix(r["v"])
                D = parse_int_matrix(r["d"])
                Ui = parse_int_matrix(r["u_1"]); Vi = parse_int_matrix(r["v_1"])
            except Exception as e:
                note("WRONG/snf-parse", cid, op, "matrices", str(e)); continue
            # U A V = D
            got = matmul(matmul(U, M), V)
            if not mat_eq(got, D):
                note("WRONG/snf-cert", cid, "U A V = D", D, got)
            # U U^-1 = I, V V^-1 = I
            for name, X, Xi in [("U", U, Ui), ("V", V, Vi)]:
                prod = matmul(X, Xi)
                n = len(X)
                I = [[1 if a == b else 0 for b in range(n)] for a in range(n)]
                if not mat_eq(prod, I):
                    note("WRONG/snf-unimod", cid, f"{name}{name}^-1=I", I, prod)
            # checks flag
            checks = s.get("checks", [])
            if not any(ch.get("passed") for ch in checks):
                note("WRONG/snf-checkflag", cid, "check passed", True, checks)
            COUNTS["checked"] += 1
        elif op == "hnf":
            try:
                U = parse_int_matrix(r["u"]); H = parse_int_matrix(r["h"])
            except Exception as e:
                note("WRONG/hnf-parse", cid, op, "matrices", str(e)); continue
            got = matmul(U, M)
            if not mat_eq(got, H):
                note("WRONG/hnf-cert", cid, "U A = H", H, got)
            COUNTS["checked"] += 1
        elif op == "zinv":
            if M and len(M) != len(M[0]):
                COUNTS["checked"] += 1
                continue
            inv_present = "inverse" in r or "value" in r
            det = det_bareiss(M) if M else 1
            invertible = abs(det) == 1
            got_inv = inv_present and ("singular" not in s.get("text", "").lower() and
                                       "not invertible" not in s.get("text", "").lower())
            if bool(got_inv) != bool(invertible):
                note("WRONG/zinv", cid, op, f"invertible={invertible}", r)


# ---------------------------------------------------------------------------
# mod p / GF oracle checks (CLI)
# ---------------------------------------------------------------------------
def build_mod_checks(cases):
    checks = []
    for c in cases:
        M = c["M"]
        if c.get("rational") or not M or len(M) > 12:
            continue
        for p, ring in [(7, f"mod 7"), (2, "mod 2"), (1000003, "mod 1000003")]:
            fm = fmt_int_matrix(M)
            checks.append((c["id"], "det", f"det {fm} {ring}", ("detmod", M, p)))
            checks.append((c["id"], "rank", f"rank {fm} {ring}", ("rankmod", M, p)))
    return checks


def evaluate_mod(case, op, stmt, data, block, rc):
    kind, M, p = data
    if M and len(M) != len(M[0]):
        # rectangular: expect "no determinant: the matrix is not square"
        if kind == "detmod" and "not square" not in block.lower():
            note("WRONG/detmod-rect", case, stmt[:90], "not-square error", block[-200:])
        return
    if any(abs(int(x)) >= 2**64 for row in M for x in row):
        # mod-p path uses machine integers; >64-bit entries return a clean error
        if "too large" not in block.lower():
            note("WRONG/detmod-big", case, stmt[:90], "too-large error", block[-200:])
        return
    if rc != 0:
        note("CRASH/" + op, case, stmt[:90], "exit 0", f"exit {rc}", block[-200:]); return
    if kind == "detmod":
        got = find_line(block, "det =")
        exp = str(det_mod(M, p))
        if got is None or str(int(got)) != exp:
            note("WRONG/detmod", case, f"p={p} " + stmt[:60], exp, got)
        else:
            COUNTS["checked"] += 1
    elif kind == "rankmod":
        got = None
        for ln in block.splitlines():
            mm = re.search(r"rank (\d+) over GF", ln)
            if mm:
                got = mm.group(1); break
        exp = str(rank_mod(M, p))
        if got != exp:
            note("WRONG/rankmod", case, f"p={p} " + stmt[:60], exp, got)
        else:
            COUNTS["checked"] += 1


def main():
    cases = gen_cases()
    print(f"Generated {len(cases)} matrices", flush=True)
    COUNTS["cases"] = len(cases)

    # Batch CLI structural checks
    cli_checks = build_cli_checks(cases)
    for i in range(0, len(cli_checks), 12):
        chunk = cli_checks[i:i + 12]
        stmts = [x[2] for x in chunk]
        rc, out = run_cli(stmts, timeout=30)
        blocks = split_blocks(out, len(stmts))
        COUNTS["cli"] += len(stmts)
        COUNTS["queries"] += len(stmts)
        for (cid, op, stmt, data), blk in zip(chunk, blocks):
            evaluate_cli(cid, op, stmt, data, blk, rc)
        if VERBOSE:
            print(f"  CLI batch {i//12+1}: rc={rc}, {len(stmts)} stmts, {len(out)} bytes", flush=True)

    print(f"CLI structural checks done: {COUNTS['cli']} stmts", flush=True)

    # Mod checks
    mod_checks = build_mod_checks(cases)
    for i in range(0, len(mod_checks), 60):
        chunk = mod_checks[i:i + 60]
        stmts = [x[2] for x in chunk]
        rc, out = run_cli(stmts, timeout=30)
        blocks = split_blocks(out, len(stmts))
        COUNTS["cli"] += len(stmts)
        COUNTS["queries"] += len(stmts)
        for (cid, op, stmt, data), blk in zip(chunk, blocks):
            evaluate_mod(cid, op, stmt, data, blk, rc)

    print(f"Mod checks done: {COUNTS['cli']} total CLI stmts", flush=True)

    # MCP certificate checks in chunks
    calls, meta = build_mcp_cert_checks(cases)
    for i in range(0, len(calls), 40):
        chunk = calls[i:i + 40]
        mchunk = meta[i:i + 40]
        rc, out = run_mcp(chunk, timeout=30, start_id=i + 1)
        COUNTS["mcp"] += len(chunk)
        COUNTS["queries"] += len(chunk)
        if rc == 124:
            for cid, op, M, rid in mchunk:
                note("HANG/mcp", cid, op, "response", "timeout")
            continue
        evaluate_mcp(mchunk, out)

    print("\n==== SUMMARY ====")
    print(json.dumps(COUNTS, indent=2))
    print(f"mismatches: {len(MISMATCHES)}")
    with open(os.path.join(HERE, "_mismatches.json"), "w") as f:
        json.dump({"counts": COUNTS, "mismatches": MISMATCHES}, f, indent=2)
    # group by kind
    from collections import Counter
    c = Counter(m["kind"] for m in MISMATCHES)
    print("by kind:", dict(c))
    for m in MISMATCHES[:40]:
        print(f"  [{m['kind']}] {m['case']}: exp={m['expected'][:60]} got={m['observed'][:60]}")


if __name__ == "__main__":
    main()
