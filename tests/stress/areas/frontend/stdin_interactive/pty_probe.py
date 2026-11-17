#!/usr/bin/env python3
"""Manual pseudo-terminal probes (NOT a golden: tty echo ordering under
`script -qec` is racy).  Run by hand to reproduce the two prompt findings.
See FINDINGS.md.  Every run is bounded by a subprocess timeout.
"""

import os
import subprocess
import sys
from pathlib import Path


def _find_root(start):
    p = Path(start).resolve()
    while True:
        if (p / "ucas").is_file() and (p / "src").is_dir():
            return p
        parent = p.parent
        if parent == p:
            raise SystemExit("cannot find repo root")
        p = parent


HERE = Path(__file__).resolve().parent
ROOT = _find_root(HERE)
BIN = ROOT / "ucas"

ENV = os.environ.copy()
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def cat_a(data):
    """Equivalent of piping bytes through `cat -A`."""
    p = subprocess.run(["cat", "-A"], input=data, stdout=subprocess.PIPE,
                       timeout=10, env=ENV)
    sys.stdout.buffer.write(p.stdout)
    sys.stdout.buffer.flush()


def script_run(cmd, data, discard=False, timeout=10):
    """Run `printf data | timeout N script -qec cmd /dev/null`.

    The shell wrapped `script` in the `timeout` utility (SIGTERM, so `script`
    prints its "Session terminated" message); keep that here and use Python's
    timeout only as a backstop so the captured bytes stay identical.
    """
    kwargs = dict(input=data, stderr=subprocess.STDOUT, timeout=timeout + 5,
                  cwd=str(HERE), env=ENV)
    if discard:
        kwargs["stdout"] = subprocess.DEVNULL
    else:
        kwargs["stdout"] = subprocess.PIPE
    try:
        return subprocess.run(["timeout", str(timeout), "script", "-qec", cmd,
                               "/dev/null"], **kwargs)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess([], 124, stdout=(e.stdout or b""))


def main():
    w = sys.stdout.buffer

    w.write(b"=== 1. both stdin+stdout tty: prompts appear ===\n")
    p = script_run(str(BIN), b"1+2\n")
    cat_a(p.stdout)

    w.write(b"=== 2. stdin tty, stdout redirected: prompt leaks into the file ===\n")
    leak = HERE / "pty_leak.txt"
    leak.unlink(missing_ok=True)
    script_run(f"{BIN} > {leak}", b"1+2\n", discard=True)
    w.write(b"-- pty_leak.txt --\n")
    cat_a(leak.read_bytes() if leak.is_file() else b"")

    w.write(b"=== 3. stdin tty, stdout redirected, ambiguous English uses default ===\n")
    leak2 = HERE / "pty_leak2.txt"
    leak2.unlink(missing_ok=True)
    script_run(f"{BIN} > {leak2}", b"the square root of x plus 1\n", discard=True)
    w.write(b"-- pty_leak2.txt --\n")
    cat_a(leak2.read_bytes() if leak2.is_file() else b"")

    w.write(b"=== 4. tty ambiguity question consumes the next input line ===\n")
    p = script_run(str(BIN), b"the square root of x plus 1\n7+7\n")
    cat_a(p.stdout)

    w.write(b"=== 5. Ctrl-D immediately (empty input) ===\n")
    p = script_run(str(BIN), b"")
    cat_a(p.stdout)

    w.write(b"=== 6. Ctrl-D mid-expression ===\n")
    p = script_run(str(BIN), b"1 + (2 *")
    cat_a(p.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
