#!/usr/bin/env python3
"""ucas.py [ARG...]: run ucas with ARG, from whichever binary this machine has.

`ucas.py which` prints the binary.  The binary, first found: $UCAS; `ucas` on
PATH; UCAS_BIN in the nearest .claude/skills.env above the working folder (~/
expanded); the ucas this skill sits in (its repository's ./ucas, after make).
None: it says so, exit 2.

Ported from ucas.sh; the final `exec` is kept as os.execv so the child replaces
this process exactly as the shell did (identical exit/signal propagation).
"""

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def from_env():
    """UCAS_BIN of the nearest .claude/skills.env, ~/ expanded."""
    d = Path.cwd()
    while True:
        f = d / ".claude" / "skills.env"
        if f.is_file():
            values = []
            for line in f.read_text().splitlines():
                if line.startswith("UCAS_BIN="):
                    values.append(line[len("UCAS_BIN="):])
            if values:
                v = values[-1]
                if v.startswith("~/"):
                    v = os.environ.get("HOME", "") + v[1:]
                if v:
                    return v
        up = d.parent
        if up == d:  # at the root, or a dirname that does not move
            return None
        d = up


def find_bin():
    env_bin = os.environ.get("UCAS")
    if env_bin:
        return env_bin
    on_path = shutil.which("ucas")
    if on_path:
        return on_path
    v = from_env()
    if v:
        return v
    candidate = (HERE / "../../../../../../ucas").resolve()
    if os.access(str(candidate), os.X_OK):
        return str(candidate)
    return None


def main():
    bin_path = find_bin()
    if not bin_path or not os.access(bin_path, os.X_OK):
        suffix = f" at {bin_path}" if bin_path else ""
        sys.stderr.write(
            f"ucas.sh: no ucas binary{suffix}: build it (make in the ucas "
            f"repository), or set UCAS, or UCAS_BIN in .claude/skills.env\n"
        )
        return 2
    if len(sys.argv) > 1 and sys.argv[1] == "which":
        print(bin_path)
        return 0
    os.execv(bin_path, [bin_path, *sys.argv[1:]])
    return 0  # unreachable


if __name__ == "__main__":
    sys.exit(main())
