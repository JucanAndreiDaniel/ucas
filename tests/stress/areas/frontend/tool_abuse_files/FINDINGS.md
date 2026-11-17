# Stress findings — `tool_abuse_files`

_Original heading: FINDINGS — `tool_abuse_files`_

# FINDINGS — `tool_abuse_files`

Area: file-path argument handling on the `ucas` MCP server (`$ROOT/ucas --mcp`).
All reproducers were run with cwd = this folder and `timeout 15`. Every catalogued case appears in a
`mcp_*.jsonl` + `mcp_*.out` golden pair; `.out` files were kept only when two consecutive runs were
byte-identical.

Fixture files created in this folder (all inputs, no source edits):
`FUNC_MARKER.c`, `BAD_MARKER.c`, `SECRET_MARKER.c`, `UNREADABLE.c` (mode 000), `subdir/`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 5 | L1–L5 below |
| DETERMINISM | 1 | D1 below |

## Findings

### LIMIT-1 — 1 — `c_optimize` ignores `files:"none"` (attachment still emitted)
**Severity:** LIMIT
_Original classification: `LIMIT-1`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (also `mcp_c_file_paths.jsonl` id 43):

```sh
cd $ROOT/tests/stress/areas/frontend/tool_abuse_files
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_optimize","args":{"file":"FUNC_MARKER.c","files":"none"}}}}' \
| timeout 15 $ROOT/ucas --mcp
```

**Observed:** (`structuredContent.files`):

```json
"files": [{"name": "FUNC_MARKER.opt.c", "mime": "text/x-c", "bytes": 148}]
```

With `nofile:true` the same call yields `"files": []`. `plot`, by contrast, honours
`files:"none"` (`mcp_figures_files.jsonl` id 2 → `"files": []`).

**Why it matters:** the documented `files` mode `none` means "nothing written / attached";
`c_optimize` violates that contract unless `nofile:true` is also given. In MCP mode the attachment
is in-memory (no disk write), so this is a contract/consistency bug, not a filesystem escape.

### LIMIT-2 — 2 — `file` argument is not a pure path: it is parsed as "one line of ucas text" with options
**Severity:** LIMIT
_Original classification: `LIMIT-2`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (`mcp_c_file_paths.jsonl` ids 16, 18–20; plus a focused probe):

```sh
cd $ROOT/tests/stress/areas/frontend/tool_abuse_files
printf '%s\n' \
'{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_lower","args":{"file":"name with spaces.c","files":"none"}}}}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_lower","args":{"file":"--dir /tmp","files":"none"}}}}' \
'{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"c","arguments":{"op":"c_lower","args":{"file":"tab\tname.c","files":"none"}}}}' \
| timeout 15 $ROOT/ucas --mcp
```

**Observed:**

```
id 2: {"code": "c_option",  "message": "c: unknown option 'name'"}
id 3: {"code": "c_option",  "message": "c: unknown option '--dir'"}
id 4: {"code": "bad_request", "message": "file: one line of ucas text, without newlines, control characters or '#'"}
```

A 5000-char path token gives `c: unknown option 'aaa…'` (id 16). An empty path gives
`file is empty` (id 44).

**Why it matters:** a value documented as "a .c file instead of code" is tokenized; paths with
spaces are split into an option + path and rejected. No injection was found — option-like tokens
(`--help`, `--dir`, `--version`, `-h`, `--target`) are all cleanly rejected as "unknown option",
so this value cannot be used to redirect output or change options.

### LIMIT-3 — 3 — directories and `/dev/null` are silently treated as empty C input
**Severity:** LIMIT
_Original classification: `LIMIT-3`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (`mcp_c_file_paths.jsonl` ids 2–6 and 22–26):

**Observed:**
```
file="/dev/null", "/tmp", ".", "..", "$ROOT/tests/stress"
  -> c_optimize: "c optimize: 0 functions, 0 rewrites proved ..."
  -> c_lower:    {"kind": "c_lower", "functions": []}
```

**Why it matters:** a directory passed as `file` yields success-with-empty-result rather than an
error; a caller cannot distinguish "empty file" from "directory / device". Low severity.

### LIMIT-4 — 4 — GLSL compile in `animate exec` is slow enough to break a 15s batch
**Severity:** LIMIT
_Original classification: `LIMIT-4`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
A single `animate exec` call with inline GLSL takes ~0.5–0.7 s (glslangValidator + spirv-opt).
A 20-call batch hit `rc=124` (timeout) on the second determinism run:

**Observed:**
**Reproducer:**
```sh
mcp_animate_file_paths.jsonl (initial, 20 GLSL calls):
  run1: rc=0   t=12.70s
  run2: rc=124 t=15.01s   -> TIMEOUT
```

**Mitigation used:** split into `mcp_animate_paths_a/b/c.jsonl` (7–8 calls each, 1.2–5.3 s).
Not a hang/crash in a single call; just a per-call cost worth recording.

### LIMIT-5 — 5 — embedded NUL in any JSON string yields `-32700 parse error` with `id: null`
**Severity:** LIMIT
_Original classification: `LIMIT-5`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer** (`mcp_tool_names.jsonl` last request; `mcp_c_file_paths.jsonl` ids 21/41;
`mcp_animate_paths_c.jsonl` id 6):

**Observed:**
```
request: {"jsonrpc":"2.0","id":56,"method":"tools/call",
          "params":{"name":"analyze\u0000X","arguments":{}}}
response: {"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"parse error"}}
```

