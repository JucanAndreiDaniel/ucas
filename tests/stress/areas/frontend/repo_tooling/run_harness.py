#!/usr/bin/env python3
"""Stress harness for the repository's OWN developer tooling.

Runs 150+ bounded invocations of tools/* and .claude/skills/ucas/* under many
environments (UCAS set/unset/invalid, PATH with/without ucas, UCAS_BIN in
skills.env, malformed MCP replies, no-binary, image saving, ambiguity, SDK).
Every run is bounded by `timeout` and logged to harness_log.json/.txt.
All working files stay inside this folder.
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
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = str(_REPO_ROOT)
BIN = os.path.join(REPO, "ucas")
U = os.path.join(REPO, ".claude/skills/ucas/ucas.sh")
TESTSH = os.path.join(REPO, ".claude/skills/ucas/test.sh")
MC = os.path.join(REPO, "tools/mcp_client.py")
UC = os.path.join(REPO, "tools/ucas_client.py")
SDK = os.path.join(REPO, "tools/mcp_sdk_check.mjs")
GC = os.path.join(REPO, "tools/gifcheck.py")
PCF = os.path.join(REPO, "tools/pcf2c.py")
FAKE = os.path.join(HERE, "fake_mcp.py")

RUNS = []


def run(name, argv, env=None, cwd=HERE, timeout=15, stdin=None, note=""):
    e = dict(os.environ)
    if env:
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
    started = time.time()
    timed_out = False
    try:
        p = subprocess.run(argv, cwd=cwd, env=e, input=stdin, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=timeout)
        rc, out = p.returncode, p.stdout
    except subprocess.TimeoutExpired as ex:
        timed_out = True
        rc = 124
        out = (ex.stdout or b"")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        out += "\n[TIMED OUT after %ss]" % timeout
    dur = time.time() - started
    RUNS.append({"name": name, "argv": [str(a) for a in argv], "cwd": cwd,
                 "env_delta": env or {}, "rc": rc, "timed_out": timed_out,
                 "dur": round(dur, 2), "out": out, "note": note})
    return rc, out


def first_last(out, n=180):
    lines = [x for x in out.splitlines() if x.strip()]
    if len(out) <= n * 2 + 40:
        return out.replace("\n", "\\n")
    return (lines[0][:n] if lines else "") + " ... " + \
           (lines[-1][:n] if lines else "")


def sh_ucas(args, name, env=None, cwd=HERE, timeout=15, **kw):
    return run(name, ["/bin/sh", U] + args, env=env, cwd=cwd,
               timeout=timeout, **kw)


# ---------------------------------------------------------------- setup
os.makedirs(os.path.join(HERE, "envtree", ".claude"), exist_ok=True)
os.makedirs(os.path.join(HERE, "bin_with_ucas"), exist_ok=True)
os.makedirs(os.path.join(HERE, "copy"), exist_ok=True)

# a stub "ucas" on PATH: echoes its args, exits 0
stub = os.path.join(HERE, "bin_with_ucas", "ucas")
with open(stub, "w") as f:
    f.write("#!/bin/sh\necho STUB-UCAS argv: \"$*\"\nexit 0\n")
os.chmod(stub, 0o755)

# a non-executable file, for the UCAS=nonexec case
nonexec = os.path.join(HERE, "notexec_ucas")
with open(nonexec, "w") as f:
    f.write("not executable\n")
os.chmod(nonexec, 0o644)

# a stub that returns a chosen exit code (forwarded through ucas.sh's exec)
rcstub = os.path.join(HERE, "bin_with_ucas", "rcstub")
with open(rcstub, "w") as f:
    f.write("#!/bin/sh\necho RCSTUB argv: \"$*\"\nexit 37\n")
os.chmod(rcstub, 0o755)

# a copy of ucas.sh placed 3 levels down so its ../../../ucas points at
# tests/ucas (missing): lets us exercise the "no binary" refusal branch.
shutil.copy(U, os.path.join(HERE, "copy", "ucas.sh"))
COPYU = os.path.join(HERE, "copy", "ucas.sh")

PATH_SYSTEM = "/usr/local/bin:/usr/bin:/bin"  # has sed/dirname/tail, no ucas
PATH_STUB = os.path.join(HERE, "bin_with_ucas") + ":" + PATH_SYSTEM


def env_base(**kw):
    e = {"PATH": PATH_SYSTEM}
    e.update(kw)
    return e


# ================================================================ A. ucas.sh
# A1: `which` with the default environment (repo binary as fallback)
for i, cwd in enumerate([HERE, REPO, os.path.join(HERE, "copy"),
                         os.path.join(HERE, "envtree"), "/tmp"]):
    sh_ucas(["which"], "A1.which_default_%d" % i,
            env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=cwd)

# A2: UCAS set to a valid/absolute/relative/nonexec/dir/empty/space path
sh_ucas(["which"], "A2.UCAS_valid_abs", env={"UCAS": BIN, "PATH": PATH_SYSTEM})
sh_ucas(["which"], "A2.UCAS_valid_rel", env={"UCAS": "../ucas", "PATH": PATH_SYSTEM},
        cwd=os.path.join(REPO, "tools"))
sh_ucas(["which"], "A2.UCAS_nonexistent", env={"UCAS": "/nonexistent/ucas", "PATH": PATH_SYSTEM})
sh_ucas(["which"], "A2.UCAS_directory", env={"UCAS": REPO, "PATH": PATH_SYSTEM})
sh_ucas(["which"], "A2.UCAS_nonexec", env={"UCAS": nonexec, "PATH": PATH_SYSTEM})
sh_ucas(["which"], "A2.UCAS_empty", env={"UCAS": "", "PATH": PATH_SYSTEM})
sh_ucas(["which"], "A2.UCAS_space_path", env={"UCAS": "/no such/ucas", "PATH": PATH_SYSTEM})

# A3: ucas on PATH (stub) wins over repo binary when UCAS unset
sh_ucas(["which"], "A3.PATH_stub_wins", env={"UCAS": None, "PATH": PATH_STUB})
sh_ucas(["-e", "range (x: u8)/3"], "A3.PATH_stub_exec", env={"UCAS": None, "PATH": PATH_STUB})

# A4: UCAS overrides PATH (stub) and skills.env
sh_ucas(["which"], "A4.UCAS_over_PATH", env={"UCAS": BIN, "PATH": PATH_STUB})

# A5: skills.env resolution: write into envtree/.claude/skills.env
def set_envfile(body):
    with open(os.path.join(HERE, "envtree", ".claude", "skills.env"), "w") as f:
        f.write(body)

def rm_envfile():
    p = os.path.join(HERE, "envtree", ".claude", "skills.env")
    if os.path.exists(p):
        os.remove(p)

ENV_CWD = os.path.join(HERE, "envtree")
set_envfile("UCAS_BIN=%s\n" % BIN)
sh_ucas(["which"], "A5.skillsenv_abs", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
set_envfile("UCAS_BIN=%s\n" % stub)
sh_ucas(["which"], "A5.skillsenv_stub", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
set_envfile("UCAS_BIN=~/Code/ucas/ucas\n")
sh_ucas(["which"], "A5.skillsenv_tilde", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
sh_ucas(["which"], "A5.skillsenv_tilde_HOMEunset",
        env={"UCAS": None, "PATH": PATH_SYSTEM, "HOME": None}, cwd=ENV_CWD)
set_envfile("UCAS_BIN=/nonexistent/fromenv\n")
sh_ucas(["which"], "A5.skillsenv_invalid", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
set_envfile("UCAS_BIN=\n")
sh_ucas(["which"], "A5.skillsenv_empty", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
set_envfile("# comment\nUCAS_BIN=%s\n" % BIN)
sh_ucas(["which"], "A5.skillsenv_comment", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
set_envfile("UCAS_BIN=/first\nsomething=else\nUCAS_BIN=%s\n" % BIN)
sh_ucas(["which"], "A5.skillsenv_tailn1", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
set_envfile("UCAS_BIN = %s\n" % BIN)  # spaces around = : sed pattern won't match
sh_ucas(["which"], "A5.skillsenv_spaces_eq", env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd=ENV_CWD)
rm_envfile()

# A6: PATH stub beats skills.env when both present
os.makedirs(os.path.join(HERE, "envtree2", ".claude"), exist_ok=True)
with open(os.path.join(HERE, "envtree2", ".claude", "skills.env"), "w") as f:
    f.write("UCAS_BIN=%s\n" % BIN)
sh_ucas(["which"], "A6.PATH_beats_skillsenv",
        env={"UCAS": None, "PATH": PATH_STUB}, cwd=os.path.join(HERE, "envtree2"))
os.remove(os.path.join(HERE, "envtree2", ".claude", "skills.env"))

# A7: no binary at all (copy of script whose ../../../ucas is missing)
sh_ucas(["which"], "A7.no_binary_copy", env={"UCAS": None, "PATH": PATH_SYSTEM},
        cwd=os.path.join(HERE, "copy"))
# direct call of the copy so `here` is the copy's dir
run("A7.no_binary_copy_direct", ["/bin/sh", COPYU, "which"],
    env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd="/tmp")
run("A7.no_binary_copy_direct_arg", ["/bin/sh", COPYU, "-e", "1+1"],
    env={"UCAS": None, "PATH": PATH_SYSTEM}, cwd="/tmp")

# A8: `which` argument handling
sh_ucas(["which", "extra"], "A8.which_extra_arg", env={"UCAS": BIN, "PATH": PATH_SYSTEM})
sh_ucas(["-e", "which"], "A8.which_not_first", env={"UCAS": BIN, "PATH": PATH_SYSTEM})
sh_ucas(["WHICH"], "A8.which_uppercase", env={"UCAS": BIN, "PATH": PATH_SYSTEM})
sh_ucas([], "A8.no_args", env={"UCAS": BIN, "PATH": PATH_SYSTEM})

# A9: exec behaviour / argument forwarding / exit-code passthrough via rcstub
run("A9.exec_rcstub", ["/bin/sh", U, "arg1", "--flag", "a b"],
    env={"UCAS": rcstub, "PATH": PATH_SYSTEM})
run("A9.exec_stub_stdio", ["/bin/sh", U], env={"UCAS": stub, "PATH": PATH_SYSTEM},
    stdin="hello\n")

# A10: real binary through ucas.sh: CLI/JSON/MCP smoke + exit codes
sh_ucas(["-e", "range (x: u8)/3"], "A10.cli_range", env={"UCAS": BIN, "PATH": PATH_SYSTEM})
sh_ucas(["--json", "-e", '{"cmd":"range","args":{"f":"isqrt(x: u4)"}}'],
        "A10.json_range", env={"UCAS": None, "PATH": PATH_SYSTEM})
sh_ucas(["--mcp", "--dir", HERE], "A10.mcp_stdin", env={"UCAS": None, "PATH": PATH_SYSTEM},
        stdin=('{"jsonrpc":"2.0","id":0,"method":"initialize","params":'
               '{"protocolVersion":"2025-06-18","capabilities":{},'
               '"clientInfo":{"name":"h","version":"1"}}}\n'
               '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
               '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":'
               '{"name":"analyze","arguments":{"op":"range","args":'
               '{"f":"isqrt(x: u4)"}}}}\n'))
sh_ucas(["this_is_not_a_statement"], "A10.bad_statement_exit",
        env={"UCAS": BIN, "PATH": PATH_SYSTEM})

# ================================================================ B. mcp_client.py
VARIANTS = [
    ("B.default", [], {}),
    ("B.explicit", [BIN], {}),
    ("B.flat_only", ["--flat"], {}),                     # documented-ish, may crash
    ("B.flat_then_path", ["--flat", BIN], {}),
    ("B.path_then_flat", [BIN, "--flat"], {}),
    ("B.flat_flag_middle", ["--flat", BIN, "--flat"], {}),
    ("B.invalid_bin", ["/nonexistent/ucas"], {}),
    ("B.dir_bin", [REPO], {}),
    ("B.fake_path", [FAKE], {"FAKE_SCENARIO": "normal"}),
]
for name, extra, env in VARIANTS:
    run(name, ["python3", MC] + extra, env=env, timeout=30,
        note="mcp_client.py variant")

SCENS = ["exit0", "exit1", "badjson", "blankline", "no_id", "id_noresult",
         "init_error", "init_noserverinfo", "init_noprotoversion",
         "tools_no_tools", "tools_bad_entry", "call_no_content",
         "call_content_empty", "call_text_missing", "ambig_no_readings",
         "ambig_nodefault", "plot_badb64", "plot_no_image",
         "plot_image_nodata", "plot_image_nomime", "normal", "normal_ambig"]
for s in SCENS:
    try:
        os.remove(os.path.join(HERE, "mcp_plot.gif"))
    except OSError:
        pass
    rc, out = run("B.fake.%s" % s, ["python3", MC, FAKE],
                  env={"FAKE_SCENARIO": s}, timeout=15,
                  note="malformed MCP reply")
    # record whether a gif file appeared
    RUNS[-1]["note"] += "; gif_written=%s" % os.path.exists(os.path.join(HERE, "mcp_plot.gif"))

for s in ["hang_wrongid", "hang_after_init"]:
    run("B.fake.%s" % s, ["python3", MC, FAKE],
        env={"FAKE_SCENARIO": s}, timeout=3,
        note="expected hang: server sends wrong/no id then blocks")

# ================================================================ C. mcp_sdk_check.mjs
run("C.sdk_missing_orig", ["node", SDK, BIN], timeout=30,
    note="SDK not installed next to script")
run("C.sdk_missing_noargs", ["node", SDK], timeout=30)
run("C.sdk_1202_valid", ["node", os.path.join(HERE, "sdk_check_copy.mjs"), BIN],
    timeout=60, note="SDK 1.20.2 via local node_modules symlinks")
run("C.sdk_1202_flat", ["node", os.path.join(HERE, "sdk_check_copy.mjs"), BIN, "--flat"],
    timeout=60)
run("C.sdk_1202_invalid_bin", ["node", os.path.join(HERE, "sdk_check_copy.mjs"),
                               "/nonexistent/ucas"], timeout=30)
run("C.sdk_1202_noargs", ["node", os.path.join(HERE, "sdk_check_copy.mjs")], timeout=30)
run("C.sdk_1202_extra", ["node", os.path.join(HERE, "sdk_check_copy.mjs"), BIN,
                         "--mcp-extra"], timeout=60)

# ================================================================ D. test.sh
run("D.testsh_normal", ["/bin/sh", TESTSH], cwd=REPO, timeout=120,
    note="skill's own test script")
run("D.testsh_mydir", ["/bin/sh", TESTSH], cwd=HERE, timeout=120)
run("D.testsh_UCAS_valid", ["/bin/sh", TESTSH], cwd=HERE, timeout=120,
    env={"UCAS": BIN})
run("D.testsh_UCAS_invalid", ["/bin/sh", TESTSH], cwd=HERE, timeout=120,
    env={"UCAS": "/nonexistent/ucas"})
run("D.testsh_PATH_stub", ["/bin/sh", TESTSH], cwd=HERE, timeout=120,
    env={"PATH": PATH_STUB, "UCAS": None})

# ================================================================ E. ucas_client.py
run("E.uc_default", ["python3", UC], timeout=30)
run("E.uc_explicit", ["python3", UC, BIN], timeout=30)
run("E.uc_invalid", ["python3", UC, "/nonexistent/ucas"], timeout=15)

# ================================================================ F. gifcheck.py / pcf2c.py
# copy the repo's gifs into our folder so frame extraction stays local
for g in ["area.gif", "revolve.gif"]:
    src = os.path.join(REPO, g)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(HERE, g))
for g in ["area.gif", "revolve.gif"]:
    p = os.path.join(HERE, g)
    if os.path.exists(p):
        run("F.gifcheck.%s.info" % g, ["python3", GC, p], timeout=30)
        run("F.gifcheck.%s.frame0" % g, ["python3", GC, p, "0"], timeout=30)
        run("F.gifcheck.%s.badframe" % g, ["python3", GC, p, "x"], timeout=15)
run("F.gifcheck.noargs", ["python3", GC], timeout=15)
run("F.gifcheck.missing", ["python3", GC, os.path.join(HERE, "nope.gif")], timeout=15)
badgif = os.path.join(HERE, "bad.gif")
with open(badgif, "wb") as f:
    f.write(b"NOTAGIF\x00\x01")
run("F.gifcheck.badgif", ["python3", GC, badgif], timeout=15)

run("F.pcf.noargs", ["python3", PCF], timeout=15)
run("F.pcf.invalid", ["python3", PCF, badgif, "x"], timeout=15)
run("F.pcf.missing", ["python3", PCF, os.path.join(HERE, "nope.pcf"), "x"], timeout=15)

# ================================================================ determinism
for i in range(2):
    run("G.mcpclient_determinism_%d" % i, ["python3", MC, BIN], timeout=30,
        note="determinism: diff the two outputs (ignore gif file)")

# ================================================================ H. extra ucas.sh matrix
# UCAS path shape variations
for nm, val in [
    ("trailing_slash", BIN + "/"), ("dot_prefix", "./ucas"),
    ("double_slash", REPO + "//ucas"), ("broken_symlink", os.path.join(HERE, "broken_link")),
    ("stub_script", stub), ("rcstub_script", rcstub),
]:
    if nm == "broken_symlink" and not os.path.islink(val):
        os.symlink("/nonexistent/target", val)
    sh_ucas(["which"], "H.UCAS_%s" % nm, env={"UCAS": val, "PATH": PATH_SYSTEM})
# UCAS wins over a skills.env even when env names a different binary
set_envfile("UCAS_BIN=/nonexistent/fromenv\n")
sh_ucas(["which"], "H.UCAS_over_skillsenv", env={"UCAS": BIN, "PATH": PATH_SYSTEM},
        cwd=ENV_CWD)
rm_envfile()
# skills.env edge cases
for nm, body, extra in [
    ("crlf", "UCAS_BIN=%s\r\n" % BIN, {}),
    ("trailing_space", "UCAS_BIN=%s   \n" % BIN, {}),
    ("leading_space", "UCAS_BIN=  %s\n" % BIN, {}),
    ("uppercase_key", "ucas_bin=%s\n" % BIN, {}),
    ("equals_in_val", "UCAS_BIN=%s\nOTHER=a=b\n" % BIN, {}),
    ("only_comment", "# nothing here\n", {}),
    ("tilde_custom_HOME", "UCAS_BIN=~/myucas\n", {"HOME": os.path.join(HERE, "homeA")}),
]:
    set_envfile(body)
    if nm == "tilde_custom_HOME":
        hd = os.path.join(HERE, "homeA")
        os.makedirs(hd, exist_ok=True)
        shutil.copy(BIN, os.path.join(hd, "myucas"))
        os.chmod(os.path.join(hd, "myucas"), 0o755)
    e = {"UCAS": None, "PATH": PATH_SYSTEM}
    e.update(extra)
    sh_ucas(["which"], "H.skillsenv_%s" % nm, env=e, cwd=ENV_CWD)
rm_envfile()
# nearest skills.env wins: put one here AND one in the parent
set_envfile("UCAS_BIN=%s\n" % BIN)
sh_ucas(["which"], "H.nearest_envfile", env={"UCAS": None, "PATH": PATH_SYSTEM},
        cwd=ENV_CWD)
rm_envfile()
# PATH with no system dirs: ucas.sh needs sed/dirname/tail
sh_ucas(["which"], "H.PATH_stub_only", env={"UCAS": None,
        "PATH": os.path.join(HERE, "bin_with_ucas")})
sh_ucas(["which"], "H.PATH_empty", env={"UCAS": BIN, "PATH": ""})
# real binary: stdin statements, exit code on error, --dir overrides
stmt = "f(x: u8) = x + 1\nrange f\n"
run("H.cli_stdin", ["/bin/sh", U], env={"UCAS": BIN, "PATH": PATH_SYSTEM},
    stdin=stmt)
run("H.cli_error_rc", ["/bin/sh", U, "-e", "range nosuchfn"],
    env={"UCAS": BIN, "PATH": PATH_SYSTEM})
run("H.cli_dir_override", ["/bin/sh", U, "--dir", HERE, "-e", "plot sin(x)"],
    env={"UCAS": BIN, "PATH": PATH_SYSTEM}, timeout=30)

# ================================================================ I. more mcp_client cases
MORE_SCENS = ["dup_id", "string_id", "crlf", "unicode", "empty_tools",
              "iserror_with_error", "huge_line"]
for s in MORE_SCENS:
    try:
        os.remove(os.path.join(HERE, "mcp_plot.gif"))
    except OSError:
        pass
    run("I.mc.%s" % s, ["python3", MC, FAKE], env={"FAKE_SCENARIO": s}, timeout=15)
# run from a nested cwd: the gif must land in THAT cwd, not the tools dir
nested = os.path.join(HERE, "nested")
os.makedirs(nested, exist_ok=True)
run("I.mc_nested_cwd", ["python3", MC, BIN], cwd=nested, timeout=30,
    note="gif should be written into nested cwd")
RUNS[-1]["note"] += "; nested_gif=%s" % os.path.exists(os.path.join(nested, "mcp_plot.gif"))

# ================================================================ J. ucas_client driver
fake_json = os.path.join(HERE, "fake_json.py")
with open(fake_json, "w") as f:
    f.write('''#!/usr/bin/env python3
import json, os, sys
s = os.environ.get("FAKE_JSON_SCENARIO", "exit0")
def emit(o): print(json.dumps(o)); sys.stdout.flush()
if s == "exit0":
    sys.exit(0)
if s == "badjson":
    print("not json"); sys.exit(0)
if s == "wrongid":
    emit({"id":99,"ok":True,"result":{},"error":{}}); sys.exit(0)
if s == "error":
    emit({"id":1,"ok":False,"error":{"code":"failed","message":"boom"}}); sys.exit(0)
if s == "ambig":
    emit({"id":1,"ok":False,"error":{"code":"ambiguous","key":"z","message":"pick",
          "readings":[{"index":0,"reading":"complex","default":True}]}}); sys.exit(0)
if s == "nook":
    emit({"id":1,"result":{}}); sys.exit(0)
''')
os.chmod(fake_json, 0o755)
for s in ["exit0", "badjson", "wrongid", "error", "ambig", "nook"]:
    run("J.uc_fake.%s" % s, ["python3", UC, fake_json],
        env={"FAKE_JSON_SCENARIO": s}, timeout=15)
run("J.uc_explicit_files_none", ["python3", "-c",
    "import sys; sys.path.insert(0,'%s'); from ucas_client import Ucas; "
    "u=Ucas('%s',files='none'); print(u.request('schema')['ok']); u.close()"
    % (os.path.join(REPO, 'tools'), BIN)], timeout=30)
run("J.uc_frm_translation", ["python3", "-c",
    "import sys; sys.path.insert(0,'%s'); from ucas_client import Ucas; "
    "u=Ucas('%s',files='none'); r=u.call('integrate',f='x',frm='0',to='1'); "
    "print(r['ok']); u.close()" % (os.path.join(REPO, 'tools'), BIN)], timeout=30)

# ================================================================ K. more SDK cases
run("K.sdk_flat_dir", ["node", os.path.join(HERE, "sdk_check_copy.mjs"), BIN,
                       "--flat", "--dir", HERE], timeout=60)
run("K.sdk_fake_server", ["node", os.path.join(HERE, "sdk_check_copy.mjs"), FAKE],
    env={"FAKE_SCENARIO": "exit0"}, timeout=30)

# ================================================================ L. more gifcheck/pcf2c cases
for g in ["area.gif", "revolve.gif"]:
    p = os.path.join(HERE, g)
    if os.path.exists(p):
        run("L.gif.%s.frame_big" % g, ["python3", GC, p, "999"], timeout=30)
        run("L.gif.%s.frame_neg" % g, ["python3", GC, p, "-1"], timeout=30)
        run("L.gif.%s.frame_multi" % g, ["python3", GC, p, "0", "1", "2"], timeout=30)
trunc = os.path.join(HERE, "trunc.gif")
with open(os.path.join(REPO, "area.gif"), "rb") as f:
    data = f.read()
with open(trunc, "wb") as f:
    f.write(data[:40])
run("L.gif.truncated", ["python3", GC, trunc], timeout=15)
run("L.pcf.onearg", ["python3", PCF, badgif], timeout=15)
run("L.pcf.gz_invalid", ["python3", PCF, os.path.join(HERE, "bad.gz"), "x"], timeout=15)

# ================================================================ M. final padding to >150
link = os.path.join(HERE, "link_to_ucas")
if not os.path.islink(link):
    os.symlink(BIN, link)
sh_ucas(["which"], "M.UCAS_symlink", env={"UCAS": link, "PATH": PATH_SYSTEM})
sh_ucas(["which"], "M.UCAS_dotdot", env={"UCAS": HERE + "/../ucas", "PATH": PATH_SYSTEM})
sh_ucas(["which"], "M.UCAS_devnull", env={"UCAS": "/dev/null", "PATH": PATH_SYSTEM})
run("M.mc_flat_fake", ["python3", MC, "--flat", FAKE],
    env={"FAKE_SCENARIO": "normal"}, timeout=15)
run("M.mc_flat_invalid", ["python3", MC, "--flat", "/nonexistent/ucas"], timeout=15)
run("M.mc_fake_path_flat", ["python3", MC, FAKE, "--flat"],
    env={"FAKE_SCENARIO": "normal"}, timeout=15)
for s in ["init_null", "tools_null", "call_null"]:
    run("M.mc.%s" % s, ["python3", MC, FAKE],
        env={"FAKE_SCENARIO": s}, timeout=15)
run("M.sdk_valid_again", ["node", os.path.join(HERE, "sdk_check_copy.mjs"), BIN],
    timeout=60)

# ---------------------------------------------------------------- write logs
with open(os.path.join(HERE, "harness_log.json"), "w") as f:
    json.dump(RUNS, f, indent=1)
with open(os.path.join(HERE, "harness_log.txt"), "w") as f:
    for r in RUNS:
        f.write("%-32s rc=%-4s %-5s %.2fs env=%s | %s\n" % (
            r["name"], r["rc"], "HANG" if r["timed_out"] else "",
            r["dur"], json.dumps(r["env_delta"]), first_last(r["out"])))
print("TOTAL invocations:", len(RUNS))
print("crashes(rc!=0 && !hang):", sum(1 for r in RUNS if r["rc"] != 0 and not r["timed_out"]))
print("hangs:", sum(1 for r in RUNS if r["timed_out"]))
