#!/usr/bin/env python3
"""Merge corpus profraws, then produce ranked coverage-gap reports."""
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
import os, glob, subprocess, json, collections, sys, math

HERE = str(_HERE)
PROF = os.path.join(HERE, "profiles")
REP = os.path.join(HERE, "reports")
BIN = os.path.join(HERE, "ucas_cov")
os.makedirs(REP, exist_ok=True)

KEY_FILES = {
    "nlp.c", "analyze.c", "sat.c", "jsonmode.c",
    "calc2.c", "closed.c", "integ.c", "ode.c", "series.c",
    "xform.c", "xfrat.c", "forms.c", "props.c", "loop.c",
    "scheme.c", "cancel.c", "cnum.c", "solve.c", "poly.c",
    "alg.c", "eval.c", "parse.c", "find.c",
}
KEY_BASE = {f[:-2] for f in KEY_FILES}  # 'nlp','analyze',...

def merge():
    profraws = sorted(glob.glob(os.path.join(PROF, "c*.profraw")))
    print(f"merging {len(profraws)} profraws", flush=True)
    acc = os.path.join(REP, "corpus.profdata")
    batch = 250
    for i in range(0, len(profraws), batch):
        chunk = profraws[i:i+batch]
        tmp = acc + ".tmp"
        cmd = ["llvm-profdata", "merge", "-sparse"]
        if os.path.exists(acc):
            cmd.append(acc)
        cmd += chunk + ["-o", tmp]
        subprocess.run(cmd, check=True)
        os.replace(tmp, acc)
    print(f"merged -> {acc} ({os.path.getsize(acc)} bytes)", flush=True)
    return acc

def export(profdata):
    out = os.path.join(REP, "corpus_export.json")
    print("exporting coverage JSON ...", flush=True)
    with open(out, "wb") as f:
        subprocess.run(["llvm-cov", "export", BIN,
                        f"-instr-profile={profdata}", "-format=text"],
                       stdout=f, stderr=subprocess.PIPE, check=True)
    print(f"exported -> {out} ({os.path.getsize(out)} bytes)", flush=True)
    return out

def base_of(path):
    return os.path.basename(path)

def main():
    profdata = merge()
    exp = export(profdata)
    d = json.load(open(exp))
    data = d["data"][0]
    files = data["files"]
    funcs = data["functions"]
    print(f"files={len(files)} functions={len(funcs)}", flush=True)

    # ---- (1) per-file line coverage, ranked (0% first) --------------------
    file_rows = []
    for f in files:
        s = f["summary"]["lines"]
        fs = f["summary"]["functions"]
        file_rows.append({
            "file": f["filename"],
            "line_pct": s["percent"],
            "lines": s["count"],
            "covered": s["covered"],
            "func_pct": fs["percent"],
            "funcs": fs["count"],
            "funcs_cov": fs["covered"],
        })
    # only real source files with code (exclude headers with 0 lines)
    coded = [r for r in file_rows if r["lines"] > 0]
    zero = [r for r in coded if r["covered"] == 0]
    low = sorted(coded, key=lambda r: (r["line_pct"], -r["lines"]))
    topcov = sorted(coded, key=lambda r: -r["line_pct"])
    with open(os.path.join(REP, "files_zero.txt"), "w") as f:
        for r in sorted(zero, key=lambda r: -r["lines"]):
            f.write(f"{base_of(r['file']):28s} lines={r['lines']:6d} funcs={r['funcs']:4d}\n")
    with open(os.path.join(REP, "files_lowest.txt"), "w") as f:
        f.write(f"{'file':28s} {'line%':>7s} {'lines':>7s} {'cov':>7s} {'func%':>7s} {'funcs':>6s}\n")
        for r in low[:60]:
            f.write(f"{base_of(r['file']):28s} {r['line_pct']:7.2f} {r['lines']:7d} "
                    f"{r['covered']:7d} {r['func_pct']:7.2f} {r['funcs']:6d}\n")
    with open(os.path.join(REP, "files_top.txt"), "w") as f:
        f.write(f"{'file':28s} {'line%':>7s} {'lines':>7s}\n")
        for r in topcov[:30]:
            f.write(f"{base_of(r['file']):28s} {r['line_pct']:7.2f} {r['lines']:7d}\n")
    print(f"files with 0 covered lines: {len(zero)} / {len(coded)}", flush=True)

    # ---- (2) functions with count==0 -------------------------------------
    zero_funcs = []
    for fn in funcs:
        if fn.get("count", 0) == 0:
            fls = fn.get("filenames", [])
            b = base_of(fls[0]) if fls else "?"
            zero_funcs.append({"name": fn["name"], "file": b})
    by_file = collections.Counter(r["file"] for r in zero_funcs)
    with open(os.path.join(REP, "funcs_zero_by_file.txt"), "w") as f:
        for b, n in by_file.most_common():
            f.write(f"{b:28s} {n:5d}\n")
    with open(os.path.join(REP, "funcs_zero_key.txt"), "w") as f:
        sel = [r for r in zero_funcs if base_of(r["file"])[:-2] in KEY_BASE]
        for r in sorted(sel, key=lambda r: (r["file"], r["name"])):
            f.write(f"{r['file']:20s} {r['name']}\n")
    print(f"zero-count functions: {len(zero_funcs)}", flush=True)

    # ---- (3) uncovered lines in KEY files --------------------------------
    line_map = {}
    for f in files:
        b = base_of(f["filename"])
        if b[:-2] not in KEY_BASE and b not in KEY_FILES:
            continue
        inst, cov = set(), set()
        for seg in f["segments"]:
            line, col, count, hascount = seg[0], seg[1], seg[2], seg[3]
            if hascount and line > 0:
                inst.add(line)
                if count > 0:
                    cov.add(line)
        line_map[b] = {
            "inst": inst, "cov": cov, "uncov": sorted(inst - cov),
            "pct": (100.0 * len(cov) / len(inst)) if inst else 0,
        }
    with open(os.path.join(REP, "key_uncovered_lines.json"), "w") as f:
        json.dump({b: {"uncov": v["uncov"], "inst": len(v["inst"]),
                       "cov": len(v["cov"]), "pct": v["pct"]}
                   for b, v in line_map.items()}, f, indent=1)
    with open(os.path.join(REP, "key_files_line_summary.txt"), "w") as f:
        f.write(f"{'file':22s} {'inst':>6s} {'cov':>6s} {'uncov':>6s} {'pct':>7s}\n")
        for b in sorted(line_map):
            v = line_map[b]
            f.write(f"{b:22s} {len(v['inst']):6d} {len(v['cov']):6d} "
                    f"{len(v['uncov']):6d} {v['pct']:7.2f}\n")
    print("wrote key-file line reports", flush=True)

    # ---- (4) totals -------------------------------------------------------
    tot = data["totals"]
    with open(os.path.join(REP, "totals.txt"), "w") as f:
        json.dump(tot, f, indent=1)
    print("TOTAL line%:", tot["lines"]["percent"], flush=True)

if __name__ == "__main__":
    main()
