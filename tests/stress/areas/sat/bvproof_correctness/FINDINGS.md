# Summary

Machine-checkable bit-vector proof objects for `equiv`, and a word-level
ring-identity fast path for multiply-heavy machine functions.

Sources adopted: Hadarean, *Bit-Vector Proofs in CVC4* (NYU thesis, ch. 6)
for the two-tier miter + resolution certificate; Liew, *A Path Paved by
Proof Complexity Towards Verifying Nonlinear Integer Arithmetic* (UW 2020)
for the succinct word-level polynomial proof of multiplier identities.

# Findings

- **CHECKS (pass)**: `equiv` now emits `checks[]` with `aig_miter`,
  `aig_model` (SAT) or `drup_refutation` (UNSAT), and attaches a
  `bvproof.cert` file. The certificate is rechecked inside ucas by a
  standalone unit-propagation replay, and again by `verify_bvproof.py`
  against the inline base64 copy (`json_04_certificates.out`).
- **CHECKS (pass)**: `x*3 == x+x+x` on u32 is proved by the ring fast path:
  identical polynomial normal forms over Z plus 4096 sampled tuples (8 values
  per parameter, not an exhaustive domain check), with no AIG and no SAT call.
  The checks `ring_identity_normal_form` and `ring_identity_small_domain`
  report it.
- **FIX (critical)**: the DRUP replay's conflict test was inverted in both
  checkers (all-unassigned was taken for a conflict). A single empty clause
  then "proved" any SAT miter UNSAT. The C `rv_propagate()` and the Python
  `propagate()` now require all assigned literals to be false (including the
  empty clause), and unit propagation requires exactly one unassigned
  literal. `test_regression.py` checks that a SAT CNF never conflicts and
  that a one-empty-clause refutation of a SAT miter is rejected.
- **FIX (high)**: the ring fast path no longer treats same-width float↔int
  casts as bit-preserving; such casts fall back to SAT, and the sampled guard
  refuses them too. The certificate hash serialises its fields little-endian
  so the independent checker agrees on every host.
- **LIMIT**: the fast path covers +, -, *, neg, constants and parameters of
  one machine width. Shifts, division, `where`, floats and lanes fall back
  to bit-blasting (`04_ring_fallback.out`).
- **LIMIT**: the top-level `proof.kind`/`text` wording for a fast-path proof
  still comes from `analyze.c` (`"sat"`, "proved by SAT: 0 AIG nodes"); the
  new evidence is in `checks[]`, `notes[]`, `sat.why` and the certificate
  file. Those files are outside this area's ownership.

# Checks that passed

- `STRESS_AREA=bvproof_correctness`: 8 paired goldens, no diffs.
- `python3 verify_bvproof.py json_04_certificates.out`: PASS for both the
  model and the DRUP certificate.
- `STRESS_AREA=sat_crypto_circuits` and `STRESS_AREA=witness_verification`:
  see `SUMMARY.md` for the recapture outcome.
