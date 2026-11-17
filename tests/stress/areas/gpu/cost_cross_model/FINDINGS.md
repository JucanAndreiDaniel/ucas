# Stress findings — `cost_cross_model`

_Original heading: FINDINGS — `cost_cross_model`_

# FINDINGS — `cost_cross_model`

Area: cost-model consistency and monotonicity across µarch models, custom model
overrides, inheritance, `use` switching, subset/superset instruction sets,
`find`-produced forms and `mca` bounds. Binary: `$ROOT/ucas`
(prebuilt). All candidates were run under `timeout`; every golden was run twice
and byte-diffed (no nondeterminism observed anywhere in this area).

Durable goldens are `01_…10_…` (CLI) and `mcp_crossmodel_cost` /
`mcp_crossmodel_mca` (MCP). The bug reproducers below are all deterministic, so
their outputs are also kept as goldens (`07`, `10`) — no crash/hang/nondeterminism
was found in this area.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | `mca`'s “simulated” cycles contradict the critical-path bound it prints (integer division) |
| NLP | 1 | a mistyped, undefined short function name is silently read as a product |
| LIMIT | 1 | “cheaper in one µarch” does NOT imply “cheaper in every µarch” |

## Findings

### WRONG-1 — `mca`'s “simulated” cycles contradict the critical-path bound it prints (integer division)
**Severity:** WRONG
_Original classification: `WRONG (high`._
**Expected:** _not recorded_
`zen2`, `zen4` (and any expression using integer `/` or `%` there). `glc`/`rpl`
are consistent.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/gpu/cost_cross_model
timeout 15 $ROOT/ucas 07_mca_divergence.ucas
# or, minimal:
printf 'd(x: u32, y: u32) = x / y\nmca d on zen4\nmca d on skl\nmca d on glc\n' > /tmp/d.ucas
timeout 15 $ROOT/ucas /tmp/d.ucas
```

**Observed:** (`07_mca_divergence.out`, and MCP `mcp_crossmodel_mca.out` ids 3–5, 7):
```
> d(x: u32, y: u32) = x / y
> mca d on zen4
  straight-line code: 1 instruction, 2 uops
     #  instruction                     lat   rtp uops  ports
     0  div r32   x/y                    12     6    2  ALU1
  bounds: critical path 12.00, ports 7.00 (ALU1), front end 0.33 (2 uops / 6)
  simulated: 18.00 cycles, limited by the critical path
> mca d on skl
     0  div r32   x/y                    26     6   10  p0156
  bounds: critical path 26.00, ports 6.00 (p0), front end 2.50 (10 uops / 4)
  simulated: 28.00 cycles, limited by the critical path
> mca d on glc
  bounds: critical path 12.00, ports 6.00 (p0), front end 0.67 (4 uops / 6)
  simulated: 12.00 cycles, limited by the critical path
