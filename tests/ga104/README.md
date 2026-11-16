<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The GA104 calibration run

`ga104` is NVIDIA's Ampere GA104, the GPU of the host's GeForce RTX 3060 Ti
(sm_86, driver 620.70.06, Vulkan 1.4.357).  The classes were measured by
running the GT 1030 corpus through ScarletNX's `snx-shaderperf`, the way
`../gt1030/run.py` does on a GT 1030.  `manifest.json` is a copy of that
corpus's manifest; the shaders and generator live in `../gt1030`.

## The run

From the ScarletNX build tree with `build/snx-shaderperf`:

```sh
python3 tests/gt1030/run.py \
  --sp /path/to/scarletnx/build/snx-shaderperf \
  --out tests/ga104/results/2026-11-16
```

The full corpus ran: 215 tests, including the latency builds, the graphics
stages and the I/O sweeps.  The GPU was idle apart from the shaders being
timed.  `report.md` lists every test's measured ratio and the fit's source
for each class; the `lat N clk` column is the latency build's clocks a step,
kept here for a future latency field in the model (ucas #546).

## What was fitted

24 of the 26 classes.  `bitcast` fitted to zero and `branch` below zero (a
branch's cost being absorbed by the other classes in the fit), so those keep
the parent `sm86` prices.  The parent also supplies the fusions, folds and
the classes the corpus does not fit.  The differences from `sm86`'s
estimates are the point of the measurement: integer add is full rate (1.13,
not 2), imul 1.70 not 2, integer division 19.26 not 28.5, fp64 61.68 not 64.

The fitted block is `results/2026-11-16/2026-11-16.model.ucas`, added to the
prelude as `model ga104 : sm86`.
