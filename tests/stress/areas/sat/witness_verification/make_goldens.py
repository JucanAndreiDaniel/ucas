#!/usr/bin/env python3
"""Create (and determinism-check) the CLI + MCP golden files for this area."""
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

import os
import json
import subprocess

import verify_witnesses as V

BIN = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))

# Selected clean, deterministic cases (ids from verify_witnesses.build_cases).
SELECTED = [
    ("01_equiv_counter", "EQ_WRAP_00"),
    ("02_equiv_equal", "EQ_EQ_00"),
    ("03_wrap_witnesses", "WR_OV_01"),
    ("04_domain_undefined", "DM_00"),
    ("05_crit_extrema", "CR_X_00"),
    ("06_range_values", "RG_X_00"),
    ("07_error_worst", "ER_00"),
    ("08_fit_worst", "FT_00"),
]


def run_file(name):
    """Run exactly as SPEC.md prescribes: ucas NAME.ucas (from this folder)."""
    p = subprocess.run([BIN, name + ".ucas"], cwd=HERE, text=True,
                       capture_output=True, timeout=30)
    return p.stdout + p.stderr


def main():
    cases = {c["id"]: c for c in V.build_cases()}
    determinism = []
    for name, cid in SELECTED:
        src = V.case_source(cases[cid], with_table=False)
        if name == "08_fit_worst":
            # `fit` needs free parameters in the fitted expression itself.
            src = "f(x: u8) = x*x\nfit a*x + b ~ f\n"
        with open(os.path.join(HERE, name + ".ucas"), "w") as f:
            f.write(src)
        out1 = run_file(name)
        out2 = run_file(name)
        det = out1 == out2
        determinism.append((name, det))
        if not det:
            print(f"NONDETERMINISTIC: {name} -- NOT writing golden")
            continue
        with open(os.path.join(HERE, name + ".out"), "w") as f:
            f.write(out1)
        print(f"wrote {name}.ucas/.out ({len(out1)} bytes, deterministic)")

    # MCP golden: define typed functions, then exercise each witness-producing
    # op in one JSONL session.
    lines = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "stress", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ]
    _did = [10]
    def define(name, body, ty="u8"):
        _did[0] += 1
        return {"jsonrpc": "2.0", "id": _did[0], "method": "tools/call",
                "params": {"name": "session", "arguments": {
                    "op": "define", "args": {"name": name,
                    "params": [{"name": "x", "type": ty}], "body": body}}}}
    def analyze(i, op, args):
        return {"jsonrpc": "2.0", "id": i, "method": "tools/call",
                "params": {"name": "analyze", "arguments": {"op": op, "args": args}}}
    lines += [
        define("f", "x*x"), define("g", "x*x+1"), define("q", "100/(x-3)"),
        analyze(1, "equiv", {"f": "f", "g": "g"}),
        analyze(2, "wrap", {"f": "f"}),
        analyze(3, "domain", {"f": "q"}),
        analyze(4, "range", {"f": "f"}),
        analyze(5, "crit", {"f": "f"}),
        analyze(6, "error", {"g": "g", "f": "f"}),
    ]
    jsonl = "\n".join(json.dumps(l) for l in lines) + "\n"
    with open(os.path.join(HERE, "mcp_witnesses.jsonl"), "w") as f:
        f.write(jsonl)
    # Run it twice for determinism.
    def run_mcp():
        p = subprocess.run([BIN, "--mcp"], input=jsonl, text=True,
                           capture_output=True, timeout=30)
        return p.stdout + p.stderr
    o1, o2 = run_mcp(), run_mcp()
    det = o1 == o2
    determinism.append(("mcp_witnesses", det))
    print(f"mcp deterministic: {det}")
    with open(os.path.join(HERE, "mcp_witnesses.out"), "w") as f:
        f.write(o1 if det else "NONDETERMINISTIC (see FINDINGS.md)\n" + o1)

    print("\nDeterminism summary:", determinism)


if __name__ == "__main__":
    main()
