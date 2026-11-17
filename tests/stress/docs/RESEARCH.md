# More ways to stress the SAT and NLP sides (literature →ucas recipes)

Sources consulted (all reachable online; dates as of 2026):

- Winterer, Zhang, Su — *On the Unusual Effectiveness of Type-Aware Operator Mutations for Testing SMT
  Solvers* (OOPSLA 2020): <https://arxiv.org/html/2004.08799v4> — OpFuzz. 1,092 bugs reported in Z3/CVC4,
  819 confirmed, 184 soundness bugs. Key idea: mutate operators **within conforming types** so mutants stay
  well-typed, then differentially test.
- Brummayer, Lonsing, Biere — *Automated Testing and Debugging of SAT and QBF Solvers* (SAT 2010):
  <https://cca.informatik.uni-freiburg.de/papers/BrummayerLonsingBiere-SAT10.pdf> — grammar-based random
  generation plus **delta debugging** to minimize failing formulas; finds crashes, invalid models, wrong SAT
  results. (Same authors, AIG-fuzzing/multiplier-verification follow-up:
  <https://danielakaufmann.at/publication/2022_tap/slides.pdf>.)
- *CAST: Continuous Fuzzing for SMT Solvers* (PLDI 2026):
  <https://pldi26.sigplan.org/details/pldi-2026-src/14/CAST-Continuous-Fuzzing-for-SMT-Solvers> — put
  differential testing + type-aware mutation into CI.
- Komarov — *Compiler Testing Part 2: Metamorphic Testing with Verified Identities* (2026):
  <https://nowarp.io/blog/compiler-testing-part-2> — hand-written + synthesized equivalence-preserving
  mutations, stacked, with corner-valued inputs. Rich source of concrete identities (see below).
- Ribeiro et al. — *Beyond Accuracy: Behavioral Testing of NLP Models with CheckList* (ACL 2020):
  <https://arxiv.org/html/2005.04118v1>, <https://github.com/marcotcr/checklist> — **MFT** (minimum
  functionality), **DIR** (directional expectation), **INV** (invariance under meaning-preserving changes).
- *Adversarial misspellings / robust word recognition*: <https://www.researchgate.net/publication/335780501_Combating_Adversarial_Misspellings_with_Robust_Word_Recognition>;
  AdversNLP guide: <https://openreview.net/forum?id=hq9lK3QsRm>.
- SAT Competition benchmark notes on how bit-blasted multipliers become hard:
  <https://fmv.jku.at/papers/Biere-SAT-Competition-2016-benchmarks.pdf>; and *Associativity of Multiplication
  Is Hard for Resolution* (2026): <https://arxiv.org/html/2610.08988> — explains why `x*y` vs `y*x` and
  associativity are exactly the right SAT stress patterns.

## Techniques not yet in the initial 16-agent swarm

### 1. Verified metamorphic identities as an oracle (highest value)

