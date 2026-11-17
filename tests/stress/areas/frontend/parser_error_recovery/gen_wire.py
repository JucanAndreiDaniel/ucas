#!/usr/bin/env python3
"""Create JSON / MCP session-recovery goldens (deterministic)."""
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
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = str(_REPO_ROOT / "ucas")


def jline(o):
    return json.dumps(o, separators=(",", ":"))


def mcp_init():
    return [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "stress", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ]


def tc(i, name, args):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call",
            "params": {"name": name, "arguments": args}}


def write(name, lines, flags=""):
    path = os.path.join(HERE, name + ".jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(jline(x) for x in lines) + "\n")
    if flags:
        with open(os.path.join(HERE, name + ".flags"), "w") as f:
            f.write(flags + "\n")
    return path


# ---- JSON frontend: parse error must not break the session -------------------
json_recovery = [
    {"id": 1, "cmd": "define", "args": {"name": "ok", "params": [{"name": "x", "type": "u8"}], "body": "x+1"}},
    {"id": 2, "cmd": "ucas", "args": {"source": "show (x +"}},
    {"id": 3, "cmd": "state", "args": {}},
    {"id": 4, "cmd": "show", "args": {"f": "ok"}},
    {"id": 5, "cmd": "define", "args": {"name": "bad", "params": [{"name": "x", "type": "u8"}], "body": "x + )"}},
    {"id": 6, "cmd": "state", "args": {}},
    {"id": 7, "cmd": "show", "args": {"f": "bad"}},
    {"id": 8, "cmd": "ucas", "args": {"source": "bad2(y: u8) = y + )\nshow bad2\nbigint 3^5"}},
    {"id": 9, "cmd": "bigint", "args": {"expr": "2^10"}},
    {"id": 10, "cmd": "parse", "args": {"expr": "x+)"}},
    {"id": 11, "cmd": "parse", "args": {"expr": "x+1"}},
]

# A failed request that still carries successful results (inconsistent ok flag).
json_mixed = [
    {"id": 1, "cmd": "ucas", "args": {"source": "bad(x: u8) = x + )\nshow bad\nbigint 3^5"}},
    {"id": 2, "cmd": "state", "args": {}},
    {"id": 3, "cmd": "show", "args": {"f": "bad"}},
    {"id": 4, "cmd": "bigint", "args": {"expr": "2^10"}},
]
write("json_mixed_result", json_mixed)
write("json_recovery", json_recovery)

# ---- MCP wrapped: same idea, plus a leaked-name check ------------------------
mcp_recovery = mcp_init()
mcp_recovery += [
    tc(1, "session", {"op": "define", "args": {"name": "good", "params": [{"name": "x", "type": "u8"}], "body": "x+2"}}),
    tc(2, "ucas", {"source": "show (x +"}),
    tc(3, "session", {"op": "state", "args": {}}),
    tc(4, "analyze", {"op": "show", "args": {"f": "good"}}),
    tc(5, "ucas", {"source": "bad2(y: u8) = y + )\nshow bad2\nbigint 3^5"}),
    tc(6, "session", {"op": "funcs", "args": {}}),
    tc(7, "analyze", {"op": "parse", "args": {"expr": "x+)"}}),
    tc(8, "analyze", {"op": "parse", "args": {"expr": "x+1"}}),
    tc(9, "ucas", {"source": "show (1 +", "\u0062igint": "ignored"} if False else {"source": "show 1 + )\nbigint 4^5"}),
]
# remove the accidental bogus key path
mcp_recovery[-1] = tc(9, "ucas", {"source": "show 1 + )\nbigint 4^5"})
write("mcp_recovery", mcp_recovery)

# ---- MCP flat: parse errors then valid ops in flat mode -----------------------
flat = mcp_init()
flat += [
    tc(1, "define", {"name": "f", "params": [{"name": "x", "type": "u8"}], "body": "x*2"}),
    tc(2, "show", {"f": "f"}),
    tc(3, "parse", {"expr": "show (x +"}),
    tc(4, "parse", {"expr": "x+1"}),
    tc(5, "state", {}),
    tc(6, "bigint", {"expr": "2^20"}),
    tc(7, "range", {"f": "f"}),
    tc(8, "equiv", {"f": "(x*y)^5", "g": "(y*x)^5"}),
]
write("mcp_flat_recovery", flat, flags="--flat")

# ---- MCP: unterminated string / bad unicode then valid over the wire ----------
wire_bad = mcp_init()
wire_bad += [
    tc(1, "ucas", {"source": 'show "unterminated'}),
    tc(2, "session", {"op": "state", "args": {}}),
    tc(3, "ucas", {"source": "parse \u221e"}),
    tc(4, "session", {"op": "state", "args": {}}),
    tc(5, "analyze", {"op": "parse", "args": {"expr": "x+1"}}),
]
write("mcp_bad_lex_wire", wire_bad)

# ---- capture goldens twice and verify determinism -----------------------------
def capture(name, flags):
    jsonl = os.path.join(HERE, name + ".jsonl")
    if name.startswith("json_"):
        cmd = [BIN, "--json", "--files", "none"]
    else:
        cmd = [BIN, "--mcp"] + (flags.split() if flags else [])
    outs = []
    for _ in range(2):
        with open(jsonl, "rb") as f:
            r = subprocess.run(cmd, stdin=f, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=30)
        outs.append((r.returncode, r.stdout))
    if outs[0] == outs[1] and outs[0][0] == 0:
        with open(os.path.join(HERE, name + ".out"), "wb") as f:
            f.write(outs[0][1])
        return "ok"
    return "NONDET/CRASH " + str([o[0] for o in outs])


for n, fl in [("json_recovery", ""), ("json_mixed_result", ""),
              ("mcp_recovery", ""), ("mcp_flat_recovery", "--flat"),
              ("mcp_bad_lex_wire", "")]:
    print(n, capture(n, fl))
