<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The gp107 calibration run

`run.py` times the GT 1030 corpus (`../gt1030/spv`, `../gt1030/manifest.json`) on the host's
NVIDIA GeForce GTX 1050 3 GB (GP107, Pascal sm_61) and fits ucas's cost classes from it, the
way `../gt1030/run.py` does on a GT 1030.  The corpus maths, the interleaved runs and the fit
are the GT 1030 script's, imported from it; only the transport differs: the local
`snx-shaderperf` is asked for the NVIDIA device by name.

## The device

PCI `10de:1c91` (GP107-301), 6 SMs / 768 cores, 96-bit GDDR5 3 GiB, warp 32.
Verified with `nvidia-smi -q` (Product Architecture Pascal, compute capability 6.1,
3072 MiB, 2075 MHz) and `lspci`. 84 GB/s spec bandwidth.  GP107 is the same Pascal
sm_61 through SPIR-V as the GT 1030 (GP108) this project's prelude model was
measured on, so only the memory-stream classes need rescaling.

## The run

```sh
tests/gp107/run.py --out tests/gp107/results/$(date +%F)
```

The SM clock is read from `nvidia-smi` after the run.  Some corpus tests may not
fit on this older Pascal driver and are excluded from the fit; the runner writes
`results.json`, the fitted `gp107.model.ucas`, and the report.
