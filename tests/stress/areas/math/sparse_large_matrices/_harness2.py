#!/usr/bin/env python3
"""Second differential harness: solve, modular inverse/nullspace, GF(2^8),
malformed rows, and determinism.  Reuses helpers from _harness.py.
"""
import json
import os
import random
import re
import subprocess
from fractions import Fraction

import _harness as H

BIN = H.BIN
HERE = H.HERE
MISM = []
COUNTS = {"queries": 0, "checked": 0}


def note(kind, case, stmt, expected, observed, extra=""):
    MISM.append({"kind": kind, "case": case, "stmt": stmt,
                 "expected": str(expected), "observed": str(observed), "extra": extra})
    print(f"[{kind}] {case}: {stmt[:80]}\n  exp={expected}\n  got={observed} {extra}")


def parse_space_matrix(text):
    """Parse rows like '[5 1]' / '[5, 1]' possibly indented."""
    rows = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].replace(",", " ")
            parts = inner.split()
            if parts:
                rows.append([int(x) for x in parts])
    return rows


def block_after(block, marker):
    lines = block.splitlines()
    for i, ln in enumerate(lines):
        if marker in ln:
            return "\n".join(lines[i + 1:])
    return ""


def build_checks(cases):
    checks = []
    for c in cases:
        M = c["M"]
        cid, kind = c["id"], c["kind"]
        if c.get("rational") or not M:
            continue
        n = len(M)
        # mod-p path uses machine integers: skip entries that overflow 64 bits
        if any(abs(int(x)) >= 2**64 for row in M for x in row):
            continue
        # square integer cases get solve / modular inverse / nullspace
        if n <= 12 and len(M) == len(M[0]):
            fm = H.fmt_int_matrix(M)
            # solvable solve: choose x0 with small entries, b = A x0
            x0 = [[random.randint(-3, 3)] for _ in range(n)]
            b = [[sum(M[i][k] * x0[k][0] for k in range(n))] for i in range(n)]
            fb = H.fmt_int_matrix(b)
            checks.append((cid, "zsolve", f"zmat solve {fm}, {fb}", ("zsolve", M, b)))
            # modular inverse + nullspace for prime p=7 and p=1000003
            for p in (7, 1000003):
                checks.append((cid, "minv", f"inverse {fm} mod {p}", ("minv", M, p)))
            checks.append((cid, "mnull", f"nullspace {fm} mod 7", ("mnull", M, 7)))
    return checks


def evaluate(cid, op, stmt, data, block, rc):
    kind = data[0]
    if rc != 0:
        note("CRASH/" + op, cid, stmt[:90], "exit 0", f"exit {rc}", block[-200:])
        return
    if kind == "zsolve":
        M, b = data[1], data[2]
        xs = find_x(block)
        if xs is None:
            note("WRONG/zsolve", cid, stmt[:90], "x matrix", block[-200:])
            return
        got = H.matmul(M, xs)
        if got != b:
            note("WRONG/zsolve-check", cid, stmt[:90], b, got)
        else:
            COUNTS["checked"] += 1
    elif kind == "minv":
        M, p = data[1], data[2]
        d = H.det_mod(M, p)
        tail = block_after(block, "inverse:")
        inv = parse_space_matrix(tail) if tail else []
        if d != 0:
            if not inv:
                note("WRONG/minv-missing", cid, f"p={p}", "inverse matrix", block[-250:])
                return
            prod = [[sum(M[i][k] * inv[k][j] for k in range(len(M))) % p for j in range(len(M))] for i in range(len(M))]
            I = [[1 if i == j else 0 for j in range(len(M))] for i in range(len(M))]
            if prod != I:
                note("WRONG/minv", cid, f"p={p}", I, prod)
            else:
                COUNTS["checked"] += 1
        else:
            if not ("no inverse" in block or "not a unit" in block or inv):
                note("WRONG/minv-singular", cid, f"p={p}", "no inverse", block[-250:])
            else:
                COUNTS["checked"] += 1
    elif kind == "mnull":
        M, p = data[1], data[2]
        n = len(M)
        expdim = n - H.rank_mod(M, p)
        mm = re.search(r"dimension (\d+)", block)
        if not mm:
            note("WRONG/mnull-dim", cid, stmt[:80], expdim, block[-200:])
            return
        if int(mm.group(1)) != expdim:
            note("WRONG/mnull-dim", cid, stmt[:80], expdim, mm.group(1))
            return
        vs = parse_space_matrix(block_after(block, "basis (rows):"))
        for v in vs:
            if len(v) != n:
                note("WRONG/mnull-len", cid, stmt[:80], n, len(v))
                return
            prod = [sum(M[i][k] * v[k] for k in range(n)) % p for i in range(n)]
            if any(prod):
                note("WRONG/mnull-vec", cid, stmt[:80], "zero", prod)
                return
        COUNTS["checked"] += 1


