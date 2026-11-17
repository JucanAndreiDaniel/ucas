<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The gfx90c calibration run

`run.py` times the GT 1030 corpus (`../gt1030/spv`, `../gt1030/manifest.json`) on the NAS's
AMD Radeon Vega 8 iGPU (gfx90c, in a Ryzen 7 5825U) and fits ucas's cost classes from it, the
way `../gt1030/run.py` does on a GT 1030.  The corpus maths, the interleaved runs and the fit
are the GT 1030 script's, imported from it; only the transport differs: snx-shaderperf runs
inside the llama-swap Docker container on the NAS, driven over ssh.

## The device

PCI `1002:15e7` (Barcelo), 8 GCN 5.1 CUs, wave 64, 64 KiB LDS, UMA DDR4-3200.
Verified with the NAS host's `lspci`, `/proc/cpuinfo` (Ryzen 7 5825U), and the Vulkan
device line inside the container (`RADV RENOIR`, `warp size: 64`, `int dot: 0`,
`matrix cores: none`). Read-bandwidth ceiling ~45.1 GB/s.
Earlier local notes calling this part gfx1032 (RDNA2) were wrong: RDNA2 reports
wave 32 / RADV VANGOGH; the part is GCN 5.1 / wave 64.

## The device binary and corpus transport

`snx-shaderperf` links Vulkan headers and opens the loader at run time, so the host build
runs unchanged in the container (Ubuntu/glibc 2.43).  It is copied to
`/tmp/lb/snx-shaderperf` in the container with `docker cp`, and the corpus SPIR-V to
`/tmp/lb/cal/spv`.  On the NAS host, `/var/ucas-cal/spwrap.sh` maps `spv/` paths to
those container paths and runs each timing via `docker exec`.  The host has numpy for the
fit; the container does not, so the Python side never runs there.

## The run

```sh
tests/gfx90c/run.py --out tests/gfx90c/results/$(date +%F)
```

Latency builds are skipped (NVIDIA-specific SM-clock path).  NVIDIA-only corpus tests
fail on this driver and are excluded from the fit.  This is an UMA iGPU sharing memory
with the NAS services; keep other GPU load closed.
