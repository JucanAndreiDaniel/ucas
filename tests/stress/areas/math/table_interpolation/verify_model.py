#!/usr/bin/env python3
"""Generate table-lookup cases, run ucas, compare against a Python list model.

Model: [t0..tn-1][j] -> tj if 0 <= j < n else undefined.
Index j is coerced to the index expression's integer type first:
  int literal -> itself; uN(k) -> k mod 2^N; iN(k) -> signed N-bit wrap;
  true/false -> 1/0.
Element values are chosen to be exactly representable in each element type so
the Python value equals the printed value (modulo the common table type).
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
_HERE = _ROOT_PATH(__file__).resolve().parent
import subprocess, re, sys, itertools

BIN = str(_REPO_ROOT / "ucas")

def coerce_index(expr):
    """Return (coerced integer value) for supported index expressions."""
    expr = expr.strip()
    m = re.fullmatch(r"u(\d+)\((-?\d+)\)", expr)
    if m:
        w, k = int(m.group(1)), int(m.group(2))
        return k % (1 << w)
    m = re.fullmatch(r"i(\d+)\((-?\d+)\)", expr)
    if m:
        w, k = int(m.group(1)), int(m.group(2))
        k &= (1 << w) - 1
        if k >> (w - 1):
            k -= 1 << w
        return k
    if expr == "true":
        return 1
    if expr == "false":
        return 0
    m = re.fullmatch(r"-?\d+", expr)
    if m:
        return int(expr)
    return None  # unknown, skip

def run(lines):
    p = subprocess.run([BIN], input="\n".join(lines) + "\n", text=True,
                       capture_output=True, timeout=30, cwd=str(_HERE))
    return p.stdout + p.stderr, p.returncode

def parse_show(out):
    """Return list of (value_str, type_str) for each '_() = ...' show block."""
    res = []
    lines = out.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"_\(\) = (.*)$", lines[i])
        if m:
            val = m.group(1).strip()
            ty = None
            if i + 1 < len(lines):
                tm = re.match(r"\s+-> (.*)$", lines[i + 1])
                if tm:
                    ty = tm.group(1).strip()
            res.append((val, ty))
            i += 2
        else:
            i += 1
    return res

def main():
    cases = []  # (label, ucas_expr, expected_value_or_None, expected_type_hint)

    # ---- Batch A: out-of-range across table sizes ----
    sizes = [1, 2, 3, 4, 5, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 100, 127, 128, 255, 256, 257, 511, 512, 1023, 1024]
    for n in sizes:
        vals = list(range(1000, 1000 + n))
        els = ",".join(map(str, vals))
        for j in [0, n - 1, n, n + 1, -1]:
            expr = f"[{els}][{j}]"
            exp = vals[j] if 0 <= j < n else None
            cases.append((f"A n={n} j={j}", f"show {expr}", exp, "int"))

    # ---- Batch B: index coercion ----
    vals = [11, 22, 33, 44, 55]
    els = ",".join(map(str, vals))
    idxs = ["0", "1", "4", "5", "-1", "u8(1)", "u8(256)", "u8(255)",
            "i8(3)", "i8(-1)", "i8(127)", "i16(4)", "u16(65535)",
            "u32(4294967295)", "u64(18446744073709551615)",
            "true", "false", "1+1", "2*2", "u8(3)+1"]
    for ix in idxs:
        j = coerce_index(ix)
        if ix in ("1+1", "2*2", "u8(3)+1"):
            # compute simple arithmetic manually
            j = {"1+1": 2, "2*2": 4, "u8(3)+1": 4}[ix]
        expr = f"[{els}][{ix}]"
        exp = vals[j] if j is not None and 0 <= j < len(vals) else None
        cases.append((f"B idx={ix}", f"show {expr}", exp, "int"))

    # ---- Batch C: mixed element types (values exact) ----
    mixed = [
        ("[u8(10),u16(300),u32(70000)][0]", 10, "u32"),
        ("[u8(10),u16(300),u32(70000)][1]", 300, "u32"),
        ("[u8(10),u16(300),u32(70000)][2]", 70000, "u32"),
        ("[i8(-1),u8(200)][0]", 255, "u8"),
        ("[i8(-1),u8(200)][1]", 200, "u8"),
        ("[u8(1),f32(2.5)][0]", 1, "f32"),
        ("[u8(1),f32(2.5)][1]", 2.5, "f32"),
        ("[1,2.5,3][1]", 2.5, "real"),
        ("[f32(1.5),f64(2.25)][0]", 1.5, "f64"),
        ("[f32(1.5),f64(2.25)][1]", 2.25, "f64"),
    ]
    for expr, exp, ty in mixed:
        cases.append((f"C {expr}", f"show {expr}", exp, ty))

    # ---- Batch D: nested tables ----
    nested = [
        ("[[1,2],[3,4]][0][0]", 1), ("[[1,2],[3,4]][0][1]", 2),
        ("[[1,2],[3,4]][1][0]", 3), ("[[1,2],[3,4]][1][1]", 4),
        # [[...,...]][2][0] is omitted: an out-of-range outer index yields
        # undefined, and indexing a scalar is a parse error (see 09_errors).
        ("[[1,2],[3,4]][0][2]", None),
        ("[[[1,2],[3,4]],[[5,6],[7,8]]][1][1][0]", 7),
    ]
    for expr, exp in nested:
        cases.append((f"D {expr}", f"show {expr}", exp, "int"))

    # ---- Batch E: negative signed indices at various widths ----
    evals = [10, 20, 30, 40]
    for w in [1, 2, 4, 8, 16, 32, 64]:
        for k in [-1, -2]:
            expr = f"[10,20,30,40][i{w}({k})]"
            j = coerce_index(f"i{w}({k})")
            exp = evals[j] if j is not None and 0 <= j < len(evals) else None
            cases.append((f"E i{w}({k})", f"show {expr}", exp, "int"))
    # unsigned high-bit indices
    for w in [8, 16, 32, 64]:
        hi = (1 << w) - 1
        expr = f"[10,20,30,40][u{w}({hi})]"
        j = coerce_index(f"u{w}({hi})")
        exp = evals[j] if j is not None and 0 <= j < len(evals) else None
        cases.append((f"E u{w}({hi})", f"show {expr}", exp, "int"))

    # run in chunks
    mismatches = []
    total = 0
    for start in range(0, len(cases), 60):
        chunk = cases[start:start + 60]
        lines = [c[1] for c in chunk]
        out, rc = run(lines)
        parsed = parse_show(out)
        if len(parsed) != len(chunk):
            print(f"WARN chunk {start}: {len(parsed)} parsed vs {len(chunk)} expected; rc={rc}")
            print(out[:1000])
        for (label, _, exp, tyhint), (val, ty) in zip(chunk, parsed):
            total += 1
            ok = True
            if exp is None:
                ok = (val == "undefined")
            else:
                try:
                    if isinstance(exp, float):
                        ok = abs(float(val) - exp) < 1e-9
                    else:
                        ok = int(val) == exp
                except Exception:
                    ok = False
            if not ok:
                mismatches.append((label, exp, val, ty, tyhint))

    print(f"TOTAL cases: {total}, mismatches: {len(mismatches)}")
    for m in mismatches[:80]:
        print("MISMATCH", m)
    return mismatches

if __name__ == "__main__":
    sys.exit(0 if not main() else 1)
