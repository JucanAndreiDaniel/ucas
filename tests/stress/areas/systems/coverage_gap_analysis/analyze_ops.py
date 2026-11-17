#!/usr/bin/env python3
"""Compare the authoritative MCP tool list against tool names actually invoked
by the accumulated .jsonl corpus. Emits ranked 'never reached op' lists."""
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
import json, glob, os, collections

HERE = str(_HERE)
ROOT = str(_REPO_ROOT)

# tool names from tools/list (JSONL: initialize / initialized / tools/list)
raw = None
for line in open(os.path.join(HERE, "reports", "tools_list.json")):
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except Exception:
        continue
    if o.get("id") == 1 and "result" in o and "tools" in o["result"]:
        raw = o
if raw is None:
    raise SystemExit("no tools/list result found")
tools = [t["name"] for t in raw["result"]["tools"]]
all_tools = set(tools)
json.dump({"tools": tools}, open(os.path.join(HERE, "reports", "tool_names.json"), "w"), indent=1)

# tool names invoked in corpus .jsonl
called = collections.Counter()
for f in glob.glob(os.path.join(ROOT, "tests", "stress", "*", "*.jsonl")) + \
         glob.glob(os.path.join(ROOT, "tests", "json", "*.jsonl")) + \
         glob.glob(os.path.join(ROOT, "tests", "mcp", "*.jsonl")):
    for line in open(f, errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        # MCP tools/call
        p = o.get("params") if isinstance(o, dict) else None
        nm = None
        if isinstance(p, dict):
            nm = p.get("name")
        if not isinstance(o, dict):
            continue
        if o.get("method") == "tools/call" and nm:
            called[nm] += 1
        # flat mode / json frontend: "cmd" or "op" top-level
        elif isinstance(o, dict):
            for k in ("cmd", "op", "tool"):
                if k in o and isinstance(o[k], str):
                    called[o[k]] += 1
            if isinstance(p, dict):
                for k in ("cmd", "op", "tool"):
                    if k in p and isinstance(p[k], str):
                        called[p[k]] += 1

never = sorted(all_tools - set(called))
print(f"TOTAL MCP TOOLS: {len(all_tools)}")
print(f"MCP TOOLS CALLED IN CORPUS: {len(set(called) & all_tools)}")
print(f"MCP TOOLS NEVER CALLED: {len(never)}")
for t in never:
    print("  " + t)

# All 248 jcmd op names vs what the JSONL corpus invokes by name
jcmds = [l.split("\t")[0] for l in open(os.path.join(HERE, "reports", "jcmd_names.txt"))
         if l.strip() and l.strip()[0].isdigit() is False]
# first line of jcmd_names.txt is a count; skip it
with open(os.path.join(HERE, "reports", "jcmd_names.txt")) as f:
    lines = [l.rstrip("\n") for l in f if l.strip()]
jcmds = [l for l in lines[1:]]
jcmds_set = set(jcmds)
jcmd_called = set(called) & jcmds_set
jcmd_never = sorted(jcmds_set - jcmd_called)
print(f"\nTOTAL JCMD OPS: {len(jcmds_set)}")
print(f"JCMD OPS CALLED BY NAME IN JSONL: {len(jcmd_called)}")
print(f"JCMD OPS NEVER CALLED BY NAME IN JSONL: {len(jcmd_never)}")
for t in jcmd_never:
    print("  " + t)

out = {
    "total_tools": len(all_tools),
    "called": sorted(set(called) & all_tools),
    "never_called": never,
    "total_jcmd": len(jcmds_set),
    "jcmd_never_by_name": jcmd_never,
    "call_counts": dict(called),
}
json.dump(out, open(os.path.join(HERE, "reports", "ops_analysis.json"), "w"), indent=1)
