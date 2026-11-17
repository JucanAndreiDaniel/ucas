#!/usr/bin/env python3
"""Env / locale / terminal sensitivity matrix for the ucas binary.

For every CLI golden (NAME.ucas + NAME.out) and the MCP golden, re-run the same
input under a matrix of LANG / LC_ALL / LC_NUMERIC / UCAS* / TMPDIR / HOME / TERM
settings and require byte-identical output to the baseline golden.  A difference
means some environment variable leaked into output.

Three extra probes that are NOT golden diffs:
  * TTY: pipe vs pseudo-terminal (script -qec) -- interactive prompts are
    EXPECTED to differ; we assert the exact expected pattern and no hang.
  * file location: `plot X to NAME` must write NAME.gif in the CURRENT directory
    regardless of HOME / TMPDIR.
  * determinism: baseline run twice must be byte-identical.

All scratch files live in ./.scratch and are removed on exit.  Every child is
bounded by a subprocess timeout.
"""

import atexit
import os
import re
import shutil
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


AREA = Path(__file__).resolve().parent
ROOT = _find_root(AREA)
BIN = ROOT / "ucas"
SCRATCH = AREA / ".scratch"

BASE_ENV = os.environ.copy()
BASE_ENV["UCAS_NO_TIMES"] = "1"
BASE_ENV["UCAS_SPIRV_CROSS"] = "none"

GOLDENS = ["01_numbers", "02_errors", "03_types_ranges", "04_algebra", "05_nlp"]

# Each config is the exact list of arguments passed to env(1).
CONFIGS = {
    "base":      ["LANG=en_US.UTF-8", "LC_ALL="],
    "C":         ["LANG=C", "LC_ALL=C"],
    "Cutf8":     ["LANG=C.UTF-8", "LC_ALL=C.UTF-8"],
    "ro":        ["LANG=ro_RO.UTF-8", "LC_ALL=ro_RO.UTF-8"],
    "posix":     ["LANG=POSIX", "LC_ALL=POSIX"],
    "invalid":   ["LANG=xx_XX.INVALID", "LC_ALL=xx_XX.INVALID"],
    "numro":     ["LANG=C", "LC_ALL=C", "LC_NUMERIC=ro_RO.UTF-8"],
    "bogusbin":  ["LANG=C", "UCAS=/no/such/ucas", "UCAS_BIN=/no/such/ucas"],
    "spv":       ["LANG=C", "UCAS_SPIRV_CROSS=/no/such/spirv-cross"],
    "tmpdir":    ["LANG=C", "TMPDIR=/no/such/tmp"],
    "home":      ["LANG=C", "HOME=/no/such/home"],
    "termdumb":  ["LANG=C", "TERM=dumb"],
    "termempty": ["LANG=C", "TERM="],
    "unsetall":  ["-u", "LANG", "-u", "LC_ALL", "-u", "LC_NUMERIC",
                  "-u", "TERM", "-u", "HOME", "-u", "TMPDIR"],
    "kitchen":   ["LANG=ro_RO.UTF-8", "LC_ALL=ro_RO.UTF-8", "UCAS=/bogus",
                  "UCAS_BIN=/bogus", "UCAS_SPIRV_CROSS=/bogus", "TMPDIR=/bogus",
                  "HOME=/bogus", "TERM=bogus"],
    "LANGonly":  ["LANG=ro_RO.UTF-8", "LC_ALL="],
    "LCnumeric": ["LANG=en_US.UTF-8", "LC_ALL=", "LC_NUMERIC=ro_RO.UTF-8"],
    "LCctype":   ["LANG=C", "LC_ALL=C", "LC_CTYPE=ro_RO.UTF-8"],
    "lowerutf8": ["LANG=ro_RO.utf8", "LC_ALL=ro_RO.utf8"],
    "mixLC":     ["LANG=ro_RO.UTF-8", "LC_ALL=C"],
    "seed":      ["LANG=C", "UCAS_SEED=12345"],
    "notimes":   ["LANG=C", "UCAS_NO_TIMES=1"],
    "nopath":    ["LANG=C", "PATH=/nonexistent"],
    "badcc":     ["LANG=C", "UCAS_CC=/no/such/cc"],
    "termx":     ["LANG=C", "TERM=xterm-256color"],
    "termvt":    ["LANG=C", "TERM=vt100"],
    "language":  ["LANG=C", "LC_ALL=C", "LANGUAGE=ro:de"],
}

RUNS = 0
PASS = 0
FAIL = 0


def cleanup():
    shutil.rmtree(SCRATCH, ignore_errors=True)


atexit.register(cleanup)


def record(ok):
    global RUNS, PASS, FAIL
    RUNS += 1
    if ok:
        PASS += 1
    else:
        FAIL += 1


def run_env(cfg, args, stdin=None, stdout_file=None, timeout=20, cwd=None):
    """Run `env <cfg args> <args>` with base env, capturing/returning rc."""
    cmd = ["env", *CONFIGS[cfg], *[str(a) for a in args]]
    try:
        p = subprocess.run(cmd, input=stdin, stdout=stdout_file,
                           stderr=subprocess.STDOUT, timeout=timeout,
                           cwd=str(cwd or AREA), env=BASE_ENV)
        return p.returncode
    except subprocess.TimeoutExpired:
        return 124


def same_bytes(a, b):
    return Path(a).read_bytes() == Path(b).read_bytes()


