# SUMMARY — `llm_mutators_findings`

## Counts
- Distinct expressions/queries tried: 224
- Goldens written: 12
- Files created: not recorded

### What was done

Turned the confirmed bug catalog (`MASTER_FINDINGS.md` + per-area `FINDINGS.md`)
into a seeded neighbourhood-mutation generator. Each of 14 families encodes a
confirmed bug *shape* and re-applies it in a different type / command /
frontend / context (e.g. `equiv` domain bug → u8/u16/u32/i8/i16/i32, `where` /
declared range / value set, CLI/JSON/MCP/flat; English bound-flip → 6 functions
× 6 intervals; stale auto-name → 6 bodies × 3 wire frontends).

### Counts

- **Distinct mutation programs tried: 224** (seed `20261116`, deterministic), across **14 families** and **4 frontends** (CLI, `--json`, `--mcp`, `--mcp --flat`). Each program is 1–3 statements/queries (~300 underlying statements).
- **Outcome classes:** 209 semantic / structured responses, 8 parse-errors only, 4 crashes (SIGSEGV), 0 hangs, 3 other. → 217/224 reached a real parse + semantic/structured pass.
- **New instances of known classes:** 185 catalogued in the FINDINGS breadth table + 11 NLP misparses (§15).
- **Entirely new bug classes:** 0 confirmed. **New interface finding:** 1 (JSON/MCP function-object `where` silently dropped, FINDINGS §2). **New boundary refinements:** 2 (f32 spike depends on spike hitting the sample grid, §6; English integral flip is phrasing-specific, §10).

### Files created (all inside `tests/stress/areas/sat/llm_mutators_findings/`)

- `generate.py`, `run_corpus.py` — the seeded generator and the validation/execution runner.
- `mutations.json`, `MUTATIONS.md` — the full 224-mutation corpus and family index.
- `results.jsonl`, `run_summary.txt` — per-mutation outcomes and aggregate statistics.
- `FINDINGS.md`, `SUMMARY.md` — this catalog.
- Goldens (each `NAME.ucas`/`NAME.jsonl` + `NAME.out`, deterministic):
  `01_equiv_domain_u16`, `02_real_identity_newexpr`, `03_cast_i16`,
  `04_domain_total_u16`, `05_range_spike_boundary`, `06_mixed_sign`,
  `07_symmetry_both`, `08_powerseries`, `09_english_boundflip`, `10_vacuous`,
  `mcp_stale_autoname`, `mcp_laplace_ic`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | §14 (depth-1600 paren/minus/abs nesting, CLI + whole MCP server, rc 139) |
| WRONG | 12 | §1, §3–§13 (equiv-domain, real identity, cast coercion, domain-total, range-spike, mixed-sign, symmetry, powerseries, English bound-flip, va |
| NLP | 2 | §2 (where dropped), §15 (number/chained-comparison misparse) |

### Issues by severity (distinct findings in FINDINGS.md)

| severity | count | finding ids |
|---|---:|---|
| WRONG | 12 | §1, §3–§13 (equiv-domain, real identity, cast coercion, domain-total, range-spike, mixed-sign, symmetry, powerseries, English bound-flip, vacuous, stale auto-name, laplace IC) |
| NLP | 2 | §2 (where dropped), §15 (number/chained-comparison misparse) |
| CRASH | 1 | §14 (depth-1600 paren/minus/abs nesting, CLI + whole MCP server, rc 139) |
| HANG | 0 | — |
| DETERMINISM | 0 | all 12 goldens byte-identical across two runs |


## Takeaway
Turning our own bug catalog into a seeded neighbourhood generator paid off: 185 new instances of 12 known bug classes appeared across new types, commands and frontends — notably the `equiv`-ignores-domain and stale-auto-name bugs fire for essentially *any* widening of the original repro — plus two boundary refinements and one new silent-`where`-drop on the structured API; no brand-new bug class emerged, and the only crashes remain the well-known deep-nesting parser overflow.

### Original takeaway (verbatim)

Turning our own bug catalog into a seeded neighbourhood generator paid off:
185 new instances of 12 known bug classes appeared across new types, commands
and frontends — notably the `equiv`-ignores-domain and stale-auto-name bugs
fire for essentially *any* widening of the original repro — plus two boundary
refinements and one new silent-`where`-drop on the structured API; no brand-new
bug class emerged, and the only crashes remain the well-known deep-nesting
parser overflow.

### Confinement

Stayed entirely in `tests/stress/areas/sat/llm_mutators_findings/`. No source file,
Makefile, existing test, `opencode.json`, another stress area, or git state was
touched; all scratch data went to `/tmp/opencode/llm_mut_scratch/`. No `make`,
no `git`, every run bounded by `timeout`.
