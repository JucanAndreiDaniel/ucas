#!/usr/bin/env python3
"""Generate a 120x120 integer determinant statement (~56 KB) that ucas
zmatrix rejects with a confusing 'parse_error' (truncated matrix) rather
than the clean 'too long for me' that rings.matrix returns.

Usage:
  python3 repro_large_det.py > repro_large_det.ucas
  timeout 30 $ROOT/ucas repro_large_det.ucas 2>&1 | head -c 500
"""
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
n = 120
M = [[str((i*31 + j*17 + 1) % 997 + 1) for j in range(n)] for i in range(n)]
print("zmat det [" + ",".join("[" + ",".join(row) + "]" for row in M) + "]")
