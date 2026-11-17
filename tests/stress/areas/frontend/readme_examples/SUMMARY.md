# SUMMARY — `readme_examples`

## Counts
- Distinct expressions/queries tried: 150
- Goldens written: 21
- Files created: not recorded

### Coverage

- Sources read in full: `$ROOT/README.md` (~3110 lines),
  `.claude/skills/ucas/SKILL.md`, `.claude/skills/ucas/test.sh`,
  `.claude/skills/ucas/ucas.sh`, plus the exact definitions the README refers
  to (`tests/roundeft.ucas`, `tests/roundchoice.ucas`, `tests/numsearch.ucas`).
- Extracted and executed: every fenced code block / example statement / claimed
  output that carries a command or a result — the tour, language/examples,
  machine-integer and float `equiv` proofs, symbolic algebra, complex/trig and
  hypercomplex, approx/adamfit invocation, all `error` examples, all `find`
  rewrite examples, cost-model and loop-cost examples, dot products, English
  examples, the JSON frontend (requests, response shape, ambiguity, typed
  examples) and the MCP server (handshake, tools, resources, prompts).
- **Distinct expressions/queries tried: ~150** (117 statements across the 19 CLI
  goldens, plus JSON requests, MCP calls and ad-hoc characterization probes).
- Every candidate was bounded with `timeout 15`; the one long search (README
  lines 788–795) was retried at `timeout 30` and still timed out.  Each would-be
  golden was run twice and `diff`ed: all 21 goldens are byte-identical across
  runs, so none were rejected for nondeterminism.

### Files created (all inside `tests/stress/areas/frontend/readme_examples/`)

- 19 CLI goldens `NN_name.ucas` + `NN_name.out` (`01_gates_tour` …
  `19_bases_doc_ellipsis_fail`).  Of these, `17_`, `18_`, `19_` deliberately
  capture *stable error output* for documented commands/blocks that fail; this
  is stated explicitly in FINDINGS.md.
- 2 MCP goldens `mcp_calculus_integrate.jsonl` + `.out` and
  `mcp_equiv_avg.jsonl` + `.out`.
- `FINDINGS.md`, `SUMMARY.md`.

No side-effect files are produced by any golden (no `plot`, `animate`, `mma`,
`texenc`, `spirv_simplify` writer runs).  All runs used the absolute binary
`$ROOT/ucas` from this folder.  No source, Makefile, existing
test or `opencode.json` was touched; no `make`/`git` was run.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 6 | F1 find days lookup cost 9→8; F4 SKILL SAT conflicts 818→833; F5 MCP tools/list ~60/340 KB → 133/509 KB; F6 cost quant 134→190.25; F7 polar  |
| NLP | 1 | F3 is avg comutative? errors unless avg is pre-defined |
| LIMIT | 3 | F2 inline multi-param cost F(...)=... commands error; F9 documented anneal example >30 s; F10 basis block has literal ... placeholders |

### Issues by severity

| severity | count | findings |
|---|---|---|
| WRONG | 6 | F1 `find days` lookup cost 9→8; F4 SKILL SAT conflicts 818→833; F5 MCP `tools/list` ~60/340 KB → 133/509 KB; F6 `cost quant` 134→190.25; F7 `polar` check 4e-16→3e-16; F8 JSON `ucas` echo missing `wrt x` |
| NLP | 1 | F3 `is avg comutative?` errors unless `avg` is pre-defined |
| LIMIT | 3 | F2 inline multi-param `cost F(...)=...` commands error; F9 documented anneal example >30 s; F10 `basis` block has literal `...` placeholders |
| CRASH / HANG / DETERMINISM | 0 | — |

Total findings: **10** (6 WRONG, 1 NLP, 3 LIMIT).  Roughly 6 of the 10 are stale
documentation numbers rather than engine faults; the most substantive defects
are F2 (three documented commands that cannot run as written), F3 (an English
example that fails without hidden session state) and F6 (a 134 → 190.25 cost
claim drift).


## Takeaway
The README/SKILL examples are overwhelmingly accurate and deterministic, but a handful of stale numbers and three non-runnable examples (inline multi-arg `cost`, undefined `avg`, literal `...` in a `basis` block) need documentation fixes.

### Original takeaway (verbatim)

The README/SKILL examples are overwhelmingly accurate and deterministic, but a
handful of stale numbers and three non-runnable examples (inline multi-arg
`cost`, undefined `avg`, literal `...` in a `basis` block) need documentation
fixes.
