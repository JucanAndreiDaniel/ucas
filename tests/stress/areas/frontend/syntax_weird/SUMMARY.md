# SUMMARY — `syntax_weird`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 12
- Files created: 22

### Counts

- Distinct expressions/queries in durable goldens: **169**
  - 158 CLI statements across 11 `.ucas` files, plus 11 MCP `tools/call`s in `mcp_syntax.jsonl`.
  - ~50 additional exploratory probes were run via stdin/wire while hunting; not saved as goldens.
- Files written (22):
  - CLI goldens: `01_chained`, `02_unicode`, `03_implicit`, `04_mod_logical`,
    `05_ternary`, `06_match`, `07_tables`, `08_where`, `09_semicom`, `10_cmds`,
    `11_prec` (each `.ucas` + `.out`).
  - MCP golden: `mcp_syntax.jsonl` + `mcp_syntax.out`
    (`initialize`, `notifications/initialized`, then `analyze.parse` × 8,
    `analyze.show` × 1, `ucas` raw-source × 2).
  - Reports: `FINDINGS.md`, `SUMMARY.md`.
- Issues by severity: **WRONG 1** (with 4 concrete misparses), **LIMIT 9**,
  **CRASH 0**, **HANG 0**, **DETERMINISM 0**, **NLP 0**.
- All 12 goldens were generated from this directory with the canonical
  commands (`timeout 30 $ROOT/ucas NAME.ucas > NAME.out 2>&1`
  and `timeout 30 ... --mcp < mcp_syntax.jsonl > mcp_syntax.out 2>&1`), all
  exited 0, contain no `error:` lines, and were confirmed byte-identical on a
  second run.

### Coverage

Chained comparisons (incl. mixed operators and `=`), Unicode (`⊕`, `°`, `²`,
`³`, `π`, `≤`, `≥`, `≠`, `×`, `−`, `√`; rejected `∞`/`τ`/`⁴` documented),
implicit multiplication, `mod` vs `%`, `and`/`or`/`not` vs `&&`/`||`/`!`,
deeply nested `?:`, `match` (duplicate/overlapping arms, alternation, ranges,
default, separators, trailing comma) and piecewise guards, mixed-type and
nested tables with indexing, single/double `where` plus value-list narrowing,
semicolon blocks and `#`/`//` comments, odd comment placement, power/unary
precedence, `x in a..b`, and `range`/`equiv`/`find` plus MCP `analyze`/`ucas`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| LIMIT | 9 | — |

## Takeaway
The parser handles most exotic syntax and all goldens are stable, but an inline annotation at the head of a bare command expression is silently multiplied into (or made the scrutinee of) the body — producing genuinely wrong functions — and a cluster of otherwise-valid forms (`!` leading, `∞`, variable-first nested-table indexing, open `in` bounds, table trailing comma, match guards) are rejected as parse errors.

### Original takeaway (verbatim)

The parser handles most exotic syntax and all goldens are stable, but an
inline annotation at the head of a bare command expression is silently
multiplied into (or made the scrutinee of) the body — producing genuinely
wrong functions — and a cluster of otherwise-valid forms (`!` leading,
`∞`, variable-first nested-table indexing, open `in` bounds, table trailing
comma, match guards) are rejected as parse errors.
