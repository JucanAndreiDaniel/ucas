#!/usr/bin/env python3
"""Runner for the cli_args_fuzz folder.

The bmake stress-test target only discovers .ucas/.jsonl goldens,
and CLI invocations (flags, stdin, pipes, multiple argv) cannot be expressed as
a .ucas file.  Each cli_NN_*.py is a self-contained reproducer that prints a
stable report (label / exit / merged stdout+stderr); cli_NN_*.out is its golden.
Run this script to re-check.
"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ENV = os.environ.copy()
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def main():
    passed = 0
    failed = 0
    for script in sorted(HERE.glob("cli_*.py")):
        out = script.with_suffix(".out")
        got = script.with_suffix(".got")
        diff = script.with_suffix(".diff")
        if not out.is_file():
            print(f"MISSING {out.name}")
            failed += 1
            continue
        with open(got, "wb") as g:
            subprocess.run(
                [sys.executable, str(script)],
                cwd=str(HERE),
                stdout=g,
                stderr=subprocess.STDOUT,
                timeout=300,
                env=ENV,
            )
        with open(diff, "wb") as df:
            d = subprocess.run(
                ["diff", "-u", str(out), str(got)],
                stdout=df,
                stderr=subprocess.STDOUT,
            )
        if d.returncode == 0:
            print(f"ok   {script.name}")
            passed += 1
            got.unlink(missing_ok=True)
            diff.unlink(missing_ok=True)
        else:
            print(f"FAIL {script.name} (see {diff.name})")
            failed += 1
    print(f"cli_args_fuzz: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
