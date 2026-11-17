# SUMMARY — `nlp_roundtrip`

## Counts
- Distinct expressions/queries tried: 238
- Goldens written: 7
- Files created: 17

### What was tested
Round-trip integrity between the English frontend and the ucas language. For each
English query the emitted `ucas:` statements were obtained from the `english` MCP tool
(and CLI), then fed into a **fresh** `ucas --mcp` process via the `ucas` tool. Each case
was checked for (a) parse-without-error and (b) answer equality with what the English
frontend printed. `--flat` MCP mode was tested separately.

### Counts
- **English queries tried through the automated fresh-process harness: 238**
  (178 broad + 50 adversarial + 10 validation). Plus ~18 targeted session/assume
  probes and CLI cross-checks.
- Intent coverage: range, wrap/domain, equiv, critical points, derivative/integral,
  sum/product/closed form, find/gates/cost, table, min/max, accuracy, ODE/identify,
  define/assume, numbers/taylor/approx/limits — all represented, with working
  round-trips for each.
- Harness outcome (228 primary+adversarial): **156 OK** (parse + exact answer match),
  **5 answer mismatches** (all lost `note:` lines), **3 front-end-error cases** (the
  emitted statement itself errors), **65 not understood / raw-command passthrough**.
- **Files created: 17** — 7 golden pairs (`.jsonl`/`.ucas` + `.out`), 1 `.flags`,
  `FINDINGS.md`, `SUMMARY.md`.
- All 7 goldens replay byte-identically (verified twice with `diff`) and pass a local
  run of the stress runner logic.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| NLP | 1 | — |
| LIMIT | 2 | — |

### Issues by severity
- **CRASH: 0**
- **HANG: 0**
- **WRONG: 3**
  - emitted `f(3)` re-read as multiplication `f*3` in a fresh process (Finding 1)
  - emitted `range h` yields a different range in a fresh process (Finding 2)
  - emitted statements omit the disambiguation/type the frontend chose, so a different
    legit `assume` silently changes the answer — `keep_ends`, `isqrt`, `untyped` (Finding 3)
- **NLP: 1** — frontend emits statements that its own backend rejects (`find` on a float
  result, `diff` order > 12) (Finding 5)
- **LIMIT: 2** — interpretation `note:` lines dropped on round-trip (Finding 4); many
  phrasings unsupported / raw-command passthrough has no `statements` (Finding 6)
- **DETERMINISM: 0**


## Takeaway
The clean round-trips are genuinely clean, but the English frontend emits **non-self-contained statements**: names/types/disambiguations it resolved from session state or defaults are left out of the `ucas:` text, so re-running that text in a fresh process can silently change the answer (`f(3)` → `3f`, `range h` → sampled range, `approx`/`sqrt`/`untyped` under a different `assume`).

### Original takeaway (verbatim)
The clean round-trips are genuinely clean, but the English frontend emits
**non-self-contained statements**: names/types/disambiguations it resolved from session
state or defaults are left out of the `ucas:` text, so re-running that text in a fresh
process can silently change the answer (`f(3)` → `3f`, `range h` → sampled range,
`approx`/`sqrt`/`untyped` under a different `assume`).
