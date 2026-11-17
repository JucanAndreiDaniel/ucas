# SUMMARY — `cfront_fuzz`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 27
- Files created: 67

### Counts

- **Distinct C snippets / queries tried: ~450**
  - 141 C functions in the durable `.ucas` catalog (30 CLI files: 27 golden
    files plus 3 hang reproducers), each run twice under `timeout`.
  - 253 automatically generated snippets covering every integer type with
    `+ - * / % << >> & | ^ ~ ! &&` and casts between all representative
    type pairs, float ops/literals, loop shapes, pointers, aliasing, variadic
    calls and invalid C (all exited 0, no crash).
  - ~50 targeted probes (isolated hangs, `check` with/without a clang `cc`
    shim, `bench` determinism, `analyze domain` cross-checks, file-vs-block
    struct parsing, MCP direct calls).
  - 8 MCP tool calls across 4 `.jsonl` sessions.
- **Files created: 67**
  - 27 CLI `.ucas` + 27 matching `.out` goldens (`01_…` … `27_…`),
    all byte-identical across two runs and verified again with the canonical
    command `timeout 30 ucas NAME.ucas > NAME.out 2>&1`.
  - 4 MCP `mcp_*.jsonl` + 4 `.out` goldens, verified with
    `timeout 30 ucas --mcp < NAME.jsonl > NAME.out 2>&1`.
  - 3 hang reproducers **without** `.out` (`hang_break_loop.ucas`,
    `hang_nested_inc.ucas`, `hang_nested_inc_opt.ucas`) — deliberately not
    goldens.
  - `FINDINGS.md`, `SUMMARY.md`.
- **Issues by severity:** CRASH 0, HANG 2, WRONG 0, NLP 0, LIMIT 5,
  DETERMINISM 1.

### Coverage map (files)

| File(s) | Category |
|---|---|
| `01_signed_overflow`, `25_misc_ub`, `23_tricky_expr` | signed overflow, `INT_MIN/-1`, `++`/`--`, peepholes |
| `02_division`, `05_unsigned_wrap` | division/modulo by zero, unsigned wrap |
| `03_shifts`, `21_assume` | shift ≥ width / negative, guarded shifts, `assume` bounds |
| `04_promotions`, `15_float_literals`, `16_float_ops` | integer promotions, float/double rounding, literals |
| `06_loops_closed`, `07_loops_continue`, `08_loops_nested`, `26_break_loop_opt`, `hang_*` | loops, break/continue, nested induction |
| `09_strlen` | strlen-style scans |
| `10_pointer_arith`, `11_aliasing`, `13_volatile` | pointer arithmetic, strict aliasing, volatile |
| `12_aggregates`, `24_bitfields` | struct padding, unions, bitfields (not lowered — LIMIT-3) |
| `14_uninitialized` | uninitialized/partially initialised reads |
| `17_math_calls`, `18_calls`, `19_invalid_c` | `math.h`, variadic/undeclared calls, invalid C |
| `20_wrapv`, `22_targets`, `27_check_default_cc` | `wrapv`, `c targets`/target selection, `check` limit |
| `mcp_c_targets`, `mcp_c_lower`, `mcp_c_optimize`, `mcp_c_errors` | MCP tool `c` ops and error handling |

No generated C files were left in the folder; all snippets are embedded blocks
and every rewrite command uses `nofile`. All work stayed inside
`tests/stress/areas/systems/cfront_fuzz/`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| HANG | 2 | — |
| LIMIT | 5 | — |
| DETERMINISM | 1 | — |

## Takeaway
The C frontend is robust across 400+ adversarial snippets — no crashes and no unsound rewrite was found, and every rewrite that could be differentially tested agreed with the original — but its loop summariser **does not terminate** on a `break` with an input-dependent bound or on a nested loop whose accumulator is `s++` (both `c lower`, the latter also `c optimize`), the `check` option is unusable with the host GCC because of a hardcoded clang-only UBSan flag, and `bench` output is inherently nondeterministic.

### Original takeaway (verbatim)

The C frontend is robust across 400+ adversarial snippets — no crashes and no
unsound rewrite was found, and every rewrite that could be differentially
tested agreed with the original — but its loop summariser **does not terminate**
on a `break` with an input-dependent bound or on a nested loop whose
accumulator is `s++` (both `c lower`, the latter also `c optimize`), the
`check` option is unusable with the host GCC because of a hardcoded clang-only
UBSan flag, and `bench` output is inherently nondeterministic.
