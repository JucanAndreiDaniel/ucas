#!/usr/bin/env python3
"""Emit MCP JSONL goldens for mode-sensitive equivalence."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

def req(i, name, args):
    return {"jsonrpc":"2.0","id":i,"method":"tools/call",
            "params":{"name":name,"arguments":args}}

def head(lines):
    return [
        {"jsonrpc":"2.0","id":0,"method":"initialize",
         "params":{"protocolVersion":"2025-06-18","capabilities":{},
                   "clientInfo":{"name":"stress","version":"1"}}},
        {"jsonrpc":"2.0","method":"notifications/initialized"},
    ] + lines

def dump(path, lines):
    with open(os.path.join(HERE, path), 'w') as f:
        for o in lines:
            f.write(json.dumps(o) + '\n')

DEFS = "\n".join([
    "# mode-sensitive pairs",
    "add0f(x: u32) = asfloat(x) + f32(0)",
    "add0g(x: u32) = asfloat(x)",
    "nanf(x: u32) = asfloat(x | 0x7fc12345)",
    "nang(x: u32) = asfloat(u32(0x7fc00000))",
    "zerof(x: u32) = asuint(asfloat(x) + f32(0))",
    "zerog(x: u32) = x",
    "minf(x: f32, y: f32) = min(x, y)",
    "ming(x: f32, y: f32) = min(y, x)",
    "ctlf(x: u32) = asfloat(x) * f32(1)",
    "ctlg(x: u32) = asfloat(x)",
])

# ---- mcp_mode_matrix.jsonl ----
L = head([req(1, "ucas", {"source": DEFS})])
i = 2
combos = [(False, False), (False, True), (True, False), (True, True)]
pairs = [
    ("add0f", "add0g"), ("nanf", "nang"), ("zerof", "zerog"),
    ("minf", "ming"), ("ctlf", "ctlg"),
]
for f, g in pairs:
    for ftz, nb in combos:
        L.append(req(i, "analyze", {"op":"equiv",
                     "args":{"f":f,"g":g,"ftz":ftz,"nanbits":nb}}))
        i += 1
dump("mcp_mode_matrix.jsonl", L)

# ---- mcp_state_leak.jsonl: alternate modes on the same pairs ----
L = head([req(1, "ucas", {"source": DEFS})])
i = 2
seq = [
    ("add0f","add0g",True,False),   # differ (ftz)
    ("add0f","add0g",False,False),  # equal (noftz)
    ("add0f","add0g",True,False),   # differ again (no leak)
    ("nanf","nang",False,True),     # differ (nanbits)
    ("nanf","nang",False,False),    # equal (no nanbits)
    ("nanf","nang",False,True),     # differ again
    ("add0f","add0g",True,True),    # ftz+n nanbits
    ("minf","ming",True,True),      # equal under all
    ("minf","ming",False,False),
    ("zerof","zerog",False,False),  # differ
    ("ctlf","ctlg",True,False),     # equal (folded)
    ("ctlf","ctlg",False,False),
    ("add0f","add0g",False,False),  # equal again (final)
]
for f, g, ftz, nb in seq:
    L.append(req(i, "analyze", {"op":"equiv",
                 "args":{"f":f,"g":g,"ftz":ftz,"nanbits":nb}}))
    i += 1
dump("mcp_state_leak.jsonl", L)

# ---- mcp_expr_misparse.jsonl: WRONG verdict via expression-string args ----
L = head([
    req(1, "analyze", {"op":"equiv", "args":{
        "f":"asfloat(x: u32) + f32(0)", "g":"asfloat(x)",
        "ftz":False, "nanbits":False}}),
    req(2, "analyze", {"op":"equiv", "args":{
        "f":"asfloat(x: u32) + f32(0)", "g":"asfloat(x)",
        "ftz":True, "nanbits":False}}),
    # correct form via object with body+params (control)
    req(3, "analyze", {"op":"equiv", "args":{
        "f":{"body":"asfloat(x) + f32(0)","params":[{"name":"x","type":"u32"}]},
        "g":{"body":"asfloat(x)","params":[{"name":"x","type":"u32"}]},
        "ftz":False, "nanbits":False}}),
])
dump("mcp_expr_misparse.jsonl", L)

# ---- mcp_aux_leak.jsonl: interleave wrap/domain/range with mode flips ----
L = head([req(1, "ucas", {"source": DEFS})])
seq = [
    (2, "analyze", {"op":"range",  "args":{"f":"add0f"}}),
    (3, "analyze", {"op":"equiv",  "args":{"f":"add0f","g":"add0g","ftz":True,"nanbits":False}}),
    (4, "analyze", {"op":"range",  "args":{"f":"add0f"}}),
    (5, "analyze", {"op":"domain", "args":{"f":"add0f"}}),
    (6, "analyze", {"op":"equiv",  "args":{"f":"nanf","g":"nang","ftz":False,"nanbits":True}}),
    (7, "analyze", {"op":"domain", "args":{"f":"nanf"}}),
    (8, "analyze", {"op":"wrap",   "args":{"f":"zerof"}}),
    (9, "analyze", {"op":"equiv",  "args":{"f":"zerof","g":"zerog","ftz":False,"nanbits":False}}),
    (10,"analyze", {"op":"wrap",   "args":{"f":"zerof"}}),
    (11,"analyze", {"op":"range",  "args":{"f":"minf"}}),
    (12,"analyze", {"op":"equiv",  "args":{"f":"minf","g":"ming","ftz":True,"nanbits":True}}),
    (13,"analyze", {"op":"range",  "args":{"f":"minf"}}),
]
for i, name, args in seq:
    L.append(req(i, name, args))
dump("mcp_aux_leak.jsonl", L)

print("wrote mcp jsonl files")
