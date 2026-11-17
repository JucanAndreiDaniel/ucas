# Focused + wild testing ideas (second literature sweep)

Sources (2026 unless noted):

- **Racer — Hunting GPU Kernel Bugs with Symbolic Equivalence Checking** (Vu & Tan, arXiv 2610.28429):
  <https://arxiv.org/html/2610.28429> — 82 real bugs in 2,408 production kernels. Key insight: *differential
  testing compares numbers, correctness is a statement about functions*. Execute both programs over symbolic
  inputs, get exact algebraic expressions, subtract, ask CAS to simplify to zero; use exact numeric refutation
  at rational points when inconclusive; reuse proofs across output cells by a verified variable renaming
  ("shape reduction"). Also: bugs hidden *below the floating-point tolerance* cannot be found by sampled
  differential testing.
- **cas-testing.org / GEMM** (Cyber Tester): <https://cas-testing.org/?list=6> — a CAS black-box testing
  methodology: a precomputed DB of **10,000+ known-tricky examples**, ~20,700 textbook problems, automated
  verification of `int, limit, factor, series, taylor, residue, sum, product, simplify` over *all elementary
  and special functions*, plus a monitor that schedules test units to maximise bug discovery. Each finding:
  minimise, double-check, locate first bad version, give a short proof it IS a bug, classify.
- **Compiler Testing Part 1 — Coverage-Guided Fuzzing with Grammars and LLMs** (nowarp, 2026):
  <https://nowarp.io/blog/compiler-testing-part-1> — 100+ bugs in production compilers, all *structurally
  valid* inputs. Tools: AFL++ `afl-ts` tree-sitter custom mutator (`ts-del`, `ts-bank`, `ts-swap`, `ts-shrink`,
  `ts-lit`, `ts-dup`, `ts-ins`, `ts-kdel`, `ts-kins`, `ts-stutter`), `tsgen` grammar-based seed generation,
  identifier renaming (`v0`, `v1`, …) to avoid "undeclared variable" noise, fuzzing dictionaries from grammar
  tokens and previous crashes, corpus minimisation, crash dedup by backtrace callsite, grammar-aware reduction
  (perses/treereduce/LLM). WhiteFox/GapForge: use docs, coverage gaps, `git blame` and **previous findings** to
  generate seeds. MetaMut/Mut4All/IssueMut: LLM synthesises hundreds of language-specific mutators from bug
  reports; validate by rejecting ones that only produce parse errors.
- **Discovering discrepancies in numerical libraries** (ICSE 2020): 655 discrepancies, 125 bugs across GSL,
  mpmath, SciPy, jmat — cross-library differential at controlled precision.
- **MF++ metamorphic fuzzing** (ETH): 21 previously-unknown bugs in numerical libraries; derived operations
  from Boolean algebra (De Morgan etc.).

## Focused ideas for ucas

1. **Symbolic-difference oracle** — for two `int`/`real` expressions, compute `expand(f - g)` and require it to
   simplify to 0; when inconclusive, substitute exact rational points (Python `Fraction`) to refute. This is a
   *different* oracle from ucas's `equiv` (which uses SAT on machine types) and can catch the unsound `equiv`
   cases already found. Add proof reuse: if a claim holds for `f(x,y)`, check renamed variants `f(y,x)`,
   `f(x+1,y)` structurally before asking the engine again.
2. **Below-tolerance float bugs** — build pairs differing by an epsilon-scale logic error (e.g. `1/rstd^2 + eps`
   vs `- eps`) and check whether `error`/`equiv` can see them; sampled comparison with tolerance cannot.
3. **Known-tricky CAS corpus** — assemble a corpus from the literature (integrals with singular endpoints,
   limits at essential singularities, `limit sin(n)/n`, divergent-looking convergent series, zero polynomials,
   `simplify` identities) and run *every* symbolic command over every elementary/special function.
4. **Mutators learned from our own findings** — feed each `FINDINGS.md` entry to an LLM to invent a mutator
   ("apply the same shape in a different command/type/context"), validate that mutated inputs still parse, and
   keep the ones that reach semantic passes. This turns the bug catalog into a generator.
5. **Grammar-aware corpus + dictionaries** — seed from `tests/*.ucas`, rename identifiers uniformly to `v0..`,
   build a token dictionary (operators, types, boundary literals `0, -1, MIN, MAX, 2^63, 2^64, NaN payloads`),
   and apply tree-style mutations (delete/swAP/shrink/duplicate/insert/kill-insert/stutter at the statement and
   subexpression level). Dedupe findings by root cause and minimise with the existing ddmin reducer.
6. **Coverage-gap seeding** — build with coverage instrumentation in a scratch folder, find source lines/branches
   never hit by `make test` + the stress corpus, and generate inputs targeting exactly those gaps.
7. **Cross-library float differential** — compare ucas `f32`/`f64`/`real` results against mpmath/SciPy at high
   precision across elementary/special functions and their singular points.
8. **Triage passes** — dedupe the master findings by root cause, separate parser-stack-overflow noise from
   genuine semantic bugs, and re-verify each WRONG claim independently before treating it as confirmed.

Note: the compiler-fuzzing literature explicitly dismisses "5000 nested parens" parser crashes as not worth
reporting. For a "newborn monkey" robustness goal we deliberately keep them — but they should be triaged
separately from semantic bugs.
