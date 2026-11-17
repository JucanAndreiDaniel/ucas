# Analysis — dd_diff_isolation

- pairs run: 247
- valid (pass=PASS, fail=FAIL, dd succeeded): 247
- invalid/skipped: 0
- total distinct ucas oracle calls (cached): 1138
- NOTE: `nesting_crash` minimal counts fluctuate +/-1 between runs because the binary's depth-1525 crash boundary is nondeterministic (FINDINGS.md §7); all other classes are byte-stable.

## Minimal flip per bug class

### conflation (16 pairs)
- undefined_name: 16 pairs; minimal-change counts {1: 16}; signatures: `del:'('` x16

### english_of (44 pairs)
- command_the: 12 pairs; minimal-change counts {1: 12}; signatures: `del:'the'` x12
- fraction_please: 32 pairs; minimal-change counts {1: 32}; signatures: `del:'please'` x32

### equiv_cast (39 pairs)
- result_coercion: 39 pairs; minimal-change counts {1: 13, 2: 26}; signatures: `del:'+'` x13, `del:'+'|del:'2'` x13, `del:'+'|del:'3'` x13

### equiv_signed (28 pairs)
- reinterpret: 28 pairs; minimal-change counts {1: 7, 2: 21}; signatures: `del:'+'` x7, `del:'+'|del:'2'` x7, `del:'+'|del:'3'` x7, `del:'+'|del:'4'` x7

### equiv_where (104 pairs)
- body_coincide: 40 pairs; minimal-change counts {2: 40}; signatures: `del:'+'|del:'1'` x8, `del:'+'|del:'2'` x8, `del:'+'|del:'3'` x8, `del:'+'|del:'4'` x8
- narrow_bound: 64 pairs; minimal-change counts {2: 64}; signatures: `del:'10'|ins:'5'` x8, `del:'20'|ins:'7'` x8, `del:'16'|ins:'8'` x8, `del:'30'|ins:'12'` x8

### nesting_crash (16 pairs)
- paren_depth: 16 pairs; minimal-change counts {25: 3, 126: 2, 75: 2, 526: 1, 326: 1, 425: 1, 225: 1, 176: 1, 276: 1, 6: 1, 45: 1, 376: 1}; signatures: `ins:'(' x25` x3, `ins:'(' x126` x2, `ins:'(' x75` x2, `ins:'(' x526` x1

## Normalized root-cause clusters (cross-class)

- **delete additive offset (+N) in G body -> bodies coincide** — 107 pairs across 3 finding group(s): equiv_cast/result_coercion, equiv_signed/reinterpret, equiv_where/body_coincide
- **replace G where-bound with a smaller value (narrow G's domain)** — 64 pairs across 1 finding group(s): equiv_where/narrow_bound
- **delete trailing "please" ("of" preposition parse)** — 32 pairs across 1 finding group(s): english_of/fraction_please
- **insert N extra "(" tokens (cross recursion depth 1525)** — 16 pairs across 1 finding group(s): nesting_crash/paren_depth
- **delete "(" so b definition fails / b becomes undefined** — 16 pairs across 1 finding group(s): conflation/undefined_name
- **delete leading "the" (command-word recognition)** — 12 pairs across 1 finding group(s): english_of/command_the

## Root-cause clustering (exact minimal flip across classes)

- `del:'please'` — 32 pairs across: english_of/fraction_please
- `del:'+'|del:'2'` — 28 pairs across: equiv_cast/result_coercion, equiv_signed/reinterpret, equiv_where/body_coincide
- `del:'+'|del:'3'` — 28 pairs across: equiv_cast/result_coercion, equiv_signed/reinterpret, equiv_where/body_coincide
- `del:'+'` — 20 pairs across: equiv_cast/result_coercion, equiv_signed/reinterpret
- `del:'('` — 16 pairs across: conflation/undefined_name
- `del:'+'|del:'4'` — 15 pairs across: equiv_signed/reinterpret, equiv_where/body_coincide
- `del:'the'` — 12 pairs across: english_of/command_the
- `del:'10'|ins:'5'` — 8 pairs across: equiv_where/narrow_bound
- `del:'20'|ins:'7'` — 8 pairs across: equiv_where/narrow_bound
- `del:'16'|ins:'8'` — 8 pairs across: equiv_where/narrow_bound
- `del:'30'|ins:'12'` — 8 pairs across: equiv_where/narrow_bound
- `del:'12'|ins:'3'` — 8 pairs across: equiv_where/narrow_bound
- `del:'15'|ins:'9'` — 8 pairs across: equiv_where/narrow_bound
- `del:'25'|ins:'4'` — 8 pairs across: equiv_where/narrow_bound
- `del:'18'|ins:'11'` — 8 pairs across: equiv_where/narrow_bound

## Reduction that changes the bug (oracle sensitivity)

- Ran BOTH a strict oracle and a verdict-only oracle (`are equal` in output) on 18 equiv pairs. 18/18 reductions changed under the loose oracle.
  - verdict-only minimal flip `del:'1'` on 4 pairs
  - verdict-only minimal flip `del:'2'` on 4 pairs
  - verdict-only minimal flip `del:'3'` on 4 pairs
  - verdict-only minimal flip `del:'4'` on 3 pairs
  - verdict-only minimal flip `del:'5'` on 3 pairs
  - In these cases deleting the single digit `1` leaves a dangling `+` (`x+` / `i32(x)+` / `i8(x)+`), which is a parse error: the definition of `g`/`b` fails to parse and `equiv` then reports `are equal` via the *undefined-function-name* bug. The minimized input therefore no longer exhibits where-ignoring / result-coercion / signed-reinterpretation — reduction changed the bug into a different one.

With a symptom-only oracle (`are equal` in the output), the 16 conflation pairs reduce to: `del:'('` x16. The minimized input deletes the definition of `b`, so `equiv a b` reports `are equal` via the *undefined-function-name* bug — a different root cause than signed/unsigned reinterpretation or where-clause ignoring. A verdict-only oracle therefore merges (and can mutate) several unrelated findings; the strict oracles above keep them separate.