Same for `file:"nul\u0000byte.c"` and for `inputs:[{"file":"nul\u0000byte.c"}]`.
The escaped `\u0000` is legal JSON, so rejecting it is a parser limitation (C-string NUL handling).
The server survives — subsequent requests in the same stream are answered correctly — but the
error has no `id` and cannot be correlated to the request.

### DETERMINISM-1 — 1 — `animate exec` with default/noise inputs is nondeterministic
**Severity:** DETERMINISM
_Original classification: `DETERMINISM-1`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer** (`mcp_animate_nondet.jsonl`, no golden kept):

**Observed:**
```sh
cd $ROOT/tests/stress/areas/frontend/tool_abuse_files
timeout 15 $ROOT/ucas --mcp < mcp_animate_nondet.jsonl
```

`inputs:[null]` and `inputs:[]` (with a valid sampler2D GLSL shader, `nofile:true`, `files:"none"`)
succeed but use a fresh random seed. Two runs differ:

```
-  buffers start with random values (seed 57025)
-  input 1 = img (binding 0): noise RGBA8 64x64, mipmapped, checksum 41f5775a
-  output o: RGBA8 64x64, checksum f84453f6
-  (nofile: GIF checksum 916a08f1)
+  buffers start with random values (seed 57029)
+  input 1 = img (binding 0): noise RGBA8 64x64, mipmapped, checksum 4a51f315
+  output o: RGBA8 64x64, checksum de746be5
+  (nofile: GIF checksum e4f56965)
```

Per-element sampled values and GIF byte counts also change. Supplying an explicit `seed` was not
tested as a fix; as-is this cannot be a golden. Documented only.

## Checks that passed

### Summary of severity
| Severity | Count | Topic |
|---|---|---|
| CRASH | 0 | — |
| HANG | 0 | — (one slow batch, see LIMIT-4) |
| WRONG | 0 | — |
| NLP | 0 | — |
| LIMIT | 5 | L1–L5 below |
| DETERMINISM | 1 | D1 below |
| PASS (positive results) | 4 | P1–P4 below |

### PASS results (positive findings — no bug)
#### P1 — unusual tool names always give a clean `unknown tool` error

`mcp_tool_names.jsonl` (55 calls): MCP/JSON-RPC method names (`tools/list`, `tools/call`,
`initialize`, `ping`, `resources/*`, `prompts/*`, `shutdown`, `exit`, …), op names
(`schema`, `state`, `define`, `equiv`, `c_optimize`, `plot3d`, …), empty/whitespace names,
Unicode (NBSP, ZWSP, RTL override, emoji), case variants, path-like names (`/dev/null`,
`../..`, `c/../../etc/passwd`), and a 200-char name all return:

```
{"jsonrpc":"2.0","id":N,"error":{"code":-32602,"message":"unknown tool \"<name>\""}}
```

No crashes, no family-name dispatch, no accidental routing. (`notifications/initialized` sent as a
*request* with an id returns `-32601 method not found` — also clean.)

#### P2 — no unintended file-content leak via errors

Files with recognizable unique markers were used as `file` inputs:
`BAD_MARKER.c` = `int UNIQUE_LEAK_MARKER_7766 = @ ;`, `FUNC_MARKER.c` = `int UNIQUE_FUNC_MARKER_5566…`.

- Parse errors echo **only filename + line:col + expected token**, never the line text:
  `/etc/hostname:1:1: expected a declaration`,
  `BAD_MARKER.c:1:31: expected an expression before '@'`. `UNIQUE_LEAK_MARKER_7766` never appears.
- Files read successfully (`FUNC_MARKER.c`, `/etc/passwd`) produce `expected a declaration` with no content.
- Content does appear in *successful* `c_optimize`/`c_lower` output (`UNIQUE_FUNC_MARKER_5566`), but
  that is the explicit subject of the operation (the C code being analyzed), not a leak.
- `animate` image inputs that are not images report only the path:
  `animate exec: /etc/hostname: not an image file I can read (PNG, JPEG, GIF, BMP, PPM/PGM)`.

#### P3 — no file writes outside the folder; path traversal in `to` is blocked

- `to` is validated as a name (`^[A-Za-z_][A-Za-z0-9_]*$`). All traversal/odd values
  (`../escape`, `a/b`, `subdir/../INSIDE`, `""`, `é`, `1abc`, `a-b`, ZWSP) return
  `{"code":"bad_request","message":"to: a name"}` (`mcp_figures_files.jsonl` ids 12–29).
- Default MCP `files` mode attaches files **in memory** (`"files":[{"name":"plot.gif",…}]`, no `path`).
- Explicit `files:"write"` / `"both"` writes only to the process cwd, reporting
  `"path":"$ROOT/tests/stress/areas/frontend/tool_abuse_files/plot.gif"` (ids 6/8). This stayed
  inside my folder; the artifact was removed afterwards.
- No `.opt.c` or `.gif` was ever observed outside this folder.

#### P4 — unreadable / nonexistent paths are handled cleanly; no hangs

- `UNREADABLE.c` (mode 000) → `c: cannot read UNREADABLE.c` / `animate exec: cannot open UNREADABLE.c`.
- Nonexistent paths → `c: cannot read <path>` / `animate exec: cannot open <path>`.
- Relative `..` paths are resolved normally (`subdir/../FUNC_MARKER.c`
  resolved back inside the folder and succeeded).
- Every catalogued batch returned `rc=0` with empty stderr (except the split-out slow batch of LIMIT-4).
