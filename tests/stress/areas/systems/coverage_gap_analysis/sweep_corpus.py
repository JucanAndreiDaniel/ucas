#!/usr/bin/env python3
"""Run the coverage-instrumented ucas binary over the whole accumulated corpus.

Each invocation writes a unique .profraw (LLVM_PROFILE_FILE=%p) so parallel
workers never race. Both CLI (.ucas) and MCP/JSON (.jsonl) entry points are
exercised. A global deadline bounds total wall time; files are shuffled so a
deadline abort still samples broadly rather than biasing to early directories.
"""
# --- portability: derive the repo root from this file's own location -------
# Walk up until a directory containing both the `ucas` binary and `src/` is found.
from pathlib import Path as _ROOT_PATH
def _repo_root():
    here = _ROOT_PATH(__file__).resolve()
    for d in here.parents:
        if (d / 'ucas').is_file() and (d / 'src').is_dir():
            return d
    raise RuntimeError('ucas repo root not found above ' + str(here))
_REPO_ROOT = _repo_root()
ROOT = str(_REPO_ROOT)
_HERE = _ROOT_PATH(__file__).resolve().parent
import os, subprocess, sys, time, random, glob
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = str(_HERE)
ROOT = str(_REPO_ROOT)
BIN = os.path.join(HERE, "ucas_cov")
PROF = os.path.join(HERE, "profiles")
os.makedirs(PROF, exist_ok=True)

PER_FILE_TIMEOUT = int(os.environ.get("PER_FILE_TIMEOUT", "4"))
GLOBAL_DEADLINE = int(os.environ.get("GLOBAL_DEADLINE", "900"))  # seconds
WORKERS = int(os.environ.get("WORKERS", "12"))

ENV_BASE = dict(os.environ)
ENV_BASE["UCAS_NO_TIMES"] = "1"
ENV_BASE["UCAS_SPIRV_CROSS"] = "none"

# Build the work list -------------------------------------------------------
work = []  # (path, cwd, mode)
# Stress corpus (recursive: include deeply nested _scratch / sub folders)
for p in glob.glob(os.path.join(ROOT, "tests", "stress", "**", "*.ucas"), recursive=True):
    work.append((p, os.path.dirname(p), "cli"))
for p in glob.glob(os.path.join(ROOT, "tests", "stress", "**", "*.jsonl"), recursive=True):
    work.append((p, os.path.dirname(p), "mcp"))
    work.append((p, os.path.dirname(p), "json"))
# Canonical repo suites (read-only)
for p in glob.glob(os.path.join(ROOT, "tests", "*.ucas")):
    work.append((p, os.path.join(ROOT, "tests"), "cli"))
for p in glob.glob(os.path.join(ROOT, "tests", "json", "*.jsonl")):
    work.append((p, os.path.join(ROOT, "tests", "json"), "json"))
for p in glob.glob(os.path.join(ROOT, "tests", "mcp", "*.jsonl")):
    work.append((p, os.path.join(ROOT, "tests", "mcp"), "mcp"))

random.seed(1234)
random.shuffle(work)
print(f"work items: {len(work)}", flush=True)

counter = 0
start = time.time()
stats = {"cli": 0, "mcp": 0, "json": 0, "timeout": 0, "nonzero": 0, "ok": 0}

def run_one(item):
    global counter
    path, cwd, mode = item
    counter += 1
    outprof = os.path.join(PROF, f"c{counter:06d}.profraw")
    env = dict(ENV_BASE)
    env["LLVM_PROFILE_FILE"] = outprof
    flags = []
    flagfile = os.path.join(cwd, os.path.basename(path)[:-6] + ".flags")
    if os.path.exists(flagfile) and mode == "mcp":
        flags = open(flagfile).read().split()
    if mode == "cli":
        cmd = [BIN, path]
    elif mode == "mcp":
        cmd = [BIN, "--mcp"] + flags
    else:
        cmd = [BIN, "--json", "--files", "none"] + flags
    try:
        with open(path, "rb") as fin, open(os.devnull, "wb") as fout:
            r = subprocess.run(cmd, cwd=cwd, env=env, stdin=fin, stdout=fout,
                               stderr=subprocess.STDOUT, timeout=PER_FILE_TIMEOUT)
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
    except Exception as e:
        rc = f"exc:{e}"
    return (mode, rc, outprof)

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futures = [ex.submit(run_one, it) for it in work]
    for fut in as_completed(futures):
        try:
            mode, rc, outprof = fut.result()
        except Exception as e:
            continue
        stats[mode] += 1
        if rc == "timeout":
            stats["timeout"] += 1
            if os.path.exists(outprof):
                os.remove(outprof)  # killed runs have no flushed data
        elif isinstance(rc, int) and rc != 0:
            stats["nonzero"] += 1
        else:
            stats["ok"] += 1
        if time.time() - start > GLOBAL_DEADLINE:
            break

print(f"elapsed {time.time()-start:.1f}s stats={stats}", flush=True)
print(f"profraws: {len(glob.glob(os.path.join(PROF,'c*.profraw')))}", flush=True)
