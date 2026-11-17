# SUMMARY — `dd_diff_isolation`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 9
- Files created: not recorded

### Original preamble

Generalized delta debugging on pairs of ucas inputs (one correct, one buggy). Implemented
in `dd.py`: token-level diff → subset testing with the ucas CLI as oracle → 1-minimal
set of edits that flips PASS→FAIL. Covers the 5 requested bug classes plus a bug-mutation
experiment.

### Counts

- **Distinct pass/fail pairs tried: 247** (all valid; 0 skipped).
  - `equiv_where / narrow_bound`: 64
  - `equiv_where / body_coincide`: 40
  - `equiv_cast / result_coercion`: 39
  - `english_of / fraction_please`: 32
  - `equiv_signed / reinterpret`: 28
  - `conflation / undefined_name`: 16
  - `nesting_crash / paren_depth`: 16
  - `english_of / command_the`: 12
- Oracle subprocess calls (cached by candidate text): **1136**.
- Bug classes covered: 5 requested (true/false `equiv`, narrowed/un-narrowed `where`,
  parsed/misparsed English query, signed/unsigned variant, crashing/non-crashing nesting
  depth) + 1 mutation class (undefined function name).
- Files created: `dd.py`, `README.md`, `FINDINGS.md`, `SUMMARY.md`, `analysis.md`,
  `results.jsonl`, `mutations.jsonl`, 9 golden pairs (`NN_*.ucas` + `NN_*.out`).
- Issues by severity (per FINDINGS.md): WRONG 3 (§1 cluster, §2, §5 mutation),
  NLP 1 (§3, two sub-variants), CRASH 1 (§4), LIMIT 2 (§6, §5 conflation),
  DETERMINISM 1 (§7, crash boundary at depth 1525).
- Determinism: all 9 goldens generated twice and `diff`ed identically; no nondeterministic
  case kept as a golden. Crash documented in FINDINGS.md only, not as a `.out`.
  All dd classes except `nesting_crash` reproduce byte-identically; the crash class
  varies ±1 token because the binary's depth-1525 crash boundary is itself
  nondeterministic (§7).

### Reproduce

```sh
cd $ROOT/tests/stress/areas/sat/dd_diff_isolation
python3 dd.py --full            # rewrites results.jsonl, mutations.jsonl, analysis.md
```


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| WRONG | 3 | — |
| NLP | 1 | — |
| LIMIT | 2 | — |
| DETERMINISM | 1 | — |

### Root-cause clustering (headline)

- **107 pairs across 3 seemingly different findings** (`equiv` cast coercion,
  `equiv` signed↔unsigned reinterpretation, `equiv` where-body coincidence) reduce to
  the **same one-token cause**: delete the additive offset `+N` in G's body. These are
  one comparison-layer bug, not three.
- 16 pairs of nesting crashes reduce to "insert enough `(` tokens to cross recursion
  depth 1525" — and dd discovers unbalanced `(` crashes at the same depth, so the real
  trigger is open-paren recursion, not balanced nesting.

### Bug mutation (headline)

- Under a naive verdict-only oracle, 18/18 equiv pairs minimize to deleting a single
  digit and leaving a dangling `+` — a parse error that flips `equiv` to `are equal` via
  the **undefined-function-name** bug. The reduction changes the bug into a different one;
  strict mechanism-aware oracles are required to avoid it.


## Takeaway
Minimal-difference analysis collapses three unsound-`equiv` findings into one comparison bug (`+N` body offset), exposes a strict-vs-verdict oracle trap that mutates bugs, and shows the nesting crash is driven by `(` recursion depth rather than balanced parens — confirming `dd` on pairs as a root-cause clustering tool, not just a minimizer.

### Original takeaway (verbatim)

Minimal-difference analysis collapses three unsound-`equiv` findings into one comparison
bug (`+N` body offset), exposes a strict-vs-verdict oracle trap that mutates bugs, and
shows the nesting crash is driven by `(` recursion depth rather than balanced parens —
confirming `dd` on pairs as a root-cause clustering tool, not just a minimizer.
