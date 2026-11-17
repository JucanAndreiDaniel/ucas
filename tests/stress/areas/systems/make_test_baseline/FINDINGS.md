# Stress findings — `make_test_baseline`

_Original heading: Baseline of the repo's own test suite — findings_

# Baseline of the repo's own test suite — findings

Area: `tests/stress/areas/systems/make_test_baseline/`.  Binary: `$ROOT/ucas`
(mtime 2026-11-16 16:11:28, 23235368 bytes).  All logs/reproducers are in this
folder.  Full raw output is in `full.cli.log`, `full.json.log`, `full.mcp.log`,
`full.libc.log`; per-failure unified diffs are in `full.diffs/`,
`*-json.diffs/`, `*-mcp.diffs/`.  Dry-run evidence: `dryruns.log`,
`build_context.log`.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | `cfbridge.ucas` hangs immediately after echoing its command |
| WRONG | 1 | official goldens are broadly stale vs the shipped binary (default env) |
| LIMIT | 4 | official `make test` cannot run without rebuilding; GNU make cannot parse the Makefile |
| DETERMINISM | 1 | 14 goldens pass only with the default seed (1) |

## Findings

### LIMIT-1 — official `make test` cannot run without rebuilding; GNU make cannot parse the Makefile
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT && bmake -n test 2>&1 | head
cd $ROOT && make -n test 2>&1
```
**Observed:** first lines are `cc … -c src/parse.c`, `cc … -c src/find.c`, … and
`cc … -o ucas main.o …`; GNU make gives `Makefile:66: *** missing separator. Stop.`
**Expected:** a test-only run should not modify the binary.  Source files were
touched after the build, so the official suite is not reproducible from the
shipped binary without a rebuild.  See `dryruns.log`, `build_context.log`.

### HANG-1 — `cfbridge.ucas` hangs immediately after echoing its command
**Severity:** HANG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests
timeout 45 env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none \
  $ROOT/ucas cfbridge.ucas; echo "rc=$?"
```
**Observed:** (rc=124 at both 30 s and 45 s):
```
> c optimize cfront/bridge.c nofile budget 120
```
No further output, no process exit.  The same pattern holds for
`cfbridge_zen4.ucas`, `cfront.ucas`, `mma.ucas` and `numsearch.ucas`: each
produced a `TIMEOUT … (45s)` line in `full.cli.log` and a truncated `.got`.
Consequence: the official CLI suite never finishes — with the plain 300 s
replay only **23 of 250** tests ran before `cfbridge` consumed the remaining
time (`baseline.cli.log` ends at `ok cfbridge_icl`); with a 45 s per-test cap
the suite still needs >300 s (`full` used ~12 min).

### WRONG-1 — official goldens are broadly stale vs the shipped binary (default env)
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests
for t in calc x86 mma_validate execfadd; do
  timeout 45 env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none \
    $ROOT/ucas $t.ucas > /tmp/$t.got 2>&1
  diff -u $t.out /tmp/$t.got | head -12
done
```
**Observed:** (excerpts from `full.diffs/`):
- `calc.diff`: `- … max relative difference 6.1e-16` / `+ … 5.9e-16` —
  floating-point bound numbers drift with the build/CPU.
- `x86.diff`: `+  zen2   znver2   AMD Zen 2 …` — the binary knows a `zen2`
  cost model that the 2026-11-15 golden does not; many cost tables gain a row.
- `mma_validate.diff`: candidates 3 and 4 (both cost 137) swap order —
  equal-cost tie ordering is unstable.
- `execfadd.diff`: `exec of SPIR-V (115 instructions)` → `(114 instructions)`
  — external `glslangValidator`/`spirv-opt` version drift changes the module.

Full FAIL sets (default env): 37 CLI (`full.cli.log`), 11 JSON
(`full.json.log`: calculus, complex, elip, files, hyper, mma, ozaki, session,
viz, x86, xform), 2 MCP (`full.mcp.log`: calls, x86).
**Expected:** the repo's own
goldens should match its own binary in its own default environment; they do
not.  Most goldens are dated 2026-11-15, the binary 2026-11-16.

### DETERMINISM-1 — 14 goldens pass only with the default seed (1)
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/json
timeout 45 env UCAS_SEED=0 UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none \
  $ROOT/ucas --json --files none < adamfit.jsonl > x.got 2>&1
diff -u adamfit.out x.got | head
```
**Observed:** with `UCAS_SEED=0`, `json/adamfit`, `json/numsearch` and
`json/stoke` newly FAIL (JSON goes from 42 ok/11 fail to **39 ok/14 fail**);
`adamfit.out` expects `"fitted": 58` and a quadratic `af1` with
`error: 53556.000137658906`, while seed 0 yields `"fitted": 59` and a cubic
`af1` with `error: 5828.999983689178`.  With `UCAS_SEED=1` the JSON suite is
**identical to baseline (42/11)**.  The Makefile never sets `UCAS_SEED`, so
the default is 1 (`stoch.h`: "UCAS_SEED, or 1"): these goldens silently pin an
undocumented environment value.  Evidence: `seed0-json.*`, `seed1-json.*`,
`seed0-json.diffs/json-adamfit.diff`.

The same holds for the CLI suite.  A complete re-run under `UCAS_SEED=0`
(`seed0-cli.*`) gives **200 ok / 48 FAIL / 2 skip** vs the baseline 211/37/2:
11 additional failures — `approxcert`, `approxsearch`, `cfbridge_icl`,
`fsimp`, `integ2`, `nlp_robust`, `phashtable`, `qmcmore`, `sparsemap`, `stoke`,
`texenc` — and no baseline failure becomes a pass.  `seed0-cli.diffs/stoke.diff`
shows the seed printed in the output itself (`seed 1` in the golden, a
different proposal/accept count with seed 0).  `cfbridge_icl` also crossed the
45 s per-test cap only in the seed-0 run, so it is additionally timing-sensitive.

