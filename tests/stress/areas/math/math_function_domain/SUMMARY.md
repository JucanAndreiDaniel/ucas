# SUMMARY — `math_function_domain`

## Counts
- Distinct expressions/queries tried: 236
- Goldens written: 24
- Files created: 24

### Counts

- Distinct expressions / queries tried: **236** (207 CLI statements in `.ucas` files + 29 MCP `tools/call` calls in `.jsonl` files).
- Golden files written: **24 `.out`** files paired with **20 `NAME.ucas`** + **4 `mcp_*.jsonl`** files.
- Golden determinism: all 24 outputs regenerated twice and `diff`ed — **all byte-identical**.
- Bounded runs: every candidate run under `timeout 30`; **0 crashes, 0 hangs, 0 truncated JSON**.
- Special-value cross-checks: `mpmath 1.3.0` and `sympy 1.14.0` used for `isqrt`, `log`, `W`,
  `-1/e`, and pole limits.

### Layout

- `01`–`20_*.ucas` — CLI goldens covering domain, range, derivative, integral, wrap, limit,
  continuity, critical points, parity, properties, aliases, and the inline-annotation misparse.
- `mcp_domain.jsonl`, `mcp_limits.jsonl`, `mcp_calculus.jsonl`, `mcp_equiv.jsonl` — MCP goldens
  (stdlib text + structured results), including the wrong structured answers for F1/F2/F3.
- `FINDINGS.md` — full reproducers, exact observed output, and expected behaviour for all five issues.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| LIMIT | 2 | — |

### Issues by severity

| id | severity | one-line title |
|----|----------|----------------|
| F1 | WRONG | `domain` omits division singularities of `sec`/`csc`/`cot` (declares `sec` total on reals) |
| F2 | WRONG | `limit` at reciprocal-trig poles returns spurious finite value (e.g. `sec` at `pi/2` → `1.63e16`) |
| F3 | WRONG / NLP | inline `x: T in a..b` annotation misparsed in anonymous command args → wrong ranges/domains |
| F4 | LIMIT / WRONG | `continuity`/`discontinuities` miss poles (`tan`/`sec` miss `±pi/2`; `csc`/`cot` miss `±2pi`, `±3pi`) |
| F5 | LIMIT / NLP | parity witness for `log`/`acosh` uses an undefined point as value `0` |

Totals: **3 WRONG** (one also NLP), **2 LIMIT** (one also NLP), **0 CRASH / HANG / DETERMINISM**.


## Takeaway
Core calculus (derivatives, integrals, aliases) and machine-type wrap witnesses are sound, but the **domain/limit layer is unsound for reciprocal trig** (poles are omitted by `domain`, replaced by spurious finite numbers by `limit`, and partially missed by `continuity`) and **inline ranged annotations are silently misparsed in anonymous command arguments**, yielding wrong ranges for fundamental functions such as `log`, `asin`, and `W`.

### Original takeaway (verbatim)

Core calculus (derivatives, integrals, aliases) and machine-type wrap witnesses are sound, but the
**domain/limit layer is unsound for reciprocal trig** (poles are omitted by `domain`, replaced by
spurious finite numbers by `limit`, and partially missed by `continuity`) and **inline ranged
annotations are silently misparsed in anonymous command arguments**, yielding wrong ranges for
fundamental functions such as `log`, `asin`, and `W`.
