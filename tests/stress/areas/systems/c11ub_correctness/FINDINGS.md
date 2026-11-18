# Stress findings — `c11ub_correctness`

Area: C11 undefinedness and unspecified evaluation order in the C frontend,
audited against Krebbers' CH2O thesis and Hathhorn/Ellison/Roşu,
*Defining the Undefinedness of C* (PLDI 2015, 77 core-language UB
categories). All runs bounded; every kept golden was run twice and `diff`ed
and is byte-identical.

## Summary

| Severity | Count | One-line headline |
|----------|-------|-------------------|
| UB modeled | 6 new | unsequenced access, OOB subscript, uninitialised local, value-return fall-through, float-cast overflow check in `check`, unspecified-order disclosure |
| WRONG | 0 | — |
| LIMIT | 4 | pointer/alignment/atomic/library UB unreachable in ucas's C subset (see the paper report) |

## Findings

### UB-1 — unsequenced accesses to one scalar (C11 6.5p2, UB #35)

**Before:** `i++ + i++` and `i = i++` were lowered to a single value with
only incidental overflow conditions; one evaluation order was silently
chosen.
**Now:** `seq_scan` walks each full expression, groups accesses by
unsequenced region (a sequence point starts a new region) and refuses the
lowering on a read/write or write/write conflict. A `requires` note names
the symbol and both source lines. `c optimize` reports `not lowered` and
emits no rewrite for the function (`01_unsequenced`, `06_optimize_refusal`).

### UB-2 — array subscript out of range (C11 6.5.6p8, UB #49)

**Before:** `tab[x]` produced `mk_index` with no condition; an out-of-range
index silently yielded `undefined`.
**Now:** the load adds `0 <= i < count` guarded by the reaching path
(`03_array_oob`).

### UB-3 — reading an uninitialised automatic object (C11 6.3.2.1p2, UB #21)

**Before:** the value was `mk_undef` but no domain condition was recorded.
**Now:** a per-symbol `init` condition tracks the paths on which an
assignment or initialiser reached the local; a read adds it to `where`
(`04_uninitialized`). Parameters/globals add nothing.

### UB-4 — reaching `}` of a value-returning function (C11 6.9.1p12, UB #88)

**Before:** the fall-through path returned `mk_undef` as if defined.
**Now:** the reaching path is excluded from the domain (`05_fallthrough`).

### UB-5 — float-to-int overflow in the differential checker

`cf_check.c` now enables UBSan's `float-cast-overflow` (with a minimal
runtime handler), so a benchmark input whose original performs an
out-of-range cast is skipped rather than compared against an arbitrary
value. The lowering itself already had the 6.3.1.4 condition.

### UNSPEC-1 — evaluation order of two effects on different objects (C11 6.5p3)

Two side-effecting operands that do not conflict are still unspecified.
Instead of choosing an order, ucas lowers the value and emits a `requires`
note disclosing the unspecified order (`02_unspecified_order`); the note is
also in the structured JSON report under `notes` with `kind: requires`.

## Post-audit fixes (REVIEW_C11UB)

- **HIGH — assignment RHS reads vs. sibling writes.** `acc_drop_reads()`
  dropped *all* reads from an assignment's RHS, so a sibling write to a
  symbol read only in that RHS was never compared (`i++ + (j = i)` lowered
  and could get a SAT-proved rewrite). It now drops only reads of the lhs
  symbol (`i = i + 1` still lowers); reads of other symbols survive to the
  enclosing conflict check. The same narrowing applies to increments on a
  non-symbol lvalue (`a[i]++`). New golden: `08_assign_rhs_read`.
- **MEDIUM — genuine UB was mislabelled as unspecified order.** The 6.5p3
  `requires` note was emitted before the 6.5p2 conflict check, so
  `i++ + i++` got both notes. It is now emitted only when no same-object
  conflict was found. Goldens `01_unsequenced`, `06_optimize_refusal` and
  `mcp_c11ub` were recaptured.
- **LOW — call arguments stayed silent.** Two side-effecting arguments on
  different objects (`g(i++, j++)`) now emit the 6.5p3 note; a same-object
  conflict (`g(i++, i++)`) is still UB only. New golden: `09_call_args`.

## Checks that passed

- Prior-wave UB conditions are unchanged: div/mod-by-zero, `INT_MIN/-1`,
  shift count and signed-`<<` overflow, signed `+ - *`, float-to-int range
  (`07_condition_mix`).
- Controls in every golden lower without a new condition: comma-sequenced
  increments, ordinary assignment, initialised locals, complete if/else,
  unsigned shifts, bitwise-only arithmetic.
- `c lower` refuses unsequenced bodies but still proves an ordinary rewrite
  in the same `c optimize` run (`06_optimize_refusal`).
- MCP `c_lower` returns both a `requires` list in `structuredContent.result`
  and `notes` entries with `kind: "requires"` (`mcp_c11ub`).
- The durable `INT64_MIN` crash/hang reproducers in `cfront_ub_contracts`
  complete cleanly (rc=0) with this binary.
