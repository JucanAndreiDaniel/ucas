#!/usr/bin/env python3
"""--mcp mode: grouped vs --flat, --dir (chdir) and its failures, -- separator, early-return interaction with --json, UCAS_MCP_PROTO override.

Ported from cli_06_mcp.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS

VARS['INIT'] = '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}'
VARS['NOTIF'] = '{"jsonrpc":"2.0","method":"notifications/initialized"}'


def main():
    probe('mcp: no stdin', '$B --mcp </dev/null')
    probe('mcp: initialize (grouped)', "printf '%s\\n' '$INIT' '$NOTIF' | $B --mcp")
    probe('mcp: initialize --flat', "printf '%s\\n' '$INIT' '$NOTIF' | $B --mcp --flat")
    probe('mcp: --flat --flat', "printf '%s\\n' '$INIT' '$NOTIF' | $B --mcp --flat --flat")
    probe('mcp: --dir valid then initialize', "printf '%s\\n' '$INIT' '$NOTIF' | $B --mcp --dir fixtures/a_directory")
    probe('mcp: --dir then --flat', "printf '%s\\n' '$INIT' '$NOTIF' | $B --mcp --dir fixtures/a_directory --flat")
    probe('mcp: unknown flag', '$B --mcp --bogus </dev/null')
    probe('mcp: --dir nonexistent', '$B --mcp --dir /nonexistent-xyz-abc </dev/null')
    probe('mcp: --dir no value', '$B --mcp --dir </dev/null')
    probe('mcp: -- separator', '$B --mcp -- </dev/null')
    probe('mcp: --json after --mcp (usage)', '$B --mcp --json </dev/null')
    probe('mcp: UCAS_MCP_PROTO override', "printf '%s\\n' '$INIT' '$NOTIF' | UCAS_MCP_PROTO=2024-11-05 $B --mcp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
