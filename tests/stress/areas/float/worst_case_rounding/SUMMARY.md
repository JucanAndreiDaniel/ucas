# SUMMARY — `worst_case_rounding`

## Counts
- Distinct expressions/queries tried: 406
- Goldens written: 28
- Files created: 27

### What was done

Built a 200-bit mpmath oracle (`oracle.py`) that rounds the exact image of
`exp/log/sqrt/sin/cos/1-x` at an exact f16/f32/f64 input to IEEE
binary16/32/64 (ties-to-even, subnormals, overflow).  Its rounding was validated
against Python's correct `mpf->float` conversion (0/4000 mismatches) and the key
results re-checked at 1000 bits.  `gen.py` generated **406 adversarial inputs**
via 200-bit root-finding at rounding midpoints, published Lefèvre/Muller
worst-case constants, targeted f64->f32/f16 double-rounding constructions,
tie midpoints and neighbours, subnormal/normal boundaries, and large-argument
sin/cos.  Every input was fed to ucas as `show asuint(EXPR)` and compared to the
oracle (`cases.json`, `gen_report.txt`).

Extra probes: ~15 equivalence/identity queries (`equiv` on exp-log,
sin^2+cos^2, float narrowing identities) and a 30 000-input brute-force search
for an `equiv` counterexample.

### Counts

- Distinct curated expressions/queries tried: **406** cases + **~15** extra
  `equiv`/identity probes (plus 60 000 exploratory narrowing evaluations).
- Oracle comparison: **368 MATCH**, **33 WRONG** (numeric), **5 UNEVAL**.
- Files created: 27 `.ucas` + 28 `.out` (CLI goldens), 1 `.jsonl` + 1 `.out`
  (MCP golden), `gen.py`, `oracle.py`, `cases.json`, `gen_report.txt`,
  `FINDINGS.md`, `SUMMARY.md` (62 files).
- Every golden was run twice and `diff`ed: all deterministic (no
  nondeterminism found).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 33 | — |

### Issues by severity

| Severity | Count | Summary |
|---|---|---|
| WRONG | 33 numeric + 1 equivalence | 3 host-libm 1-ulp errors (2 published worst cases, 1 large-argument sin); 30 double-rounding errors (24 f64->f32, 6 f64->f16); `equiv` says `equal:true` with a concrete witness |
| LIMIT | 1 class | float division overflowing to inf stays unevaluated (5 inputs) |
| CRASH / HANG / DETERMINISM | 0 | — |


## Takeaway
ucas evaluates f64 transcendentals with the host libm and f32/f16 by rounding that f64 result again, so at Table-Maker's-Dilemma inputs it returns 1-ulp-wrong values (including on two published worst cases) and double-rounding errors for 30 constructed inputs; `equiv` also claims equality for float functions where a concrete double-rounding witness exists.

### Original takeaway (verbatim)

ucas evaluates f64 transcendentals with the host libm and f32/f16 by rounding
that f64 result again, so at Table-Maker's-Dilemma inputs it returns 1-ulp-wrong
values (including on two published worst cases) and double-rounding errors for
30 constructed inputs; `equiv` also claims equality for float functions where
a concrete double-rounding witness exists.
