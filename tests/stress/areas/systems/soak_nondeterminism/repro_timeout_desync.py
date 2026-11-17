#!/usr/bin/env python3
"""Reproducer: `timeout_s` requests corrupt a long-lived JSON/MCP session.

The request runs in a forked child.  After enough timed-out requests the
process's one-line-per-request reply stream desynchronises: replies carry the
WRONG `id`, so a later, completely deterministic request (bigint 2^200+1) can
receive an error reply and report ok:false.  Timed-out children also linger.

Usage:  python3 repro_timeout_desync.py [pairs]   (default 60)
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

def readline(p, t=8):
    r, _, _ = select.select([p.stdout], [], [], t)
    return p.stdout.readline() if r else None

def children(pid):
    try:
        out = subprocess.run(["ps", "--ppid", str(pid), "-o", "pid="],
                             capture_output=True, text=True, timeout=3).stdout
        return [x for x in out.split() if x.strip()]
    except Exception:
        return []

def main():
    pairs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    p = subprocess.Popen([BIN, "--json", "--files", "none"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1)
    seq = 0
    desync = 0
    first = None
    for c in range(pairs):
        seq += 1; tid = seq
        p.stdin.write(json.dumps({"id": tid, "cmd": "english",
            "args": {"text": "factor (x+1)^20", "timeout_s": 0.001}}) + "\n")
        p.stdin.flush()
        tr = readline(p)
        seq += 1; bid = seq
        p.stdin.write(json.dumps({"id": bid, "cmd": "bigint",
            "args": {"expr": "2^200 + 1"}}) + "\n")
        p.stdin.flush()
        br = readline(p)
        tro = json.loads(tr) if tr else {}
        bro = json.loads(br) if br else {}
        if tro.get("id") != tid or bro.get("id") != bid:
            desync += 1
            if first is None:
                first = (c, tid, tro.get("id"), tro.get("ok"),
                         bid, bro.get("id"), bro.get("ok"))
    kids = children(p.pid)
    print(f"pairs={pairs}  desynced_pairs={desync}")
    print("first desync (cycle, timeout_req_id, timeout_resp_id, timeout_ok, "
          "bigint_req_id, bigint_resp_id, bigint_ok):")
    print("  ", first)
    print(f"lingering child processes after {pairs} timeouts: {len(kids)}")
    p.stdin.close(); p.wait(timeout=5)

if __name__ == "__main__":
    main()
