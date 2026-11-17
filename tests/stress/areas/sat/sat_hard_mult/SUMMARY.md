# SUMMARY — `sat_hard_mult`

## Counts
- Distinct expressions/queries tried: 266
- Goldens written: 12
- Files created: not recorded

### Original preamble

**Expressions / queries tried:** ~266 distinct expressions/queries.
- 186 systematic pairs (xor/mask/shift under multiplication swap; 3/4-operand product
  permutations and associations; `(x*x) xor (y*y)` and xor-vs-add; low-bit mod 2^k
  identities; i/u 8,16,32,64 commutation and bit-mixing; 8 magic constants incl.
  multiply-xor-shift; Horner/nested multiply-add; polynomial vs bit forms; u8..u24
  exhaustive-vs-give-up sweep).
- ~80 targeted probes (domain-restricted `where`, mixed signedness/width, `prove`,
  `differ`, `cost`, f32 multiplication/ftz, malformed MCP args, crash minimization,
  MCP/flat-mode queries).

### Files created (all inside this folder):
- 12 CLI goldens: `01_...ucas` .. `12_...ucas` + matching `.out`
  (exhaustive, algebra-proved, SAT-proved, two give-up shapes, budget boundary,
  magic constants, nested multiply-add, xor squares, restricted domains, mod 2^k,
  signed wide).
- 3 MCP goldens: `mcp_equiv_fields.{jsonl,out}`, `mcp_domains.{jsonl,out}`,
  `mcp_flat.{jsonl,out}` + `mcp_flat.flags` (`--flat`).
- `FINDINGS.md`, `SUMMARY.md`.
- All 15 goldens were generated from their own directory under `timeout` and verified
  deterministic by running twice and `diff` (identical). No crash/hang is kept as a
  golden.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| LIMIT | 5 | — |

### Issues by severity:
- CRASH: 1 — `equiv` SIGSEGV on a >=786-factor u32 product (CLI **and** `--mcp`);
  threshold n=786, n<=785 OK. Stable partial output documented, not golden.
- WRONG: 0 — no `equal:true` contradicted by the Python oracle (no unsoundness found).
- HANG: 0 — apparent hangs were scheduler contention; isolated runs finish (give-ups
  ~15 s).
- DETERMINISM: 0 — all kept outputs stable across repeated runs.
- LIMIT: 5 — (a) give-up boundary mapped (exhaustive<=u11; low masks 1/3 bits SAT-proved,
  >=8-bit masks give up; AIG counts deterministic); (b) `^` is power not xor, `differ`
  is not an op and is silently misparsed, raw-string MCP `equiv` fails to parse;
  (c) `equiv` crosses signedness and compares only "domain of a" (bounding-box note
  misleading); (d) give-ups cost ~15 s so long MCP batches hit client timeouts;
  (e) malformed args are rejected, `timeout_s:-5` silently ignored.


## Takeaway
`equiv` is sound and deterministic on 266 hard-multiplication queries (proved by algebra/SAT or honestly "sampled, not proved"), but it segfaults on large AIGs (~786 chained factors) and has a sharp, structure-dependent SAT give-up boundary plus several parsing/semantics footguns (`^`, `differ`, cross-type domains).

### Original takeaway (verbatim)
`equiv` is sound and deterministic on 266 hard-multiplication
queries (proved by algebra/SAT or honestly "sampled, not proved"), but it segfaults on
large AIGs (~786 chained factors) and has a sharp, structure-dependent SAT give-up
boundary plus several parsing/semantics footguns (`^`, `differ`, cross-type domains).
