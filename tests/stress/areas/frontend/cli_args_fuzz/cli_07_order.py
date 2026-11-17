#!/usr/bin/env python3
"""Ordering and early-return interactions: which flag wins, and what is ignored.

Ported from cli_07_order.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS

VARS['REQ'] = '{"id":1,"cmd":"parse","args":{"expr":"1"}}'


def main():
    probe('order: --json then --mcp', '$B --json --mcp </dev/null')
    probe('order: --mcp then --json', '$B --mcp --json </dev/null')
    probe('order: file then --json (stdin null)', '$B fixtures/good.ucas --json </dev/null')
    probe('order: file then --mcp (stdin null)', "printf '' | $B fixtures/good.ucas --mcp")
    probe('order: -q then --json', "$B -q --json -e '$REQ' </dev/null")
    probe('order: -i then --json', "$B -i --json -e '$REQ' </dev/null")
    probe('order: --json then -e', "$B --json -e '$REQ' </dev/null")
    probe('order: --mcp then --flat', "printf '' | $B --mcp --flat")
    probe('order: -e then -h then -e', "$B -e '1+1' -h -e '2+2' | head -2")
    probe('order: -h then -e', "$B -h -e '1+1' | tail -2")
    probe('order: --foo before --sat-selftest', '$B --foo --sat-selftest')
    probe('order: -e then --foo (error after)', "$B -e '1+1' --foo")
    probe('order: -q after --json flag', "$B --json -q -e '$REQ' </dev/null")
    probe('order: two -q then file', '$B -q -q fixtures/good.ucas')
    probe('order: --flat before --mcp (file)', '$B --flat --mcp </dev/null')
    probe('order: -e after --json-schema', "$B --json-schema -e '$REQ' | head -c 80")
    return 0


if __name__ == "__main__":
    sys.exit(main())
