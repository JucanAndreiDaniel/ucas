"""Run each JSONL probe twice under `timeout 15`, diff, and keep a golden .out
only when the two runs are byte-identical. Run from this folder.
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
import glob, os, subprocess, sys, time

BIN = str(_REPO_ROOT / "ucas")
TIMEOUT = 15

def run(path):
    with open(path, "rb") as f:
        data = f.read()
    t0 = time.time()
    p = subprocess.run(["timeout", "15", BIN, "--mcp"], input=data,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=".")
    return p.returncode, p.stdout, p.stderr, time.time() - t0

def stats(out):
    n = ok = err = 0
    for ln in out.decode("utf-8", "replace").splitlines():
        try:
            d = __import__("json").loads(ln)
        except Exception:
            continue
        if "id" not in d:
            continue
        n += 1
        if "error" in d and isinstance(d["error"], dict) and "jsonrpc" in d["error"]:
            pass
        elif "error" in d:
            err += 1
        else:
            r = d.get("result", {})
            sc = r.get("structuredContent", {}) if isinstance(r, dict) else {}
            if isinstance(sc, dict) and sc.get("ok") is False:
                err += 1
            else:
                ok += 1
    return n, ok, err

files = sorted(p for p in glob.glob("mcp_*.jsonl") if not p.endswith("_nondet.jsonl"))
for path in files:
    rc1, o1, e1, t1 = run(path)
    rc2, o2, e2, t2 = run(path)
    same = (o1 == o2 and e1 == e2 and rc1 == rc2)
    n, ok, err = stats(o1)
    print("%-36s rc=%s/%s t=%.2f/%.2fs out=%dB err=%dB responses=%d ok=%d errlike=%d deterministic=%s"
          % (path, rc1, rc2, t1, t2, len(o1), len(e1), n, ok, err, same))
    if e1:
        print("   STDERR:", e1[:400].decode("utf-8", "replace").replace("\n", " | "))
    if same and rc1 == 0 and not e1:
        base = path[:-6]
        open(base + ".out", "wb").write(o1)
        print("   -> wrote", base + ".out")
    else:
        print("   -> NO GOLDEN (nondeterministic or nonzero rc or stderr)")
