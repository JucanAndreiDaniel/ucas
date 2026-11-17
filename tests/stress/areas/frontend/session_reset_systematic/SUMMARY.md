# SUMMARY — `session_reset_systematic`

## Counts
- Distinct expressions/queries tried: 220
- Goldens written: 22
- Files created: 22

### Counts

- **Distinct state/clear sequences tried: >220** (213 in kept goldens + ~90 exploratory
  creator×clearer/frontend probes, including a 1200-reset scaling run and a 1200-state control).
- **Golden files written: 22** — 10 CLI (`NN_*.ucas`/`.out`) and 12 MCP (`.jsonl`/`.out`, one
  with a `--flat` `.flags`). All 22 were run twice and byte-diffed: all deterministic, all
  exit 0 under `timeout` (20 s CLI / 30 s MCP).
- **Issues found:** 7 WRONG, 1 NLP (overlaps a WRONG), 2 LIMIT, 1 rare non-reproducible
  DETERMINISM; **0 CRASH, 0 HANG**.

### Folder scope

All artifacts are confined to `$ROOT/tests/stress/areas/frontend/session_reset_systematic/`.
No source file, Makefile, existing test, `opencode.json`, or another subagent's folder was touched;
no `make`/`git` commands were run.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 7 | — |
| NLP | 1 | — |
| LIMIT | 2 | — |
| DETERMINISM | 1 | — |

### Issues by severity

| # | Severity | One-line headline |
|---|----------|-------------------|
| 1 | WRONG/LIMIT | CLI has no working reset: `reset`/`clear`/`forget f`/`undefine`/`del`/`forget everything` all leave definitions in `funcs` |
| 2 | WRONG | Only `session reset` clears fully; `assume clear`, English `forget everything`, and a second `initialize` leave function/assumption residue |
| 3 | WRONG | A second `initialize` leaks functions and assumptions across "sessions" |
| 4 | WRONG | English `assume` store is invisible to `state`, and a stale English meaning overrides a newer JSON assumption (wrong `log` answer) |
| 5 | WRONG | A failed `basis ... cost 3` definition (`ok:false`) still registers a phantom entry in `state.bases` |
| 6 | WRONG | `state()` hides `_`-prefixed but callable functions; `funcs` lists builtin-named defs that calls do not resolve to; user `_` silently clobbered (14→140) |
| 7 | NLP/WRONG | English `its` binds to the last *defined* function, not the one just evaluated (`range beta` after `alpha(5)`) |
| 8 | LIMIT | `--json cmd:state` omits the empty `assumptions` key that MCP `session state` always reports |
| 9 | DETERMINISM | 1/14 runs of a 1200-reset batch truncated the reply stream mid-JSON and dropped 221 replies with exit 0 (non-repro; no golden kept) |


## Takeaway
`session reset` is the only complete clear in the JSON/MCP frontends, while the CLI has none; every other "clear" (English `forget everything`, `session assume clear`, a second `initialize`) has partial or zero reach, and several introspection surfaces disagree with evaluation.

### Original takeaway (verbatim)

`session reset` is the only complete clear in the JSON/MCP frontends, while the CLI has none;
every other "clear" (English `forget everything`, `session assume clear`, a second `initialize`)
has partial or zero reach, and several introspection surfaces disagree with evaluation.
