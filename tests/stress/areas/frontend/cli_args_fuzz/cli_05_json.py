#!/usr/bin/env python3
"""--json mode: request flags (--dir, --files), -e one-shot, usage errors, repeated -e, malformed requests, stdin lines.

Ported from cli_05_json.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS

VARS['REQ'] = '{"id":1,"cmd":"parse","args":{"expr":"1+2*3"}}'
VARS['REQ2'] = '{"id":2,"cmd":"parse","args":{"expr":"9"}}'


def main():
    probe('json: no -e, stdin /dev/null', '$B --json </dev/null')
    probe('json: -e valid parse', "$B --json -e '$REQ' </dev/null")
    probe('json: --files none -e', "$B --json --files none -e '$REQ' </dev/null")
    probe('json: --files base64 -e', "$B --json --files base64 -e '$REQ' </dev/null")
    probe('json: --files both -e', "$B --json --files both -e '$REQ' </dev/null")
    probe('json: --files bogus -e (default write)', "$B --json --files bogus -e '$REQ' </dev/null")
    probe('json: --files no value', '$B --json --files </dev/null')
    probe('json: --dir nonexistent -e', "$B --json --dir /nonexistent-xyz-abc -e '$REQ' </dev/null")
    probe('json: --dir no value', '$B --json --dir </dev/null')
    probe('json: -e no value', '$B --json -e </dev/null')
    probe('json: unknown flag', '$B --json --wat </dev/null')
    probe('json: -e then extra positional', "$B --json -e '$REQ' foo </dev/null")
    probe('json: repeated -e (only last served)', "$B --json -e '$REQ' -e '$REQ2' </dev/null")
    probe('json: -e then --files none', "$B --json -e '$REQ' --files none </dev/null")
    probe('json: --files none then -e', "$B --json --files none -e '$REQ' </dev/null")
    probe('json: -e malformed JSON', "$B --json -e 'not json' </dev/null")
    probe('json: -e empty string', "$B --json -e '' </dev/null")
    probe('json: two stdin requests', "printf '%s\\n' '$REQ' '$REQ2' | $B --json --files none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
