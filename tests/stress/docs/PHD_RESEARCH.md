# PhD theses on testing solvers, compilers, and NLP — ideas for ucas

Companion to `RESEARCH.md`. These are doctoral dissertations; each section gives the source and the concrete
ucas experiment it suggests.

## Solver / SAT / SMT testing

| Thesis | Author, year, institution | Link | Core idea → ucas experiment |
|---|---|---|---|
| *Solidifying Modern SMT Solvers* | Dominik Winterer, 2024, ETH Zürich (advisors Müller, Christakis, Su) | [PDF](https://wintered.github.io/SolidifyingModernSMTSolvers.pdf), [news](https://ast.ethz.ch/ast-news/2024/11/congratulations-to-dominik-winterer-on-his-successful-phd-defense.html) | Led a campaign of 1,800+ bugs / 1,300+ fixes. Combines **Semantic Fusion** (fabricate formula pairs that are equal/unsat *by construction*) and **YinYang** with type-aware mutation. → Build fusion pairs of ucas functions guaranteed equal by a shared generator, then assert `equiv`. Exhaustively enumerate all expressions up to depth 3 over a tiny operator set (correctness **and** runtime), rather than sampling. |
| *Automatically Detecting and Mitigating Issues in Program Analysis Tools* (aka *Dependency-Aware Metamorphic Testing…*) | Muhammad Numair Mansur, 2023, TU Kaiserslautern | [PDF](https://kluedo.ub.rptu.de/files/7235/Phd_Thesis_Mansur.pdf), [overview](https://dl.gi.de/items/b23b5c7a-71ed-4a39-8f63-7265c3016182) | 55+ confirmed soundness bugs in SMT solvers and Datalog engines; **STORM** blackbox mutational fuzzing (seed fragmentation → formula generation → instance generation) and **dependency-aware** metamorphic testing. → Mutate *dependencies* consistently across both sides (swap `x`↔`y` in `f` **and** `g`), and fragment a seed expression into pieces before regenerating. Add **performance-regression** checks: flag equivalent reformulations that unexpectedly jump AIG nodes/conflicts or hit the 2 s budget. |
| *Stronger SMT Solvers for Proof Assistants* | (schurr.io, thesis PDF) | [PDF](https://schurr.io/pubs/phd-thesis.pdf) | Proof-producing solvers for proof assistants; soundness of proof reconstruction. → Stress ucas's `proofs` LCF kernel and `proof_check`: mutate proof trees and require rejection, check every proof-producing command independently. |
| *Efficient Sampling of SAT and SMT Solutions for Testing and Verification* (Berkeley tech report / related thesis work) | Berkeley group | [PDF](http://eecs.berkeley.edu/Pubs/TechRpts/2019/EECS-2019-167.pdf) | SMTSampler: sample diverse solutions for good coverage. → Generate diverse corner witnesses for `differ`/`wrap` and check each returned witness actually violates the claim. |

## Equivalence checking, compilers, fuzzing

| Thesis | Author, year | Link | Core idea → ucas experiment |
|---|---|---|---|
| *Blackbox Equivalence Checking of Program Optimizations* | Berkeley R. Churchill, 2019, UC Berkeley (Aiken) | [PDF](https://berkeleychurchill.com/research/phd_thesis.pdf), [PLDI'19 paper](https://theory.stanford.edu/~aiken/publications/papers/pldi19.pdf) | **Semantic program alignment**: align concrete traces of two programs to find divergences, then verify with a formal checker; bounded equivalence checking; superoptimizer guided by the checker. → Run `find`/`gates` candidate programs through an independent trace-alignment check on corner inputs, then confirm with `equiv`. This is a direct oracle for ucas's own rewriting/search. |
| *Abstractions and Algorithms for Specializing Dynamic Program Analysis and Random Fuzz Testing* | Rohan Padhye, 2020, UC Berkeley | [record](https://escholarship.org/uc/item/6r94r40b) | **PerfFuzz**: coverage-guided fuzzing specialised to generate *pathological, worst-case* inputs; **JQF**: coverage-guided property-based testing. → Generate expressions that maximise AIG node count / conflicts / search time to discover new give-up points; property-based tests for commutativity, associativity, distributivity, idempotence across all types. |

## Metamorphic testing

| Thesis | Author, year, institution | Link | Core idea → ucas experiment |
|---|---|---|---|
| *Automated and Effective Metamorphic Testing: Relation Discovery, Deduction, and Generation* | Congying Xu, 2026, HKUST | [portal](https://researchportal.hkust.edu.hk/en/studentTheses/automated-and-effective-metamorphic-testing-relation-discovery-de) | **MR-Scout** mined 11,000 MR-encoded tests from 701 projects; **MR-Adopt** (LLM) supplies missing input transformations (72% success); **MR-Coupler** uses functional coupling between methods to generate MRs (90% of programs, 22 real bugs). → Mine the 500+ existing `tests/*.ucas` files for implicit relations between statements, and exploit **functional coupling** between ucas commands (`range f` vs `differ f g` vs `wrap f`) as cross-command invariants. |
| *Metamorphic Testing Techniques to Detect Defects in Applications without Test Oracles* | Columbia University | [record](https://academiccommons.columbia.edu/doi/10.7916/D8765P5P/download) | General oracle-free MT. → Same as above; also invariant checks (`range` idempotence, `equiv` reflexivity/symmetry/transitivity, `find` cost monotonicity). |
| *Validating autonomous driving… / metamorphic testing* | Nottingham, 2025 | [PDF](https://research.nottingham.edu.cn/files/1713549069/20250515.PhD_Thesis_source.pdf) | Systematic MR construction and "oracle problem" treatment. → Use MRs as the primary oracle for stress tests where no expected output exists. |

## NLP robustness

| Thesis | Author, year, institution | Link | Core idea → ucas experiment |
|---|---|---|---|
| *Robustness in natural language processing* | Zhenhao Li, 2025, Imperial College London | [portal](https://spiral.imperial.ac.uk/entities/publication/8eea262c-9a6b-4581-a610-2c90ed0c6c4c) | Three robustness axes: **noisy text**, **textual adversarial attacks**, **unintended data bias**; `DiffuseDef` iteratively denoises hidden representations. → Noise-injection at graded rates into English queries; adversarial paraphrase; bias probes (does the NLP infer signedness/type from variable *names* or from "byte" without "unsigned"?). |
| *On robustness for natural language processing* | Emanuele La Malfa, 2023, University of Oxford | [ORA](https://ora.ox.ac.uk/objects/uuid:2aee14de-4ee5-402f-b9ca-24d57412c34d) | Formal/linguistic grounding of robustness to input variation. → Check invariance under meaning-preserving linguistic transformations at scale (extends `nlp_checklist`). |
| *Character-level Adversarial Robustness in NLP* | EPFL | [portal](https://infoscience.epfl.ch/entities/publication/20231bb1-7317-4a9b-acdd-1efe6cd123bd/thesisdetails) | Character-level attacks: homoglyphs, transpositions, visual confusables. → Feed Unicode homoglyphs / transposed letters into the English frontend; check graceful failure rather than misrouting. |
| *Adversarial Robustness of Language Models with Humans and Models in the Loop* | Max Bartolo, 2025, UCL | [record](https://discovery.ucl.ac.uk/id/eprint/10208031) | Human-in-the-loop adversarial attacks. → Curate a hand-adversarial set of English queries targeting ucas's specific vocabulary (odd/even, byte, range, log, i, e, pi). |
| *Evaluating and Improving the Robustness of LLMs to Input Sequence Variations* | 2026, arXiv thesis | [HTML](https://arxiv.org/html/2610.02432) | Prompt injection, trojans, input-sequence variation. → Prompt-injection strings in English mode must not make the frontend emit arbitrary ucas statements. |

## New cross-cutting ideas distilled from the theses

1. **Fusion pairs**: generate two expressions from one random *generator tree* by two different but provably
   equal emitters; `equiv` must prove them, `differ` must find nothing.
2. **Exhaustive small-expression enumeration**: enumerate every expression of depth ≤3 over `+ - * & | xor
   << >>` on `u4`, run `equiv`/`range` — bounded but complete for that fragment.
3. **PerfFuzz-style pathological search**: maximise AIG nodes/conflicts/time; record the new give-up boundary.
4. **MR mining from the existing test corpus**: treat `tests/*.ucas` as test cases embedding domain knowledge;
   derive relations automatically instead of hand-writing them.
5. **Functional coupling across commands**: `range f` must be consistent with `differ f g`, `wrap f` with
   `domain f`, `equiv f g` with `equiv g f` and transitivity over a chain.
6. **Bias/probe NLP tests**: vary variable names, capitalization, and the presence of `unsigned`; the parsed
   `ucas` statement must change only when the meaning changes.
7. **Noise-graded NLP**: insert k% character/word noise (k = 5, 10, 20, 40) and measure how quickly the parsed
   statement diverges from the clean baseline.
