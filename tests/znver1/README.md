<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The Zen+ measurement (host Ryzen 5 3550H)

`zen1` is the CPU microarchitecture of the host's Ryzen 5 3550H (Picasso).
The latencies in `src/x86data.c` come from `tools/x86bench.c`, compiled with
`-O2 -march=native` and run on this machine.  The tool times dependent rdtsc
chains and scales them by a one-cycle add chain, so the numbers are core
cycles independent of the TSC clock (raw scale factor 0.5673).  The raw run is
in `results/2026-11-16/x86bench.txt`.

`x86bench` covers add (1), imul (3), popcnt (1), pdep (21), vpaddd (1), vpshufb
(1), vpmulld (4), vaddps (3), vfmadd (5) and div64 (~11).  Classes it does not
cover start as copies of Zen 4 marked `Z` in the table.  This is not a complete
Zen+ instruction table; a full one needs uops.info or AMD's Zen SOG.  Zen+ has
no AVX-512, GFNI, VAES or VPCLMULQDQ; the generic x86v4-only classes are
cleared in `x86_init` along with the other non-V3 cores.