def find_x(block):
    for ln in block.splitlines():
        s = ln.strip()
        if s.startswith("x ="):
            return H.parse_int_matrix(s[2:].strip())
    return None


def gf_det_oracle(M, mod=0x11d):
    # ucas embeds integers into GF(2)[x] by reducing coefficients mod 2:
    # -4 -> 4 (since -1 == 1 in char 2).  Use abs() before taking the byte.
    A = [[abs(int(x)) & 0xFF for x in row] for row in M]
    n = len(A)
    if n == 0:
        return 1
    det = 1
    for c in range(n):
        piv = None
        for r in range(c, n):
            if A[r][c]:
                piv = r
                break
        if piv is None:
            return 0
        if piv != c:
            A[c], A[piv] = A[piv], A[c]  # char 2: sign irrelevant
        det = H_gf_mul(det, A[c][c], mod)
        inv = H_gf_inv(A[c][c], mod)
        for r in range(c + 1, n):
            if A[r][c]:
                f = H_gf_mul(A[r][c], inv, mod)
                for k in range(c, n):
                    A[r][k] ^= H_gf_mul(f, A[c][k], mod)
    return det


def H_gf_mul(a, b, mod):
    res = 0
    while b:
        if b & 1:
            res ^= a
        b >>= 1
        a <<= 1
        if a & 0x100:
            a ^= mod
    return res & 0xFF


def H_gf_inv(a, mod):
    for x in range(1, 256):
        if H_gf_mul(a, x, mod) == 1:
            return x
    raise ValueError


def build_gf_checks(cases):
    checks = []
    for c in cases:
        M = c["M"]
        if c.get("rational") or not M or len(M) > 10 or len(M) != len(M[0]):
            continue
        # entries must be < 256 for GF(2^8) integer notation
        if any(abs(x) > 255 for row in M for x in row):
            continue
        fm = H.fmt_int_matrix(M)
        checks.append((c["id"], "gf", f"det {fm} in GF(2^8)", ("gf", M)))
    return checks


def evaluate_gf(cid, op, stmt, data, block, rc):
    M = data[1]
    if rc != 0:
        note("CRASH/gf", cid, stmt[:90], "exit 0", f"exit {rc}", block[-200:]); return
    got = H.find_line(block, "det =")
    exp = "0x%02x" % gf_det_oracle(M)
    if got is None or got.lower() != exp:
        note("WRONG/gf", cid, stmt[:90], exp, got, block[-150:])
    else:
        COUNTS["checked"] += 1


