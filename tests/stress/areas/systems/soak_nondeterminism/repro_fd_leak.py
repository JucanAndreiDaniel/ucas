#!/usr/bin/env python3
"""Reproducer: --json and --mcp long-lived processes leak one FD per reset.

Watch the FD count of one process climb linearly as `reset` (or MCP
`session reset`) is issued repeatedly.  No other command leaks: defining new
functions, bigint, english, state, assume all plateau at a fixed FD count.

Usage:  python3 repro_fd_leak.py [n]      (default n = 200)
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
import json, os, select, subprocess, sys

BIN = str(_REPO_ROOT / "ucas")

def fds(pid):
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except (PermissionError, FileNotFoundError, ProcessLookupError):
        return -1

def readline(p, t=10):
    r, _, _ = select.select([p.stdout], [], [], t)
    return p.stdout.readline() if r else None

def run(mode, n):
    if mode == "json":
        p = subprocess.Popen([BIN, "--json", "--files", "none"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, bufsize=1)
        def issue(i):
            p.stdin.write(json.dumps({"id": i + 1, "cmd": "reset", "args": {}}) + "\n")
            p.stdin.flush()
            return readline(p)
    else:
        p = subprocess.Popen([BIN, "--mcp"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, bufsize=1)
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "repro", "version": "1"}}}) + "\n"); p.stdin.flush(); readline(p)
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"); p.stdin.flush()
        def issue(i):
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i + 1, "method": "tools/call",
                "params": {"name": "session", "arguments": {"op": "reset"}}}) + "\n")
            p.stdin.flush()
            return readline(p)
    start = fds(p.pid)
    peak = start
    for i in range(n):
        issue(i)
        peak = max(peak, fds(p.pid))
    end = fds(p.pid)
    p.stdin.close(); p.wait(timeout=5)
    print(f"{mode:4s}: FDs start={start} end={end} peak={peak} "
          f"delta=+{end-start} after {n} resets")
    return end - start

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    run("json", n)
    run("mcp", n)
