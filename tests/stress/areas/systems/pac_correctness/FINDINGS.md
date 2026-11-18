# PAC / Nullstellensatz certificate correctness

## Summary

ucas's `proof NAME` prints an LCF kernel proof outline. This area covers the
optional algebraic proof certificates added on top of it, following Kaufmann
& Biere (AMulet2, STTT 2023) and the DRUP+PAC certificate practice of keeping
externally produced proof steps independently checkable and attributed.

## Findings

- `proof NAME ns` emits a concise Nullstellensatz-style certificate: the
  algebraic steps of the kernel proof, each written as cofactors `a_i` over
  premise relations `g_i` with `f = sum a_i*g_i` (`KR_LIN`), plus ring
  normalizations where a relation reduces to zero (`KR_CONV`). It is emitted
  only when every term canonicalizes to a polynomial over Z; otherwise the
  output says `not supported` rather than claiming a certificate.
- `proof NAME pac` emits the expanded PAC-style step proof: one line per kernel
  inference, with cofactors on the combination steps.
- `proof NAME cert` emits both, alongside the unchanged default proof text.
- `check NAME cert` re-checks the certificate with the independent checker in
  `kcheck.c` (canonical polynomial arithmetic, not `knorm.c`).
- `check NAME cert broken N` corrupts step N and the checker names that step
  and the faulty cofactor, instead of printing a bare `FAILED`.

## Checks that passed

- All four goldens are byte-stable across repeated canonical runs
  (`UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`, run from this directory).
- The default `proof NAME` and `check NAME` output is unchanged; the existing
  `proof_kernel_axioms` and `prove_symbolic` areas still pass.
- Valid certificates (combination and ring-normalization) verify.
- Corrupted combination and ring steps are localized to their step number.
