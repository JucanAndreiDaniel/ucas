<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The gfx902 calibration run

`run.py` times the GT 1030 corpus (`../gt1030/spv`, `../gt1030/manifest.json`) on the host's
AMD Radeon Vega 8 iGPU (gfx902, in a Ryzen 5 3550H) and fits ucas's cost classes from it, the
way `../gt1030/run.py` does on a GT 1030.  The corpus maths, the interleaved runs and the fit
are the GT 1030 script's, imported from it; only the transport differs: the local
`snx-shaderperf` is asked for the AMD device by name.

## The device

PCI `1002:15d8` (Picasso/Raven 2), 8 GCN5 CUs, wave 64, 64 KiB LDS, UMA DDR4-2400.
Verified with `lspci`, `/proc/cpuinfo` (Ryzen 5 3550H), and the Vulkan device line
(`warp size: 64, int dot: 0, matrix cores: none`). Read-bandwidth ceiling ~37.9 GB/s.

## The run

```sh
tests/gfx902/run.py --out tests/gfx902/results/$(date +%F)
```

This is an UMA iGPU sharing memory with the desktop; keep other GPU load closed.  Latency
builds are skipped (the `KHR_shader_clock` SM-clock path is NVIDIA-specific); `load`,
`store`, `branch` and `diverge` come from throughput tests alone.  Some NVIDIA-only tests
(e.g. `sg_partition`, `atomic_global_f32`) fail on this driver and are excluded from the fit.
