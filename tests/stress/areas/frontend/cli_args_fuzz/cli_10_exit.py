#!/usr/bin/env python3
"""Exit-status audit: statement-level errors and failed JSON requests all return exit 0 (only file-open / usage / flag errors return nonzero).

Ported from cli_10_exit.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS



def main():
    probe('exit: -e syntax error', "$B -e '1+'")
    probe('exit: -e unknown name (auto-var)', "$B -e 'foobar'")
    probe('exit: file with syntax error', '$B fixtures/bad.ucas')
    probe('exit: file with unknown name', '$B fixtures/undef.ucas')
    probe('exit: stdin syntax error', "printf '1+\\n' | $B")
    probe('exit: --json bad_json one-shot', "$B --json -e 'garbage' </dev/null")
    probe('exit: --json error request', '$B --json -e \'{\\"id\\":1,\\"cmd\\":\\"range\\",\\"args\\":{\\"f\\":\\"x\\",\\"var\\":\\"x\\"}}\' </dev/null')
    probe('exit: good then bad-statement file', '$B fixtures/good.ucas fixtures/bad.ucas')
    probe('exit: file-open error (control)', '$B /no/such/file')
    probe('exit: usage error (control)', '$B --json --bogus')
    return 0


if __name__ == "__main__":
    sys.exit(main())
