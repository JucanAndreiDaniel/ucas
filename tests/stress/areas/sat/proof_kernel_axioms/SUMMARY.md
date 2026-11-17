# SUMMARY — `proof_kernel_axioms`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 7
- Files created: 16

### Original preamble

Focus: LCF proof-kernel axiom accounting via MCP `proofs` (theorem / prove /
proof / proof_check / axioms / lemmas) and the matching CLI commands.

### Counts

* **Distinct theorem/proof sequences tried:** 156 generated statements
  (92 in `/tmp/gen_theorems.py` + 64 in `/tmp/gen_more.py`) plus ~46 ad-hoc
  probes (automatic-kinds probe batch, 26 adversarial edge cases, multi-route
  bockstein/naming experiments) — **200+ statements**, each cross-checking
  `proof T`'s "axioms used", `axioms T`, `check T` / `proof_check`, prove status,
  and the printed proof tree. All runs under `timeout 15`.
* **Category coverage:** simple tautologies/reflexivity, linear integer
  arithmetic, abelian-group equalities, subgroup membership, imported library
  theorems, diagram chases / exactness, nested proofs, deliberately false
  claims, plus malformed/adversarial inputs.
* **Files created (16):**
  * CLI goldens: `01_axiom_overreport.{ucas,out}`,
    `02_group_axioms.{ucas,out}`, `03_linarith_axioms.{ucas,out}`,
    `04_library_route.{ucas,out}`, `05_false_claims.{ucas,out}`
  * MCP goldens: `mcp_axiom_accounting.{jsonl,out}`,
    `mcp_proof_routes.{jsonl,out}`
  * `FINDINGS.md`, `SUMMARY.md`
* **Issues by severity:** WRONG 1 · LIMIT 2 (one NLP-flavoured) · CRASH 0 ·
  HANG 0 · DETERMINISM 0.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | — |
| LIMIT | 2 | — |

## Takeaway
The kernel's `proof` axiom accounting is internally consistent and sound, but `axioms NAME` systematically over-reports axioms (`ipow_zero`/`ipow_succ`/ `ipow_neg`, often `int_discrete`) for conversion-based proofs — even for `forall x:int: x = x` — so the two public views of "which axioms a proof uses" disagree; no crash, hang, check disagreement, or unsound proof was found.

### Original takeaway (verbatim)

The kernel's `proof` axiom accounting is internally consistent and sound, but
`axioms NAME` systematically over-reports axioms (`ipow_zero`/`ipow_succ`/
`ipow_neg`, often `int_discrete`) for conversion-based proofs — even for
`forall x:int: x = x` — so the two public views of "which axioms a proof uses"
disagree; no crash, hang, check disagreement, or unsound proof was found.
