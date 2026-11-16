<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The Zen 2 measurement

`zen2` is the CPU microarchitecture of both the host's Ryzen 5 3600 and the
Steam Deck's Custom APU 0932.  The latencies in `src/x86data.c` come from
`tools/x86bench.c`, compiled with `-O2 -march=native` and run on both machines.
The tool times dependent rdtsc chains and scales them by a one-cycle add
chain, so the numbers are core cycles independent of the TSC clock; the raw
scale factors differ (about 0.92 on the host, 1.38 on the Deck).  The two runs
agree on the normalized latencies, which is why one model serves both cores.

`results/2026-11-16/` keeps both runs and the divider probe.  The probe found
two divider paths: with RDX=0, which is what compilers emit for a 64-bit
divide with zero upper bits, the latency is about 10 cycles on the host and
12 on the Deck; with a full 128-bit dividend it is 40.90 and 42.12.  The table
uses the full-width worst case (41), ucas's `zen4` convention.  `MULX` is 3
cycles, so a division by a constant (`idivk`) is 4.

Classes `x86bench` does not cover (load, store, conversion, bitcast, fdiv,
fsqrt, atomics) use `llvm-mca -mcpu=znver2` scheduling latencies, and the
remaining columns and classes start as copies of Zen 4 marked `Z` in the
table.  This is not a complete Zen 2 instruction table: a full one needs
uops.info or AMD's Zen 2 SOG.  Zen 2 has no AVX-512, GFNI, VAES or
VPCLMULQDQ; those classes are cleared in `x86_init`.
