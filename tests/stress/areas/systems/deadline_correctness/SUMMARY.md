# SUMMARY — `deadline_correctness`

## Counts

- Goldens in this area: 4 (3 CLI + 1 JSON line file with 2 requests)
- Existing goldens needing recapture: 5 (see FINDINGS.md)
- Source files changed: 3 (`cf_bridge.c`, `mma.c`, `jsonmode.c`)

## Issues by severity

- CRASH: 0
- HANG: 0 (after fix; before: mma 13-17 s, find up to 60 s)
- WRONG: 0
- LIMIT: 2, both honest (mma search budget exhausted; timeout_s expired)
- DETERMINISM: 0 on this host; the mma partial result is wall-clock dependent
  across machines (documented in FINDINGS.md)

## Takeaway

The three budgets now mean what they say: find gets its real CPU share,
mma's two searches share a 3.5 s deadline and say so when cut, and a JSON
reply read cannot outlive `timeout_s`.  The remaining ~4 s of a small-budget
`c optimize` is candidate proof, not the find search this task owned.
