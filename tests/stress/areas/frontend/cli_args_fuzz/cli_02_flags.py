#!/usr/bin/env python3
"""Flag handling: -q, -y, -i, -h/--help, abbreviated, combined, -- separator, unknown flags, '=' forms.

Ported from cli_02_flags.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS



def main():
    probe('flag: -q with -e (echo irrelevant)', "$B -q -e '1+1'")
    probe('flag: -y with -e', "$B -y -e '1+1'")
    probe('flag: -i with -e', "$B -i -e '1+1'")
    probe('flag: -y -i -y sequence', "$B -y -i -y -e '1+1'")
    probe('flag: -h (help, head)', '$B -h | head -3')
    probe('flag: --help (head)', '$B --help | head -3')
    probe('flag: -h then extra args ignored', '$B -h --foo | tail -2')
    probe('flag: --help then unknown ignored', '$B --help --bogus | tail -2')
    probe('flag: abbreviated --js', '$B --js')
    probe('flag: abbreviated --sat', '$B --sat')
    probe('flag: combined -qe', "$B -qe '1+1'")
    probe('flag: combined -eq', "$B -eq '1+1'")
    probe('flag: -e=1+1 equals form', '$B -e=1+1')
    probe('flag: --json=1 equals form', '$B --json=1 </dev/null')
    probe('flag: -- separator', '$B --')
    probe('flag: single dash', '$B -')
    probe('flag: unknown --foo', '$B --foo')
    probe('flag: unknown -z', '$B -z')
    probe('flag: triple dash ---', '$B ---')
    probe('flag: empty-string argument', "$B ''")
    return 0


if __name__ == "__main__":
    sys.exit(main())
