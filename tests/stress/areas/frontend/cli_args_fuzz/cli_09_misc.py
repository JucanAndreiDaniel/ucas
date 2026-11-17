#!/usr/bin/env python3
"""Misc residual CLI cases: Unicode/CJK values, '=' forms in sub-modes, --dir pointing at a non-directory, help/schema early-return with extra input, --flat changing the MCP tool list, repeated -e in --json, env override.

Ported from cli_09_misc.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS

VARS['REQ'] = '{"id":1,"cmd":"parse","args":{"expr":"5"}}'
VARS['REQ2'] = '{"id":2,"cmd":"parse","args":{"expr":"6"}}'
VARS['REQ3'] = '{"id":3,"cmd":"parse","args":{"expr":"7"}}'
VARS['INIT'] = '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}'
VARS['NOTIF'] = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
VARS['LIST'] = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'


def main():
    probe('misc: unicode ident é in -e', "$B -e 'é'")
    probe('misc: CJK ident in -e', "$B -e '表=1'")
    probe('misc: sin(pi/2) in -e', "$B -e 'sin(pi/2)'")
    probe('misc: --files=none equals form', "$B --json --files=none -e '$REQ' </dev/null")
    probe('misc: --mcp --flat=1 equals form', '$B --mcp --flat=1 </dev/null')
    probe('misc: --mcp --dir is a file', "$B --mcp --dir 'fixtures/name with spaces.ucas' </dev/null")
    probe('misc: -h with stdin piped', "printf '2+2\\n' | $B -h | head -2")
    probe('misc: --json-schema extra flag', '$B --json-schema --files none | head -c 60')
    probe('misc: --json triple -e (only last)', "$B --json -e '$REQ' -e '$REQ2' -e '$REQ3' </dev/null")
    probe('misc: mcp grouped tool-name count', 'printf \'%s\\n\' \'$INIT\' \'$NOTIF\' \'$LIST\' | $B --mcp | tail -1 | grep -o \'\\"name\\"\' | wc -l')
    probe('misc: mcp --flat tool-name count', 'printf \'%s\\n\' \'$INIT\' \'$NOTIF\' \'$LIST\' | $B --mcp --flat | tail -1 | grep -o \'\\"name\\"\' | wc -l')
    probe('misc: -e newline-only value', "$B -e $'\\n\\n'")
    probe('misc: -q -q -q then -e', "$B -q -q -q -e '1+1'")
    probe('misc: -e with filenames as text', "$B -e 'fixtures/good.ucas'")
    probe('misc: --files none w/ newline value', "$B --json --files \\$'none\\nfoo' -e '$REQ' </dev/null")
    probe('misc: bare stdin 1000 stmts', 'python3 -c \'print(\\";\\".join([\\"3\\"]*1000))\' | $B | tail -2')
    probe('misc: -e 500 pi terms', '$B -e \\"\\$(python3 -c \'print(\\"pi+\\"*499+\\"pi\\")\')\\"')
    probe('misc: --mcp --dir then bad flag', '$B --mcp --dir fixtures/a_directory --bogus </dev/null')
    probe('misc: --json --dir then bad flag', '$B --json --dir fixtures/a_directory --bogus </dev/null')
    probe('misc: -e then -q then --foo', "$B -e '1+1' -q --foo")
    probe('misc: --sat-selftest behind -h', '$B -h --sat-selftest | tail -2')
    return 0


if __name__ == "__main__":
    sys.exit(main())
