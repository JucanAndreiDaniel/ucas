#!/usr/bin/env python3
"""Create golden inputs, run them twice, keep .out only when deterministic."""
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
import os, subprocess, hashlib, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = str(_REPO_ROOT / "ucas")

UCAS = {
"01_unsigned_divmod": """f(x: u8 in 0..11) = x / 3
table f
g(x: u8 in 0..11) = x % 3
table g
h(x: u8 in 0..7) = x / 8
table h
k(x: u8 in 0..7) = x % 8
table k
range f
""",
"02_signed_divmod": """f(x: i8 in -8..8) = x / 3
table f
g(x: i8 in -8..8) = x % 3
table g
h(x: i8 in -4..4) = x / -2
table h
m(x: i8) = x / -1
range m
wrap m
domain m
""",
"03_identities": """f(x: i8) = (x/3)*3 + x%3
id(x: i8) = x
equiv f id
g(x: i8) = x/2
s(x: i8) = x>>1
equiv g s
p(x: u8) = x%8
q(x: u8) = x&7
equiv p q
r(x: i8) = (-x)/3
t(x: i8) = -(x/3)
equiv r t
""",
"04_mixed_signs": """f(x: i8 in -4..4, y: u8 in 1..3) = x / y
show f
table f
g(x: u8 in 0..8, y: i8 in -3..-1) = x / y
show g
table g
""",
"05_zero_domain": """f(x: u8 in 0..3) = x / 0
domain f
range f
g(x: u8, y: u8 in 0..3) = x / y
domain g
h(x: i8 in -3..3) = x % (x-x)
domain h
""",
"06_magic": """magic 3 u8
magic 3 i8
magic 7 u32
magic 10 i32
""",
"07_rem_quo_constants": """rem 7, 3
rem -7, 3
quo 7, 3
quo -7, 3
rem 10, 3
rem 8, 4
""",
}

JSONL = {
"mcp_divmod": [
 {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}},
 {"jsonrpc":"2.0","method":"notifications/initialized"},
 {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"table","args":{"f":{"body":"x / 3","params":[{"name":"x","type":"u8","range":[0,7]}]}}}}},
 {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"equiv","args":{"f":{"body":"(x/3)*3 + x%3","params":[{"name":"x","type":"i8"}]},"g":{"body":"x","params":[{"name":"x","type":"i8"}]}}}}},
 {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"range","args":{"f":{"body":"x / -1","params":[{"name":"x","type":"i8"}]}}}}},
 {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"domain","args":{"f":{"body":"x / y","params":[{"name":"x","type":"u8"},{"name":"y","type":"u8","range":[0,3]}]}}}}},
 {"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"wrap","args":{"f":{"body":"x / -1","params":[{"name":"x","type":"i8"}]}}}}},
],
"mcp_rings_magic": [
 {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}},
 {"jsonrpc":"2.0","method":"notifications/initialized"},
 {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"rings","arguments":{"op":"magic","args":{"divisor":3,"type":"u8"}}}},
 {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"rings","arguments":{"op":"magic","args":{"divisor":7,"type":"i32"}}}},
 {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"rings","arguments":{"op":"magic","args":{"divisor":10,"type":"i32"}}}},
],
}

def run(srcfile, args, outfile):
    with open(srcfile,'rb') as f: data=f.read()
    outs=[]
    for _ in range(2):
        p=subprocess.run([BIN,*args], input=data, capture_output=True, timeout=30, cwd=HERE)
        outs.append(p.stdout + p.stderr)
    if outs[0]!=outs[1]:
        print("NONDET", srcfile); return False
    with open(outfile,'wb') as f: f.write(outs[0])
    print("OK", os.path.basename(srcfile), len(outs[0]), "bytes")
    return True

def main():
    ok=True
    for name, src in UCAS.items():
        s=os.path.join(HERE,name+".ucas"); o=os.path.join(HERE,name+".out")
        with open(s,'w') as f: f.write(src)
        if not run(s,[name+".ucas"],o): ok=False
    for name, lines in JSONL.items():
        s=os.path.join(HERE,name+".jsonl"); o=os.path.join(HERE,name+".out")
        with open(s,'w') as f:
            for x in lines: f.write(json.dumps(x)+"\n")
        if not run(s,["--mcp"],o): ok=False
    return ok

import json
if __name__=="__main__":
    sys.exit(0 if main() else 1)
