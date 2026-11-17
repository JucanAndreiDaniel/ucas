# SUMMARY — `tool_abuse_files`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 7
- Files created: not recorded

### Scope
File-path argument handling on the `ucas` MCP server over JSON-RPC (`ucas --mcp`).
Focus: (1) unusual tool names, (2) unusual `file`-like arguments, (3) filesystem confinement and
content-leak checks. All runs used `timeout 15` with cwd = this folder.

### Counts
- **Distinct catalogued queries: 157** (tool names 55, c-file-paths 43, animate file inputs 23,
  figure/file modes 29, global `files` arg 7), plus ~40 focused exploratory probes ≈ **197 total**.
- **Golden pairs written: 7** (`mcp_tool_names`, `mcp_c_file_paths`, `mcp_animate_paths_a/b/c`,
  `mcp_figures_files`, `mcp_global_files`). Each kept only after a two-run byte-identical determinism
  check. Sizes 6–44 KB.
- **Non-golden probe kept: 1** (`mcp_animate_nondet.jsonl`, documented nondeterministic — no `.out`).
- **Fixture input files: 5** (`FUNC_MARKER.c`, `BAD_MARKER.c`, `SECRET_MARKER.c`, `UNREADABLE.c`,
  `subdir/`). No source, Makefile, test, or `opencode.json` edits; no `make`; no git commands.
- **Helper scripts: 3** (`gen_study.py` generator, `run_study.py` runner, plus earlier `probe.py` /
  `gen_probe.py`). Reference dumps kept: `schema.json`, `toollist.raw`, `session_schema.raw`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| LIMIT | 5 | — |
| DETERMINISM | 1 | — |

### Issues by severity
| Severity | Count |
|---|---|
| CRASH | 0 |
| HANG | 0 |
| WRONG | 0 |
| NLP | 0 |
| LIMIT | 5 |
| DETERMINISM | 1 |

List: LIMIT-1 `c_optimize` ignores `files:"none"`; LIMIT-2 `file` arg is tokenized as ucas text
(paths with spaces / option tokens rejected, no injection); LIMIT-3 directories/`dev/null` silently
empty; LIMIT-4 ~0.6 s GLSL compile per animate call; LIMIT-5 NUL in any JSON string → `-32700`
with `id:null`. DETERMINISM-1 animate noise inputs use a random seed.


## Takeaway
tool-name and file-path handling is robust (clean errors, no traversal, no content leaks, no crashes); the actionable gaps are `files:"none"` not honored by `c_optimize`, loss of request id on NUL-containing JSON, and nondeterministic `animate` noise inputs.

### Original takeaway (verbatim)
tool-name and file-path handling is robust (clean errors, no traversal, no content
leaks, no crashes); the actionable gaps are `files:"none"` not honored by `c_optimize`, loss of
request id on NUL-containing JSON, and nondeterministic `animate` noise inputs.

### Confinement / leak result
No file was written outside this folder. Explicit `files:"write"` writes only into cwd.
`to` path traversal is schema-blocked (`to: a name`). Error messages echo only filenames and
line:column — never file content; content appears only when it is the explicit subject of a
successful operation. All 55 unusual tool names produced clean `-32602 unknown tool` errors.
