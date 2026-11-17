# Stress findings — `parser_error_recovery`

_Original heading: FINDINGS — `parser_error_recovery`_

# FINDINGS — `parser_error_recovery`

**Area.** What happens *after* a syntax error: per-statement recovery, line/column
positions, cascading errors, leaked state, and `--json` / `--mcp` session usability.

**Corpus.** 173 `.ucas` files (each: a malformed statement followed by `bigint 2^N`
sentinels and, where relevant, `show NAME` / `range NAME` checks), 5 wire files
(`json_*`, `mcp_*`, one `--flat`). 178 `.out` goldens. All runs bounded by
`timeout 15` (wire: 30), binary `$ROOT/ucas`. Every would-be
golden was run twice and `diff`ed; **no nondeterminism, no crash, no hang** was
found in any kept file. Adversarial sweeps (100 trailing-operator lines, 100
unclosed brackets, 1000 bad statements, NUL / invalid UTF-8, 10 KB unterminated
string) also completed within the timeout.

Note on golden line numbers: each `.ucas` has a one-line `# comment` header, so
statement 1 is reported at line 2.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 5 | 1 — A trailing operator (or unclosed bracket) at end of line swallows the following lines,… |
| LIMIT | 1 | 1 — Lexical errors abort the whole file (no per-statement recovery) |

## Findings

### WRONG-1 — 1 — A trailing operator (or unclosed bracket) at end of line swallows the following lines, silently turning command keywords into variables
**Severity:** WRONG
_Original classification: `WRONG (silent misparse + wrong error location + dropped statements`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_error_recovery
timeout 15 $ROOT/ucas 172_cont_chain.ucas
```

**Observed:**
```
> show 1 +
_(show: real, bigint: real) = 2show + 1 + bigint*real(7^30)
  -> real
> bigint 2^172
...
```
The three physical lines
```
show 1 +
  show 2 +
  bigint 7^30
