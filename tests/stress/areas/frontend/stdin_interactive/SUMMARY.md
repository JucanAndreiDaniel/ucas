# SUMMARY — `stdin_interactive`

## Counts
- Distinct expressions/queries tried: >1100
- Goldens written: 27
- Files created: 56

### Counts

- **Distinct expressions / queries tried: >1100.** 1111 non-blank statements were
  fed to the binary across 26 input files (35 distinct CAS queries in `sin_basic.txt`,
  1000 distinct `i+1` statements in `sin_many.txt`, plus definitions, English
  requests, bracket/line-ending variants and the pty/repro scripts).
- **Files created in this folder: 56** — 14 `*.ucas`, 27 `*.out` goldens,
  12 `sin_*.txt` stdin inputs (`sin_filearg.ucas` included in the .ucas count),
  3 Python helpers (`run_stdin.py` golden runner, `pty_probe.py`, `repro_edgecases.py`),
  plus `FINDINGS.md` and this `SUMMARY.md`.
- **Golden tests:** all 14 `.ucas` files and all 14 stdin scenarios driven by
  `run_stdin.py` were run twice and `diff`ed — all deterministic.
- **Issues by severity:** CRASH 1, WRONG 4, LIMIT 2, DETERMINISM 1 (plus a list of
  verified clean/non-issues in `FINDINGS.md`).


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| WRONG | 4 | — |
| LIMIT | 2 | — |
| DETERMINISM | 1 | — |

### Issues at a glance

| # | Severity | One-line reproducer / takeaway |
|---|----------|--------------------------------|
| 1 | CRASH | `python3 -c 'print("("*1600+"1"+")"*1600,end="")' \| timeout 10 ucas` → exit 139 (SIGSEGV); safe at 1500. |
| 2 | WRONG | `printf '(1+\n2)\n' \| ucas` → parse errors, no `3`; indented continuation works. REPL `... ` prompt disagrees with lexer's indentation rule. |
| 3 | WRONG | `python3 -c 'print("1+"*5000+"1",end="")' \| ucas` → two outputs (`4096`,`905`); 8192-byte `fgets` splits one expression. |
| 4 | WRONG | `printf '...square root of x plus 1\n1+1\n2+2\n' \| ucas -i` → `1+1` consumed as the answer; `2` missing. Also on a tty. |
| 5 | WRONG | `printf '1+2\n' \| script -qec 'ucas > /tmp/p' /dev/null` → `/tmp/p` contains `ucas> 3` / `ucas> `; prompts leak when stdout is redirected. |
| 6 | LIMIT | `printf '1 + \\\n2\n' \| ucas` → backslash-newline continuation broken in the REPL. |
| 7 | LIMIT | `defer` file with an ambiguity drops later statements in the same buffer. |
| 8 | DETERMINISM | TTY echo vs prompt ordering under `script -qec` is racy; no pty golden kept. |


## Takeaway
EOF/CRLF/blank-line/directory/1000-statement handling is clean, but the REPL has three concrete correctness problems — a stack-overflow crash on deep nesting, a bracket-continuation rule that contradicts its own `...

### Original takeaway (verbatim)

EOF/CRLF/blank-line/directory/1000-statement handling is clean, but the REPL has
three concrete correctness problems — a stack-overflow crash on deep nesting, a
bracket-continuation rule that contradicts its own `... ` prompt, and an 8192-byte
line split that silently turns one statement into two — plus interactive prompt
leakage and answer-reading that can swallow the next statement.
