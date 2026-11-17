# SUMMARY — `nlp_numbers`

## Counts
- Distinct expressions/queries tried: 167
- Goldens written: 12
- Files created: 28

### Scope
English number/quantity parsing in both front ends: CLI plain English (stdin /
`.ucas`) and MCP `english`.

### Counts
- **Distinct queries tried: 167** (CLI, `what is …?` form) plus **13 distinct
  MCP `english` texts** (all 13 are a subset of the 167; 14 MCP calls total).
- **CLI queries per topic** (approximate): percentages 12, ordinals 12, spelled
  large numbers 14, fractions 14, decimals/scientific 14, negatives 9,
  hex/binary 12, units 11, Roman numerals 6, mixed/ratios 12, large digit
  strings / widths / overflow 22, adversarial & misc 39.
- **Files created: 28**
  - 12 CLI goldens: `01_percent` … `12_large_digits` (`.ucas` + `.out`)
  - 1 MCP golden: `mcp_english_numbers.jsonl` + `.out`
  - `FINDINGS.md`, `SUMMARY.md`
- **Issues by severity: 13 total**
  - CRASH: 0
  - HANG: 0
  - WRONG: 2 — "trillion" → 10^6; 39-character silent token truncation
  - NLP: 4 — `%` + "of"; "ratio of A to B"; digit mixed numbers; additive
    scale words
  - LIMIT: 7 — spelled decimals; trailing-`b` binary; Roman numerals;
    dB/rad/decibels units; restricted fraction denominators; ordinal words
    past twelfth; silent u64 wraparound
  - DETERMINISM: 0

### Verification
- Every query run under `timeout 12`; every golden and the MCP JSONL under
  `timeout 30`. All exit codes were 0 — no crash, signal, hang or truncated
  output.
- Every golden was generated from its own directory with the canonical command
  (`timeout 30 $ROOT/ucas NAME.ucas > NAME.out 2>&1`) and
  the MCP golden with (`timeout 30 …/ucas --mcp < mcp_english_numbers.jsonl`).
- Every golden was run twice and `diff`ed byte-for-byte: all deterministic.
- MCP JSONL output contains 10 `isError:false` and 4 `isError:true` responses;
  even error responses keep the process exit 0, so the golden is runner-safe.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| NLP | 4 | — |
| LIMIT | 7 | — |

## Takeaway
The English number frontend is broadly correct for ordinary quantities, but silently mis-scales "trillion" and silently truncates any token past 39 characters (turning long literals into wrong-but-valid values); most other gaps are documented limitations of the hand-written phrase tables.

### Original takeaway (verbatim)
The English number frontend is broadly correct for ordinary quantities, but
silently mis-scales "trillion" and silently truncates any token past 39
characters (turning long literals into wrong-but-valid values); most other gaps
are documented limitations of the hand-written phrase tables.
