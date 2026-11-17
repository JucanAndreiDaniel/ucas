# SUMMARY — `trig_identity_sweep`

## Counts
- Distinct expressions/queries tried: 59
- Goldens written: 11
- Files created: not recorded

### Coverage
- **Distinct identities / queries tried:** 59 symbolic identities (46 true + 13 deliberately
  false) + 134 special-point evaluations/branch checks + ~90 property/calculus/parser probes
  (CLI) + 17 MCP calls = **~300 distinct expressions/queries**, all checked against an independent
  `mpmath` 1.3.0 oracle at 50–60 decimal digits where applicable.
- Areas covered: `sin²+cos²`, double/half/triple-angle, addition & subtraction, sum-to-product,
  product-to-sum, Pythagorean/tan/atan, inverse-trig branch behaviour (`asin(sin x)`,
  `acos(cos x)`, `atan(tan x)` at multiples of `pi/2` and `pi`), tan/atan identities, hyperbolic
  analogues (`sinh/cosh/tanh` and `asinh/acosh/atanh`), degree/radian conversions (`45°`,
  `45 deg`, `45 degrees`), exact values at special angles, `taylor`/`diff`/`antiderivative`/
  `integrate`, limits at singularities, and `period`/`parity`/`bounded`/`zeros`/`asymptotes`/
  `continuity`/`domain`/`range`/`identify`/`equiv`.

### Files created (all in `tests/stress/areas/math/trig_identity_sweep/`)
- 11 CLI golden pairs: `01_pythagorean` … `11_equiv_float_WRONG` (`.ucas` + `.out`).
- 1 MCP golden: `mcp_trig_identity.jsonl` + `mcp_trig_identity.out` (17 calls across
  `algebra`, `properties`, `calculus`).
- `FINDINGS.md`, `SUMMARY.md`.
- `_scratch/`: local harnesses (`harness.py`, `evalharness.py`, `make_files.py`), probes and
  raw outputs (not goldens).
- All 12 goldens: exit 0 under `timeout 30`, byte-identical on two consecutive runs (deterministic).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | — |
| NLP | 1 | — |
| LIMIT | 1 | — |

### Issues by severity
- **CRASH / HANG:** 0
- **WRONG:** 4
  - F1 `limit` of `sec`/`1/cos`/`csc`/`cot` at singularities → huge finite value instead of `±inf`/DNE
    (own check says `DISAGREES`; MCP structured `limit.kind:"number"`).
  - F2 `asymptotes`/`continuity`/`discontinuities` miss poles on default range (`tan` misses `±pi/2`,
    `1/sin` misses `±2pi,±3pi`); bounded range finds them.
  - F3 `equiv` on real functions reports false "differ" with equal-looking witnesses (`1 vs 1`).
  - (F1 and F2 share a root cause family: float substitution/grid scanning near singularities.)
- **WRONG (false-difference):** included above (F3).
- **NLP:** 1 — F4 `sech/csch/coth/arcsinh/arccosh/arctanh` silently parsed as multiplication;
  `limit coth(x) x -> 0` then errors with a confusing multi-variable message.
- **LIMIT:** 1 — F5 `simplify` fails to reduce ~15 true trig/hyperbolic identities to 0.
- **DETERMINISM:** 0 (all retained goldens are stable; no nondeterminism observed).


## Takeaway
Exact values, branch handling and ordinary identity simplification are sound, but `limit` at non-exact-float singularities and pole/discontinuity enumeration on the default range produce confidently WRONG answers (the former even flagged `DISAGREES` by the tool's own numeric check), and `equiv` on reals reports false differences — all captured as deterministic reproducers.

### Original takeaway (verbatim)
Exact values, branch handling and ordinary identity simplification are sound, but `limit` at
non-exact-float singularities and pole/discontinuity enumeration on the default range produce
confidently WRONG answers (the former even flagged `DISAGREES` by the tool's own numeric check),
and `equiv` on reals reports false differences — all captured as deterministic reproducers.

### Folder confirmation
All files were written only under `tests/stress/areas/math/trig_identity_sweep/`. No source files, Makefile,
`opencode.json`, shared files, or other subagents' folders were touched; no `make`, `git`, or
unbounded runs were performed.
