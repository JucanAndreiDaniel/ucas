#!/usr/bin/env python3
"""Shared helper for the cli_args_fuzz reproducers.

A cli script imports ``probe`` and populates ``VARS`` with variables such as
REQ and INIT.  ``probe`` expands the double-quoted command string as a shell
would (so ``$B``/``$REQ``/``\\$``/``\\"`` behave identically), then runs the
resulting string under ``sh -c`` with stdout+stderr merged and a 15-second
subprocess timeout.  The golden is the concatenation of every report:

    \\n===== LABEL =====\\n
    exit=N
    <merged stdout+stderr bytes>
"""

import os
import re
import subprocess
import sys
import tempfile
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


# Anchor ROOT on __file__ so the helper works from any current directory.
ROOT = _find_root(Path(__file__).resolve())
B = str(ROOT / "ucas")

# The suite runner exports these for the whole stress suite; set them here so
# the reproducers are self-contained and byte-identical when run directly.
ENV = os.environ.copy()
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"

# Variables expanded inside the command strings by ``_expand``.  B is always
# the binary path; each cli script adds its own (REQ, INIT, ...).
VARS = {"B": B}

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _expand(raw):
    """Emulate POSIX double-quote expansion of the raw command-string text."""
    out = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == "\\":
            if i + 1 < n:
                nxt = raw[i + 1]
                if nxt in ('$', '`', '"', '\\'):
                    out.append(nxt)
                    i += 2
                    continue
                if nxt == "\n":
                    i += 2
                    continue
            out.append("\\")
            i += 1
            continue
        if c == "$":
            m = _VAR_RE.match(raw, i)
            if m:
                name = m.group(1) or m.group(2)
                out.append(VARS.get(name, ""))
                i = m.end()
                continue
            out.append("$")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def probe(label, command):
    command = _expand(command)
    w = sys.stdout.buffer
    w.write(f"\n===== {label} =====\n".encode("utf-8"))
    w.flush()
    # Capture into a temporary file and read it back; this keeps output
    # byte-exact and avoids pipe hangs on a timeout.
    with tempfile.TemporaryFile() as pf:
        try:
            p = subprocess.run(
                ["sh", "-c", command],
                stdout=pf,
                stderr=subprocess.STDOUT,
                timeout=15,
                env=ENV,
            )
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
        pf.seek(0)
        out = pf.read()
    w.write(f"exit={rc}\n".encode("ascii"))
    w.write(out)
    w.flush()
