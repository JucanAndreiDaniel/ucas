#!/usr/bin/env python3
"""Verify texenc's reported BC4 decodes against an independent Python BC4
decoder.  For each random 16-entry table the block line gives r0,r1 and the
16 selectors; the 'decodes to' line gives f32(palette/255).  We recompute the
palette exactly and compare.
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
import subprocess, random, re, struct, sys

BIN = str(_REPO_ROOT / "ucas")
CWD = str(_HERE)

def f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]

def palette(r0, r1):
    p = [r0, r1]
    if r0 > r1:
        for i in range(2, 8):
            p.append(((8 - i) * r0 + (i - 1) * r1) / 7.0)
    else:
        for i in range(2, 6):
            p.append(((6 - i) * r0 + (i - 1) * r1) / 5.0)
        p += [0.0, 255.0]
    return p

def run(src):
    p = subprocess.run([BIN], input=src, text=True, capture_output=True,
                       timeout=25, cwd=CWD)
    return p.stdout + p.stderr

def main():
    random.seed(777)
    bad = []
    tested = 0
    for t in range(60):
        vals = [random.randint(0, 255) for _ in range(16)]
        tab = "[" + ",".join(map(str, vals)) + "]"
        out = run(f"Q = {tab}\ntexenc Q\n")
        pline = [l for l in out.splitlines() if "endpoints" in l and "selectors" in l]
        dline = [l for l in out.splitlines() if l.strip().startswith("decodes to")]
        if not pline or not dline:
            continue
        m = re.search(r"endpoints (\d+), (\d+)", pline[0])
        r0, r1 = int(m.group(1)), int(m.group(2))
        sm = re.search(r"selectors ([\d ]+)", pline[0])
        sels = list(map(int, sm.group(1).split()))
        dec = re.search(r"decodes to \[(.*?)\]", dline[0])
        reported = [float(x) for x in dec.group(1).split(",")]
        pal = palette(r0, r1)
        tested += 1
        if len(sels) != 16 or len(reported) != 16:
            bad.append((t, vals, "len", sels, reported))
            continue
        for i, s in enumerate(sels):
            expect = f32(pal[s] / 255.0)
            if abs(reported[i] - expect) > 2e-7:
                bad.append((t, vals, r0, r1, i, s, expect, reported[i]))
                break
    print("tested", tested, "bad", len(bad))
    for b in bad[:10]:
        print("BAD", b)
    return bad

if __name__ == "__main__":
    sys.exit(0 if not main() else 1)
