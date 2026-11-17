#!/usr/bin/env python3
"""Regenerate every golden in this folder (ported from gen_goldens.sh).

Run from this folder.  All commands run with cwd = this folder so any GIF/PNG
the tools write stays here.  Not run as part of the conversion.
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

U = ROOT / ".claude" / "skills" / "ucas" / "ucas.sh"
BIN = ROOT / "ucas"
MC = ROOT / "tools" / "mcp_client.py"
UC = ROOT / "tools" / "ucas_client.py"

ENV = os.environ.copy()
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def run(cmd, outfile, stdin=None):
    """Run cmd bounded by 30s, writing merged stdout+stderr to outfile."""
    with open(HERE / outfile, "wb") as g:
        try:
            p = subprocess.run(cmd, input=stdin, stdout=g,
                               stderr=subprocess.STDOUT, timeout=30,
                               cwd=str(HERE), env=ENV)
            return p.returncode
        except subprocess.TimeoutExpired:
            return 124


def main():
    # CLI golden (through the skill's ucas.sh wrapper)
    rc = run(["/bin/sh", str(U), "01_ucas_sh_cli.ucas"], "01_ucas_sh_cli.out")
    if rc:
        return rc

    # MCP golden (through ucas.sh --mcp, --dir keeps outputs local)
    rc = run(["/bin/sh", str(U), "--mcp", "--dir", str(HERE)],
             "mcp_tooling_smoke.out",
             stdin=(HERE / "mcp_tooling_smoke.jsonl").read_bytes())
    if rc:
        return rc

    # Direct tool-output goldens (stdout captures; commands recorded in .cmd files)
    for outfile, extra in [
        ("tool_mcp_client.out", []),
        ("tool_mcp_client_flat.out", ["--flat"]),
        ("tool_ucas_client.out", None),
    ]:
        if extra is None:
            cmd = [sys.executable, str(UC), str(BIN)]
        else:
            cmd = [sys.executable, str(MC), str(BIN), *extra]
        rc = run(cmd, outfile)
        if rc:
            return rc

    print("goldens regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
