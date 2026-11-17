#!/usr/bin/env python3
"""Self-contained fault-injection regression harness.

Replaces ``run_fault_injection.sh``.  Compiles the LD_PRELOAD shim if needed,
then checks graceful-degradation paths (clean OOM, write errors, read-only cwd,
unwritable TMPDIR, MCP sessions that keep answering under fork/pipe/waitpid
faults).  Every subprocess is bounded by timeout.
"""
# --- portability: derive the repo root from this file's own location -------
# Walk up until a directory containing both the `ucas` binary and `src/` is found.
from pathlib import Path as _ROOT_PATH
from pathlib import Path
def _repo_root():
    here = _ROOT_PATH(__file__).resolve()
    for d in here.parents:
        if (d / 'ucas').is_file() and (d / 'src').is_dir():
            return d
    raise RuntimeError('ucas repo root not found above ' + str(here))
_REPO_ROOT = _repo_root()
ROOT = str(_REPO_ROOT)

import os
import re
import subprocess

HERE = Path(__file__).resolve().parent
BIN = str(_REPO_ROOT / "ucas")
SHIM = HERE / "fi_shim.so"
TMP = Path("/tmp/opencode/fi_run")

fail = 0


def ok(name):
    print("ok   fi/%s" % name)


def bad(name, msg):
    global fail
    print("FAIL fi/%s: %s" % (name, msg))
    fail += 1


def absent(path):
    return not Path(path).exists()


def run(argv, *, cwd=None, env=None, stdin_path=None, timeout=10):
    """Run with stdout+stderr merged; return (rc, text).  124 on timeout."""
    e = dict(os.environ)
    if env:
        e.update(env)
    kw = dict(cwd=str(cwd) if cwd else None, env=e,
              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
              timeout=timeout)
    if stdin_path is not None:
        kw["stdin"] = open(stdin_path, "rb")
    try:
        p = subprocess.run(argv, **kw)
        rc, out = p.returncode, p.stdout
    except subprocess.TimeoutExpired as ex:
        rc, out = 124, (ex.stdout or b"")
    finally:
        if "stdin" in kw:
            kw["stdin"].close()
    return rc, out.decode("utf-8", "replace")


def tail2(text):
    lines = text.splitlines()
    return "\n".join(lines[-2:])


def ls_l(path):
    p = subprocess.run(["ls", "-l", str(path)], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=30)
    return p.stdout.decode("utf-8", "replace").strip()


def main():
    global fail
    TMP.mkdir(parents=True, exist_ok=True)

    if not SHIM.exists():
        p = subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-o",
                            str(SHIM), str(HERE / "shim.c"), "-ldl"],
                           timeout=120)
        if p.returncode != 0:
            return 1

    (TMP / "one.ucas").write_text("show 1+2\n")
    (TMP / "plot.ucas").write_text("plot sin(x) x in -1..1 to fwtest\n")

    # 1. calloc / realloc OOM => clean "ucas: out of memory", exit 2
    for f in ("CALLOC", "REALLOC"):
        rc, out = run([BIN, str(TMP / "one.ucas")],
                      env={"FI_FAIL_" + f: "5", "LD_PRELOAD": str(SHIM)})
        if rc == 2 and "ucas: out of memory" in out:
            ok("%s-oom-clean" % f)
        else:
            bad("%s-oom-clean" % f, "rc=%s out=%s" % (rc, tail2(out)))

    # 2. malloc OOM at a well-handled index => clean message (index 30)
    rc, out = run([BIN, str(TMP / "one.ucas")],
                  env={"FI_FAIL_MALLOC": "30", "LD_PRELOAD": str(SHIM)})
    if rc == 2 and "ucas: out of memory" in out:
        ok("malloc-oom-clean")
    else:
        bad("malloc-oom-clean", "rc=%s" % rc)

    # 3. fopen of the input file fails => perror + exit 1, no crash
    rc, out = run([BIN, str(TMP / "one.ucas")],
                  env={"FI_FAIL_FOPEN": "1", "LD_PRELOAD": str(SHIM)})
    if rc == 1:
        ok("fopen-input-clean")
    else:
        bad("fopen-input-clean", "rc=%s out=%s" % (rc, tail2(out)))

    # 4. fopen of the GIF fails => clean 'cannot write', no file left
    gif = TMP / "fwtest.gif"
    gif.unlink(missing_ok=True)
    rc, out = run([BIN, "plot.ucas"], cwd=TMP,
                  env={"FI_FAIL_FOPEN": "2", "LD_PRELOAD": str(SHIM)})
    if rc == 0 and "error: cannot write fwtest.gif" in out and absent(gif):
        ok("fopen-output-clean")
    else:
        bad("fopen-output-clean", "rc=%s file=%s" % (rc, ls_l(gif)))

    # 5. fwrite of the GIF fails => clean 'cannot write' (partial file documented)
    gif.unlink(missing_ok=True)
    rc, out = run([BIN, "plot.ucas"], cwd=TMP,
                  env={"FI_FAIL_FWRITE": "1", "LD_PRELOAD": str(SHIM)})
    if rc == 0 and "error: cannot write fwtest.gif" in out:
        ok("fwrite-output-clean")
    else:
        bad("fwrite-output-clean", "rc=%s out=%s" % (rc, tail2(out)))
    gif.unlink(missing_ok=True)

    # 6. read-only cwd: write fails cleanly, following command still runs
    ro = TMP / "ro"
    ro.mkdir(parents=True, exist_ok=True)
    (ro / "ro.ucas").write_text(
        "plot sin(x) x in -1..1 to roplot\nshow 1+2\n")
    os.chmod(ro, 0o555)
    try:
        rc, out = run([BIN, "ro.ucas"], cwd=ro)
    finally:
        os.chmod(ro, 0o755)
    if (rc == 0 and "error: cannot write roplot.gif" in out
            and "_() = 3" in out):
        ok("readonly-cwd-clean")
    else:
        bad("readonly-cwd-clean", "rc=%s" % rc)

    # 7. unwritable TMPDIR (adamfit) => clean error
    rc, out = run([BIN, "adamfit_tmp.ucas"], cwd=HERE,
                  env={"TMPDIR": "/no/such/dir"}, timeout=20)
    if rc == 0 and "cannot make a temporary folder" in out:
        ok("tmpdir-clean")
    else:
        bad("tmpdir-clean", "rc=%s" % rc)

    # 8. MCP with fork/pipe/waitpid faults: session keeps answering (no crash)
    for f, n in (("FORK", "1"), ("FORK", "2"), ("PIPE", "1"),
                 ("PIPE", "2"), ("WAITPID", "1")):
        rc, out = run([BIN, "--mcp"], cwd=HERE,
                      env={"FI_FAIL_" + f: n, "LD_PRELOAD": str(SHIM)},
                      stdin_path=HERE / "mcp_timeout_base.jsonl", timeout=20)
        ids = len(set(re.findall(r'"id": [123],', out)))
        if rc == 0 and ids == 3 and "Segmentation" not in out:
            ok("mcp-%s%s-alive" % (f, n))
        else:
            bad("mcp-%s%s-alive" % (f, n), "rc=%s ids=%s" % (rc, ids))

    print("fault_injection: %s (%d failures)" %
          ("PASS" if fail == 0 else "FAIL", fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
