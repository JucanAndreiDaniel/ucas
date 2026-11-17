#!/usr/bin/env python3
"""Reliable reproducer for the timeout-child reply-stream desync (Top priority #2).

The worker forked by `timeout_s` writes its success reply to stdout, then signals
the waiter; when the deadline lands at the same instant as the worker finishing,
the waiter ALSO emits a timeout reply with the same id.  Two replies for one
request shift every later id.  The race window is widest when timeout_s is near
the request's own runtime: `english "factor (x+1)^20"` takes ~0.3 ms, so a
sub-millisecond timeout_s (0.0005 s) desyncs 30-40/40 request pairs.

Usage: python3 repro_desync_systematic.py [pairs] [mode|all]
       mode in {json, mcp, flat}; default all.
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
import json, os, select, signal, subprocess, sys
BIN = str(_REPO_ROOT / "ucas")
TS = 0.0005

def readline(p, t=3):
    r, _, _ = select.select([p.stdout], [], [], t)
    return p.stdout.readline() if r else None

def spawn(mode):
    flags = ["--json", "--files", "none"] if mode == "json" else (
            ["--mcp", "--flat"] if mode == "flat" else ["--mcp"])
    p = subprocess.Popen([BIN] + flags, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, bufsize=1, start_new_session=True)
    if mode != "json":
        p.stdin.write(json.dumps({"jsonrpc":"2.0","id":0,"method":"initialize",
            "params":{"protocolVersion":"2025-06-18","capabilities":{},
                      "clientInfo":{"name":"repro","version":"1"}}})+"\n")
        p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\n")
        p.stdin.flush(); readline(p); readline(p)
    return p

def mk(mode, rid, op, args):
    if mode == "json":
        return {"id": rid, "cmd": op, "args": args}
    if mode == "flat":
        return {"jsonrpc":"2.0","id":rid,"method":"tools/call",
                "params":{"name":op,"arguments":args}}
    if op == "bigint":  # grouped MCP exposes bigint via the `ucas` tool
        return {"jsonrpc":"2.0","id":rid,"method":"tools/call",
                "params":{"name":"ucas","arguments":{"source":"bigint 2^200+1"}}}
    return {"jsonrpc":"2.0","id":rid,"method":"tools/call",
            "params":{"name":op,"arguments":args}}

def rid_of(line):
    if not line: return None
    try: return json.loads(line).get("id")
    except Exception: return "BADJSON"

def code_of(line):
    if not line: return None
    try:
        o = json.loads(line); r = o.get("result")
        sc = r.get("structuredContent") if isinstance(r, dict) else None
        env = sc if isinstance(sc, dict) else o
        return (env.get("error") or {}).get("code")
    except Exception: return None

def trial(mode, pairs):
    p = spawn(mode); mism = 0; first = None; dup = 0; codes = {}
    try:
        for i in range(pairs):
            tid = 2 + 2*i; bid = tid + 1
            tr = mk(mode, tid, "english", {"text":"factor (x+1)^20", "timeout_s":TS})
            p.stdin.write(json.dumps(tr)+"\n"); p.stdin.flush(); tl = readline(p)
            br = mk(mode, bid, "bigint", {"expr":"2^200+1"})
            p.stdin.write(json.dumps(br)+"\n"); p.stdin.flush(); bl = readline(p)
            for c in (code_of(tl), code_of(bl)):
                if c: codes[c] = codes.get(c, 0) + 1
            if rid_of(tl) != tid or rid_of(bl) != bid:
                mism += 1
                if first is None:
                    first = f"cycle={i} timeout_req={tid} timeout_reply={rid_of(tl)} " \
                            f"bigint_req={bid} bigint_reply={rid_of(bl)}"
        while True:
            r, _, _ = select.select([p.stdout], [], [], 0.15)
            if not r: break
            if not p.stdout.readline(): break
            dup += 1
    finally:
        try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception: pass
        p.wait(timeout=4)
    return mism, first, dup, codes

def main():
    pairs = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    modes = ["json", "mcp", "flat"] if which == "all" else [which]
    print(f"pairs={pairs}  timeout_s={TS}  op=english 'factor (x+1)^20'")
    for m in modes:
        mism, first, dup, codes = trial(m, pairs)
        print(f"  {m:5s}: desync={mism}/{pairs}  extra_reply_lines={dup}  codes={codes}")
        print(f"         first: {first}")

if __name__ == "__main__":
    main()
