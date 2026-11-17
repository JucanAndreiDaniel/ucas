"""Probe harness for tool_abuse_files stress tests. Not a golden itself.
Run: python3 probe.py <jsonl-file> [timeout]
Prints rc, elapsed, and each response line (truncated).
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
import json, subprocess, sys, time

BIN = str(_REPO_ROOT / "ucas")

def run_jsonl(path, timeout=10, extra_args=None, cwd=None):
    args = [BIN, "--mcp"]
    if extra_args:
        args += extra_args
    with open(path, "rb") as f:
        data = f.read()
    t0 = time.time()
    try:
        p = subprocess.run(args, input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, cwd=cwd)
        rc, out, err, elapsed = p.returncode, p.stdout, p.stderr, time.time()-t0
    except subprocess.TimeoutExpired as e:
        rc, out, err, elapsed = "TIMEOUT", e.stdout or b"", e.stderr or b"", timeout
    return rc, out, err, elapsed

def summarize(out):
    lines = out.decode("utf-8", "replace").splitlines()
    res = []
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            res.append(("RAW", ln[:200]))
            continue
        if "error" in d and isinstance(d.get("error"), dict) and "jsonrpc" in d.get("error", {}):
            res.append(("RPCERR", json.dumps(d)[:300]))
            continue
        rid = d.get("id")
        if "error" in d and isinstance(d.get("error"), dict):
            res.append((rid, "TOOLERR", json.dumps(d.get("error"))[:400]))
        elif "result" in d:
            r = d["result"]
            cont = r.get("content", [])
            txt = ""
            for c in cont:
                if isinstance(c, dict) and c.get("type") == "text":
                    txt += c.get("text", "")
            sc = r.get("structuredContent")
            extra = ""
            if isinstance(sc, dict):
                keys = list(sc.keys())
                extra = " SC.keys=" + str(keys)[:120]
                if "files" in sc:
                    extra += " files=" + json.dumps(sc["files"])[:200]
            res.append((rid, "OK", txt[:300].replace("\n", " "), extra))
        else:
            res.append((rid, json.dumps(d)[:300]))
    return res

if __name__ == "__main__":
    path = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 10
    rc, out, err, elapsed = run_jsonl(path, timeout)
    print("rc=%s elapsed=%.2fs stdout=%dB stderr=%dB" % (rc, elapsed, len(out), len(err)))
    if err:
        print("STDERR:", err.decode("utf-8", "replace")[:500])
    for s in summarize(out):
        print(s)