Instead of checking a single answer, assert that two expressions that are equal by construction stay equal
according to ucas (`equiv`, `prove`, `range`). Sources of identities: Hacker's Delight, TAOCP, Bit Twiddling
Hacks (<https://graphics.stanford.edu/~seander/bithacks.html>), MBA/obfuscation literature.

Concrete identities to feed `equiv` on u8/u16/u32/u64/iN:

```
x + x            == x << 1
x - x            == 0
x ^ x            == 0
(x & y) + (x ^ y) == x | y          # addition as xor + carry
(x ^ y)          == (x | y) - (x & y)
~x               == -x - 1         # two's complement
~(x & y)         == ~x | ~y        # De Morgan
x & (x | y)      == x              # absorption
(x ^ C) ^ C      == x              # self-cancellation against a constant
x * 0            == 0
x << k >> k      == x & (MAX >> k)
(a + b)^2        == a^2 + 2ab + b^2   (on `int`/finite ranges only)
isqrt(x)^2 <= x < (isqrt(x)+1)^2
```

**Stack** several identity rewrites onto one seed expression and assert the result still equals the seed —
the nowarp post found real miscompilations from 4–5 stacked rewrites. Divergence between `equiv` (SAT) and
`equiv` on a narrowed/exhaustively enumerable type is a strong bug signal.

### 2. Type-aware operator mutation + differential testing *within ucas*

You do not need a second solver: ucas already has several independent proof paths
(`proof.kind`: `exhaustive`, `sat`, `symbolic`, `numeric`). OpFuzz-style recipe:

1. Start from a seed function with typed params (e.g. `f(x: u16, y: u16) = (x & y) + ((x xor y) >> 1)`).
2. Replace one operator by another of the same type/signature (`+`↔`-`, `&`↔`|`, `xor`↔`+`, `<`↔`<=`,
   `*`↔`mod`, `>>`↔`<<`), keeping the expression well-typed.
3. Ask `equiv f mutant`. Then independently check the claim by exhaustive enumeration on a small type
   (`u4`/`u8`) or by a narrowed range, and compare the two answers.
4. Also compare CLI vs JSON vs MCP on the *same* request, and grouped MCP vs `--flat` MCP.

Any disagreement, crash, or `ok:true` on a malformed mutant is a bug. OpFuzz used 200–400 mutations per
seed in practice.

### 3. Fingerprint-based identity synthesis (cheap oracle)

Enumerate small random expressions over a few variables and constants, evaluate them on a **fixed battery of
corner valuations** — `0, 1, -1, MIN, MAX`, type boundaries, plus seeded random points — and hash the result
vector. Structurally different terms that collide are candidate identities: ask ucas `equiv` to prove or
refute each. Refutation where the fingerprint agreed = either a fingerprint blind spot or an unsound `equiv`.
This scales to hundreds of candidates cheaply.

### 4. Delta debugging / minimization (ddmin)

When a crash/hang is found, shrink it automatically: repeatedly remove statements, operators, or parameters
(and re-run under `timeout`) until removing any further piece makes the bug disappear. Applies to `.ucas`
files, `.jsonl` request streams, and English queries. The literature stresses that bugs reduce to small
formulas but reduction is itself challenging — worth a dedicated pass after the swarm reports.

### 5. Grammar-based generative fuzzing

Build a small generator for well-typed ucas expressions (type-directed, bottom-up, bounded depth), with a
token/operator distribution biased toward the hard corners: wide multipliers, variable shifts, division,
`match`/tables, float bit-casts. Coverage-guided fuzzing was the subject of the companion post
<https://nowarp.io/blog/compiler-testing-part-1>. Pair it with the corner-valuation battery above.

### 6. CheckList-style NLP testing (MFT / DIR / INV)

For the English frontend, do not just throw typos at it. Build three test categories:

- **MFT (minimum functionality):** a minimal phrase per supported intent ("what is the range of isqrt(x: u4)",
  "does this overflow", "is f equal to g", "find 2 cheaper implementations"). Failure = not understood.
- **DIR (directional expectation):** rephrasings that must *increase/decrease* something, e.g. adding
  "with a narrower range" must not increase the sampled point count; "cheapest" must return cost <= "cheap".
- **INV (invariance):** meaning-preserving transformations must yield the identical parsed statement and
  answer. Synonyms (`times`/`multiplied by`, `square`/`x squared`, `range`/`how big can`), politeness
  ("please", "could you"), extra whitespace/punctuation, capitalization, and word order where grammar allows.
  Compare the `ucas` field returned by MCP `english` before and after the transformation.

Add **negation pairs** ("is f equal to g" vs "is f different from g") and **adversarial misspellings**
(`comutative`, `chebysev`, `polynomaial`) — the latter are already in `nlp_arith`/`nlp_calculus`.

### 7. Wire-level/protocol differential (already partly covered)

Grouped MCP (`analyze`, op in args) vs `--flat` MCP (op as tool name) vs `--json` CLI vs plain CLI on the
same statement: all must agree. The repo already has `tests/mcp/flat.flags`; extend it to more ops.

### 8. Put it in CI

`tests/stress/run.sh` is the seed for CAST-style continuous fuzzing: add a small, fast subset to `make test`
(or a nightly job) and keep the heavy/hang-prone reproducers in `FINDINGS.md` only.