def show_diff(golden, got):
    d = subprocess.run(["diff", "-u", str(golden), str(got)],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = d.stdout.splitlines(keepends=True)
    sys.stdout.buffer.write(b"".join(lines[:12]))
    sys.stdout.buffer.flush()


def run_cli(name, cfg):
    got = SCRATCH / f"{name}.{cfg}.got"
    with open(got, "wb") as g:
        rc = run_env(cfg, [BIN, f"{name}.ucas"], stdout_file=g)
    if rc != 0:
        print(f"FAIL {name} [{cfg}] exit={rc}")
        record(False)
        return
    if same_bytes(AREA / f"{name}.out", got):
        record(True)
    else:
        print(f"FAIL {name} [{cfg}] OUTPUT DIFFERS")
        show_diff(AREA / f"{name}.out", got)
        record(False)


def run_mcp(cfg):
    got = SCRATCH / f"mcp_env.{cfg}.got"
    with open(got, "wb") as g:
        rc = run_env(cfg, [BIN, "--mcp"], stdin=(AREA / "mcp_env.jsonl").read_bytes(),
                     stdout_file=g)
    if rc != 0:
        print(f"FAIL mcp_env [{cfg}] exit={rc}")
        record(False)
        return
    if same_bytes(AREA / "mcp_env.out", got):
        record(True)
    else:
        print(f"FAIL mcp_env [{cfg}] OUTPUT DIFFERS")
        show_diff(AREA / "mcp_env.out", got)
        record(False)


def tty_probes():
    global RUNS, PASS, FAIL
    q = b"what is log of x\n"

    # pipe: no prompt, no interactive menu, has a "note:" line
    pipe = SCRATCH / "tty.pipe"
    with open(pipe, "wb") as f:
        p = subprocess.run([str(BIN)], input=q, stdout=f,
                           stderr=subprocess.STDOUT, timeout=10,
                           cwd=str(AREA), env=BASE_ENV)
    rc = p.returncode
    data = pipe.read_bytes()
    ok = (rc == 0 and re.search(rb"^  note:", data, re.M) is not None
          and b"ucas> " not in data and b"which?" not in data)
    if ok:
        record(True)
    else:
        print(f"FAIL tty pipe exit={rc}" if rc != 0 else "FAIL tty pipe shape")
        record(False)

    # stdin=tty, stdout=file: prompt appears but NLP stays non-interactive
    mixed = SCRATCH / "tty.mixed"
    cmd = f"{BIN} > {mixed} 2>&1"
    p = subprocess.run(["script", "-qec", cmd, "/dev/null"], input=q,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                       timeout=10, cwd=str(AREA), env=BASE_ENV)
    rc = p.returncode
    data = mixed.read_bytes() if mixed.is_file() else b""
    if rc != 0:
        print(f"FAIL tty mixed exit={rc}")
        record(False)
    elif b"ucas> " in data and b"which?" not in data:
        record(True)
    else:
        print("FAIL tty mixed shape")
        record(False)

    # stdin=tty, stdout=tty: full interactive ambiguity menu present
    pty = SCRATCH / "tty.pty"
    with open(pty, "wb") as f:
        p = subprocess.run(["script", "-qec", str(BIN), "/dev/null"], input=q,
                           stdout=f, stderr=subprocess.STDOUT, timeout=10,
                           cwd=str(AREA), env=BASE_ENV)
    rc = p.returncode
    data = pty.read_bytes()
    if rc != 0:
        print(f"FAIL tty pty exit={rc}")
        record(False)
    elif (b"ucas> " in data and b"which?" in data
          and b"the natural log" in data):
        record(True)
    else:
        print("FAIL tty pty shape (possible hang / wrong menu)")
        record(False)


def file_location_probe():
    fw = SCRATCH / "fw"
    shutil.rmtree(fw, ignore_errors=True)
    fw.mkdir(parents=True)
    log = SCRATCH / "fw.log"
    env = BASE_ENV.copy()
    env["HOME"] = "/no/such/home"
    env["TMPDIR"] = "/no/such/tmp"
    with open(log, "wb") as g:
        try:
            p = subprocess.run([str(BIN)], input=b"plot x^2 to traced\n",
                               stdout=g, stderr=subprocess.STDOUT, timeout=15,
                               cwd=str(fw), env=env)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    ok = (rc == 0 and (fw / "traced.gif").is_file()
          and b"wrote traced.gif" in log.read_bytes())
    if ok:
        record(True)
    else:
        print(f"FAIL file-location probe (rc={rc})")
        record(False)


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True)

    print("== CLI golden x env matrix ==")
    for cfg in CONFIGS:
        for n in GOLDENS:
            run_cli(n, cfg)

    print("== MCP golden x env matrix ==")
    for cfg in CONFIGS:
        run_mcp(cfg)

    print("== determinism (baseline twice) ==")
    for n in GOLDENS:
        det = SCRATCH / f"{n}.det2"
        with open(det, "wb") as g:
            run_env("base", [BIN, f"{n}.ucas"], stdout_file=g)
        if same_bytes(AREA / f"{n}.out", det):
            record(True)
        else:
            print(f"FAIL {n} NONDETERMINISTIC")
            record(False)

    print("== TTY probes ==")
    tty_probes()

    print("== file-location probe ==")
    file_location_probe()

    print("----------------------------------------")
    print(f"env matrix: {RUNS} runs, {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
