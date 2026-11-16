<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The Zen 3 measurement (NAS Ryzen 7 5825U)

`zen3` is the CPU microarchitecture of the NAS's Ryzen 7 5825U (Cezanne).
The latencies in `src/x86data.c` come from `tools/x86bench.c`, compiled on the
host with `-O2 -march=native` (the resulting AVX2 binary runs on Zen 3) and
copied to the NAS.  The tool times dependent rdtsc chains and scales them by a
one-cycle add chain; the raw run is in `results/2026-11-16/x86bench.txt`
(scale factor about 0.45, normalize the figures by the add figure of 0.98 to
read core cycles).

Normalized latencies: add 1, imul 3, popcnt 1, pdep 3, vpaddd 1, vpshufb 1,
vpmulld 3, vaddps 3, vfmadd 4, div64 ~7.  Compared with Zen+, Zen 3 has a
fast PDEP/PEXT (3 vs 21 cycles), a 4-cycle FMA (vs 5) and a faster divider.
Classes `x86bench` does not cover start as copies of Zen 4 marked `Z` in the
table.  This is not a complete Zen 3 instruction table; a full one needs
uops.info or AMD's Zen 3 SOG.  Zen 3 has no AVX-512, GFNI, VAES or VPCLMULQDQ;
those classes are cleared in `x86_init`.
