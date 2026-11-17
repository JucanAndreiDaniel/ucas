"""Generate the tool/file-path abuse JSONL probes. Not a golden itself.
Run from this folder: python3 gen_study.py
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
import json, os

def req(i, m, p=None):
    d = {"jsonrpc": "2.0", "id": i, "method": m}
    if p is not None:
        d["params"] = p
    return json.dumps(d, ensure_ascii=False)

def call(i, name, args=None):
    return req(i, "tools/call", {"name": name, "arguments": args if args is not None else {}})

HDR = lambda: [
    req(0, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "stress", "version": "1"}}),
    req(1, "notifications/initialized"),
]

# ---- fixtures (all created inside our own folder) ----
open("FUNC_MARKER.c", "w").write("int UNIQUE_FUNC_MARKER_5566(int x) { return x + 1; }\n")
open("BAD_MARKER.c", "w").write("int UNIQUE_LEAK_MARKER_7766 = @ ;\n")
import stat
if os.path.exists("UNREADABLE.c"):
    os.chmod("UNREADABLE.c", 0o644)
open("UNREADABLE.c", "w").write("int UNREADABLE_MARKER_3344(int x){return x+2;}\n")
os.chmod("UNREADABLE.c", 0)
os.makedirs("subdir", exist_ok=True)

# ---- Group A: unusual tool names ----------------------------------------
names = [
    # MCP / JSON-RPC method names used as tool names
    "tools/list", "tools/call", "initialize", "notifications/initialized",
    "ping", "resources/list", "resources/read", "resources/templates/list",
    "prompts/list", "prompts/get", "completion/complete", "logging/setLevel",
    "shutdown", "exit", "initialize/probe",
    # op names (valid ops, not tools)
    "schema", "state", "define", "reset", "assume", "funcs", "models",
    "use", "help", "equiv", "c_optimize", "c_lower", "c_targets",
    "plot3d", "animate", "show", "range", "parse", "table",
    # whitespace / unicode / case / path-like
    "", " ", "   ", "\t", "\n", "\r\n", "\u00a0", "\u200b",
    "c ", " c", "Analyze", "C", "SESSION", "tools/list ",
    "/dev/null", "../..", "c/../../etc/passwd", "\U0001f4a1", "\u202e",
    "a" * 200,
]
lines = HDR()
i = 2
for n in names:
    lines.append(call(i, n, {}))
    i += 1
# one name containing a NUL byte
lines.append(call(i, "analyze\u0000", {}))
open("mcp_tool_names.jsonl", "w").write("\n".join(lines) + "\n")

# ---- shared path lists --------------------------------------------------
PATHS = [
    "/dev/null",
    str(_REPO_ROOT / "tests/stress"),   # directory
    ".",                                     # directory (cwd)
    "..",                                    # directory, relative parent
    "/tmp",                                  # directory
    "../BRIEF.md",                           # relative with ..
    "../../opencode.json",                   # relative with .. (outside folder)
    "subdir/../FUNC_MARKER.c",               # .. resolves back inside folder
    "../../../../etc/hostname",              # relative traversal to /etc
    "no_such_file_998877.c",                 # does not exist
    "/nonexistent/dir/file.c",               # does not exist, absolute
    "UNREADABLE.c",                          # unreadable (mode 000)
    "FUNC_MARKER.c",                         # valid, content marker
    "/etc/hostname",                         # readable file outside folder
    "a" * 5000,                              # very long path component
    "/" + "a/" * 500 + "x.c",                # very long multi-component path
    "name with spaces.c",                    # spaces
    "tab\tname.c",                           # tab in path
    "line\nbreak.c",                         # newline in path
    "nul\u0000byte.c",                       # NUL byte in path
]

# ---- Group B: c tool `file` argument ------------------------------------
lines = HDR()
i = 2
for op in ("c_optimize", "c_lower"):
    for p in PATHS:
        args = {"file": p, "files": "none"}
        if op == "c_optimize":
            args["nofile"] = True
        lines.append(call(i, "c", {"op": op, "args": args}))
        i += 1
# conflicts / edge arg combos
lines.append(call(i, "c", {"op": "c_optimize", "args": {
    "code": "int f(int x){return x+1;}", "file": "FUNC_MARKER.c",
    "nofile": True, "files": "none"}})); i += 1
lines.append(call(i, "c", {"op": "c_optimize", "args": {
    "file": "FUNC_MARKER.c", "files": "none"}})); i += 1
lines.append(call(i, "c", {"op": "c_lower", "args": {
    "file": "", "files": "none"}})); i += 1
open("mcp_c_file_paths.jsonl", "w").write("\n".join(lines) + "\n")

# ---- Group C: animate inputs[].file -------------------------------------
# A valid GLSL exec shader that actually declares a sampler2D input, so the
# `file` input is genuinely opened/parsed (invalid code fails before that).
GLSL = ("#version 450\n"
        "layout(binding = 0) uniform sampler2D img;\n"
        "layout(location = 0) in vec2 uv;\n"
        "layout(location = 0) out vec4 o;\n"
        "void main() { o = texture(img, uv).bgra; }\n")
# GLSL compilation is ~0.6s per call, so split into small batches that each
# finish well within `timeout 15`.
def anim_lines(start_id, paths):
    out = HDR()
    i = start_id
    for p in paths:
        out.append(call(i, "plot", {"op": "animate", "args": {
            "code": GLSL, "inputs": [{"file": p}],
            "nofile": True, "files": "none"}}))
        i += 1
    return out

open("mcp_animate_paths_a.jsonl", "w").write(
    "\n".join(anim_lines(2, PATHS[:7])) + "\n")
open("mcp_animate_paths_b.jsonl", "w").write(
    "\n".join(anim_lines(2, PATHS[7:14])) + "\n")
# inputs as bare string / other shapes, plus the remaining paths
lines = HDR()
i = 2
for p in PATHS[14:]:
    lines.append(call(i, "plot", {"op": "animate", "args": {
        "code": GLSL, "inputs": [{"file": p}],
        "nofile": True, "files": "none"}})); i += 1
lines.append(call(i, "plot", {"op": "animate", "args": {
    "code": GLSL, "inputs": ["/etc/hostname"],
    "nofile": True, "files": "none"}})); i += 1
open("mcp_animate_paths_c.jsonl", "w").write("\n".join(lines) + "\n")

# [None] and [] inputs fall back to random noise and are NONdeterministic
# (random seed + GIF checksums change every run). Documented, no golden.
lines = HDR()
i = 2
for inp in ([None], []):
    lines.append(call(i, "plot", {"op": "animate", "args": {
        "code": GLSL, "inputs": inp,
        "nofile": True, "files": "none"}})); i += 1
open("mcp_animate_nondet.jsonl", "w").write("\n".join(lines) + "\n")

# ---- Group D: file modes + `to` output names ----------------------------
lines = HDR()
i = 2
for mode in ("none", "base64", "both", "write"):
    lines.append(call(i, "plot", {"op": "plot", "args": {
        "fs": "x^2", "files": mode}})); i += 1
    lines.append(call(i, "plot", {"op": "plot", "args": {
        "fs": "x^2", "nofile": True, "files": mode}})); i += 1
TOKENS = ["GOODNAME", "../escape", "a/b", "", "a" * 100,
          "\u00e9", "1abc", "a-b", "subdir/../INSIDE", "\u200b"]
for tok in TOKENS:
    lines.append(call(i, "plot", {"op": "plot", "args": {
        "fs": "x^2", "to": tok, "files": "none"}})); i += 1
    lines.append(call(i, "plot", {"op": "animate", "args": {
        "code": "%x = 1\n", "to": tok, "nofile": True,
        "files": "none"}})); i += 1
# spirv_simplify is a flat tool (code/... directly, no op/args wrapper)
lines.append(call(i, "spirv_simplify", {
    "code": "not spirv", "nofile": True, "files": "none"})); i += 1
open("mcp_figures_files.jsonl", "w").write("\n".join(lines) + "\n")

# ---- Group E: global `files` arg on other tools -------------------------
lines = HDR()
i = 2
for mode in ("none", "base64", "both", "write"):
    lines.append(call(i, "analyze", {"op": "range",
        "args": {"f": "x^2", "files": mode}})); i += 1
# NOTE: `session schema` is intentionally excluded — its text is ~800KB and
# would bloat the golden. It is probed separately in FINDINGS.md.
lines.append(call(i, "session", {"op": "state", "args": {"files": "none"}})); i += 1
lines.append(call(i, "c", {"op": "c_targets", "args": {"files": "none"}})); i += 1
lines.append(call(i, "english", {"text": "range of x squared",
    "files": "none"})); i += 1
open("mcp_global_files.jsonl", "w").write("\n".join(lines) + "\n")

for f in ("mcp_tool_names.jsonl", "mcp_c_file_paths.jsonl",
          "mcp_animate_paths_a.jsonl", "mcp_animate_paths_b.jsonl",
          "mcp_animate_paths_c.jsonl", "mcp_animate_nondet.jsonl",
          "mcp_figures_files.jsonl", "mcp_global_files.jsonl"):
    print(f, sum(1 for _ in open(f)), "lines")
