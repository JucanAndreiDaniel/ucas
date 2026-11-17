# SUMMARY — `algebra_ring_ff`

## Counts
- Distinct expressions/queries tried: 330
- Goldens written: 19
- Files created: 19

### Counts

* **Distinct expressions / queries tried:** ~330
  * ~164 MCP tool calls committed in golden `.jsonl` files (24 algebra + 35 rings-number +
    22 rings-structures + 17 GF-polynomial + 29 abstract-algebra + 17 perm/Groebner +
    14 elliptic + 4 primroot-wrong + 4 flat-mode).
  * ~150+ additional discovery calls via the `tools.ucas.*` MCP client and CLI probes
    (factorization, gcd/lcm/resultant/discriminant/division, solve, all `rings` ops,
    `snf`/`hnf`/abelian/perm/Groebner ops, elliptic/`elliptic_ff`, determinism and hang sweeps).
* **Golden files written:** 19
  * 9 MCP `.jsonl` + 9 `.out` (`mcp_algebra`, `mcp_rings_number`, `mcp_rings_structures`,
    `mcp_gf_poly`, `mcp_abstract`, `mcp_perm_groebner`, `mcp_elliptic`, `mcp_primroot_wrong`,
    `mcp_flat`) plus `mcp_flat.flags`.
  * 5 CLI `.ucas` + 5 `.out` (`01_algebra_cli` … `05_elliptic_cli`).
  * `FINDINGS.md`, `SUMMARY.md`.
* **Issues by severity:**
  * WRONG: 1 (`primroot` argument swap; two concrete false verdicts)
  * HANG: 2 (`permgroup S≥50`/S1000; `ring Z/1000000007`), both of which also take down the
    MCP server process and kill the session
  * CRASH: reported as the MCP-server consequence of the two HANGs (not a separate standalone
    crash)
  * DETERMINISM: 0
  * NLP / LIMIT: 0 (one flat-mode argument-shape note, not a bug)

### Folder-scope confirmation

All files created live only under `tests/stress/areas/math/algebra_ring_ff/` (including the scratch
`.work/` directory). No source file, Makefile, existing test, `opencode.json`, or another
subagent's folder was touched; no `make`, `git`, or commit was run.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 2 | — |
| WRONG | 1 | — |

## Takeaway
The exact-algebra core is sound and deterministic across ~330 probes (certificates checked, edge cases n=0/1/non-fields/char-2/huge-primes handled cleanly), but the MCP `primroot` wrapper swaps its `a`/`n` arguments and returns wrong yes/no answers, and two summary ops (`permgroup S1000`, `ring Z/1000000007`) hang forever and kill the MCP server — so a session must never issue them.

### Original takeaway (verbatim)

The exact-algebra core is sound and deterministic across ~330 probes (certificates checked, edge
cases n=0/1/non-fields/char-2/huge-primes handled cleanly), but the MCP `primroot` wrapper swaps
its `a`/`n` arguments and returns wrong yes/no answers, and two summary ops (`permgroup S1000`,
`ring Z/1000000007`) hang forever and kill the MCP server — so a session must never issue them.
