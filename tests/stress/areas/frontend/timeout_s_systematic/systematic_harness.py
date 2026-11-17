#!/usr/bin/env python3
"""Systematic follow-up on the confirmed timeout-child desync (Top priority #2).

Generates 200+ request streams spanning the cross product

    timeout_variant x interface x request_pattern x repetition

and, for every stream, measures:
  * one-response-per-request (reply count vs request count)
  * id correctness (reply.id == request.id for each step)
  * session state unchanged (state.functions before vs after)
  * stray children (live ucas processes left in the process group)
  * error code == "timeout" on timed-out requests
  * what later calls do after a timeout (canary ok / hang / EOF)

Also runs a focused high-repetition desync measurement per interface and a
command-family sweep to find families where timeout_s is ignored.

Every process is spawned in its own session (start_new_session=True) and the
whole process group is SIGKILLed in a finally block, so no orphans survive.

Usage:  python3 systematic_harness.py [out.json]
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
import json, os, select, signal, subprocess, sys, time
from collections import Counter, defaultdict

BIN = str(_REPO_ROOT / "ucas")
READ_T = 1.2          # per-request reply deadline (hang detector)
DRAIN_T = 0.25        # drain leftover buffered replies at end of a stream
MODES = ("json", "mcp", "flat")
VARIANTS = ("none", "numeric", "string", "zero", "negative", "huge")
PATTERNS = ("single", "n_after", "interleaved", "two_timeouts", "crash", "reset")
REPS = 2

# ---------------------------------------------------------------- wire helpers
FAMILY = {  # grouped-MCP tool family for each op (None => top-level tool)
    "define": "session", "reset": "session", "state": "session", "funcs": "session",
    "show": "analyze", "gates": "analyze", "find": "analyze", "equiv": "analyze",
    "range": "analyze", "approx": "analyze", "fit": "analyze", "parse": "analyze",
    "prove": "proofs", "english": None, "ucas": None, "bigint": None,
    "c": None, "spirv_simplify": None, "x86check": None,
}

def mk(mode, rid, op, args, family=None):
    if mode == "json":
        return {"id": rid, "cmd": op, "args": args}
    if mode == "flat":
        return {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                "params": {"name": op, "arguments": args}}
    if op == "bigint":  # grouped MCP exposes bigint via the `ucas` tool
        return {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                "params": {"name": "ucas", "arguments": {"source": "bigint 2^200+1"}}}
    fam = FAMILY.get(op) if family is None else family
    params = ({"name": fam, "arguments": {"op": op, "args": args}}
              if fam else {"name": op, "arguments": args})
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": params}

def spawn(mode):
    flags = ["--json", "--files", "none"] if mode == "json" else (
            ["--mcp", "--flat"] if mode == "flat" else ["--mcp"])
    return subprocess.Popen([BIN] + flags, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1, start_new_session=True)

def readline(p, t=READ_T):
    try:
        r, _, _ = select.select([p.stdout], [], [], t)
        return p.stdout.readline() if r else None
    except (ValueError, OSError):
        return None

def handshake(p, mode):
    if mode == "json":
        return
    p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "stress-sys", "version": "1"}}}) + "\n")
    p.stdin.write(json.dumps({"jsonrpc": "2.0",
                              "method": "notifications/initialized"}) + "\n")
    p.stdin.flush(); readline(p); readline(p)

def extract(reply):
    """Return (reply_id, ok, error_code) from either envelope style."""
    if reply is None:
        return (None, None, None, "no-reply")
    try:
        o = json.loads(reply)
    except Exception:
        return (None, None, None, "bad-json")
    rid = o.get("id")
    sc = None
    res = o.get("result")
    if isinstance(res, dict):
        sc = res.get("structuredContent")
    env = sc if isinstance(sc, dict) else o
    ok = env.get("ok")
    err = env.get("error") or {}
    code = err.get("code")
    iserr = bool(res.get("isError")) if isinstance(res, dict) else False
    if code is None and iserr:
        code = "MCP-isError"
    return (rid, ok, code, "ok")

def state_functions(reply):
    """Extract list of defined function names from a state reply."""
    if reply is None:
        return None
    try:
        o = json.loads(reply)
    except Exception:
        return None
    res = o.get("result")
    sc = res.get("structuredContent") if isinstance(res, dict) else None
    env = sc if isinstance(sc, dict) else o
    r = env.get("result")
    if isinstance(r, dict) and r.get("kind") == "state":
        return sorted(f.get("name") for f in r.get("functions", []))
    return None

def live_children(p):
    """Count live (non-zombie) ucas processes in the process group, minus leader."""
    try:
        pgid = os.getpgid(p.pid)
        out = subprocess.run(["ps", "-eo", "pid,pgid,stat,cmd"],
                             capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return -1
    n = 0
    for line in out.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, g, stat, cmd = parts
        try:
            if int(g) == pgid and int(pid) != p.pid and "Z" not in stat and "ucas" in cmd:
                n += 1
        except ValueError:
            pass
    return n

def cleanup(p):
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        try: p.kill()
        except Exception: pass
    try: p.wait(timeout=4)
    except Exception: pass

# ---------------------------------------------------------------- stream build
DEFINE = {"name": "zz", "params": [{"name": "x", "type": "u6"}], "body": "x*x*x+47"}
BIGINT = {"expr": "2^200+1"}
ENGLISH = {"text": "factor x^4-1"}

def gates_args(ts):
    a = {"f": "zz", "max": 45, "nodes": 100000000}
    if ts is not ...:
        a["timeout_s"] = ts
    return a

def trigger(mode, variant, rid):
    """Build the 'trigger' request for a timeout variant."""
    if variant == "none":
        return mk(mode, rid, "bigint", dict(BIGINT))         # clean fast control
    ts = {"numeric": 0.02, "string": "0.02", "zero": 0,
          "negative": -1, "huge": 1e9}[variant]
    return mk(mode, rid, "gates", gates_args(ts))            # long search

def build_stream(mode, variant, pattern, rid0):
    """Return list of (label, reqdict) steps with a shared id counter."""
    c = [rid0]
    def nxt():
        c[0] += 1
        return c[0]
    steps = []
    # common prologue: define zz + capture baseline state
    steps.append(("prologue-define", mk(mode, nxt(), "define", dict(DEFINE))))
    steps.append(("baseline-state", mk(mode, nxt(), "state", {})))
    if pattern == "single":
        steps.append(("trigger", trigger(mode, variant, nxt())))
    elif pattern == "n_after":
        steps.append(("trigger", trigger(mode, variant, nxt())))
        for i in range(8):
            steps.append((f"canary-bigint-{i}", mk(mode, nxt(), "bigint", dict(BIGINT))))
    elif pattern == "interleaved":
        for i in range(3):
            steps.append((f"trigger-{i}", trigger(mode, variant, nxt())))
            steps.append((f"english-{i}", mk(mode, nxt(), "english", dict(ENGLISH))))
    elif pattern == "two_timeouts":
        steps.append(("trigger-1", trigger(mode, variant, nxt())))
        steps.append(("trigger-2", trigger(mode, variant, nxt())))
    elif pattern == "crash":
        steps.append(("trigger", trigger(mode, variant, nxt())))
        deep = "(" * 2000 + "x" + ")" * 2000
        steps.append(("crash-deepparse", mk(mode, nxt(), "parse", {"expr": deep})))
        steps.append(("canary-after-crash", mk(mode, nxt(), "bigint", dict(BIGINT))))
    elif pattern == "reset":
        steps.append(("trigger", trigger(mode, variant, nxt())))
        steps.append(("reset", mk(mode, nxt(), "reset", {})))
        steps.append(("canary-after-reset", mk(mode, nxt(), "bigint", dict(BIGINT))))
    # common epilogue: capture final state + show zz
    steps.append(("final-state", mk(mode, nxt(), "state", {})))
    steps.append(("epilogue-show", mk(mode, nxt(), "show", {"f": "zz"})))
    return steps

# ---------------------------------------------------------------- stream runner
def run_stream(mode, variant, pattern, rep):
    steps = build_stream(mode, variant, pattern, 10)
    p = spawn(mode)
    res = {"mode": mode, "variant": variant, "pattern": pattern, "rep": rep}
    baseline = final = None
    matched = []
    codes = []
    req_ids, reply_ids = [], []
    replies_total = 0
    hang_at = None
    try:
        handshake(p, mode)
        for label, req in steps:
            rid = req.get("id")
            req_ids.append(rid)
            try:
                p.stdin.write(json.dumps(req) + "\n")
                p.stdin.flush()
            except Exception:
                hang_at = label + ":brokenpipe"
                for _, r in steps[replies_total + 1:]:
                    req_ids.append(r.get("id"))
                break
            line = readline(p)
            if line is None or line == "":
                # head-of-line blocked / hung / process died: remaining steps unreachable
                hang_at = label
                for _, r in steps[replies_total:]:
                    req_ids.append(r.get("id"))
                break
            replies_total += 1
            r_id, ok, code, status = extract(line)
            reply_ids.append(r_id)
            matched.append((rid == r_id))
            if code: codes.append(code)
            if label == "baseline-state": baseline = state_functions(line)
            if label == "final-state": final = state_functions(line)
        # drain any leftover buffered replies (duplicate / late child output)
        extra = 0
        while True:
            r, _, _ = select.select([p.stdout], [], [], DRAIN_T)
            if not r: break
            line = p.stdout.readline()
            if not line: break
            extra += 1
            _,_,code,_ = extract(line)
            if code: codes.append("extra:" + code)
        replies_total += extra
        res["extra_replies"] = extra
        res["children"] = live_children(p)
    except Exception as e:
        res["error"] = repr(e)
    finally:
        cleanup(p)
    res["n_requests"] = len(req_ids)
    res["n_replies"] = replies_total
    res["one_per_request"] = (replies_total == len(req_ids))
    res["id_mismatches"] = sum(1 for m in matched if not m)
    res["desynced"] = res["id_mismatches"] > 0 or not res["one_per_request"]
    res["codes"] = Counter(codes)
    res["has_timeout_code"] = "timeout" in codes
    res["hang_at"] = hang_at
    # state comparison: expected unchanged unless pattern == reset
    if baseline is not None and final is not None:
        res["state_same"] = (baseline == final)
    else:
        res["state_same"] = None
    return res

# ---------------------------------------------------------------- focused probes
def desync_pairs(mode, pairs=40, ts=0.0005):
    """High-repetition sub-ms-timeout english + canary (reliable desync trigger)."""
    p = spawn(mode); mism = 0; first = None; kids = 0
    try:
        handshake(p, mode)
        for i in range(pairs):
            tid = 2 + 2*i; bid = tid + 1
            tr = mk(mode, tid, "english", {"text":"factor (x+1)^20", "timeout_s":ts})
            p.stdin.write(json.dumps(tr) + "\n"); p.stdin.flush()
            tl = readline(p)
            br = mk(mode, bid, "bigint", dict(BIGINT))
            p.stdin.write(json.dumps(br) + "\n"); p.stdin.flush()
            bl = readline(p)
            tri = extract(tl)[0]; bri = extract(bl)[0]
            if tri != tid or bri != bid:
                mism += 1
                if first is None:
                    first = {"cycle": i, "tid": tid, "trid": tri,
                             "bid": bid, "brid": bri}
        kids = live_children(p)
    finally:
        cleanup(p)
    return {"mode": mode, "pairs": pairs, "mismatches": mism,
            "first": first, "children": kids}

# Ops with a naturally-expensive invocation to test whether numeric + string
# timeout_s is honoured per command family.
FAMILY_SWEEP = {
    "gates":  {"f": "zz", "max": 45, "nodes": 100000000},
    "find":   {"f": "zz", "n": 300, "max": 45},
    "equiv":  {"f": "zz", "g": "zz"},
    "range":  {"f": "zz"},
    "approx": {"f": "zz"},
    "fit":    {"f": "zz", "target": "zz"},
    "prove":  {"name": "bockstein"},
    "parse":  {"expr": "(" * 2000 + "x" + ")" * 2000},
    "english": {"text": "factor (x+1)^20"},
    "bigint": dict(BIGINT),
}

def family_sweep(mode):
    out = []
    for op, base in FAMILY_SWEEP.items():
        for variant, ts in (("numeric", 0.02), ("string", "0.02")):
            args = dict(base)
            args["timeout_s"] = ts
            p = spawn(mode);
            try:
                handshake(p, mode)
                d = mk(mode, 1, "define", dict(DEFINE))
                p.stdin.write(json.dumps(d) + "\n"); p.stdin.flush(); readline(p)
                r = mk(mode, 2, op, args)
                p.stdin.write(json.dumps(r) + "\n"); p.stdin.flush()
                line = readline(p)
                rid, ok, code, status = extract(line)
                out.append({"mode": mode, "op": op, "variant": variant,
                            "status": status, "code": code, "ok": ok,
                            "hung": status == "no-reply"})
            finally:
                cleanup(p)
    return out

# ---------------------------------------------------------------- main
def main():
    outpath = sys.argv[1] if len(sys.argv) > 1 else \
        str(_HERE / "_scratch/results.json")
    streams = []
    t0 = time.time()
    n = 0
    for rep in range(REPS):
        for mode in MODES:
            for variant in VARIANTS:
                for pattern in PATTERNS:
                    r = run_stream(mode, variant, pattern, rep)
                    streams.append(r); n += 1
                    if n % 25 == 0:
                        print(f"... {n} streams, {time.time()-t0:.0f}s", flush=True)
    focused = [desync_pairs(m) for m in MODES]
    sweep = []
    if os.environ.get("SYS_FULL_SWEEP") == "1":
        for m in MODES:
            sweep.extend(family_sweep(m))
    data = {"streams": streams, "focused_desync": focused,
            "family_sweep": sweep, "elapsed_s": time.time() - t0}

    # ---- aggregate report ----
    ds = [s for s in streams if s["desynced"]]
    print(f"\n=== STREAM MATRIX: {len(streams)} streams in {time.time()-t0:.0f}s ===")
    print(f"desynced streams: {len(ds)}/{len(streams)}")
    print(f"id-mismatch total: {sum(s['id_mismatches'] for s in streams)}")
    print(f"not one-per-request: {sum(not s['one_per_request'] for s in streams)}")
    print(f"streams with a hang: {sum(s['hang_at'] is not None for s in streams)}")
    by_variant = defaultdict(lambda: [0, 0])
    for s in streams:
        by_variant[s["variant"]][0] += 1
        by_variant[s["variant"]][1] += s["desynced"]
    print("desync by variant:", {k: f"{v[1]}/{v[0]}" for k, v in by_variant.items()})
    by_mode = defaultdict(lambda: [0, 0])
    for s in streams:
        by_mode[s["mode"]][0] += 1
        by_mode[s["mode"]][1] += s["desynced"]
    print("desync by mode:", {k: f"{v[1]}/{v[0]}" for k, v in by_mode.items()})
    # timeout code correctness: numeric variant should produce code:timeout
    num = [s for s in streams if s["variant"] == "numeric"]
    print(f"numeric streams with code:timeout: "
          f"{sum(s['has_timeout_code'] for s in num)}/{len(num)}")
    # ignored timeouts: string/zero/negative/huge triggers should hang
    for v in ("string", "zero", "negative", "huge"):
        vs = [s for s in streams if s["variant"] == v]
        print(f"variant {v}: hung={sum(s['hang_at'] is not None for s in vs)}/{len(vs)}, "
              f"has_timeout_code={sum(s['has_timeout_code'] for s in vs)}/{len(vs)}")
    # stray children
    ck = Counter(s.get("children") for s in streams)
    print("children distribution:", dict(ck))
    # state checks
    sc = Counter(str(s.get("state_same")) for s in streams)
    print("state_same:", dict(sc))
    print("\n=== FOCUSED DESYNC ===")
    for f in focused:
        print(f"  {f['mode']:5s}: {f['mismatches']}/{f['pairs']} mismatched, "
              f"children={f['children']}, first={f['first']}")
    print("\n=== FAMILY SWEEP (numeric / string timeout_s) ===")
    for s in sweep:
        print(f"  {s['mode']:5s} {s['op']:12s} {s['variant']:7s} -> "
              f"status={s['status']:8s} code={s['code']} ok={s['ok']}")

    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w") as f:
        json.dump(data, f, indent=1, default=str)
    print(f"\nwrote {outpath}")

if __name__ == "__main__":
    main()
