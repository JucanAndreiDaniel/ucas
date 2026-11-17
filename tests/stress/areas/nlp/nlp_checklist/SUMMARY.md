# SUMMARY — `nlp_checklist`

## Counts
- Distinct expressions/queries tried: 207
- Goldens written: 12
- Files created: not recorded

### Original preamble

CheckList-style testing (MFT / DIR / INV) of the ucas English frontend, per
RESEARCH.md §6.  All work is confined to `tests/stress/areas/nlp/nlp_checklist/`.

### Counts

| Item | Count |
|---|---|
| Distinct English queries tried | **207** |
| MFT queries (18 supported intents + state/table) | 20 |
| DIR queries (range narrowing / domain narrowing / cheapest-cost) | 19 |
| INV queries (synonyms / politeness / case+punct / word order / negation) | 168 |
| CLI golden files (`.ucas` + `.out`) | 3 |
| MCP golden files (`.jsonl` + `.out`) | 9 |
| Total golden files (`.out`) | 12 |
| Issues found | 7 |
| — `WRONG` | 1 (F1: negation "unequal" read as "equal", answer not flipped) |
| — `NLP` | 3 (F2 negation phrasings, F4 all-caps var rename, F7 `understood:false` with valid result) |
| — `DETERMINISM` | 1 (F3: MCP `english` response shape flips when `tmpfile()` capture fails) |
| — `LIMIT` | 2 (F5 word order / comma rejected, F6 unsupported synonyms & best-constant) |
| — `CRASH` / `HANG` | 0 |
| Crashes / hangs / nonzero exits | 0 (all files exit 0 under `timeout 30`) |

### Files

- `01_mft_core.ucas` / `.out` — minimal English phrase per supported intent (CLI).
- `02_dir_range.ucas` / `.out` — range-narrowing pairs (CLI).
- `03_inv_cli.ucas` / `.out` — invariance + negation pairs (CLI).
- `mcp_mft.jsonl` / `.out` — MFT via MCP `english` (all intents).
- `mcp_dir_range.jsonl` / `.out` — DIR sampled-point-count pairs.
- `mcp_dir_domain.jsonl` / `.out` — DIR where-condition / domain pairs.
- `mcp_dir_cost.jsonl` / `.out` — DIR cost / cheapest pairs.
- `mcp_inv_syn.jsonl` / `.out` — INV synonyms.
- `mcp_inv_polite.jsonl` / `.out` — INV politeness ("please", "could you", ...).
- `mcp_inv_casepunct.jsonl` / `.out` — INV capitalization, whitespace, punctuation.
- `mcp_inv_wordorder.jsonl` / `.out` — INV alternative word order.
- `mcp_inv_negation.jsonl` / `.out` — negation pairs.
- `FINDINGS.md`, `SUMMARY.md`.

Every `.jsonl` begins with `initialize` + `notifications/initialized` and uses
unique ids. All `.out` files were produced with the canonical commands in `SPEC.md`
(CLI: `ucas NAME.ucas`; MCP: `ucas --mcp < NAME.jsonl`) and verified by running
twice and diffing.

### Note for the orchestrator (cross-area)

MCP `english` goldens are sensitive to `/tmp` capacity: `cap_begin()` uses
`tmpfile()` and, on failure, silently drops `statements` / flips `understood` to
false (F3). Other areas that keep `english` goldens should re-generate them in a
healthy-`/tmp` window and double-check that `statements` is non-empty before
committing.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| NLP | 3 | — |
| LIMIT | 2 | — |
| DETERMINISM | 1 | — |

## Takeaway
The frontend handles all 18 intents and the DIR/INV synonym families well, but **negation is unsound** — "unequal" is silently read as "equal" so the `equiv` answer is not flipped (F1) — and standard negated-equivalence phrasings are not understood at all (F2); additionally the MCP `english` typed response is not deterministic when stdout capture fails (F3).

### Original takeaway (verbatim)

The frontend handles all 18 intents and the DIR/INV synonym families well, but
**negation is unsound** — "unequal" is silently read as "equal" so the `equiv`
answer is not flipped (F1) — and standard negated-equivalence phrasings are not
understood at all (F2); additionally the MCP `english` typed response is not
deterministic when stdout capture fails (F3).
