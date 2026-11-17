# SUMMARY — `nlp_ambiguity`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 9
- Files created: 20

### Coverage

- **180 distinct English queries** in the CLI corpus (`/tmp/opencode/corpus.txt`),
  covering every focus word: odd/even, sign, range, square, root, log,
  sin/cos, complex z, byte/char/int/integer/word/N-bit, bit, min/max,
  integral/antiderivative, product, sum, period, order, degree, mod, power,
  absolute value, pi, e, i, infinity, overflow, table, fast/cheap, proof, plus
  scope ("of") and misspelling cases. Each run under `timeout 15`; all exited 0.
- **~40 additional targeted CLI queries** (word/type phrasings, note checks,
  Unicode, ambiguity cascades).
- **~170 MCP `english` calls** across exploration, ambiguity-answer matrices,
  adversarial fuzz (empty/emoji/long/Greek/bad `assume` values), and the two
  JSONL goldens. For each ambiguity key, both the default and the non-default
  reading were answered with `args.assume.KEY` (by index and by name) and the
  resulting `statements`/notes recorded.

Total: **~390 query invocations**, all bounded by `timeout`.

### Files created (20)

CLI goldens (`.ucas` + `.out`, all double-run diffed = deterministic):

- `01_odd_even.ucas/.out`
- `02_log_sqrt.ucas/.out`
- `03_types.ucas/.out`
- `04_scope_juxtaposition.ucas/.out`
- `05_complex_andor.ucas/.out`
- `06_it_juxtaposition.ucas/.out`
- `07_more_keys.ucas/.out`

MCP goldens (`.jsonl` + `.out`, all double-run diffed = deterministic):

- `mcp_ambiguity_answers.jsonl/.out` — ambiguity errors plus answers using each
  reading (odd/even, log, byte, sqrt), including cascaded `untyped` ambiguities
  and `defaults:true` comparisons.
- `mcp_ambiguity_juxtaposition.jsonl/.out` — spelling, juxtaposition, z, andor,
  and multi-ambiguity cases with per-reading answers.

Docs: `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | 7/8 of 64 → 7/(512(of)); emoji input → raw 0xf0 in MCP JSON |
| NLP | 5 | wrap of/make it faster → of/it; wrong juxtaposition readings; only first ambiguity reported; modular inverse default breaks parse; even-hint |
| LIMIT | 2 | w is a word not understood; misc words silently become variables |

### Issues by severity

| Severity | Count | Short reproducer |
|----------|-------|------------------|
| CRASH | 0 | — |
| HANG | 0 | — |
| DETERMINISM | 0 | — |
| WRONG | 2 | `7/8 of 64` → `7/(512(o*f))`; emoji input → raw 0xf0 in MCP JSON |
| NLP | 5 | `wrap of`/`make it faster` → `o*f`/`i*t`; wrong juxtaposition readings; only first ambiguity reported; `modular inverse` default breaks parse; even-hint says "odd" |
| LIMIT | 2 | `w is a word` not understood; misc words silently become variables |


## Takeaway
The ambiguity *machinery* is mostly sound: CLI default notes match MCP default readings across all documented keys, and `args.assume.KEY` selects each reading as advertised.

### Original takeaway (verbatim)

The ambiguity *machinery* is mostly sound: CLI default notes match MCP default
readings across all documented keys, and `args.assume.KEY` selects each reading
as advertised. The damage is in the English lexer/pragmatics: high-frequency
function words ("of", "it") and several ordinary words silently turn into
variable products or bare variables, the MCP `juxtaposition` readings omit the
intended reading, secondary ambiguities in one sentence are hidden, the
odd/even hint is hardcoded to "odd", and non-ASCII input can corrupt the JSON
wire format with an invalid UTF-8 byte.

Confinement: all created files live under `tests/stress/areas/nlp/nlp_ambiguity/`.
