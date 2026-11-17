#!/usr/bin/env python3
"""Python replacement for the sourced ``config_*.sh`` files.

In the original scripts ``build_parallel.sh`` and ``worker.sh`` did
``. "$BD/config_$name.sh"`` to obtain ``CC`` and ``FLAGS``.  Keeping the
per-variant data in an importable Python module preserves that separation
(one place to edit a variant) while removing the shell ``source``.  Both
converted callers import :data:`VARIANTS` and use ``FLAGS.split()`` to
reproduce bash's unquoted ``$FLAGS`` word splitting.
"""

VARIANTS = {
    "clang_O2":           {"CC": "clang", "FLAGS": "-O2"},
    "clang_O3_fastmath":  {"CC": "clang", "FLAGS": "-O3 -ffast-math"},
    "gcc_O2_fpmath":      {"CC": "gcc",   "FLAGS": "-O2 -mfpmath=sse -msse2"},
    "gcc_O2_noalias":     {"CC": "gcc",   "FLAGS": "-O2 -fno-strict-aliasing"},
    "gcc_O3_fastmath":    {"CC": "gcc",   "FLAGS": "-O3 -ffast-math -mfpmath=sse"},
}
