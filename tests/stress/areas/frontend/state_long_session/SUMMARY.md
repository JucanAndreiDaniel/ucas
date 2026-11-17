# SUMMARY — `state_long_session`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 11
- Files created: not recorded

### Coverage (distinct statements / queries tried)

| Source | Count |
|---|---|
| `stress_big.ucas` (single 172-statement CLI session) | 172 |
| `mcp_long_session.jsonl` (single 92-call MCP session) | 92 |
| Small CLI goldens 01–05 | 62 |
| Small MCP goldens (state funcs, assume divergence, builtin shadow, underscore collision) | 30 |
| Scratch probes (assume/reset/forward/unicode/recursion/duplicate-key, ad-hoc `-e` runs) | ~95 |
| **Total** | **~450** |

Topics exercised: hundreds of definitions and redefinitions, case-only-different
names, 240-char names, Unicode names (all three front ends), forward references,
self/mutual recursion, names shadowing builtins/constants/commands/types,
underscore names, `assume` collisions (English vs session vs per-request,
duplicate keys), `forget`/`reset` mid-session, `funcs` vs `state` inventory,
and mixed ucas + English + MCP `session` sessions.

### Files created

CLI goldens: `01_builtin_shadow`, `02_case_and_long`, `03_forward_redefine`,
`04_shadow_command_type`, `05_english_state_mix`, `stress_big` (each `.ucas` +
`.out`).

MCP goldens: `mcp_state_funcs`, `mcp_assume_divergence`, `mcp_builtin_shadow`,
`mcp_underscore_collision`, `mcp_long_session` (each `.jsonl` + `.out`).

Docs: `FINDINGS.md`, `SUMMARY.md`.

All 11 goldens are deterministic (two runs byte-diffed) and exit 0 under
`timeout`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | builtin-named defs listed-but-not-callable; state omits _-prefixed funcs; English vs session assume stores diverge; user _ clobbered by anon |
| NLP | 5 | forget everything clears only assumptions; command names misroute definitions; Unicode names rejected; duplicate JSON key → id:null parse er |
| LIMIT | 5 | forget everything clears only assumptions; command names misroute definitions; Unicode names rejected; duplicate JSON key → id:null parse er |

### Issues by severity

| Severity | Count | Titles |
|---|---|---|
| `WRONG` | 4 | builtin-named defs listed-but-not-callable; `state` omits `_`-prefixed funcs; English vs session assume stores diverge; user `_` clobbered by anonymous results |
| `NLP` / `LIMIT` | 5 | `forget everything` clears only assumptions; command names misroute definitions; Unicode names rejected; duplicate JSON key → `id:null` parse error; (order-dependent assume winner) |
| `CRASH` | 0 | — |
| `HANG` | 0 | — |
| `DETERMINISM` | 0 | — |


## Takeaway
Interpreter state is stable and deterministic over long sessions (172 statements / 92 calls), but its name resolution and assumption tracking are incoherent: builtin-named and `_`-prefixed definitions are reported in the listings yet not actually used, and `session state.assumptions` disagrees with the assumptions the English frontend really applies.

### Original takeaway (verbatim)

Interpreter state is stable and deterministic over long sessions (172 statements /
92 calls), but its name resolution and assumption tracking are incoherent:
builtin-named and `_`-prefixed definitions are reported in the listings yet not
actually used, and `session state.assumptions` disagrees with the assumptions the
English frontend really applies.
