# Summary — `proof_army`

## Counts

| Kind | Inputs | Goldens |
|------|--------|---------|
| CLI (`NN_*.ucas`) | 2 | 2 |
| MCP (`mcp_*.jsonl`) | 2 | 2 |
| Total | 4 | 4 |

## Issues by severity

* WRONG: 1 (empty counterexample for closed false statements, fixed)
* CRASH: 0
* HANG: 0
* DETERMINISM: 0

## Takeaway

Counterexample reporting in `prove_model.c` assumed every refuted
statement begins with `forall`.  Closed statements (constant equations,
`false`, `prime(4)`) were refuted correctly but printed an empty
`counterexample:` field in both the CLI and MCP output.  The fix emits a
short description when there are no variables to assign; quantified
counterexamples and true statements are unchanged.  Two goldens in
`thesis_mr_mining` recorded the old empty value and need recapture.
