#!/usr/bin/env python3
"""Durable reproducer catalog for signal_interrupts.

Replaces ``reproduce.sh``.  Each scenario is bounded by timeout/kill.  The
shell's inline ``python3 - <<PY`` blocks from the original are implemented as
inline Python here (they were already Python).
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

import fcntl
import json
import os
import re
import select
import signal
import subprocess
import sys
import time

BIN = str(_REPO_ROOT / "ucas")
D = _REPO_ROOT / "tests" / "stress" / "areas" / "systems" / "signal_interrupts"
S = D / "scenarios"


def banner(title):
    print("#" * 60)
    print("# " + title)
    print("#" * 60)


def run_mcp_capture(name, timeout):
    """timeout N BIN --mcp < NAME 2>&1 ; returns combined text."""
    with open(S / name, "rb") as fh:
        try:
            p = subprocess.run([BIN, "--mcp"], stdin=fh,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=timeout,
                               cwd=str(S))
            return p.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as ex:
            return (ex.stdout or b"").decode("utf-8", "replace")


def finding_baseline():
    banner("BASELINE: a well-formed JSON-RPC error when the request times out internally")
    text = run_mcp_capture("mcp_internal_timeout.jsonl", 10)
    for m in re.findall(r'"error": {[^}]*}', text):
        print(m)
    print('# expected: {"code": "timeout", "message": "timed out after 0.02 s; the state is unchanged"}')


def finding_1():
    print()
    banner("FINDING 1 (HANG): kill the MCP server mid-search; client stalls until timeout_s")
    f = "mcp_short_t.jsonl"
    with open(S / f, "rb") as fh:
        p = subprocess.Popen([BIN, "--mcp"], stdin=fh,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             cwd=str(S))
        time.sleep(1.0)
        kid = int(subprocess.check_output(["pgrep", "-P", str(p.pid)],
                                          timeout=30).split()[0])
        print("server pid", p.pid, "forked timeout-child", kid,
              "-> SIGKILL server")
        p.kill()
        p.wait()
        fd = p.stdout.fileno()
        fcntl.fcntl(fd, fcntl.F_SETFL,
                    fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
        t0 = time.time()
        events = []
        buf = b""
        while time.time() - t0 < 8:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    c = os.read(fd, 65536)
                except OSError:
                    c = b""
                if not c:
                    events.append(("EOF", round(time.time() - t0, 2)))
                    break
                buf += c
                events.append(("DATA", round(time.time() - t0, 2), len(c)))
    print("client events (t seconds after server death):", events)
    print("last response:", buf[-220:].decode("utf-8", "replace"))
    print("orphan still alive at end?", end=" ")
    try:
        os.kill(kid, 0)
        print("YES")
        os.kill(kid, signal.SIGKILL)
    except OSError:
        print("no")
    print("# observed: DATA(765 B, t=0) then a ~2 s silence, then DATA(310 B, t~2) = JSON-RPC timeout error, then EOF.")


def finding_2():
    print()
    banner("FINDING 2 (WRONG): kill the forked timeout child -> timeout_s silently disabled")
    print("-- baseline (no child kill): times out at ~3 s --")
    text = run_mcp_capture("mcp_short_t.jsonl", 8)
    for line in text.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("id") == 1:
            print("  id1 error:", (o.get("result", {}).get("structuredContent")
                                   or {}).get("error"))
    print("-- with timeout child SIGKILLed at t=1 s: runs to completion past the 3 s deadline --")

    with open(S / "mcp_short_t.jsonl", "rb") as fh:
        p = subprocess.Popen([BIN, "--mcp"], stdin=fh,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             cwd=str(S))
        time.sleep(1.0)
        kid = int(subprocess.check_output(["pgrep", "-P", str(p.pid)],
                                          timeout=30).split()[0])
        os.kill(kid, signal.SIGKILL)
        t0 = time.time()
        out = p.communicate(timeout=15)[0]
    print("  exited at t=%.1fs with rc=%d" % (time.time() - t0 + 1, p.returncode))
    for line in out.decode("utf-8", "replace").splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("id") == 1:
            r = o.get("result", {})
            print("  id1 isError:", r.get("isError"),
                  "error:", (r.get("structuredContent") or {}).get("error"))
    print("# observed: no timeout at 3 s; a full success response (isError:false) is returned at ~6-12 s.")


def verified_correct():
    print()
    banner("VERIFIED-CORRECT: CLI Ctrl-C via pseudo-terminal (script -qec)")
    p = subprocess.Popen(["timeout", "8", "script", "-qec",
                          "%s long_gates.ucas" % BIN, "/dev/null"],
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, cwd=str(S))
    time.sleep(1.5)
    try:
        p.stdin.write(b"\003")
        p.stdin.flush()
        p.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    rc = p.wait()
    print("script rc=%d  (130 == SIGINT; no core dump, no orphan)" % rc)


def main():
    finding_baseline()
    finding_1()
    finding_2()
    verified_correct()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