```
were merged into **one** expression: `show` and `bigint` (command words) were
read as *variables*, and no error at all was emitted for the two swallowed
statements. Only the fourth line (`bigint 2^172`) executed as intended.

Related, with an unclosed bracket (`173_unclosed_bracket_swallow.ucas`):
```
> show [1, 2,
    bigint 7^31
173_unclosed_bracket_swallow.ucas:4:1: error: expected ']', found 'bigint'
    bigint 2^173
    ^
```
The valid `bigint 7^31` on line 3 was consumed into the bracket; the error is
reported at **line 4**, pointing at the *next* statement (`bigint 2^173`), not at
the unclosed bracket on line 2.

Also `008_paren_continuation.ucas` (`show (1 +` followed by `  bigint 4^10`)
reports `...:3:14: error: expected ')', found 'eol'` and never runs `bigint 4^10`.

**Why it matters:** it is a bug.** A syntax error should be confined to one statement. Here a
dangling operator makes the parser keep reading past the newline, so valid
statements are silently lost or reinterpreted as identifiers, and the diagnostic
names a different line than the one containing the fault. This is the opposite
of error recovery. (Statements that end in a *complete* expression but an open
delimiter, e.g. `show (1 + 2`, do **not** swallow the next line — see
`129_cascade_unclosed_swallow` — so the defect is specifically the trailing
operator.)

### WRONG-2 — 2 — A failed definition leaks its name as a free variable; resolution is inconsistent between commands
**Severity:** WRONG
_Original classification: `WRONG (state corruption / misleading analysis`._
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_error_recovery
timeout 15 $ROOT/ucas 099_fn_body_stray.ucas
timeout 15 $ROOT/ucas 132_state_failed_def_name.ucas
```

**Observed:** (`099_fn_body_stray.ucas`)
```
> f(x: u8) = x + )
099_fn_body_stray.ucas:2:16: error: unexpected ')'
    f(x: u8) = x + )
                   ^
> bigint 2^108
...
> show f
_(f: real) = f
  -> real
```
The definition failed, yet `show f` reports a *real free variable* `f` instead
of "undefined". `range f` then silently analyses that phantom variable over
`[-10, 10]` (`132_state_failed_def_name.ucas`). Worse, the same phantom is
resolved differently depending on the command:
```
> show alpha
_(alpha: real) = alpha      # free variable
> range alpha
range of alpha: [-10, 10] ...   # analysed
> bigint alpha(3)
...:5:8: error: bigint: unknown function alpha/1   # "not defined" here
```
If the leaked name is `w` or `z` it even inherits the complex default
(`137_state_w_complex.ucas`: `_(w: complex) = w` with a "taken as complex" note).

Over the wire the same inconsistency appears (`json_recovery.jsonl`): `define`
with body `x + )` returns `ok:false, parse_error`; `state` then lists **no** such
function (`functions:["ok"]`), but a later `show bad` returns
`_(bad: real) = bad`.

**Why it matters:** it is a bug.** A client cannot tell whether the definition exists.
Downstream `show` / `range` silently analyse a made-up variable and return
plausible-looking numbers instead of an error.
**Expected:** the failed name is
undefined everywhere (or a partial definition is explicitly exposed in state).

### WRONG-3 — 3 — Error columns are counted in UTF-8 bytes, not characters (multibyte Unicode shifts the caret)
**Severity:** WRONG
_Original classification: `WRONG (wrong position; error does not point at the bad token`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_error_recovery
printf 'parse p + )\nbigint 2^2\n' > /tmp/opencode/per/a.ucas
printf 'parse \xcf\x80 + )\nbigint 2^2\n' > /tmp/opencode/per/b.ucas
timeout 10 $ROOT/ucas /tmp/opencode/per/a.ucas | sed -n '2,4p'
timeout 10 $ROOT/ucas /tmp/opencode/per/b.ucas | sed -n '2,4p'
```
(kept as goldens `156_col_pi.ucas`, `157_col_oplus.ucas`, `158_col_leq.ucas`)

**Observed:**
```
a.ucas:1:11: error: unexpected ')'
    parse p + )
              ^
b.ucas:1:12: error: unexpected ')'
    parse π + )
               ^
```
`)` is the 11th *character* in both lines. With the 2-byte `π` it is reported as
column **12** and the caret is drawn one cell past the `)`. With `⊕` (3 bytes),
`157_col_oplus` reports column 17 where the character column is 15 (+2),
confirming byte counting.

**Why it matters:** it is a bug.** Diagnostics for any line containing a non-ASCII character
before the fault point at the wrong column and render a misaligned caret —
exactly when precise positions matter most.

### WRONG-4 — 4 — A leading stray operator makes the command keyword itself a variable, with no error
**Severity:** WRONG
_Original classification: `WRONG (silent misparse; no diagnostic identifies the bad statement`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_error_recovery
timeout 15 $ROOT/ucas 029_leading_plus.ucas
timeout 15 $ROOT/ucas 038_stray_question.ucas
```

**Observed:**
```
> show + 1
_(show: real) = show + 1
  -> real
> parse ? x : y
_(parse: real, x: real, y: real) = parse != 0 ? x : y
  -> real
```
`show + 1` is not an error: it defines a function whose parameter is named
`show`. `parse ? x : y` similarly makes `parse` a variable. `show * 1`,
`range + 1`, `bigint + 1`, `equiv + 1 2` behave the same way (files
`148`–`155`).

**Why it matters:** it is a bug.** A command word followed by an operator is unambiguously
malformed; it should produce a `parse_error` naming the offending statement,
not a silent success that mutates the session with a variable named after a
built-in command.

### LIMIT-1 — 1 — Lexical errors abort the whole file (no per-statement recovery)
**Severity:** LIMIT
_Original classification: `LIMIT (documented-style behavior, but destructive`._
**Expected:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_error_recovery
for f in 087_unterminated_double 092_unicode_infinity 170_nul_truncation; do
  timeout 10 $ROOT/ucas $f.ucas
done
```

**Observed:** no `> ...` echo at all; statements before and after are lost:
```
087_unterminated_double.ucas:2:6: error: unexpected character '"'
    show "unterminated
         ^
092_unicode_infinity.ucas:2:7: error: unexpected character '?'
    parse ∞
          ^
170_nul_truncation.ucas:2:10: error: expected an expression
    show 1 + 
             ^
```
A bare `"` (unterminated string) and unsupported Unicode (`∞`, `⁴`, CJK, emoji)
abort lexical analysis for the whole file; a NUL byte also truncates everything
after it (the sentinel `bigint 2^170` never runs). By contrast *parse* errors are
recovered per statement.

**Why it matters:** it matters.** One stray byte discards all work in a large `.ucas` file.
At minimum a client should be told which statements were lost. (Same class as
`parser_json_fuzz` LIMIT-1; reproduced here with trailing valid statements.)

### WRONG-5 — 5 — JSON `ucas` response has `ok:false` but still carries successful `result` / `results`
**Severity:** WRONG
_Original classification: `WRONG (wire-protocol inconsistency`._
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/frontend/parser_error_recovery
timeout 30 $ROOT/ucas --json --files none < json_mixed_result.jsonl
```

**Observed:** (first response, abbreviated):
```json
{"id":1,"ok":false,"cmd":"ucas","structured":true,
 "result":{"kind":"bigint","value":"243",...},
 "results":[{"kind":"show","definition":"_(bad: real) = bad",...},
            {"kind":"bigint","value":"243",...}],
 "text":"> bad(...) ... error ... > show bad ... > bigint 3^5 ...",
 "error":{"code":"parse_error","message":"unexpected ')'","pos":{"line":1,"col":18}}}
```
`ok:false` and an `error` are set, yet `structured:true`, `result` (the last
statement's value) and `results` (the two statements after the error) are also
present. A client that branches on `ok` discards valid results; one that reads
`result` treats the request as successful.

**Why it matters:** it is a bug.** A single response must have an unambiguous success/failure
meaning.
**Expected:** either `ok:true` with per-statement errors reported separately,
or `ok:false` with no success payload fields.

## Checks that passed

### POSITIVE — The session stays usable after parse errors (CLI, `--json`, `--mcp`, `--flat`)
No crash or hang was observed, and later statements/calls keep working:

- CLI: in all 173 `.ucas` goldens, `bigint 2^N` sentinels after a malformed
  statement execute (except the whole-file lexical aborts of LIMIT-1).
- `--json`: `json_recovery.jsonl` ids 3/4/6/8/9/10/11 succeed after parse errors
  at ids 2 and 5.
- `--mcp`: `mcp_recovery.jsonl` ids 3/4/6/8/9 succeed after errors at 2/5/7/9.
- `--mcp --flat`: `mcp_flat_recovery.jsonl` ids 4/5/6/7 succeed after the error
  at id 3.
- Error objects carry the documented `parse_error` code and a `pos`
  `{line, col}` (except WRONG-3/WRONG-1 above, where the position is misleading).

### Test inventory (what is covered)
| Group | Files | Examples |
|---|---|---|
| unmatched `(`, `[`, `{` and extra closers | 1–24 | `008_paren_continuation`, `016_bracket_unclosed_index` |
| stray operators (`+ +`, `* *`, `= =`, `!`, `->`, `..`, `:`) | 25–38 | `025_stray_plus`, `038_stray_question` |
| bad types, undefined names, annotations | 39–63 | `040_type_empty`, `052_undef_in_def` |
| incomplete definitions | 64–71 | `064_def_no_body`, `068_def_unclosed_params` |
| bad `match` / `where` | 72–86 | `080_match_in_def`, `082_where_trailing` |
| unterminated strings, bad Unicode, NUL | 87–98, 170–171 | `087_unterminated_double`, `170_nul_truncation` |
| errors inside functions / loops / `if` | 99–116 | `099_fn_body_stray`, `102_fn_loop_bad`, `109_if_then_else` |
| position / cascading / state | 117–139, 156–173 | `173_unclosed_bracket_swallow`, `156_col_pi` |
| trailing-operator swallow / command-word capture | 140–155 | `147_cont_chain_swallow`, `148_cmd_show_plus` |
| wire (JSON / MCP / flat) | 5 `.jsonl` | `json_mixed_result`, `mcp_flat_recovery` |

Every issue above has a deterministic reproducer kept as a golden (or, for the
wire inconsistency, as a `.jsonl` + `.out` pair), so the catalog is runnable by
`tests/stress/run.sh`.
