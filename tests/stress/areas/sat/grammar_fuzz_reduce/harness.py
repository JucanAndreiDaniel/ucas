#!/usr/bin/env python3
"""Shared helpers for the grammar_fuzz_reduce stress area.

Everything here is self-contained in this folder.  It provides:

* subprocess wrappers for the ucas CLI and MCP stdio frontends (always bounded
  by ``timeout``),
* a Python evaluator for the small typed expression AST that ``gen.py`` emits
  (machine-integer wrapping, casts, bit casts, partial operations),
* corner/random valuation batteries and fingerprint utilities.

The Python evaluator is an *independent* oracle: ucas results are cross-checked
against it to look for unsound equivalence / range answers.
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
import struct
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, "_scratch")
BIN = str(_REPO_ROOT / "ucas")
os.makedirs(SCRATCH, exist_ok=True)

# ---------------------------------------------------------------------------
# process runners
# ---------------------------------------------------------------------------

def run_cli(lines, timeout=15, name="case"):
    """Run a .ucas source (string or list of lines) under timeout.  cwd=HERE."""
    if isinstance(lines, (list, tuple)):
        src = "\n".join(lines) + "\n"
    else:
        src = lines if lines.endswith("\n") else lines + "\n"
    path = os.path.join(SCRATCH, name + ".ucas")
    with open(path, "w") as fh:
        fh.write(src)
    try:
        p = subprocess.run(
            ["timeout", str(timeout), BIN, os.path.basename(path)],
            cwd=SCRATCH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout + 3,
        )
        rc, out, timed = p.returncode, p.stdout.decode("utf-8", "replace"), False
    except subprocess.TimeoutExpired as e:
        rc, timed = None, True
        out = (e.stdout or b"").decode("utf-8", "replace")
    return {"rc": rc, "timed_out": timed, "out": out, "src": src}


def run_mcp(requests, timeout=15, extra_flags=()):
    """Run a list of JSON-RPC request dicts through `ucas --mcp` under timeout.

    Returns parsed responses plus the raw output.  `initialize` and the
    initialized notification are prepended automatically.
    """
    msgs = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "stress", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ] + list(requests)
    data = "".join(json.dumps(m) + "\n" for m in msgs)
    try:
        p = subprocess.run(
            ["timeout", str(timeout), BIN, "--mcp", *extra_flags],
            input=data.encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=SCRATCH, timeout=timeout + 3,
        )
        rc, out, timed = p.returncode, p.stdout.decode("utf-8", "replace"), False
    except subprocess.TimeoutExpired as e:
        rc, timed = None, True
        out = (e.stdout or b"").decode("utf-8", "replace")
    parsed = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            parsed.append(json.loads(ln))
        except Exception:
            pass
    return {"rc": rc, "timed_out": timed, "out": out, "parsed": parsed}


def mcp_call(id_, name, args):
    return {"jsonrpc": "2.0", "id": id_, "method": "tools/call",
            "params": {"name": name, "arguments": args}}


# ---------------------------------------------------------------------------
# type info
# ---------------------------------------------------------------------------

INT_TYPES = {
    "u8": (8, False), "u16": (16, False), "u32": (32, False), "u64": (64, False),
    "i8": (8, True), "i16": (16, True), "i32": (32, True), "i64": (64, True),
}
FLOAT_TYPES = ("f32", "real")


def tw(t):
    return INT_TYPES[t][0] if t in INT_TYPES else (32 if t == "f32" else 53)


def is_signed(t):
    return INT_TYPES.get(t, (0, False))[1]


def is_int(t):
    return t in INT_TYPES


def wrap(v, t):
    """Wrap an integer v to machine type t."""
    w, s = INT_TYPES[t]
    v = int(v) & ((1 << w) - 1)
    if s and v >= (1 << (w - 1)):
        v -= 1 << w
    return v


class _Undef:
    def __repr__(self):
        return "UNDEF"


UNDEF = _Undef()


def rnd32(x):
    """Round a Python float to an IEEE-754 binary32 value."""
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return float("inf") if x >= 0 else float("-inf")


def trunc_div(a, b):
    if b == 0:
        return UNDEF
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


# ---------------------------------------------------------------------------
# independent evaluator for generator AST nodes
# ---------------------------------------------------------------------------

def ev(node, env):
    """Evaluate a generator AST node in environment env ({var: python value}).

    Returns a wrapped int for integer types, a float for f32/real, or UNDEF.
    """
    k = node["k"]
    t = node.get("t", "int")

    def wrap_res(v):
        if v is UNDEF:
            return UNDEF
        return wrap(v, t) if is_int(t) else (rnd32(v) if t == "f32" else float(v))

    if k == "var":
        v = env.get(node["name"], UNDEF)
        if v is UNDEF:
            return UNDEF
        return wrap(v, t) if is_int(t) else v
    if k == "const":
        v = node["v"]
        if is_int(t):
            return wrap(v, t)
        return rnd32(v) if t == "f32" else float(v)
    if k == "un":
        a = ev(node["a"], env)
        if a is UNDEF:
            return UNDEF
        op = node["op"]
        if op == "~":
            return wrap_res(~a)
        if op == "-":
            return wrap_res(-a)
        if op == "abs":
            return wrap_res(abs(a))
        if op in ("clz", "ctz", "popcount"):
            w = tw(node["a"].get("t", t))
            u = a & ((1 << w) - 1)
            if op == "popcount":
                return bin(u).count("1")
            if op == "clz":
                return w - u.bit_length()
            return (u & -u).bit_length() - 1 if u else w
        raise ValueError("un op " + op)
    if k == "bin":
        a = ev(node["a"], env)
        b = ev(node["b"], env)
        if a is UNDEF or b is UNDEF:
            return UNDEF
        op = node["op"]
        if op == "+":
            return wrap_res(a + b)
        if op == "-":
            return wrap_res(a - b)
        if op == "*":
            return wrap_res(a * b)
        if op == "&":
            return wrap_res(a & b)
        if op == "|":
            return wrap_res(a | b)
        if op == "xor":
            return wrap_res(a ^ b)
        if op == "<<":
            if not (0 <= b < tw(node["a"].get("t", t))):
                return UNDEF
            return wrap_res(a << b)
        if op == ">>":
            if not (0 <= b < tw(node["a"].get("t", t))):
                return UNDEF
            return wrap_res(a >> b)
        if op == "/":
            if isinstance(a, float) or isinstance(b, float):
                if b == 0:
                    if t == "real":
                        return UNDEF  # ucas's `real` division by zero is partial
                    # IEEE machine float: division by zero gives inf / NaN
                    import math
                    if a == 0 or a != a:
                        return float("nan")
                    s = math.copysign(1.0, a) * math.copysign(1.0, b)
                    return float("inf") if s > 0 else float("-inf")
                return wrap_res(a / b)
            q = trunc_div(a, b)
            return UNDEF if q is UNDEF else wrap_res(q)
        if op == "%":
            if isinstance(a, float) or isinstance(b, float):
                import math
                if b == 0:
                    return UNDEF
                return wrap_res(math.fmod(a, b))
            q = trunc_div(a, b)
            return UNDEF if q is UNDEF else wrap_res(a - q * b)
        if op in ("<", "<=", "==", "!=", ">", ">="):
            r = {"<": a < b, "<=": a <= b, "==": a == b,
                 "!=": a != b, ">": a > b, ">=": a >= b}[op]
            return 1 if r else 0
        if op == "min":
            return wrap_res(min(a, b))
        if op == "max":
            return wrap_res(max(a, b))
        raise ValueError("bin op " + op)
    if k == "tern":
        # condition is a comparison node evaluating to 0/1
        c = ev(node["c"], env)
        if c is UNDEF:
            return UNDEF
        return ev(node["a"] if c else node["b"], env)
    if k == "cast":
        a = ev(node["a"], env)
        if a is UNDEF:
            return UNDEF
        to = node["to"]
        if is_int(to):
            return wrap(int(a), to)
        return rnd32(float(a)) if to == "f32" else float(a)
    if k == "bitcast":
        a = ev(node["a"], env)
        if a is UNDEF:
            return UNDEF
        op = node["op"]
        if op == "asfloat":
            return rnd32(struct.unpack("<f", struct.pack("<I", a & 0xFFFFFFFF))[0])
        if op == "asuint":
            return struct.unpack("<I", struct.pack("<f", float(a)))[0]
        if op == "asint":
            return struct.unpack("<i", struct.pack("<f", float(a)))[0]
        raise ValueError("bitcast " + op)
    if k == "match":
        v = env.get(node["var"], UNDEF)
        if v is UNDEF:
            return UNDEF
        for pat, val in node["arms"]:
            if isinstance(pat, tuple):
                lo, hi = pat
                if lo <= v <= hi:
                    return wrap(val, t) if is_int(t) else val
            elif pat == v:
                return wrap(val, t) if is_int(t) else val
        return wrap(node["default"], t) if is_int(t) else node["default"]
    if k == "table":
        idx = ev(node["idx"], env)
        if idx is UNDEF:
            return UNDEF
        i = int(idx)
        if not (0 <= i < len(node["vals"])):
            return UNDEF
        v = node["vals"][i]
        return wrap(v, t) if is_int(t) else v
    raise ValueError("node kind " + k)


# ---------------------------------------------------------------------------
# valuation batteries and fingerprints
# ---------------------------------------------------------------------------

def tminmax(t):
    if t in FLOAT_TYPES:
        return (-3.4028235e38, 3.4028235e38) if t == "f32" else (-1e30, 1e30)
    w, s = INT_TYPES[t]
    return (-(1 << (w - 1)), (1 << (w - 1)) - 1) if s else (0, (1 << w) - 1)


def corner_points(t, rng):
    """Corner valuations for one variable of type t."""
    lo, hi = tminmax(t)
    pts = [0, 1, 2, 3, lo, hi]
    if lo < 0:
        pts += [-1, -2, lo + 1, hi - 1]
    else:
        pts += [hi - 1, hi // 2, min(hi, 255), min(hi, 0x7F)]
    if t in FLOAT_TYPES:
        pts = [float(p) for p in pts[:4]] + [0.5, -0.5, 1.5,
              float("inf"), float("-inf")]
    # seeded random points
    for _ in range(6):
        if is_int(t):
            pts.append(rng.randint(lo, hi))
        else:
            pts.append(float(rng.randint(-1000, 1000)) / 7.0)
    # de-dup
    seen, out = set(), []
    for p in pts:
        key = repr(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def fingerprint(node, envs):
    """Hash the vector of results of a node over a list of environments."""
    vals = []
    for env in envs:
        v = ev(node, env)
        vals.append("U" if v is UNDEF else repr(v))
    return tuple(vals)
