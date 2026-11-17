# SUMMARY — `prove_symbolic`

## Counts
- Distinct expressions/queries tried: ~262
- Goldens written: 32
- Files created: 32

### Counts

- **Distinct statements/queries tried:** ~262
  - 120 generated linear-arithmetic implication theorems (brute-force ground truth)
  - ~98 CLI statements across `theorem`/`prove`/`proof`/`check`/`axioms`,
    `equiv`, `closed`, `expand`/`simplify`/`solve`, `identify`/`symmetry`
  - 44 MCP calls across `proofs` (theorem/prove/proof/proof_check/axioms/lemmas),
    `analyze equiv`, `properties`, `calculus closed`/`integrate`, `session define`
  - plus ad-hoc exploration probes (overflow boundary search, malformed inputs,
    deep exponents) not kept as goldens.
- **Golden files written:** 32 (16 CLI `.ucas`/`.out` pairs — 10 topic files
  plus the 120-theorem fuzz batch — and 5 MCP `.jsonl`/`.out` pairs), plus
  `FINDINGS.md` and `SUMMARY.md` = **34 files**, all inside
  `tests/stress/areas/sat/prove_symbolic/`.
- **Determinism:** every would-be golden was run twice and `diff`ed; all matched.
  No nondeterministic/timing-dependent output was kept.
- **Exit codes:** every golden run exited 0 under `timeout 30`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | equiv over real rejects a true polynomial identity; identify gives degree (1,1) for the zero bivariate polynomial; axioms NAME over-reports  |
| NLP | 1 | documented MCP equiv on raw expressions is a parse error (named functions required) |
| LIMIT | 2 | bare error: for integer literals ≥ 2^63−8; linear-only automation rejects true/nonlinear/existential claims (even an axiom instance) |

### Issues by severity

| Severity | Count | Short description |
|----------|-------|-------------------|
| WRONG    | 4     | `equiv` over `real` rejects a true polynomial identity; `identify` gives degree (1,1) for the zero bivariate polynomial; `axioms NAME` over-reports vs `proof NAME`; numeric `identify` invents properties of `sin^2+cos^2-1` |
| LIMIT    | 2     | bare `error:` for integer literals ≥ 2^63−8; linear-only automation rejects true/nonlinear/existential claims (even an axiom instance) |
| NLP      | 1     | documented MCP `equiv` on raw expressions is a parse error (named functions required) |
| CRASH    | 0     | — |
| HANG     | 0     | — |
| DETERMINISM | 0  | — |


## Takeaway
The LCF kernel and its linear-arithmetic/polynomial-normalisation automation are sound on everything exercised (120 fuzzed implications, false polynomial claims all rejected, no crashes/hangs), but the user-facing layers are not: `equiv` and `identify` let floating-point noise overturn mathematically true identities, and `axioms NAME` disagrees with `proof NAME` about which axioms a proof uses.

### Original takeaway (verbatim)

The LCF kernel and its linear-arithmetic/polynomial-normalisation automation are
sound on everything exercised (120 fuzzed implications, false polynomial claims
all rejected, no crashes/hangs), but the user-facing layers are not: `equiv`
and `identify` let floating-point noise overturn mathematically true
identities, and `axioms NAME` disagrees with `proof NAME` about which axioms a
proof uses.
