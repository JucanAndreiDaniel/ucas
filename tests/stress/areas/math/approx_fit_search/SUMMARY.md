# SUMMARY — `approx_fit_search`

## Counts
- Distinct expressions/queries tried: 208
- Goldens written: 17
- Files created: 17

### Counts

- **Distinct expressions / queries tried: ≈ 208**
  - 110 CLI statements in the 17 golden `.ucas` files
  - 15 MCP `tools/call` invocations across the 3 golden `.jsonl` files
  - ≈ 83 one-off exploratory queries (edge intervals, bad degrees, NaN/inf
    ranges, poles/discontinuities, tolerances, domain mismatches, seeds,
    malformed fit targets, NLP phrasings) run under `timeout 12–30`
- **Golden files written:** 17 CLI pairs (`NN_*.ucas` + `NN_*.out`) and 3 MCP
  pairs (`mcp_*.jsonl` + `mcp_*.out`).  Every pair was generated twice and
  `diff`-identical; all runs exited 0 within 30 s.
- **Support files:** `README.md`, `FINDINGS.md`, `SUMMARY.md`,
  `verify_fit_oracle.py` (exhaustive independent check of the fit constant).
- **No goldens were added for** the default `search anneal` (does not finish in
  30 s), degree 100 (~20–30 s) or `adamfit` (trailing timing line varies);
  these are documented in `FINDINGS.md` only.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 1 | default search anneal emits no candidate table within 30 s |
| WRONG | 3 | fit returns a non-minimax magic constant; error/fit ignore the declared domain; fit accepts an undefined target |
| NLP | 1 | English front-end cannot route "fit the quake constant" / "find the rsqrt bit hack" |
| LIMIT | 3 | degenerate/reversed/negative degree silently reinterpreted; degree-100 search is very slow; MCP approx more / ambiguity handling differs fro |
| DETERMINISM | 1 | adamfit prints a wall-clock time that changes between runs |

### Issues by severity

| Severity | Count | Headline |
|---|---|---|
| WRONG | 3 | `fit` returns a non-minimax magic constant; `error`/`fit` ignore the declared domain; `fit` accepts an undefined target |
| HANG | 1 | default `search anneal` emits no candidate table within 30 s |
| LIMIT | 3 | degenerate/reversed/negative `degree` silently reinterpreted; degree-100 search is very slow; MCP `approx more` / ambiguity handling differs from CLI |
| DETERMINISM | 1 | `adamfit` prints a wall-clock time that changes between runs |
| NLP | 1 | English front-end cannot route "fit the quake constant" / "find the rsqrt bit hack" |

Total distinct issues documented: **9** across 8 `FINDINGS.md` headings
(the "long searches" heading covers both a HANG and a slow-search LIMIT).


## Takeaway
The approximation machinery is deterministic for `approx`, `error`, `fit`, `find` and seeded `stoke`, but its headline numbers are *sampled* and can be plainly wrong: `fit`'s rsqrt magic constant is not the true minimax, `error` measures approximations at points outside their declared domain, and several malformed degree/target arguments are silently accepted rather than rejected.

### Original takeaway (verbatim)

The approximation machinery is deterministic for `approx`, `error`, `fit`,
`find` and seeded `stoke`, but its headline numbers are *sampled* and can be
plainly wrong: `fit`'s rsqrt magic constant is not the true minimax, `error`
measures approximations at points outside their declared domain, and several
malformed degree/target arguments are silently accepted rather than rejected.
