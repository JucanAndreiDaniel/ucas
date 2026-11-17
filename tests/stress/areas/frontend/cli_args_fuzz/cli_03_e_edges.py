#!/usr/bin/env python3
"""-e edge cases: flag-looking values consumed as text, missing value, interleaving with files/flags, huge expressions, control characters.

Ported from cli_03_e_edges.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS



def main():
    probe('e-edge: value --json consumed as text', '$B -e --json </dev/null')
    probe('e-edge: value -q consumed as text', '$B -e -q')
    probe('e-edge: value --help consumed as text', '$B -e --help | head -3')
    probe('e-edge: value --sat-selftest consumed', '$B -e --sat-selftest | head -3')
    probe('e-edge: value --mcp consumed as text', '$B -e --mcp | head -3')
    probe('e-edge: value -e consumed as text', '$B -e -e')
    probe('e-edge: missing value (trailing -e)', '$B -e')
    probe('e-edge: empty then real', "$B -e '' -e '1+1'")
    probe('e-edge: real then empty', "$B -e '1+1' -e ''")
    probe('e-edge: -e, file, -e', "$B -e '1+1' fixtures/eq.ucas -e '2+2'")
    probe('e-edge: -q between -e', "$B -e '1+1' -q -e '2+2'")
    probe('e-edge: tab in value', "$B -e $'1+1\\t2+2'")
    probe('e-edge: CR in value', "$B -e $'1+1\\r2+2'")
    probe('e-edge: 2000-term expression', '$B -e \\"\\$(python3 -c \'print(\\"1+\\"*1999+\\"1\\")\')\\"')
    probe('e-edge: 100k-char expression', '$B -e \\"\\$(python3 -c \'print(\\"1+\\"*50000+\\"1\\")\')\\"')
    probe('e-edge: many statements (500)', '$B -e \\"\\$(python3 -c \'print(\\";\\".join([\\"7\\"]*500))\')\\" | tail -2')
    return 0


if __name__ == "__main__":
    sys.exit(main())
