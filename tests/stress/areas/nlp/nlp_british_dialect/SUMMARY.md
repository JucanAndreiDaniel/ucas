# SUMMARY — `nlp_british_dialect`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 5
- Files created: not recorded

### Coverage
- **320 distinct English queries** tried in total (168 baseline/variant pairs over a
  236-query systematic comparison set, plus exploratory vocabulary probes and the
  golden-session queries).
- Focus categories: British spellings (29 pairs), keyword misspellings (52),
  number words / billion scale (26), archaic/formal phrasing (18), regional
  synonyms (17), punctuation conventions (26).
- Every query run under `timeout 15`; MCP goldens re-run under `timeout 30`.

### Files written
- `mcp_british_spelling.jsonl` + `.out`
- `mcp_number_words.jsonl` + `.out`
- `mcp_misspellings.jsonl` + `.out`
- `mcp_archaic_regional.jsonl` + `.out`
- `mcp_punctuation.jsonl` + `.out`
- `FINDINGS.md`, `SUMMARY.md`

All five `.out` files were generated twice and verified byte-identical, then a
third run reproduced the checked-in file exactly (deterministic).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| NLP | 7 | — |
| LIMIT | 2 | — |

### Issues by severity
- **CRASH**: 0
- **HANG**: 0
- **WRONG** (unsound / silently wrong translation): 6
  - number-word scale addition bug (`one thousand million` -> `1001000`)
  - `one million million`/`billion billion` addition bug
  - `one billionth` silently read as `1000000000`
  - unknown word silently becomes a variable (`a billion` -> bogus implicit function, `ok:true`)
  - hyphen in `ninety-nine billion` silently read as subtraction
  - `;` after a verb drops the operation (`differentiate; x squared` -> `show it`)
- **NLP**: 7
  - US `factor` routes differently from `factorise`/`factorize`
  - British `analyse` mis-normalised to noun `analysis`
  - inconsistent misspelling coverage (some near-misses work, others fail)
  - archaic/formal phrasing not understood (9+ forms)
  - regional synonyms not understood; `whilst` clause emits a malformed ucas statement
  - punctuation changes translation or breaks parsing (`!`, `,`, `()`, quotes, all-caps)
  - `and` between number words rejected while `plus` works
- **LIMIT**: 2
  - small number-word vocabulary / short-scale billion default; no way to express 10^12
  - control characters in `text` rejected by the tool schema (documented constraint)
- **DETERMINISM**: 0 (all goldens stable)


## Takeaway
The English frontend is surprisingly tolerant of misspellings, but its number-word parser is unsound (multi-scale phrases are summed instead of multiplied, ordinals and articles are silently misread) and unknown words silently become variables with `ok:true` and no emitted statement — so a confident-but-wrong translation is the dominant failure mode, not crashes.

### Original takeaway (verbatim)
The English frontend is surprisingly tolerant of misspellings, but its number-word
parser is unsound (multi-scale phrases are summed instead of multiplied, ordinals
and articles are silently misread) and unknown words silently become variables
with `ok:true` and no emitted statement — so a confident-but-wrong translation is
the dominant failure mode, not crashes.
