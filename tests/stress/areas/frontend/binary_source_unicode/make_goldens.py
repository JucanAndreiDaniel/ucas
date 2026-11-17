#!/usr/bin/env python3
"""Generate and verify goldens (ported from make_goldens.sh).

Run each case TWICE under a 15-second subprocess timeout and compare with
cmp.  Only byte-identical outputs are kept as .out goldens.
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
B = ROOT / "ucas"

ENV = os.environ.copy()
ENV["UCAS_NO_TIMES"] = "1"
ENV["UCAS_SPIRV_CROSS"] = "none"


def run_twice(cmd, stdin=None):
    """Run cmd under `timeout 15`, twice; return (rc1, rc2, bytes1, bytes2)."""
    results = []
    for _ in range(2):
        try:
            p = subprocess.run(
                cmd,
                input=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=15,
                cwd=str(HERE),
                env=ENV,
            )
            results.append((p.returncode, p.stdout))
        except subprocess.TimeoutExpired as e:
            results.append((124, e.stdout or b""))
    return results[0][0], results[1][0], results[0][1], results[1][1]


def emit_result(fname, r1, r2, b1, b2):
    n = Path(fname).stem
    t1 = HERE / f"{n}.t1"
    t2 = HERE / f"{n}.t2"
    t1.write_bytes(b1)
    t2.write_bytes(b2)
    if b1 == b2:
        out = HERE / f"{n}.out"
        out.write_bytes(b1)
        print(f"OK   {fname}  rc={r1}/{r2}  bytes={out.stat().st_size}")
    else:
        print(f"NONDET {fname}  rc={r1}/{r2}")
    t1.unlink(missing_ok=True)
    t2.unlink(missing_ok=True)


def main():
    for f in sorted(HERE.glob("*.ucas")):
        r1, r2, b1, b2 = run_twice([str(B), f.name])
        emit_result(f.name, r1, r2, b1, b2)

    for f in sorted(HERE.glob("mcp_*.jsonl")):
        n = f.stem
        flags_file = HERE / f"{n}.flags"
        # $(cat file 2>/dev/null || true): trailing newlines stripped, then
        # unquoted $flags undergoes shell word splitting.
        flags = flags_file.read_text().split() if flags_file.is_file() else []
        cmd = [str(B), "--mcp", *flags]
        r1, r2, b1, b2 = run_twice(cmd, stdin=f.read_bytes())
        emit_result(f.name, r1, r2, b1, b2)

    for f in sorted(HERE.glob("json_*.jsonl")):
        cmd = [str(B), "--json", "--files", "none"]
        r1, r2, b1, b2 = run_twice(cmd, stdin=f.read_bytes())
        emit_result(f.name, r1, r2, b1, b2)

    # stdin runner: generate its golden once, then verify by re-running.
    runner = HERE / "run_stdin.py"
    subprocess.run([sys.executable, str(runner)], cwd=str(HERE),
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                   timeout=300, env=ENV)
    subprocess.run(["cp", str(HERE / "stdin_all.got"),
                    str(HERE / "stdin_all.out")], cwd=str(HERE), env=ENV)
    p = subprocess.run([sys.executable, str(runner)], cwd=str(HERE),
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                       timeout=300, env=ENV)
    print(f"stdin runner verify rc={p.returncode} (0 = deterministic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
