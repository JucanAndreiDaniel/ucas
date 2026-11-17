"""Symbolic-difference oracle harness.

Builds a deterministic corpus of 200+ rational-function pairs, computes ground
truth with an INDEPENDENT exact oracle (fractions.Fraction evaluation at many
rational points), and compares against ucas `equiv` (real + bounded int + i8)
and `expand`/`simplify` on the exact difference.

Outputs (all under _scratch/, none are goldens):
  _scratch/oracle_report.json - full per-pair record
  _scratch/mismatches.md      - human-readable discrepancy summary
  _scratch/shape_report.json  - shape-reduction verification summary
"""
from __future__ import annotations

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

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from fractions import Fraction

from corpus import build_corpus, oracle_verdict
from shapes import verify as verify_shapes

BIN = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, "_scratch")


# ---------------------------------------------------------------------------
# MCP batch driver
# ---------------------------------------------------------------------------

def run_mcp(calls, timeout=60):
    """calls: list of (id, op, args). Returns id -> structuredContent dict."""
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "stress", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
    ]
    for cid, op, args in calls:
        lines.append(json.dumps({
            "jsonrpc": "2.0", "id": cid, "method": "tools/call",
            "params": {"name": op, "arguments": args},
        }))
    payload = "\n".join(lines) + "\n"
    try:
        proc = subprocess.run([BIN, "--mcp"], input=payload, text=True,
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        print("MCP TIMEOUT after %ss" % timeout, file=sys.stderr)
        return {}, {"timeout": True, "partial": (e.stdout or "")[-2000:]}
    out = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        cid = obj.get("id")
        if cid is None or "result" not in obj:
            continue
        sc = obj["result"].get("structuredContent")
        if sc is None:
            # still capture a bare text error
            out[cid] = {"ok": False, "raw": obj["result"]}
            continue
        out[cid] = sc
    meta = {"rc": proc.returncode, "stderr": proc.stderr[-2000:]}
    return out, meta


def make_equiv_calls(pairs, id_offset):
    """Build MCP calls for all comparison queries; returns calls + index map."""
    calls = []
    idx = {}
    cid = id_offset
    for p in pairs:
        fs = p["f"].render()
        gs = p["g"].render()
        diff = "(" + fs + ") - (" + gs + ")"
        names = sorted(p["f"].vars() | p["g"].vars())

        def params(t, rng=None):
            out = []
            for nm in names:
                d = {"name": nm, "type": t}
                if rng is not None:
                    d["range"] = list(rng)
                out.append(d)
            return out

        queries = {
            "expand_real": ("algebra", {"op": "expand", "args": {"f": diff}}),
            "simplify_real": ("algebra", {"op": "simplify", "args": {"f": diff}}),
            "equiv_real": ("analyze", {"op": "equiv", "args": {
                "f": {"body": fs, "params": params("real")},
                "g": {"body": gs, "params": params("real")}}}),
            "equiv_int": ("analyze", {"op": "equiv", "args": {
                "f": {"body": fs, "params": params("int", (-4, 4))},
                "g": {"body": gs, "params": params("int", (-4, 4))}}}),
            "equiv_i8": ("analyze", {"op": "equiv", "args": {
                "f": {"body": p["f"].render(pow_as_mul=True), "params": params("i8")},
                "g": {"body": p["g"].render(pow_as_mul=True), "params": params("i8")}}}),
        }
        idx[p["id"]] = {}
        for key, (op, args) in queries.items():
            cid += 1
            calls.append((cid, op, args))
            idx[p["id"]][key] = cid
    return calls, idx, cid


# ---------------------------------------------------------------------------
# counterexample exact re-evaluation
# ---------------------------------------------------------------------------

_CE_RE = re.compile(r"(?:x|y|z|a|b|u|v)\s*=\s*-?\d+(?:\.\d+)?|/|-?\d+(?:\.\d+)?")


def parse_counterexample(text):
    """Parse 'x=-9.98, y=-10: 399.2 vs 399.2' -> (env, left, right)."""
    if not text or ":" not in text:
        return None
    lhs, rhs = text.split(":", 1)
    numpat = r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    env = {}
    for m in re.finditer(r"([A-Za-z]\w*)\s*=\s*" + numpat, lhs):
        env[m.group(1)] = Fraction(m.group(2))
    vm = re.findall(numpat, rhs)
    if not env or len(vm) < 2:
        return None
    return env, Fraction(vm[0]), Fraction(vm[1])


def check_counterexample(p, text):
    """Return a dict describing whether a counterexample survives exact eval."""
    parsed = parse_counterexample(text)
    if parsed is None:
        return {"parsed": False}
    env, printed_l, printed_r = parsed
    # only keep variables that actually appear; pad missing ones with 0
    needed = p["f"].vars() | p["g"].vars()
    for nm in needed:
        env.setdefault(nm, Fraction(0))
    try:
        fl = p["f"].eval(env)
        gl = p["g"].eval(env)
    except Exception as e:
        return {"parsed": True, "eval_error": str(e), "env": {k: str(v) for k, v in env.items()}}
    exact_diff = fl - gl
    printed_identical = (printed_l == printed_r)
    exact_equal = (exact_diff == 0)
    return {
        "parsed": True,
        "env": {k: str(v) for k, v in env.items()},
        "exact_f": str(fl), "exact_g": str(gl),
        "exact_diff": str(exact_diff),
        "printed_l": str(printed_l), "printed_r": str(printed_r),
        "printed_identical": printed_identical,
        "exact_equal": exact_equal,
        "counterexample_fails": exact_equal,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def extract(query_sc):
    """Normalise a structuredContent into a compact dict."""
    if query_sc is None:
        return {"missing": True}
    if not query_sc.get("ok", True):
        return {"ok": False, "error": query_sc.get("error", {}),
                "text": query_sc.get("text", "")}
    res = query_sc.get("result") or {}
    if res.get("kind") == "equiv":
        return {"equal": res.get("equal"), "exhaustive": res.get("exhaustive"),
                "mismatch_points": res.get("mismatch_points"),
                "method": res.get("method"),
                "counterexample": res.get("counterexample", ""),
                "text": query_sc.get("text", "")}
    if res.get("kind") in ("expand", "simplify"):
        return {"result": res.get("result"), "conditions": query_sc.get("conditions", []),
                "text": query_sc.get("text", "")}
    return {"raw": res, "text": query_sc.get("text", "")}


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    pairs = build_corpus()
    print("corpus size:", len(pairs))

    calls, idx, _ = make_equiv_calls(pairs, 1000)
    print("MCP calls:", len(calls))

    # Split into chunks to be safe about long single sessions.
    chunk_size = 480
    responses = {}
    metas = []
    for start in range(0, len(calls), chunk_size):
        chunk = calls[start:start + chunk_size]
        print("running chunk", start, "..", start + len(chunk))
        r, meta = run_mcp(chunk, timeout=120)
        responses.update(r)
        metas.append(meta)
        if meta.get("timeout"):
            print("WARNING: chunk timed out", file=sys.stderr)

    results = []
    for p in pairs:
        ov, od = oracle_verdict(p["f"], p["g"])
        q = {}
        for key, cid in idx[p["id"]].items():
            q[key] = extract(responses.get(cid))
        rec = {
            "id": p["id"], "family": p["family"], "shape": p["shape"],
            "note": p["note"], "intended": p["intended"],
            "f": p["f"].render(), "g": p["g"].render(),
            "oracle": {"is_identity": ov, "detail": od},
            "queries": q,
        }
        # counterexample checks on real and i8 equiv
        for key in ("equiv_real", "equiv_i8"):
            ce = q.get(key, {}).get("counterexample", "")
            rec.setdefault("ce_check", {})[key] = check_counterexample(p, ce)
        results.append(rec)

    report = {"count": len(pairs), "metas": metas, "results": results}
    with open(os.path.join(SCRATCH, "oracle_report.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)

    shapes, reusable, inconsistent = verify_shapes(pairs, {r["id"]: r for r in results})
    with open(os.path.join(SCRATCH, "shape_report.json"), "w") as fh:
        json.dump({"classes": shapes, "reusable_queries": reusable,
                   "inconsistent": inconsistent}, fh, indent=1, default=str)

    # ---- console summary ----
    cats = defaultdict(list)
    for r in results:
        ov = r["oracle"]["is_identity"]
        er = r["queries"].get("equiv_real", {}).get("equal")
        ei = r["queries"].get("equiv_int", {}).get("equal")
        e8 = r["queries"].get("equiv_i8", {}).get("equal")
        ex = r["queries"].get("expand_real", {}).get("result")
        sm = r["queries"].get("simplify_real", {}).get("result")
        if er is not None and er != ov:
            cats["real_disagree"].append(r)
        if ei is not None and ei != ov:
            cats["int_disagree"].append(r)
        if e8 is not None and e8 != ov:
            cats["i8_disagree"].append(r)
        if ex is not None and (ex.strip() == "0") != ov:
            cats["expand_disagree"].append(r)
        if sm is not None and (sm.strip() == "0") != ov:
            cats["simplify_disagree"].append(r)
        for key in ("equiv_real", "equiv_i8"):
            cc = r["ce_check"][key]
            if cc.get("counterexample_fails"):
                cats["ce_fails_" + key].append(r)
            if cc.get("parsed") and cc.get("printed_identical"):
                cats["ce_identical_" + key].append(r)

    print("\n=== DISCREPANCY COUNTS ===")
    for k in sorted(cats):
        print("  %-24s %d" % (k, len(cats[k])))
    print("\n=== SHAPE REDUCTION ===")
    print("  equivalence classes:", len(shapes))
    print("  structural_ok all:", all(s["structural_ok"] for s in shapes))
    print("  reusable engine queries:", reusable)
    print("  inconsistent classes:", len(inconsistent))

    # write human-readable mismatch summary
    with open(os.path.join(SCRATCH, "mismatches.md"), "w") as fh:
        fh.write("# Discrepancies (oracle vs ucas)\n\n")
        for k in sorted(cats):
            fh.write("## %s (%d)\n\n" % (k, len(cats[k])))
            for r in cats[k][:40]:
                q = r["queries"]
                fh.write("- **%s** [%s] oracle=%s f=`%s` g=`%s`\n" % (
                    r["id"], r["family"], r["oracle"]["is_identity"],
                    r["f"], r["g"]))
                fh.write("  equiv_real=%s (%s)  equiv_int=%s  equiv_i8=%s  expand=%r simplify=%r\n" % (
                    q.get("equiv_real", {}).get("equal"),
                    q.get("equiv_real", {}).get("counterexample", ""),
                    q.get("equiv_int", {}).get("equal"),
                    q.get("equiv_i8", {}).get("equal"),
                    q.get("expand_real", {}).get("result"),
                    q.get("simplify_real", {}).get("result")))
            fh.write("\n")
    print("\nwrote oracle_report.json and _scratch/mismatches.md")


if __name__ == "__main__":
    main()
