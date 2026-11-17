#!/usr/bin/env python3
"""Faithful replay of the repo Makefile's test recipes WITHOUT rebuilding.

Replaces ``replay.sh``.  ``bmake -n test`` would recompile parse.o / x86data.o
and relink ucas, so the recipes are replayed verbatim here with $BIN fixed.
Running with cwd == this folder keeps transient .got/.diff files confined here
while each recipe's own test directory is used as the input cwd.

Usage: replay.py LABEL ["EXTRA KEY=VAL EXPORTS"] ["RECIPE_ENV_BASE"]
                       [PT] [ST] [SECTIONS]
  LABEL     tag for output log files
  EXTRA     space-separated KEY=VAL exported into the environment
  BASE      replacement for TESTPRE's base env string
            (default: "UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none")
  PT        optional per-test timeout in seconds (empty = exact official behaviour)
  ST        per-suite wall-clock timeout (default 300)
  SECTIONS  all | cli | json | mcp | libc
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
import shutil
import subprocess
import sys
import time

REPO = str(_REPO_ROOT)
HERE = Path(__file__).resolve().parent
BIN = str(_REPO_ROOT / "ucas")

DEFAULT_BASE = "UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none"


def parse_env(spec):
    out = {}
    for kv in spec.split():
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k] = v
    return out


def env_for(spec):
    e = dict(os.environ)
    e.update(parse_env(spec))
    return e


def run_to(argv, *, cwd, env=None, stdin_path=None, out_path, timeout):
    """Run one command with stdout+stderr merged into out_path; return rc."""
    kw = dict(cwd=str(cwd), env=env, stdout=subprocess.PIPE,
              stderr=subprocess.STDOUT, timeout=timeout)
    if stdin_path is not None:
        kw["stdin"] = open(stdin_path, "rb")
    try:
        p = subprocess.run(argv, **kw)
        data, rc = p.stdout, p.returncode
    except subprocess.TimeoutExpired as ex:
        data, rc = (ex.stdout or b""), 124
    finally:
        if "stdin" in kw:
            kw["stdin"].close()
    with open(out_path, "wb") as fh:
        fh.write(data)
    return rc


def diff_to(golden, got, diff_path):
    with open(diff_path, "wb") as fh:
        p = subprocess.run(["diff", "-u", str(golden), str(got)],
                           stdout=fh, stderr=subprocess.STDOUT, timeout=120)
        return p.returncode


def ext_of_env(base, env_path, default_marker="UCAS_NO_TIMES=1 "):
    if Path(env_path).is_file():
        return default_marker + Path(env_path).read_text().rstrip("\n")
    return base


def needs_ok(path):
    tool = Path(path).read_text().strip()
    if not tool:
        return True, tool
    return shutil.which(tool) is not None, tool


def clear_leftovers():
    for pat in ("*.got", "*.diff"):
        for f in HERE.glob(pat):
            try:
                f.unlink()
            except OSError:
                pass


def leftover_names():
    out = []
    for pat in ("*.got", "*.diff"):
        out += [f.name for f in HERE.glob(pat)]
    return sorted(out)


def record_leftovers(label, section):
    lf = HERE / ("%s.%s.leftover" % (label, section))
    names = leftover_names()
    lf.write_text("".join(n + "\n" for n in names))
    if names:
        print("%s: LEFTOVER %d file(s): %s" %
              (section, len(names), " ".join(names) + " "))
        d = HERE / (label + ".diffs")
        d.mkdir(parents=True, exist_ok=True)
        for f in HERE.glob("*.diff"):
            shutil.copyfile(f, d / f.name)
    else:
        print("%s: no leftover .got/.diff" % section)
    clear_leftovers()


def tail1(path):
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
        return lines[-1] if lines else ""
    except OSError:
        return ""


def want(sections, name):
    return sections == "all" or sections == name


def suite_cli(label, base, pt, st, log):
    log.write("")  # truncate handled by caller
    deadline = time.monotonic() + st
    fail = ok = skipped = 0
    rc = 0
    tests = Path(REPO) / "tests"
    for t in sorted(tests.glob("*.ucas")):
        if time.monotonic() >= deadline:
            rc = 124
            break
        n = t.name[:-6] if t.name.endswith(".ucas") else t.name
        e = ext_of_env(base, tests / (n + ".env"))
        needs = tests / (n + ".needs")
        if needs.is_file():
            good, tool = needs_ok(needs)
            if not good:
                log.write("skip %s (no %s)\n" % (n, tool))
                skipped += 1
                continue
        env = env_for(e)
        got = HERE / (n + ".got")
        diff = HERE / (n + ".diff")
        run_argv = [BIN, t.name]
        timeout = int(pt) if pt else 3600
        trc = run_to(run_argv, cwd=tests, env=env, out_path=got,
                     timeout=timeout)
        if pt and trc == 124:
            log.write("TIMEOUT %s (%ss)\n" % (n, pt))
        if diff_to(tests / (n + ".out"), got, diff) == 0:
            log.write("ok   %s\n" % n)
            got.unlink(missing_ok=True)
            diff.unlink(missing_ok=True)
            ok += 1
        else:
            log.write("FAIL %s (see %s.diff)\n" % (n, n))
            fail += 1
    log.write("TOTAL ok=%d fail=%d skip=%d\n" % (ok, fail, skipped))
    return rc if rc else fail


def suite_json(label, base, pt, st, log):
    deadline = time.monotonic() + st
    fail = ok = skipped = 0
    rc = 0
    tests = Path(REPO) / "tests" / "json"
    for t in sorted(tests.glob("*.jsonl")):
        if time.monotonic() >= deadline:
            rc = 124
            break
        n = t.name[:-6] if t.name.endswith(".jsonl") else t.name
        e = ext_of_env(base, tests / (n + ".env"))
        needs = tests / (n + ".needs")
        if needs.is_file():
            good, tool = needs_ok(needs)
            if not good:
                log.write("skip json/%s (no %s)\n" % (n, tool))
                skipped += 1
                continue
        env = env_for(e)
        got = HERE / ("json-" + n + ".got")
        diff = HERE / ("json-" + n + ".diff")
        timeout = int(pt) if pt else 3600
        trc = run_to([BIN, "--json", "--files", "none"], cwd=tests, env=env,
                     stdin_path=t, out_path=got, timeout=timeout)
        if pt and trc == 124:
            log.write("TIMEOUT json/%s (%ss)\n" % (n, pt))
        if diff_to(tests / (n + ".out"), got, diff) == 0:
            log.write("ok   json/%s\n" % n)
            got.unlink(missing_ok=True)
            diff.unlink(missing_ok=True)
            ok += 1
        else:
            log.write("FAIL json/%s (see json-%s.diff)\n" % (n, n))
            fail += 1
    log.write("TOTAL ok=%d fail=%d skip=%d\n" % (ok, fail, skipped))
    return rc if rc else fail


def suite_mcp(label, base, pt, st, log):
    deadline = time.monotonic() + st
    fail = ok = skipped = 0
    rc = 0
    tests = Path(REPO) / "tests" / "mcp"
    for t in sorted(tests.glob("*.jsonl")):
        if time.monotonic() >= deadline:
            rc = 124
            break
        n = t.name[:-6] if t.name.endswith(".jsonl") else t.name
        flags_file = tests / (n + ".flags")
        fl = flags_file.read_text().rstrip("\n") if flags_file.is_file() else ""
        e = ext_of_env(base, tests / (n + ".env"))
        needs = tests / (n + ".needs")
        if needs.is_file():
            good, tool = needs_ok(needs)
            if not good:
                log.write("skip mcp/%s (no %s)\n" % (n, tool))
                skipped += 1
                continue
        env = env_for(e)
        got = HERE / ("mcp-" + n + ".got")
        diff = HERE / ("mcp-" + n + ".diff")
        argv = [BIN, "--mcp"] + fl.split()
        timeout = int(pt) if pt else 3600
        trc = run_to(argv, cwd=tests, env=env, stdin_path=t, out_path=got,
                     timeout=timeout)
        if pt and trc == 124:
            log.write("TIMEOUT mcp/%s (%ss)\n" % (n, pt))
        if diff_to(tests / (n + ".out"), got, diff) == 0:
            log.write("ok   mcp/%s\n" % n)
            got.unlink(missing_ok=True)
            diff.unlink(missing_ok=True)
            ok += 1
        else:
            log.write("FAIL mcp/%s (see mcp-%s.diff)\n" % (n, n))
            fail += 1
    log.write("TOTAL ok=%d fail=%d skip=%d\n" % (ok, fail, skipped))
    return rc if rc else fail


def suite_libc(label, st, log):
    # bmake -C REPO -V SRCS 2>/dev/null | awk '... .c$ ...' > .srcs.list
    try:
        p = subprocess.run(["bmake", "-C", REPO, "-V", "SRCS"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=120)
        raw = p.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        raw = ""
    srcs = [tok for tok in raw.split()
            if tok.endswith(".c") and "$" not in tok]
    srcs_path = HERE / ".srcs.list"
    srcs_path.write_text("".join(s + "\n" for s in srcs))

    deadline = time.monotonic() + st
    fail = ok = 0
    rc = 0
    err_path = HERE / (label + ".libc.err")
    snipdef = '-DUCAS_SNIPDIR="%s/snippets"' % REPO
    argv_base = ["cc", "-pipe", "-g", "-DCF_HAVE_X86", "-O2",
                 "-I" + REPO + "/src", "-I" + REPO, snipdef,
                 "-std=gnu2x", "-D_GNU_SOURCE", "-w", "-fsyntax-only"]
    with open(err_path, "wb") as err:
        for s in srcs:
            if time.monotonic() >= deadline:
                rc = 124
                break
            try:
                p = subprocess.run(argv_base + [s], cwd=REPO + "/src",
                                   stdout=subprocess.DEVNULL, stderr=err,
                                   timeout=120)
                good = p.returncode == 0
            except subprocess.TimeoutExpired:
                good = False
            if good:
                ok += 1
            else:
                log.write("FAIL %s\n" % s)
                fail += 1
    log.write("TOTAL ok=%d fail=%d\n" % (ok, fail))
    return rc if rc else fail


def main(argv):
    if not argv:
        print("label required", file=sys.stderr)
        return 2
    label = argv[0]
    extra = argv[1] if len(argv) > 1 else ""
    base = argv[2] if len(argv) > 2 else DEFAULT_BASE
    pt = argv[3] if len(argv) > 3 else ""
    st = int(argv[4]) if len(argv) > 4 and argv[4] else 300
    sections = argv[5] if len(argv) > 5 else "all"

    os.chdir(str(HERE))
    for kv in extra.split():
        if "=" in kv:
            k, v = kv.split("=", 1)
            os.environ[k] = v

    clear_leftovers()
    summary = HERE / (label + ".exit")
    summary.write_text("")

    # sat-selftest (first line of the `test` recipe)
    selftest_out = HERE / (label + ".selftest.out")
    rc = run_to([BIN, "--sat-selftest"], cwd=HERE, out_path=selftest_out,
                timeout=300)
    with open(summary, "a") as fh:
        fh.write("sat-selftest exit=%d\n" % rc)
    print("sat-selftest exit=%d (output: %s.selftest.out)" % (rc, label))

    if want(sections, "cli"):
        log_path = HERE / (label + ".cli.log")
        with open(log_path, "w") as log:
            cli_rc = suite_cli(label, base, pt, st, log)
        with open(summary, "a") as fh:
            fh.write("cli exit=%d\n" % cli_rc)
        print("cli: exit=%d  %s" % (cli_rc, tail1(log_path)))
        record_leftovers(label, "cli")

    if want(sections, "json"):
        log_path = HERE / (label + ".json.log")
        with open(log_path, "w") as log:
            json_rc = suite_json(label, base, pt, st, log)
        with open(summary, "a") as fh:
            fh.write("json exit=%d\n" % json_rc)
        print("json: exit=%d  %s" % (json_rc, tail1(log_path)))
        record_leftovers(label, "json")

    if want(sections, "mcp"):
        log_path = HERE / (label + ".mcp.log")
        with open(log_path, "w") as log:
            mcp_rc = suite_mcp(label, base, pt, st, log)
        with open(summary, "a") as fh:
            fh.write("mcp exit=%d\n" % mcp_rc)
        print("mcp: exit=%d  %s" % (mcp_rc, tail1(log_path)))
        record_leftovers(label, "mcp")

    if want(sections, "libc"):
        log_path = HERE / (label + ".libc.log")
        with open(log_path, "w") as log:
            libc_rc = suite_libc(label, st, log)
        with open(summary, "a") as fh:
            fh.write("libc exit=%d\n" % libc_rc)
        print("libc: exit=%d  %s" % (libc_rc, tail1(log_path)))

    print("=== DONE %s (see %s) ===" % (label, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
