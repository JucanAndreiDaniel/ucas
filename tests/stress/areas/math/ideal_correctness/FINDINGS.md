# ideal correctness

## Summary

Two families of fuzz reproducers used to hang for multi-minute durations:
Groebner bases of 4-variable quadratic systems over Q (lex and grevlex), and
the Smith form over Q[x] of dense 6x6 degree-4 polynomial matrices.  The
`LIMIT` guards in `src/ideal.c` now turn both into a documented refusal in a
few seconds; the small controls still produce full, verified results.

## Findings

- `LIMIT` — `01_groebner_lex_quadratic4`, `02_groebner_grevlex_quadratic4`:
  Buchberger's basis grows past 60 elements with S-polynomials of degree 20+
  (lex) or 90+ terms (grevlex).  Before the fix these ran past 120 s (and
  SymPy itself needs 30–118 s on the same systems).  They now report
  `Groebner basis: the computation grows too large: not done` in ~6 s.
- `LIMIT` — `03_pmsnf_6x6_deg4_a`, `04_pmsnf_6x6_deg4_b`: the polynomial
  fraction-free Smith reduction grows intermediate pivots to 12 000+ bits
  and degree 17+, so the run exceeded 180 s.  They now report
  `pmsnf: the polynomial coefficients grow too large: not done` in ~6–10 s.
- The pair-selection strategy for lex now orders S-pairs by total degree of
  the lcm ("sugar") before the monomial order.  This bounds the lex degree
  explosion (an lcm such as `w^100` is lexicographically small but enormous
  in degree) and does not change any basis or cofactor.

## Checks that passed

- The four reproducers terminate under `timeout 30` and produce a stable
  refusal instead of hanging.
- Controls `05`–`08` produce the complete reduced Groebner basis / Smith form
  with the printed certificates; each Groebner basis is verified by ucas
  itself (cofactor identity, reduction of every input, all S-pairs) and each
  Smith form by the `U A V = D` and invertibility checks.
- `bmake stress-test STRESS_AREA=ideal_correctness` is byte-stable across
  two consecutive runs under the canonical environment.
