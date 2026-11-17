#!/usr/bin/env python3
"""Emit an MCP JSONL request for a 150x150 sparse (identity) matrix.

Usage:
  python3 repro_mcp_large_sparse.py > /tmp/mlarge.jsonl
  timeout 30 $ROOT/ucas --mcp < /tmp/mlarge.jsonl > /tmp/mlarge.out 2>&1
  tail -c 300 /tmp/mlarge.out

The CLI handles this matrix fine (`zmat rank` -> 100 for the 100x100 case,
150 for this one); the MCP argument->ucas serializer truncates the statement
at ~52 KB and the parser reports a nonsensical `bigint: unexpected ""`.
"""
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
import json
import sys

n = 150
M = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
lines = [
    json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "stress", "version": "1"}}}),
    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "abstract_algebra",
                           "arguments": {"op": "zmatrix",
                                         "args": {"op": "rank", "matrix": M}}}}),
]
sys.stdout.write("\n".join(lines) + "\n")
