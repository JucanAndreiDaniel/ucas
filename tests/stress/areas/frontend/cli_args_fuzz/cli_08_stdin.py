#!/usr/bin/env python3
"""stdin / REPL: bare invocation, multiple lines, bracket continuation, the 8192-byte line-buffer split, CRLF, blank lines, and stdin-vs--e priority.

Ported from cli_08_stdin.sh. Each probe runs the same shell command string under
``sh -c`` with a 15-second subprocess timeout and a byte-identical report.
"""

import sys

from _probe import probe, VARS



def main():
    probe('stdin: bare /dev/null', '$B </dev/null')
    probe('stdin: one line', "printf '1+1\\n' | $B")
    probe('stdin: three lines', "printf '1+1\\n2+2\\n3+3\\n' | $B")
    probe('stdin: no trailing newline', "printf '1+1' | $B")
    probe('stdin: blank lines', "printf '\\n\\n1+1\\n\\n' | $B")
    probe('stdin: comment line', "printf '# hi\\n1+1\\n' | $B")
    probe('stdin: error then valid', "printf '1+\\n1+1\\n' | $B")
    probe('stdin: CRLF', "printf '1+1\\r\\n2+2\\r\\n' | $B")
    probe('stdin: semicolon line', "printf '1+1;2+2\\n' | $B")
    probe('stdin: 8001-char line (fits buffer)', '$B < midlongline.txt')
    probe('stdin: 10001-char line (SPLIT bug)', '$B < longline.txt')
    probe('stdin: -e wins, stdin ignored', "printf '2+2\\n' | $B -e '1+1'")
    probe('stdin: def then use', "printf 'f(x)=x^2\\nf(3)\\n' | $B")
    probe('stdin: multi-line parens', "printf '(1 +\\n 2 +\\n 3)\\n' | $B")
    probe('stdin: tab-separated', "printf '1\\t2\\n' | $B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
