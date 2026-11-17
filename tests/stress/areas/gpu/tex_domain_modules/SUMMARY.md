# SUMMARY — `tex_domain_modules`

## Counts
- Distinct expressions/queries tried: ~590
- Goldens written: 9
- Files created: not recorded

### Counts
- Distinct MCP calls / queries tried (exploratory + goldens + probes): **~590**
- Calls captured in durable goldens: **188** (9 `mcp_*.jsonl` files; 206 lines
  including the 18 `initialize`/`notifications/initialized` headers)
- Golden file pairs (`mcp_*.jsonl` + `mcp_*.out`): **9**
- All goldens verified deterministic across two runs; all exit 0 with complete
  JSON-RPC responses; `files:"none"` / `nofile:true` used throughout (no files
  left behind).

### Files created (all under tests/stress/areas/gpu/tex_domain_modules/)
- `mcp_texenc_bc.jsonl` / `.out`
- `mcp_texenc_astc_etc.jsonl` / `.out`
- `mcp_texalu_borders.jsonl` / `.out`
- `mcp_lperm_odd.jsonl` / `.out`
- `mcp_winograd_bounds.jsonl` / `.out`
- `mcp_tcdot_ozaki.jsonl` / `.out`
- `mcp_solids_singular.jsonl` / `.out`
- `mcp_hypercomplex_zero.jsonl` / `.out`
- `mcp_plot_degenerate.jsonl` / `.out`
- `FINDINGS.md`, `SUMMARY.md`


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 8 | — |
| LIMIT | 1 | — |

### Issues by severity
- **WRONG: 8** — 4 in `solids` (divergent arc lengths reported finite; cusp arc
  length below its own chord; finite surface area falsely "divergent"), 1 in
  `winograd` (error bound ignores f32 overflow), 2 in `hypercomplex` (unknown
  algebra silently defaults / yields a garbage table), 1 in `texenc` (3-D ASTC
  footprint silently truncated to 2-D).
- **NLP: 0 separately** (3 of the WRONG items are also malformed-argument
  mis-handling; noted in FINDINGS).
- **LIMIT: 1** — `tcdot samples=100000` (documented max) takes ~20 s.
- **CRASH: 0**, **HANG: 0** (within a 30 s bound), **DETERMINISM: 0**.


## Takeaway
No crashes, hangs, or nondeterminism; the real defects are **unsound numerical answers** — `solids` reports finite values for divergent arc-length integrals (and a below-chord length for a cusp) and `winograd` derives an error bound that ignores floating-point overflow — plus a few malformed-argument cases that are silently mis-handled instead of rejected.

### Original takeaway (verbatim)
No crashes, hangs, or nondeterminism; the real defects are **unsound numerical
answers** — `solids` reports finite values for divergent arc-length integrals
(and a below-chord length for a cusp) and `winograd` derives an error bound that
ignores floating-point overflow — plus a few malformed-argument cases that are
silently mis-handled instead of rejected.
