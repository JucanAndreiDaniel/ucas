#!/usr/bin/env python3
"""File arguments: valid, -q placement, multiple, spaces/Unicode in names, directory, missing, unreadable, /dev/null and /dev/stdin, early-abort.

Ported from cli_04_files.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS



def main():
    probe('file: single valid', '$B fixtures/good.ucas')
    probe('file: -q before file', '$B -q fixtures/good.ucas')
    probe('file: -q after file (only later files)', "$B fixtures/good.ucas -q 'fixtures/name with spaces.ucas'")
    probe('file: two valid files', "$B fixtures/good.ucas 'fixtures/name with spaces.ucas'")
    probe('file: name with spaces', "$B 'fixtures/name with spaces.ucas'")
    probe('file: unicode name', "$B 'fixtures/é-unicode.ucas'")
    probe('file: directory is silently empty', '$B fixtures/a_directory')
    probe('file: nonexistent', '$B /no/such/file.ucas')
    probe('file: unreadable (chmod 000)', '$B fixtures/unreadable.ucas')
    probe('file: good then bad (partial output)', '$B fixtures/good.ucas /no/such/file')
    probe('file: bad then good (early abort)', '$B /no/such/file fixtures/good.ucas')
    probe('file: /dev/null', '$B /dev/null')
    probe('file: /dev/stdin from pipe', "printf '5+5\\n' | $B /dev/stdin")
    probe('file: two directories', '$B fixtures/a_directory fixtures/a_directory')
    probe('file: empty-string name', "$B ''")
    probe('file: relative dot dir', '$B .')
    return 0


if __name__ == "__main__":
    sys.exit(main())
