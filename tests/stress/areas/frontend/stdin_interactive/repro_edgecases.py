#!/usr/bin/env python3
"""Manual reproducers for the CRASH / SIGPIPE / LIMIT findings (NOT goldens).

Every binary run is bounded by a subprocess timeout; see FINDINGS.md.
"""

import os
import shlex
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

PAYLOAD = b"(" * 1600 + b"1" + b")" * 1600


def run_bin(data=None, args=(), discard=True):
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                  timeout=10, cwd=str(HERE), env=ENV)
    if data is not None:
        kwargs["input"] = data
    if not discard:
        kwargs["stdout"] = subprocess.PIPE
    try:
        return subprocess.run([str(BIN), *args], **kwargs).returncode
    except subprocess.TimeoutExpired:
        return 124


def cat_a(data):
    p = subprocess.run(["cat", "-A"], input=data, stdout=subprocess.PIPE,
                       timeout=10, env=ENV)
    sys.stdout.buffer.write(p.stdout)
    sys.stdout.buffer.flush()


def shell_rc(rc):
    """Python reports a signal death as -N; the shell reported 128+N."""
    return 128 - rc if rc < 0 else rc


def main():
    w = sys.stdout.buffer

    def emit(s):
        w.write(s.encode() if isinstance(s, str) else s)
        w.flush()

    emit("=== CRASH: ~1600 nested parens on stdin -> SIGSEGV ===\n")
    rc = shell_rc(run_bin(data=PAYLOAD))
    emit(f"exit={rc} (139 = SIGSEGV)\n")

    emit("=== CRASH: same via a file argument ===\n")
    deep = Path("/tmp/ucas_deep.ucas")
    deep.write_bytes(PAYLOAD)
    rc = shell_rc(run_bin(args=(str(deep),)))
    emit(f"exit={rc}\n")
    deep.unlink(missing_ok=True)

    emit("=== SIGPIPE: reader closes early ===\n")
    # PIPESTATUS is bash-specific, so run this exact pipeline under bash to
    # preserve the three exit statuses the original printed.
    cmd = (f"yes '1+1' | timeout 10 {shlex.quote(str(BIN))} 2>/dev/null | head -1; "
           'echo "pipeline exits (yes ucas head)=${PIPESTATUS[*]}"')
    subprocess.run(["bash", "-c", cmd], timeout=15, cwd=str(HERE), env=ENV)

    emit("=== LIMIT: backslash line continuation is broken in the REPL ===\n")
    try:
        p = subprocess.run([str(BIN)], input=b"1 + \\\n2\n",
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=10, cwd=str(HERE), env=ENV)
        cat_a(p.stdout)
    except subprocess.TimeoutExpired:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
