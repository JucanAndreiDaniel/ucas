# SUMMARY — `resource_limits`

## Counts
- Distinct expressions/queries tried: ~900
- Goldens written: 17
- Files created: 15

### Original preamble

**Focus:** memory / stack / domain exhaustion (not timeouts).

### Counts

- **~900 distinct expressions / queries tried** across ~126 generated input files
  (CLI `.ucas` probes, MCP JSONL calls, and one-line threshold probes), covering:
  - enumeration-cap boundaries (u21/u22/u23; 2^21–2^23-point domains, exact point counts);
  - tables / list literals from 100 to 100000 entries and the 1024-entry cap;
  - deeply nested parentheses, unary minus, calls, conversions, indexing and `|...|` from 100 to 100000 levels;
  - `where` chains up to 5000 conjuncts, nested-paren where conditions, and `x in {...}` lists up to 1000 values;
  - huge integers (2^63, 2^64−1, 2^64, 2^100000), big products/powers and symbolic powers;
  - algebra/series depth (`expand (1+x)^n` up to 5000, `taylor` orders up to 1000);
  - 100–20000 definitions in one session; `match`/piecewise arms up to 20000;
  - wide `equiv` proofs (u32/u64 algebra, u22 exhaustive), many-parameter domains, and
    parallel-ish batches of `find` / `approx` / `stoke` searches;
  - memory caps via `ulimit -v` from 10 MB to 2 GB.
- **17 golden files written:** 15 CLI (`NN_*.ucas` + `.out`) and 2 MCP
  (`mcp_resource_limits.*`, `mcp_limits_errors.*`). Plus `FINDINGS.md` and this `SUMMARY.md`.
- **Issues by severity:** 7 CRASH (all SIGSEGV / stack-overflow class), 0 HANG, 0 WRONG,
  0 NLP, 6 LIMIT, 0 DETERMINISM.
- Every golden was run twice and byte-compared; all deterministic.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 7 | — |
| LIMIT | 6 | — |

## Takeaway
The evaluator handles large *data* (millions of enumerated points, 20k definitions, 100k-entry text, multi-search batches) fluently and reports OOM cleanly, but the **parser crashes with SIGSEGV once expression nesting passes roughly 1000–1500 levels** (parentheses, unary minus, calls, conversions, index chains and `|...|` bars); MCP isolates these crashes into a single failed call while the CLI dies outright.

### Original takeaway (verbatim)

The evaluator handles large *data* (millions of enumerated points, 20k definitions, 100k-entry
text, multi-search batches) fluently and reports OOM cleanly, but the **parser crashes with
SIGSEGV once expression nesting passes roughly 1000–1500 levels** (parentheses, unary minus,
calls, conversions, index chains and `|...|` bars); MCP isolates these crashes into a single
failed call while the CLI dies outright. Several hard, mostly graceful ceilings were also
mapped: tables 1024, `in`-lists 128, `match`/piecewise 255, `taylor` order 12, and a silent
no-op for `expand` above degree 64.
