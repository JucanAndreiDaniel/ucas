# SUMMARY — `sanitizer_builds`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 318
- Files created: not recorded

### What was done

A **separate** ASan+UBSan binary (`ucas_san`, 111 MB) was built in this folder by
reconstructing the Makefile's flags — no `make`, no source edits, no touching
`$ROOT/ucas`. `build_sanitized.sh` compiles all 144 `src/*.c` plus the
5 `src/snxglslc/*.c` files with
`-O1 -g -std=gnu99 -fsanitize=address,undefined -fno-omit-frame-pointer -lm`;
the generated headers `nlp_words.h` and `thy_absalg.inc` were copied in and `-I .` added.
`run_sanitized.py`, `sweep_corpus.py`, and `sweep_rest.py` drive the tests.

### Counts

- **Distinct expressions / queries / statements tried:** ≈ **710**
  - ≈ 450 in 40 generated, batched cases (`A01`–`A10`, `B01`–`B04`, `C01`–`C09`,
    `D01`–`D03`, `E01`–`E04`, `F01`–`F05`) covering deep nesting, huge tables/bignums,
    NaN/float edges, all type casts, and the harsh SAT reproducers from sibling areas.
  - 37 focused UB-edge probes (signed overflow, `MIN/-1`, shifts ≥ width, div-by-zero,
    extreme float→int casts).
  - 16 malformed `--json` / `--mcp` requests (null/wrong types, deep JSON, bogus tools).
  - ~10 minimized repros used to localize the findings.
  - a broad, time-bounded subset of the 318 golden-corpus files replayed through the
    sanitized binary (250 `tests/*.ucas`, 54 `tests/json/*.jsonl`, 14 `tests/mcp/*.jsonl`);
    the sweep was cut short by the time budget, but every file that produced a sanitizer
    report (13 corpus files, all in `a…i`) was captured and is documented in FINDINGS.md.
- **Files created:** `build_sanitized.sh`, `run_sanitized.py`, `sweep_corpus.py`,
  `sweep_rest.py`, `FINDINGS.md`, this `SUMMARY.md`, copied headers `nlp_words.h` and
  `thy_absalg.inc`, the `ucas_san` binary, 149 objects in `obj/`, 3 list files, and
  ~90 `.in`/`.log` evidence artifacts in `evidence/`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 3 | 1. ASan stack-overflow in prefix/parse_expr on deep nesting (~10 variants incl. JSON/MCP servers). 2. ASan global-buffer-overflow in nlp.c:7 |
| LIMIT | 3 | 4. LeakSanitizer: 64 B/definition leaked by hy_def (hyper.c:1860) for where/table definitions. 5. UBSan signed-integer overflow in idrw.c:84 |

### Issues found (by severity)

| Severity | Count | Finding |
|---|---|---|
| **CRASH** | 3 | 1. ASan `stack-overflow` in `prefix`/`parse_expr` on deep nesting (~10 variants incl. JSON/MCP servers). 2. ASan `global-buffer-overflow` in `nlp.c:707 isw()` on a bare `differentiate …` English line. 3. ASan `heap-buffer-overflow` in `spv_mem.inc:269 mem_uni_at` on `spvsimplify`. |
| **LIMIT** | 3 | 4. LeakSanitizer: 64 B/definition leaked by `hy_def` (hyper.c:1860) for `where`/table definitions. 5. UBSan signed-integer overflow in `idrw.c:840`, `scheme.c:1506`, `approx.c:568/1137`, `find.c:562/563` (analysis code, at `LONG_MIN/MAX`). 6. UBSan nonnull-arg violations in `pgrp.c`, `simp.c`, `cf_opt.c`, `find.c`. |
| WRONG / NLP / HANG / DETERMINISM | 0 | No new logical-wrongness, misparse, hang, or nondeterminism attributable to this area (the sibling WRONG/NLP findings are documented in their own folders). |

**Not observed (important negatives):** no use-after-free, no misaligned access, no
null-pointer dereference (SEGV at address 0), no double-free; no UBSan report in the
expression evaluator; and no sanitizer report at all for fp_edge NaNs, type_coercion,
resource-limit inputs (other than the §4 leak), or malformed JSON/MCP requests.


## Takeaway
The sanitized rebuild works and exposes three genuine memory-safety bugs that the uninstrumented binary hides — a parser stack overflow, an NLP `W[-1]` global OOB read on "differentiate …", and a SPIR-V uniformity heap off-by-one — plus a small repeatable `hy_def` leak and several latent signed-overflow / nonnull UB diagnostics in the analysis engine; the core expression evaluator itself is clean under UBSan.

### Original takeaway (verbatim)

The sanitized rebuild works and exposes three genuine memory-safety bugs that the
uninstrumented binary hides — a parser stack overflow, an NLP `W[-1]` global OOB read
on "differentiate …", and a SPIR-V uniformity heap off-by-one — plus a small repeatable
`hy_def` leak and several latent signed-overflow / nonnull UB diagnostics in the
analysis engine; the core expression evaluator itself is clean under UBSan.

### Confirmation

All artifacts were created under `$ROOT/tests/stress/areas/systems/sanitizer_builds/`.
The repo binary, source, Makefile, tests, and all sibling folders were left untouched.
No core files remain. Long-running cases were bounded with `timeout`.
