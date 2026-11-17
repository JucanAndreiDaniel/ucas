# Canonical spec for `tests/stress/`

This file and `README.md` describe the suite. The `stress-test` target in the Makefile sets the rules that a program checks. Everything else is a convention that the Makefile does not check.

## 1. Layout

```
tests/stress/
  SPEC.md  README.md  MASTER_FINDINGS.md  AREAS.md
  docs/   research notes
  areas/<domain>/<area>/
    NN_<topic>.ucas  NN_<topic>.out
    mcp_<topic>.jsonl  mcp_<topic>.out  (optional mcp_<topic>.flags)
    json_<topic>.jsonl json_<topic>.out
    FINDINGS.md  SUMMARY.md
    <fixture files>
```

Domains: `sat`, `math`, `frontend`, `systems`, `nlp`, `float`, `gpu`.

## 2. Rules the runner checks

### Golden pairs

The runner discovers a golden only when the input and the `.out` file share a name. The runner skips an input with no `.out`. The runner ignores a `.out` with no input.

### Invocation and environment

One invocation per golden type. Run from the area directory. The runner exports `UCAS_NO_TIMES=1` and `UCAS_SPIRV_CROSS=none`.

| kind | command |
|---|---|
| CLI | `ucas NAME.ucas` |
| JSON | `ucas --json --files none < NAME.jsonl` |
| MCP | `ucas --mcp $(cat NAME.flags) < NAME.jsonl` |

`json_*` inputs use the JSON frontend. Other `.jsonl` inputs use MCP. The runner never derives a command from output bytes.

### Language boundary

`bin/` holds POSIX shell only. `run.sh` checks goldens. It does not run area-local scripts. Area helpers are Python research tools. The runner treats them as manual tools, not tests.

## 3. Conventions (not checked)

The runner does not check the rules in this section.

- CLI goldens use `NN_<topic>` names. `NN` is a 2-digit ordinal. Convention, not checked.
- `mcp_<topic>.jsonl` starts with an `initialize` request line. Convention, not checked.
- `FINDINGS.md` uses the Summary, Findings and Checks that passed headings. Convention, not checked.
- `SUMMARY.md` uses the Counts, Issues by severity and Takeaway headings. Convention, not checked.
- The severity vocabulary is `CRASH`, `HANG`, `WRONG`, `NLP`, `LIMIT`, `DETERMINISM`. Convention, not checked.
- A golden produces byte-identical output on two runs under the canonical environment. Convention, not checked.
- Nondeterministic reproducers have no `.out` file. Document them in `FINDINGS.md` only. Convention, not checked.
- Use no absolute machine paths in scripts, docs, goldens or fixtures. Convention, not checked.
- Keep an empty directory with a `.keep` file when Git must track it. Convention, not checked.
- Do not commit a `node_modules` symlink farm. Convention, not checked.
