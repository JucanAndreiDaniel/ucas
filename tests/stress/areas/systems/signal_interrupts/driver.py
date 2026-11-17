#!/usr/bin/env python3
"""signal_interrupts stress driver.

Generates 150+ interrupt scenarios against $ROOT/ucas,
records exact commands/timing/observed behaviour to results.jsonl (one JSON
object per scenario) and saves each run's stdout/stderr to per-scenario files.
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
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
import json, os, signal, subprocess, sys, time, select, pty, errno
from pathlib import Path

BIN = str(_REPO_ROOT / "ucas")
HERE = Path(__file__).resolve().parent
RESET = [sys.executable, str(HERE / "reset_exec.py")]
LOG = HERE / "results.jsonl"
OUTD = HERE / "runs"
OUTD.mkdir(exist_ok=True)
LOG.write_text("")  # fresh

_counter = [0]

def kids(pid):
    try:
        out = subprocess.check_output(["pgrep", "-P", str(pid)], stderr=subprocess.DEVNULL)
        return [int(x) for x in out.split()]
    except Exception:
        return []

def alive(pid):
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False

def fresh_ok():
    try:
        r = subprocess.run([BIN], input=b"1+1\n",
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5)
        return r.returncode == 0 and b"2" in r.stdout
    except Exception:
        return False

def json_lines_ok(path, mode):
    """Return (valid, detail): every complete line must be a JSON object."""
    try:
        data = Path(path).read_bytes()
    except Exception:
        return False, "no file"
    lines = data.split(b"\n")
    complete = [l for l in lines if l.strip()]
    bad = []
    for l in complete:
        try:
            o = json.loads(l)
            if not isinstance(o, dict): bad.append("not-object")
        except Exception as e:
            bad.append(l[:60].decode("utf-8", "replace"))
    # unterminated final line
    trailing = bool(data) and not data.endswith(b"\n")
    return (not bad and not trailing), f"nlines={len(complete)} bad={bad[:2]} trailing_no_nl={trailing}"

def record(cat, name, cmd, mode, sigs, delay, rc, elapsed_ms, outp, errp,
           kids_before, orphans, extra=None):
    _counter[0] += 1
    ent = dict(id=_counter[0], category=cat, name=name, cmd=cmd, mode=mode,
               signals=sigs, delay_s=delay, rc=rc, elapsed_ms=elapsed_ms,
               out_bytes=Path(outp).stat().st_size if Path(outp).exists() else 0,
               out_lines=Path(outp).read_bytes().count(b"\n") if Path(outp).exists() else 0,
               err_bytes=Path(errp).stat().st_size if Path(errp).exists() else 0,
               kids_before=kids_before, orphans=orphans, fresh_ok=fresh_ok())
    if mode in ("json", "mcp"):
        ent["json_valid"], ent["json_detail"] = json_lines_ok(outp, mode)
    if extra: ent.update(extra)
    with LOG.open("a") as f: f.write(json.dumps(ent)+"\n")
    # concise console line
    print(f"#{ent['id']:03d} {cat:14s} {name:26s} sig={','.join(sigs):9s} "
          f"d={delay:4} rc={rc:4} kids={len(kids_before)} orph={len(orphans)} "
          f"fresh={'Y' if ent['fresh_ok'] else 'N'} "
          f"{ent.get('json_valid','')}", flush=True)
    # cleanup any orphans we found
    for k in orphans:
        try: os.kill(k, signal.SIGKILL)
        except OSError: pass
    return ent

def wait_kill(p, timeout=10):
    try:
        return p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill(); return p.wait()

# --------------------------------------------------------------------------
# 1. CLI file mode: signal matrix over {find,gates,approx,fit,prove,range}
# --------------------------------------------------------------------------
CLI_FILES = {
    "find": "long_find.ucas", "gates": "long_gates.ucas",
    "approx": "long_approx.ucas", "fit": "long_fit.ucas",
    "prove": "long_prove.ucas", "range": "long_range.ucas",
}
def cli_signal(cmdname, sig, delay, reset):
    name = f"cli_{cmdname}_{sig}{'_dfl' if reset else ''}"
    outp = str(OUTD/f"{name}_{delay}.out"); errp = str(OUTD/f"{name}_{delay}.err")
    argv = (RESET if reset else []) + [BIN, CLI_FILES[cmdname]]
    t0=time.time()
    p = subprocess.Popen(argv, cwd=str(HERE), stdout=open(outp,"wb"), stderr=open(errp,"wb"))
    time.sleep(delay)
    kb = kids(p.pid)
    if alive(p.pid):
        try: p.send_signal(getattr(signal,"SIG"+sig))
        except OSError: pass
    rc = wait_kill(p); el=int((time.time()-t0)*1000)
    time.sleep(0.25)
    orph = [k for k in kb if alive(k)]
    record("cli_signal", name, f"{' '.join(argv)} (cwd={HERE.name})", "cli",
           [sig], delay, rc, el, outp, errp, kb, orph)

def category_cli():
    delays=[0.7,1.4,2.1,2.8]
    for cmdname in CLI_FILES:
        for sig in ["INT","TERM","HUP"]:
            for d in delays:
                cli_signal(cmdname, sig, d, reset=(sig=="INT"))

# --------------------------------------------------------------------------
# 2/3. --json and --mcp: signal matrix
# --------------------------------------------------------------------------
MODE_FILES = {"json":("json_long.jsonl", ["--json","--files","none"]),
              "mcp":("mcp_long.jsonl", ["--mcp"])}
def mode_signal(mode, sig, delay, reset):
    fname, extra = MODE_FILES[mode]
    name=f"{mode}_signal_{sig}{'_dfl' if reset else ''}"
    outp=str(OUTD/f"{name}_{delay}.out"); errp=str(OUTD/f"{name}_{delay}.err")
    argv=(RESET if reset else [])+[BIN]+extra
    with open(HERE/fname,"rb") as fin:
        t0=time.time()
        p=subprocess.Popen(argv, cwd=str(HERE), stdin=fin,
                           stdout=open(outp,"wb"), stderr=open(errp,"wb"))
        time.sleep(delay)
        kb=kids(p.pid)
        if alive(p.pid):
            try: p.send_signal(getattr(signal,"SIG"+sig))
            except OSError: pass
        rc=wait_kill(p); el=int((time.time()-t0)*1000)
    time.sleep(0.25)
    orph=[k for k in kb if alive(k)]
    record(f"{mode}_signal", name, f"{' '.join(argv)} < {fname}", mode,
           [sig], delay, rc, el, outp, errp, kb, orph)

def category_modes():
    for mode in ["json","mcp"]:
        for sig in ["INT","TERM","HUP"]:
            for d in [0.8,1.6,2.4]:
                mode_signal(mode, sig, d, reset=(sig=="INT"))

# --------------------------------------------------------------------------
# 4. Kill the forked timeout child externally, observe server response
# --------------------------------------------------------------------------
def child_kill(mode, sig):
    fname, extra = MODE_FILES[mode]
    name=f"{mode}_childkill_{sig}"
    outp=str(OUTD/f"{name}.out"); errp=str(OUTD/f"{name}.err")
    argv=[BIN]+extra
    with open(HERE/fname,"rb") as fin:
        t0=time.time()
        p=subprocess.Popen(argv, cwd=str(HERE), stdin=fin,
                           stdout=open(outp,"wb"), stderr=open(errp,"wb"))
        time.sleep(1.5)
        kb=kids(p.pid)
        target = kb[0] if kb else None
        if target and alive(target):
            try: os.kill(target, getattr(signal,"SIG"+sig))
            except OSError: pass
        time.sleep(1.0)
        parent_alive = alive(p.pid)
        if parent_alive:
            p.send_signal(signal.SIGKILL)
        rc=wait_kill(p); el=int((time.time()-t0)*1000)
    time.sleep(0.2)
    orph=[k for k in kb if alive(k)]
    record(f"{mode}_childkill", name, f"kill -{sig} <worker-child of {argv[0]} {mode}>",
           mode, [sig], 1.5, rc, el, outp, errp, kb, orph,
           extra={"parent_alive_after_child_kill":parent_alive})

def category_childkill():
    for mode in ["json","mcp"]:
        for sig in ["TERM","INT","KILL"]:
            child_kill(mode, sig)

# --------------------------------------------------------------------------
# 5. Kill the parent server externally -> orphaned worker (already seen once)
# --------------------------------------------------------------------------
def parent_kill(mode, sig):
    fname, extra = MODE_FILES[mode]
    name=f"{mode}_parentkill_{sig}"
    outp=str(OUTD/f"{name}.out"); errp=str(OUTD/f"{name}.err")
    argv=[BIN]+extra
    with open(HERE/fname,"rb") as fin:
        t0=time.time()
        p=subprocess.Popen(argv, cwd=str(HERE), stdin=fin,
                           stdout=open(outp,"wb"), stderr=open(errp,"wb"))
        time.sleep(1.5)
        kb=kids(p.pid)
        p.send_signal(getattr(signal,"SIG"+sig))
        rc=wait_kill(p); el=int((time.time()-t0)*1000)
    time.sleep(0.4)
    orph=[k for k in kb if alive(k)]
    record(f"{mode}_parentkill", name, f"kill -{sig} <parent> ({argv[0]} {mode})",
           mode, [sig], 1.5, rc, el, outp, errp, kb, orph)

def category_parentkill():
    for mode in ["json","mcp"]:
        for sig in ["TERM","INT","HUP","KILL"]:
            parent_kill(mode, sig)

# --------------------------------------------------------------------------
# 6. SIGTSTP / SIGCONT
# --------------------------------------------------------------------------
def stop_cont(mode, delay, kill_after):
    name=f"{mode}_tstp_cont"+(f"_{kill_after}" if kill_after else "")
    outp=str(OUTD/f"{name}_{delay}.out"); errp=str(OUTD/f"{name}_{delay}.err")
    if mode=="cli":
        argv=[BIN, "long_gates.ucas"]; fin=subprocess.DEVNULL; md="cli"
    else:
        fname,extra=MODE_FILES[mode]; argv=[BIN]+extra; fin=open(HERE/fname,"rb"); md=mode
    t0=time.time()
    p=subprocess.Popen(argv, cwd=str(HERE), stdin=fin,
                       stdout=open(outp,"wb"), stderr=open(errp,"wb"))
    time.sleep(delay)
    kb=kids(p.pid)
    p.send_signal(signal.SIGTSTP)
    time.sleep(0.4)
    stat = ""
    try:
        stat=Path(f"/proc/{p.pid}/stat").read_text().split()[2]
    except Exception: pass
    p.send_signal(signal.SIGCONT)
    if kill_after:
        time.sleep(0.6)
        if alive(p.pid): p.send_signal(getattr(signal,"SIG"+kill_after))
    rc=wait_kill(p); el=int((time.time()-t0)*1000)
    time.sleep(0.25)
    orph=[k for k in kb if alive(k)]
    record("tstp_cont", name, "SIGTSTP then SIGCONT"+(f" then {kill_after}" if kill_after else ""),
           md, ["TSTP","CONT"]+([kill_after] if kill_after else []), delay,
           rc, el, outp, errp, kb, orph, extra={"state_at_stop":stat})

def category_tstp():
    for mode in ["cli","json","mcp"]:
        for d in [1.0, 2.0]:
            stop_cont(mode, d, None)
            stop_cont(mode, d, "INT")

# --------------------------------------------------------------------------
# 7. Close stdin mid-query
# --------------------------------------------------------------------------
def close_stdin(mode, delay):
    name=f"{mode}_close_stdin"
    outp=str(OUTD/f"{name}_{delay}.out"); errp=str(OUTD/f"{name}_{delay}.err")
    if mode=="cli":
        argv=[BIN, "--files", "none"]; md="cli"
        seed=b"f(x: u6) = x*x*x+47\ngates f max 70 nodes 100000000\n"
    elif mode=="json":
        argv=[BIN,"--json","--files","none"]; md="json"
        seed=(Path(HERE)/"json_long.jsonl").read_bytes()
    else:
        argv=[BIN,"--mcp"]; md="mcp"
        seed=(Path(HERE)/"mcp_long.jsonl").read_bytes()
    t0=time.time()
    p=subprocess.Popen(argv, cwd=str(HERE), stdin=subprocess.PIPE,
                       stdout=open(outp,"wb"), stderr=open(errp,"wb"))
    p.stdin.write(seed); p.stdin.flush()
    time.sleep(delay)
    kb=kids(p.pid)
    try:
        p.stdin.close()   # close the pipe while the search is running
    except Exception: pass
    time.sleep(0.4)
    if alive(p.pid): p.send_signal(signal.SIGKILL)  # bound: server may ignore EOF
    rc=wait_kill(p); el=int((time.time()-t0)*1000)
    time.sleep(0.2)
    orph=[k for k in kb if alive(k)]
    record("close_stdin", name, f"close stdin pipe after {delay}s mid-search ({' '.join(argv)})",
           md, ["EOF"], delay, rc, el, outp, errp, kb, orph)

def category_close_stdin():
    for mode in ["cli","json","mcp"]:
        for d in [0.8, 1.6, 2.4]:
            close_stdin(mode, d)

# --------------------------------------------------------------------------
# 8. Ctrl-C via pseudo-terminal (script -qec) and pty.fork
# --------------------------------------------------------------------------
def pty_script(cmdname, delay):
    name=f"pty_script_{cmdname}"
    outp=str(OUTD/f"{name}_{delay}.out")
    t0=time.time()
    # feed ^C after delay; keep stdin open a little after so script doesn't EOF early
    sh=f"( sleep {delay}; printf '\\003'; sleep 2 ) | timeout 12 script -qec \"{BIN} {CLI_FILES[cmdname]}\" /dev/null"
    with open(outp,"wb") as f:
        p=subprocess.Popen(["bash","-c",sh], cwd=str(HERE), stdout=f, stderr=subprocess.STDOUT)
        rc=wait_kill(p, timeout=16); el=int((time.time()-t0)*1000)
    errp=str(OUTD/f"{name}_{delay}.err"); Path(errp).write_bytes(b"")
    record("pty_ctrlc", name, sh, "cli", ["Ctrl-C(pty)"], delay, rc, el, outp, errp, [], [])

def pty_fork(cmdname, delay):
    name=f"pty_fork_{cmdname}"
    outp=str(OUTD/f"{name}_{delay}.out"); errp=str(OUTD/f"{name}_{delay}.err")
    data=[]
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(str(HERE)); os.execv(BIN, [BIN, CLI_FILES[cmdname]]); os._exit(127)
    t0=time.time()
    # drain master in a loop until child exits
    import fcntl
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
    sent=False
    status=None
    deadline=time.time()+15
    while time.time()<deadline:
        if not sent and time.time()-t0>=delay:
            os.write(fd, b"\x03"); sent=True
        try:
            r,_,_=select.select([fd],[],[],0.1)
            if r:
                try: chunk=os.read(fd,65536)
                except OSError: chunk=b""
                if not chunk: break
                data.append(chunk)
        except OSError: break
        w,st=os.waitpid(pid, os.WNOHANG)
        if w==pid:
            status=st; break
    if status is None:
        try: os.kill(pid, signal.SIGKILL)
        except OSError: pass
        _,status=os.waitpid(pid,0)
    el=int((time.time()-t0)*1000)
    Path(outp).write_bytes(b"".join(data))
    Path(errp).write_bytes(b"")
    rc=os.waitstatus_to_exitcode(status)
    record("pty_ctrlc", name, f"pty.fork + write \\003 after {delay}s -> {BIN} {CLI_FILES[cmdname]}",
           "cli", ["Ctrl-C(pty)"], delay, rc, el, outp, errp, [], [])

def category_pty():
    for cmdname in CLI_FILES:
        for d in [1.0,2.0]:
            pty_script(cmdname, d)
    for cmdname in ["gates","approx","find","range"]:
        pty_fork(cmdname, 1.5)

# --------------------------------------------------------------------------
# 9. Rapid double / triple interrupts
# --------------------------------------------------------------------------
def double_int(mode, sigs, gap):
    name=f"{mode}_double_{'_'.join(sigs)}"
    outp=str(OUTD/f"{name}_{gap}.out"); errp=str(OUTD/f"{name}_{gap}.err")
    if mode=="cli":
        argv=[BIN,"long_gates.ucas"]; fin=subprocess.DEVNULL; md="cli"
    else:
        fname,extra=MODE_FILES[mode]; argv=[BIN]+extra; fin=open(HERE/fname,"rb"); md=mode
    t0=time.time()
    p=subprocess.Popen(argv, cwd=str(HERE), stdin=fin,
                       stdout=open(outp,"wb"), stderr=open(errp,"wb"))
    time.sleep(1.0)
    kb=kids(p.pid)
    for s in sigs:
        if alive(p.pid):
            try: p.send_signal(getattr(signal,"SIG"+s))
            except OSError: pass
        time.sleep(gap)
    rc=wait_kill(p); el=int((time.time()-t0)*1000)
    time.sleep(0.25)
    orph=[k for k in kb if alive(k)]
    record("double_int", name, f"send {'/'.join(sigs)} {gap}s apart mid-search ({mode})",
           md, sigs, 1.0, rc, el, outp, errp, kb, orph)

def category_double():
    combos=[["INT","INT"],["TERM","TERM"],["INT","TERM"],["TERM","INT"],
            ["HUP","HUP"],["INT","TERM","INT"]]
    for mode in ["cli","mcp"]:
        for c in combos:
            double_int(mode, c, 0.02)

# --------------------------------------------------------------------------
def main():
    which = sys.argv[1] if len(sys.argv)>1 else "all"
    cats = {
      "cli":category_cli, "modes":category_modes, "childkill":category_childkill,
      "parentkill":category_parentkill, "tstp":category_tstp,
      "close":category_close_stdin, "pty":category_pty, "double":category_double,
    }
    if which=="all":
        for f in cats.values(): f()
    else:
        cats[which]()
    print("TOTAL", _counter[0], flush=True)

if __name__=="__main__":
    main()
