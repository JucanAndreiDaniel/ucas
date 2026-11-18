# ecdivpoly torsion-field correctness

`px_ddf()` (src/ecisog.c) used to cap distinct-degree factorisation at degree
599 and return `-1` when a factor larger than that remained.  `cmd_ecdivpoly`
(src/ecff_isog.inc) compensated with a guess from the leftover degree: it
printed `torsion field: not determined` when it could not isolate one factor.
Both reproducers below hit that path; the n=59 one also hung for ~65 s because
the linear scan did one full Euclidean gcd at every candidate degree.

## Fixed behaviour

* `px_ddf()` now determines the degree of **every** irreducible factor.  It
  scans in blocks of 32 degrees, building one product
  `P = prod (x^(p^i) - x) mod f` per block and testing `gcd(P, f)` once; only
  a nontrivial block gcd triggers per-degree gcds, on the small isolated
  factor product.  The loop terminates only when the unfactored part is
  irreducible, so its degree is exact.  It never returns `-1`.
* `ecff_isog.inc` no longer has the leftover/`bigdeg` approximation and always
  prints the exact lcm of the factor degrees.
* Frobenius in `F_p[x]/(f)` is a linear combination of precomputed
  `x^(i p)`, and polynomial multiplication for small `p` uses a one-prime NTT;
  this brings `ecdivpoly [91,6] mod 179 59` down from ~65 s to ~16 s.

## Goldens

* `01_torsion_37_f5.ucas` — n=37 over F_5 (factor degree 684 > 599).
  `[2,1]` and `[3,3]` give torsion field F_5^684; `[1,1]` is the F_5^36
  control.
* `02_torsion_59_f179.ucas` — `[91,6] mod 179 59`, one degree-1740 factor,
  torsion field F_179^1740.  Old output: "not determined".
* `03_controls.ucas` — ordinary multi-factor cases (F_97^4, F_97^3), an even
  n, three equal degree-580 factors (F_101^580), and an inseparable
  `psi_7` (p | n).

Outputs were captured from the fixed binary; all factor-degree multisets were
independently checked with SymPy for 220 nonsingular cases (n <= 20).
