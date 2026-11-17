# SUMMARY — `binary_source_unicode`

## Counts
- Distinct expressions/queries tried: ~236
- Goldens written: 14
- Files created: 10

### Scope:
non-ASCII and control bytes in source and English input — NUL bytes,
bidi overrides (U+202E/202A–202D/200E/200F), zero-width (U+200B/200C/200D),
Unicode Tags block (U+E0000–U+E007F), homoglyphs, NFC/NFD + combining marks,
terminal escape sequences, math symbols (≤ vs ∫), invalid UTF-8, across CLI
files, CLI stdin, `--json` source/text and MCP `english`/tool names.

### Counts

- **~236 distinct cases tried**: 172 independent stdin cases (`run_cases.sh`),
  20 focused stdin cases (`run_stdin.sh`), 10 CLI-file goldens, 4 JSONL goldens
  containing 34 MCP/JSON calls.
- **Files created:** 10 `.ucas` + `.out` pairs, 3 `mcp_*.jsonl` + `.out` pairs,
  1 `json_*.jsonl` + `.out` pair, `run_stdin.sh` + `stdin_all.out`,
  `run_cases.sh` + `cases_all.out`, `generate.py`, `generate_cases.py`,
  `make_goldens.sh`, `FINDINGS.md`, `SUMMARY.md`.
- All 14 JSONL/file goldens were run **twice and byte-compared** (`cmp`) before
  being kept; both runner scripts re-verify deterministically (`rc=0`).
  Verified with the exact `run.sh` commands: **all goldens pass, `fail=0`**.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | NUL silently truncates source (file vs stdin vs JSON/MCP differ; fabricated _(sho: real) = sho); invalid UTF-8 lead bytes emitted inside JSO |
| NLP | 3 | control chars in English: CLI echoes raw ESC, JSON/MCP reject |
| LIMIT | 2 | CR (0x0D) acts as a statement separator |

### Issues by severity

| Severity | Count | Summary |
|---|---|---|
| WRONG              | 2 | NUL silently truncates source (file vs stdin vs JSON/MCP differ; fabricated `_(sho: real) = sho`); invalid UTF-8 lead bytes emitted inside JSON/MCP replies |
| NLP                | 2 | bidi/format controls echoed raw into diagnostics (Trojan-Source display confusion); math-symbol normalization asymmetric across symbols/frontends |
| NLP/LIMIT          | 1 | control chars in English: CLI echoes raw ESC, JSON/MCP reject |
| LIMIT              | 1 | CR (0x0D) acts as a statement separator |
| CRASH / HANG       | 0 | none found; combining-mark bombs (5k/20k) and invalid UTF-8 handled gracefully |


## Takeaway
The binary **never crashes or hangs** on binary/Unicode input, but a single NUL byte silently rewrites or drops statements (differently in each frontend), and the English error path truncates multi-byte characters to a bare lead byte, making its JSON/MCP replies **invalid UTF-8** and unparseable by strict clients.

### Original takeaway (verbatim)

The binary **never crashes or hangs** on binary/Unicode input, but a single NUL
byte silently rewrites or drops statements (differently in each frontend), and
the English error path truncates multi-byte characters to a bare lead byte,
making its JSON/MCP replies **invalid UTF-8** and unparseable by strict clients.
