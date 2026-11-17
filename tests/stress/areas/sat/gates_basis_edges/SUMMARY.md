# SUMMARY — `gates_basis_edges`

## Counts
- Distinct expressions/queries tried: ~240
- Goldens written: 14
- Files created: not recorded

### Coverage

* **~240 distinct statements / tool calls** exercised against the prebuilt
  `$ROOT/ucas`, every run bounded by `timeout 15` (25 s for MCP goldens).
* Categories: empty bases; one-gate bases; duplicate gate definitions (same name, different
  body/arity, inherited replacement); gates named after builtins/commands/constants; unknown
  gate symbols and functions; wrong gate arities (0 and 4 inputs); gate cost 0 / negative / huge
  (0…2^64−1, hex forms); inheritance cycles and self-inheritance (regular + LUT); incomplete bases;
  LUT-1/LUT-2/LUT-3 with malformed/impossible table syntax; Unicode gate names; 1000+ gate
  definitions, 1000+ duplicates, 1000+ bases and a 1000-deep inheritance chain; `gates`, `cost`,
  `find … snippets` via CLI, `--mcp`, and `--mcp --flat` (including machine-readable
  `structuredContent` / `proof` fields).
* Exploratory generators are kept in `_scratch/` for reproducibility.

### Files created (deliverables)

* 14 CLI golden pairs (`01_…` … `14_….ucas` + `.out`) — 28 files
* `mcp_basis_edges.jsonl` + `.out`
* `mcp_analyze_cost_find.jsonl` + `.out`
* `mcp_flat_basis.jsonl` + `.out` + `mcp_flat_basis.flags` — flat mode
* `FINDINGS.md`, `SUMMARY.md`
* 17 golden files total (14 CLI + 3 MCP); all run twice and `diff`ed — **all deterministic**.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | uint8 cost truncation (cost 256 → "minimal cost 0", incl. MCP minimal:true); negative cost coerced to 0 with phantom gate |
| NLP | 1 | English number-word basis/model names break CLI gates … basis NAME → "sorry: of what?" (MCP unaffected) |
| LIMIT | 3 | parse error leaves half-defined basis (lut 255); non-LUT cost n unparsed; cost-0 "minimal: cost 0, 230 steps" with vacuous proof |

### Issues by severity

| Severity | Count | Short description |
|---|---|---|
| CRASH | 0 | none (including 1000+ definition files) |
| HANG | 0 | none |
| WRONG | 2 | uint8 cost truncation (`cost 256` → "minimal cost 0", incl. MCP `minimal:true`); negative cost coerced to 0 with phantom gate |
| NLP | 1 | English number-word basis/model names break CLI `gates … basis NAME` → "sorry: of what?" (MCP unaffected) |
| LIMIT | 3 | parse error leaves half-defined basis (`lut 255`); non-LUT `cost n` unparsed; cost-0 "minimal: cost 0, 230 steps" with vacuous proof |

(The two STATE-flavoured wrong answers — negative cost and `lut 255` — are grouped with their
primary WRONG/LIMIT entry above; 6 distinct findings in total.)


## Takeaway
Gate-base handling never crashes, but it silently truncates declared costs to 8 bits (turning `cost 256` into a machine-readable `minimal:true, cost:0` proof), commits gates from rejected definitions, and lets English number-word basis names hijack CLI commands — so gate-cost and minimality results on custom bases cannot be trusted.

### Original takeaway (verbatim)

Gate-base handling never crashes, but it silently truncates declared costs to 8 bits (turning
`cost 256` into a machine-readable `minimal:true, cost:0` proof), commits gates from rejected
definitions, and lets English number-word basis names hijack CLI commands — so gate-cost and
minimality results on custom bases cannot be trusted.
