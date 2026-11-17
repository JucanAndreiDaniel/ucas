#!/usr/bin/env python3
"""
Correctness harness for interleaving / state isolation across multiple clients
of one long-lived `ucas --mcp` process (and concurrent `--json` CLI runs).

This is a CORRECTNESS study, not a load test: 2-4 threads, a few dozen
requests, every server operation bounded by a wall-clock timeout, no loops.

Usage:
    python3 harness.py <experiment>

Experiments:
    id_echo            two clients alternate tools/call; check id echo + no crossed answers
    large_interleave   two clients push >PIPE_BUF lines concurrently; look for bad_json/crash
    state_share        define/assume in one client, observe in the other, reset, observe again
    reset_inflight     client A long request, client B resets mid-flight
    longshort          client A long timeout_s request, client B short requests (latency)
    twoproc_flat       two servers at once (grouped + flat); isolation between processes
    reconnect          rapid connect/disconnect cycles
    concurrent_dir     concurrent CLI --json runs sharing --dir
    all                run every experiment in sequence
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

import json
import os
import subprocess
import sys
import threading
import time

BIN = str(_REPO_ROOT / "ucas")
HERE = os.path.dirname(os.path.abspath(__file__))

INIT = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "stress-concurrent", "version": "1"},
    },
}
NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def call(rid, name, arguments):
    return {
        "jsonrpc": "2.0",
        "id": rid,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def expand_req(rid, marker, pad=0):
    """An algebra/expand call whose reply text is guaranteed to contain marker
    and 2*marker. `pad` inflates the JSON line past PIPE_BUF when requested."""
    args = {"op": "expand", "args": {"f": f"(x + {marker})^2"}}
    if pad:
        args["pad"] = "Z" * pad
    return call(rid, "algebra", args)


def resp_text(obj):
    try:
        return obj["result"]["content"][0].get("text", "")
    except Exception:
        return ""


def resp_sc(obj):
    try:
        return obj["result"]["structuredContent"]
    except Exception:
        return None


class Server:
    """A long-lived `ucas --mcp` process with a single demultiplexing reader.

    The reader models a well-behaved transport layer: it consumes every reply
    line and routes it to whoever is waiting for that id. A multi-client
    harness MUST demultiplex by id because the process emits replies in request
    arrival order, not per-connection order.
    """

    def __init__(self, flat=False, cwd=None, capture_stderr=True):
        cmd = [BIN, "--mcp"] + (["--flat"] if flat else [])
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        self._write_lock = threading.Lock()
        self._cv = threading.Condition()
        self.responses = {}
        self.eof = False
        self.stderr = ""
        self._t = threading.Thread(target=self._reader, daemon=True)
        self._t.start()
        if capture_stderr:
            self._te = threading.Thread(target=self._err_reader, daemon=True)
            self._te.start()

    def _reader(self):
        try:
            for line in self.proc.stdout:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    with self._cv:
                        self.responses.setdefault("__badjson__", []).append(line[:500])
                        self._cv.notify_all()
                    continue
                rid = obj.get("id")
                with self._cv:
                    self.responses.setdefault(rid, []).append(obj)
                    self._cv.notify_all()
        except Exception:
            pass
        finally:
            with self._cv:
                self.eof = True
                self._cv.notify_all()

    def _err_reader(self):
        try:
            self.stderr = self.proc.stderr.read()
        except Exception:
            pass

    def send_raw(self, text):
        """Write exactly one JSON line. Caller supplies the newline."""
        self.proc.stdin.write(text)
        self.proc.stdin.flush()

    def send(self, obj):
        line = json.dumps(obj) + "\n"
        with self._write_lock:
            self.send_raw(line)

    def send_unlocked(self, obj):
        """No lock: used to model two independent fds writing the same pipe."""
        self.send_raw(json.dumps(obj) + "\n")

    def initialize(self):
        self.send(INIT)
        self.send(NOTIF)
        return self.wait(0, timeout=5)

    def wait(self, rid, timeout=8):
        deadline = time.time() + timeout
        with self._cv:
            while True:
                if rid in self.responses:
                    return self.responses[rid].pop(0)
                if self.eof:
                    return None
                rem = deadline - time.time()
                if rem <= 0:
                    return None
                self._cv.wait(rem)

    def request(self, obj, timeout=8):
        self.send(obj)
        return self.wait(obj.get("id"), timeout)

    def alive(self):
        return self.proc.poll() is None

    def close(self, hard=False):
        if hard:
            try:
                self.proc.kill()
            except Exception:
                pass
        else:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:
                pass

    def rc(self):
        return self.proc.poll()


def banner(name):
    print(f"\n{'='*70}\nEXP: {name}\n{'='*70}")
    sys.stdout.flush()


# --------------------------------------------------------------------------
# 1. id echo / crossed answers under strict A,B,A,B interleaving
# --------------------------------------------------------------------------
def exp_id_echo(n=12):
    banner("id_echo (two clients, strict interleaving, %d reqs each)" % n)
    s = Server()
    s.initialize()
    got = {}
    errors = []
    turn_a = threading.Event()
    turn_b = threading.Event()
    turn_a.set()

    def client(marker_base, id_base, my_turn, next_turn):
        for i in range(n):
            if not my_turn.wait(8):
                errors.append("turn timeout")
                return
            my_turn.clear()
            marker = marker_base + i
            rid = id_base + i
            got[rid] = marker
            s.send(expand_req(rid, marker))
            next_turn.set()

    ta = threading.Thread(target=client, args=(700001, 1000, turn_a, turn_b))
    tb = threading.Thread(target=client, args=(800001, 2000, turn_b, turn_a))
    ta.start(); tb.start()
    ta.join(10); tb.join(10)

    crossed = 0
    missing = 0
    bad_id = 0
    for rid, marker in sorted(got.items()):
        r = s.wait(rid, timeout=5)
        if r is None:
            missing += 1
            continue
        sc = resp_sc(r)
        if sc is not None and sc.get("id") != rid:
            bad_id += 1
            errors.append(f"structuredContent.id={sc.get('id')} for request id={rid}")
        txt = resp_text(r)
        if str(marker) not in txt or str(2 * marker) not in txt:
            # does it carry someone ELSE's marker?
            others = [m for m in got.values() if str(m) in txt]
            crossed += 1
            errors.append(f"id {rid}: expected marker {marker}, text={txt[:120]!r} others={others[:5]}")
    print(f"requests={2*n} missing={missing} crossed={crossed} bad_id={bad_id}")
    print(f"eof={s.eof} rc={s.rc()} badjson_lines={len(s.responses.get('__badjson__', []))}")
    if errors:
        print("ERRORS:")
        for e in errors[:20]:
            print("  -", e)
    s.close()
    return dict(missing=missing, crossed=crossed, bad_id=bad_id, errors=errors)


# --------------------------------------------------------------------------
# 2. large concurrent writes (models two fds on one pipe, no client lock)
# --------------------------------------------------------------------------
def exp_large_interleave(n=6, pad=120000):
    banner("large_interleave (2 clients, %d reqs each, pad=%d bytes)" % (n, pad))
    s = Server()
    s.initialize()
    got = {}

    def client(marker_base, id_base):
        for i in range(n):
            marker = marker_base + i
            rid = id_base + i
            got[rid] = marker
            try:
                s.send_unlocked(expand_req(rid, marker, pad=pad))
            except Exception as e:
                print("send error", e)

    ta = threading.Thread(target=client, args=(910001, 3000))
    tb = threading.Thread(target=client, args=(920001, 4000))
    ta.start(); tb.start()
    ta.join(12); tb.join(12)

    time.sleep(0.5)
    crossed = 0; missing = 0
    for rid, marker in sorted(got.items()):
        r = s.wait(rid, timeout=4)
        if r is None:
            missing += 1
            continue
        txt = resp_text(r)
        if str(marker) not in txt:
            crossed += 1
            print(f"  id {rid}: expected {marker}, got {txt[:160]!r}")
    bad = s.responses.get("__badjson__", [])
    print(f"requests={2*n} missing={missing} wrong_marker={crossed} badjson_lines={len(bad)}")
    print(f"eof={s.eof} rc={s.rc()}")
    if bad:
        print("  badjson sample:", repr(bad[0][:200]))
    if s.stderr:
        print("  stderr sample:", repr(s.stderr[:300]))
    s.close(hard=s.alive())
    return dict(missing=missing, crossed=crossed, badjson=len(bad), rc=s.rc())


# --------------------------------------------------------------------------
# 3. state sharing across clients of one process
# --------------------------------------------------------------------------
def exp_state_share():
    banner("state_share (definitions + assume are process-global)")
    s = Server()
    s.initialize()
    # client A defines a function
    s.request(call(1, "session", {"op": "define", "args": {
        "name": "shared_a", "params": [{"name": "x", "type": "u8"}], "body": "x+1"}}))
    # client B observes it
    b1 = s.request(call(2, "analyze", {"op": "show", "args": {"f": "shared_a"}}))
    print("B sees A's function:", repr(resp_text(b1)[:80]))
    # client A sets a session-wide assumption (caret = power)
    s.request(call(3, "session", {"op": "assume", "args": {"set": {"caret": "power"}}}))
    # client B sends an expression that needs that assumption
    b2 = s.request(call(4, "ucas", {"source": "probe = 3 ^ 5 & 1"}))
    b2txt = resp_text(b2)
    sc = resp_sc(b2)
    notes = (sc or {}).get("notes", [])
    print("B ambiguous after A's assume:", (sc or {}).get("ok"), repr(b2txt[:100]), "notes:", notes[:1])
    # client A resets
    s.request(call(5, "session", {"op": "reset", "args": {}}))
    # client B observes function again
    b3 = s.request(call(6, "analyze", {"op": "show", "args": {"f": "shared_a"}}))
    print("B after A's reset:", repr(resp_text(b3)[:80]))
    # client B sends caret expression again after reset
    b4 = s.request(call(7, "ucas", {"source": "probe2 = 3 ^ 5 & 1"}))
    print("B caret expr after reset:", (resp_sc(b4) or {}).get("ok"), repr(resp_text(b4)[:100]))
    print(f"eof={s.eof} rc={s.rc()}")
    s.close()


# --------------------------------------------------------------------------
# 4. reset while a long request is in flight
# --------------------------------------------------------------------------
def exp_reset_inflight():
    banner("reset_inflight (A long stoke, B session.reset mid-flight)")
    s = Server()
    s.initialize()
    s.request(call(1, "session", {"op": "define", "args": {
        "name": "slowfn", "params": [{"name": "x", "type": "u8"}], "body": "x*x+3*x"}}))

    # Prepare B's reset request but do not send until A is in flight.
    t0 = time.time()
    s.send(call(2, "analyze", {"op": "stoke", "args": {
        "f": "slowfn", "steps": 8000000, "timeout_s": 4}}))
    time.sleep(0.3)
    b_sent = time.time()
    s.send(call(3, "session", {"op": "reset", "args": {}}))
    r2 = s.wait(2, timeout=8)
    r3 = s.wait(3, timeout=8)
    t1 = time.time()
    print(f"A reply after {t1-t0:.2f}s: err={(resp_sc(r2) or {}).get('ok') if r2 else None} "
          f"text={repr(resp_text(r2)[:120]) if r2 else 'None'}")
    print(f"B reset reply after {t1-b_sent:.2f}s: {repr(resp_text(r3)[:80]) if r3 else 'None'}")
    print(f"eof={s.eof} rc={s.rc()} stderr={repr(s.stderr[:200])}")
    alive = s.alive()
    if alive:
        post = s.request(call(4, "algebra", {"op": "expand", "args": {"f": "(x+1)^2"}}), timeout=4)
        print("post-reset health:", repr(resp_text(post)[:60]))
    s.close(hard=s.alive())


# --------------------------------------------------------------------------
# 5. long request from A, short requests from B (serialization check)
# --------------------------------------------------------------------------
def exp_longshort():
    banner("longshort (A timeout_s=3 stoke; B sends short calls during it)")
    s = Server()
    s.initialize()
    s.request(call(1, "session", {"op": "define", "args": {
        "name": "slowfn", "params": [{"name": "x", "type": "u8"}], "body": "x*x+3*x"}}))
    latencies = []

    def client_b():
        for i in range(3):
            rid = 5000 + i
            t = time.time()
            s.send(expand_req(rid, 950001 + i))
            r = s.wait(rid, timeout=10)
            latencies.append(time.time() - t)

    t0 = time.time()
    s.send(call(2, "analyze", {"op": "stoke", "args": {
        "f": "slowfn", "steps": 8000000, "timeout_s": 3}}))
    time.sleep(0.2)
    tb = threading.Thread(target=client_b)
    tb.start(); tb.join(12)
    r2 = s.wait(2, timeout=8)
    print(f"A long reply after {time.time()-t0:.2f}s: {repr(resp_text(r2)[:100]) if r2 else 'None'}")
    print("B latencies:", [f"{x:.2f}s" for x in latencies])
    print(f"eof={s.eof} rc={s.rc()}")
    s.close(hard=s.alive())


# --------------------------------------------------------------------------
# 6. two server processes at once, grouped + flat, isolation
# --------------------------------------------------------------------------
def exp_twoproc_flat():
    banner("twoproc_flat (two processes: grouped + flat, concurrent)")
    sg = Server(flat=False)
    sf = Server(flat=True)
    sg.initialize(); sf.initialize()

    def name(rid, name_, args):
        return call(rid, name_, args)

    # grouped: session define + show ; flat: define + show with tool name = op
    results = {}

    def worker(s, tag, define_args, show_args, define_name, show_name):
        s.request(name(100 + len(tag), define_name, define_args))
        r = s.request(name(200 + len(tag), show_name, show_args))
        results[tag] = resp_text(r)

    tg = threading.Thread(target=worker, args=(
        sg, "grouped",
        {"op": "define", "args": {"name": "only_g", "params": [{"name": "x", "type": "u8"}], "body": "x+1"}},
        {"op": "show", "args": {"f": "only_g"}}, "session", "analyze"))
    tf = threading.Thread(target=worker, args=(
        sf, "flat",
        {"name": "only_f", "params": [{"name": "x", "type": "u8"}], "body": "x+2"},
        {"f": "only_f"}, "define", "show"))
    tg.start(); tf.start(); tg.join(8); tf.join(8)
    print("grouped show:", repr(results.get("grouped", "")[:90]))
    print("flat show   :", repr(results.get("flat", "")[:90]))

    # isolation: grouped cannot see only_f, flat cannot see only_g
    iso_g = sg.request(call(300, "analyze", {"op": "show", "args": {"f": "only_f"}}))
    iso_f = sf.request(call(301, "show", {"f": "only_g"}))
    print("grouped sees only_f?:", repr(resp_text(iso_g)[:90]))
    print("flat sees only_g?   :", repr(resp_text(iso_f)[:90]))
    print(f"grouped rc={sg.rc()} flat rc={sf.rc()}")
    sg.close(); sf.close()


# --------------------------------------------------------------------------
# 7. rapid connect/disconnect cycles
# --------------------------------------------------------------------------
def exp_reconnect(cycles=8):
    banner("reconnect (%d rapid spawn / initialize / close cycles)" % cycles)
    bad = []
    rcs = []
    for i in range(cycles):
        s = Server()
        r = s.initialize()
        if r is None or r.get("id") != 0:
            bad.append(f"cycle {i}: no init reply")
        s.close()
        rcs.append(s.rc())
    print("rcs:", rcs)
    print("bad:", bad)
    # check no stray ucas --mcp processes survived
    try:
        out = subprocess.run(["pgrep", "-af", "ucas --mcp"], capture_output=True, text=True, timeout=3).stdout
        print("stray processes:", repr(out[:300]))
    except Exception as e:
        print("pgrep unavailable:", e)


# --------------------------------------------------------------------------
# 8. concurrent CLI --json runs sharing --dir
# --------------------------------------------------------------------------
def exp_concurrent_dir(n=6):
    banner("concurrent_dir (%d CLI --json runs sharing one --dir)" % n)
    os.makedirs(os.path.join(HERE, "shdir"), exist_ok=True)
    d = os.path.join(HERE, "shdir")

    def run(i):
        req = {"id": 1, "cmd": "parse", "args": {"expr": f"{100000+i}+7*3"}}
        p = subprocess.run([BIN, "--json", "--files", "none", "--dir", d],
                           input=json.dumps(req) + "\n", capture_output=True, text=True, timeout=10)
        return i, p.returncode, p.stdout[:120], p.stderr[:120]

    threads = [threading.Thread(target=lambda i=i: results.append(run(i))) for i in range(n)]
    results = []
    for t in threads: t.start()
    for t in threads: t.join(12)
    fail = 0
    for i, rc, out, err in sorted(results):
        if rc != 0 or "ok" not in out:
            fail += 1
            print(f"  run {i}: rc={rc} out={out!r} err={err!r}")
    print(f"runs={n} failures={fail}")


# --------------------------------------------------------------------------
# 9. two independent clients that both start their id counter at 1
# --------------------------------------------------------------------------
def exp_dup_id():
    banner("dup_id (two clients both use id=1; server echoes ids verbatim)")
    s = Server()
    s.initialize()
    # define slowfn under a distinct id
    s.request(call(99, "session", {"op": "define", "args": {
        "name": "slowfn", "params": [{"name": "x", "type": "u8"}], "body": "x*x+3*x"}}))
    # A: id=1, slow (2s). B: id=1, fast. Both sent before replies arrive.
    s.send(call(1, "analyze", {"op": "stoke", "args": {
        "f": "slowfn", "steps": 8000000, "timeout_s": 2}}))
    time.sleep(0.1)
    s.send(expand_req(1, 770001))
    # Collect replies in arrival order (central reader demuxes by id, so both
    # land under the same key, in order).
    time.sleep(3.0)
    bucket = s.responses.get(1, [])
    print(f"replies received for id=1: {len(bucket)}")
    for j, obj in enumerate(bucket):
        print(f"  reply[{j}]: id={obj.get('id')} text={resp_text(obj)[:90]!r}")
    print("Both replies carry id=1 and arrive in REQUEST-arrival order (slow A first).")
    print("=> A client that demultiplexes only by id cannot attribute a reply to itself;")
    print("   the stdio transport offers no per-client channel (no session/connection id).")
    s.close(hard=s.alive())


# --------------------------------------------------------------------------
# 10. client disconnects (closes stdin) while a long request is in flight
# --------------------------------------------------------------------------
def exp_disconnect_midflight():
    banner("disconnect_midflight (client closes stdin during 3s stoke)")
    s = Server()
    s.initialize()
    s.request(call(1, "session", {"op": "define", "args": {
        "name": "slowfn", "params": [{"name": "x", "type": "u8"}], "body": "x*x+3*x"}}))
    s.send(call(2, "analyze", {"op": "stoke", "args": {
        "f": "slowfn", "steps": 8000000, "timeout_s": 3}}))
    time.sleep(0.2)
    t0 = time.time()
    try:
        s.proc.stdin.close()
    except Exception:
        pass
    try:
        s.proc.wait(timeout=6)
        print(f"server exited on its own after {time.time()-t0:.2f}s rc={s.rc()}")
    except subprocess.TimeoutExpired:
        print(f"server STILL ALIVE {time.time()-t0:.2f}s after stdin closed mid-request rc={s.rc()}")
        s.close(hard=True)


# --------------------------------------------------------------------------
# 11. concurrent CLI runs sharing --dir, writing the SAME output file
# --------------------------------------------------------------------------
def exp_concurrent_dir_files(n=4):
    banner("concurrent_dir_files (%d CLI --json plots to same file in one --dir)" % n)
    d = os.path.join(HERE, "shdir")
    os.makedirs(d, exist_ok=True)
    target = os.path.join(d, "raceplot")
    for ext in ("", ".gif"):
        try:
            os.remove(target + ext)
        except OSError:
            pass
    req = json.dumps({"id": 1, "cmd": "ucas",
                      "args": {"source": "plot x^2 to raceplot"}})

    def run(i):
        try:
            p = subprocess.run([BIN, "--json", "--dir", d],
                               input=req + "\n", capture_output=True, text=True, timeout=12)
            return i, p.returncode, p.stderr[:120]
        except subprocess.TimeoutExpired:
            return i, "TIMEOUT", ""

    res = []
    ts = [threading.Thread(target=lambda i=i: res.append(run(i))) for i in range(n)]
    for t in ts: t.start()
    for t in ts: t.join(14)
    print("results:", sorted(res))
    f = target + ".gif"
    if os.path.exists(f):
        with open(f, "rb") as fh:
            head = fh.read(6)
        print(f"output file size={os.path.getsize(f)} header={head!r} (valid GIF header = b'GIF89a')")
    else:
        print("output file MISSING")
    for ext in ("", ".gif"):
        try:
            os.remove(target + ext)
        except OSError:
            pass


EXPERIMENTS = {
    "id_echo": exp_id_echo,
    "dup_id": exp_dup_id,
    "disconnect_midflight": exp_disconnect_midflight,
    "concurrent_dir_files": exp_concurrent_dir_files,
    "large_interleave": exp_large_interleave,
    "state_share": exp_state_share,
    "reset_inflight": exp_reset_inflight,
    "longshort": exp_longshort,
    "twoproc_flat": exp_twoproc_flat,
    "reconnect": exp_reconnect,
    "concurrent_dir": exp_concurrent_dir,
}

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "all":
        for k, fn in EXPERIMENTS.items():
            try:
                fn()
            except Exception as e:
                print(f"!! experiment {k} raised: {e!r}")
    elif arg in EXPERIMENTS:
        EXPERIMENTS[arg]()
    else:
        print("unknown experiment:", arg, file=sys.stderr)
        sys.exit(2)
