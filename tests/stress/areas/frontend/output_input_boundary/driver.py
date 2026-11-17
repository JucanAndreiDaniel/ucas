#!/usr/bin/env python3
"""
driver.py -- output_input_boundary stress driver.

Focus: the seam where one ucas tool's OUTPUT becomes another tool's INPUT.
It generates 200+ chained cases and hunts for outputs that do not round-trip,
self-amplifying errors, state leaks across generations, crashes, hangs and
nondeterminism.

All writes stay in this folder.  Every subprocess is bounded by a timeout.
Run:  python3 driver.py            (full run, writes driver_results.json)
      python3 driver.py --quick    (subset, for a fast smoke check)

The driver is deterministic: seeds and budgets are fixed, no wall-clock based
decisions feed into goldens.  Goldens (deterministic chains only) are emitted
as *.jsonl / *.ucas + *.out next to this file; nondeterministic / crashing
chains are NOT turned into goldens -- they are only recorded in the log.
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
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

UCAS = str(_REPO_ROOT / "ucas")
HERE = Path(__file__).resolve().parent
TIMEOUT = 12
RESULT_LOG = HERE / "driver_results.json"

INIT = [
    {"jsonrpc": "2.0", "id": 0, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "stress-oib", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
]

# ---------------------------------------------------------------------------
# low-level runners
# ---------------------------------------------------------------------------
_err_re = re.compile(
    r"error: (?:unexpected|expected|parse_error|ambiguous|domain_error|"
    r"unknown|not defined|no theorem|cannot|unsupported|failed)", re.I)
_crash_re = re.compile(r"Segmentation|Aborted|core dumped|AddressSanitizer|"
                      r"runtime error:|free\(\)|double free|Assertion", re.I)


def run_cli(source, timeout=TIMEOUT, as_file=False, tag=""):
    """Run raw ucas source. Returns a dict describing the outcome."""
    t0 = time.time()
    if as_file:
        path = HERE / ("_case_%d.ucas" % os.getpid())
        path.write_text(source)
        argv = [UCAS, str(path)]
    else:
        argv = [UCAS]
    try:
        p = subprocess.run(argv, input=None if as_file else source,
                           capture_output=True, text=True, timeout=timeout,
                           cwd=str(HERE))
        rc, out, err = p.returncode, p.stdout, p.stderr
        timedout = False
    except subprocess.TimeoutExpired as e:
        rc = -99
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        timedout = True
    if as_file:
        try: path.unlink()
        except OSError: pass
    dur = round(time.time() - t0, 3)
    combined = out + ("\n" + err if err else "")
    return {
        "tag": tag, "rc": rc, "out": out, "err": err, "combined": combined,
        "dur": dur, "timedout": timedout,
        "parse_err": bool(_err_re.search(combined)),
        "crash": (rc is not None and rc < 0 and rc != -99) or bool(_crash_re.search(combined)),
        "len": len(out),
    }


def mcp_batch(requests, timeout=40):
    """Run a batch of tools/call requests in ONE --mcp process (state persists).

    requests: list of (id, tool, args).  Returns {id: response-object}.
    """
    lines = list(INIT)
    for rid, tool, args in requests:
        lines.append({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                      "params": {"name": tool, "arguments": args}})
    payload = "\n".join(json.dumps(x) for x in lines) + "\n"
    t0 = time.time()
    try:
        p = subprocess.run([UCAS, "--mcp"], input=payload, capture_output=True,
                           text=True, timeout=timeout, cwd=str(HERE))
        raw = p.stdout
    except subprocess.TimeoutExpired as e:
        raw = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
    byid = {}
    for line in raw.splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        if "id" in o:
            byid[o["id"]] = o
    return byid, round(time.time() - t0, 3)


def resp(byid, rid):
    """Extract structuredContent from a tools/call response."""
    o = byid.get(rid, {})
    r = o.get("result", {})
    sc = r.get("structuredContent", r)
    return sc, (o.get("error") or sc.get("error"))


def content_blocks(byid, rid):
    """MCP content[] blocks (images arrive here, not in files[].base64)."""
    o = byid.get(rid, {})
    r = o.get("result", {})
    return r.get("content") or []


def classify(res):
    """Map a runner result to a short anomaly label."""
    if res["timedout"]: return "HANG"
    if res["crash"]: return "CRASH"
    if res["rc"] not in (0,): return "RC%d" % res["rc"]
    if res["parse_err"]: return "PARSE_ERR"
    return "OK"


# ---------------------------------------------------------------------------
# seed catalogs
# ---------------------------------------------------------------------------
# Group A seeds: single commands whose textual output we paste back verbatim.
SEEDS_A = [
    "show sin(1)", "show cos(0.5)", "show 2^10", "show 1/3", "show pi",
    "show isqrt(x: u8)", "show x^2 + 3x + 2",
    "parse x^2 + 3x + 2", "parse sin(x)*cos(x)", "parse (a+b)^3",
    "simplify (x^2-1)/(x-1)", "simplify x/x", "simplify sin(x)^2+cos(x)^2",
    "expand (x+1)^4", "expand (x+y)*(x-y)", "factor x^2-1",
    "factor x^4-1", "together 1/x+1/y", "cancel x^2/x",
    "diff x^3 - 3x", "diff sin(x)*cos(x)", "diff exp(x^2)",
    "integrate 2x", "integrate sin(x)", "antiderivative x^2",
    "limit sin(x)/x x -> 0", "taylor exp(x) at 0 order 5",
    "gcd x^2-1 x^3-1", "lcm x y", "solve x^2 = 4 for x",
    "complex 1 + i", "re (1+2i)*(3-i)", "modulus 3+4i",
    "f(x: i8) = x*x\nrange f", "f(x: i8) = 1/x\ndomain f",
    "f(x: i8) = x+1\ng(x: i8) = 1+x\nequiv f g",
    "f(x: u8) = x+1\ncost f", "identify x^2+2x+1",
    "zeros x^2-5x+6", "parity x^3", "f(x: u4) = x*x\ntable f",
    "f(x: u8) = x+1\nwrap f", "f(x: real) = x^3-3x\ncrit f",
]

# English seeds for group G.
SEEDS_ENGLISH = [
    "what is 2+2", "what is 3 times 4", "what is the square of 5",
    "what is x squared plus 2x plus 1", "compute 10 divided by 4",
    "what is the range of x squared for a signed byte x?",
    "is x squared even?", "what is the derivative of x cubed",
    "what is the sine of 1", "simplify (x^2-1)/(x-1)",
    "what is 2 to the power 8", "what is the factorial of 5",
    "is 1 less than 2", "what is the gcd of 12 and 18",
    "what is the integral of 2x", "solve x^2 = 4",
    "what is the range of x for an unsigned byte x?",
    "define f of x as x squared", "forget everything", "show f",
]

# C snippets for group D (c optimize -> re-optimize).
C_SNIPPETS = [
    "int f(int x){return x+1;}",
    "int f(int x){return x*2;}",
    "int f(int x){return x*x + 2*x + 1;}",
    "int f(int x){return (x & 15) + (x >> 4);}",
    "int f(int x){return x < 0 ? -x : x;}",
    "int f(int x, int y){return x + y + x + y;}",
    "unsigned f(unsigned x){return x*3;}",
    "int f(int x){return (x+1)*(x-1);}",
]

# SPIR-V/GLSL-ish snippets for group E.
GLSL_SNIPPETS = [
    "int f(int x){return x+1;}",
    "int f(int x){return x*3+1;}",
    "int f(int x){return (x&7)+1;}",
]

# Theorems for group F (proof text round-trip).
THEOREMS = [
    "forall x:int: x + 1 > x",
    "forall x y:int: x + y = y + x",
    "forall x:int: 2*x = x + x",
    "forall x y z:int: (x + y) + z = x + (y + z)",
    "forall x:int: x <= x + 1",
    "forall x:int: not (x < x)",
    "forall x y:int: x <= y and y <= x -> x = y",
    "forall x y z:int: x + y = x + z -> y = z",
]

# find seeds (typed) for group B.
FIND_SEEDS = [
    ("f1", "i8", "x*x + 2x + 1"),
    ("f2", "u8", "x + 1"),
    ("f3", "u8", "x*3"),
    ("f4", "i8", "x*x"),
    ("f5", "u8", "(x & 15) + (x >> 4)"),
    ("f6", "i8", "x + x + x"),
    ("f7", "u8", "x ^ 255"),
    ("f8", "f32", "x*x + 2x + 1"),
]

# gates seeds for group C (<=6 input bits).
GATES_SEEDS = [
    ("g1", "x: u2,y:u2", "(x&y)|(x|y)"),
    ("g2", "x: u1,y:u1", "x & y"),
    ("g3", "x: u2,y:u2", "x | y"),
    ("g4", "x: u3", "x + 1"),
    ("g5", "x: u1,y:u1,z:u1", "(x&y)|z"),
]


# ---------------------------------------------------------------------------
# case groups
# ---------------------------------------------------------------------------
def group_A(log):
    """Feed the FULL text field of a CLI answer back as ucas source, 4 gens."""
    n = 0
    for seed in SEEDS_A:
        text = seed + "\n"
        gens = []
        for gen in range(5):  # gen 0 = original, then 4 re-ingestions
            res = run_cli(text, tag="A:%s:g%d" % (seed[:18], gen))
            gens.append({"gen": gen, "label": classify(res),
                         "len": res["len"], "out_head": res["out"][:400],
                         "rc": res["rc"], "timedout": res["timedout"]})
            if res["timedout"] or res["crash"] or res["rc"] not in (0,):
                break
            # feed the entire textual output back as the next source
            text = res["out"]
            if not text.strip():
                break
            n += 1
        log.append({"group": "A_text_feedback", "seed": seed, "gens": gens})
    return n


def group_A_file(log):
    """Same, but as a .ucas FILE (idea #1 mentions both source and file)."""
    n = 0
    for seed in SEEDS_A[:12]:
        text = seed + "\n"
        gens = []
        for gen in range(4):
            res = run_cli(text, as_file=True, tag="Af:%s:g%d" % (seed[:14], gen))
            gens.append({"gen": gen, "label": classify(res), "len": res["len"],
                         "out_head": res["out"][:300]})
            if res["timedout"] or res["crash"] or res["rc"] not in (0,):
                break
            text = res["out"]
            if not text.strip(): break
            n += 1
        log.append({"group": "A_file_feedback", "seed": seed, "gens": gens})
    return n


def group_B_find_equiv(log):
    """find -> take expr -> define g -> equiv f g -> find on g, iterate."""
    n = 0
    for name, ty, body in FIND_SEEDS:
        src = "%s(x: %s) = %s\nfind %s 2" % (name, ty, body, name)
        byid, dur = mcp_batch([(1, "ucas", {"source": src, "timeout_s": 8})])
        sc, err = resp(byid, 1)
        exprs = []
        if sc and sc.get("ok"):
            r = sc.get("result") or {}
            for e in (r.get("peephole") or []) + (r.get("implementations") or []):
                if e.get("expr"): exprs.append(e["expr"])
        exprs = sorted(set(exprs))[:3]
        chain = []
        prev = body
        for i, ex in enumerate(exprs):
            csrc = ("%s(x: %s) = %s\ng_i(x: %s) = %s\nequiv %s g_i\n"
                    "find g_i 1" % (name, ty, prev, ty, ex, name))
            res = run_cli(csrc, tag="B:%s:%d" % (name, i))
            chain.append({"expr": ex, "label": classify(res),
                          "out_head": res["out"][:400], "dur": res["dur"]})
            n += 1
            prev = ex
        log.append({"group": "B_find_equiv", "seed": name, "type": ty,
                    "body": body, "found_exprs": exprs, "chain": chain,
                    "extract_dur": dur, "extract_err": bool(err)})
    return n


def group_C_gates_equiv(log):
    """gates -> take program exprs -> build function -> equiv."""
    n = 0
    for name, params, body in GATES_SEEDS:
        src = "%s(%s) = %s\ngates %s" % (name, params, body, name)
        byid, dur = mcp_batch([(1, "ucas", {"source": src, "timeout_s": 8,
                                            "assume": {"caret": "xor"}})])
        sc, err = resp(byid, 1)
        exprs = []
        if sc and sc.get("ok"):
            prog = (sc.get("result") or {}).get("program") or []
            for st in prog:
                if st.get("expr"): exprs.append(st["expr"])
        chain = []
        if exprs:
            # use the last expr as a candidate replacement fn (may need many
            # temps; just round-trip each emitted expr through equiv on a
            # freshly defined 1-bit fn where possible)
            pnames = [p.strip() for p in params.split(",")]
            for i, ex in enumerate(exprs[:3]):
                # wrap into a definition using the same params, then equiv
                csrc = "%s(%s) = %s\ng_i(%s) = %s\nequiv %s g_i" % (
                    name, params, body, params, ex, name)
                res = run_cli(csrc, tag="C:%s:%d" % (name, i))
                chain.append({"expr": ex, "label": classify(res),
                              "out_head": res["out"][:300]})
                n += 1
        log.append({"group": "C_gates_equiv", "seed": name, "program_exprs": exprs,
                    "chain": chain, "extract_err": bool(err)})
    return n


def group_D_c_optimize(log):
    """c optimize -> take result.code -> re-optimize / feed to spirv_simplify."""
    n = 0
    for i, code in enumerate(C_SNIPPETS):
        byid, dur = mcp_batch([(1, "c", {"op": "c_optimize", "args": {
            "code": code, "nofile": True, "budget": 6}})])
        sc, err = resp(byid, 1)
        out_code = None
        if sc and sc.get("ok"):
            out_code = (sc.get("result") or {}).get("code")
        chain = []
        if out_code:
            # re-ingest the emitted C
            b2, _ = mcp_batch([(1, "c", {"op": "c_optimize", "args": {
                "code": out_code, "nofile": True, "budget": 6}})])
            s2, e2 = resp(b2, 1)
            chain.append({"step": "c_optimize(emitted_code)", "ok": bool(s2 and s2.get("ok")),
                          "err": (e2 or {}).get("message") if e2 else None})
            n += 1
            # feed emitted C into spirv_simplify (lang c)
            b3, _ = mcp_batch([(1, "spirv_simplify", {"code": out_code, "lang": "c",
                                                      "nofile": True, "budget": 4})])
            s3, e3 = resp(b3, 1)
            chain.append({"step": "spirv_simplify(emitted_code)", "ok": bool(s3 and s3.get("ok")),
                          "err": (e3 or {}).get("message") if e3 else None})
            n += 1
        log.append({"group": "D_c_roundtrip", "seed": code, "out_code": out_code,
                    "chain": chain, "extract_err": bool(err)})
    return n


def group_E_spirv_roundtrip(log):
    """spirv_simplify -> take emitted code -> re-simplify."""
    n = 0
    for code in GLSL_SNIPPETS:
        b1, _ = mcp_batch([(1, "spirv_simplify", {"code": code, "lang": "c",
                                                  "nofile": True, "budget": 4})])
        s1, e1 = resp(b1, 1)
        out_code = None
        if s1 and s1.get("ok"):
            out_code = (s1.get("result") or {}).get("code")
        chain = []
        if out_code:
            b2, _ = mcp_batch([(1, "spirv_simplify", {"code": out_code, "lang": "c",
                                                      "nofile": True, "budget": 4})])
            s2, e2 = resp(b2, 1)
            chain.append({"step": "spirv_simplify(emitted_code)",
                          "ok": bool(s2 and s2.get("ok")),
                          "err": (e2 or {}).get("message") if e2 else None})
            n += 1
        log.append({"group": "E_spirv_roundtrip", "seed": code, "out_code": out_code,
                    "chain": chain, "extract_err": bool(e1)})
    return n


def group_F_proofs(log):
    """theorem -> prove -> proof text -> proof_check / prove(text) (idea #14/#47)."""
    n = 0
    for i, st in enumerate(THEOREMS):
        reqs = [
            (1, "proofs", {"op": "theorem", "args": {"name": "t%d" % i, "statement": st}}),
            (2, "proofs", {"op": "prove", "args": {"name": "t%d" % i}}),
            (3, "proofs", {"op": "proof", "args": {"name": "t%d" % i}}),
            (4, "proofs", {"op": "proof_check", "args": {"name": "t%d" % i}}),
        ]
        byid, dur = mcp_batch(reqs)
        s1, e1 = resp(byid, 1)
        s2, e2 = resp(byid, 2)
        s3, e3 = resp(byid, 3)
        s4, e4 = resp(byid, 4)
        proof_text = (s3 or {}).get("text") if s3 else None
        chain = []
        # feed proof text into proof_check as 'text' (should be a clean bad_request)
        if proof_text:
            b2, _ = mcp_batch([(1, "proofs", {"op": "proof_check",
                                              "args": {"text": proof_text}})])
            s5, e5 = resp(b2, 1)
            chain.append({"step": "proof_check(text=<proof text>)",
                          "ok": bool(s5 and s5.get("ok")),
                          "err": (e5 or {}).get("message") if e5 else None})
            n += 1
            # feed proof text back as raw ucas source
            res = run_cli(proof_text, tag="F:rawproof:%d" % i)
            chain.append({"step": "ucas source=<proof text>",
                          "label": classify(res), "out_head": res["out"][:200]})
            n += 1
            # feed the theorem statement (clean round-trippable text) back
            ttext = (s1 or {}).get("text") if s1 else None
            if ttext:
                res2 = run_cli(ttext, tag="F:thm:%d" % i)
                chain.append({"step": "ucas source=<theorem printed text>",
                              "label": classify(res2), "out_head": res2["out"][:200]})
                n += 1
        log.append({"group": "F_proofs", "statement": st,
                    "theorem_ok": bool(s1 and s1.get("ok")),
                    "prove_ok": bool(s2 and s2.get("ok")),
                    "check_ok": bool(s4 and s4.get("ok")),
                    "proof_text": proof_text, "chain": chain})
    return n


def group_G_english(log):
    """english statements -> fresh ucas; english text -> english text (ideas #3/#25/#41)."""
    n = 0
    for text in SEEDS_ENGLISH:
        b1, _ = mcp_batch([(1, "english", {"text": text})])
        s1, e1 = resp(b1, 1)
        stmts = []
        if s1 and s1.get("ok"):
            stmts = ((s1.get("result") or {}).get("statements") or [])
        chain = []
        # feed each emitted ucas statement into a FRESH ucas process
        for st in stmts[:3]:
            res = run_cli(st + "\n", tag="G:stmt:" + st[:20])
            chain.append({"step": "ucas(statement)", "stmt": st,
                          "label": classify(res), "out_head": res["out"][:200]})
            n += 1
        # feed the whole text field back into english (self-translation loop)
        ttext = (s1 or {}).get("text")
        if ttext:
            b2, _ = mcp_batch([(1, "english", {"text": ttext})])
            s2, e2 = resp(b2, 1)
            chain.append({"step": "english(text=<full output text>)",
                          "ok": bool(s2 and s2.get("ok")),
                          "understood": ((s2 or {}).get("result") or {}).get("understood"),
                          "err": (e2 or {}).get("message") if e2 else None})
            n += 1
        # feed emitted statements back as one ucas source block (fresh process)
        if stmts:
            res = run_cli("\n".join(stmts) + "\n", tag="G:allstmts")
            chain.append({"step": "ucas(all statements)", "label": classify(res),
                          "out_head": res["out"][:300]})
            n += 1
        log.append({"group": "G_english", "seed": text, "statements": stmts,
                    "extract_err": bool(e1), "chain": chain})
    return n


def group_H_files(log):
    """plot emits a GIF (files[] + MCP content image); feed it back into animate
    both as base64 (png_base64) and as a file path (idea #4)."""
    n = 0
    b1, _ = mcp_batch([(1, "plot", {"op": "plot", "args": {
        "fs": "x^3 - 3x"}, "files": "both"})])
    s1, e1 = resp(b1, 1)
    files = (s1 or {}).get("files") or [] if s1 else []
    blocks = content_blocks(b1, 1)
    b64 = None
    for blk in blocks:
        if blk.get("type") == "image" and blk.get("data"):
            b64 = blk["data"]; break
    path = None
    for f in files:
        if f.get("path"): path = f["path"]; break
    chain = []
    if b64:
        b2, _ = mcp_batch([(1, "plot", {"op": "animate", "args": {
            "spec": "scan", "inputs": [{"png_base64": b64}],
            "nofile": True}})], timeout=45)
        s2, e2 = resp(b2, 1)
        chain.append({"step": "animate(inputs=[{png_base64:<GIF>}])",
                      "ok": bool(s2 and s2.get("ok")),
                      "err": (e2 or {}).get("message") if e2 else None,
                      "text": ((s2 or {}).get("text") or "")[:200] if s2 else None})
        n += 1
    if path:
        b3, _ = mcp_batch([(1, "plot", {"op": "animate", "args": {
            "spec": "scan", "inputs": [{"file": path}],
            "nofile": True}})], timeout=45)
        s3, e3 = resp(b3, 1)
        chain.append({"step": "animate(inputs=[{file:<self GIF path>}])",
                      "ok": bool(s3 and s3.get("ok")),
                      "err": (e3 or {}).get("message") if e3 else None,
                      "text": ((s3 or {}).get("text") or "")[:200] if s3 else None})
        n += 1
    log.append({"group": "H_files", "n_files": len(files),
                "mimes": [f.get("mime") for f in files],
                "files_have_base64_field": any("base64" in f for f in files),
                "b64_len": len(b64) if b64 else 0, "path": path,
                "chain": chain, "extract_err": bool(e1)})
    return n


def group_J_state_leak(log):
    """Same session: feed 3 different machine-output strings that DO parse,
    then check whether introspection (state/funcs) sees the resulting defs.
    A prose line emitted by `diff` parses into a hidden anonymous definition."""
    n = 0
    feeds = [
        "holds for every real x",                       # diff's own note line
        "_() = 0.8414709848",                            # show's definition (clean)
        "d/dx x^3 - 3x = 3x^2 - 3",                     # diff's own headline
    ]
    reqs = [(1, "session", {"op": "state"})]
    rid = 2
    for i, src in enumerate(feeds):
        reqs.append((rid, "ucas", {"source": src})); rid += 1
        reqs.append((rid, "session", {"op": "state"})); rid += 1
        reqs.append((rid, "session", {"op": "funcs"})); rid += 1
    reqs.append((rid, "session", {"op": "state"})); rid += 1
    byid, dur = mcp_batch(reqs)
    stages = []
    for i, src in enumerate(feeds):
        sid = 2 + i * 3
        sc, err = resp(byid, sid)
        st_sc, _ = resp(byid, sid + 1)
        fn_sc, _ = resp(byid, sid + 2)
        stages.append({
            "gen": i, "fed": src,
            "ucas_text": ((sc or {}).get("text") or "")[:400],
            "state_functions": ((st_sc or {}).get("result") or {}).get("functions"),
            "funcs_text": ((fn_sc or {}).get("text") or "")[:200],
        })
        n += 3
    final_sc, _ = resp(byid, rid - 1)
    log.append({"group": "J_state_leak", "stages": stages,
                "final_functions": ((final_sc or {}).get("result") or {}).get("functions")})
    return n


def group_K_amplification(log):
    """Precise self-amplification measurement for a canonical error chain."""
    text = "show sin(1)\n"
    series = []
    for gen in range(6):
        r = run_cli(text, tag="K:amp:%d" % gen)
        series.append({"gen": gen, "len": r["len"], "label": classify(r),
                       "out": r["out"]})
        if r["timedout"] or r["len"] > 400000:
            break
        text = r["out"]
        if not text.strip(): break
    log.append({"group": "K_amplification", "series":
                [{"gen": s["gen"], "len": s["len"], "label": s["label"]} for s in series],
                "final_out_head": series[-1]["out"][:600] if series else ""})
    return len(series)


def group_I_witness(log):
    """equiv counterexample witness -> feed printed point back as expression."""
    n = 0
    pairs = [
        ("i8", "x*x", "(x+1)*(x-1)"),
        ("u8", "x + 1", "x - 1"),
        ("f32", "x*x", "x*x + 1e-30"),
        ("i8", "x/2", "x*0.5"),
        ("u4", "x*x", "x<<1"),
        ("real", "(x^2-1)/(x-1)", "x+1"),
    ]
    for i, (ty, fb, gb) in enumerate(pairs):
        f, g = "f%d" % i, "g%d" % i
        src = "%s(x: %s) = %s\n%s(x: %s) = %s\nequiv %s %s" % (
            f, ty, fb, g, ty, gb, f, g)
        b1, _ = mcp_batch([(1, "ucas", {"source": src})])
        s1, e1 = resp(b1, 1)
        txt = (s1 or {}).get("text") or "" if s1 else ""
        chain = []
        # extract numbers from the witness text and feed them back as an expr
        nums = re.findall(r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", txt)
        for v in nums[:4]:
            res = run_cli("show " + v + "\n", tag="I:witness:%d:%s" % (i, v[:8]))
            chain.append({"step": "show(witness value)", "value": v,
                          "label": classify(res), "out_head": res["out"][:120]})
            n += 1
        log.append({"group": "I_witness", "f": f, "g": g, "body_f": fb, "body_g": gb,
                    "equiv_text": txt[:500], "chain": chain, "extract_err": bool(e1)})
    return n


# ---------------------------------------------------------------------------
# determinism check for a few would-be goldens
# ---------------------------------------------------------------------------
def determinism_checks(log):
    samples = [
        ("det_show", "show sin(1)\n"),
        ("det_selfeed", "_() = 0.8414709848\n  -> real\n"),
        ("det_find", "f(x: i8) = x*x + 2x + 1\nfind f 2\n"),
        ("det_equiv", "f(x: i8) = x*x\ng(x: i8) = (x+1)*(x-1)\nequiv f g\n"),
    ]
    out = {}
    for name, src in samples:
        a = run_cli(src, tag="det:%s:a" % name)
        b = run_cli(src, tag="det:%s:b" % name)
        out[name] = {
            "deterministic": (a["out"] == b["out"] and a["rc"] == b["rc"]),
            "label_a": classify(a), "len": a["len"],
        }
    log.append({"group": "Z_determinism", "samples": out})
    return 0


# ---------------------------------------------------------------------------
# golden emission (deterministic chains only)
# ---------------------------------------------------------------------------
def _golden_from_file(name):
    """Run a golden .ucas by its own (stable) filename; return combined output."""
    p = subprocess.run([UCAS, name], capture_output=True, text=True,
                       timeout=30, cwd=str(HERE))
    return p.stdout + (("\n" + p.stderr) if p.stderr else "")


def emit_goldens(log):
    """Emit a few deterministic boundary goldens."""
    written = []

    # 1) CLI golden: full-text feedback that produces the '-> real' parse error.
    g1 = "01_show_text_feedback.ucas"
    (HERE / g1).write_text("_() = 0.8414709848\n  -> real\n")
    (HERE / "01_show_text_feedback.out").write_text(_golden_from_file(g1))
    written.append(g1)

    # 2) CLI golden: english-emitted statements round-tripped into raw ucas.
    g2 = "02_english_statements_roundtrip.ucas"
    (HERE / g2).write_text("it(x: i8) = x^2\nrange it\n")
    (HERE / "02_english_statements_roundtrip.out").write_text(_golden_from_file(g2))
    written.append(g2)

    # 3) CLI golden: find expression fed back into equiv + find.
    g3 = "03_find_expr_roundtrip.ucas"
    (HERE / g3).write_text(
        "f(x: i8) = x*x + 2x + 1\n"
        "g(x: i8) = (x + 2)*x + 1\n"
        "equiv f g\n"
        "find f 2\n")
    (HERE / "03_find_expr_roundtrip.out").write_text(_golden_from_file(g3))
    written.append(g3)

    # 4) MCP golden: output of call N becomes literal input of call N+1.
    g4 = "mcp_output_to_input.jsonl"
    reqs = [
        INIT[0], INIT[1],
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "ucas", "arguments": {"source": "show sin(1)"}}},
        # call 2 input is verbatim text from call 1 (known deterministic)
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "ucas", "arguments": {"source": "_() = 0.8414709848\n  -> real\n"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "english", "arguments": {"text": "what is 2+2"}}},
        # call 4 input is the english-emitted ucas statement '2 + 2'
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "ucas", "arguments": {"source": "2 + 2\n"}}},
    ]
    (HERE / g4).write_text("\n".join(json.dumps(x) for x in reqs) + "\n")
    payload = (HERE / g4).read_text()
    r = subprocess.run([UCAS, "--mcp"], input=payload, capture_output=True,
                       text=True, timeout=40, cwd=str(HERE))
    (HERE / "mcp_output_to_input.out").write_text(r.stdout)
    written.append(g4)

    return written


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated group names")
    args = ap.parse_args()
    only = set(x.strip() for x in args.only.split(",") if x.strip())

    log = []
    total = 0
    groups = [
        ("A_text", group_A),
        ("A_file", group_A_file),
        ("B_find", group_B_find_equiv),
        ("C_gates", group_C_gates_equiv),
        ("D_c", group_D_c_optimize),
        ("E_spirv", group_E_spirv_roundtrip),
        ("F_proofs", group_F_proofs),
        ("G_english", group_G_english),
        ("H_files", group_H_files),
        ("I_witness", group_I_witness),
        ("J_state", group_J_state_leak),
        ("K_amp", group_K_amplification),
        ("Z_det", determinism_checks),
    ]
    for name, fn in groups:
        if only and name not in only:
            continue
        if args.quick and name in ("D_c", "E_spirv", "H_files", "I_witness"):
            continue
        t0 = time.time()
        try:
            c = fn(log)
            total += c
            print("[%s] %d chain steps (%.1fs)" % (name, c, time.time() - t0),
                  file=sys.stderr)
        except Exception as e:
            print("[%s] EXCEPTION %s" % (name, e), file=sys.stderr)
            log.append({"group": name, "EXCEPTION": str(e)})

    RESULT_LOG.write_text(json.dumps({"total_chain_steps": total, "cases": log},
                                     indent=1))
    print("total chain steps: %d -> %s" % (total, RESULT_LOG), file=sys.stderr)
    if not args.quick:
        w = emit_goldens(log)
        print("goldens written:", ", ".join(w), file=sys.stderr)


if __name__ == "__main__":
    main()
