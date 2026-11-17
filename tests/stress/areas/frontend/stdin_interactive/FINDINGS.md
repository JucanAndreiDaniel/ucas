# Stress findings — `stdin_interactive`

_Original heading: FINDINGS — `stdin_interactive`_

# FINDINGS — `stdin_interactive`

Area: interactive/stdin behaviour of `$ROOT/ucas`.
All runs were bounded with `timeout`. Golden files in this folder are deterministic
(each was run twice and `diff`ed); hangs, crashes and racy TTY cases are documented
here instead of being added as goldens.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | SIGSEGV on deeply nested parentheses |
| WRONG | 4 | REPL multi-line continuation disagrees with the lexer (non-indented lines split a statemen… |
| LIMIT | 2 | backslash-newline line continuation is broken in the REPL |
| DETERMINISM | 1 | TTY echo/prompt interleaving is racy under `script -qec` |

## Findings

### CRASH-1 — SIGSEGV on deeply nested parentheses
**Severity:** CRASH
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (stdin):
```sh
python3 -c 'print("("*1600 + "1" + ")"*1600, end="")' | \
  timeout 10 $ROOT/ucas >/dev/null 2>&1; echo $?
```
**Observed:** `139` (SIGSEGV), `timeout: the monitored command dumped core`.
The same input via a file argument also exits `139`.

Threshold measured: depth 1500 → exit 0; depth 1600 → exit 139
(and 1700/1800/1900/2000/3000/5000 all crash). The single-line input is
only 3201 bytes, well under the REPL's 8192-byte `fgets` buffer, so this is
parser recursion overflowing the stack, not a line-splitting artefact.
**Reproducer:**
Reproducer script: `repro_edgecases.py`.

**Expected:** either evaluate the expression or report a clean "nesting too deep"
error with exit 0. A crash on syntactically valid input is a bug.

### WRONG-1 — REPL multi-line continuation disagrees with the lexer (non-indented lines split a statement)
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
```sh
printf '(1+\n2)\n' | $ROOT/ucas
```
**Observed:**
```
<stdin>:1:4: error: expected an expression
    (1+
       ^
<stdin>:2:2: error: unexpected ')' after the statement
    2)
     ^
```
No `3` is ever printed. With an indented continuation line the *same*
expression works:
```sh
printf '(1+\n 2)\n' | $ROOT/ucas   # -> 3
```
Even worse, an inner line is evaluated standalone:
```sh
printf '(\n1+2\n)\n' | $ROOT/ucas
```
```
<stdin>:1:2: error: expected an expression
    (
     ^
3
<stdin>:3:1: error: unexpected ')'
    )
    ^
```
The `1+2` that is syntactically inside the parentheses is executed as a
separate statement (prints `3`) even though the enclosing expression failed.

**Why it matters:** `repl()` in `main.c` counts `(`, `[`, `{` to decide when to
show the `... ` continuation prompt and when to submit a buffered statement.
It therefore promises that an unclosed `(` continues onto the next line. But
`lex.c` (lines 147–161) explicitly sets `depth = 0` at a newline unless the
next line starts with a space or tab. The two mechanisms disagree: the user
sees `... ` and types a normal (unindented) continuation, and the statement is
then split into several, producing errors and/or partial, wrong evaluations.
Golden `06_multiline_unindented.ucas/.out` captures the stable error output;
`05_multiline_indented.ucas/.out` shows the correct behaviour.

### WRONG-2 — lines longer than 8191 bytes are split into separate statements
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
```sh
python3 -c 'print("1+"*5000 + "1", end="")' | \
  $ROOT/ucas
```
**Observed:**
```
4096
905
```
One arithmetic expression (5001 terms, value `5001`) is turned into two
independent statements. The `fgets(line, 8192, stdin)` in `repl()` reads only
8191 bytes at a time; with no brackets the depth stays 0, so each chunk is
submitted to `run_text()` separately. The first 8191 bytes evaluate to
`4096`, the remainder (`905` terms plus a dangling `+`) to `905`. A chunk
boundary can also fall in the middle of a token (number, identifier), silently
corrupting it.

**Expected:** one expression, one result (`5001`). Golden: `sin_long.txt/.out`.

### WRONG-3 — an ambiguity question consumes the next stdin line as its answer (statement silently swallowed)
**Severity:** WRONG
**Reproducer:**
```sh
printf 'the square root of x plus 1\n1+1\n2+2\n' | \
  $ROOT/ucas -i
```
**Observed:** (tail):
```
    which? [1]   ucas: it(x) = sqrt(x) + 1
  ucas: show it
it(x: real) = sqrt(x) + 1
  -> real
4
```
`1+1` is consumed by `fgets()` in `clarify()` as the reply to "which reading
of 'the square root of'?" (`1` selects the default). Its result `2` is
missing; only `4` (from `2+2`) is printed.

The same happens on a real terminal without `-i` (because `interactive()` is
true when stdin and stdout are ttys). Reproducer (see `pty_probe.py` section 4):
```sh
printf 'the square root of x plus 1\n7+7\n' | \
  script -qec $ROOT/ucas /dev/null
```
`7+7` is read as an invalid answer ("a number from 1 to 2"), the question is
asked again, and `7+7` is never executed as a statement.

**Why it matters:** with piped input (`-i` forces this) there is no way to tell
an answer line from a statement line, so statements are silently dropped.
**Expected:** a batch/ piped session should never read answers from stdin, or
should clearly mark the consumed line. Golden `sin_ambig_i.txt/.out` captures
the deterministic `-i` case (not a golden for the racy TTY echo).

### WRONG-4 — REPL prompts leak into redirected / piped stdout
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (stdin is a tty, stdout is a file):
```sh
rm -f /tmp/pty_leak
printf '1+2\n' | script -qec \
  '$ROOT/ucas > /tmp/pty_leak' /dev/null >/dev/null 2>&1
cat -A /tmp/pty_leak
```
**Observed:**
```
ucas> 3$
ucas> ```
`ucas> ` prompts are written into the file/pipe even though stdout is not a
terminal. `repl()` decides to prompt from `isatty(0)` alone.

Inconsistency: the NLP frontend's `interactive()` requires
`isatty(0) && isatty(1)`. With stdout redirected, the ambiguous sentence in
`the square root of x plus 1` uses its default reading (note printed, no
question) — yet the REPL still prints `ucas> ` prompts. With stdin piped and
stdout a tty, the mirror case happens: no prompt at all.

**Expected:** prompts only when the output is interactive, i.e. gated on stdout
being a tty (or on both stdin and stdout being ttys). See `pty_probe.py`
sections 1–3.

### LIMIT-1 — backslash-newline line continuation is broken in the REPL
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf '1 + \\\n2\n' | $ROOT/ucas
```
**Observed:**
```
<stdin>:2:1: error: expected an expression
    
    ^
2
```
`lex.c` treats `\` + newline as a continuation marker, but `repl()` submits
each line separately (bracket depth 0), so the backslash line is parsed alone
and the following line is parsed as a separate `2`. The intended `1 + 2` is
never evaluated. See `repro_edgecases.py`.

### LIMIT-2 — `defer` mode silently drops later statements in the same buffer
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf '\036defer\nthe square root of x plus 1\n9+9\n4*4\n' > /tmp/d.ucas
$ROOT/ucas /tmp/d.ucas
```
**Observed:**
```
> the square root of x plus 1
^^ask choice 2
? what does "the square root of" apply to:
  1) sqrt(x) + ...  (default)
  2) sqrt(x + ...)
```
`9+9` and `4*4` are not executed: `run_text_plain()` breaks on `nlp_asked`.
This is by design for a front end that re-runs the whole buffer with answers,
but it means a single batch run silently drops every statement after the
first ambiguity. In the REPL each line is its own buffer, so only the
ambiguous line is held back (the following lines still run) — an
inconsistency between file and stdin modes.

### DETERMINISM-1 — TTY echo/prompt interleaving is racy under `script -qec`
**Severity:** DETERMINISM
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (run several times):
**Observed:**
```sh
printf '1+2\n' | script -qec $ROOT/ucas /dev/null | cat -A
```
Both of these orderings were observed across runs:
```
1+2^M$                      ucas> 1+2^M$
ucas> 3^M$          and      3^M$
ucas>                         ucas> ^M$
```
The pty line discipline echoes the typed input while `ucas` is concurrently
printing its prompt to stdout. The *values* are correct and the process exits
0 each time, but the byte stream is not reproducible, so no golden `.out` is
kept for pty scenarios. The non-TTY scenarios in this folder are all
deterministic (each verified by a double run and `diff`).

## Checks that passed

### Clean / non-issues (verified, no bug found)
- **EOF mid-expression** (`printf '1 + (2 * 3' | ucas`): clean parse error,
  exit 0, no hang (`sin_eof_mid`).
- **EOF after a definition / no trailing newline** (`12_definition_eof`,
  `sin_no_newline`): clean exit 0; last statement is executed.
- **Blank lines, whitespace-only lines** (`01_blank_lines`, `sin_blank`): ignored.
- **CRLF single-line input** (`02_crlf`, `sin_crlf`): handled; same values as LF.
- **Ctrl-D** (empty input on a pty): prints one prompt then exits 0; mid-expression
  Ctrl-D produces the same clean error as EOF.
- **stdin from a directory** (`ucas < .`): `fgets` returns NULL, exit 0, no output
  (`sin_dir`), no hang/crash.
- **Mixing a file argument with piped stdin** (`ucas file.ucas < input`): stdin is
  ignored (`ran=1` suppresses `repl()`), exit 0 (`sin_mixed`).
- **Pipes closing early (SIGPIPE)** (`yes 1+1 | ucas | head -1`): ucas exits 141
  (SIGPIPE) promptly, no hang.
- **1000 statements** (`sin_many`): all 1000 executed, no state loss, exit 0.