```
The MCP structured result is unambiguous (`mcp_crossmodel_mca.out`):
```
id 3 zen4  cycles=18  latency_bound=12  port_bound=7   limited_by="the critical path"
id 4 zen2  cycles=18  latency_bound=12  port_bound=7   limited_by="the critical path"
id 5 skl   cycles=28  latency_bound=26  port_bound=6   limited_by="the critical path"
id 7 x86v4 cycles=28  latency_bound=26  port_bound=6   limited_by="the critical path"
id 6 glc   cycles=12  latency_bound=12  port_bound=6   limited_by="the critical path"   (consistent)
```

**Why it matters:** it is a bug / expected.** For a single instruction the simulated latency
*must* be its listed latency (the critical-path bound); the other bounds are
6–7 and 0.3–2.5. On zen4/zen2 18 > 12 and on skl/x86v* 28 > 26, yet the report
says the result is "limited by the critical path". The simulation evidently
uses a different (undisclosed) latency for `div r32` than the table it prints,
so the printed bounds do not bound the simulation. This also breaks agreement
with `cost`: for `c1(x,y,z) = ((x*3+7)/13 + y) % z`, `cost c1 model zen4` = 24
but `mca c1 on zen4` = 27 cycles (the composite probes are in the exploratory
`harness3` run; the single-instruction repro above is the minimal case).

### WRONG-2 — `cost` of an undefined function silently returns 0 (CLI and MCP)
**Severity:** WRONG
_Original classification: `WRONG (medium`._
**Expected:** _not recorded_
exist, instead of a diagnostic.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/gpu/cost_cross_model
timeout 10 $ROOT/ucas 10_bad_model_values.ucas   # last statement
# or minimal:
printf 'cost totally_undefined_function\n' | timeout 10 $ROOT/ucas
# MCP:
printf '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze","arguments":{"op":"cost","args":{"f":"no_such_fn","model":"gt1030"}}}}\n' | timeout 10 $ROOT/ucas --mcp
```

**Observed:**
```
cost of totally_undefined_function under phantom: 0 (0 operations, shared subterms counted once)
```
MCP (`mcp_crossmodel_cost.out`, id 12): `ok=true`,
`"total": 0, "operations": 0, "by_class": [], "isError": false`.

**Why it matters:** it is a bug / expected.** Pricing a non-existent function should be a
clean `unknown function` error (as `use bogus` and `cost f model bogus` are), not
a successful result claiming cost 0. A typo in an expression/filename therefore
silently produces a plausible-looking free cost. This is the cost counterpart of
the already-reported “`mca` on an undefined function returns a bare header”
LIMIT in `x86_intrinsics_mca/FINDINGS.md` §4.

### WRONG-3 — non-numeric / `inf` / `nan` cost values are silently accepted as 0
**Severity:** WRONG
_Original classification: `WRONG (medium`._
class by a value that is not a number at all.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/gpu/cost_cross_model
timeout 15 $ROOT/ucas 10_bad_model_values.ucas
# or minimal, one value at a time:
for v in abc inf nan -5 +3 5abc 1.2.3; do
  printf 'f(x: u32) = x*7 + 11\nmodel m : gt1030 { imul: %s }\ncost f model m\n' "$v" > /tmp/v.ucas
  timeout 10 $ROOT/ucas /tmp/v.ucas
done
```

**Observed:** (`10_bad_model_values.out`):
```
> model nan_cost : gt1030 { imul: abc }
> cost f model nan_cost
cost of f under nan_cost: 0 (2 operations, shared subterms counted once)
  fused by the model (one instruction for several operations):
    imad 1 x 0 = 0 (a*b + c; saves 1)
> model inf_cost : gt1030 { imul: inf }
cost of f under inf_cost: 0 ...
> model neg_cost : gt1030 { imul: -5 }
...: error: expected a cost class        <- error, yet the model exists
cost of f under neg_cost: 0 ...
> model plus_cost : gt1030 { imul: +3 }
...: error: expected a cost class        <- error, yet the model exists
cost of f under plus_cost: 0 ...
```
Other probed values: `5abc` → error “unknown cost class 'abc'” but `imul=5`;
`1.2.3` → error “expected a cost class” but `imul=1.2`; `0x10` → 16 (valid);
`1e400` → `inf` (valid overflow); `.5` → 0.5 (valid).

**Why it matters:** it is a bug / expected.** `strtod`-style parsing maps `abc`, `inf` and
`nan` to 0 (and accepts a numeric prefix before junk), so a malformed model
turns a class into a *free* instruction instead of rejecting it. `inf` in
particular is the natural spelling for “unavailable instruction”, yet it
becomes 0.
**Expected:** reject non-finite / non-numeric prices (or at least report
a parse error and not create the model).

### WRONG-4 — a `model` definition that fails still leaves a usable default-cost model behind
**Severity:** WRONG
_Original classification: `WRONG (medium`._
**Expected:** _not recorded_
reported an error.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/gpu/cost_cross_model
timeout 15 $ROOT/ucas 10_bad_model_values.ucas
# or minimal:
printf 'f(x: u32) = x*7 + 11\nmodel phantom : nosuch_parent { imul: 5 }\nmodels\nuse phantom\ncost f\n' > /tmp/ph.ucas
timeout 10 $ROOT/ucas /tmp/ph.ucas
```

**Observed:** (`10_bad_model_values.out`, plus the probe above):
```
...: error: unknown model
    model phantom : nosuch_parent { imul: 5 }
                    ^
> cost f model phantom
cost of f under phantom: 2 (2 operations, shared subterms counted once)
  iadd 1 x 1 = 1
  imul 1 x 1 = 1
> use phantom
cost model: phantom
cost of f under phantom: 2 ...
```
`models` lists `model phantom { iadd: 1, ..., imul: 1, ... }` — a completely
fresh default model, with none of the requested `imul: 5` and none of the
parent's fusions. The same happens for `model a : gt1030 { bogusclass: 5 }`
(error “unknown cost class”) and `model a : gt1030 { nofuse nosuch }` (error
“model a has no fusion nosuch”) — in each case `a` is registered and usable.

**Why it matters:** it is a bug / expected.** A statement that emits an error should not
commit a half-built model. `use phantom`, `cost f model phantom` and `find`
under it now silently use default prices (1 per class) rather than the user's
parent or overrides, which is a wrong cost with no indication that the
definition failed. Note also `model a : a { imul: 5 }` (self-inheritance) and
a two-model inheritance cycle (`a : b`, `b : a` with `b` unknown at the time)
are accepted / leave phantom models without a cycle diagnostic.

### NLP-1 — a mistyped, undefined short function name is silently read as a product
**Severity:** NLP
**Reproducer:**
```sh
printf 'cost tg model gt1030\n' | timeout 10 $ROOT/ucas
```
**Observed:**
```
  note: 'tg' read as t*g (single-letter variables)
cost of t*g under gt1030: 1 (1 operations, shared subterms counted once)
  fmul 1 x 1 = 1
```
**Why it matters:** it is a bug / expected.** The “single-letter variables” fallback is
useful for mathematical shorthand, but when a two-letter name is *meant* to be
a defined function (e.g. a failed definition named `tg`) the fallback silently
prices `t*g` and reports success. This was hit while constructing
`09_subset_and_fallback` (`tg(x) = tex_fetch(x)` — `tex_fetch` is not an
expression-level builtin, the definition failed, and `cost tg` became `t*g`);
the golden now uses `udot4x8` instead.
**Expected:** apply the split only when no
definition of that name was attempted, or at least warn more strongly.

### LIMIT-1 — “cheaper in one µarch” does NOT imply “cheaper in every µarch”
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
per-class prices plus fusions, recorded so the invariant is not mistaken for a
bug.

**Evidence** (from the exploratory cross-model matrices, not a golden):
* `(x<<3)+y` costs 1.93 under `ga104` while `x*8+y` costs 1.70 there — the
  multiply-add fusion is priced as `imul` (1.7), which is cheaper than the
  shift-add fusion priced as `shift` (1.93). The order reverses on gt1030
  (2.00 vs 3.00 before fusion).
* `x*x + 3*x + 5` (7) is dearer than `x*x+x+x+x+5` (6) under gt1030, because
  the repeated adds fuse into a shift-add while `3*x` becomes an IMAD — fewer
  *written* operations is not always cheaper once instruction selection runs.
* `x/8` is priced as a shift (1–2) on every model, so overriding `idiv` does
  **not** change it, while `x/7` (idivk) does — golden `04_override_effects`
  shows both.

**Takeaway.** Overrides, inheritance and `use` all resolve correctly (goldens
`03`, `04`, `05`), but any tool that assumes a single global cost ordering
across models is wrong. Also note a built-in model can be silently redefined
in place (`model gt1030 { imul: 5 }` changes the active built-in with no
warning) — LIMIT, exercising this requires a fresh process.

## Checks that passed

### Invariants that held (no issue)
* `cost f model M` == `use M; cost f` for all 16 built-in models, including
  interleaved switching (`03_use_switch_equivalence`).
* Overrides of every probed class (`iadd`, `imul`, `idivk`, `shift`, `fadd`)
  took effect; fusions re-price through overridden classes (`imad` with
  `imul:100` costs 100); `nofuse` drops exactly one named fusion.
* Inheritance resolves multi-level chains and sibling models correctly; an
  empty derived model inherits everything; a bare model uses unit prices.
* `find` uses the active model and picks model-appropriate cheapest forms
  (gt1030 → `x + (x<<3)`/`(x<<4)-x`; x86 → `x + (x + (x<<2))`); the claimed
  costs match a subsequent `cost` of the same form.
* Models missing a class (`tiny`, `mali_g715` without dot4x8/f64) price it as
  `inf` with an explicit “not available under …” note (`09_subset_and_fallback`).
* For non-division straight-line code, `mca` simulated cycles equal the largest
  printed bound and never exceed `cost` (`06_mca_bounds_consistent`).
* No crashes, hangs or nondeterminism: ~1,700 probes plus all goldens run
  cleanly, every golden byte-identical on two runs.
