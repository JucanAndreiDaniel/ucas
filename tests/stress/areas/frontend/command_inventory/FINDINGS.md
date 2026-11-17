# Stress findings — `command_inventory`

_Original heading: command_inventory — findings_

# command_inventory — findings

Scope: every top-level `ucas` command (CLI), cross-checked against the
`tests/stress/*` areas and the `tests/*.ucas` corpus.  All 30 golden files below
were run twice under `timeout 15` and were byte-identical, exit 0.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | `banks` reports a bogus "largest index 0" for an unbounded u32 index |
| LIMIT | 1 | bare `mma` / `hmma` is a >15 s search with no early progress output, and writes a file int… |

## Findings

### WRONG-1 — `banks` reports a bogus "largest index 0" for an unbounded u32 index
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'banks lane xor 3'
```

**Observed:** output (exact):

```
banks under gt1030: 32 banks of 4 bytes, a warp of 32 lanes, 4-byte elements; a shared load 3, each further address on a bank +4
  index = lane xor 3
    lane parameter lane; conflict degree 1: sampled: 4096 of the cases, the degree is at least this (not a bound)
    price 3
  array size taken as 32 (the largest index 0, in whole rows of 32; `size N` to say)
  -> no swizzle searched: a degree above is not exact (give the parameters ranges small enough to enumerate)
```

The same incorrect "largest index 0" appears for `banks lane xor (lane >> 4)`
and for `banks (lane >> 4)` (golden `01_banks.out`).  `lane` is an unrestricted
`u32`, so the largest value of `lane xor 3` is 4294967295 and that of
`lane >> 4` is 268435455; reporting 0 is an interval-analysis failure (it looks
like an overflowing/unsigned-wrap of an unbounded upper bound to 0).
**Expected:**
either the true maximum or an explicit "unknown" — not 0, which would make a
reader size the shared array as one element.  The `size N` option suppresses
the misleading line, so the damage is limited to the informative text.

### LIMIT-1 — bare `mma` / `hmma` is a >15 s search with no early progress output, and writes a file into the CWD
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
timeout 15 ./ucas -e 'mma'          # exit 124, 0 bytes of output
timeout 15 ./ucas -e 'hmma'         # exit 124, 8.7 KB of partial output
```

**Observed:** `timeout 15 ucas -e 'mma'` exits 124 with **zero** bytes on stdout;
`hmma`, `mma all` and `mma validate` print the dataflow table but are still
running at 15 s.  An untruncated run (`timeout 45 ./ucas -e 'mma'`) finished
with exit 0 after roughly 30–45 s (8488 dataflows) and created
`mma_m16n8k16_f32.glsl` in the current directory (removed during this run to
respect folder confinement).

Not a hang and not a crash — `tests/mma.out` is a 97 KB golden for this command —
but a bare invocation gives no progress indication for over 15 s and has a
filesystem side effect unless `nofile` is given.  No golden was kept for it.

## Checks that passed

### Non-findings worth recording
- No crash, signal, truncated output or nondeterminism was observed in any of
  the 30 gap-area golden files (223 CLI statements).
- The FOCUS words `eval`, `vals`, `sub`, `reportall`, `ntheory`, `gif`, `dot`,
  `emit`, `viz` are **not** top-level CLI commands: the reader treats them as
  ordinary free variables and prints an anonymous function, e.g.
  `_sub: real) = sub`.  `sub` is not an alias either (the algebra module's
  alias is `subst`); `viz` is the name of the plotting module
  (`area`/`revolve`/`volume`/...), not a command.  See `29_noncommands.ucas`.
- `tabulate` is an **English/NLP** starter word, translated by `nlp.c` into
  `ucas: table it`; it is not a CLI command.  `29_noncommands.out` captures the
  translation and the resulting table.
- `saturate` is an option of `find`, and `sink`/`advice`/`assume` are options
  of `spvsimplify` (or `simplify`), not standalone commands; they are covered
  in `23_saturate.ucas` and `14_spvsimplify.ucas`.
- `state`, `reset`, `assume`, `schema` are JSON/MCP tools (`jsonmode.c`), and
  `forget` is an NLP preference reset — none are CLI commands.
- `c optimize`, `c lower`, `c targets` are handled at the source-line level by
  the C frontend (`cf_cmd.c`), not by the normal command parser.
