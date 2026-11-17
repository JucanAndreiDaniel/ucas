#!/usr/bin/env python3
"""Emit an MCP JSONL request with a 120x120 matrix argument. Through
`ucas --mcp` this returns parse_error (statement silently truncated);
the same matrix run as a CLI .ucas file succeeds with det = 0.

Usage:
  python3 repro_mcp_large_det.py > repro_mcp_large_det.jsonl
  timeout 30 $ROOT/ucas --mcp < repro_mcp_large_det.jsonl 2>&1 | tail -c 400
"""
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
import json
n = 120
M = [[str((i*31 + j*17 + 1) % 997 + 1) for j in range(n)] for i in range(n)]
lines = [
 {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}},
 {"jsonrpc":"2.0","method":"notifications/initialized"},
 {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"abstract_algebra","arguments":{"op":"zmatrix","args":{"matrix":M,"op":"det"}}}},
]
print("\n".join(json.dumps(l) for l in lines))
