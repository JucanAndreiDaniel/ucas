#!/usr/bin/env python3
"""Basic -e evaluation: arithmetic, empty strings, repeated -e, whitespace, Unicode/constant names, newlines, comments, semicolons.

Ported from cli_01_eval.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS



def main():
    probe('e: 1+1', "$B -e '1+1'")
    probe('e: empty string', "$B -e ''")
    probe('e: whitespace only', "$B -e '   '")
    probe('e: repeated three times', "$B -e '1+1' -e '2*3' -e '7-4'")
    probe('e: leading/trailing spaces', "$B -e '   1+1   '")
    probe('e: spaced operators', "$B -e '1 + 2 * 3'")
    probe('e: pi constant', "$B -e 'pi + 1'")
    probe('e: exponent', "$B -e '2^10'")
    probe('e: division', "$B -e '10/4'")
    probe('e: embedded newline', "$B -e $'1+1\\n2+2'")
    probe('e: semicolon sequence', "$B -e '1+1; 2+2; 3+3'")
    probe('e: comment only', "$B -e '# just a comment'")
    probe('e: trailing comment', "$B -e '1+1 # trailing'")
    probe('e: bool expr', "$B -e 'true and false'")
    probe('e: parse command', "$B -e 'parse 1+2*3'")
    probe('e: parse unicode expr', "$B -e 'parse (x+1)^2'")
    probe('e: negative number', "$B -e '-5 + 3'")
    probe('e: unicode identifier π-look', "$B -e 'pi*pi'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
