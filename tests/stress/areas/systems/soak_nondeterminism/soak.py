#!/usr/bin/env python3
"""
soak_nondeterminism harness
===========================

Long-running repetition to catch rare nondeterminism, state leaks and drift in
the `ucas` binary.  Three independent phases:

  calibrate : run every golden from sibling tests/stress/*/ once, time it and
              check it still matches its stored .out (read-only on siblings).
  golden    : re-run a broad sample of those goldens 50-200x each under
              `timeout 15`, comparing every run to the stored .out AND to the
              first run of the same case (run-to-run drift).
  live      : keep ONE long-lived `--json` process and ONE long-lived `--mcp`
              process open across thousands of calls; mix definitions, English
              queries, timeouts, ambiguity answers and resets; run fixed
              canary + stateful-script probes to detect answer drift and
              call-order dependence; sample RSS and open FDs for growth.

All artifacts (logs, staging copies, reports) stay under this folder.  Sibling
folders are only ever read from.

Usage:
  python3 soak.py calibrate
  python3 soak.py golden  [--iters 60] [--budget 1200] [--sample-per-area 5] [--maxt 1.0]
  python3 soak.py live    [--calls 4000] [--checkpoint 200]
  python3 soak.py report
  python3 soak.py all     (calibrate + golden + live + report)
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
import argparse, glob, hashlib, json, os, select, shutil, subprocess, sys, time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SIB = os.path.dirname(HERE)                       # tests/stress
BIN = str(_REPO_ROOT / "ucas")
WORK = os.path.join(HERE, "work")
CALIB = os.path.join(WORK, "calibration.json")
GOLDLOG = os.path.join(HERE, "soak_golden.jsonl")
LIVELOG = os.path.join(HERE, "soak_live.jsonl")
FINDJSON = os.path.join(HERE, "soak_findings.json")

TIMEOUT = 15


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def logline(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")


def sha(b):
    if isinstance(b, str):
        b = b.encode("utf-8", "replace")
    return hashlib.sha256(b).hexdigest()[:16]


def first_diff(a, b):
    """Return the first line where byte strings a and b differ (1-based)."""
    al = a.decode("utf-8", "replace").splitlines()
    bl = b.decode("utf-8", "replace").splitlines()
    for i in range(max(len(al), len(bl))):
        x = al[i] if i < len(al) else "<EOF>"
        y = bl[i] if i < len(bl) else "<EOF>"
        if x != y:
            return i + 1, x[:200], y[:200]
    return None, "", ""


def read_flags(path):
    try:
        return open(path).read().split()
    except OSError:
        return []


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #
def discover():
    cases = []
    for area_dir in sorted(glob.glob(os.path.join(SIB, "*"))):
        area = os.path.basename(area_dir)
        if area == "soak_nondeterminism" or not os.path.isdir(area_dir):
            continue
        for f in sorted(glob.glob(os.path.join(area_dir, "*.ucas"))):
            out = f[:-5] + ".out"
            if os.path.isfile(out):
                cases.append(dict(area=area, name=os.path.basename(f)[:-5],
                                  frontend="CLI", ext="ucas",
                                  src=f, out=out, flags=[]))
        for f in sorted(glob.glob(os.path.join(area_dir, "*.jsonl"))):
            out = f[:-6] + ".out"
            if not os.path.isfile(out):
                continue
            n = os.path.basename(f)[:-6]
            frontend = "JSON" if n.startswith("json_") else "MCP"
            cases.append(dict(area=area, name=n, frontend=frontend, ext="jsonl",
                              src=f, out=out,
                              flags=read_flags(os.path.join(area_dir, n + ".flags"))))
    for c in cases:
        c["key"] = c["area"] + "/" + c["name"]
        c["src_bytes"] = open(c["src"], "rb").read()
        c["expected"] = open(c["out"], "rb").read()
    return cases


def cmd_for(case, cwd):
    if case["frontend"] == "CLI":
        return [BIN, case["name"] + ".ucas"], None
    if case["frontend"] == "MCP":
        return [BIN, "--mcp"] + case["flags"], case["src_bytes"]
    return [BIN, "--json", "--files", "none"] + case["flags"], case["src_bytes"]


def stage(case):
    d = os.path.join(WORK, "golden", case["area"], case["name"])
    os.makedirs(d, exist_ok=True)
    fn = case["name"] + "." + case["ext"]
    p = os.path.join(d, fn)
    if not os.path.exists(p):
        shutil.copyfile(case["src"], p)
    # Snapshot the expected .out too, so a sibling agent concurrently editing
    # its golden cannot make our comparison flap. Siblings are only ever read.
    ep = os.path.join(d, case["name"] + ".out")
    if not os.path.exists(ep):
        shutil.copyfile(case["out"], ep)
    return d


def staged_expected(case):
    return open(os.path.join(WORK, "golden", case["area"], case["name"],
                             case["name"] + ".out"), "rb").read()


def run_golden(case):
    d = stage(case)
    cmd, stdin = cmd_for(case, d)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, input=stdin, cwd=d, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=TIMEOUT)
        return r.returncode, r.stdout, time.time() - t0, False
    except subprocess.TimeoutExpired as e:
        return -99, (e.stdout or b""), time.time() - t0, True


# --------------------------------------------------------------------------- #
# phase: calibrate
# --------------------------------------------------------------------------- #
def phase_calibrate(args):
    os.makedirs(WORK, exist_ok=True)
    cases = discover()
    recs = []
    for i, c in enumerate(cases):
        rc, out, dt, to = run_golden(c)
        recs.append(dict(key=c["key"], area=c["area"], name=c["name"],
                         frontend=c["frontend"], rc=rc, timedout=to,
                         secs=round(dt, 3), matches=(out == c["expected"]),
                         out_sha=sha(out), exp_sha=sha(c["expected"])))
        if (i + 1) % 25 == 0:
            print(f"calibrate {i+1}/{len(cases)}", flush=True)
    with open(CALIB, "w") as f:
        json.dump(recs, f, indent=1)
    fast = [r for r in recs if r["matches"] and not r["timedout"] and r["secs"] <= 1.0]
    print(f"calibrated {len(recs)} goldens; {len(fast)} are fast+match "
          f"(<=1.0s) candidates for the repetition sample", flush=True)
    return recs


# --------------------------------------------------------------------------- #
# phase: golden repetition soak
# --------------------------------------------------------------------------- #
def choose_sample(recs, per_area, maxt):
    by_area = defaultdict(list)
    for r in recs:
        if r["matches"] and not r["timedout"] and r["secs"] <= maxt:
            by_area[r["area"]].append(r)
    sample = []
    for area in sorted(by_area):
        rs = sorted(by_area[area], key=lambda r: r["secs"])[:per_area]
        sample.extend(rs)
    return sample


def phase_golden(args):
    if not os.path.exists(CALIB):
        recs = phase_calibrate(args)
    else:
        recs = json.load(open(CALIB))
    cases = {c["key"]: c for c in discover()}
    sample = [r for r in choose_sample(recs, args.sample_per_area, args.maxt)
              if r["key"] in cases]
    # Snapshot expected outputs now (before any repetition) so the comparison
    # is self-consistent even if sibling agents are still writing goldens.
    for sr in sample:
        c = cases[sr["key"]]
        stage(c)
        try:
            shutil.copyfile(c["out"], os.path.join(WORK, "golden", c["area"],
                                                    c["name"], c["name"] + ".out"))
        except OSError:
            pass
    print(f"golden soak: {len(sample)} cases x {args.iters} iters "
          f"= {len(sample)*args.iters} executions "
          f"({dict(Counter(r['area'] for r in sample))})", flush=True)
    t_start = time.time()
    exec_count = 0
    for si, sr in enumerate(sample):
        c = cases[sr["key"]]
        expected = staged_expected(c)
        ref = None
        baseline_bad = 0
        drift = 0
        for it in range(args.iters):
            if time.time() - t_start > args.budget:
                print(f"golden budget ({args.budget}s) reached", flush=True)
                break
            rc, out, dt, to = run_golden(c)
            exec_count += 1
            if ref is None:
                ref = out
            line, x, y = first_diff(ref, out)
            mism_exp = (out != expected)
            rec = dict(case=sr["key"], iter=it, rc=rc, timedout=to,
                       secs=round(dt, 3), drift=bool(line),
                       exp_mismatch=mism_exp, out_sha=sha(out),
                       ref_sha=sha(ref), exp_sha=sha(expected))
            if line:
                rec["first_diff_line"] = line
                rec["ref_line"] = x
                rec["got_line"] = y
                drift += 1
                logline(FINDJSON, dict(kind="GOLDEN_DRIFT", **rec))
            if mism_exp:
                baseline_bad += 1
                if baseline_bad == 1:
                    dl, rx, gy = first_diff(expected, out)
                    logline(FINDJSON, dict(kind="GOLDEN_EXP_MISMATCH",
                                           first_diff_line=dl,
                                           expected_line=rx, got_line=gy, **rec))
            if to or rc not in (0,):
                logline(FINDJSON, dict(kind="GOLDEN_CRASH_OR_TIMEOUT", **rec))
            logline(GOLDLOG, rec)
        if drift or baseline_bad:
            print(f"  ISSUE {sr['key']}: drift={drift} exp_mismatch={baseline_bad}",
                  flush=True)
        if (si + 1) % 10 == 0:
            print(f"golden {si+1}/{len(sample)} cases, {exec_count} execs, "
                  f"{time.time()-t_start:.0f}s", flush=True)
    print(f"golden soak done: {exec_count} executions in {time.time()-t_start:.0f}s",
          flush=True)


# --------------------------------------------------------------------------- #
# long-lived process wrappers
# --------------------------------------------------------------------------- #
def proc_stats(pid):
    rss_kb = -1
    try:
        for line in open(f"/proc/{pid}/statm"):
            rss_kb = int(line.split()[1]) * (os.sysconf("SC_PAGE_SIZE") // 1024)
            break
    except OSError:
        pass
    fd = -1
    try:
        fd = len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        pass
    return rss_kb, fd


def readline_timeout(p, timeout):
    r, _, _ = select.select([p.stdout], [], [], timeout)
    if not r:
        return None
    line = p.stdout.readline()
    if line == "":
        return ""  # EOF
    return line


class JSONProc:
    def __init__(self, read_timeout=20):
        self.read_timeout = read_timeout
        self.id = 0
        self.p = subprocess.Popen([BIN, "--json", "--files", "none"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1)
        self.dead = False

    def request(self, cmd, args):
        self.id += 1
        req = {"id": self.id, "cmd": cmd, "args": args}
        try:
            self.p.stdin.write(json.dumps(req) + "\n")
            self.p.stdin.flush()
        except (BrokenPipeError, OSError):
            self.dead = True
            return None, "write-failed"
        line = readline_timeout(self.p, self.read_timeout)
        if line is None:
            return None, "hang"
        if line == "":
            self.dead = True
            return None, "eof"
        try:
            return json.loads(line), None
        except Exception as e:
            return {"_raw": line}, "badjson:" + str(e)

    def stats(self):
        return proc_stats(self.p.pid)

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()
            self.p.wait()


class MCPProc:
    def __init__(self, read_timeout=20):
        self.read_timeout = read_timeout
        self.id = 0
        self.p = subprocess.Popen([BIN, "--mcp"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, bufsize=1)
        self.dead = False
        self._send({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18",
                               "capabilities": {},
                               "clientInfo": {"name": "soak", "version": "1"}}})
        readline_timeout(self.p, self.read_timeout)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, o):
        self.p.stdin.write(json.dumps(o) + "\n")
        self.p.stdin.flush()

    def call(self, name, arguments):
        self.id += 1
        req = {"jsonrpc": "2.0", "id": self.id, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
        try:
            self._send(req)
        except (BrokenPipeError, OSError):
            self.dead = True
            return None, "write-failed"
        line = readline_timeout(self.p, self.read_timeout)
        if line is None:
            return None, "hang"
        if line == "":
            self.dead = True
            return None, "eof"
        try:
            return json.loads(line), None
        except Exception as e:
            return {"_raw": line}, "badjson:" + str(e)

    def stats(self):
        return proc_stats(self.p.pid)

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()
            self.p.wait()


# --------------------------------------------------------------------------- #
# response normalisation (drop ids; the only intentionally-varying field)
# --------------------------------------------------------------------------- #
def norm_json(resp):
    if resp is None:
        return None
    r = dict(resp)
    r.pop("id", None)
    return json.dumps(r, sort_keys=True, default=str)


def norm_mcp(resp):
    if resp is None:
        return None
    r = dict(resp)
    r.pop("id", None)
    # structuredContent carries the per-request id inside; strip it too
    sc = r.get("result", {}).get("structuredContent") if isinstance(r.get("result"), dict) else None
    if isinstance(sc, dict):
        sc = dict(sc)
        sc.pop("id", None)
        rr = dict(r)
        rr["result"] = dict(r["result"])
        rr["result"]["structuredContent"] = sc
        r = rr
    return json.dumps(r, sort_keys=True, default=str)


def ok_of_json(resp):
    if not isinstance(resp, dict):
        return None
    return resp.get("ok")


def ok_of_mcp(resp):
    if not isinstance(resp, dict):
        return None
    sc = resp.get("result", {}).get("structuredContent") if isinstance(resp.get("result"), dict) else None
    if isinstance(sc, dict):
        return sc.get("ok")
    return resp.get("result", {}).get("isError")


# --------------------------------------------------------------------------- #
# request pools for the live phase
# --------------------------------------------------------------------------- #
def json_pool():
    """(tag, kind, cmd, args, canary)"""
    return [
        ("j_bigint",      "pure",     "bigint",  {"expr": "2^200 + 1"}, True),
        ("j_factor",      "pure",     "factor",  {"f": "x^4 - 1"}, True),
        ("j_expand",      "pure",     "expand",  {"f": "(x+1)^5"}, True),
        ("j_range_inline","pure",     "range",   {"f": {"body": "x xor 255",
                                                        "params": [{"name": "x", "type": "u8"}]}}, True),
        ("j_equiv_inline","pure",     "equiv",   {"f": {"body": "x + x",
                                                        "params": [{"name": "x", "type": "u8"}]},
                                                  "g": {"body": "x << 1",
                                                        "params": [{"name": "x", "type": "u8"}]}}, True),
        ("j_en_pure",     "english",  "english", {"text": "what is 2 plus 3?"}, True),
        ("j_en_factor",   "english",  "english", {"text": "factor x squared minus one"}, False),
        ("j_en_range",    "english",  "english", {"text": "what is the range of x squared for a byte x?"}, False),
        ("j_en_diff",     "english",  "english", {"text": "differentiate x^3 + 2x"}, False),
        ("j_amb_even1",   "ambiguity","english", {"text": "is x squared even?", "assume": {"question": 1}}, False),
        ("j_amb_even2",   "ambiguity","english", {"text": "is x squared even?", "assume": {"question": 2}}, False),
        ("j_amb_log2",    "ambiguity","english", {"text": "the log of x", "assume": {"log": 2}}, False),
        ("j_amb_log3",    "ambiguity","english", {"text": "the log of x", "assume": {"log": 3}}, False),
        ("j_amb_byte2",   "ambiguity","english", {"text": "b is a byte", "assume": {"byte": 2}}, False),
        ("j_amb_sqrt2",   "ambiguity","english", {"text": "range of the square root of a 4-bit unsigned x",
                                                  "assume": {"sqrt": 2}}, False),
        ("j_en_amb_raw",  "ambiguity","english", {"text": "the log of x"}, False),
        ("j_def_f",       "define",   "define",  {"name": "f", "params": [{"name": "x", "type": "u8"}],
                                                  "body": "x + 1"}, False),
        ("j_def_g",       "define",   "define",  {"name": "g",
                                                  "params": [{"name": "x", "type": "u8"},
                                                             {"name": "y", "type": "u8"}],
                                                  "body": "(x & y) + (x xor y)"}, False),
        ("j_def_h",       "define",   "define",  {"name": "h", "params": [{"name": "x", "type": "real"}],
                                                  "body": "x^3 - 3x"}, False),
        ("j_def_hu32",    "define",   "define",  {"name": "hu",
                                                  "params": [{"name": "x", "type": "u32"},
                                                             {"name": "y", "type": "u32"}],
                                                  "body": "(x*y)^5"}, False),
        ("j_use_f",       "english",  "english", {"text": "what is f of 3?"}, False),
        ("j_state",       "state",    "state",   {}, False),
        ("j_funcs",       "state",    "funcs",   {}, False),
        ("j_assume_set",  "state",    "assume",  {"set": {"log": "base 10"}}, False),
        ("j_assume_clear","state",    "assume",  {"clear": True}, False),
        ("j_reset",       "reset",    "reset",   {}, False),
        ("j_timeout_big", "timeout",  "bigint",  {"expr": "2^200000 + 1", "timeout_s": 0.001}, False),
        ("j_timeout_equiv","timeout", "equiv",   {"f": "hu", "g": "hu", "timeout_s": 0.001}, False),
        ("j_timeout_en",  "timeout",  "english", {"text": "factor (x+1)^20", "timeout_s": 0.001}, False),
    ]


def mcp_pool():
    """(tag, kind, tool, arguments, canary)"""
    return [
        ("m_bigint",   "pure",     "ucas",   {"source": "bigint 2^200 + 1"}, True),
        ("m_factor",   "pure",     "algebra",{"op": "factor", "args": {"f": "x^4 - 1"}}, True),
        ("m_diff",     "pure",     "calculus",{"op": "diff", "args": {"f": "x^3 + 2x", "x": "x"}}, True),
        ("m_en_pure",  "english",  "english",{"text": "what is 2 plus 3?"}, True),
        ("m_en_factor","english",  "english",{"text": "factor x squared minus one"}, False),
        ("m_en_range", "english",  "english",{"text": "what is the range of x squared for a byte x?"}, False),
        ("m_en_diff",  "english",  "english",{"text": "differentiate x^3 + 2x"}, False),
        ("m_amb_even1","ambiguity","english",{"text": "is x squared even?", "assume": {"question": 1}}, False),
        ("m_amb_even2","ambiguity","english",{"text": "is x squared even?", "assume": {"question": 2}}, False),
        ("m_amb_log2", "ambiguity","english",{"text": "the log of x", "assume": {"log": 2}}, False),
        ("m_amb_log3", "ambiguity","english",{"text": "the log of x", "assume": {"log": 3}}, False),
        ("m_amb_byte2","ambiguity","english",{"text": "b is a byte", "assume": {"byte": 2}}, False),
        ("m_amb_sqrt2","ambiguity","english",{"text": "range of the square root of a 4-bit unsigned x",
                                              "assume": {"sqrt": 2}}, False),
        ("m_en_amb_raw","ambiguity","english",{"text": "the log of x"}, False),
        ("m_def_f",    "define",   "session",{"op": "define", "args": {"name": "f",
                        "params": [{"name": "x", "type": "u8"}], "body": "x + 1"}}, False),
        ("m_def_g",    "define",   "session",{"op": "define", "args": {"name": "g",
                        "params": [{"name": "x", "type": "u8"}, {"name": "y", "type": "u8"}],
                        "body": "(x & y) + (x xor y)"}}, False),
        ("m_def_h",    "define",   "session",{"op": "define", "args": {"name": "h",
                        "params": [{"name": "x", "type": "real"}], "body": "x^3 - 3x"}}, False),
        ("m_use_f",    "english",  "english",{"text": "what is f of 3?"}, False),
        ("m_state",    "state",    "session",{"op": "state"}, False),
        ("m_funcs",    "funcs",    "session",{"op": "funcs"}, False),
        ("m_assume_set","state",   "session",{"op": "assume", "args": {"set": {"log": "base 10"}}}, False),
        ("m_assume_clear","state", "session",{"op": "assume", "args": {"clear": True}}, False),
        ("m_reset",    "reset",    "session",{"op": "reset"}, False),
        ("m_timeout_big","timeout","ucas",  {"source": "bigint 2^200000 + 1", "timeout_s": 0.001}, False),
    ]


# --------------------------------------------------------------------------- #
# stateful script (order-dependence / drift detector)
# --------------------------------------------------------------------------- #
STATEFUL_JSON = [
    ("reset",   "reset", {}),
    ("define_f","define",{"name": "f", "params": [{"name": "x", "type": "u8"}], "body": "x + 1"}),
    ("define_g","define",{"name": "g", "params": [{"name": "x", "type": "u8"}], "body": "x xor 255"}),
    ("equiv",   "equiv", {"f": "f", "g": "f"}),
    ("english", "english",{"text": "what is f of 3?"}),
    ("assume",  "assume",{"set": {"log": "base 2"}}),
    ("english2","english",{"text": "what is the log of 8?"}),
    ("state",   "state", {}),
    ("reset2",  "reset", {}),
    ("state2",  "state", {}),
]

STATEFUL_MCP = [
    ("reset",   "session", {"op": "reset"}),
    ("define_f","session", {"op": "define", "args": {"name": "f",
                "params": [{"name": "x", "type": "u8"}], "body": "x + 1"}}),
    ("define_g","session", {"op": "define", "args": {"name": "g",
                "params": [{"name": "x", "type": "u8"}], "body": "x xor 255"}}),
    ("equiv",   "ucas",    {"source": "equiv f f"}),
    ("english", "english", {"text": "what is f of 3?"}),
    ("assume",  "session", {"op": "assume", "args": {"set": {"log": "base 2"}}}),
    ("english2","english", {"text": "what is the log of 8?"}),
    ("state",   "session", {"op": "state"}),
    ("reset2",  "session", {"op": "reset"}),
    ("state2",  "session", {"op": "state"}),
]


def run_stateful(proc, iface, script):
    out = []
    for tag, cmd, args in script:
        if iface == "json":
            resp, err = proc.request(cmd, args)
            norm = norm_json(resp)
            ok = ok_of_json(resp)
        else:
            resp, err = proc.call(cmd, args)
            norm = norm_mcp(resp)
            ok = ok_of_mcp(resp)
        out.append((tag, norm, ok, err))
    return out


# --------------------------------------------------------------------------- #
# phase: live
# --------------------------------------------------------------------------- #
def phase_live(args):
    os.makedirs(WORK, exist_ok=True)
    jp = JSONProc()
    mp = MCPProc()
    jpool = json_pool()
    mpool = mcp_pool()
    # deterministic rotation: cover all templates evenly, with base canaries first
    jseq = [p for p in jpool] + [p for p in jpool if p[4]]  # canaries twice as often
    mseq = [p for p in mpool] + [p for p in mpool if p[4]]

    # baseline canary signatures
    jcanon0 = {}
    for tag, kind, cmd, a, can in jpool:
        if can:
            resp, err = jp.request(cmd, a)
            jcanon0[tag] = (norm_json(resp), ok_of_json(resp))
    mcanon0 = {}
    for tag, kind, tool, a, can in mpool:
        if can:
            resp, err = mp.call(tool, a)
            mcanon0[tag] = (norm_mcp(resp), ok_of_mcp(resp))
    st0 = dict(j=run_stateful(jp, "json", STATEFUL_JSON),
               m=run_stateful(mp, "mcp", STATEFUL_MCP))

    rss0 = dict(json=jp.stats(), mcp=mp.stats())
    print("live baseline rss/fd:", rss0, flush=True)

    ok_counter = defaultdict(Counter)   # tag -> Counter(ok values)
    ji = mi = 0
    checkpoints = []
    t0 = time.time()
    n = 0
    for n in range(1, args.calls + 1):
        # interleave the two processes
        tag, kind, cmd, a, can = jseq[ji % len(jseq)]; ji += 1
        resp, err = jp.request(cmd, a)
        ok_counter[("json", tag)][ok_of_json(resp)] += 1
        logline(LIVELOG, dict(i=n, iface="json", tag=tag, kind=kind, ok=ok_of_json(resp),
                              err=err, rss=jp.stats()[0], fd=jp.stats()[1]))
        if err in ("eof", "hang", "write-failed") or jp.dead:
            logline(FINDJSON, dict(kind="LIVE_PROC_DIED", iface="json", i=n, tag=tag, err=err))
            break

        tag, kind, tool, a, can = mseq[mi % len(mseq)]; mi += 1
        resp, err = mp.call(tool, a)
        ok_counter[("mcp", tag)][ok_of_mcp(resp)] += 1
        logline(LIVELOG, dict(i=n, iface="mcp", tag=tag, kind=kind, ok=ok_of_mcp(resp),
                              err=err, rss=mp.stats()[0], fd=mp.stats()[1]))
        if err in ("eof", "hang", "write-failed") or mp.dead:
            logline(FINDJSON, dict(kind="LIVE_PROC_DIED", iface="mcp", i=n, tag=tag, err=err))
            break

        if n % args.checkpoint == 0:
            # canary drift check
            jnow = {}
            for tag, kind, cmd, a, can in jpool:
                if can:
                    resp, err = jp.request(cmd, a)
                    jnow[tag] = (norm_json(resp), ok_of_json(resp))
            mnow = {}
            for tag, kind, tool, a, can in mpool:
                if can:
                    resp, err = mp.call(tool, a)
                    mnow[tag] = (norm_mcp(resp), ok_of_mcp(resp))
            for tag in jcanon0:
                if jnow[tag] != jcanon0[tag]:
                    logline(FINDJSON, dict(kind="LIVE_CANARY_DRIFT", iface="json", i=n,
                                           tag=tag, baseline=jcanon0[tag], now=jnow[tag]))
            for tag in mcanon0:
                if mnow[tag] != mcanon0[tag]:
                    logline(FINDJSON, dict(kind="LIVE_CANARY_DRIFT", iface="mcp", i=n,
                                           tag=tag, baseline=mcanon0[tag], now=mnow[tag]))
            # stateful script drift / order check
            stj = run_stateful(jp, "json", STATEFUL_JSON)
            stm = run_stateful(mp, "mcp", STATEFUL_MCP)
            for iface, cur, base in (("json", stj, st0["j"]), ("mcp", stm, st0["m"])):
                for (tag, norm, ok, err), (btag, bnorm, bok, berr) in zip(cur, base):
                    if norm != bnorm or ok != bok:
                        logline(FINDJSON, dict(kind="LIVE_STATEFUL_DRIFT", iface=iface, i=n,
                                               step=tag, base_ok=bok, now_ok=ok,
                                               base=bnorm, now=norm))
            jrss, jfd = jp.stats()
            mrss, mfd = mp.stats()
            cp = dict(i=n, secs=round(time.time() - t0, 1),
                      json_rss=jrss, json_fd=jfd, mcp_rss=mrss, mcp_fd=mfd)
            checkpoints.append(cp)
            logline(FINDJSON, dict(kind="LIVE_CHECKPOINT", **cp))
            print(f"live {n}/{args.calls}  json rss/fd={jrss}/{jfd}  "
                  f"mcp rss/fd={mrss}/{mfd}  {cp['secs']}s", flush=True)
        if (n % 500) == 0:
            print(f"  {n} calls done ({time.time()-t0:.0f}s)", flush=True)

    # ok-flapping: any tag whose observed ok set has >1 distinct value
    for (iface, tag), ctr in ok_counter.items():
        if len(ctr) > 1:
            logline(FINDJSON, dict(kind="LIVE_OK_FLAPPING", iface=iface, tag=tag,
                                   counts=dict(ctr)))

    # resource growth summary
    def growth(prefix):
        vals = [c[prefix] for c in checkpoints if c[prefix] >= 0]
        return dict(first=vals[0] if vals else None, last=vals[-1] if vals else None,
                    max=max(vals) if vals else None, npts=len(vals))
    summary = dict(json_rss=growth("json_rss"), json_fd=growth("json_fd"),
                   mcp_rss=growth("mcp_rss"), mcp_fd=growth("mcp_fd"))
    logline(FINDJSON, dict(kind="LIVE_RESOURCE_SUMMARY", **summary))
    jp.close(); mp.close()
    total = n * 2
    print(f"live done: {n} loop iterations (~{total} calls) in {time.time()-t0:.0f}s",
          flush=True)
    print("resource summary:", json.dumps(summary), flush=True)
    return summary


# --------------------------------------------------------------------------- #
# phase: report
# --------------------------------------------------------------------------- #
def phase_report(args):
    findings = [json.loads(l) for l in open(FINDJSON)] if os.path.exists(FINDJSON) else []
    by = Counter(f["kind"] for f in findings)
    print("findings by kind:", dict(by))
    distinct = defaultdict(set)
    for f in findings:
        k = f["kind"]
        if k == "GOLDEN_DRIFT" or k == "GOLDEN_EXP_MISMATCH" or k == "GOLDEN_CRASH_OR_TIMEOUT":
            distinct[k].add(f.get("case"))
        elif k.startswith("LIVE_"):
            distinct[k].add((f.get("iface"), f.get("tag", f.get("step", ""))))
    print("affected distinct cases/tags:")
    for k, v in distinct.items():
        print(f"  {k}: {len(v)}")
    return findings


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="phase", required=True)

    sub.add_parser("calibrate")

    g = sub.add_parser("golden")
    g.add_argument("--iters", type=int, default=60)
    g.add_argument("--budget", type=float, default=1200)
    g.add_argument("--sample-per-area", type=int, default=5)
    g.add_argument("--maxt", type=float, default=1.0)

    l = sub.add_parser("live")
    l.add_argument("--calls", type=int, default=4000)
    l.add_argument("--checkpoint", type=int, default=200)

    sub.add_parser("report")

    a = sub.add_parser("all")
    a.add_argument("--iters", type=int, default=60)
    a.add_argument("--budget", type=float, default=1200)
    a.add_argument("--sample-per-area", type=int, default=5)
    a.add_argument("--maxt", type=float, default=1.0)
    a.add_argument("--calls", type=int, default=4000)
    a.add_argument("--checkpoint", type=int, default=200)

    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.phase == "calibrate":
        phase_calibrate(args)
    elif args.phase == "golden":
        phase_golden(args)
    elif args.phase == "live":
        phase_live(args)
    elif args.phase == "report":
        phase_report(args)
    elif args.phase == "all":
        phase_calibrate(args)
        phase_golden(args)
        phase_live(args)
        phase_report(args)


if __name__ == "__main__":
    main()
