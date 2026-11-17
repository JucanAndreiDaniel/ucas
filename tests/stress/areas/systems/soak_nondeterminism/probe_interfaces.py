#!/usr/bin/env python3
"""One-off probe: discover how --json and --mcp processes behave over a pipe."""
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
import json, subprocess, sys, os

BIN = str(_REPO_ROOT / "ucas")

def drain_line(p, timeout=5.0):
    import select
    r, _, _ = select.select([p.stdout], [], [], timeout)
    if not r:
        return None
    line = p.stdout.readline()
    return line

def probe_json():
    print("=== --json ===")
    p = subprocess.Popen([BIN, "--json", "--files", "none"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1)
    cmds = [
        {"id": 1, "cmd": "bigint", "args": {"expr": "2^10"}},
        {"id": 2, "cmd": "define", "args": {"name": "f", "params": [{"name":"x","type":"u8"}], "body": "x+1"}},
        {"id": 3, "cmd": "range", "args": {"f": "f"}},
    ]
    for c in cmds:
        p.stdin.write(json.dumps(c) + "\n"); p.stdin.flush()
        line = drain_line(p, 5.0)
        print("IN ", json.dumps(c))
        print("OUT", repr(line))
    # Try a command that might produce multiple lines (english?)
    for c in [{"id":4,"cmd":"parse","args":{"f":"x+1"}}]:
        p.stdin.write(json.dumps(c)+"\n"); p.stdin.flush()
        line=drain_line(p,5.0)
        print("IN ",json.dumps(c)); print("OUT",repr(line))
    p.stdin.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
    print("stderr:", repr(p.stderr.read()[:500]))
    print("rc:", p.returncode)

def probe_mcp():
    print("=== --mcp ===")
    p = subprocess.Popen([BIN, "--mcp"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1)
    def send(obj):
        p.stdin.write(json.dumps(obj)+"\n"); p.stdin.flush()
    def recv(t=5.0):
        return drain_line(p, t)
    init={"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}
    send(init); print("INIT OUT", repr(recv()))
    send({"jsonrpc":"2.0","method":"notifications/initialized"})
    print("notif sent (no response expected)")
    calls=[
      (1,{"name":"tools/call","params":{"name":"session","arguments":{"op":"define","args":{"name":"f","params":[{"name":"x","type":"u8"}],"body":"x+1"}}}}),
      (2,{"name":"tools/call","params":{"name":"english","arguments":{"text":"what is f of 3?"}}}),
      (3,{"name":"tools/call","params":{"name":"session","arguments":{"op":"state"}}}),
    ]
    for id_,method in calls:
        send({"jsonrpc":"2.0","id":id_,"method":method["name"],"params":method["params"]})
        print("CALL",id_,repr(recv()))
    p.stdin.close()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
    print("stderr:",repr(p.stderr.read()[:500]))
    print("rc:",p.returncode)

if __name__=="__main__":
    probe_json()
    probe_mcp()
