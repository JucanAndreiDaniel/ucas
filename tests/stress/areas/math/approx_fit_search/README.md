# Stress area: numeric approximation machinery

Covers `approx`, `approx more`, `error`, `fit`, `find`, `stoke`, `adamfit`,
numeric search seeds, magic-constant fitting and the NLP front-end for these ops.

- `NN_*.ucas` / `NN_*.out` — CLI goldens (deterministic, bounded runs).
- `mcp_*.jsonl` / `mcp_*.out` — MCP (JSON-RPC over stdio) goldens.
- `FINDINGS.md` — every issue found, with copy-pasteable reproducers.
- `SUMMARY.md` — counts and takeaway.

All reproducers use `$ROOT/ucas` and are bounded with `timeout`.
