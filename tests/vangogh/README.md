<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Copyright 2026 the ScarletNX contributors -->
# The VANGOUGH calibration run

`vangogh` is AMD's Custom GPU 0932 in the Steam Deck (gfx10.3 / RDNA2, RADV
with Mesa 26.x).  The classes were measured by running the GT 1030 corpus
through ScarletNX's `snx-shaderperf`, imported to the Deck under
`/tmp/opencode` (the binary and a Python 3.14 numpy/BLAS tree for the runner;
nothing was installed system-wide).  `manifest.json` is a copy of the corpus
manifest; the shaders and generator live in `../gt1030`.

## The run

From the Deck, with `PYTHONPATH`/`LD_LIBRARY_PATH` pointing at the local
numpy and BLAS:

```sh
python3 gt1030/run.py \
  --sp /tmp/opencode/ucas-proper-data/snx-shaderperf \
  --out /home/deck/.cache/ucas/deck-gpu-compute \
  --only "$(cat compute-only.txt)" --no-io
```

`compute-only.txt` holds the 145 tests whose names do not begin `vert_`,
`geom_` or `frag_`.  The graphics-stage tests cannot be timed here: the corpus
passes each stage shader pair twice to `snx-shaderperf`, and RADV reports
negative or zero differences for them, which crashed the fit.  Two tests
fail outright in every run: `sg_partition`/`sg_partitioned_add` (unsupported
NV subgroup extension) and `atomic_global_f32` (`ACO ERROR: Unsupported
opcode: buffer_atomic_add_f32`).  No I/O sweeps were run.

The fit was repeated independently (`deck-gpu-compute-rerun`); every shipped
class reproduced within about 1 percent.  `vangogh` uses the mean of the two
fits.  The report's `lat N clk` column is the latency build's clocks a step,
kept for a future latency field in the model (ucas #546).

## What was fitted

22 of the 26 classes.  `logic` and `bitcnt` fit near zero because the LOP3 and
BMI fusions absorb them; `bitcast` fitted to zero and `branch` below zero.
Those four keep the parent `rdna2` prices, which also supplies the fusions,
folds and unmeasured classes.  The fitted block is
`results/2026-11-16/2026-11-16.model.ucas`, added to the prelude as
`model vangogh : rdna2`.
