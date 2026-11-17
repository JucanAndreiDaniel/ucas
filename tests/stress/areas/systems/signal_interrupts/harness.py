#!/usr/bin/env python3
"""Run a command in the background, signal it after a delay, capture status.

Replaces ``harness.sh`` (and its ``_scratch`` copy).
Usage: harness.py SIG DELAY OUT_PREFIX -- CMD ARGS...
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

import os
import signal
import subprocess
import sys
import time

# Equivalent of date +%s%N used by the original for elapsed_ms.


def pgrep_children(pid):
    try:
        p = subprocess.run(["pgrep", "-P", str(pid)], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=30)
        kids = [x for x in p.stdout.decode().split() if x]
    except (OSError, subprocess.TimeoutExpired):
        kids = []
    kids.sort()
    return kids


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wc(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return len(data), data.count(b"\n")


def tail4_prefixed(path):
    with open(path, "rb") as fh:
        lines = fh.read().splitlines()
    lines = lines[-4:]
    if not lines:
        return ""
    return "\n".join("  | " + ln.decode("utf-8", "replace") for ln in lines) + "\n"


def signal_number(sig):
    try:
        if sig.isdigit():
            return int(sig)
        return int(signal.Signals[sig])
    except (KeyError, ValueError):
        return signal.SIGTERM


def main(argv):
    if len(argv) < 4:
        print("usage: harness.py SIG DELAY OUT_PREFIX -- CMD ARGS...",
              file=sys.stderr)
        return 2
    sig, delay, prefix = argv[0], argv[1], argv[2]
    rest = argv[3:]
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not rest:
        print("no command given", file=sys.stderr)
        return 2

    out_path = prefix + ".out"
    err_path = prefix + ".err"
    meta_path = prefix + ".meta"

    start = time.time_ns()
    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        p = subprocess.Popen(rest, stdout=out, stderr=err)
        time.sleep(float(delay))
        alive_before = p.poll() is None
        if alive_before:
            try:
                p.send_signal(signal_number(sig))
            except (OSError, ProcessLookupError):
                pass
            kill_sent = 1
        else:
            kill_sent = 0

        kids = pgrep_children(p.pid)             # KIDS_BEFORE
        rc = p.wait()
        if rc < 0:                               # shell $? reports 128+signal
            rc = 128 - rc
        end = time.time_ns()
    time.sleep(0.3)

    orphans = [k for k in kids if alive(int(k))]
    kids_str = " ".join(kids) + (" " if kids else "")
    orphans_str = "".join(" " + k for k in orphans)

    out_bytes, out_lines = wc(out_path)
    err_bytes, _ = wc(err_path)
    elapsed_ms = (end - start) // 1_000_000

    meta = (
        "signal=%s delay=%s kill_sent=%s\n"
        "pid=%d rc=%d elapsed_ms=%d\n"
        "out_bytes=%d out_lines=%d\n"
        "err_bytes=%d\n"
        "children_at_signal=[%s] orphans=[%s]\n"
        "stdout_tail:\n"
        "%s"
        "stderr_tail:\n"
        "%s"
    ) % (sig, delay, kill_sent, p.pid, rc, elapsed_ms,
         out_bytes, out_lines, err_bytes, kids_str, orphans_str,
         tail4_prefixed(out_path), tail4_prefixed(err_path))

    with open(meta_path, "w") as fh:
        fh.write(meta)
    sys.stdout.write(meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
