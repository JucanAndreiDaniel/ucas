# Historical / foundational papers (and the ucas ideas they suggest)

- **Miller, Fredriksen & So — *An Empirical Study of the Reliability of UNIX Utilities***, CACM 33(12), 1990
  ([PDF](https://gwern.net/doc/cs/security/1990-miller.pdf)) — the original fuzzing paper: feed random input to
  programs; 25–33% of utilities crashed. Introduced `fuzz`. → Our `parser_json_fuzz`/`resource_limits` are the
  modern version; keep the "random + boundary-literal + Unicode" triple.
- **McKeeman — *Differential Testing for Software***, Digital Technical Journal 10(1), 1998 — formalised running
  the same input through sibling implementations and diffing. → Cross-frontend (CLI/JSON/MCP/flat) and
  cross-build (gcc/clang, -O levels) differential.
- **Chen, Cheung & Yiu — *Metamorphic Testing: A New Approach for Generating Next Test Cases***, HKUST-CS98-01,
  1998 ([arXiv reprint](https://arxiv.org/abs/2002.12543)) — derive *new* test cases from *successful* ones by
  transformations that should preserve the verdict. → `metamorphic_identities`, `thesis_mr_mining`,
  `nlp_checklist` are direct descendants.
- **Claessen & Hughes — *QuickCheck: a lightweight tool for random testing of Haskell programs***, ICFP 2000
  ([PDF](https://cs.tufts.edu/~nr/cs257/archive/john-hughes/quick.pdf)) — properties + type-directed random
  generators + shrinking. → Algebraic-law properties (reflexivity/symmetry/transitivity of `equiv`, range
  idempotence, `find` cost monotonicity) with random generation and ddmin shrinking.
- **Hildebrandt & Zeller — *Simplifying failure-inducing input***, ISSTA 2000 / IEEE TSE 2002
  ([summary](https://debuggingbook.org/html/DeltaDebugger.html)) — `ddmin` shrinks one failing input; the
  generalized `dd` **isolates the difference between a passing and a failing input**. → We used `ddmin` in
  `grammar_fuzz_reduce`; `dd` on *pairs* of ucas inputs is still unexplored.
- **King — *Symbolic Execution and Program Testing***, CACM 19(7), 1976 — execute over symbolic inputs. →
  Modern form in Racer (see FOCUSED_IDEAS.md) and in `symbolic_diff_exact`.
- **Pnueli, Siegel & Singerman — *Translation Validation***, 1998 (also Necula's *Translation validation for an
  optimizing compiler*, PLDI 2000) — validate each compiler run by proving source and target equivalent, rather
  than trusting the compiler. → Every `find`/`gates`/`c optimize` rewrite should be independently validated;
  check that ucas does this per rewrite and reports a failure instead of silently emitting an unproved form.
- **Barr et al. — *The Oracle Problem in Software Testing: A Survey***, IEEE TSE 2015
  ([PDF](https://eecs481.org/readings/testoracles.pdf)) — taxonomy of oracles; metamorphic relations are one
  way to avoid needing an expected output. → Most stress findings use MRs because ucas has no external oracle.
- ***A practical approach to testing random number generators in computer algebra systems***, arXiv 2004.08913
  ([PDF](https://arxiv.org/pdf/2004.08913)) — CAS stochastic components need statistical testing. → ucas's
  `find`, `stoke`, `approx`, `numsearch` use randomness: check seed control, reproducibility, distribution of
  witnesses, and that `timeout_s` forked children do not share/corrupt RNG state.
- **arXiv 1312.3270** — authors detected a Mathematica determinant error while doing mathematics; illustrates
  that CAS bugs surface on ordinary inputs, not just adversarial ones. → Determinant/matrix identities
  (`det(AB)=det(A)det(B)`, singular matrices, integer matrices mod n) as a focused linear-algebra oracle.

## Themes worth carrying forward

1. **Classic fuzz triad**: random input + grammar structure + boundary literals (`0, ±1, MIN, MAX, 2^63, 2^64`).
2. **Properties over cases**: assert invariants rather than expected outputs.
3. **Two-input reduction (`dd`)**: find the minimal *difference* that flips a verdict.
4. **Per-rewrite validation**: treat `find`/`c optimize` output as a translation that must be checked.
5. **Statistical validation of stochastic commands**: reproducibility, seed control, witness distribution.
6. **Ordinary-input bugs**: include a corpus of everyday mathematical expressions, not only adversarial ones.
