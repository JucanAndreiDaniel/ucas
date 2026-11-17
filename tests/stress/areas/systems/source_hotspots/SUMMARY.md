# SUMMARY — `source_hotspots`

## Counts
- Distinct expressions/queries tried: 2204
- Goldens written: 24
- Files created: 24

### What was covered

Targeted probes of the suspicious source patterns in `tests/stress/IDEAS_SOURCE.md`
(items 5, 8, 9, 10, 12, 19, 27 and the related image/engine/recursion paths):

| Area | Focus | Goldens |
|---|---|---|
| (a) | global `jmp_buf fail_jmp` / `longjmp` — errors from deep inside C, SPIR-V, algebra and option parsers, then state checks | `01`–`03`, `mcp_longjmp_session` |
| (b) | fixed `engine[16]` `strcat` at `cf_opt.c:1867`; very long C identifiers | `04`, `05`, `mcp_engine_longid` |
| (c) | `clock()` deadlines at `find.c:632,3534` (`rules infer`, `find … stoke`, `stoke`) | `06`, `07` (short, pre-deadline only) |
| (d) | `part[256]` / `rows[64]` / `cells[64]` in `absalg_cmd.c` (`groebner`, `idealmember`, `pmsnf`, `abgroup`, `absub`, `permhom`) | `08`–`13` |
| (e) | recursion caps (`snxglslc/emit.c:823` vs `spirv.c:8755`); deep GLSL and SPIR-V | `14`–`17` |
| (f) | `file` lexer word at `lex.c:113-120` (odd path syntax) | `18`, `19` |
| (g) | image decode through `animate exec … input N file` (texenc-style texture inputs) | `20`, `21`, `mcp_img_decode`, `img/*` |

### Counts

* **Distinct expressions / queries tried:** 2204 CLI statement lines in the kept goldens
  (including a 2000-instruction SPIR-V chain and a 64/70-row matrix battery), 14 MCP tool calls,
  plus ~170 exploratory probes: 9 longjmp/state cases, ~16 fixed-array count sweeps,
  ~11 recursion-depth probes, 43 malformed image files and 100 seeded image-byte mutations.
  Roughly **2400+ distinct inputs** total.
* **Runs:** every candidate executed under `timeout 15` (no longer); every would-be golden run
  twice and byte-diffed (24 files × 2 runs = 48 verification runs, all identical).
* **Files written (24 goldens + data + docs):** 21 `.ucas` + 3 `.jsonl` inputs, their 24 `.out`
  files, 15 crafted image files under `img/`, `FINDINGS.md`, `SUMMARY.md`.
* **Issues by severity:**
  * `WRONG` — **2**: `groebner` drops polynomials past #256 (silently gives `x^2` instead of `x`);
    `pmsnf` drops rows past #64 (silently gives `diag(x)` instead of `diag(1)`).
  * `DETERMINISM` — **3**: `clock()`-bounded `rules infer seconds 1` changes candidate counts and
    rule sets under CPU load; failed GLSL diagnostics carry a random mkstemp filename; MCP
    `animate` without `seed` uses a fresh random seed and changes GIF checksums.
  * `CRASH` / `HANG` — **0** (143 malformed/mutated image files and 2000-deep recursion probes
    all returned rc 0).
  * `LIMIT` — **5**: guarded `engine[16]` `strcat` (truncates, cannot overflow); `fx_build` depth
    cap 24 and `emit_constant` cap 32 both effective; `file` path mode reads only (no traversal
    or blocking read observed); image decoders enforce dimension caps; longjmp state survival
    verified with no stale-frame failure.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 5 | — |
| DETERMINISM | 3 | — |

## Takeaway
The strongest real defects are **silent truncation of valid mathematical input** in the abstract-algebra commands (`split_commas` caps the output count, so items past 256/64 are discarded and the answer can be wrong without any diagnostic); the clock/seed/mkstemp sources of nondeterminism mean those probe shapes must stay in FINDINGS rather than become goldens.

### Original takeaway (verbatim)

The strongest real defects are **silent truncation of valid mathematical input** in the
abstract-algebra commands (`split_commas` caps the output count, so items past 256/64 are
discarded and the answer can be wrong without any diagnostic); the clock/seed/mkstemp sources of
nondeterminism mean those probe shapes must stay in FINDINGS rather than become goldens. The
three headline "crash" ideas from IDEAS_SOURCE (#8 engine `strcat`, #10 fixed arrays, #12 recursion
cap) are all already guarded in this build and did not reproduce.
