# SUMMARY — `nlp_arith`

## Counts
- Distinct expressions/queries tried: 262
- Goldens written: 10
- Files created: not recorded

### Counts

- **Distinct English queries tried:** 262
  (10 hand-written probe batches, a 151-case adversarial fuzz sweep including a typo sweep
  over every property word, the CLI goldens and the MCP goldens, deduplicated).
- **Adversarial fuzz runs:** 151 separate `timeout 6` CLI processes — 0 crashes, 0 hangs,
  0 nonzero exits, 0 sanitizer/assert messages.
- **Goldens written:** 10 pairs (20 golden files)
  - CLI: `01_typos`, `02_chained`, `03_scope`, `04_properties`, `05_range_table`,
    `06_find`, `07_nested`, `08_always` (`.ucas` + `.out` each).
  - MCP: `mcp_english`, `mcp_properties` (`.jsonl` + `.out` each).
- **Other files:** `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | chained comparisons false for true chains; "always/ever" drops the comparison; x + 1 squared binds to 1 silently |
| NLP | 5 | broken "always odd" hint; unknown word becomes a variable; misplaced type clause changes the analysed function; find 0 -> find 10; "is x eve |
| LIMIT | 2 | variable comparisons only echoed as a bool function; uneven request vocabulary (max/min, which-is-bigger, multi-type clauses, "a few", "ever |
| DETERMINISM | 1 | one unconfirmed anomalous/empty MCP stdout, not reproducible in 20 reruns (no golden kept from it) |

### Issues by severity

| Severity | Count | Titles |
|---|---|---|
| WRONG | 3 | chained comparisons false for true chains; "always/ever" drops the comparison; `x + 1 squared` binds to `1` silently |
| NLP | 5 | broken "always odd" hint; unknown word becomes a variable; misplaced type clause changes the analysed function; `find 0` -> `find 10`; "is x even?" answered as "odd" |
| LIMIT | 2 | variable comparisons only echoed as a bool function; uneven request vocabulary (max/min, which-is-bigger, multi-type clauses, "a few", "everywhere") |
| DETERMINISM | 1 | one unconfirmed anomalous/empty MCP stdout, not reproducible in 20 reruns (no golden kept from it) |
| CRASH | 0 | — |
| HANG | 0 | — |

### Determinism

Every kept golden was generated twice and `diff`ed (identical).  `mcp_english.jsonl` was
additionally rerun 20 times: all 20 outputs byte-identical (8791 bytes).  The five focus
misspellings (`comutative`, `asociative`, `add ivite`, `monotonik`, `injctive`) are all
corrected with a note; no crash/hang was found.


## Takeaway
The English frontend is robust against crashes but semantically unsound on comparisons: chained comparisons and the quantifier words "always"/"ever" silently produce the wrong function or the wrong boolean, and the narrow scope of a trailing "squared" is applied without warning.

### Original takeaway (verbatim)

The English frontend is robust against crashes but semantically unsound on comparisons:
chained comparisons and the quantifier words "always"/"ever" silently produce the wrong
function or the wrong boolean, and the narrow scope of a trailing "squared" is applied
without warning.

### Folder confirmation

All files were created only under `tests/stress/areas/nlp/nlp_arith/`.  Scratch/fuzz scripts were kept
in `/tmp/opencode/` and are not part of the deliverable.  No source file, Makefile, test, or
`opencode.json` was edited; no build, git command, or commit was run.
