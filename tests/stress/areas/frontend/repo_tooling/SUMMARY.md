# SUMMARY — `repo_tooling`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 2
- Files created: 3

### Counts

- **Tool invocations executed: 157** (all bounded by `timeout`; full evidence in
  `harness_log.txt` and machine-readable `harness_log.json`).
  - ucas.sh resolution/exec/smoke (A1–A10, H, part of M): **60**
  - `mcp_client.py` variants + 31 fake-server reply scenarios (B, I, M): **51**
  - `mcp_sdk_check.mjs` (no SDK / SDK 1.20.2, valid, `--flat`, bad bin, fake server): **9**
  - `test.sh` (5 env configurations): **5**
  - `ucas_client.py` (real + fake JSON + driver): **11**
  - `gifcheck.py` / `pcf2c.py` (valid/invalid/malformed inputs): **21**
- Behaviour: 85 succeeded (rc 0), 70 exited nonzero (mostly deliberate malformed-input
  crashes), 2 hung and were killed by `timeout` (`rc 124`).
- **Distinct malformed MCP reply scenarios: 31** (server exits, bad/blank JSON, wrong/string
  ids, missing/null `result`, error at each handshake stage, missing `tools`/`name`/
  `content`/`text`/`readings`/`data`/`mimeType`, invalid base64, duplicate ids, CRLF,
  Unicode, empty tools, `isError`, 10 KB line, two hangs, plus controls).
- **Files created:** harness (3: `run_harness.py`, `fake_mcp.py`, `fake_json.py`), logs
  (2), goldens (5 `.out` + `01_ucas_sh_cli.ucas` + `mcp_tooling_smoke.jsonl` +
  `run_goldens.sh`), SDK test copy (1 `sdk_check_copy.mjs` + local `node_modules/`
  symlinks), and runtime artifacts (GIFs/PNGs/stub binaries/env-tree fixtures) — all inside
  `tests/stress/areas/frontend/repo_tooling/`. **No file was written outside this folder.**


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 2 | F1 (mcp_client.py --flat alone tries to exec --mcp), F3 (missing/dead/bad-JSON server → raw traceback) |
| HANG | 1 | F2 (request() has no timeout; wrong-id/silent server hangs forever) |
| WRONG | 2 | F5 (ucas.sh which accepts a directory as the binary), F6 (HOME unset + ~/ → unbound variable, silent fallback) |
| LIMIT | 7 | F4 (no validation of MCP reply shapes), F7 (no trimming of skills.env values), F8 (coreutils needed even for which), F9 (unconditional mcp_p |

### Issues by severity (see FINDINGS.md for each reproducer)

| Severity | Count | IDs |
| --- | --- | --- |
| CRASH | 2 | F1 (`mcp_client.py --flat` alone tries to exec `--mcp`), F3 (missing/dead/bad-JSON server → raw traceback) |
| HANG | 1 | F2 (`request()` has no timeout; wrong-id/silent server hangs forever) |
| WRONG | 2 | F5 (`ucas.sh which` accepts a directory as the binary), F6 (`HOME` unset + `~/` → unbound variable, silent fallback) |
| NLP | 0 | — |
| LIMIT | 7 | F4 (no validation of MCP reply shapes), F7 (no trimming of skills.env values), F8 (coreutils needed even for `which`), F9 (unconditional `mcp_plot.gif` write, 0-byte file on failure), F10 (SDK-check prerequisite errors), F11 (`ucas_client.py` raw tracebacks), F12 (`test.sh` misidentifies wrong binary; no-binary branch unreachable in-tree) |
| DETERMINISM | 0 | all kept goldens byte-identical across two runs |

### Golden files (all deterministic; regenerate with `sh run_goldens.sh`)

- `01_ucas_sh_cli.ucas` / `.out` — CLI through `ucas.sh` (range + SAT `equiv`).
- `mcp_tooling_smoke.jsonl` / `.out` — MCP through `ucas.sh --mcp --dir .`.
- `tool_mcp_client.out` / `tool_mcp_client_flat.out` — stdout of `mcp_client.py <bin>` with
  and without `--flat` (commands recorded in `run_goldens.sh`).
- `tool_ucas_client.out` — stdout of `ucas_client.py <bin>` demo.


## Takeaway
The tooling works on the happy path (all SKILL.md recipes, the skill test, ambiguity answering and image saving pass, and the SDK check is clean with SDK 1.20.2), but it is written with zero defensive handling: `mcp_client.py --flat` alone crashes, malformed MCP replies or a silent server produce raw tracebacks or a hang, and `ucas.sh`/`skills.env` resolution has several misleading edge cases (directory as binary, CRLF/spaces, unset `HOME`).

### Original takeaway (verbatim)

The tooling works on the happy path (all SKILL.md recipes, the skill test, ambiguity
answering and image saving pass, and the SDK check is clean with SDK 1.20.2), but it is
written with zero defensive handling: `mcp_client.py --flat` alone crashes, malformed MCP
replies or a silent server produce raw tracebacks or a hang, and `ucas.sh`/`skills.env`
resolution has several misleading edge cases (directory as binary, CRLF/spaces, unset
`HOME`).
