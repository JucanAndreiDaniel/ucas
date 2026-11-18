# Stress findings — `kernel_army`

Area: the LCF proof kernel / cost-model entry points owned by `model.c`,
`kterm.c`, `knorm.c`, `kcheck.c`, `kernel.c`, `kauto.c`, `kscript.c`,
`inst.c` and `memk.c`. Binary: `$ROOT/ucas`. All goldens were captured from
the fixed binary with the canonical command (`ucas NAME.ucas`, run from this
folder, `UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`) and byte-diffed on two runs
(no nondeterminism). Each input includes a control that must keep working.

## Summary

| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | `cost` of a bare undefined identifier silently priced as a free variable (0); int64 literals up to 2^63−1 rejected by the theorem parser |
| LIMIT | 1 | an overflowing int64 literal in a theorem produced an empty `error:` diagnostic |

## Findings

### WRONG-1 — `cost` of an undefined function silently returns 0

**Severity:** WRONG
**Source:** `src/model.c`, `cmd_cost()`.

`cost totally_undefined_function` used to print
`cost of totally_undefined_function under gt1030: 0 (0 operations...)`.
`cmd_func()` turns a bare unknown identifier into an anonymous one-parameter
function whose body is just that auto parameter; `cmd_cost()` priced it as a
free variable. (This is the cost counterpart of the `mca` LIMIT in
`gpu/x86_intrinsics_mca`.) The `equiv` path already guards this with
`cmd_named_func`, but `cost` had no equivalent hook in `parse.c`.

**Fix (model.c only):** `cmd_cost()` now detects the exact shape produced for
an unresolved bare name — an anonymous function with one auto parameter whose
body is that parameter's own var node — and reports `undefined function NAME`
before pricing. A defined function (`f->anon == 0`) and a real expression
whose body is not a bare var are unaffected.

**Reproducer / control:** `01_undefined_cost.ucas` — `cost f` and `cost x + 1`
price as before; `cost totally_undefined_function` is now an error.

### WRONG-2 — valid int64 literals 2^63−8 … 2^63−1 rejected by the theorem parser

**Severity:** WRONG
**Source:** `src/kterm.c`, `next()` (the `kt_parse` tokenizer).

The decimal accumulator guard was `v > (INT64_MAX - 9)/10`, which rejects
`9223372036854775800` (= 2^63−8) and every larger literal up to and including
`INT64_MAX` (= 2^63−1), even though they are valid int64 values. For example
`theorem t: forall x:int: 9223372036854775807 > x` failed to parse. This is a
different defect from the empty diagnostic in LIMIT-1: the literal itself is
valid and should be accepted.

**Fix:** the guard now uses the current digit, `v > (INT64_MAX - d)/10`, the
exact condition for `v*10 + d` to stay in int64. The loop stops at the first
overflow so the accumulator can never itself overflow (undefined behaviour in
the old code).

**Reproducer / control:** `02_literal_max.ucas` — a small literal and two
previously-rejected boundary values now all parse and prove.

### LIMIT-1 — overflowing int64 literal produced a bare `error:`

**Severity:** LIMIT
**Source:** `src/kterm.c`, `next()`.

`next()` set `p->failed = 1` on an over-large literal but never called
`perr()`, so `kt_parse()` returned `KNONE` with an empty error buffer and the
CLI printed `error:` with no explanation. The documented failure mode
(`prove_symbolic/FINDINGS.md` LIMIT-1) is now a readable diagnostic.

**Fix:** call `perr(p, "%s", "integer literal is too large: the largest is
9223372036854775807 (2^63 - 1)")` at the overflow point.

**Reproducer / control:** `03_literal_overflow.ucas` — a 20-digit literal is
rejected with a specific message and column; a valid literal (`02`) still
proves.

## Out of scope (reported, not edited)

The flagged `gpu/cost_cross_model/FINDINGS.md` WRONG-2/3/4 are rooted in
`src/parse.c`, which this agent must not edit:

* WRONG-2 (undefined function cost 0): see WRONG-1 above — fixable from
  `model.c` because `cmd_cost` sees the anonymous function; a cleaner fix is
  to make the `cost` command use `cmd_named_func` in `parse.c:4368`.
* WRONG-3 (`abc`/`inf`/`nan` cost values silently become 0):
  `parse_model()` at `parse.c:3307` calls `number(p)` on a `T_ID` token;
  `number()` (`parse.c:267`) runs `strtoull`/`strtod` on non-numeric text and
  returns 0. Needs `pk(p) == T_NUM` validation and a non-finite check in
  `parse.c`. No model.c-level fix can distinguish a bad 0 from a valid 0.
* WRONG-4 (a failed `model` definition stays registered): `parse_model()`
  calls `model_new()` (`parse.c:3150`) before the parent/fusion validation,
  so `fail()` leaves the half-built model in `models[]`. Needs a transaction
  in `parse.c` (or a `model_remove()` called on failure).

## Goldens needing recapture (owned by other areas)

* `gpu/cost_cross_model/10_bad_model_values.out` — the final
  `cost totally_undefined_function` line now errors instead of showing cost 0.
* `gpu/cost_cross_model/mcp_crossmodel_cost.out` — MCP id 12 (`cost` on
  `no_such_fn`) now returns an error instead of `"total": 0`.
* `sat/prove_symbolic/06_overflow.out` — `theorem o04` with
  `9223372036854775800` now parses; downstream `prove` output changes, and
  the empty `error:` becomes a readable message.

## Checks that passed

* All 113 library lemmas still pass `check` unchanged.
* Integer instruction evaluation: 480 differential `show` cases against an
  independent Python oracle (bfe/sbfe/brev/mulhi/smulhi/funl/funr/med3/
  usad/msad/lerp/sad/byteperm/lanewise/addsat/subsat) — all matched.
* `frexp_mant`/`frexp_exp` (240 cases) and `ldexp` (150 cases) against
  Python `math.frexp`/NumPy — all matched.
* Cost class assignment and `all:` scaling: isolated-price probes and 60
  random expressions under unit/7× bare models — all consistent.
* Random linear-arithmetic theorem fuzz (80 generated sequents): no false
  theorem was proved by the kernel.
* `bmake` succeeds; `bmake test`, `bmake stress-test STRESS_AREA=kernel_army`
  and `STRESS_AREA=cost_cross_model` are covered by the handoff report.