def run_malformed():
    bads = [
        ("ragged_short", "zmat det [[1,2],[3]]"),
        ("ragged_long", "zmat det [[1,2],[3,4,5]]"),
        ("ragged_snf", "snf [[1,2],[3]]"),
        ("empty_row", "zmat rank [[1,2],[]]"),
        ("double_comma", "zmat det [[1,,2],[3,4]]"),
        ("unclosed", "zmat det [[1,2],[3,4]"),
        # trailing comma and flat single-row are accepted ucas grammar:
        ("trailing_comma_ok", "zmat det [[1,2,],[3,4]]"),
        ("flat_ok", "zmat rank [1,2,3,4]"),
        ("nonnumeric", "zmat det [[a,2],[3,4]]"),
        ("ragged_qmat", "qmat det [[1/2,1/3],[1/5]]"),
        ("ragged_mod", "det [[1,2],[3]] mod 7"),
    ]
    stmts = [s for _, s in bads]
    rc, out = H.run_cli(stmts, timeout=20)
    blocks = H.split_blocks(out, len(stmts))
    COUNTS["queries"] += len(stmts)
    for (cid, stmt), blk in zip(bads, blocks):
        if cid.endswith("_ok"):
            # accepted lenient forms: just require a result, no error
            if "error" in blk.lower():
                note("WRONG/malformed-reject", cid, stmt, "accepted", blk[-200:])
            else:
                COUNTS["checked"] += 1
            continue
        if rc != 0:
            note("CRASH/malformed", cid, stmt, "exit 0", f"exit {rc}", blk[-200:]); continue
        low = blk.lower()
        if "error" not in low and "different lengths" not in low and "expected" not in low:
            note("WRONG/malformed-noerror", cid, stmt, "clean error", blk[-250:])
        else:
            COUNTS["checked"] += 1


def run_determinism(cases):
    # pick a representative mix of deterministic operations
    picks = [c for c in cases if not c.get("rational") and c["M"] and len(c["M"]) <= 20][:40]
    stmts = []
    for c in picks:
        fm = H.fmt_int_matrix(c["M"])
        stmts.append("zmat det " + fm)
        stmts.append("zmat rank " + fm)
        if len(c["M"]) == len(c["M"][0]):
            stmts.append("snf " + fm)
            stmts.append("hnf " + fm)
    rc1, out1 = H.run_cli(stmts, timeout=30)
    rc2, out2 = H.run_cli(stmts, timeout=30)
    COUNTS["queries"] += 2 * len(stmts)
    if rc1 != 0 or rc2 != 0:
        note("CRASH/determinism", "run", f"{len(stmts)} stmts", "exit 0", f"{rc1},{rc2}")
    elif out1 != out2:
        # find first differing line
        a, b = out1.splitlines(), out2.splitlines()
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                note("DETERMINISM", "run", f"{len(stmts)} stmts", "identical", f"line {i}", f"{x[:80]} vs {y[:80]}")
                break
    else:
        COUNTS["checked"] += 1


def main():
    random.seed(H.SEED)
    cases = H.gen_cases()
    checks = build_checks(cases)
    for i in range(0, len(checks), 30):
        chunk = checks[i:i + 30]
        stmts = [x[2] for x in chunk]
        rc, out = H.run_cli(stmts, timeout=30)
        blocks = H.split_blocks(out, len(stmts))
        COUNTS["queries"] += len(stmts)
        for (cid, op, stmt, data), blk in zip(chunk, blocks):
            evaluate(cid, op, stmt, data, blk, rc)

    gf = build_gf_checks(cases)
    for i in range(0, len(gf), 30):
        chunk = gf[i:i + 30]
        stmts = [x[2] for x in chunk]
        rc, out = H.run_cli(stmts, timeout=30)
        blocks = H.split_blocks(out, len(stmts))
        COUNTS["queries"] += len(stmts)
        for (cid, op, stmt, data), blk in zip(chunk, blocks):
            evaluate_gf(cid, op, stmt, data, blk, rc)

    run_malformed()
    run_determinism(cases)

    print("\n==== SUMMARY2 ====")
    print(json.dumps(COUNTS, indent=2))
    print("mismatches:", len(MISM))
    json.dump(COUNTS, open(os.path.join(HERE, "_counts2.json"), "w"), indent=2)
    json.dump(MISM, open(os.path.join(HERE, "_mismatches2.json"), "w"), indent=2)
    from collections import Counter
    print("by kind:", dict(Counter(m["kind"] for m in MISM)))


if __name__ == "__main__":
    main()