### LIMIT-2 — removing `UCAS_NO_TIMES` breaks `json/adamfit`
**Severity:** LIMIT
_Original classification: `LIMIT/DETERMINISM`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/json
timeout 45 env UCAS_SPIRV_CROSS=none \
  $ROOT/ucas --json --files none < adamfit.jsonl > x.got 2>&1
diff -u adamfit.out x.got | tail -3
```
**Observed:** an extra trailing `+  0.19 s` line appears in `text` (JSON 41 ok/12
fail).  The number is machine-load dependent, so this golden can never pass
without `UCAS_NO_TIMES=1`.  Evidence: `notimes_off-json.*`.

### LIMIT-3 — a non-`none` `UCAS_SPIRV_CROSS` breaks 7 JSON + 1 MCP golden
**Severity:** LIMIT
_Original classification: `LIMIT/DETERMINISM`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/mcp
timeout 45 env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=/nonexistent/spirv-cross \
  $ROOT/ucas --mcp < dot.jsonl > x.got 2>&1
diff -u dot.out x.got | head
```
**Observed:** result gains
`"glsl_view": "  GLSL view: spirv-cross not found (install it …): skipped"`
and an extra text line.  JSON goes 42→**35 ok** (advice, csimp, dot, fsimp,
memrw, sink, subgroup newly fail); MCP 11→**10 ok** (dot newly fails).
Only the exact Makefile value `UCAS_SPIRV_CROSS=none` (which turns the view
off *silently*, `spvcross.c:36`) keeps these goldens passing.  Note
`spirv-cross` is genuinely absent on this machine, so all `*.needs spirv-cross`
tests are skipped.  Evidence: `spv_bogus-json.*`, `spv_bogus-mcp.*`.

### LIMIT-4 — failing official tests leave `.got`/`.diff` files behind
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Repro: any failing case above, e.g. `FAIL calc`, then look in the make cwd.
**Observed:** the `test` recipe only removes `$n.got`/`$n.diff` on success; on
FAIL it prints `see $n.diff` and leaves both.  The complete baseline left
**37 CLI + 11 JSON + 2 MCP `.got`/`.diff` pairs** (`full.*.leftover`); the
300 s-truncated replay leaves even more because in-flight tests are killed.
The repo root already contains ~40 such files dated 2026-11-16 16:11–16:21,
so this happens routinely.  My replay confined all of them to this folder.

## Checks that passed

### How the baseline was obtained (important deviation)
The official targets could **not** be run as-is: `bmake -n test` (and every
other `*-test` target) shows that make would recompile `parse.o`, `x86data.o`,
… and **relink `ucas`**, because `src/parse.c` and `src/x86data.c` have mtimes
(2026-11-16 20:43:05) newer than the shipped binary (16:11:28).  GNU `make`
cannot parse this BSD Makefile at all (`Makefile:66: *** missing separator`).
Per the harness exception ("do NOT rebuild the binary … if make would
rebuild, use make -n first and report"), I did **not** run the rebuilding
targets.  Instead `replay.sh` replays the Makefile recipes verbatim with `$BIN`
pinned to the existing binary, with cwd set to this folder so every transient
`.got`/`.diff` the recipes create stays inside this folder.  An optional
per-test `timeout` (used only for the complete catalog) bounds the hangs
documented below; the *unaltered* 300 s replay (`baseline.*`) is also kept.

Numbers in the complete baseline (`PT=45s`, suite budget 1500 s):
- CLI: **211 ok / 37 FAIL / 2 skip** (exit 37)
- JSON: **42 ok / 11 FAIL / 1 skip** (exit 11)
- MCP: **11 ok / 2 FAIL / 1 skip** (exit 2)
- libc syntax check: **144 ok / 0 FAIL** (exit 0)
- `--sat-selftest`: ok

### 8. Confirmation: locale changes do NOT alter results
`LC_ALL=C` and `LC_ALL=ro_RO.utf8` (and `LC_ALL=C.UTF-8` available as `C.utf8`)
leave both JSON (42/11/1) and MCP (11/2/1) identical to baseline
(`lcC-*`, `lcCutf8-*`, `lcRO-*`).  No locale-sensitive golden was found in the
fast suites.

### Reproducer / file index
- `replay.sh LABEL "EXTRA KEY=VAL…" "RECIPE_ENV_BASE" PT ST SECTIONS` —
  faithful recipe replay; `PT` = per-test timeout, `ST` = suite timeout.
- `run_variants.sh [json|mcp|both]` — all six altered environments above.
- `capture_dryruns.sh` — non-mutating rebuild/provenance evidence.
- `baseline.*` = unaltered 300 s replay (no per-test cap; stops at `cfbridge`);
  `basefull.*` = 300 s replay with a 20 s per-test cap (also cut short);
  `full.*` = complete 1500 s / 45 s-per-test replay — **the authoritative
  baseline** used for all comparisons;
  `seed0-*, seed1-*, lcC-*, lcCutf8-*, lcRO-*, notimes_off-*, spv_bogus-*` =
  variants (JSON/MCP unless suffixed `-cli`).
- `*.leftover` files list the `.got`/`.diff` each suite left behind; the
  corresponding `.diff` files were copied into `<label>.diffs/` before cleanup.
