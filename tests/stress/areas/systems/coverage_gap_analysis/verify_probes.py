#!/usr/bin/env python3
"""Run a probe under the instrumented binary and verify the target function
was actually reached (function-entry counter > 0) via llvm-cov show.

Probe spec fields:
  name, cmd (argv list), src (basename of source file), sym (function-name
  substring in the llvm-cov function header), inline (optional file content).
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
import os, sys, json, subprocess

HERE = str(_HERE)
ROOT = str(_REPO_ROOT)
BIN = os.path.join(HERE, "ucas_cov")
WORK = os.path.join(HERE, "work")
os.makedirs(WORK, exist_ok=True)

PROBES = json.load(open(sys.argv[1] if len(sys.argv) > 1 else
                        os.path.join(HERE, "probes.json")))

def run(probe):
    name = probe["name"]
    stdin = subprocess.DEVNULL
    if "inline" in probe:
        ext = "jsonl" if probe.get("mode") in ("mcp", "json") else "ucas"
        inp = os.path.join(WORK, f"probe_{name}.{ext}")
        with open(inp, "w") as f:
            f.write(probe["inline"])
        if any(a == "@IN" for a in probe["cmd"]):
            argv = probe["cmd"]
        else:
            stdin = open(inp, "rb")
            argv = probe["cmd"]
    else:
        argv = probe["cmd"]
    cmd = [inp if a == "@IN" else
           BIN if a == "@BIN" else
           a.replace("@ROOT", ROOT) for a in argv]
    prof = os.path.join(WORK, f"probe_{name}.profraw")
    outp = os.path.join(WORK, f"probe_{name}.out")
    for p in (prof, outp):
        if os.path.exists(p):
            os.remove(p)
    env = dict(os.environ)
    env["LLVM_PROFILE_FILE"] = prof
    env["UCAS_NO_TIMES"] = "1"
    env["UCAS_SPIRV_CROSS"] = "none"
    try:
        with open(outp, "wb") as fo:
            r = subprocess.run(cmd, stdin=stdin, stdout=fo, stderr=subprocess.STDOUT,
                               env=env, timeout=probe.get("timeout", 10), cwd=WORK)
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"
    finally:
        if stdin is not subprocess.DEVNULL:
            stdin.close()
    reached = None
    detail = ""
    if os.path.exists(prof) and os.path.getsize(prof) > 0:
        pd = os.path.join(WORK, f"probe_{name}.profdata")
        subprocess.run(["llvm-profdata", "merge", "-sparse", prof, "-o", pd],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        src = os.path.join(ROOT, "src", probe["src"])
        sh = subprocess.run(["llvm-cov", "show", BIN, f"-instr-profile={pd}",
                             src], capture_output=True, text=True).stdout
        lines = sh.splitlines()
        sym = probe["sym"]
        hits = []
        counts = []
        for i, ln in enumerate(lines):
            if sym in ln:
                # scan the next few lines for a numeric count field
                for j in range(i + 1, min(i + 6, len(lines))):
                    f = lines[j].split("|")
                    if len(f) > 1 and f[1].strip().lstrip("-").isdigit():
                        counts.append(int(f[1].strip()))
                        hits.append(f"L{i+1}:{ln.strip()[:70]} -> {lines[j].strip()[:70]}")
                        break
        reached = max(counts) if counts else None
        detail = " ; ".join(hits[:6])
    # output snippet
    snippet = ""
    if os.path.exists(outp):
        snippet = open(outp, errors="replace").read().strip().replace("\n", " | ")[:240]
    verdict = "REACHED" if (reached is not None and reached > 0) else "NOT-REACHED"
    print(f"[{verdict}] {name:22s} rc={rc} count={reached}")
    print(f"    sym: {detail}")
    print(f"    out: {snippet}")
    return {"name": name, "rc": rc, "count": reached, "verdict": verdict,
            "detail": detail, "snippet": snippet}

results = [run(p) for p in PROBES]
json.dump(results, open(os.path.join(HERE, "reports", "probe_results.json"), "w"), indent=1)
print(f"\nReached: {sum(1 for r in results if r['verdict']=='REACHED')}/{len(results)}")
