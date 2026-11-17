# SUMMARY — `undefined_propagation`

## Counts
- Distinct expressions/queries tried: 850
- Goldens written: 17
- Files created: 46

### Coverage

- **Distinct expressions/queries tried: ≈ 850**
  - `probe.py`: 94 curated definitions × 4 analyses (`domain`, `range`, `wrap`, `crit`).
  - `probe2.py`: 39 focused cases (direct evaluation, `equiv` around undefined points,
    NaN-bit equiv, `wrap`, adversarial nested/undefined power cases).
  - `sweep.py`: **718** combinatorial expressions (22 real cores × 24 wrappers,
    9 integer cores × 24 wrappers, 5 signalling-NaN bit patterns), each with
    `domain` + `range` under a 15 s timeout. Audit: `sweep_audit.txt` →
    `TOTAL EXPRESSIONS: 718`, `EXIT COUNTS: {0: 718}`, `BAD: 0` (no crash, no hang).
- **Files created: 46**
  - 17 CLI golden pairs `NN_*.ucas` + `NN_*.out`
  - 2 MCP golden pairs `mcp_undefined.{jsonl,out}`, `mcp_flat.{jsonl,flags,out}`
  - `FINDINGS.md`, `SUMMARY.md`, `gen_goldens.sh`, `probe.py`, `probe2.py`,
    `sweep.py`, `sweep_audit.txt`
- All goldens regenerated and verified twice with `sh gen_goldens.sh` →
  `ALL GOLDENS DETERMINISTIC`; all runs bounded by `timeout 30` (binary) /
  `timeout 15` (sweep).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | domain↔range contradiction on NaN results; dead-branch conditions leak into requires; undefined collapsed to 0/1 by direct evaluation; bogus |
| NLP | 1 | parse error silently defaults a failed definition to a free real parameter and yields bogus domain/range |
| LIMIT | 2 | equiv nanbits on signalling-NaN arithmetic stays sampled (“counterexample did not reproduce”); wrap prints an empty e.g.  witness |

### Issues by severity

| Severity | Count | Short description |
|---|---|---|
| CRASH / HANG | 0 | 718-expression sweep and all curated probes returned exit 0 |
| WRONG | 4 | domain↔range contradiction on NaN results; dead-branch conditions leak into `requires`; undefined collapsed to 0/1 by direct evaluation; bogus “correctly rounded” `wrap` claim on NaN |
| NLP | 1 | parse error silently defaults a failed definition to a free real parameter and yields bogus domain/range |
| LIMIT | 2 | `equiv nanbits` on signalling-NaN arithmetic stays sampled (“counterexample did not reproduce”); `wrap` prints an empty `e.g. ` witness |
| DETERMINISM | 0 | every golden was byte-identical across two runs |


## Takeaway
The evaluator does flag most undefined subexpressions and honours dead `?:` / short-circuited `&&` branches at the numeric level, but the *symbolic* metadata is unsound: `domain`'s `requires` list unions conditions from branches that are never taken (sometimes producing contradictory conditions), and NaN results are counted as defined by `domain` yet “undefined everywhere” by `range`.

### Original takeaway (verbatim)

The evaluator does flag most undefined subexpressions and honours dead `?:` /
short-circuited `&&` branches at the numeric level, but the *symbolic* metadata is
unsound: `domain`'s `requires` list unions conditions from branches that are never
taken (sometimes producing contradictory conditions), and NaN results are counted
as defined by `domain` yet “undefined everywhere” by `range`.  Direct evaluation
additionally collapses undefined real subexpressions into ordinary `0`/`1` values,
so “undefined” is not propagated consistently across the tool's interfaces.
