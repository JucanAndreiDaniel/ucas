# SUMMARY — `sat_ranges_where`

## Counts
- Distinct expressions/queries tried: 190
- Goldens written: 8
- Files created: 7

### Counts

- **Distinct statements / queries tried:** 190
  - 178 ucas lines in 7 CLI probe/golden files (definitions + `equiv` / `range` /
    `domain` / `find` / `gates` / `show` commands), plus ~20 one-off exploratory
    probes (SAT paths, 2^22 boundary, huge tables, mismatch-of-domains cases).
  - 12 MCP JSON-RPC tool calls in `mcp_sat_ranges_where.jsonl`
    (`ucas` define batch; `analyze` `equiv`, `domain`, `range`, `gates`, `show`;
    plus the rejected `differ` op).
- **Files written:** 7 CLI `.ucas` + 7 matching `.out`, 1 `.jsonl` + 1 `.out` MCP golden,
  `FINDINGS.md`, `SUMMARY.md` (17 deliverable files); plus a scratch probe directory
  used only during exploration and removed afterwards.
- **Issues by severity:** WRONG 2 (same root cause: `equiv` ignores G's `where`
  clause / declared range when checking definedness), LIMIT 4 (`differ` op missing;
  `gates` uses type width not narrowed range; table cap 1024; sampled `range` headline
  is not a sound bound). CRASH 0, HANG 0, NLP 0, DETERMINISM 0.
- All goldens: exit 0, run twice with identical output, each well under 1.5 s
  (max ~1.35 s for the SAT/`find` files), bounded by `timeout 30`.

### Golden inventory

| File | Topic |
|------|-------|
| `01_subrange_equiv.ucas/.out` | equivalences holding only on a sub-range; where narrowing |
| `02_tables_match.ucas/.out` | 16/64/256-entry tables, duplicate/overlapping/partial match arms, index definedness |
| `03_where_narrowing.ucas/.out` | conjunctions, disjunctions, `{…}` value sets, bindings, empty domains |
| `04_signed_boundaries.ucas/.out` | signed negative ranges, type boundaries, 2^22 enumeration cap |
| `05_sat_paths.ucas/.out` | SAT proofs/counterexamples, where clauses and division on large domains |
| `06_multiparam_uniform.ucas/.out` | multi-param ranges, cross-param where, uniform params, `find` |
| `07_equiv_domain_bug.ucas/.out` | WRONG reproducer (captures current buggy answers; see FINDINGS.md) |
| `mcp_sat_ranges_where.jsonl/.out` | MCP golden: `equiv`/`domain`/`range`/`gates`/`show`, rejected `differ` |


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 4 | — |

## Takeaway
The SAT/equivalence machinery is solid on narrowed domains — SAT witnesses and proofs are deterministic and where-clause narrowing is correct — but `equiv` is unsound when the *second* function is restricted by a `where` clause or a narrower range: it evaluates G's body outside G's domain and reports "equal" instead of "G undefined".

### Original takeaway (verbatim)

The SAT/equivalence machinery is solid on narrowed domains — SAT witnesses and proofs
are deterministic and where-clause narrowing is correct — but `equiv` is unsound when
the *second* function is restricted by a `where` clause or a narrower range: it
evaluates G's body outside G's domain and reports "equal" instead of "G undefined".
